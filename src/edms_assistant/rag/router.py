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

    llm = ChatOpenAI(
        api_key="not-needed",
        base_url=str(settings.vllm.generative_base_url),
        model=settings.vllm.generative_model,
        temperature=0.0
    )

    prompt = f"""
Ты — маршрутизатор запросов в системе документооборота.
Доступные файлы: {available_files}

Вопрос пользователя: "{question}"
История чата: {chat_history}

Выбери ОДИН файл, в котором скорее всего содержится ответ.
Ответь строго в формате JSON:
{{
  "filename": "имя_файла",
  "reason": "краткое обоснование"
}}
"""

    try:
        response = await llm.ainvoke([("user", prompt)])
        result = json.loads(response.content)
        filename = result.get("filename", "").strip()
        if filename in available_files:
            logger.info(f"🔍 Маршрутизация: '{question}' → {filename}")
            return filename
    except Exception as e:
        logger.warning(f"⚠️ Ошибка маршрутизации, выбираем первый файл: {e}")

    return available_files[0]