# srccc/edms_assistant/core/tool_registry.py
from typing import Dict, List, Callable
from langchain_core.tools import BaseTool


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, List[Callable]] = {}

    def register_for_agent(self, agent_name: str, tools: List[Callable]):
        if agent_name not in self._tools:
            self._tools[agent_name] = []
        self._tools[agent_name].extend(tools)

    def get_tools_for_agent(self, agent_name: str) -> List[Callable]:
        return self._tools.get(agent_name, [])

    def get_all_tools(self) -> Dict[str, List[Callable]]:
        return self._tools


# Глобальный экземпляр
tool_registry = ToolRegistry()
