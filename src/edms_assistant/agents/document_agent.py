# src/edms_assistant/agents/document_agent.py
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.core.base_agent import BaseAgent
from src.edms_assistant.infrastructure.llm.llm import get_llm
from src.edms_assistant.tools.document import (
    get_document_tool,
    search_documents_tool,
    create_document_tool,
    update_document_tool,
)
from src.edms_assistant.tools.employee import (
    find_responsible_tool,
    get_employee_by_id_tool,
)
from src.edms_assistant.tools.attachment import (
    summarize_attachment_tool,
    extract_and_summarize_file_tool,
)


class DocumentAgent(BaseAgent):
    """Агент для работы с документами EDMS"""

    def __init__(self, llm=None, tools=None):
        super().__init__(llm or get_llm(), tools)
        self.llm = llm or get_llm()
        # Добавляем все необходимые инструменты
        self.add_tool(get_document_tool)
        self.add_tool(search_documents_tool)
        self.add_tool(create_document_tool)
        self.add_tool(update_document_tool)
        self.add_tool(find_responsible_tool)
        self.add_tool(get_employee_by_id_tool)
        self.add_tool(summarize_attachment_tool)
        self.add_tool(extract_and_summarize_file_tool)

    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        """Обработка запроса к документам"""
        try:
            user_message = state.user_message

            # Если есть загруженный файл — анализируем его
            if state.uploaded_file_path:
                tool_input = {
                    "file_path": state.uploaded_file_path,
                    "service_token": state.service_token,
                }
                summary_result = await extract_and_summarize_file_tool.ainvoke(
                    tool_input
                )
                return {
                    "messages": [
                        HumanMessage(content=user_message),
                        AIMessage(content=summary_result),
                    ],
                    "requires_execution": False,
                    "requires_clarification": False,
                }

            # Если есть ID документа — получаем его
            elif state.document_id:
                tool_input = {
                    "document_id": state.document_id,
                    "service_token": state.service_token,
                }
                doc_result = await get_document_tool.ainvoke(tool_input)
                return {
                    "messages": [
                        HumanMessage(content=user_message),
                        AIMessage(content=doc_result),
                    ],
                    "requires_execution": False,
                    "requires_clarification": False,
                }

            # По умолчанию — ищем документы по запросу
            else:
                tool_input = {
                    "query": user_message,
                    "service_token": state.service_token,
                }
                search_result = await search_documents_tool.ainvoke(tool_input)
                return {
                    "messages": [
                        HumanMessage(content=user_message),
                        AIMessage(content=search_result),
                    ],
                    "requires_execution": False,
                    "requires_clarification": False,
                }

        except Exception as e:
            error_msg = f"Ошибка обработки документа: {str(e)}"
            return {
                "messages": [
                    HumanMessage(content=state.user_message),
                    AIMessage(content=error_msg),
                ],
                "requires_execution": False,
                "requires_clarification": False,
                "error": str(e),
            }
