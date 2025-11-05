# src\edms_assistant\core\agents\employee_agent.py
import re
import json
import logging
from uuid import UUID
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from src.edms_assistant.core.state.global_state import GlobalState
from src.edms_assistant.core.tools.employee_tool import find_responsible_tool
from src.edms_assistant.infrastructure.llm.llm import get_llm
from src.edms_assistant.core.tools.get_employee_by_id_tool import get_employee_by_id_tool
from src.edms_assistant.core.tools.add_responsible_tool import add_responsible_to_document_tool
from langchain_core.messages import ToolMessage, AIMessage

logger = logging.getLogger(__name__)

llm = get_llm()

async def find_responsible_node(state: GlobalState) -> dict:
    """
    Извлекает фамилию из agent_input или из сообщения пользователя и ищет ответственных.
    Если найдено несколько — вызывает прерывание для уточнения.
    Если пришло уточнение (ID) — получает сотрудника по ID и, если нужно, добавляет в документ.
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

                    # ✅ Проверяем, нужно ли добавлять, по флагу из state
                    # Эти флаги должны быть установлены до interrupt в orchestrator_planner
                    should_add_flag = state.get("should_add_responsible_after_clarification", False)
                    document_id_to_add = state.get("document_id_to_add")

                    if should_add_flag and document_id_to_add:
                        logger.info(f"find_responsible_node: resume - should_add_flag = {should_add_flag}, doc_id_to_add = {document_id_to_add}")
                        # ✅ Направляем в add_responsible_node
                        return {
                            "selected_candidate_id": selected_id,
                            "document_id_to_add": document_id_to_add,
                            "next_node": "add_responsible",
                        }

                    # ✅ Иначе — просто возвращаем информацию о сотруднике
                    service_token = state["service_token"]
                    employee_json = await get_employee_by_id_tool.ainvoke({
                        "employee_id": selected_id,
                        "service_token": service_token
                    })
                    employee_data = json.loads(employee_json)
                    if "error" in employee_data:
                        logger.warning(f"find_responsible_node: failed to get employee: {employee_data}")
                        return {"messages": [AIMessage(content=f"Ошибка: {employee_data['message']}")]}

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
            "document_id": agent_input.get("document_id"),
        })

    # Если кандидат один — проверяем, нужно ли добавлять в документ
    if candidates:
        selected_candidate = candidates[0]
        user_msg_lower = state["user_message"].lower()
        document_id_from_input = agent_input.get("document_id")
        # Проверим, содержит ли сообщение просьбу "добавить в документ"
        add_keywords = ["добавь", "в документ", "включить", "включить в", "добавить в"]
        should_add = document_id_from_input and any(kw in user_msg_lower for kw in add_keywords)

        if should_add:
            # ✅ Направляем в add_responsible_node
            return {
                "selected_candidate_id": selected_candidate["id"],
                "document_id_to_add": document_id_from_input,
                "next_node": "add_responsible",
            }

        # ✅ Иначе — возвращаем информацию о кандидате
        return {"messages": [AIMessage(content=json.dumps(selected_candidate, ensure_ascii=False, indent=2))]}
    else:
        response_text = "Кандидаты не найдены."

    return {"messages": [AIMessage(content=response_text)]}

# ✅ добавление сотрудника
async def add_responsible_node(state: GlobalState) -> dict:
    """
    Добавляет выбранного сотрудника в документ.
    """
    logger.info("add_responsible_node: started")
    selected_id = state.get("selected_candidate_id")
    document_id_str = state.get("document_id_to_add")
    service_token = state["service_token"]

    logger.info(f"add_responsible_node: selected_id={selected_id}, document_id_str={document_id_str}")

    if not selected_id or not document_id_str:
        logger.warning(f"add_responsible_node: missing selected_id ({selected_id}) or document_id ({document_id_str})")
        return {"messages": [AIMessage(content="Ошибка: не указаны ID сотрудника или документа.")]}

    try:
        emp_uuid = UUID(selected_id)
        doc_uuid = UUID(document_id_str)
    except ValueError as e:
        logger.error(f"add_responsible_node: invalid UUID: {e}")
        return {"messages": [AIMessage(content="Ошибка: неверный формат ID сотрудника или документа.")]}

    logger.info(f"add_responsible_node: adding employee {emp_uuid} to document {doc_uuid}")

    try:
        result = await add_responsible_to_document_tool.ainvoke({
            "document_id": doc_uuid,
            "responsible_id": emp_uuid,
            "service_token": service_token
        })

        result_data = json.loads(result)
        if "error" in result_data:
            msg = f"Не удалось добавить ответственного: {result_data.get('message', 'Неизвестная ошибка.')}"
            logger.error(f"add_responsible_node: {msg}")
            return {"messages": [AIMessage(content=msg)]}

        # ✅ Успешно добавлен
        name = f"{result_data.get('last_name', '')} {result_data.get('first_name', '')} {result_data.get('middle_name', '')}".strip()
        success_msg = f"Сотрудник {name} успешно добавлен как ответственный в документ."
        logger.info(f"add_responsible_node: {success_msg}")
        return {"messages": [AIMessage(content=success_msg)]}

    except Exception as e:
        logger.error(f"add_responsible_node: failed to add responsible: {e}", exc_info=True)
        return {"messages": [AIMessage(content=f"Ошибка при добавлении ответственного: {str(e)}")]}

# ✅ Функция маршрутизации после find_responsible_node
def route_after_find_responsible(state: GlobalState) -> str:
    next_node = state.get("next_node")
    if next_node == "add_responsible":
        return "add_responsible"
    return END

def create_employee_agent_graph():
    workflow = StateGraph(GlobalState)

    workflow.add_node("find_responsible", find_responsible_node)
    workflow.add_node("add_responsible", add_responsible_node)

    workflow.set_entry_point("find_responsible")

    # Условный переход после find_responsible
    workflow.add_conditional_edges(
        "find_responsible",
        route_after_find_responsible,
        {
            "add_responsible": "add_responsible",
            END: END
        }
    )
    # Прямой переход из add_responsible к концу
    workflow.add_edge("add_responsible", END)

    return workflow.compile()