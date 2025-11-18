# src/edms_assistant/agents/agent_factory.py
from src.edms_assistant.core.agent_registry import agent_registry
from src.edms_assistant.agents.main_planner_agent import MainPlannerAgent
from src.edms_assistant.agents.employee_agent import EmployeeAgent
from src.edms_assistant.agents.document_agent import DocumentAgent
from src.edms_assistant.agents.attachment_agent import AttachmentAgent
from src.edms_assistant.core.settings import settings

class AgentFactory:
    """
    Фабрика для создания агентов.
    """
    @staticmethod
    def register_all_agents():
        """Регистрация всех доступных агентов в реестре."""
        agent_registry.register("main_planner_agent", MainPlannerAgent)
        agent_registry.register("employee_agent", EmployeeAgent)
        agent_registry.register("document_agent", DocumentAgent)
        agent_registry.register("attachment_agent", AttachmentAgent)

    @staticmethod
    def get_agent(agent_name: str):
        """Получение агента по имени из реестра."""
        return agent_registry.get_agent_instance(agent_name)

    @staticmethod
    def get_available_agents() -> list:
        """Получение списка всех зарегистрированных агентов."""
        return agent_registry.get_all_agent_names()

# Вызов статического метода при импорте
AgentFactory.register_all_agents()