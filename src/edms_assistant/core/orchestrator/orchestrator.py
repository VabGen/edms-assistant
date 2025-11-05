# src/edms_assistant/core/orchestrator/orchestrator.py

import logging
from langgraph.graph import StateGraph, END
from src.edms_assistant.core.state.global_state import GlobalState
from src.edms_assistant.infrastructure.llm.llm import get_llm
from src.edms_assistant.core.agents.document_agent import create_document_agent_graph
from src.edms_assistant.core.agents.attachment_agent import create_attachment_agent_graph
from src.edms_assistant.core.agents.employee_agent import create_employee_agent_graph
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, PromptTemplate
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

llm = get_llm()

async def orchestrator_planner(state: GlobalState) -> dict:
    user_msg = state["user_message"]
    document_id = state.get("document_id")
    uploaded_file_path = state.get("uploaded_file_path")
    current_document = state.get("current_document", "Нет данных о документе.")

    logger.info(f"orchestrator_planner: user_msg={user_msg}, document_id={document_id}, uploaded_file_path={uploaded_file_path}")

    # ✅ Если файл загружен и сообщение про него — направляем в attachment_agent
    if uploaded_file_path and any(kw in user_msg.lower() for kw in ["файл", "содержимое", "суммируй", "приложение", "вложение"]):
        logger.info(f"orchestrator_planner: directing to attachment_agent (file uploaded)")
        return {
            "next_agent": "attachment",
            "agent_input": {"uploaded_file_path": uploaded_file_path},
            "requires_clarification": False
        }

    # ✅ Если document_id есть И (в сообщении есть ключевые слова ИЛИ пользователь спрашивает про ВЛОЖЕНИЕ) — направляем в attachment_agent
    attachment_keywords = [
        "вложение", "файл", "приложение", "содержание файла", "приложен",
        "о чем вложение", "что в вложении", "содержимое вложения", "суммируй вложение", "опиши вложение",
        "содержание вложения", "вложения", "прикрепленный", "прикреплённый", "pdf", "docx", "txt",
        "о чем вложение", "что в вложении", "содержимое вложения", "суммируй вложение", "опиши вложение"
    ]
    if document_id and any(kw in user_msg.lower() for kw in attachment_keywords):
        logger.info(f"orchestrator_planner: directing to attachment_agent (document + attachment keywords)")
        return {
            "next_agent": "attachment",
            "agent_input": {"document_id": document_id},
            "requires_clarification": False
        }

    # ✅ Если в сообщении упоминается "документ" и есть document_id — направляем в document_agent
    document_keywords = [
        "статус", "реквизиты", "содержание", "о чем документ", "кто автор", "дата создания",
        "номер", "дата регистрации", "подписан", "согласован", "исполнитель", "профиль"
    ]
    is_about_doc_content = any(kw in user_msg.lower() for kw in document_keywords)
    is_about_attachment = any(kw in user_msg.lower() for kw in attachment_keywords)
    if "документ" in user_msg.lower() and document_id and not is_about_attachment and is_about_doc_content:
        logger.info(f"orchestrator_planner: directing to document_agent (document keywords + not attachment)")
        return {
            "next_agent": "document",
            "agent_input": {"document_id": document_id},
            "requires_clarification": False
        }

    # ✅ Если в сообщении упоминается поиск/добавление сотрудника — направляем в employee_agent
    employee_keywords = [
        "специалист", "найди", "добавь", "ответственный", "сотрудник", "поиск", "искать", "найти", "выбери", "кто"
    ]
    import re
    words = user_msg.split()
    has_surname = any(w.istitle() and len(w) > 2 for w in words)  # например, Иванов

    # ✅ Проверим, нужно ли добавлять
    add_keywords = ["добавь", "в документ", "включить", "включить в", "добавить в"]
    should_add_flag = document_id and any(kw in user_msg.lower() for kw in add_keywords)

    if any(kw in user_msg.lower() for kw in employee_keywords) and has_surname:
        logger.info(f"orchestrator_planner: directing to employee_agent (employee keywords + surname)")
        # Попробуем извлечь фамилию
        pattern = r'\b([А-ЯЁ][а-яё]+)\b'
        matches = re.findall(pattern, user_msg)
        surname = next((m for m in matches if len(m) > 2), None)
        agent_input_dict = {}
        if surname:
            agent_input_dict["last_name"] = surname
        if document_id:
            agent_input_dict["document_id"] = document_id

        # ✅ Возвращаем обновления state для employee_agent
        state_updates = {
            "next_agent": "employee",
            "agent_input": agent_input_dict,
            "requires_clarification": False
        }

        # ✅ Если нужно добавить — устанавливаем флаги в state
        if should_add_flag and document_id:
            state_updates["should_add_responsible_after_clarification"] = True
            state_updates["document_id_to_add"] = document_id
            logger.info(f"orchestrator_planner - should_add_flag: {state_updates}")

        return state_updates

    # Если не сработало, используем LLM
    system_template = """
Ты — планировщик запросов к EDMS. Ты должен выбрать, какой агент должен обработать запрос пользователя.
Доступные агенты:
- document: для работы с содержимым документа (просмотр, поиск данных, статус и т.д.).
- attachment: для работы с вложениями документа (суммаризация, извлечение текста).
- employee: для поиска сотрудников (ответственных, специалистов и т.д.).
- default: если запрос не подходит ни под один из вышеуказанных.

Правила:
- Если запрос касается **содержимого, статуса, реквизитов** документа — используй `document`.
- Если запрос касается **вложения, файла, приложения** — используй `attachment`.
- Если запрос касается **поиска, добавления, выбора сотрудника** — используй `employee`.
- Если `document_id` есть, но запрос явно не про документ — не используй `document`.

Формат ответа:
- next_agent: "document" / "attachment" / "employee" / "default"
- agent_input: {{"document_id": "..."}} если нужен документ, иначе {{}}
"""

    system_prompt = PromptTemplate.from_template(system_template)
    system_message_prompt = SystemMessagePromptTemplate(prompt=system_prompt)

    human_template = "Пользователь: {user_msg}\n\nДокумент: {current_document}\n\nID документа: {document_id}\n\nЗагруженный файл: {uploaded_file_path}"
    human_prompt = PromptTemplate.from_template(human_template)
    human_message_prompt = HumanMessagePromptTemplate(prompt=human_prompt)

    prompt = ChatPromptTemplate.from_messages([system_message_prompt, human_message_prompt])

    chain = prompt | llm
    response = await chain.ainvoke({
        "user_msg": user_msg,
        "current_document": current_document,
        "document_id": document_id,
        "uploaded_file_path": uploaded_file_path
    })

    content = response.content
    logger.info(f"orchestrator_planner: LLM raw response = {content}")

    import json
    try:
        parsed = json.loads(content)
        next_agent = parsed.get("next_agent", "default")
        agent_input = parsed.get("agent_input", {})
        requires_clarification = parsed.get("requires_clarification", False)
    except Exception as e:
        logger.error(f"orchestrator_planner: failed to parse LLM response: {e}")
        next_agent = "default"
        agent_input = {}
        requires_clarification = False

    logger.info(f"orchestrator_planner: parsed plan = {{'next_agent': '{next_agent}', 'agent_input': {agent_input}}}")

    return {
        "next_agent": next_agent,
        "agent_input": agent_input,
        "requires_clarification": requires_clarification
    }

async def route_to_agent(state: GlobalState) -> str:
    next_agent = state.get("next_agent")
    if next_agent:
        logger.info(f"route_to_agent: next_agent = {next_agent}")
        return next_agent
    logger.info("route_to_agent: no next_agent found, returning 'default'")
    return "default"

def create_orchestrator_graph():
    workflow = StateGraph(GlobalState)

    document_agent_graph = create_document_agent_graph()
    attachment_agent_graph = create_attachment_agent_graph()
    employee_agent_graph = create_employee_agent_graph()

    workflow.add_node("planner", orchestrator_planner)
    workflow.add_node("document_agent", document_agent_graph)
    workflow.add_node("attachment_agent", attachment_agent_graph)
    workflow.add_node("employee_agent", employee_agent_graph)

    workflow.set_entry_point("planner")
    workflow.add_conditional_edges(
        "planner",
        route_to_agent,
        {
            "document": "document_agent",
            "attachment": "attachment_agent",
            "employee": "employee_agent",
            "default": END
        }
    )
    workflow.add_edge("document_agent", END)
    workflow.add_edge("attachment_agent", END)
    workflow.add_edge("employee_agent", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)