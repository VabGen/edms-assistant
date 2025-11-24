# srccc/edms_assistant/tools/employee.py
from langchain_core.tools import tool
from typing import Optional
import json
import logging
from srccc.edms_assistant.infrastructure.api_clients.employee_client import EmployeeClient

logger = logging.getLogger(__name__)


@tool
def find_responsible_tool(query: str, service_token: str) -> str:
    """Инструмент для поиска сотрудников по запросу."""
    logger.info(f"Вызов find_responsible_tool с query: {query}")
    try:
        # Используем API клиент
        client = EmployeeClient()
        # asyncio.run не работает в tool, но мы можем использовать синхронный вызов
        # или передавать event_loop в tool, что сложно
        # Поэтому, для простоты, используем синхронный вызов
        import asyncio
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(client.search_employees(query, service_token))
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка в find_responsible_tool: {e}")
        return json.dumps({"error": str(e)})


@tool
def get_employee_by_id_tool(employee_id: str, service_token: str) -> str:
    """Инструмент для получения сотрудника по ID."""
    logger.info(f"Вызов get_employee_by_id_tool с employee_id: {employee_id}")
    try:
        client = EmployeeClient()
        import asyncio
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(client.get_employee(employee_id, service_token))
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка в get_employee_by_id_tool: {e}")
        return json.dumps({"error": str(e)})
