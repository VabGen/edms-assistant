# src/edms_assistant/agents/base_agent.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.infrastructure.llm.llm import get_llm
from src.edms_assistant.core.tool_registry import tool_registry


class BaseAgent(ABC):
    def __init__(self, llm: BaseChatModel = None, agent_name: str = ""):
        self.llm = llm or get_llm()
        self.agent_name = agent_name
        # Загружаем инструменты из реестра
        self.tools: List[BaseTool] = []
        self.tool_map = {}
        self._load_tools_from_registry()

    def _load_tools_from_registry(self):
        """
        Загружает инструменты для этого агента из ToolRegistry.
        """
        if self.agent_name:
            tools_to_add = tool_registry.get_tools_for_agent(self.agent_name)
            for tool_func in tools_to_add:
                self.add_tool(tool_func)

    def add_tool(self, tool_func):
        """
        Добавляет инструмент в агент.
        """
        self.tools.append(tool_func)
        self.tool_map[tool_func.name] = tool_func

    @abstractmethod
    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError("Subclasses must implement process method")
