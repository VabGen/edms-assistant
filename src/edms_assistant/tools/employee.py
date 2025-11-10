# src/edms_assistant/tools/employee.py
import json
import logging
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from src.edms_assistant.infrastructure.resources_openapi import (
    EmployeeFilter,
    DocOperation,
    OperationType2,
    ResponsibleUpdate,
)

logger = logging.getLogger(__name__)


class FindResponsibleInput(BaseModel):
    last_name: str = Field(..., description="Фамилия ответственного (обязательно)")
    service_token: str = Field(..., description="JWT-токен для авторизации")
    first_name: Optional[str] = Field(None, description="Имя (опционально)")
    department_id: Optional[UUID] = Field(
        None, description="ID подразделения (опционально)"
    )


class AddResponsibleInput(BaseModel):
    document_id: UUID = Field(..., description="UUID документа в EDMS")
    responsible_id: UUID = Field(
        ..., description="UUID сотрудника, которого нужно добавить как ответственного"
    )
    service_token: str = Field(..., description="JWT-токен для авторизации")


class GetEmployeeByIdInput(BaseModel):
    employee_id: UUID = Field(..., description="UUID сотрудника в EDMS")
    service_token: str = Field(..., description="JWT-токен для авторизации")


@tool(
    args_schema=GetEmployeeByIdInput,
    name_or_callable="get_employee_by_id",
    description="Получить данные сотрудника по его UUID. Возвращает полную информацию о сотруднике.",
)
async def get_employee_by_id_tool(
        employee_id: UUID,
        service_token: str,
) -> str:
    """
    Выполняет GET /api/employee/{id} через DocumentClient.
    Возвращает JSON-ответ от EDMS.
    """
    try:

        async with DocumentClient(service_token=service_token) as client:
            response = await client.get_employee_by_id(employee_id)

        if not response:
            return json.dumps(
                {
                    "error": "employee_not_found",
                    "message": f"Сотрудник с ID {employee_id} не найден.",
                },
                ensure_ascii=False,
            )

        # Возвращаем оригинальный JSON как есть
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
            ensure_ascii=False,
        )


@tool(
    args_schema=FindResponsibleInput,
    name_or_callable="find_responsible",
    description="Найти сотрудника по фамилии (и опционально по имени и подразделению). Возвращает список кандидатов.",
)
async def find_responsible_tool(
        last_name: str,
        service_token: str,
        first_name: Optional[str] = None,
        department_id: Optional[UUID] = None,
) -> str:
    try:
        filter_data = EmployeeFilter(
            lastName=last_name,
            firstName=first_name,
            departmentId=[department_id] if department_id else None,
            active=True,
        )

        async with DocumentClient(service_token=service_token) as client:
            response = await client.search_employees(
                filter_data.model_dump(exclude_none=True, mode="json")
            )

        if not response or "content" not in response:
            return json.dumps({"error": "Пустой ответ от EDMS"})

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
    try:
        body_data = ResponsibleUpdate(addIds=[responsible_id])
        operation = DocOperation(
            operationType=OperationType2.DOCUMENT_CONTRACT_RESPONSIBLE, body=body_data
        )
        operations_payload = [operation.model_dump(mode="json", exclude_none=True)]

        logger.info(
            f"add_responsible_to_document_tool: sending payload = {operations_payload}"
        )

        async with DocumentClient(service_token=service_token) as client:
            response = await client.execute_document_operations(
                document_id, operations_payload
            )

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error(
            f"Ошибка добавления ответственного в документ {document_id}: {e}",
            exc_info=True,
        )
        return json.dumps({"error": f"Не удалось добавить ответственного: {str(e)}"})
