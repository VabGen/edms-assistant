# src/edms_assistant/rag/router.py
import json
import logging
from typing import List, Dict
from langchain_openai import ChatOpenAI
from edms_assistant.core.settings import settings

logger = logging.getLogger(__name__)


async def route_question_to_file(
        question: str,
        chat_history: List[Dict],
        available_files: List[str]
) -> str:
    if not available_files:
        raise ValueError("Нет доступных документов")
    if len(available_files) == 1:
        return available_files[0]

    history = " ".join(msg["content"] for msg in chat_history if msg["role"] == "user") if chat_history else ""

    context = f"История диалога: {history}\nТекущий вопрос: {question}" if history else question

    llm = ChatOpenAI(
        api_key="not-needed",
        base_url=str(settings.vllm.generative_base_url),
        model=settings.vllm.generative_model,
        temperature=0.0
    )

    prompt = f"""Ты — маршрутизатор в системе документооборота.
Выбери ОДИН файл, в котором наиболее вероятно содержится ответ на вопрос.
Доступные файлы: {available_files}

Контекст:
{context}

Верни ТОЛЬКО валидный JSON:
{{"filename": "имя_файла", "reason": "1-2 слова"}}"""

    try:
        resp = await llm.ainvoke([("user", prompt)])
        data = json.loads(resp.content)
        fname = data.get("filename", "").strip()
        if fname in available_files:
            logger.debug(f"Маршрутизация: {fname} ({data.get('reason')})")
            return fname
    except Exception as e:
        logger.warning(f"Ошибка маршрутизации: {e}")

    return available_files[0]
