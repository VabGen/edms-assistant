# src/edms_assistant/core/tools/add_responsible_tool.py

import logging
import json
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from src.edms_assistant.infrastructure.resources_openapi import (
    DocOperation,
    OperationType2,
    ResponsibleUpdate,
)

logger = logging.getLogger(__name__)

class AddResponsibleInput(BaseModel):
    document_id: UUID = Field(..., description="UUID документа в EDMS")
    responsible_id: UUID = Field(
        ..., description="UUID сотрудника, которого нужно добавить как ответственного"
    )
    service_token: str = Field(..., description="JWT-токен для авторизации")

@tool(
    args_schema=AddResponsibleInput,
    name_or_callable="add_responsible_to_document",
    description="Добавить сотрудника как ответственного по договору в документ. Возвращает JSON-ответ об успехе или ошибке.",
)
async def add_responsible_to_document_tool(
    document_id: UUID,
    responsible_id: UUID,
    service_token: str,
) -> str:
    """
    Выполняет POST /api/document/{id}/execute с операцией DOCUMENT_CONTRACT_RESPONSIBLE.
    Использует DTO из схемы бэкенда.
    """
    try:
        # ✅ document_id уже валиден (Pydantic проверил)
        # ✅ Создаём тело операции через DTO
        body_data = ResponsibleUpdate(addIds=[responsible_id])  # Pydantic-модель

        # ✅ Создаём операцию через DTO
        operation = DocOperation(
            operationType=OperationType2.DOCUMENT_CONTRACT_RESPONSIBLE,  # Pydantic Enum
            body=body_data  # Pydantic-модель
        )

        # ✅ Конвертируем в словарь для отправки
        operations_payload = [operation.model_dump(mode="json", exclude_none=True)]

        logger.info(f"add_responsible_to_document_tool: sending payload = {operations_payload}")

        async with DocumentClient(service_token=service_token) as client:
            # ✅ Вызываем метод клиента
            response = await client.execute_document_operations(document_id, operations_payload)

        # ✅ Возвращаем результат от клиента (уже JSON)
        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка добавления ответственного в документ {document_id}: {e}", exc_info=True)
        return json.dumps({"error": f"Не удалось добавить ответственного: {str(e)}"})