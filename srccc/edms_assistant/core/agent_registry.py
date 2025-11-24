# srccc/edms_assistant/core/agent_registry.py
from typing import Dict, Type, List
from srccc.edms_assistant.agents.base_agent import BaseAgent


class AgentRegistry:
    """
    Реестр для регистрации и получения классов агентов.
    Не хранит экземпляры, только типы.
    """

    def __init__(self):
        self._agent_classes: Dict[str, Type[BaseAgent]] = {}

    def register(self, name: str, agent_class: Type[BaseAgent]):
        self._agent_classes[name] = agent_class

    def get_agent_class(self, name: str) -> Type[BaseAgent]:
        return self._agent_classes.get(name)

    def get_all_agent_names(self) -> List[str]:
        return list(self._agent_classes.keys())


# Глобальный экземпляр
agent_registry = AgentRegistry()
