# src/edms_assistant/agents/agent.py

from typing import Dict, Any
from langgraph.graph import StateGraph, END
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.core.registry import agent_registry


def create_agent_graph():
    """Создание графа агента с поддержкой прерываний и уточнений"""
    graph = StateGraph(GlobalState)

    # Узел обработки - используем main_planner_agent
    async def process_node(state: GlobalState) -> Dict[str, Any]:
        # Проверяем, является ли сообщение числовым уточнением (например, "2")
        if state.user_message.strip().isdigit() and hasattr(state,
                                                            'clarification_context') and state.clarification_context:
            # Это уточнение - передаем в employee_agent напрямую
            employee_agent = agent_registry.get_agent_instance("employee_agent")
            if employee_agent:
                result = await employee_agent.process(state)
                return result

        # В остальных случаях используем main_planner_agent
        planner_agent = agent_registry.get_agent_instance("main_planner_agent")
        if planner_agent:
            result = await planner_agent.process(state)
            return result
        else:
            return {
                "messages": [],
                "error": f"Planner agent not found"
            }

    # Добавляем узел
    graph.add_node("process", process_node)

    # Устанавливаем точку входа
    graph.set_entry_point("process")

    # Добавляем переход
    graph.add_edge("process", END)

    # Используем MemorySaver как в документации LangChain
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)