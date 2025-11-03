# src\edms_assistant\tools\employee_tool.py
import json
from typing import List, Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from src.edms_assistant.infrastructure.resources_openapi import EmployeeFilter
import logging

logger = logging.getLogger(__name__)

class FindResponsibleInput(BaseModel):
    last_name: str = Field(..., description="Фамилия ответственного (обязательно)")
    service_token: str = Field(..., description="JWT-токен для авторизации")
    first_name: Optional[str] = Field(None, description="Имя (опционально)")
    department_id: Optional[UUID] = Field(
        None, description="ID подразделения (опционально)"
    )

@tool(
    args_schema=FindResponsibleInput,
    name_or_callable="find_responsible",
    description="Найти ответственных лиц по фамилии (и опционально по имени и подразделению). Возвращает список кандидатов.",
)
async def find_responsible_tool(
        last_name: str,
        service_token: str,
        first_name: Optional[str] = None,
        department_id: Optional[UUID] = None,
) -> str:
    """
    Выполняет поиск сотрудников через EDMS API /employee/search.
    """
    try:
        # Формируем фильтр
        filter_data = EmployeeFilter(
            lastName=last_name,
            firstName=first_name,
            departmentId=[department_id] if department_id else None,
            active=True,
        )

        async with DocumentClient(service_token=service_token) as client:
            # ✅ Вызываем метод клиента
            response = await client.search_employees(filter_data.model_dump(exclude_none=True, mode="json"))

        if not response or "content" not in response:
            return json.dumps({"error": "Пустой ответ от EDMS"})

        # Извлекаем список сотрудников
        employees = response["content"]
        candidates = []
        for emp in employees:
            candidates.append(
                {
                    "id": emp.get("id"),
                    "last_name": emp.get("lastName", ""),
                    "first_name": emp.get("firstName", ""),
                    "middle_name": emp.get("middleName", ""),
                    "department": (
                        emp.get("department", {}).get("name", "")
                        if emp.get("department")
                        else ""
                    ),
                    "post": (
                        emp.get("post", {}).get("postName", "")
                        if emp.get("post")
                        else ""
                    ),
                }
            )

        return json.dumps(candidates, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка поиска ответственных в EDMS: {e}", exc_info=True)
        return json.dumps({"error": f"Не удалось найти ответственных: {str(e)}"})