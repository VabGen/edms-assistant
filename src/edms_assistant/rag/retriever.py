# src/edms_assistant/rag/retriever.py
import logging
from typing import List, Dict, Any
from pathlib import Path
import pickle

from langchain_openai import ChatOpenAI
from edms_assistant.core.settings import settings
from src.edms_assistant.rag.hybrid_search import HybridSearch

logger = logging.getLogger(__name__)


async def _expand_and_route_query(question: str, chat_history: List[Dict]) -> str:
    """Объединяет расширение запроса и контекст."""
    history = " ".join(
        msg["content"] for msg in chat_history[-2:] if msg["role"] == "user"
    ) if chat_history else ""

    input_text = f"Контекст: {history}\nВопрос: {question}" if history else question

    llm = ChatOpenAI(
        api_key="not-needed",
        base_url=str(settings.vllm.generative_base_url),
        model=settings.vllm.generative_model,
        temperature=0.0
    )

    prompt = f"""Расширь запрос для поиска в документах, добавив синонимы и официальные термины.
Вопрос: {input_text}
Расширенный запрос:"""

    resp = await llm.ainvoke([("user", prompt)])
    return resp.content.strip()


async def retrieve_and_generate(
        question: str,
        filename: str,
        chat_history: List[Dict[str, Any]],
        vector_store
) -> str:
    logger.debug(f"💬 История чата (из Redis): {chat_history}")
    # Формируем enriched query
    enriched_query = await _expand_and_route_query(question, chat_history)
    logger.debug(f"🔍 Расширенный запрос: {enriched_query}")

    # Загрузка чанков
    store_dir = Path(settings.paths.vector_stores_dir) / Path(filename).stem
    chunks_path = store_dir / "chunks.pkl"

    if not chunks_path.exists():
        logger.error(f"❌ Чанки не найдены: {chunks_path}")
        return "REFLECT: Не найдено в этом файле"

    with open(chunks_path, "rb") as f:
        chunks = pickle.load(f)

    # Гибридный поиск
    hybrid = HybridSearch(vector_store, chunks)
    results = hybrid.search(query=enriched_query, k=5)
    relevant_docs = [doc for doc, _ in results[:3]] if results else []

    if not relevant_docs:
        return "REFLECT: Не найдено в этом файле"

    context = "\n\n".join(
        f"[{doc.metadata.get('source', 'Unknown')}]\n{doc.page_content}"
        for doc in relevant_docs
    )
    logger.debug(f"📚 Контекст:\n{context}")

    # Формируем промпт с историей
    history_str = "\n".join(
        f"{m['role']}: {m['content']}" for m in chat_history
    ) if chat_history else "Нет истории."

    system = f"""Ты — эксперт по документам. Отвечай ТОЛЬКО по контексту.
Верни ПОЛНЫЙ ответ со ВСЕМИ деталями. Если информации нет — скажи: «Я не нашёл информацию в документах».

Контекст:
{context}"""

    user = f"""История:
{history_str}

Вопрос: {question}"""

    llm = ChatOpenAI(
        api_key="not-needed",
        base_url=str(settings.vllm.generative_base_url),
        model=settings.vllm.generative_model,
        temperature=0.0,
        max_tokens=1024
    )

    resp = await llm.ainvoke([("system", system), ("user", user)])
    answer = resp.content.strip()

    if any(p in answer.lower() for p in ["не нашёл", "не могу найти", "нет информации"]):
        return "REFLECT: Не найдено в этом файле"

    return answer
