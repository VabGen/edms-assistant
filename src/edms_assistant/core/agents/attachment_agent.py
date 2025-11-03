# src/edms_assistant/core/agents/attachment_agent.py

import logging
from langgraph.graph import StateGraph, END
from src.edms_assistant.core.state.global_state import GlobalState
from src.edms_assistant.core.tools.attachment_tool import summarize_attachment_tool
from src.edms_assistant.infrastructure.llm.llm import get_llm
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from src.edms_assistant.utils.file_utils import extract_text_from_bytes
from langchain_core.messages import HumanMessage, AIMessage
from uuid import UUID
import os

logger = logging.getLogger(__name__)

llm = get_llm()


async def analyze_and_summarize_node(state: GlobalState) -> dict:
    """
    Определяет, что суммаризировать:
    1. Если загружен файл → суммаризировать его
    2. Иначе, если запрос про вложение → суммаризировать вложение из EDMS
    """
    user_msg = state["user_message"].lower()
    # ✅ Берём пути из agent_input
    agent_input = state.get("agent_input", {})
    uploaded_file_path = agent_input.get("uploaded_file_path")
    doc_id_str = agent_input.get("document_id")

    logger.info(
        f"analyze_and_summarize_node: agent_input = {agent_input}, uploaded_file_path = {uploaded_file_path}, doc_id_str = {doc_id_str}")

    # === Приоритет 1: Загруженный файл ===
    if uploaded_file_path and os.path.exists(uploaded_file_path):
        file_name = os.path.basename(uploaded_file_path)
        clean_filename = file_name.split("_", 1)[-1] if "_" in file_name else file_name

        try:
            with open(uploaded_file_path, "rb") as f:
                file_bytes = f.read()

            text = extract_text_from_bytes(file_bytes, clean_filename)
            if text and len(text.strip()) >= 20:
                summary = await _generate_summary(text, clean_filename)
                final_summary = f"Содержание вашего файла '{clean_filename}':\n{summary}"
            else:
                final_summary = f"Файл '{clean_filename}' не содержит текста или не поддерживается."

        except Exception as e:
            final_summary = f"Не удалось обработать ваш файл: {e}"

        return {"messages": [AIMessage(content=final_summary)]}

    # === Приоритет 2: Вложение из EDMS ===
    attachment_keywords = ["вложение", "файл", "приложение", "содержание файла", "приложен"]
    if doc_id_str and any(kw in user_msg for kw in attachment_keywords):
        try:
            # ✅ Загружаем документ, чтобы получить список вложений
            from src.edms_assistant.core.tools.document_tool import get_document_tool
            service_token = state["service_token"]
            doc_data = await get_document_tool.ainvoke({"document_id": doc_id_str, "service_token": service_token})

            if not doc_data or "error" in doc_data:
                return {"messages": [AIMessage(content="Документ не найден.")]}

            attachments = doc_data.get("attachmentDocument", [])
            if not attachments:
                return {"messages": [AIMessage(content="В документе нет вложений.")]}

            target_att = attachments[0]
            for att in attachments:
                if att.get("name") and att["name"].lower() in user_msg:
                    target_att = att
                    break

            doc_uuid = UUID(doc_id_str)
            att_id_str = target_att.get("id")
            if not att_id_str:
                return {"messages": [AIMessage(content="ID вложения не найден.")]}

            att_uuid = UUID(att_id_str)

            async with DocumentClient(service_token=service_token) as client:
                file_bytes = await client.download_attachment(doc_uuid, att_uuid)

            if not file_bytes:
                return {"messages": [
                    AIMessage(content=f"Не удалось загрузить файл '{target_att.get('name', 'без имени')}'.")]}

            text = extract_text_from_bytes(file_bytes, target_att.get("name", "вложение"))
            if text and len(text.strip()) >= 20:
                summary = await _generate_summary(text, target_att.get("name", "вложение"))
                final_summary = f"Содержание вложения '{target_att.get('name', 'без имени')}':\n{summary}"
            else:
                final_summary = f"Вложение '{target_att.get('name', 'без имени')}' не содержит текста."

        except Exception as e:
            final_summary = f"Не удалось обработать вложение: {e}"

        return {"messages": [AIMessage(content=final_summary)]}

    return {"messages": [AIMessage(content="Нет файлов для суммаризации.")]}


async def _generate_summary(text: str, filename: str) -> str:
    prompt = (
        "Создай краткое содержание (3-5 предложений) на русском языке. "
        "Выдели ключевые положения: стороны, предмет, суммы, сроки, обязательства.\n\n"
        f"Текст:\n{text[:10000]}"
    )
    response = await llm.ainvoke([{"role": "user", "content": prompt}])
    return getattr(response, "content", str(response))


def create_attachment_agent_graph():
    workflow = StateGraph(GlobalState)
    workflow.add_node("analyze_and_summarize", analyze_and_summarize_node)

    workflow.set_entry_point("analyze_and_summarize")
    workflow.add_edge("analyze_and_summarize", END)

    return workflow.compile()
