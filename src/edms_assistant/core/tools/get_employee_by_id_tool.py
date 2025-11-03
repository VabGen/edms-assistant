# src/edms_assistant/core/tools/get_employee_by_id_tool.py

import json
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from src.edms_assistant.utils.api_utils import validate_document_id as validate_uuid
import logging

logger = logging.getLogger(__name__)

class GetEmployeeByIdInput(BaseModel):
    employee_id: str = Field(..., description="UUID сотрудника в EDMS")
    service_token: str = Field(..., description="JWT-токен для авторизации")

@tool(
    args_schema=GetEmployeeByIdInput,
    name_or_callable="get_employee_by_id",
    description="Получить данные сотрудника по его UUID. Возвращает полную информацию о сотруднике.",
)
async def get_employee_by_id_tool(
    employee_id: str,
    service_token: str,
) -> str:
    """
    Выполняет поиск сотрудника по UUID через EDMS API /api/employee/{id}.
    """
    try:
        emp_uuid = validate_uuid(employee_id)
        if emp_uuid is None:
            return json.dumps({"error": "invalid_employee_id", "message": f"Неверный формат ID: '{employee_id}'."})

        async with DocumentClient(service_token=service_token) as client:
            # ✅ Вызываем метод клиента
            response = await client.get_employee_by_id(emp_uuid)

        if not response:
            return json.dumps({"error": "employee_not_found", "message": f"Сотрудник с ID {employee_id} не найден."})

        # ✅ Возвращаем оригинальный JSON как есть
        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка получения сотрудника по ID {employee_id}: {e}", exc_info=True)
        return json.dumps({"error": "api_error", "message": f"Не удалось получить сотрудника: {str(e)}"})