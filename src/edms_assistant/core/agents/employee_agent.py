# src/edms_assistant/core/agents/employee_agent.py

import re
import json
import logging
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from src.edms_assistant.core.state.global_state import GlobalState
from src.edms_assistant.core.tools.employee_tool import find_responsible_tool
from src.edms_assistant.infrastructure.llm.llm import get_llm
from src.edms_assistant.core.tools.get_employee_by_id_tool import get_employee_by_id_tool  # ✅ Новый инструмент
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage

logger = logging.getLogger(__name__)

llm = get_llm()


async def find_responsible_node(state: GlobalState) -> dict:
    """
    Извлекает фамилию из agent_input или из сообщения пользователя и ищет ответственных.
    Если найдено несколько — вызывает прерывание для уточнения.
    Если пришло уточнение (ID) — получает сотрудника по ID и возвращает полный JSON.
    """
    # ✅ Проверяем, пришло ли уточнение (ToolMessage)
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        if isinstance(last_message, ToolMessage):
            try:
                selected_data = json.loads(last_message.content)
                selected_id = selected_data.get("id")
                if selected_id:
                    logger.info(f"find_responsible_node: user selected ID {selected_id}")
                    # ✅ Вызываем НОВЫЙ инструмент
                    service_token = state["service_token"]
                    employee_json = await get_employee_by_id_tool.ainvoke({
                        "employee_id": selected_id,
                        "service_token": service_token
                    })
                    employee_data = json.loads(employee_json)
                    if "error" in employee_data:
                        return {"messages": [AIMessage(content=f"Ошибка: {employee_data['message']}")]}

                    # ✅ Возвращаем полный JSON как строку в content
                    return {"messages": [AIMessage(content=json.dumps(employee_data, ensure_ascii=False, indent=2))]}

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"find_responsible_node: failed to parse ToolMessage: {e}")
                return {"messages": [AIMessage(content="Не удалось обработать выбор.")]}

    # ✅ Обычная логика поиска по фамилии
    agent_input = state.get("agent_input", {})
    last_name = agent_input.get("last_name")

    if not last_name:
        user_msg = state["user_message"]
        pattern = r'\b([А-ЯЁ][а-яё]+)\b'
        matches = re.findall(pattern, user_msg)
        last_name = next((m for m in matches if len(m) > 2), None)

    if not last_name:
        return {"messages": [AIMessage(content="Фамилия не найдена в сообщении.")]}

    service_token = state["service_token"]

    args = {
        "last_name": last_name,
        "service_token": service_token,
        "first_name": None,
        "department_id": None
    }

    output = await find_responsible_tool.ainvoke(args)

    try:
        parsed_output = json.loads(output)
        if isinstance(parsed_output, dict) and "error" in parsed_output:
            error_msg = parsed_output.get("error", "Неизвестная ошибка")
            return {"messages": [AIMessage(content=f"Ошибка при поиске сотрудника: {error_msg}")]}

        candidates = parsed_output

    except (json.JSONDecodeError, TypeError):
        candidates = []

    if isinstance(candidates, list) and len(candidates) > 1:
        # 🔴 ПРЕРЫВАНИЕ: нужно уточнение
        logger.info(f"find_responsible_node: found {len(candidates)} candidates, interrupting for clarification.")
        return interrupt({
            "type": "clarification",
            "candidates": candidates,
            "document_id": state.get("document_id"),
        })

    # Если кандидат один — сразу возвращаем результат (полный JSON)
    if candidates:
        # Для единичного кандидата тоже возвращаем JSON, как в Java-контроллере
        # Но find_responsible_tool возвращает список, поэтому берём первого
        employee_data = candidates[0]
        return {"messages": [AIMessage(content=json.dumps(employee_data, ensure_ascii=False, indent=2))]}
    else:
        response_text = "Кандидаты не найдены."

    return {"messages": [AIMessage(content=response_text)]}


def create_employee_agent_graph():
    workflow = StateGraph(GlobalState)

    workflow.add_node("find_responsible", find_responsible_node)

    workflow.set_entry_point("find_responsible")
    workflow.add_edge("find_responsible", END)

    return workflow.compile()