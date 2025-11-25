# src/edms_assistant/rag/retriever.py
import logging
from typing import List, Dict
from pathlib import Path
import pickle

from langchain_openai import ChatOpenAI
from edms_assistant.core.settings import settings
from src.edms_assistant.rag.hybrid_search import HybridSearch

logger = logging.getLogger(__name__)


async def expand_query(query: str) -> str:
    llm = ChatOpenAI(
        api_key="not-needed",
        base_url=str(settings.vllm.generative_base_url),
        model=settings.vllm.generative_model,
        temperature=0.0
    )
    prompt = f"""
Ты — эксперт по корпоративной документации: инструкции, регламенты, руководства, формы, политики, процессы.
Перепиши вопрос пользователя, добавив синонимы, официальные термины и возможные формулировки, 
которые могут встречаться в деловых документах.

Не добавляй пояснений. Верни только расширенный текст запроса.

Вопрос: "{query}"

Расширенный запрос:
"""
    response = await llm.ainvoke([("user", prompt)])
    return response.content.strip()


async def retrieve_and_generate(
        question: str,
        filename: str,
        chat_history: List[Dict],
        vector_store
) -> str:
    # === 1. Расширяем запрос с помощью LLM ===
    expanded_query = await expand_query(question)
    logger.debug(f"Исходный запрос: {question}")
    logger.debug(f"Расширенный запрос: {expanded_query}")

    # === 2. Загружаем чанки из файла ===
    store_dir = Path(settings.paths.vector_stores_dir) / Path(filename).stem
    chunks_path = store_dir / "chunks.pkl"

    if not chunks_path.exists():
        logger.error(f"❌ Файл чанков не найден: {chunks_path}")
        return "REFLECT: Не найдено в этом файле"

    try:
        with open(chunks_path, "rb") as f:
            chunks = pickle.load(f)
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки чанков для {filename}: {e}")
        return "REFLECT: Не найдено в этом файле"

    # === 3. Гибридный поиск по расширенному запросу ===
    hybrid = HybridSearch(vector_store, chunks)
    hybrid_results = hybrid.search(
        query=expanded_query,
        k=5,
        semantic_weight=0.6,
        keyword_weight=0.4
    )

    relevant_docs = [doc for doc, score in hybrid_results[:3]]
    if not relevant_docs:
        return "REFLECT: Не найдено в этом файле"

    # === 4. Формируем контекст и генерируем ответ ===
    context = "\n\n".join([
        f"Источник: {doc.metadata.get('source', 'Unknown')}\nСодержимое:\n{doc.page_content}"
        for doc in relevant_docs
    ])

    system_prompt = f"""Ты — эксперт по документам. Отвечай ТОЛЬКО на основе контекста.
    Верни ПОЛНЫЙ и ТОЧНЫЙ ответ, включая ВСЕ пункты и подпункты.
    Если информации нет — скажи: «Я не нашёл информацию в документах».
    Не сокращай, не обобщай, не выдумывай.

    Контекст:
    {context}
    """

    user_prompt = f"Вопрос: {question}"

    llm = ChatOpenAI(
        api_key="not-needed",
        base_url=str(settings.vllm.generative_base_url),
        model=settings.vllm.generative_model,
        temperature=0.0,
        max_tokens=1024,
    )

    messages = [("system", system_prompt), ("user", user_prompt)]
    response = await llm.ainvoke(messages)
    answer = response.content.strip()

    if any(phrase in answer.lower() for phrase in [
        "не нашёл", "не могу найти", "нет информации", "не указано", "не содержится"
    ]):
        return "REFLECT: Не найдено в этом файле"

    return answer
