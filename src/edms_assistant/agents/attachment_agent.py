from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.core.registry import BaseAgent
from src.edms_assistant.tools.attachment import (
    summarize_attachment_tool,
    extract_and_summarize_file_tool
)
from src.edms_assistant.tools.document import get_document_tool
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from src.edms_assistant.infrastructure.llm.llm import get_llm
import json


class AttachmentAgent(BaseAgent):
    """Агент для работы с вложениями и файлами - отвечает на сообщения пользователя"""

    def __init__(self):
        super().__init__()
        self.llm = get_llm()
        self.tools = [
            summarize_attachment_tool,
            extract_and_summarize_file_tool,
            get_document_tool,
        ]

    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        """Обработка запроса - отвечает на сообщения пользователя"""
        try:
            user_message = state.user_message

            # Если есть загруженный файл - анализируем его
            if state.uploaded_file_path:
                tool_input = {
                    "file_path": state.uploaded_file_path,
                    "service_token": state.service_token
                }
                summary_result = await extract_and_summarize_file_tool.ainvoke(tool_input)
                return {
                    "messages": [HumanMessage(content=user_message),
                                 AIMessage(content=summary_result)],
                    "requires_execution": False,
                    "requires_clarification": False
                }

            # Если есть ID документа - получаем вложения и анализируем
            elif state.document_id:
                # Сначала получаем сам документ
                doc_tool_input = {
                    "document_id": state.document_id,
                    "service_token": state.service_token
                }
                doc_result = await get_document_tool.ainvoke(doc_tool_input)

                # Парсим результат, чтобы найти вложения
                try:
                    doc_data = json.loads(doc_result)
                    if "error" in doc_data:
                        return {
                            "messages": [HumanMessage(content=user_message),
                                         AIMessage(content=f"Ошибка получения документа: {doc_data['error']}")],
                            "requires_execution": False,
                            "requires_clarification": False
                        }

                    # Пытаемся получить список вложений
                    async with DocumentClient(service_token=state.service_token) as client:
                        attachments = await client.get_document_attachments(state.document_id)

                    if attachments and len(attachments) > 0:
                        first_attachment = attachments[0]
                        attachment_id = first_attachment.get("id")
                        attachment_name = first_attachment.get("name", "attachment")

                        if attachment_id:
                            # Вызываем инструмент для суммаризации вложения
                            tool_input = {
                                "document_id": str(state.document_id),
                                "attachment_id": attachment_id,
                                "attachment_name": attachment_name,
                                "service_token": state.service_token
                            }
                            summary_result = await summarize_attachment_tool.ainvoke(tool_input)
                            return {
                                "messages": [HumanMessage(content=user_message),
                                             AIMessage(content=summary_result)],
                                "requires_execution": False,
                                "requires_clarification": False
                            }
                        else:
                            return {
                                "messages": [HumanMessage(content=user_message),
                                             AIMessage(content="Не найден ID вложения в документе")],
                                "requires_execution": False,
                                "requires_clarification": False
                            }
                    else:
                        return {
                            "messages": [HumanMessage(content=user_message),
                                         AIMessage(content="В документе нет вложений для анализа")],
                            "requires_execution": False,
                            "requires_clarification": False
                        }

                except json.JSONDecodeError:
                    return {
                        "messages": [HumanMessage(content=user_message),
                                     AIMessage(content="Ошибка парсинга данных документа")],
                        "requires_execution": False,
                        "requires_clarification": False
                    }

            # По умолчанию - отвечаем на сообщение пользователя
            return {
                "messages": [HumanMessage(content=user_message),
                             AIMessage(
                                 content="Пожалуйста, загрузите файл или укажите ID документа для анализа вложений.")],
                "requires_execution": False,
                "requires_clarification": True,
                "clarification_context": {
                    "type": "file_or_document_required",
                    "message": "Требуется файл или ID документа для анализа"
                }
            }

        except Exception as e:
            error_msg = f"Ошибка обработки: {str(e)}"
            return {
                "messages": [HumanMessage(content=user_message),
                             AIMessage(content=error_msg)],
                "requires_execution": False,
                "requires_clarification": False,
                "error": str(e)
            }