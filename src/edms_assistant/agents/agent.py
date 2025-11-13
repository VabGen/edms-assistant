# src/edms_assistant/agents/agent.py
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.pregel import Pregel
from langgraph.types import Command
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.core.registry import agent_registry


def create_agent_graph():
    """Создание production-grade графа агента с универсальным прерыванием и постоянным хранилищем"""

    # Создаем граф с типизированным состоянием
    graph = StateGraph(GlobalState)

    # Узел планирования - основной узел
    async def planning_node(state: GlobalState) -> Dict[str, Any]:
        """Планирующий узел - анализирует запрос и формирует план"""
        planner_agent = agent_registry.get_agent_instance("main_planner_agent")
        if not planner_agent:
            return {"error": "Main planner agent not found"}

        result = await planner_agent.process(state)
        return result

    # Узел обработки документа
    async def document_node(state: GlobalState) -> Dict[str, Any]:
        """Узел обработки документов"""
        document_agent = agent_registry.get_agent_instance("document_agent")
        if not document_agent:
            return {"error": "Document agent not found"}

        result = await document_agent.process(state)
        return result

    # Узел обработки сотрудников
    async def employee_node(state: GlobalState) -> Dict[str, Any]:
        """Узел обработки сотрудников"""
        employee_agent = agent_registry.get_agent_instance("employee_agent")
        if not employee_agent:
            return {"error": "Employee agent not found"}

        result = await employee_agent.process(state)
        return result

    # Узел обработки вложений
    async def attachment_node(state: GlobalState) -> Dict[str, Any]:
        """Узел обработки вложений"""
        attachment_agent = agent_registry.get_agent_instance("attachment_agent")
        if not attachment_agent:
            return {"error": "Attachment agent not found"}

        result = await attachment_agent.process(state)
        return result

    # Добавляем все узлы
    graph.add_node("planning", planning_node)
    graph.add_node("document", document_node)
    graph.add_node("employee", employee_node)
    graph.add_node("attachment", attachment_node)

    # Устанавливаем точку входа
    graph.add_edge(START, "planning")

    # Добавляем переходы с условиями
    def route_after_planning(state: GlobalState) -> str:
        """Маршрутизация после планирования"""
        # В простом случае всегда идем к employee, можно улучшить
        # Проверяем, есть ли документ_id или другие критерии
        if state.document_id:
            return "document"
        elif state.uploaded_file_path:
            return "attachment"
        else:
            return "employee"

    def route_after_employee(state: GlobalState) -> str:
        """Маршрутизация после обработки сотрудника"""
        # После обработки сотрудника завершаем или возвращаемся к планированию
        return END

    # Добавляем условные переходы
    graph.add_conditional_edges(
        "planning",
        route_after_planning,
        {"employee": "employee", "document": "document", "attachment": "attachment"}
    )

    graph.add_conditional_edges(
        "employee",
        route_after_employee,
        {END: END, "planning": "planning"}
    )

    # Прямые переходы между узлами
    graph.add_edge("document", END)
    graph.add_edge("attachment", END)

    # Используем MemorySaver как постоянное хранилище (в проде использовать AsyncPostgresSaver)
    checkpointer = MemorySaver()

    # Компилируем граф с checkpointer - это позволяет использовать прерывания
    compiled_graph = graph.compile(
        checkpointer=checkpointer,
        # Убираем interrupt_before и interrupt_after, т.к. прерывания теперь происходят внутри узлов
        # LangGraph автоматически обрабатывает interrupt через checkpointer
    )

    return compiled_graph