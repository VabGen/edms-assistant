# src/edms_assistant/tools/attachment.py
import json
import logging
import os
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from src.edms_assistant.utils.file_utils import extract_text_from_bytes
from src.edms_assistant.infrastructure.llm.llm import get_llm

logger = logging.getLogger(__name__)


class SummarizeAttachmentInput(BaseModel):
    document_id: str = Field(..., description="UUID документа")
    attachment_id: str = Field(..., description="UUID вложения")
    service_token: str = Field(..., description="JWT-токен для авторизации")
    attachment_name: str = Field(..., description="Имя файла для отображения")


class ExtractAndSummarizeFileInput(BaseModel):
    file_path: str = Field(..., description="Путь к загруженному файлу")
    service_token: str = Field(...,
                               description="JWT-токен для авторизации (может не использоваться для локального файла)")


@tool(
    args_schema=SummarizeAttachmentInput,
    name_or_callable="summarize_attachment",
    description="Извлечь текст из вложения документа и создать краткое содержание. Поддерживает PDF, DOCX, TXT.",
)
async def summarize_attachment_tool(
        document_id: str, attachment_id: str, attachment_name: str, service_token: str
) -> str:
    try:
        doc_uuid = UUID(document_id)
        att_uuid = UUID(attachment_id)
    except ValueError as e:
        return json.dumps({"error": f"Неверный UUID. {e}"})

    try:
        async with DocumentClient(service_token=service_token) as client:
            file_bytes = await client.download_attachment(doc_uuid, att_uuid)
        if not file_bytes:
            return json.dumps({"error": "Файл не найден."})

        text = extract_text_from_bytes(file_bytes, attachment_name)
        if not text or len(text) < 20:
            return json.dumps({"error": f"Файл '{attachment_name}' содержит мало текста или не поддерживается."})

        llm = get_llm()
        prompt = (
            "Создай краткое содержание (3-5 предложений) на русском языке. "
            "Выдели суть, ключевые условия, стороны, суммы, даты.\n\n"
            f"Текст:\n{text[:8000]}"
        )
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        summary = getattr(response, "content", str(response))
        return json.dumps({"summary": f"Краткое содержание файла '{attachment_name}':\n{summary}"}, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка суммаризации вложения: {e}", exc_info=True)
        return json.dumps({"error": f"Не удалось обработать вложение: {e}"})


@tool(
    args_schema=ExtractAndSummarizeFileInput,
    name_or_callable="extract_and_summarize_file",  # Переименован
    description="Извлечь текст из загруженного файла пользователя и создать краткое содержание. Поддерживает PDF, DOCX, TXT.",
)
async def extract_and_summarize_file_tool(file_path: str, service_token: str) -> str:
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
            "Выдели суть, ключевые условия, стороны, суммы, даты.\n\n"
            f"Текст:\n{text[:8000]}"
        )
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        summary = getattr(response, "content", str(response))
        return json.dumps({"summary": f"Краткое содержание файла '{filename}':\n{summary}"}, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка суммаризации файла: {e}", exc_info=True)
        return json.dumps({"error": f"Не удалось обработать файл: {e}"})
