import threading
from typing import Dict, Type, Any, Optional, List
from langchain_core.tools import BaseTool
from src.edms_assistant.infrastructure.llm.llm import get_llm

# src/edms_assistant/core/registry.py

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAgent(ABC):
    """Базовый класс для всех агентов — содержит методы для получения инструментов и выполнения"""

    def __init__(self):
        self.tools = []
        self.llm = None

    @abstractmethod
    async def process(self, state: Any, **kwargs) -> Dict[str, Any]:
        """Обработка запроса агентом - должен быть реализован в дочерних классах"""
        raise NotImplementedError("Метод process должен быть реализован в дочернем классе")

    def get_tools(self) -> list:
        """Возвращает инструменты для агента"""
        return self.tools

    def set_llm(self, llm):
        """Устанавливает LLM для агента"""
        self.llm = llm


class AgentRegistry:
    """Реестр агентов для централизованного управления"""

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
            self._agents: Dict[str, Type[BaseAgent]] = {}
            self._instances: Dict[str, BaseAgent] = {}
            self._initialized = True

    def register(self, name: str, agent_class: Type[BaseAgent]):
        """Регистрация класса агента"""
        self._agents[name] = agent_class

    def get_agent_class(self, name: str) -> Optional[Type[BaseAgent]]:
        """Получение класса агента"""
        return self._agents.get(name)

    def get_agent_instance(self, name: str) -> Optional[BaseAgent]:
        """Получение экземпляра агента (создается при первом запросе)"""
        if name not in self._instances:
            agent_class = self.get_agent_class(name)
            if agent_class:
                self._instances[name] = agent_class()
        return self._instances.get(name)

    def get_all_agent_names(self) -> List[str]:
        """Получение всех зарегистрированных агентов"""
        return list(self._agents.keys())

    def create_agent_executor(self, agent_name: str) -> BaseAgent | None:
        """Создание executor для агента (если нужно)"""
        agent = self.get_agent_instance(agent_name)
        if agent:
            return agent
        return None


agent_registry = AgentRegistry()
