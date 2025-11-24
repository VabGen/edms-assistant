# rag_graph_advanced.py
import logging
import os
import pickle
from typing import List, Dict, Any, TypedDict, Optional
from datetime import datetime

import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_community.document_loaders import UnstructuredExcelLoader
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
import redis

# === Настройка логирования ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === Глобальные переменные (для FastAPI) ===
VECTOR_STORES: Dict[str, FAISS] = {}
DOCUMENT_MAP: Dict[str, Any] = {}

# === Кэш: на диске или Redis ===
class CacheManager:
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_path = os.path.join(self.cache_dir, "answers.pkl")
        self.cache = {}
        self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "rb") as f:
                    self.cache = pickle.load(f)
                logger.info(f"💾 Кэш загружен: {len(self.cache)} записей")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки кэша: {e}")

    def save_cache(self):
        try:
            with open(self.cache_path, "wb") as f:
                pickle.dump(self.cache, f)
            logger.info(f"💾 Кэш сохранён: {len(self.cache)} записей")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения кэша: {e}")

    def get(self, key: str) -> Optional[str]:
        return self.cache.get(key)

    def set(self, key: str, value: str, ttl=3600):
        self.cache[key] = value
        self.save_cache()

cache_manager = CacheManager()

# === Модель для маршрутизации ===

class FileSelection(BaseModel):
    filename: str
    reason: str

# === Класс ModelClient ===

class ModelClient:
    def __init__(
        self,
        embedding_base_url: str,
        generative_base_url: str,
        embedding_model: str,
        generative_model: str
    ):
        self.llm = ChatOpenAI(
            api_key="not-needed",
            base_url=generative_base_url,
            model=generative_model,
            temperature=0.6,
        )
        try:
            self.embeddings = OpenAIEmbeddings(
                api_key="not-needed",
                base_url=embedding_base_url,
                model=embedding_model,
            )
            logger.info("✅ Embeddings успешно инициализированы.")
            self.embeddings_available = True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации embeddings: {e}")
            self.embeddings_available = False

    async def agenerate(self, prompt: str, system_prompt: str = None) -> str:
        messages = []
        if system_prompt:
            messages.append(("system", system_prompt))
        messages.append(("user", prompt))
        response = await self.llm.ainvoke(messages)
        return response.content

# === Загрузка документов с поддержкой .xlsx ===

def get_loader(file_path: str):
    ext = file_path.lower().split(".")[-1]
    if ext == "docx":
        return Docx2txtLoader(file_path)
    elif ext == "pdf":
        return PyPDFLoader(file_path)
    elif ext == "txt" or ext == "md":
        return TextLoader(file_path, encoding="utf-8")
    elif ext == "xlsx" or ext == "xls":
        return UnstructuredExcelLoader(file_path, mode="elements")
    else:
        raise ValueError(f"Формат {ext} не поддерживается")

async def load_and_index_all_documents(
    documents_dir: str = "data/documents",
    vector_store_dir: str = "data/vector_stores",
    embedding_base_url: str = "http://model-embedding.shared.du.iba/v1",
    embedding_model: str = "embedding-model",
    batch_size: int = 1,
    chunk_size: int = 500,
    chunk_overlap: int = 100
):
    """Загружает все документы и создаёт отдельный vector store для каждого"""
    global VECTOR_STORES

    model_client = ModelClient(
        embedding_base_url=embedding_base_url,
        generative_base_url="http://model-generative.shared.du.iba/v1",
        embedding_model=embedding_model,
        generative_model="generative-model"
    )

    if not model_client.embeddings_available:
        raise RuntimeError("Embeddings недоступны")

    os.makedirs(vector_store_dir, exist_ok=True)

    for filename in os.listdir(documents_dir):
        file_path = os.path.join(documents_dir, filename)
        if not os.path.isfile(file_path):
            continue

        store_dir = os.path.join(vector_store_dir, os.path.splitext(filename)[0])
        os.makedirs(store_dir, exist_ok=True)

        index_file = os.path.join(store_dir, "index.faiss")
        if os.path.exists(index_file):
            try:
                vector_store = FAISS.load_local(
                    store_dir,
                    model_client.embeddings,
                    allow_dangerous_deserialization=True
                )
                VECTOR_STORES[filename] = vector_store
                logger.info(f"✅ Векторное хранилище загружено: {filename}")
                continue
            except Exception as e:
                logger.warning(f"⚠️ Не удалось загрузить {filename}, пересоздаём: {e}")

        # Загружаем и индексируем
        try:
            loader = get_loader(file_path)
            docs = loader.load()

            # Обработка таблиц...
            if any("table" in doc.metadata.get("type", "").lower() for doc in docs):
                logger.info(f"📄 Обнаружены таблицы в {filename}, преобразуем в текст...")
                cleaned_docs = []
                for doc in docs:
                    if doc.metadata.get("type") == "table":
                        table_text = doc.page_content.replace("\n", " | ").replace("  ", " ")
                        cleaned_docs.append(
                            type(doc)(
                                page_content=f"Таблица из {filename}:\n{table_text}",
                                metadata={**doc.metadata, "source": filename, "type": "table"}
                            )
                        )
                    else:
                        cleaned_docs.append(doc)
                docs = cleaned_docs

            # ИСПОЛЬЗУЕМ ПАРАМЕТРЫ
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            split_docs = text_splitter.split_documents(docs)

            # Обработка по батчам с переданным batch_size
            vector_store = None
            for i in range(0, len(split_docs), batch_size):
                batch = split_docs[i:i + batch_size]
                try:
                    if vector_store is None:
                        vector_store = FAISS.from_documents(batch, model_client.embeddings)
                    else:
                        vector_store.add_documents(batch)
                    # logger.info(f"✅ Обработан батч {i//batch_size + 1} для {filename}")
                except Exception as e:
                    logger.error(f"❌ Ошибка в батче {i//batch_size + 1} для {filename}: {e}")
                    continue

            if vector_store is not None:
                vector_store.save_local(store_dir)
                VECTOR_STORES[filename] = vector_store
                logger.info(f"✅ Документ проиндексирован: {filename}")
            else:
                logger.error(f"❌ Не удалось проиндексировать {filename}")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка при индексации {filename}: {e}")
            continue

# === Маршрутизация: выбрать файл ===

async def route_question_to_file(
    question: str,
    chat_history: List,
    embedding_base_url: str = "http://model-embedding.shared.du.iba/v1",
    generative_base_url: str = "http://model-generative.shared.du.iba/v1"
) -> str:
    model_client = ModelClient(
        embedding_base_url=embedding_base_url,
        generative_base_url=generative_base_url,
        embedding_model="embedding-model",
        generative_model="generative-model"
    )

    files_list = list(VECTOR_STORES.keys())
    if not files_list:
        return "СЭД.docx"

    prompt = f"""
Ты эксперт по маршрутизации запросов в системе электронного документооборота.
Доступные файлы: {files_list}

Пользователь спрашивает: "{question}"

История чата: {chat_history}

Выбери ОДИН файл, в котором, скорее всего, есть ответ.
Ответь ТОЛЬКО в формате JSON:
{{
  "filename": "имя_файла",
  "reason": "краткое объяснение, почему именно этот файл"
}}
"""

    try:
        response = await model_client.agenerate(prompt)
        import json
        result = json.loads(response)
        filename = result.get("filename", "").strip()
        if filename in VECTOR_STORES:
            logger.info(f"🔍 Маршрутизация: '{question}' → {filename} ({result.get('reason', 'не указано')})")
            return filename
        else:
            logger.warning(f"⚠️ Выбран несуществующий файл: {filename}, используем СЭД.docx")
            return "СЭД.docx"
    except Exception as e:
        logger.error(f"❌ Ошибка маршрутизации: {e}")
        return "СЭД.docx"

# === RAG: поиск и генерация ===

async def retrieve_and_generate(
    question: str,
    filename: str,
    chat_history: List,
    embedding_base_url: str = "http://model-embedding.shared.du.iba/v1",
    generative_base_url: str = "http://model-generative.shared.du.iba/v1"
) -> str:
    vector_store = VECTOR_STORES.get(filename)
    if not vector_store:
        return "❌ Файл не найден."

    # Поиск
    docs_with_scores = vector_store.similarity_search_with_score(question, k=5)
    relevant_docs = [doc for doc, score in docs_with_scores if score >= 0.5]

    if not relevant_docs and docs_with_scores:
        best_doc, _ = docs_with_scores[0]
        relevant_docs = [best_doc]

    if not relevant_docs:
        return "Не удалось найти информацию в этом файле."

    context = "\n\n".join([
        f"Источник: {doc.metadata.get('source', 'Unknown')}\n"
        f"Тип: {doc.metadata.get('type', 'text')}\n"
        f"Содержимое:\n{doc.page_content}"
        for doc in relevant_docs
    ])

    system_prompt = f"""Ты эксперт по СЭД. Отвечай только на основе контекста.
Если контекст не содержит ответ — скажи «Я не нашёл информацию в документах».
Не придумывай ничего от себя.

Контекст:
{context}
"""

    prompt = f"Вопрос: {question}\nИстория: {chat_history}\nОтвет:"
    model_client = ModelClient(
        embedding_base_url=embedding_base_url,
        generative_base_url=generative_base_url,
        embedding_model="embedding-model",
        generative_model="generative-model"
    )
    answer = await model_client.agenerate(prompt, system_prompt=system_prompt)

    # Проверка на "пустой" или "неизвестный" ответ
    if any(phrase in answer.lower() for phrase in [
        "я не нашёл", "не могу найти", "не указано", "неизвестно",
        "не содержится", "нет информации", "не нашёл", "не могу ответить"
    ]):
        return "REFLECT: Не найдено в этом файле"

    return answer

# === Рефлексия: если ответ плохой — попробовать другой файл ===

async def reflect_and_retry(
    question: str,
    chat_history: List,
    initial_file: str,
    embedding_base_url: str = "http://model-embedding.shared.du.iba/v1",
    generative_base_url: str = "http://model-generative.shared.du.iba/v1"
) -> str:
    """Если ответ плохой — попробуем другие файлы"""
    model_client = ModelClient(
        embedding_base_url=embedding_base_url,
        generative_base_url=generative_base_url,
        embedding_model="embedding-model",
        generative_model="generative-model"
    )

    other_files = [f for f in VECTOR_STORES.keys() if f != initial_file]
    if not other_files:
        return "Нет других файлов для проверки."

    logger.info(f"🔄 Рефлексия: ответ плохой, пробуем другие файлы: {other_files}")

    for alt_file in other_files:
        logger.info(f"🔁 Попытка в файле: {alt_file}")
        answer = await retrieve_and_generate(question, alt_file, chat_history, embedding_base_url, generative_base_url)
        if answer != "REFLECT: Не найдено в этом файле" and len(answer.strip()) > 20:
            logger.info(f"✅ Успешно найдено в файле: {alt_file}")
            return answer

    logger.info("❌ Рефлексия завершилась неудачно — возврат к первоначальному ответу")
    return "Я не нашёл информацию в доступных документах."

# === LangGraph State ===

class AgentState(TypedDict):
    question: str
    chat_history: List
    selected_file: str
    answer: str
    retry_count: int

# === Nodes ===

async def decide_file_node(state: AgentState) -> AgentState:
    filename = await route_question_to_file(
        state["question"],
        state["chat_history"],
        embedding_base_url=os.getenv("EMBEDDING_BASE_URL", "http://model-embedding.shared.du.iba/v1"),
        generative_base_url=os.getenv("GENERATIVE_BASE_URL", "http://model-generative.shared.du.iba/v1")
    )
    return {**state, "selected_file": filename}

async def retrieve_node(state: AgentState) -> AgentState:
    answer = await retrieve_and_generate(
        state["question"],
        state["selected_file"],
        state["chat_history"],
        embedding_base_url=os.getenv("EMBEDDING_BASE_URL", "http://model-embedding.shared.du.iba/v1"),
        generative_base_url=os.getenv("GENERATIVE_BASE_URL", "http://model-generative.shared.du.iba/v1")
    )
    return {**state, "answer": answer}

async def reflect_node(state: AgentState) -> AgentState:
    if state["answer"] == "REFLECT: Не найдено в этом файле" and state["retry_count"] < 2:
        logger.info(f"🔄 Запуск рефлексии (попытка {state['retry_count'] + 1}/2)")
        answer = await reflect_and_retry(
            state["question"],
            state["chat_history"],
            state["selected_file"],
            embedding_base_url=os.getenv("EMBEDDING_BASE_URL", "http://model-embedding.shared.du.iba/v1"),
            generative_base_url=os.getenv("GENERATIVE_BASE_URL", "http://model-generative.shared.du.iba/v1")
        )
        return {**state, "answer": answer, "retry_count": state["retry_count"] + 1}
    else:
        return state

# === Conditional Edge: если ответ плохой → рефлексия ===

def should_reflect(state: AgentState) -> str:
    if state["answer"] == "REFLECT: Не найдено в этом файле" and state["retry_count"] < 2:
        return "reflect"
    else:
        return "end"

# === Graph ===

def create_rag_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("decide_file", decide_file_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("reflect", reflect_node)

    workflow.set_entry_point("decide_file")
    workflow.add_edge("decide_file", "retrieve")
    workflow.add_conditional_edges(
        "retrieve",
        should_reflect,
        {
            "reflect": "reflect",
            "end": END
        }
    )
    workflow.add_edge("reflect", END)

    return workflow.compile()

# === Настройка логирования (для FastAPI) ===

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
# logger = logging.getLogger(__name__)