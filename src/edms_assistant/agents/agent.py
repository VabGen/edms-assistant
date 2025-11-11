from typing import Dict, Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.config.settings import settings
from src.edms_assistant.core.registry import agent_registry


def create_agent_graph():
    """Создание графа агента с поддержкой прерываний и уточнений"""
    graph = StateGraph(GlobalState)

    # Узел обработки - используем планирующий агент
    async def process_node(state: GlobalState) -> Dict[str, Any]:
        planner_agent = agent_registry.get_agent_instance("main_planner_agent")
        if planner_agent:
            result = await planner_agent.process(state)

            # Проверяем, нужно ли прерывание для уточнения
            if result.get("requires_clarification", False):
                clarification_context = result.get("clarification_context", {})
                if clarification_context.get("type") == "employee_selection":
                    candidates = clarification_context.get("candidates", [])
                    if candidates:
                        # 🔴 ПРЕРЫВАНИЕ: нужно уточнение
                        return interrupt({
                            "type": "clarification",
                            "candidates": candidates,
                            "original_query": clarification_context.get("original_query", {}),
                        })

            return result
        else:
            return {
                "messages": [],
                "error": f"Planner agent not found"
            }

    # Узел для обработки уточнений
    async def handle_clarification_node(state: GlobalState) -> Dict[str, Any]:
        """Узел для обработки уточнений от пользователя"""
        user_message = state.user_message

        # Проверяем, является ли сообщение числом (выбор из списка)
        if user_message.strip().isdigit():
            selected_number = int(user_message.strip())

            # Нужно получить информацию о кандидатах из предыдущего прерывания
            # В LangGraph это делается через сохранение состояния
            employee_agent = agent_registry.get_agent_instance("employee_agent")
            if employee_agent:
                # Вызываем специальный метод для обработки выбора
                result = await employee_agent.process_with_selection(state, selected_number)
                return result

        # Если не удалось обработать - возвращаем сообщение о необходимости уточнения
        return {
            "messages": ["Пожалуйста, укажите корректный номер из списка."],
            "requires_clarification": False
        }

    # Добавляем узлы
    graph.add_node("process", process_node)
    graph.add_node("handle_clarification", handle_clarification_node)

    # Устанавливаем точку входа
    graph.set_entry_point("process")

    # Добавляем условный переход
    def should_handle_clarification(state: GlobalState):
        user_message = state.user_message
        if user_message and user_message.strip().isdigit():
            return "handle_clarification"
        return END

    graph.add_conditional_edges(
        "process",
        should_handle_clarification,
        {
            "handle_clarification": "handle_clarification",
            END: END
        }
    )

    graph.add_edge("handle_clarification", END)

    # Создаем checkpointer в зависимости от настроек
    # if settings.checkpointer_type == "sqlite":
    #     import sqlite3
    #     conn = sqlite3.connect(settings.sqlite_path, check_same_thread=False)
        # from langgraph.checkpoint.sqlite import SqliteSaver
        # checkpointer = SqliteSaver(conn)
    # else:
    #     from langgraph.checkpoint.memory import MemorySaver
    #     checkpointer = MemorySaver()

    checkpointer = None

    checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)