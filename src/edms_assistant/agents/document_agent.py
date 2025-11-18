# src/edms_assistant/agents/document_agent.py
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from src.edms_assistant.agents.base_agent import BaseAgent
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.tools.document import get_document_tool, search_documents_tool
from langgraph.types import interrupt
import json
import logging
import re

logger = logging.getLogger(__name__)


class DocumentAgent(BaseAgent):
    def __init__(self, llm=None, agent_name: str = "document_agent"):
        super().__init__(llm, agent_name)
        # Инструменты автоматически загружаются через BaseAgent и tool_registry

    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        user_message = state.user_message

        # --- Проверяем, ждём ли мы ответ на прерывание ---
        if state.waiting_for_hitl_response and user_message.isdigit():
            choice_num = int(user_message)
            last_hitl_request = state.hitl_request
            if last_hitl_request and last_hitl_request.get("type") == "document_selection":
                documents = last_hitl_request.get("documents", [])
                if 1 <= choice_num <= len(documents):
                    selected_document = documents[choice_num - 1]
                    response_text = f"Выбран документ: {selected_document.get('title', 'N/A')} (ID: {selected_document.get('id', 'N/A')})."
                    return {
                        "messages": [HumanMessage(content=user_message), AIMessage(content=response_text)],
                        "waiting_for_hitl_response": False,
                        "hitl_request": None,
                        "requires_clarification": False,
                        "hitl_pending": False,
                    }
                else:
                    return {
                        "messages": [HumanMessage(content=user_message),
                                     AIMessage(content="Неверный номер. Пожалуйста, выберите из списка.")],
                        "requires_clarification": True,
                    }
            else:
                return {
                    "messages": [HumanMessage(content=user_message),
                                 AIMessage(content="Не ожидалось числовое сообщение. Пожалуйста, уточните запрос.")],
                    "requires_clarification": True
                }

        # --- Оригинальная логика ---
        try:
            document_id = state.document_id
            if not document_id:
                uuid_match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', user_message,
                                       re.IGNORECASE)
                if uuid_match:
                    document_id_str = uuid_match.group(1)
                    try:
                        from uuid import UUID
                        document_id = UUID(document_id_str)
                    except ValueError:
                        pass

            if document_id:
                doc_result = await get_document_tool.ainvoke({
                    "document_id": str(document_id),
                    "service_token": state.service_token
                })
                doc_data = json.loads(doc_result)
                doc_info = f"Документ: {doc_data.get('title', 'N/A')}, Статус: {doc_data.get('status', 'N/A')}, Автор: {doc_data.get('author', 'N/A')}"
                return {
                    "messages": [HumanMessage(content=user_message), AIMessage(content=doc_info)],
                    "requires_clarification": False
                }
            else:
                search_keywords = user_message.lower()
                for kw in ["договор", "акт", "счёт", "накладная", "документ"]:
                    search_keywords = search_keywords.replace(kw, "")

                search_result = await search_documents_tool.ainvoke({
                    "filters": {"query": search_keywords.strip()},
                    "service_token": state.service_token
                })

                search_data = json.loads(search_result)
                if isinstance(search_data, list) and len(search_data) > 0:
                    if len(search_data) > 1:
                        docs_list = "".join([
                            f"{i + 1}. {doc.get('title', 'N/A')} (ID: {doc.get('id', 'N/A')})\n"
                            for i, doc in enumerate(search_data)
                        ])
                        return interrupt({
                            "type": "document_selection",
                            "documents": search_data,
                            "message": f"Найдено несколько документов. Пожалуйста, уточните:\n{docs_list}Отправьте номер.",
                            "initiated_by_agent": "document_agent"
                        })
                    else:
                        doc_info = f"Найден документ: {search_data[0].get('title', 'N/A')}"
                        return {
                            "messages": [HumanMessage(content=user_message), AIMessage(content=doc_info)],
                            "requires_clarification": False
                        }
                else:
                    return {
                        "messages": [HumanMessage(content=user_message), AIMessage(content="Документ не найден.")],
                        "requires_clarification": False
                    }

        except Exception as e:
            error_msg = f"Ошибка обработки документа: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "messages": [HumanMessage(content=user_message), AIMessage(content=error_msg)],
                "requires_clarification": False,
                "error": str(e)
            }
