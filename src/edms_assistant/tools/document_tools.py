# src\edms_assistant\tools\document_tools.py
"""
Инструменты для работы с документами в EDMS.
Все инструменты возвращают сырые данные от EDMS API (в формате JSON-строки).
"""
import json
from typing import Optional, Any, Coroutine
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from src.edms_assistant.infrastructure.resources_openapi import DocumentDto
from src.edms_assistant.utils.api_utils import validate_document_id
import logging

logger = logging.getLogger(__name__)


class GetDocumentByIdInput(BaseModel):
    """Схема входных данных для получения документа по ID."""

    document_id: str = Field(..., description="UUID документа в EDMS.")
    service_token: str = Field(..., description="JWT-токен для авторизации в EDMS.")


@tool(
    args_schema=GetDocumentByIdInput,
    name_or_callable="get_document_tool",
    description="Получить документ по ID из EDMS. Возвращает сырой JSON-ответ от Java API в виде строки.",
)
async def get_document_tool(document_id: str, service_token: str) -> dict:
    """
    Получает документ по ID из EDMS и возвращает **сырой JSON-ответ** от Java API в виде строки.

    Args:
        document_id: UUID документа в EDMS (строка в формате UUID)
        service_token: JWT-токен для авторизации в EDMS

    Returns:
        str: Сырой JSON-ответ от EDMS (в виде строки), или JSON с ошибкой при неудаче.
    """
    # === 1. Валидация document_id ===
    doc_uuid = validate_document_id(document_id)
    if doc_uuid is None:
        # error_response = {
        #     "error": "invalid_document_id",
        #     "message": f"Неверный формат ID документа: '{document_id}'. Ожидался UUID.",
        #     "details": "Не удалось преобразовать строку в UUID."
        # }
        # return json.dumps(error_response, ensure_ascii=False)
        return {
            "error": "invalid_document_id",
            "message": f"Неверный формат ID документа: '{document_id}'. Ожидался UUID.",
            "details": "Не удалось преобразовать строку в UUID.",
        }
    try:
        async with DocumentClient(service_token=service_token) as client:
            doc_model: Optional[DocumentDto] = await client.get_document(doc_uuid)

        if doc_model is None:
            return {
                "error": "document_not_found",
                "message": f"Документ с ID {document_id} не найден или недоступен.",
            }

        # Преобразуем модель в dict (с вложенными объектами)
        return doc_model.model_dump(mode="json", exclude_unset=True)

    except Exception as e:
        logger.error(
            f"Ошибка при получении документа {document_id}: {e}", exc_info=True
        )
        return {
            "error": "api_error",
            "message": "Не удалось получить документ из EDMS.",
            "details": str(e),
        }
