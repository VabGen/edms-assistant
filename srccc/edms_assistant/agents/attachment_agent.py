# srccc/edms_assistant/agents/attachment_agent.py
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from srccc.edms_assistant.agents.base_agent import BaseAgent
from srccc.edms_assistant.core.state import GlobalState
from srccc.edms_assistant.tools.document import get_document_tool
from srccc.edms_assistant.tools.attachment import summarize_attachment_tool, extract_and_summarize_file_tool
from langgraph.types import interrupt
import json
import logging
import os

logger = logging.getLogger(__name__)


class AttachmentAgent(BaseAgent):
    def __init__(self, llm=None, agent_name: str = "attachment_agent"):
        super().__init__(llm, agent_name)
        # Инструменты автоматически загружаются через BaseAgent и tool_registry

    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        user_message = state.user_message

        if state.waiting_for_hitl_response:
            logger.info("AttachmentAgent: Skipping processing, waiting for HITL response.")
            return {"messages": [HumanMessage(content=user_message)], "requires_execution": False}

        try:
            if state.uploaded_file_path:
                # Вызываем инструмент для анализа загруженного файла
                result = await extract_and_summarize_file_tool.ainvoke({
                    "file_path": state.uploaded_file_path,
                    "service_token": state.service_token
                })
                return {
                    "messages": [HumanMessage(content=user_message), AIMessage(content=result)],
                    "requires_execution": False,
                    "requires_clarification": False
                }

            elif state.document_id:
                doc_result = await get_document_tool.ainvoke({
                    "document_id": str(state.document_id),
                    "service_token": state.service_token
                })
                doc_data = json.loads(doc_result)
                attachments = doc_data.get("attachments", [])

                if attachments and len(attachments) > 0:
                    if len(attachments) > 1:
                        attachments_list = "".join([
                            f"{i + 1}. {att.get('name', 'N/A')} (ID: {att.get('id', 'N/A')})\n"
                            for i, att in enumerate(attachments)
                        ])
                        return interrupt({
                            "type": "attachment_selection",
                            "attachments": attachments,
                            "message": f"В документе несколько вложений. Пожалуйста, уточните:\n{attachments_list}Отправьте номер.",
                            "initiated_by_agent": "attachment_agent"
                        })
                    else:
                        first_attachment = attachments[0]
                        attachment_id = first_attachment.get("id")
                        attachment_name = first_attachment.get("name", "attachment")
                        if attachment_id:
                            summary_result = await summarize_attachment_tool.ainvoke({
                                "document_id": str(state.document_id),
                                "attachment_id": attachment_id,
                                "attachment_name": attachment_name,
                                "service_token": state.service_token,
                            })
                            return {
                                "messages": [HumanMessage(content=user_message), AIMessage(content=summary_result)],
                                "requires_execution": False,
                                "requires_clarification": False
                            }
                        else:
                            return {
                                "messages": [HumanMessage(content=user_message),
                                             AIMessage(content="Не удалось получить ID вложения для анализа.")],
                                "requires_execution": False,
                                "requires_clarification": False
                            }
                else:
                    return {
                        "messages": [HumanMessage(content=user_message),
                                     AIMessage(content="В документе нет вложений для анализа.")],
                        "requires_execution": False,
                        "requires_clarification": False
                    }
            else:
                return {
                    "messages": [HumanMessage(content=user_message), AIMessage(
                        content="Пожалуйста, загрузите файл или укажите ID документа для анализа вложений.")],
                    "requires_execution": False,
                    "requires_clarification": True,
                }

        except Exception as e:
            error_msg = f"Ошибка обработки вложения: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "messages": [HumanMessage(content=user_message), AIMessage(content=error_msg)],
                "requires_execution": False,
                "requires_clarification": False,
                "error": str(e),
            }
