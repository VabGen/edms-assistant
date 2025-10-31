# src/edms_assistant/tools/attachment_tools.py
import json
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from src.edms_assistant.utils.file_utils import extract_text_from_bytes
from src.edms_assistant.infrastructure.llm.llm import get_llm
import logging

logger = logging.getLogger(__name__)


class SummarizeAttachmentInput(BaseModel):
    document_id: str = Field(..., description="UUID документа")
    attachment_id: str = Field(..., description="UUID вложения")
    service_token: str = Field(..., description="JWT-токен для авторизации")
    attachment_name: str = Field(..., description="Имя файла для отображения")


@tool(
    args_schema=SummarizeAttachmentInput,
    name_or_callable="summarize_attachment",
    description="Извлечь текст из вложения и создать краткое содержание. Поддерживает PDF, DOCX, TXT.",
)
async def summarize_attachment_tool(
    document_id: str, attachment_id: str, attachment_name: str, service_token: str
) -> str:
    try:
        doc_uuid = UUID(document_id)
        att_uuid = UUID(attachment_id)
    except ValueError as e:
        return f"Ошибка: неверный UUID. {e}"

    try:
        async with DocumentClient(service_token=service_token) as client:
            file_bytes = await client.download_attachment(doc_uuid, att_uuid)
        if not file_bytes:
            return "Ошибка: файл не найден."

        filename = attachment_name

        text = extract_text_from_bytes(file_bytes, filename)
        if not text or len(text) < 20:
            return f"Файл '{filename}' содержит мало текста или не поддерживается."

        llm = get_llm()
        prompt = (
            "Создай краткое содержание (3-5 предложений) на русском языке. "
            "Выдели суть, ключевые условия, стороны, суммы, даты.\n\n"
            f"Текст:\n{text[:8000]}"
        )
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        summary = getattr(response, "content", str(response))
        return f"Краткое содержание файла '{filename}':\n{summary}"

    except Exception as e:
        logger.error(f"Ошибка суммаризации: {e}", exc_info=True)
        return f"Не удалось обработать файл: {e}"
