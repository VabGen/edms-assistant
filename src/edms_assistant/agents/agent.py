# src/edms_assistant/agents/agent.py
from typing import Dict, Any
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.core.agent_registry import agent_registry
from src.edms_assistant.core.nlu_classifier import NLUClassifier
from src.edms_assistant.infrastructure.checkpointer.postgres_checkpointer import get_checkpointer
import logging

logger = logging.getLogger(__name__)

# Инициализируем NLU классификатор
nlu_classifier = NLUClassifier()


async def routing_node(state: GlobalState) -> Dict[str, Any]:
    """
    Универсальный узел маршрутизации.
    Использует NLU для определения намерения и выбирает следующий агент.
    """
    try:
        # 1. Классифицируем намерение
        intent_data = await nlu_classifier.classify(state.user_message)
        predicted_intent = intent_data.get("intent", "unknown")
        entities = intent_data.get("entities", {})

        # 2. Обновляем состояние с NLU данными
        # NOTE: В GlobalState поля immutable, поэтому мы не можем изменить state напрямую.
        # Вместо этого возвращаем словарь с обновлениями, которые LangGraph применит к состоянию.
        # Предположим, что в GlobalState есть поля nlu_intent и nlu_entities
        # и поле next_node для маршрутизации.
        # Если поле next_node не определено, добавим его к state.

        # 3. Маршрутизация на основе намерения
        # Эти правила можно вынести в конфигурацию
        intent_to_agent_map = {
            "find_employee": "employee_agent",
            "get_document_info": "document_agent",
            "search_documents": "document_agent",
            "analyze_attachment": "attachment_agent",
            "unknown": "main_planner_agent",  # По умолчанию
        }

        target_agent = intent_to_agent_map.get(predicted_intent, "main_planner_agent")

        logger.info(f"Routing to agent '{target_agent}' based on intent '{predicted_intent}'")

        # 4. Возвращаем обновления состояния
        # Это состояние будет объединено с текущим, и LangGraph продолжит выполнение
        return {
            "nlu_intent": predicted_intent,
            "nlu_entities": entities,
            "current_agent": target_agent,  # Устанавливаем текущего агента
            "next_node": target_agent  # Устанавливаем следующий узел для conditional edge
        }

    except Exception as e:
        logger.error(f"Error in routing node: {e}", exc_info=True)
        # В случае ошибки NLU, используем планирующий агент
        return {
            "current_agent": "main_planner_agent",
            "next_node": "main_planner_agent"
        }


async def dynamic_agent_node(state: GlobalState) -> Dict[str, Any]:
    """
    Универсальный узел, который вызывает агента из реестра.
    """
    # Используем state.current_agent для определения агента
    agent_name = state.current_agent

    # Получаем экземпляр агента из реестра
    agent_instance = agent_registry.get_agent_instance(agent_name)
    if not agent_instance:
        error_msg = f"Agent '{agent_name}' not found in registry."
        logger.error(error_msg)
        return {"messages": [AIMessage(content=error_msg)], "error": error_msg}

    logger.info(f"Executing agent '{agent_name}'")

    try:
        # Вызываем процесс агента. Передаем только state.
        result = await agent_instance.process(state)
        # Результат от агента должен соответствовать структуре GlobalState
        # или быть совместимым с ней для объединения.
        # Если агент возвращает interrupt, LangGraph его обработает.
        return result
    except Exception as e:
        logger.error(f"Error executing agent '{agent_name}': {e}", exc_info=True)
        error_msg = f"Ошибка выполнения агента {agent_name}: {str(e)}"
        return {"messages": [AIMessage(content=error_msg)], "error": str(e)}


def create_agent_graph():
    """
    Создает production-ready граф агента с поддержкой прерываний и постоянного хранилища.
    """
    graph = StateGraph(GlobalState)

    # Добавляем узлы
    graph.add_node("router", routing_node)
    graph.add_node("dynamic_agent", dynamic_agent_node)

    # Устанавливаем точку входа
    graph.add_edge(START, "router")

    # Условный переход после маршрутизации
    # route_after_router теперь использует state.next_node
    def route_after_router(state: GlobalState) -> str:
        # Получаем агента из состояния (установленного в routing_node)
        next_node_name = getattr(state, 'next_node', 'main_planner_agent')  # Fallback на main_planner
        # Проверяем, существует ли узел с таким именем
        # LangGraph сам проверит это, но можно добавить валидацию
        # Возвращаем имя узла, к которому нужно перейти
        # Это должно соответствовать именам узлов, добавленных через graph.add_node
        # Однако dynamic_agent один. Мы передаем туда имя агента через состояние.
        # Поэтому, всегда возвращаем "dynamic_agent".
        # А логика выбора конкретного агента внутри dynamic_agent_node.
        # Или, можно добавить конкретные узлы для каждого агента.
        # Но для универсальности, оставим dynamic_agent.
        # Важно: conditional edge должен возвращать имя *узла*, а не имя агента.
        # Наш dynamic_agent - это один узел, который вызывает разные агенты.
        # Поэтому route_after_router всегда возвращает "dynamic_agent".
        # Но если мы хотим иметь отдельные узлы для каждого агента, нужно их добавить:
        # graph.add_node("employee_agent", dynamic_agent_node_employee)
        # graph.add_node("document_agent", dynamic_agent_node_document)
        # и т.д.
        # Или использовать один dynamic_agent и передавать ему имя через состояние.
        # Второй подход проще и гибче.
        # Поэтому возвращаем "dynamic_agent".
        return "dynamic_agent"

    graph.add_conditional_edges(
        "router",
        route_after_router,
        {"dynamic_agent": "dynamic_agent"}  # Маршрут всегда ведет к dynamic_agent
    )

    # Прямой переход от dynamic_agent к END
    # Если dynamic_agent возвращает interrupt, выполнение остановится, и состояние сохранится.
    graph.add_edge("dynamic_agent", END)

    # Получаем checkpointer из инфраструктуры
    checkpointer = get_checkpointer()

    # Компилируем граф
    compiled_graph = graph.compile(checkpointer=checkpointer)

    return compiled_graph
