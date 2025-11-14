# src/edms_assistant/core/base_agent.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from langchain_core.tools import BaseTool
from langchain_core.language_models import BaseChatModel
from src.edms_assistant.core.state import GlobalState


class BaseAgent(ABC):
    """
    Абстрактный базовый класс для всех агентов.
    Обеспечивает общую структуру и методы для инициализации, получения инструментов и обработки.
    """

    def __init__(self, llm: BaseChatModel, tools: List[BaseTool] = None):
        self.llm = llm
        self.tools = tools or []

    def get_tools(self) -> List[BaseTool]:
        """
        Возвращает список инструментов агента.
        """
        return self.tools

    def add_tool(self, tool: BaseTool):
        """
        Добавляет инструмент к агенту.
        """
        self.tools.append(tool)

    @abstractmethod
    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        """
        Абстрактный метод обработки запроса агентом.
        Должен быть реализован в дочерних классах.
        Возвращает словарь с результатом выполнения.
        """
        raise NotImplementedError("Method 'process' must be implemented in a subclass")