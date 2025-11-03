# src/edms_assistant/infrastructure/security/execution_service.py
import logging
from typing import Dict, Any
from uuid import UUID

# Импортируем инструменты
from src.edms_assistant.core.tools.document_tool import get_document_tool
from src.edms_assistant.core.tools.attachment_tool import summarize_attachment_tool
from src.edms_assistant.core.tools.employee_tool import find_responsible_tool

logger = logging.getLogger(__name__)

# Словарь всех инструментов
ALL_TOOLS = {
    "get_document_tool": get_document_tool,
    "summarize_attachment_tool": summarize_attachment_tool,
    "find_responsible_tool": find_responsible_tool,
}

class ExecutionService:
    def __init__(self, tools: Dict[str, Any] = None):
        self.tools = tools or ALL_TOOLS

    async def execute_tool(self, tool_name: str, args: Dict[str, Any], user_id: UUID, service_token: str) -> Any:
        # 1. Проверка токена
        if not service_token or len(service_token) < 10:
            raise ValueError("Invalid service_token")

        # 2. Санитизация параметров
        args = args.copy()
        args["service_token"] = service_token  # добавляем токен в аргументы, если нужно

        # 3. Логирование вызова
        logger.info(f"User {user_id} executes tool {tool_name} with args {list(args.keys())}")

        # 4. Вызов инструмента
        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not found")

        result = await tool.ainvoke(args)
        return result

# Глобальный экземпляр
execution_service = ExecutionService()