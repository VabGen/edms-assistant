# src\edms_assistant\graph\graph.py
import logging
from datetime import datetime
import os
from typing import Optional
from uuid import UUID
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from src.edms_assistant.tools.document_tools import get_document_tool
from src.edms_assistant.infrastructure.llm.llm import get_llm
from src.edms_assistant.graph.state import AgentState
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from src.edms_assistant.utils.file_utils import extract_text_from_bytes

logger = logging.getLogger(__name__)
load_dotenv()
llm = get_llm()


# ======================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ======================


def format_full_document(doc: dict) -> str:
    """Форматирует ВЕСЬ DocumentDto в читаемый текст."""
    if not isinstance(doc, dict):
        return "Некорректные данные документа."

    lines = []

    # === Основная информация ===
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

    # === Автор ===
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

    # === Даты ===
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
                dt = datetime.fromisoformat(str(doc[field]).replace("Z", "+00:00"))
                lines.append(f"{label}: {dt.strftime('%d.%m.%Y')}")
            except:
                lines.append(f"{label}: {doc[field]}")

    # === Номера ===
    if doc.get("regNumber"):
        lines.append(f"Рег. номер: {doc['regNumber']}")
    if doc.get("outRegNumber"):
        lines.append(f"Исх. номер: {doc['outRegNumber']}")
    if doc.get("contractNumber"):
        lines.append(f"Номер договора: {doc['contractNumber']}")

    # === Договорные поля ===
    if doc.get("contractSum") is not None:
        currency = "руб."
        if doc.get("currency") and isinstance(doc["currency"], dict):
            currency = doc["currency"].get("name", "руб.")
        lines.append(f"Сумма договора: {doc['contractSum']} {currency}")

    # === Вложения ===
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

    # === Корреспондент ===
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

    # === Текущий этап ===
    if doc.get("currentBpmnTaskName"):
        lines.append(f"Текущий этап: {doc['currentBpmnTaskName']}")

    # === Обязательные поля ===
    if doc.get("requiredField"):
        field_map = {
            "ATTACHMENT": "Вложение",
            "CONTRACT_CORRESPONDENT": "Корреспондент",
            "DOC_SIGNERS": "Подписант",
        }
        required = [field_map.get(f, f) for f in doc["requiredField"]]
        lines.append(f"Требуются: {', '.join(required)}")

    # === Прочие важные поля ===
    if doc.get("profileName"):
        lines.append(f"Профиль: {doc['profileName']}")
    if doc.get("daysExecution") is not None:
        lines.append(f"Срок исполнения: {doc['daysExecution']} дн.")
    if doc.get("dspFlag") is True:
        lines.append("Гриф ДСП")

    return "\n".join(lines) if lines else "Документ не содержит данных."


# ======================
# НОДЫ ГРАФА
# ======================


async def load_document_if_needed(state: AgentState) -> dict:
    """
    Загружает документ и сохраняет его в состоянии (current_document).
    """
    doc_id = state.get("document_id")
    if not doc_id:
        return {"current_document": None}

    service_token = state.get("service_token")
    if not service_token:
        logger.warning("Попытка загрузить документ без service_token")
        return {"current_document": None}

    try:
        doc_data = await get_document_tool.ainvoke(
            {"document_id": doc_id, "service_token": service_token}
        )

        if isinstance(doc_data, dict) and doc_data.get("error"):
            logger.warning(f"Ошибка при загрузке документа: {doc_data}")
            return {"current_document": None}

        logger.debug(f"Документ {doc_id} успешно загружен.")
        return {"current_document": doc_data}

    except Exception as e:
        logger.error(f"Не удалось загрузить документ {doc_id}: {e}", exc_info=True)
        return {"current_document": None}


async def analyze_and_summarize(state: AgentState) -> dict:
    """
    Определяет, что суммаризировать:
    1. Если загружен файл → суммаризировать его
    2. Иначе, если запрос про вложение → суммаризировать вложение из EDMS
    """
    user_msg = state["user_message"].lower()
    uploaded_file = state.get("uploaded_file_path")
    doc_data = state.get("current_document")

    logger.debug(f"Анализ состояния: uploaded_file_path={uploaded_file}")
    logger.debug(f"Анализ состояния: document_id={state.get('document_id')}")

    # === Приоритет 1: Загруженный файл ===
    if uploaded_file and os.path.exists(uploaded_file):
        logger.debug(f"✅ Обнаружен загруженный файл: {uploaded_file}")
        file_name = os.path.basename(uploaded_file)
        clean_filename = file_name.split("_", 1)[-1] if "_" in file_name else file_name

        try:
            with open(uploaded_file, "rb") as f:
                file_bytes = f.read()

            text = extract_text_from_bytes(file_bytes, clean_filename)
            if text and len(text.strip()) >= 20:
                summary = await _generate_summary(text, clean_filename)
                final_summary = (
                    f"Содержание вашего файла '{clean_filename}':\n{summary}"
                )
            else:
                final_summary = (
                    f"Файл '{clean_filename}' не содержит текста или не поддерживается."
                )

        except Exception as e:
            logger.error(f"Ошибка обработки загруженного файла: {e}")
            final_summary = f"Не удалось обработать ваш файл: {e}"

        return {"final_summary": final_summary}

    # === Приоритет 2: Вложение из EDMS ===
    attachment_keywords = [
        "вложение",
        "файл",
        "приложение",
        "содержание файла",
        "приложен",
    ]
    if doc_data and any(kw in user_msg for kw in attachment_keywords):
        logger.debug("✅ Обнаружен запрос про вложение EDMS")
        try:
            attachments = doc_data.get("attachmentDocument", [])
            if not attachments:
                return {"final_summary": "В документе нет вложений."}

            # Ищем по имени в запросе или берём первый
            target_att = attachments[0]
            for att in attachments:
                if att.get("name") and att["name"].lower() in user_msg:
                    target_att = att
                    break

            async with DocumentClient(service_token=state["service_token"]) as client:
                file_bytes = await client.download_attachment(
                    UUID(state["document_id"]), UUID(target_att["id"])
                )

            if not file_bytes:
                return {
                    "final_summary": f"Не удалось загрузить файл '{target_att.get('name', 'без имени')}'."
                }

            text = extract_text_from_bytes(
                file_bytes, target_att.get("name", "вложение")
            )
            if text and len(text.strip()) >= 20:
                summary = await _generate_summary(
                    text, target_att.get("name", "вложение")
                )
                final_summary = f"Содержание вложения '{target_att.get('name', 'без имени')}':\n{summary}"
            else:
                final_summary = f"Вложение '{target_att.get('name', 'без имени')}' не содержит текста."

        except Exception as e:
            logger.error(f"Ошибка суммаризации вложения: {e}")
            final_summary = f"Не удалось обработать вложение: {e}"

        return {"final_summary": final_summary}

    # === Нет файлов для суммаризации ===
    return {"final_summary": None}


async def _generate_summary(text: str, filename: str) -> str:
    """Генерирует краткое содержание через LLM."""
    prompt = (
        "Создай краткое содержание (3-5 предложений) на русском языке. "
        "Выдели ключевые положения: стороны, предмет, суммы, сроки, обязательства.\n\n"
        f"Текст:\n{text[:10000]}"
    )
    response = await llm.ainvoke([{"role": "user", "content": prompt}])
    return getattr(response, "content", str(response))


async def generate_final_response(state: AgentState) -> dict:
    """Формирует итоговый ответ с учётом суммаризации."""
    user_msg = state["user_message"]
    uploaded_file = state.get("uploaded_file_path")
    final_summary = state.get("final_summary")

    # Если есть загруженный файл — отвечаем ТОЛЬКО по нему
    if uploaded_file and final_summary:
        prompt = (
            "<instruction>\n"
            "Ты — эксперт по документам. Пользователь загрузил файл и спрашивает о нём. "
            "Отвечай ТОЛЬКО на основе содержания загруженного файла. "
            "Не упоминай документы из EDMS, вложения или другие данные. "
            "Будь точным и кратким.\n"
            "</instruction>\n\n"
            "<context>\n"
            f"{final_summary}\n"
            "</context>\n\n"
            "<question>\n"
            f"{user_msg}\n"
            "</question>\n\n"
            "<answer>\n"
        )
    else:
        # Обычная обработка (документ из EDMS)
        doc_data = state.get("current_document")
        context_parts = []
        if doc_data:
            context_parts.append(format_full_document(doc_data))
        if final_summary:
            context_parts.append(final_summary)
        context = (
            "\n\n".join(context_parts) if context_parts else "Нет данных о документе."
        )

        prompt = (
            "<instruction>\n"
            "Ты — эксперт по документам в EDMS. Отвечай ТОЛЬКО на основе данных ниже. "
            "Будь точным, кратким и вежливым. Не выдумывай. "
            "Если информации нет — скажи: «В документе нет информации об этом». "
            "Не упоминай технические детали. Говори как человек.\n"
            "</instruction>\n\n"
            "<context>\n"
            f"{context}\n"
            "</context>\n\n"
            "<question>\n"
            f"{user_msg}\n"
            "</question>\n\n"
            "<answer>\n"
        )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return {
            "messages": [
                (
                    response
                    if hasattr(response, "content")
                    else AIMessage(content=str(response))
                )
            ]
        }
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        return {"messages": [AIMessage(content="Ошибка при генерации ответа.")]}


# ======================
# СБОРКА ГРАФА
# ======================
def create_agent_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("load_document", load_document_if_needed)
    workflow.add_node("analyze_and_summarize", analyze_and_summarize)
    workflow.add_node("generate_final_response", generate_final_response)

    workflow.set_entry_point("load_document")
    workflow.add_edge("load_document", "analyze_and_summarize")
    workflow.add_edge("analyze_and_summarize", "generate_final_response")
    workflow.add_edge("generate_final_response", END)

    return workflow.compile()


# # src/edms_assistant/graph/graph.py
# import json
# import re
# import logging
# from langchain_core.messages import HumanMessage, AIMessage
# from src.edms_assistant.tools.attachment_tools import summarize_attachment_tool
# from langgraph.graph import StateGraph, END
# from src.edms_assistant.tools.document_tools import get_document_tool
# from src.edms_assistant.infrastructure.llm.llm import get_llm
# from .state import AgentState
#
# logger = logging.getLogger(__name__)
# llm = get_llm()
#
#
# async def load_document_if_needed(state: AgentState) -> dict:
#     """
#     Загружает документ и сохраняет его в состоянии (current_document).
#     НЕ добавляет ничего в messages.
#     """
#     doc_id = state.get("document_id")
#     if not doc_id:
#         return {"current_document": None}
#
#     service_token = state.get("service_token")
#     if not service_token:
#         logger.warning("Попытка загрузить документ без service_token")
#         return {"current_document": None}
#
#     try:
#         raw_result = await get_document_tool.ainvoke({
#             "document_id": doc_id,
#             "service_token": service_token
#         })
#
#         # Парсим JSON-строку в объект
#         if isinstance(raw_result, str):
#             doc_data = json.loads(raw_result)
#         else:
#             doc_data = raw_result
#
#         # Проверяем ошибки (если инструмент вернул JSON с error)
#         if isinstance(doc_data, dict) and doc_data.get("error"):
#             logger.warning(f"Ошибка при загрузке документа: {doc_data}")
#             return {"current_document": None}
#
#         logger.debug(f"Документ {doc_id} успешно загружен.")
#         return {"current_document": doc_data}
#
#     except Exception as e:
#         logger.error(f"Не удалось загрузить документ {doc_id}: {e}", exc_info=True)
#         return {"current_document": None}
#
#
# async def process_user_request(state: AgentState) -> dict:
#     """
#     Генерирует ответ, используя ВСЕ поля из DocumentDto.
#     """
#     user_msg = state["user_message"]
#     doc_data = state.get("current_document")
#
#     def format_full_document(doc: dict) -> str:
#         """Форматирует ВЕСЬ DocumentDto в читаемый текст."""
#         if not isinstance(doc, dict):
#             return "Некорректные данные документа."
#
#         lines = []
#
#         # === Основная информация ===
#         if doc.get("documentType") and isinstance(doc["documentType"], dict):
#             type_name = doc["documentType"].get("typeName", "не указан")
#             category = doc.get("docCategoryConstant", "")
#             category_map = {
#                 "CONTRACT": "Договор", "INTERN": "Внутренний", "INCOMING": "Входящий",
#                 "OUTGOING": "Исходящий", "APPEAL": "Обращение"
#             }
#             cat_str = category_map.get(category, category) if category else ""
#             lines.append(f"Тип документа: {type_name}" + (f" ({cat_str})" if cat_str else ""))
#
#         if doc.get("status"):
#             status_map = {
#                 "DRAFT": "Черновик", "NEW": "Новый", "APPROVED": "Согласован",
#                 "SIGNED": "Подписан", "REGISTERED": "Зарегистрирован", "EXECUTED": "Исполнен"
#             }
#             status_str = status_map.get(doc["status"], doc["status"])
#             lines.append(f"Статус: {status_str}")
#
#         if doc.get("shortSummary"):
#             lines.append(f"Краткое содержание: {doc['shortSummary']}")
#         elif doc.get("summary"):
#             lines.append(f"Содержание: {doc['summary']}")
#
#         # === Автор ===
#         if doc.get("author") and isinstance(doc["author"], dict):
#             auth = doc["author"]
#             name = f"{auth.get('lastName', '')} {auth.get('firstName', '')} {auth.get('middleName', '')}".strip()
#             if name:
#                 parts = [f"Автор: {name}"]
#                 if auth.get("authorPost"):
#                     parts.append(f"должность: {auth['authorPost']}")
#                 if auth.get("authorDepartmentName"):
#                     parts.append(f"подразделение: {auth['authorDepartmentName']}")
#                 lines.append("; ".join(parts))
#
#         # === Даты ===
#         date_fields = [
#             ("createDate", "Дата создания"),
#             ("regDate", "Дата регистрации"),
#             ("outRegDate", "Дата исходящего"),
#             ("contractSigningDate", "Дата подписания"),
#             ("contractDurationStart", "Начало действия договора"),
#             ("contractDurationEnd", "Окончание действия договора")
#         ]
#         for field, label in date_fields:
#             if doc.get(field):
#                 try:
#                     from datetime import datetime
#                     dt = datetime.fromisoformat(str(doc[field]).replace("Z", "+00:00"))
#                     lines.append(f"{label}: {dt.strftime('%d.%m.%Y')}")
#                 except:
#                     lines.append(f"{label}: {doc[field]}")
#
#         # === Номера ===
#         if doc.get("regNumber"):
#             lines.append(f"Рег. номер: {doc['regNumber']}")
#         if doc.get("outRegNumber"):
#             lines.append(f"Исх. номер: {doc['outRegNumber']}")
#         if doc.get("contractNumber"):
#             lines.append(f"Номер договора: {doc['contractNumber']}")
#
#         # === Договорные поля ===
#         if doc.get("contractSum") is not None:
#             currency = "руб."
#             if doc.get("currency") and isinstance(doc["currency"], dict):
#                 currency = doc["currency"].get("name", "руб.")
#             lines.append(f"Сумма договора: {doc['contractSum']} {currency}")
#
#         # === Вложения ===
#         if doc.get("attachmentDocument") and isinstance(doc["attachmentDocument"], list):
#             names = [att.get("name") for att in doc["attachmentDocument"] if isinstance(att, dict) and att.get("name")]
#             if names:
#                 lines.append(f"Вложения: {', '.join(names[:5])}" + (" и др." if len(names) > 5 else ""))
#
#         # === Корреспондент ===
#         if doc.get("correspondent") and isinstance(doc["correspondent"], dict):
#             corr = doc["correspondent"]
#             name = corr.get("name") or corr.get("correspondentName", "")
#             unp = corr.get("unp", "")
#             if name or unp:
#                 parts = []
#                 if name:
#                     parts.append(name)
#                 if unp:
#                     parts.append(f"УНП: {unp}")
#                 lines.append(f"Корреспондент: {'; '.join(parts)}")
#
#         # === Текущий этап ===
#         if doc.get("currentBpmnTaskName"):
#             lines.append(f"Текущий этап: {doc['currentBpmnTaskName']}")
#
#         # === Обязательные поля ===
#         if doc.get("requiredField"):
#             field_map = {
#                 "ATTACHMENT": "Вложение",
#                 "CONTRACT_CORRESPONDENT": "Корреспондент",
#                 "DOC_SIGNERS": "Подписант"
#             }
#             required = [field_map.get(f, f) for f in doc["requiredField"]]
#             lines.append(f"Требуются: {', '.join(required)}")
#
#         # === Прочие важные поля ===
#         if doc.get("profileName"):
#             lines.append(f"Профиль: {doc['profileName']}")
#         if doc.get("daysExecution") is not None:
#             lines.append(f"Срок исполнения: {doc['daysExecution']} дн.")
#         if doc.get("dspFlag") is True:
#             lines.append("Гриф ДСП")
#
#         return "\n".join(lines) if lines else "Документ не содержит данных."
#
#     if doc_data:
#         formatted_doc = format_full_document(doc_data)
#         prompt = (
#             "<instruction>\n"
#             "Ты — эксперт по документам в EDMS. Отвечай ТОЛЬКО на основе данных ниже. "
#             "Будь точным, кратким и вежливым. Не выдумывай. "
#             "Если информации нет — скажи: «В документе нет информации об этом». "
#             "Не упоминай технические детали. Говори как человек.\n"
#             "</instruction>\n\n"
#             "<context>\n"
#             f"{formatted_doc}\n"
#             "</context>\n\n"
#             "<question>\n"
#             f"{user_msg}\n"
#             "</question>\n\n"
#             "<answer>\n"
#         )
#     else:
#         prompt = (
#             "<instruction>\n"
#             "Ты — помощник по документам в EDMS. Ответь вежливо. "
#             "Если вопрос не о документах — скажи, что помогаешь только с документами.\n"
#             "</instruction>\n\n"
#             "<question>\n"
#             f"{user_msg}\n"
#             "</question>\n\n"
#             "<answer>\n"
#         )
#
#     try:
#         response = await llm.ainvoke([HumanMessage(content=prompt)])
#         return {"messages": [response if hasattr(response, 'content') else AIMessage(content=str(response))]}
#     except Exception as e:
#         logger.error(f"Ошибка генерации ответа: {e}", exc_info=True)
#         return {"messages": [AIMessage(content="Не удалось обработать запрос. Попробуйте позже.")]}
#
# async def analyze_user_intent(state: AgentState) -> dict:
#     """
#     Анализирует запрос: нужно ли суммаризировать вложение?
#     """
#     user_msg = state["user_message"].lower()
#     doc_data = state.get("current_document")
#
#     # Ключевые фразы для вложений
#     attachment_keywords = [
#         "вложение", "файл", "документ", "приложение", "attachment", "содержание файла",
#         ".doc", ".pdf", ".docx"
#     ]
#
#     needs_summary = any(kw in user_msg for kw in attachment_keywords)
#
#     if needs_summary and doc_data and doc_data.get("attachmentDocument"):
#         # Найдём attachment_id по имени из запроса или возьмём первый
#         attachments = doc_data["attachmentDocument"]
#         target_att = None
#
#         # Попробуем найти по имени
#         for att in attachments:
#             if att.get("name") and att["name"].lower() in user_msg:
#                 target_att = att
#                 break
#
#         # Или возьмём первый
#         if not target_att and attachments:
#             target_att = attachments[0]
#
#         if target_att:
#             return {
#                 "needs_attachment_summary": True,
#                 "attachment_id": str(target_att["id"]),
#                 "attachment_name": target_att.get("name", "файл")
#             }
#
#     return {"needs_attachment_summary": False}
#
#
# async def summarize_attachment_if_needed(state: AgentState) -> dict:
#     """Вызывает инструмент суммаризации."""
#     if not state.get("needs_attachment_summary"):
#         return {"attachment_summary": None}
#
#     try:
#         result = await summarize_attachment_tool.ainvoke({
#             "document_id": state["document_id"],
#             "attachment_id": state["attachment_id"],
#             "service_token": state["service_token"]
#         })
#         return {"attachment_summary": result}
#     except Exception as e:
#         logger.error(f"Ошибка суммаризации: {e}")
#         return {"attachment_summary": f"Ошибка при обработке файла: {e}"}
#
#
# async def generate_final_response(state: AgentState) -> dict:
#     """Формирует итоговый ответ с учётом суммаризации."""
#     user_msg = state["user_message"]
#     doc_data = state.get("current_document")
#     attachment_summary = state.get("attachment_summary")
#
#     # Форматируем основной документ (как раньше)
#     def format_doc(doc):
#         # ... (используй твою существующую логику из clean_and_format_value или format_full_document) ...
#         # Для краткости — упрощённо:
#         return f"Документ: {doc.get('shortSummary', 'без описания')}"
#
#     context_parts = []
#     if doc_data:
#         context_parts.append(format_doc(doc_data))
#     if attachment_summary:
#         context_parts.append(f"\nДополнительно: {attachment_summary}")
#
#     context = "\n".join(context_parts) if context_parts else ""
#
#     prompt = (
#         "<instruction>Ты — эксперт по документам. Отвечай только по данным ниже.</instruction>\n\n"
#         f"<context>{context}</context>\n\n"
#         f"<question>{user_msg}</question>\n\n"
#         "<answer>"
#     )
#
#     try:
#         response = await llm.ainvoke([HumanMessage(content=prompt)])
#         return {"messages": [response if hasattr(response, 'content') else AIMessage(content=str(response))]}
#     except Exception as e:
#         logger.error(f"Ошибка генерации: {e}")
#         return {"messages": [AIMessage(content="Ошибка при генерации ответа.")]}
#
#
# def create_agent_graph():
#     workflow = StateGraph(AgentState)
#     workflow.add_node("load_document", load_document_if_needed)
#     workflow.add_node("analyze_intent", analyze_user_intent)
#     workflow.add_node("summarize_attachment", summarize_attachment_if_needed)
#     workflow.add_node("generate_response", generate_final_response)
#
#     workflow.set_entry_point("load_document")
#     workflow.add_edge("load_document", "analyze_intent")
#     workflow.add_edge("analyze_intent", "summarize_attachment")
#     workflow.add_edge("summarize_attachment", "generate_response")
#     workflow.add_edge("generate_response", END)
#
#     return workflow.compile()
#
