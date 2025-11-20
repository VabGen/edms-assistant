import asyncio
import logging
import os
import hashlib
import json
from typing import Literal, List

from langgraph.prebuilt import tools_condition
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# === Настройка логирования ===

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()  # Вывод в консоль
    ]
)

logger = logging.getLogger(__name__)

# === Pydantic-схемы ===

class ModelConfig(BaseModel):
    generative_base_url: str = "http://model-generative.shared.du.iba/v1"
    generative_model: str = "generative-model"
    embedding_base_url: str = "http://model-embedding.shared.du.iba/v1"
    embedding_model: str = "Qwen/Qwen3-Embedding-8B"
    api_key: str = "not-needed"

# === Клиент для вызова твоих моделей (с использованием langchain_openai) ===

class ModelClient:
    def __init__(self, config: ModelConfig):
        self.config = config

        # Инициализация LLM
        self.llm = ChatOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.generative_base_url,
            model=self.config.generative_model,
            temperature=0.0,
        )

        # Попытка инициализировать Embeddings
        try:
            self.embeddings = OpenAIEmbeddings(
                api_key=self.config.api_key,
                base_url=self.config.embedding_base_url,
                model=self.config.embedding_model,  # ← ИСПОЛЬЗУЕТСЯ ПРАВИЛЬНОЕ ИМЯ МОДЕЛИ: "Qwen/Qwen3-Embedding-8B"
            )
            logger.success("✅ Embeddings успешно инициализированы.")
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
        logger.success("✅ [LLM] Ответ от генеративной модели получен.")
        return response.content

    async def embed_text(self, texts: list[str]) -> list[list[float]]:
        if not self.embeddings_available:
            raise RuntimeError("❌ Embeddings недоступны. Сервер не поддерживает /v1/embeddings.")
        logger.info(f"🔄 [EMBED] Отправка запроса к эмбеддинговой модели: {self.config.embedding_base_url}")
        # OpenAIEmbeddings.embed_documents возвращает список векторов
        result = await self.embeddings.aembed_documents(texts)
        logger.success("✅ [EMBED] Ответ от эмбеддинговой модели получен.")
        return result

# === NLP-компонент (с использованием LLM) ===

class NLUProcessor:
    def __init__(self, model_client: ModelClient):
        self.model_client = model_client

    async def classify_intent(self, text: str) -> str:
        """Classify the intent of the user's text."""
        logger.info(f"🔄 [NLU] Классификация намерения для текста: {text[:50]}...")
        prompt = f"""
<role>
Ты — помощник системы управления документами. Твоя задача — классифицировать намерение пользователя.
</role>

<task>
Проанализируй текст пользователя и определи его намерение.
</task>

<available_intents>
- find_instruction: запрос инструкции или руководства (например, как что-то сделать)
- create_document: создание нового документа
- find_document: поиск существующего документа
- update_document: обновление документа
- delete_document: удаление документа
- find_employee: поиск сотрудника
- unknown: неизвестное намерение
</available_intents>

<text>
{text}
</text>

<thought>
Подумай, какое намерение подходит.
</thought>

<output>
Ответь только одним словом: "find_instruction", "create_document", "find_document", "update_document", "delete_document", "find_employee" или "unknown".
</output>
"""

        system_prompt = "Ты классификатор намерений. Отвечай только одним словом."
        response = await self.model_client.generate_text(prompt, system_prompt=system_prompt)
        intent = response.strip().lower()
        logger.info(f"✅ [NLU] intent = {intent}")
        return intent

    async def extract_entities(self, text: str) -> dict:
        """Extract entities from the user's text."""
        logger.info(f"🔄 [NLU] Извлечение сущностей из текста: {text[:50]}...")
        prompt = f"""
<role>
Ты — помощник системы управления документами. Твоя задача — извлекать сущности из текста пользователя.
</role>

<task>
Извлеки следующие сущности из текста:
- employee_name: имя сотрудника
- document_id: ID документа
- reg_number: регистрационный номер
- date: дата (в любом формате)
- uuid: UUID (например, 550e8400-e29b-41d4-a716-446655440000)
</task>

<text>
{text}
</text>

<thought>
Подумай, какие сущности присутствуют.
</thought>

<output>
Ответь в формате JSON: {{"employee_name": [], "document_id": [], "reg_number": [], "date": [], "uuid": []}}
</output>
"""

        system_prompt = "Ты извлекатель сущностей. Отвечай только JSON."
        response = await self.model_client.generate_text(prompt, system_prompt=system_prompt)
        import json
        try:
            entities = json.loads(response.strip())
        except json.JSONDecodeError:
            logger.error("❌ [NLU] Ошибка парсинга JSON из NLU.")
            entities = {"employee_name": [], "document_id": [], "reg_number": [], "date": [], "uuid": []}
        logger.info(f"✅ [NLU] entities = {entities}")
        return entities

    async def preprocess_query(self, query: str) -> str:
        """Preprocess the user's query."""
        logger.info(f"🔄 [NLU] Предобработка вопроса: {query[:50]}...")
        prompt = f"""
<role>
Ты — помощник системы управления документами. Твоя задача — улучшить вопрос пользователя.
</role>

<task>
Переформулируй вопрос, чтобы он был более точным и понятным.
</task>

<question>
{query}
</question>

<thought>
Подумай, как можно улучшить вопрос.
</thought>

<output>
Верни улучшенный вопрос.
</output>
"""

        response = await self.model_client.generate_text(prompt)
        improved_query = response.strip()
        logger.info(f"✅ [NLU] improved_query = {improved_query}")
        return improved_query

# === Простой RAG-компонент (на основе поиска по файлу) ===

class SimpleRAG:
    def __init__(self, model_client: ModelClient):
        self.model_client = model_client
        self.chunks: list[str] = []
        self.embeddings: list[list[float]] = []

    def _get_file_id(self, file_path: str) -> str:
        """Генерирует ID файла на основе его имени и пути."""
        file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        return f"{os.path.basename(file_path)}_{file_hash}"

    async def load_and_chunk_file(self, file_path: str):
        logger.info(f"🔄 [RAG] Загрузка файла: {file_path}")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"❌ [RAG] Файл не найден: {file_path}")

        # Простая загрузка содержимого
        if file_path.endswith('.doc'):
            logger.info("🔄 [RAG] Файл .doc обнаружен. Попытка конвертации через pypandoc...")
            try:
                import pypandoc
                text = pypandoc.convert_file(file_path, 'plain', format='doc')
            except ImportError:
                logger.error("❌ [RAG] pypandoc не установлен. Установите: pip install pypandoc")
                logger.error("💡 [RAG] Или конвертируйте файл в .docx/.txt вручную.")
                return
            except Exception as e:
                logger.error(f"❌ [RAG] Ошибка при конвертации .doc: {e}")
                return
        elif file_path.endswith('.docx'):
            from docx import Document
            doc = Document(file_path)
            text = '\n'.join([p.text for p in doc.paragraphs if p.text])
        elif file_path.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            raise ValueError(f"❌ [RAG] Неподдерживаемый формат файла: {file_path}")

        # Разбиваем текст на чанки (кусочки)
        chunk_size = 500
        self.chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        logger.info(f"✅ [RAG] Файл разбит на {len(self.chunks)} чанков.")

        # Генерируем эмбеддинги для чанков, если доступны
        if self.model_client.embeddings_available:
            logger.info("🔄 [RAG] Генерация эмбеддингов для чанков...")
            try:
                self.embeddings = await self.model_client.embed_text(self.chunks)
                logger.success("✅ [RAG] Эмбеддинги сгенерированы.")

                # --- СОХРАНЕНИЕ FAISS В ПАПКУ cli ---
                file_id = self._get_file_id(file_path)
                faiss_dir = f"./cli/faiss_index_{file_id}"
                os.makedirs(faiss_dir, exist_ok=True)

                from langchain_community.vectorstores import FAISS
                vector_store = FAISS.from_embeddings(
                    text_embeddings=list(zip(self.chunks, self.embeddings)),
                    embedding=self.model_client.embeddings
                )
                vector_store.save_local(faiss_dir)
                logger.success(f"✅ [RAG] FAISS-индекс сохранён в: {faiss_dir}")

            except RuntimeError as e:
                logger.error(f"❌ [RAG] Ошибка при генерации эмбеддингов: {e}")
                logger.info("💡 [RAG] Откат к кастомному поиску.")
                self.embeddings = []
                self.model_client.embeddings_available = False
        else:
            logger.info("💡 [RAG] Embeddings недоступны. Чанки загружены.")
            # --- СОХРАНЕНИЕ ЧАНКОВ В JSON В ПАПКУ cli ---
            file_id = self._get_file_id(file_path)
            chunks_file = f"./cli/chunks_{file_id}.json"
            os.makedirs("./cli", exist_ok=True)

            with open(chunks_file, 'w', encoding='utf-8') as f:
                json.dump(self.chunks, f, ensure_ascii=False, indent=2)
            logger.success(f"✅ [RAG] Чанки сохранены в: {chunks_file}")

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot_product = sum(i * j for i, j in zip(a, b))
        magnitude_a = sum(i ** 2 for i in a) ** 0.5
        magnitude_b = sum(i ** 2 for i in b) ** 0.5
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        return dot_product / (magnitude_a * magnitude_b)

    async def query(self, question: str) -> str:
        logger.info(f"🔄 [RAG] Получен вопрос: {question}")

        if self.model_client.embeddings_available and self.embeddings:
            # --- Векторный поиск ---
            logger.info("🔍 [RAG] Используется векторный поиск.")
            # Генерируем эмбеддинг для вопроса
            question_embedding = (await self.model_client.embed_text([question]))[0]

            # Находим ближайший чанк
            similarities = [self.cosine_similarity(question_embedding, emb) for emb in self.embeddings]
            best_idx = max(range(len(similarities)), key=lambda i: similarities[i])
            best_chunk = self.chunks[best_idx]

            logger.info(f"✅ [RAG] Лучший чанк найден (схожесть: {similarities[best_idx]:.3f})")
            return best_chunk
        else:
            # --- Кастомный поиск (по ключевым словам) ---
            logger.info("🔍 [RAG] Используется кастомный поиск по ключевым словам.")
            question_words = set(question.lower().split())

            best_chunk = ""
            best_score = 0

            for chunk in self.chunks:
                chunk_lower = chunk.lower()
                score = sum(1 for word in question_words if word in chunk_lower)

                if score > best_score:
                    best_score = score
                    best_chunk = chunk

            if best_chunk:
                logger.info(f"✅ [RAG] Найден лучший чанк с {best_score} совпадающими словами.")
            else:
                logger.info("❌ [RAG] Не найдено подходящего чанка.")
                best_chunk = "Информация не найдена в документе."

            return best_chunk

# === Инструмент для RAG (аналог LangChain `create_retriever_tool`) ===

class RAGTool:
    def __init__(self, rag: SimpleRAG):
        self.rag = rag
        self.name = "retrieve_edms_manual"
        self.description = "Search and return information about EDMS manual."

    async def invoke(self, query: str) -> str:
        logger.info(f"🔄 [TOOL] RAGTool.invoke вызван с запросом: {query[:50]}...")
        result = await self.rag.query(query)
        logger.success(f"✅ [TOOL] RAGTool.invoke вернул результат длиной {len(result)} символов.")
        return result

# === Определение состояния (аналог MessagesState) ===

class AgentState(BaseModel):
    messages: List[dict] = Field(default_factory=list)
    intent: str = None  # ← НОВОЕ ПОЛЕ: для хранения намерения
    entities: dict = Field(default_factory=dict)  # ← НОВОЕ ПОЛЕ: для хранения сущностей
    decision: str = None  # ← НОВОЕ ПОЛЕ: для хранения решения из grade_documents

# === Узлы агента (с улучшенными промптами и логированием) ===

class AgenticRAG:
    def __init__(self, model_client: ModelClient, rag_tool: RAGTool, nlu_processor: NLUProcessor):
        self.model_client = model_client
        self.rag_tool = rag_tool
        self.nlu_processor = nlu_processor

    async def preprocess_query_node(self, state: AgentState):
        """Preprocess the user's query using NLU."""
        logger.info("🔄 [NODE] preprocess_query_node запущен.")
        question = state.messages[-1]["content"]
        logger.debug(f"📝 [NODE] Входной вопрос: {question}")
        improved_question = await self.nlu_processor.preprocess_query(question)
        # Обновляем последнее сообщение
        state.messages[-1]["content"] = improved_question
        # Также извлекаем intent и entities
        intent = await self.nlu_processor.classify_intent(improved_question)
        entities = await self.nlu_processor.extract_entities(improved_question)
        logger.info(f"✅ [NODE] preprocess_query_node завершён. Intent: {intent}, Entities: {entities}")
        # Возвращаем dict, который обновляет состояние
        return {"intent": intent, "entities": entities}

    async def generate_query_or_respond(self, state: AgentState):
        """Call the model to generate a response based on the current state. Given
        the question, it will decide to retrieve using the retriever tool, or simply respond to the user.
        """
        logger.info(f"🔄 [NODE] generate_query_or_respond запущен. Intent: {state.intent}")
        last_message = state.messages[-1]
        question = last_message["content"]
        intent = state.intent

        # --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: ЯВНО ВЫЗЫВАЕМ ИНСТРУМЕНТ, ЕСЛИ НАМЕРЕНИЕ ПОДХОДИТ ---
        if intent == "find_instruction":
            logger.info("🔍 [NODE] Intent 'find_instruction' -> вызов инструмента.")
            # Возвращаем сообщение с вызовом инструмента
            # ВАЖНО: tool_calls ДОЛЖЕН БЫТЬ В СООБЩЕНИИ, КОТОРОЕ ВОЗВРАЩАЕТСЯ КАК AIMessage
            return {"messages": [AIMessage(
                content="",
                tool_calls=[
                    {"name": self.rag_tool.name, "args": {"query": question}, "id": "call_1"}
                ]
            ).dict()]}

        else:
            logger.info("💬 [NODE] Intent не 'find_instruction' -> прямой ответ.")
            response_content = await self.model_client.generate_text(question,
                                                                     system_prompt="Ты помощник по СЭД. Ответь кратко и по делу.")
            return {"messages": [AIMessage(content=response_content).dict()]}

    async def grade_documents(self, state: AgentState) -> Literal["generate_answer", "rewrite_question"]:
        """Determine whether the retrieved documents are relevant to the question."""
        logger.info("🔄 [NODE] grade_documents запущен.")
        question = state.messages[0]["content"]
        # Предположим, что контекст — это содержимое последнего ToolMessage
        tool_response = state.messages[-1]["content"]  # Это результат RAG

        grade_prompt = f"""
<role>
Ты — оценщик релевантности документа.
</role>

<task>
Определи, содержит ли извлечённый документ информацию, относящуюся к вопросу пользователя.
</task>

<question>
{question}
</question>

<thought>
Подумай, релевантен ли документ.
</thought>

<output>
Ответь 'yes', если документ релевантен, и 'no', если нет.
</output>
"""

        grade_system_prompt = "Ты оценщик. Отвечай только 'yes' или 'no'."
        grade_response = await self.model_client.generate_text(grade_prompt, system_prompt=grade_system_prompt)

        score = grade_response.strip().lower()
        decision = "generate_answer" if score == "yes" else "rewrite_question"
        logger.info(f"✅ [NODE] grade_documents завершён. Решение: {decision}, Score: {score}")
        return decision

    async def rewrite_question(self, state: AgentState):
        """Rewrite the original user question."""
        logger.info("🔄 [NODE] rewrite_question запущен.")
        question = state.messages[0]["content"]

        rewrite_prompt = f"""
<role>
Ты — помощник, который улучшает вопросы.
</role>

<task>
Переформулируй вопрос пользователя, чтобы он был более точным и понятным.
</task>

<question>
{question}
</question>

<thought>
Подумай, как можно улучшить вопрос.
</thought>

<output>
Верни улучшенный вопрос.
</output>
"""

        rewrite_response = await self.model_client.generate_text(rewrite_prompt)
        new_question = rewrite_response.strip()
        logger.info(f"✅ [NODE] rewrite_question завершён. Новый вопрос: {new_question}")
        return {"messages": [HumanMessage(content=new_question).dict()]}

    async def generate_answer(self, state: AgentState):
        """Generate an answer."""
        logger.info("🔄 [NODE] generate_answer запущен.")
        question = state.messages[0]["content"]
        # Контекст — из ToolMessage
        context = state.messages[-1]["content"]

        generate_prompt = f"""
<role>
Ты — помощник по документации СЭД (Системы Электронного Документооборота).
</role>

<task>
Ответь на вопрос пользователя, строго опираясь на предоставленный контекст.
</task>

<constraints>
- Если в контексте нет информации для ответа, честно скай: 'Информация не найдена в документе.'
- Не выдумывай и не интерпретируй информацию, которой нет в тексте.
</constraints>

<format>
Формулируй ответ кратко, в 1-3 предложениях, на русском языке.
</format>

<question>
{question}
</question>

<context>
{context}
</context>
"""

        generate_response = await self.model_client.generate_text(generate_prompt)
        logger.success("✅ [NODE] generate_answer завершён.")
        return {"messages": [AIMessage(content=generate_response).dict()]}

# === Функция для вызова инструмента (аналог ToolNode) ===

async def call_tool_node(state: AgentState, rag_tool: RAGTool):
    logger.info("🔄 [NODE] call_tool_node запущен.")
    # Извлекаем аргументы вызова инструмента из последнего сообщения
    last_message = state.messages[-1]
    tool_calls = last_message.get("tool_calls", [])
    if not tool_calls:
        logger.info("💡 [NODE] call_tool_node: нет tool_calls.")
        return state

    tool_call = tool_calls[0]
    if tool_call["name"] == rag_tool.name:
        query = tool_call["args"]["query"]
        logger.info(f"🔍 [NODE] Вызов RAGTool с запросом: {query}")
        result = await rag_tool.invoke(query)
        tool_message = ToolMessage(content=result, name=rag_tool.name, tool_call_id=tool_call["id"])
        logger.success("✅ [NODE] call_tool_node завершён.")
        return {"messages": [tool_message.dict()]}

# === Сборка графа ===

async def build_graph(model_client: ModelClient, rag_tool: RAGTool, nlu_processor: NLUProcessor):
    logger.info("🔄 [GRAPH] Создание графа...")
    agent = AgenticRAG(model_client, rag_tool, nlu_processor)

    workflow = StateGraph(AgentState)

    workflow.add_node("preprocess_query", agent.preprocess_query_node)
    workflow.add_node("generate_query_or_respond", agent.generate_query_or_respond)
    workflow.add_node("retrieve", lambda state: call_tool_node(state, rag_tool))

    # grade_documents теперь — узел, который возвращает dict с decision
    # ИСПРАВЛЕНО: обернуть вызов в асинхронную функцию, которая возвращает dict
    async def grade_documents_node(state: AgentState):
        result = await agent.grade_documents(state)
        # Возвращаем dict, который обновляет состояние
        return {"decision": result}

    workflow.add_node("grade_documents", grade_documents_node)
    workflow.add_node("rewrite_question", agent.rewrite_question)
    workflow.add_node("generate_answer", agent.generate_answer)

    workflow.add_edge(START, "preprocess_query")
    workflow.add_edge("preprocess_query", "generate_query_or_respond")

    # ИСПОЛЬЗУЕМ tools_condition (встроенный узел LangGraph)
    # Он проверяет, есть ли tool_calls в последнем сообщении
    workflow.add_conditional_edges(
        "generate_query_or_respond",
        tools_condition,
        {
            "tools": "retrieve",  # ← Если есть tool_calls -> вызвать retrieve
            END: END,             # ← Если нет -> закончить
        },
    )

    workflow.add_edge("retrieve", "grade_documents")

    # ИСПРАВЛЕНО: используем синхронную функцию для оценки
    def route_after_grade(state: AgentState):
        # state.decision — это строка, которую мы сохранили в grade_documents_node
        return state.decision

    workflow.add_conditional_edges(
        "grade_documents",
        route_after_grade,
        {
            "generate_answer": "generate_answer",
            "rewrite_question": "rewrite_question"
        }
    )

    workflow.add_edge("generate_answer", END)
    workflow.add_edge("rewrite_question", "generate_query_or_respond")

    logger.success("✅ [GRAPH] Граф создан.")
    return workflow.compile()

# === Интерактивный тест ===

async def interactive_demo():
    config = ModelConfig()
    model_client = ModelClient(config)

    # Создаём NLU-процессор
    nlu = NLUProcessor(model_client)

    # Загрузка файла
    file_path = input("Введите путь к файлу (например, Руководство_по_EDMS.docx): ").strip()
    if not os.path.exists(file_path):
        print(f"❌ [CLI] Файл не найден: {file_path}")
        return

    rag = SimpleRAG(model_client)
    await rag.load_and_chunk_file(file_path)

    # ПРОВЕРИТЬ, ЗАГРУЖЕНЫ ЛИ ЧАНКИ
    if not rag.chunks:
        print("❌ [CLI] Чанки не загружены.")
        return

    # ПРОВЕРИТЬ, ЗАГРУЖЕНЫ ЛИ ЭМБЕДДИНГИ
    if model_client.embeddings_available and not rag.embeddings:
        print("❌ [CLI] Эмбеддинги не сгенерированы. Проверь URL эмбеддинговой модели.")
        return

    rag_tool = RAGTool(rag)

    print("\n✅ [CLI] Ассистент готов. Задавай вопросы. Введи 'exit' для выхода.\n")

    graph = await build_graph(model_client, rag_tool, nlu)

    while True:
        question = input("Вопрос: ").strip()
        if question.lower() in ['exit', 'quit', 'выйти', 'q']:
            print("👋 [CLI] Выход.")
            break

        if not question:
            continue

        try:
            logger.info(f"🔄 [CLI] Получен вопрос: {question}")
            # Подготовка начального состояния
            initial_state = AgentState(messages=[HumanMessage(content=question).dict()])

            # Запуск графа
            final_state = await graph.ainvoke(initial_state)

            # Извлечение ответа
            final_message = final_state["messages"][-1]
            response = final_message.get("content", "❌ [CLI] Нет ответа")
            print(f"🤖 [CLI] Ответ: {response}\n")
        except Exception as e:
            print(f"❌ [CLI] Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(interactive_demo())