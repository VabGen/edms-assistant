# src/edms_assistant/core/nodes.py
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.core.agent_registry import agent_registry


# === Узлы графа ===
async def routing_node(state: GlobalState) -> dict:
    user_message = state.user_message

    # --- НОВОЕ: Проверяем, ждём ли мы ответ на прерывание ---
    if state.waiting_for_hitl_response:
        # Если ждём ответ, направляем в узел, который вызвал interrupt
        last_interrupted_agent = state.hitl_request.get("initiated_by_agent",
                                                        "employee") if state.hitl_request else "employee"
        agent_to_node_map = {
            "employee_agent": "employee",
            "document_agent": "document",
            "attachment_agent": "attachment",
        }
        return {"next_node": agent_to_node_map.get(last_interrupted_agent, "employee"),
                "current_agent": last_interrupted_agent}

    # --- ЛОГИКА МАРШРУТИЗАЦИИ ---
    if any(keyword in user_message.lower() for keyword in ["сотрудник", "работник", "ответственный", "человек"]):
        return {"next_node": "employee", "current_agent": "employee_agent"}
    elif any(keyword in user_message.lower() for keyword in ["документ", "файл", "договор", "акт"]):
        return {"next_node": "document", "current_agent": "document_agent"}
    elif any(keyword in user_message.lower() for keyword in ["вложение", "attachment", "прикрепленный"]):
        return {"next_node": "attachment", "current_agent": "attachment_agent"}
    else:
        return {"next_node": "planning", "current_agent": "main_planner_agent"}


async def planning_node(state: GlobalState) -> dict:
    agent = agent_registry.get_agent_instance("main_planner_agent")
    if agent:
        return await agent.process(state)
    else:
        return {"error": "MainPlannerAgent not found"}


async def employee_node(state: GlobalState) -> dict:
    agent = agent_registry.get_agent_instance("employee_agent")
    if agent:
        return await agent.process(state)
    else:
        return {"error": "EmployeeAgent not found"}


async def document_node(state: GlobalState) -> dict:
    agent = agent_registry.get_agent_instance("document_agent")
    if agent:
        return await agent.process(state)
    else:
        return {"error": "DocumentAgent not found"}


async def attachment_node(state: GlobalState) -> dict:
    agent = agent_registry.get_agent_instance("attachment_agent")
    if agent:
        return await agent.process(state)
    else:
        return {"error": "AttachmentAgent not found"}
