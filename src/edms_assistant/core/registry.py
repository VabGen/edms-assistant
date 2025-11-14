# src/edms_assistant/core/registry.py
import threading
from typing import Dict, Type, Any, Optional, List
from src.edms_assistant.core.base_agent import BaseAgent


class AgentRegistry:
    """
    Централизованный реестр агентов с поддержкой безопасной инициализации.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._agent_classes: Dict[str, Type[BaseAgent]] = {}
            self._agent_instances: Dict[str, BaseAgent] = {}
            self._initialized = True

    def register(self, name: str, agent_class: Type[BaseAgent]):
        """
        Регистрирует класс агента.
        """
        if not issubclass(agent_class, BaseAgent):
            raise TypeError(f"Agent class must inherit from BaseAgent, got {agent_class}")
        self._agent_classes[name] = agent_class
        # Не создаем экземпляр сразу, а создаем при первом запросе

    def get_agent_class(self, name: str) -> Optional[Type[BaseAgent]]:
        """
        Получает класс агента по имени.
        """
        return self._agent_classes.get(name)

    def get_agent_instance(self, name: str) -> Optional[BaseAgent]:
        """
        Получает экземпляр агента (создает при первом запросе).
        """
        if name not in self._agent_instances:
            agent_class = self.get_agent_class(name)
            if agent_class:
                # Предполагаем, что у BaseAgent есть конструктор с llm и tools
                # Эти зависимости должны быть внедрены через DI или получены из инфраструктуры
                from src.edms_assistant.infrastructure.llm.llm import get_llm
                from src.edms_assistant.tools.factory import get_tools_for_agent  # <-- Фабрика инструментов

                llm = get_llm()
                tools = get_tools_for_agent(name) # <-- Получаем инструменты для конкретного агента
                self._agent_instances[name] = agent_class(llm=llm, tools=tools)
        return self._agent_instances.get(name)

    def get_all_agent_names(self) -> List[str]:
        """
        Возвращает список всех зарегистрированных агентов.
        """
        return list(self._agent_classes.keys())


# Глобальный экземпляр реестра
agent_registry = AgentRegistry()