# src/edms_assistant/core/tools/get_employee_by_id_tool.py

import json
import logging
from typing import Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
# from src.edms_assistant.utils.api_utils import validate_uuid

logger = logging.getLogger(__name__)

class GetEmployeeByIdInput(BaseModel):
    employee_id: UUID = Field(..., description="UUID сотрудника в EDMS")
    service_token: str = Field(..., description="JWT-токен для авторизации")

@tool(
    args_schema=GetEmployeeByIdInput,
    name_or_callable="get_employee_by_id",
    description="Получить данные сотрудника по его UUID. Возвращает полную информацию о сотруднике.",
)
async def get_employee_by_id_tool(
    employee_id: UUID,  # ✅ Теперь принимаем UUID напрямую
    service_token: str,
) -> str:
    """
    Выполняет GET /api/employee/{id} через DocumentClient.
    Возвращает JSON-ответ от EDMS.
    """
    try:

        async with DocumentClient(service_token=service_token) as client:
            # ✅ Вызываем метод клиента
            response = await client.get_employee_by_id(employee_id)

        if not response:
            return json.dumps(
                {
                    "error": "employee_not_found",
                    "message": f"Сотрудник с ID {employee_id} не найден.",
                },
                ensure_ascii=False
            )

        # ✅ Возвращаем оригинальный JSON как есть
        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error(
            f"Ошибка получения сотрудника по ID {employee_id}: {e}", exc_info=True
        )
        return json.dumps(
            {
                "error": "api_error",
                "message": f"Не удалось получить сотрудника: {str(e)}",
            },
            ensure_ascii=False
        )