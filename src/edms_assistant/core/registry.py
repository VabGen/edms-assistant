# src/edms_assistant/core/registry.py
import threading
from typing import Dict, Type, Any, Optional, List
from src.edms_assistant.core.base_agent import BaseAgent


class AgentRegistry:
    """Централизованный реестр агентов с поддержкой безопасности и логирования"""

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
        """Регистрация класса агента с валидацией"""
        if not issubclass(agent_class, BaseAgent):
            raise TypeError(
                f"Agent class must inherit from BaseAgent, got {agent_class}"
            )

        if name in self._agents:
            import logging

            logging.warning(f"Agent {name} is already registered, overwriting")

        self._agents[name] = agent_class

    def get_agent_class(self, name: str) -> Optional[Type[BaseAgent]]:
        """Получение класса агента"""
        return self._agents.get(name)

    def get_agent_instance(self, name: str, **kwargs) -> Optional[BaseAgent]:
        """Получение экземпляра агента с lazy initialization"""
        if name not in self._instances:
            agent_class = self.get_agent_class(name)
            if agent_class:
                # Предполагаем, что у агента есть метод для получения LLM
                from src.edms_assistant.infrastructure.llm.llm import get_llm

                llm = get_llm()

                # Получаем инструменты для агента
                tools = self._get_agent_tools(name)

                self._instances[name] = agent_class(llm=llm, tools=tools)
        return self._instances.get(name)

    def _get_agent_tools(self, agent_name: str) -> List:
        """Получение инструментов для конкретного агента"""
        # Импортируем инструменты в зависимости от типа агента
        if agent_name == "document_agent":
            from src.edms_assistant.tools.document import (
                get_document_tool,
                search_documents_tool,
                create_document_tool,
                update_document_tool,
            )

            return [
                get_document_tool,
                search_documents_tool,
                create_document_tool,
                update_document_tool,
            ]
        elif agent_name == "employee_agent":
            from src.edms_assistant.tools.employee import (
                get_employee_by_id_tool,
                find_responsible_tool,
                add_responsible_to_document_tool,
            )

            return [
                get_employee_by_id_tool,
                find_responsible_tool,
                add_responsible_to_document_tool,
            ]
        elif agent_name == "attachment_agent":
            from src.edms_assistant.tools.attachment import (
                summarize_attachment_tool,
                extract_and_summarize_file_tool,
            )

            return [summarize_attachment_tool, extract_and_summarize_file_tool]
        elif agent_name == "main_planner_agent":
            from src.edms_assistant.tools.document import (
                get_document_tool,
                search_documents_tool,
            )
            from src.edms_assistant.tools.employee import (
                find_responsible_tool,
                get_employee_by_id_tool,
            )
            from src.edms_assistant.tools.attachment import (
                summarize_attachment_tool,
                extract_and_summarize_file_tool,
            )

            return [
                get_document_tool,
                search_documents_tool,
                find_responsible_tool,
                get_employee_by_id_tool,
                summarize_attachment_tool,
                extract_and_summarize_file_tool,
            ]
        return []

    def get_all_agent_names(self) -> List[str]:
        """Получение всех зарегистрированных агентов"""
        return list(self._agents.keys())

    def create_agent_executor(self, agent_name: str) -> Optional[BaseAgent]:
        """Создание executor для агента"""
        agent = self.get_agent_instance(agent_name)
        if agent:
            return agent
        return None


agent_registry = AgentRegistry()
