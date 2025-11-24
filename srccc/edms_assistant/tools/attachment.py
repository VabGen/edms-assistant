# srccc/edms_assistant/tools/attachment.py
from langchain_core.tools import tool
from typing import Optional
import json
import logging
import os
from srccc.edms_assistant.infrastructure.api_clients.attachment_client import AttachmentClient
from srccc.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from srccc.edms_assistant.utils.file_utils import extract_text_from_bytes
from srccc.edms_assistant.infrastructure.llm.llm import get_llm

logger = logging.getLogger(__name__)


@tool
def summarize_attachment_tool(document_id: str, attachment_id: str, attachment_name: str, service_token: str) -> str:
    """Инструмент для суммаризации вложения."""
    logger.info(f"Вызов summarize_attachment_tool для {attachment_name} в документе {document_id}")
    try:
        client = AttachmentClient()
        import asyncio
        loop = asyncio.get_event_loop()
        file_bytes = loop.run_until_complete(client.download_attachment(document_id, attachment_id, service_token))
        if not file_bytes:
            return json.dumps({"error": "Файл не найден."})

        text = extract_text_from_bytes(file_bytes, attachment_name)
        if not text or len(text) < 20:
            return json.dumps({"error": f"Файл '{attachment_name}' содержит мало текста или не поддерживается."})

        llm = get_llm()
        prompt = (
            "Создай краткое содержание (3-5 предложений) на русском языке. "
            "Выдели суть, ключевые условия, стороны, суммы, даты."
            f"Текст:\n{text[:8000]}"
        )
        response = loop.run_until_complete(llm.ainvoke([{"role": "user", "content": prompt}]))
        summary = getattr(response, "content", str(response))
        return json.dumps({"summary": f"Краткое содержание файла '{attachment_name}':\n{summary}"}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка в summarize_attachment_tool: {e}", exc_info=True)
        return json.dumps({"error": f"Не удалось обработать вложение: {e}"})


@tool
def extract_and_summarize_file_tool(file_path: str, service_token: str) -> str:
    """Инструмент для извлечения текста из файла пользователя и суммаризации."""
    logger.info(f"Вызов extract_and_summarize_file_tool для файла: {file_path}")
    if not os.path.exists(file_path):
        return json.dumps({"error": f"Файл не найден: {file_path}"})
    filename = os.path.basename(file_path)
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        text = extract_text_from_bytes(file_bytes, filename)
        if not text or len(text) < 20:
            return json.dumps({"error": f"Файл '{filename}' содержит мало текста или не поддерживается."})

        llm = get_llm()
        prompt = (
            "Создай краткое содержание (3-5 предложений) на русском языке. "
            "Выдели суть, ключевые условия, стороны, суммы, даты."
            f"Текст:\n{text[:8000]}"
        )
        import asyncio
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(llm.ainvoke([{"role": "user", "content": prompt}]))
        summary = getattr(response, "content", str(response))
        return json.dumps({"summary": f"Краткое содержание файла '{filename}':\n{summary}"}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка в extract_and_summarize_file_tool: {e}", exc_info=True)
        return json.dumps({"error": f"Не удалось обработать файл: {e}"})
