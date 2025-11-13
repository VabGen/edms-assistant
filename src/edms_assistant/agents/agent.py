# src/edms_assistant/agents/agent.py
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.pregel import Pregel
from langgraph.types import Command
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.core.registry import agent_registry
from src.edms_assistant.core.middleware.hitl_middleware import HumanInTheLoopMiddleware


def create_agent_graph():
    """Создание production-grade графа агента с поддержкой HITL и прерываний"""

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

    # Узел уточнения
    async def clarification_node(state: GlobalState) -> Dict[str, Any]:
        """Узел обработки уточнений от пользователя"""
        # Если это числовое уточнение - передаем в employee_agent
        if state.user_message.strip().isdigit() and state.clarification_context:
            employee_agent = agent_registry.get_agent_instance("employee_agent")
            if employee_agent:
                result = await employee_agent.process(state)
                return result

        # По умолчанию возвращаем к планированию
        planner_agent = agent_registry.get_agent_instance("main_planner_agent")
        if planner_agent:
            result = await planner_agent.process(state)
            return result

        return {"error": "Clarification processing failed"}

    # Узел HITL - обработка решений пользователя
    async def hitl_node(state: GlobalState) -> Dict[str, Any]:
        """Узел обработки решений HITL"""
        if state.hitl_pending and state.hitl_request:
            # Здесь обрабатываем решения пользователя
            # и возобновляем выполнение с командами
            decisions = state.hitl_decisions
            if decisions:
                # Формируем команду для возобновления
                return {"__interrupt__": Command(resume={"decisions": decisions})}

        return {}

    # Добавляем все узлы
    graph.add_node("planning", planning_node)
    graph.add_node("document", document_node)
    graph.add_node("employee", employee_node)
    graph.add_node("attachment", attachment_node)
    graph.add_node("clarification", clarification_node)
    graph.add_node("hitl", hitl_node)

    # Устанавливаем точку входа
    graph.add_edge(START, "planning")

    # Добавляем переходы с условиями
    def should_clarify(state: GlobalState) -> str:
        """Определяет, требуется ли уточнение"""
        if state.requires_clarification:
            return "clarification"
        elif state.hitl_pending:
            return "hitl"
        else:
            return "document"  # по умолчанию идем к обработке документов

    def route_after_clarification(state: GlobalState) -> str:
        """Маршрутизация после уточнения"""
        if state.next_node_after_clarification:
            return state.next_node_after_clarification
        return "planning"

    # Добавляем условные переходы
    graph.add_conditional_edges(
        "planning",
        should_clarify,
        {"clarification": "clarification", "hitl": "hitl", "document": "document"},
    )

    graph.add_conditional_edges(
        "clarification",
        route_after_clarification,
        {
            "document": "document",
            "employee": "employee",
            "attachment": "attachment",
            "planning": "planning",
        },
    )

    # Прямые переходы между узлами
    graph.add_edge("document", END)
    graph.add_edge("employee", END)
    graph.add_edge("attachment", END)
    graph.add_edge("hitl", "planning")

    # Используем MemorySaver для хранения состояния
    checkpointer = MemorySaver()

    # Компилируем граф с HITL middleware
    compiled_graph = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["clarification", "hitl"],  # Прерывания перед этими узлами
        interrupt_after=["planning"],  # Прерывания после планирования при необходимости
    )

    return compiled_graph
