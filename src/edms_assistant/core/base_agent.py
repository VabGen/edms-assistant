# src/edms_assistant/core/base_agent.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from langchain_core.tools import BaseTool
from langchain_core.language_models import BaseChatModel
from src.edms_assistant.core.state import GlobalState


class BaseAgent(ABC):
    """Базовый класс для всех агентов с поддержкой безопасности и логирования"""

    def __init__(self, llm: BaseChatModel, tools: List[BaseTool] = None):
        self.llm = llm
        self.tools = tools or []
        self._validate_initialization()

    def _validate_initialization(self):
        """Проверяет корректность инициализации агента"""
        if not self.llm:
            raise ValueError("LLM must be provided to agent")

    def get_tools(self) -> List[BaseTool]:
        """Возвращает инструменты агента"""
        return self.tools

    def add_tool(self, tool: BaseTool):
        """Добавляет инструмент к агенту"""
        self.tools.append(tool)

    @abstractmethod
    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        """Обработка запроса агентом - должен быть реализован в дочерних классах"""
        raise NotImplementedError(
            "Метод process должен быть реализован в дочернем классе"
        )

    async def _execute_with_error_handling(self, func, *args, **kwargs) -> Any:
        """Выполняет функцию с обработкой ошибок и логированием"""
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Логируем ошибку
            import logging

            logger = logging.getLogger(self.__class__.__name__)
            logger.error(f"Error in {self.__class__.__name__}: {str(e)}", exc_info=True)

            # Возвращаем структурированную ошибку
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "requires_execution": False,
                "requires_clarification": False,
            }
