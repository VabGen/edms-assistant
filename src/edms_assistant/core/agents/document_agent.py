# src/edms_assistant/core/agents/document_agent.py
import datetime
import logging
from langgraph.graph import StateGraph, END
from src.edms_assistant.core.state.global_state import GlobalState
from src.edms_assistant.core.tools.document_tool import get_document_tool
from src.edms_assistant.infrastructure.llm.llm import get_llm
from langchain_core.messages import HumanMessage, AIMessage

llm = get_llm()

logger = logging.getLogger(__name__)

async def load_document_node(state: GlobalState) -> dict:
    logger.info("load_document_node: started")
    agent_input = state.get("agent_input", {})
    doc_id = agent_input.get("document_id")

    logger.info(f"load_document_node: agent_input = {agent_input}, doc_id = {doc_id}")

    if not doc_id:
        logger.warning("load_document_node: document_id not provided in agent_input")
        return {"current_document": None, "error": "document_id not provided in agent_input"}

    service_token = state["service_token"]
    logger.info(f"load_document_node: calling get_document_tool with doc_id={doc_id}")

    try:
        doc_data = await get_document_tool.ainvoke({"document_id": doc_id, "service_token": service_token})
        logger.info(f"load_document_node: got doc_data = {type(doc_data)}, keys = {list(doc_data.keys()) if isinstance(doc_data, dict) else 'not dict'}")
        return {"current_document": doc_data}
    except Exception as e:
        logger.error(f"load_document_node: error calling tool: {e}", exc_info=True)
        return {"current_document": None, "error": str(e)}

async def format_and_respond_node(state: GlobalState) -> dict:
    logger.info("format_and_respond_node: started")
    doc_data = state.get("current_document")
    user_msg = state.get("user_message", "").lower()
    logger.info(f"format_and_respond_node: doc_data = {doc_data}, user_msg = {user_msg}")

    if not doc_data or "error" in doc_data:
        logger.warning("format_and_respond_node: doc_data is None or has error")
        return {"messages": [AIMessage(content="Документ не найден.")]}

    # ✅ Проверяем, есть ли вопрос в user_msg, и отвечаем на него
    if "автор" in user_msg:
        author = doc_data.get("author", {})
        author_name = f"{author.get('lastName', '')} {author.get('firstName', '')} {author.get('middleName', '')}".strip()
        if author_name:
            response = f"Автор документа: {author_name}"
        else:
            response = "Автор документа не указан."

    elif "статус" in user_msg:
        status = doc_data.get("status")
        status_map = {
            "DRAFT": "Черновик",
            "NEW": "Новый",
            "APPROVED": "Согласован",
            "SIGNED": "Подписан",
            "REGISTERED": "Зарегистрирован",
            "EXECUTED": "Исполнен",
        }
        status_str = status_map.get(status, status)
        response = f"Статус документа: {status_str}"

    elif "дата создания" in user_msg or "создан" in user_msg:
        create_date = doc_data.get("createDate")
        if create_date:
            try:
                dt = datetime.datetime.fromisoformat(str(create_date).replace("Z", "+00:00"))
                response = f"Дата создания документа: {dt.strftime('%d.%m.%Y')}"
            except:
                response = f"Дата создания документа: {create_date}"
        else:
            response = "Дата создания документа не указана."

    elif "номер" in user_msg and ("рег" in user_msg or "регистрации" in user_msg):
        reg_number = doc_data.get("regNumber")
        response = f"Рег. номер: {reg_number}" if reg_number else "Рег. номер не указан."

    elif "сумма" in user_msg or "договор" in user_msg and "сумм" in user_msg:
        contract_sum = doc_data.get("contractSum")
        currency_obj = doc_data.get("currency", {})
        currency_name = currency_obj.get("name", "руб.")
        if contract_sum is not None:
            response = f"Сумма договора: {contract_sum} {currency_name}"
        else:
            response = "Сумма договора не указана."

    else:
        # Если вопрос не распознан, возвращаем всё содержимое
        response = format_full_document(doc_data)

    logger.info(f"format_and_respond_node: response = {response[:100]}...")
    return {"messages": [AIMessage(content=response)]}

def format_full_document(doc: dict) -> str:
    """Форматирует ВЕСЬ DocumentDto в читаемый текст."""
    if not isinstance(doc, dict):
        return "Некорректные данные документа."

    lines = []

    if doc.get("documentType") and isinstance(doc["documentType"], dict):
        type_name = doc["documentType"].get("typeName", "не указан")
        category = doc.get("docCategoryConstant", "")
        category_map = {
            "CONTRACT": "Договор",
            "INTERN": "Внутренний",
            "INCOMING": "Входящий",
            "OUTGOING": "Исходящий",
            "APPEAL": "Обращение",
        }
        cat_str = category_map.get(category, category) if category else ""
        lines.append(
            f"Тип документа: {type_name}" + (f" ({cat_str})" if cat_str else "")
        )

    if doc.get("status"):
        status_map = {
            "DRAFT": "Черновик",
            "NEW": "Новый",
            "APPROVED": "Согласован",
            "SIGNED": "Подписан",
            "REGISTERED": "Зарегистрирован",
            "EXECUTED": "Исполнен",
        }
        status_str = status_map.get(doc["status"], doc["status"])
        lines.append(f"Статус: {status_str}")

    if doc.get("shortSummary"):
        lines.append(f"Краткое содержание: {doc['shortSummary']}")
    elif doc.get("summary"):
        lines.append(f"Содержание: {doc['summary']}")

    if doc.get("author") and isinstance(doc["author"], dict):
        auth = doc["author"]
        name = f"{auth.get('lastName', '')} {auth.get('firstName', '')} {auth.get('middleName', '')}".strip()
        if name:
            parts = [f"Автор: {name}"]
            if auth.get("authorPost"):
                parts.append(f"должность: {auth['authorPost']}")
            if auth.get("authorDepartmentName"):
                parts.append(f"подразделение: {auth['authorDepartmentName']}")
            lines.append("; ".join(parts))

    date_fields = [
        ("createDate", "Дата создания"),
        ("regDate", "Дата регистрации"),
        ("outRegDate", "Дата исходящего"),
        ("contractSigningDate", "Дата подписания"),
        ("contractDurationStart", "Начало действия договора"),
        ("contractDurationEnd", "Окончание действия договора"),
    ]
    for field, label in date_fields:
        if doc.get(field):
            try:
                dt = datetime.datetime.fromisoformat(str(doc[field]).replace("Z", "+00:00"))
                lines.append(f"{label}: {dt.strftime('%d.%m.%Y')}")
            except:
                lines.append(f"{label}: {doc[field]}")

    if doc.get("regNumber"):
        lines.append(f"Рег. номер: {doc['regNumber']}")
    if doc.get("outRegNumber"):
        lines.append(f"Исх. номер: {doc['outRegNumber']}")
    if doc.get("contractNumber"):
        lines.append(f"Номер договора: {doc['contractNumber']}")

    if doc.get("contractSum") is not None:
        currency = "руб."
        if doc.get("currency") and isinstance(doc["currency"], dict):
            currency = doc["currency"].get("name", "руб.")
        lines.append(f"Сумма договора: {doc['contractSum']} {currency}")

    if doc.get("attachmentDocument") and isinstance(doc["attachmentDocument"], list):
        names = [
            att.get("name")
            for att in doc["attachmentDocument"]
            if isinstance(att, dict) and att.get("name")
        ]
        if names:
            lines.append(
                f"Вложения: {', '.join(names[:5])}"
                + (" и др." if len(names) > 5 else "")
            )

    if doc.get("correspondent") and isinstance(doc["correspondent"], dict):
        corr = doc["correspondent"]
        name = corr.get("name") or corr.get("correspondentName", "")
        unp = corr.get("unp", "")
        if name or unp:
            parts = []
            if name:
                parts.append(name)
            if unp:
                parts.append(f"УНП: {unp}")
            lines.append(f"Корреспондент: {'; '.join(parts)}")

    if doc.get("currentBpmnTaskName"):
        lines.append(f"Текущий этап: {doc['currentBpmnTaskName']}")

    if doc.get("requiredField"):
        field_map = {
            "ATTACHMENT": "Вложение",
            "CONTRACT_CORRESPONDENT": "Корреспондент",
            "DOC_SIGNERS": "Подписант",
        }
        required = [field_map.get(f, f) for f in doc["requiredField"]]
        lines.append(f"Требуются: {', '.join(required)}")

    if doc.get("profileName"):
        lines.append(f"Профиль: {doc['profileName']}")
    if doc.get("daysExecution") is not None:
        lines.append(f"Срок исполнения: {doc['daysExecution']} дн.")
    if doc.get("dspFlag") is True:
        lines.append("Гриф ДСП")

    return "\n".join(lines) if lines else "Документ не содержит данных."

def create_document_agent_graph():
    workflow = StateGraph(GlobalState)
    workflow.add_node("load_document", load_document_node)
    workflow.add_node("format_and_respond", format_and_respond_node)

    workflow.set_entry_point("load_document")
    workflow.add_edge("load_document", "format_and_respond")
    workflow.add_edge("format_and_respond", END)

    return workflow.compile()