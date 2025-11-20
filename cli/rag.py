import asyncio
import logging
import os
from typing import List, Tuple
import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import Docx2txtLoader
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel
import docx2txt

print(docx2txt.__file__)

# === Настройка логирования ===

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# === Pydantic-схемы ===

class ModelConfig(BaseModel):
    generative_base_url: str = "http://model-generative.shared.du.iba/v1"
    generative_model: str = "generative-model"
    embedding_base_url: str = "http://model-embedding.shared.du.iba/v1"
    embedding_model: str = "embedding-model"

# === Клиент для вызова моделей ===

class ModelClient:
    def __init__(self, config: ModelConfig):
        self.config = config
        logger.info(f"🔧 Используется embedding_model: {self.config.embedding_model}")
        logger.info(f"🔧 Используется generative_model: {self.config.generative_model}")

        # Инициализация LLM
        self.llm = ChatOpenAI(
            api_key="not-needed",
            base_url=self.config.generative_base_url,
            model=self.config.generative_model,
            temperature=0.6,
        )

        try:
            self.embeddings = OpenAIEmbeddings(
                api_key="not-needed",
                base_url=self.config.embedding_base_url,
                model=self.config.embedding_model,
            )
            logger.info("✅ Embeddings успешно инициализированы.")
            self.embeddings_available = True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации embeddings: {e}")
            logger.info("💡 Embeddings недоступны. Будет использован кастомный поиск.")
            self.embeddings = None
            self.embeddings_available = False

    async def generate_text(self, prompt: str, system_prompt: str = None) -> str:
        messages = []
        if system_prompt:
            messages.append(("system", system_prompt))
        messages.append(("user", prompt))

        logger.info(f"🔄 [LLM] Отправка запроса к генеративной модели: {self.config.generative_base_url}")
        response = await self.llm.ainvoke(messages)
        logger.info("✅ [LLM] Ответ от генеративной модели получен.")
        return response.content

    async def embed_text(self, texts: list[str]) -> list[list[float]]:
        if not self.embeddings_available:
            raise RuntimeError("❌ Embeddings недоступны. Сервер не поддерживает /v1/embeddings.")
        logger.info(f"🔄 [EMBED] Отправка запроса к эмбеддинговой модели: {self.config.embedding_base_url}")
        result = await self.embeddings.aembed_documents(texts)
        logger.info("✅ [EMBED] Ответ от эмбеддинговой модели получен.")
        return result

# === Глобальные переменные ===

KNOWLEDGE_BASE_FILE = r"D:\project\edms-assistant\cli\doc\СЭД.docx"
VECTOR_STORE_DIR = r"D:\project\edms-assistant\cli\vector"

DOCS_IN_RETRIEVER = 15
RELEVANCE_THRESHOLD_DOCS = 0.5
RELEVANCE_THRESHOLD_PROMPT = 0.4

# === Функции для работы с Vector Store ===

def save_vector_store(vector_store, vector_store_dir: str):
    vector_store.save_local(vector_store_dir)
    print(f"Vector store сохранён в: {vector_store_dir}")

def load_vector_store(vector_store_dir: str, embeddings):
    index_file = os.path.join(vector_store_dir, "index.faiss")
    if not os.path.exists(index_file):
        print(f"Файл {index_file} не найден. Не удалось загрузить vector store.")
        return None
    try:
        vector_store = FAISS.load_local(
            vector_store_dir,
            embeddings,
            allow_dangerous_deserialization=True
        )
        print(f"Vector store загружен из: {vector_store_dir}")
        return vector_store
    except Exception as e:
        print(f"Ошибка при загрузке vector store: {e}")
        return None

# === Функция загрузки и индексации документа ===

import pickle

def save_docs_for_later(documents, filepath="D:\\project\\edms-assistant\\cli\\vector\\split_docs.pkl"):
    with open(filepath, "wb") as f:
        pickle.dump(documents, f)
    print(f"Чанки сохранены для повторной попытки: {filepath}")

def load_docs_from_disk(filepath="D:\\project\\edms-assistant\\cli\\vector\\split_docs.pkl"):
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            return pickle.load(f)
    return None

def load_and_index_documents(file_path: str, vector_store_dir: str, embeddings) -> bool:
    os.makedirs(vector_store_dir, exist_ok=True)

    vector_store = load_vector_store(vector_store_dir, embeddings)
    if vector_store:
        print("Существующий vector store успешно загружен.")
        return True

    # загрузить уже разделённые чанки из диска
    split_docs = load_docs_from_disk()
    if split_docs is None:
        documents = []
        if not os.path.exists(file_path):
            print(f"Файл {file_path} не найден.")
            return False

        if file_path.lower().endswith(".docx"):
            try:
                loader = Docx2txtLoader(file_path)
                doc_docs = loader.load()
                documents.extend(doc_docs)
                print(f"Добавлено {len(doc_docs)} страниц из {os.path.basename(file_path)}")
            except Exception as e:
                print(f"Ошибка при чтении {os.path.basename(file_path)}: {e}")
        else:
            print(f"Формат файла {file_path} не поддерживается.")
            return False

        if not documents:
            print("Не найдено подходящих документов для индексирования.")
            return False

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        split_docs = text_splitter.split_documents(documents)
        # -------------
        for i, doc in enumerate(split_docs[:5]):
            print(f"\n--- Чанк {i + 1} ---")
            print(doc.page_content)
            print(f"Метаданные: {doc.metadata}")
        print(f"Всего получено {len(split_docs)} чанков после разбиения.")
        # ------------

        # Сохраняем чанки, чтобы не перечитывать DOCX каждый раз
        save_docs_for_later(split_docs)

    # === пробуем создать векторное хранилище ===
    batch_size = 2
    vector_store = None

    for i in range(0, len(split_docs), batch_size):
        batch = split_docs[i:i + batch_size]
        print(f"Обработка батча {i // batch_size + 1}/{(len(split_docs) + batch_size - 1) // batch_size}...")

        try:
            if vector_store is None:
                vector_store = FAISS.from_documents(batch, embeddings)
            else:
                vector_store.add_documents(batch)
        except Exception as e:
            print(f"❌ Ошибка при обработке батча {i // batch_size + 1}: {str(e)}")
            print("💡 Подожди, пока embedding-сервер восстановится.")
            return False

    print("Документы успешно проиндексированы в FAISS.")
    save_vector_store(vector_store, vector_store_dir)
    return True

# === Предобработка запроса ===

async def preprocess_user_prompt(user_prompt: str, chat_history: list, model_client: ModelClient) -> str:
    instructions = (
        "Your task is to refine the user prompt below, preserving its meaning.\n"
        "Steps to follow:\n"
        "1. Identify the main question or request.\n"
        "2. If there are multiple tasks, list them.\n"
        "3. Keep the text concise and clear.\n\n"
        f"User prompt:\n{user_prompt}\n\n"
        "Chat history:\n"
        f"{chat_history}\n"
        "-----\n"
        "Now, provide the improved prompt below:\n"
    )
    system_prompt = "You are an assistant. Refine the user's prompt."
    response = await model_client.generate_text(instructions, system_prompt=system_prompt)
    improved_prompt = response.strip()
    return improved_prompt

# === Поиск похожих документов ===

def retrieve_documents(
        vector_store,
        user_prompt: str,
        k: int = 20,
        metadata_filters: dict = None
):
    """
    Выполняет поиск по векторному хранилищу FAISS (similarity search).
    Возвращает список кортежей (Document, score).
    """
    if not vector_store:
        print("Vector store не загружен. Сначала загрузите индекс.")
        return []

    try:
        if metadata_filters:
            docs_with_scores = vector_store.similarity_search_with_score(
                user_prompt,
                k=k,
                filter=metadata_filters
            )
        else:
            docs_with_scores = vector_store.similarity_search_with_score(user_prompt, k=k)
        return docs_with_scores
    except Exception as e:
        print(f"Ошибка при извлечении документов: {e}")
        return []

# === НЕ НУЖНО! Удаляем compute_embeddings_similarity_async ===
# (Оставляю только FAISS-оценки)

# === Проверка релевантности вопроса ===

def is_prompt_relevant_to_documents(relevance_scores, relevance_threshold=RELEVANCE_THRESHOLD_PROMPT) -> bool:
    try:
        if not relevance_scores:
            return False

        max_similarity = max((sim for _, sim in relevance_scores), default=0.0)
        logger.info(f"🔍 Максимальная оценка FAISS: {max_similarity:.4f}, порог: {relevance_threshold}")
        return max_similarity >= relevance_threshold
    except Exception as e:
        logger.error(f"Exception in is_prompt_relevant_to_documents: {str(e)}")
        return False

# === Постобработка ответа LLM ===

async def postprocess_llm_response(
        llm_response: str,
        user_prompt: str,
        context_str: str = "",
        references: dict = None,
        is_relevant: bool = False,
        model_client: ModelClient = None
) -> tuple:
    if references is None:
        references = {}

    prompt_references = (
        "You are an advanced language model tasked with providing a final, "
        "well-structured answer based on the given content.\n\n"
        "### Provided Data\n"
        f"LLM raw response:\n{llm_response}\n\n"
        f"User prompt:\n{user_prompt}\n\n"
        f"Context:\n{context_str}\n\n"
        f"References:\n{references}\n\n"
        f"is_relevant: {is_relevant}\n"
        "-------------------------\n"
        "Please re-check clarity and, if references exist, list them at the end.\n"
        "Return the final improved answer now:\n"
    )

    final_answer = await model_client.generate_text(prompt_references)
    return final_answer, references

# === Генерация ответа с контекстом ===

async def generate_response(
        prompt: str,
        model_client: ModelClient,
        chat_history=None,
        metadata_filters=None,
        context=None
):
    # Проверка доступности embeddings
    if not model_client.embeddings_available:
        print("❌ Embeddings недоступны. RAG функциональность не будет работать.")
        fallback_answer = "Embeddings недоступны, использую базовый ответ."
        return fallback_answer, None

    # 1. Загрузка/создание vector_store
    success = load_and_index_documents(KNOWLEDGE_BASE_FILE, VECTOR_STORE_DIR, model_client.embeddings)
    if not success:
        print("❌ Не удалось загрузить и индексировать документы.")
        return "Unable to load Vector Store.", None

    vector_store = load_vector_store(VECTOR_STORE_DIR, model_client.embeddings)
    logger.info(f"vector_store = {vector_store}")
    if not vector_store:
        return "Unable to load Vector Store.", None

    # 2. Предобрабатываем вопрос
    if chat_history is None:
        chat_history = []
    prepared_prompt = await preprocess_user_prompt(prompt, chat_history, model_client)

    # 3. Извлекаем документы из FAISS
    retrieved_docs_with_scores = retrieve_documents(
        vector_store=vector_store,
        user_prompt=prepared_prompt,
        k=DOCS_IN_RETRIEVER,
        metadata_filters=metadata_filters
    )

    # ----------
    logger.info(f"🔍 Найдено {len(retrieved_docs_with_scores)} документов из FAISS")

    for i, (doc, score) in enumerate(retrieved_docs_with_scores[:3]):
        logger.info(f"📄 Топ-{i + 1} документ (оценка={score:.3f}): {doc.page_content[:200]}...")

    # ----------

    # 4. Используем FAISS-оценки, НЕ пересчитываем
    relevance_scores = retrieved_docs_with_scores  # [(doc, score), ...]

    # 5. Фильтруем документы на основе RELEVANCE_THRESHOLD_DOCS
    relevant_docs = [
        doc for (doc, similarity) in relevance_scores
        if similarity >= RELEVANCE_THRESHOLD_DOCS
    ]

    # ----------
    # После фильтрации
    logger.info(f"✅ Осталось {len(relevant_docs)} релевантных документов после фильтрации")

    # ----------

    # 6. Если ничего не нашлось, берём лучший
    if not relevant_docs and relevance_scores:
        # Возьми хотя бы самый лучший, даже если < 0.5
        best_doc, best_score = max(relevance_scores, key=lambda x: x[1])
        logger.warning(f"⚠️ Нет документов выше порога, но берём лучший (score={best_score:.3f})")
        relevant_docs = [best_doc]

    # 7. Формируем «контекст» из релевантных документов
    context_str = ""
    for doc in relevant_docs:
        source = doc.metadata.get('source', 'Unknown')
        page = doc.metadata.get('page', 'N/A')
        content = doc.page_content or 'N/A'
        context_str += f"Source: {source}, Page: {page}\nContent:\n{content}\n---\n"

    # 8. «Системный» промпт: даём модели контекст
    system_prompt = (
        "You are an expert. Provide a concise answer based on the context:\n"
        f"{context_str}\n"
        "--- End Context ---\n"
        "If the user question isn't fully answered in the provided context, "
        "use your best judgment while staying truthful.\n"
    )

    # 9. Формируем финальный промпт для LLM
    final_prompt = f"{system_prompt}\n\nUser: {prepared_prompt}"

    # 10. Вызываем LLM
    answer_text = await model_client.generate_text(final_prompt)

    # 11. Оцениваем «глобальную» релевантность
    is_relevant = is_prompt_relevant_to_documents(relevance_scores)

    # 12. Готовим список ссылок
    references = {}
    for doc in relevant_docs:
        filename = doc.metadata.get("source", "Unknown")
        page = doc.metadata.get("page", "N/A")
        references.setdefault(filename, set()).add(page)

    # 13. Пост-обработка ответа
    final_answer, processed_refs = await postprocess_llm_response(
        llm_response=answer_text,
        user_prompt=prompt,
        context_str=context_str,
        references=references,
        is_relevant=is_relevant,
        model_client=model_client
    )

    # 14. Итоговый форматированный текст
    if is_relevant:
        final_text = final_answer + "\n---\nAdditional references may be listed above."
        source_files = list(processed_refs.keys()) if processed_refs else None
    else:
        final_text = final_answer
        source_files = None

    return final_text, source_files

# === тест ===

async def interactive_demo():
    config = ModelConfig()
    model_client = ModelClient(config)

    # Проверка embeddings
    if not model_client.embeddings_available:
        print("⚠️ Embeddings недоступны. Проверь URL или модель.")
        print("💡 Будет использован кастомный поиск (без векторов).")

    print("\n✅ Ассистент готов. Задавай вопросы. Введи 'exit' для выхода.\n")

    chat_history = []

    while True:
        question = input("Вопрос: ").strip()
        if question.lower() in ['exit', 'quit', 'выйти', 'q']:
            print("👋 Выход.")
            break

        if not question:
            continue

        try:
            answer, sources = await generate_response(
                prompt=question,
                model_client=model_client,
                chat_history=chat_history
            )
            print(f"🤖 Ответ: {answer}\n")
            if sources:
                print(f"📚 Использованные источники: {sources}\n")

            # Правильное формирование chat_history
            chat_history.append(HumanMessage(content=question))
            chat_history.append(AIMessage(content=answer))
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(interactive_demo())