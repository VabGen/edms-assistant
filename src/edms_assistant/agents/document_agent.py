from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.core.registry import BaseAgent
from src.edms_assistant.tools.document import get_document_tool, search_documents_tool
from src.edms_assistant.tools.employee import find_responsible_tool, get_employee_by_id_tool
from src.edms_assistant.tools.attachment import summarize_attachment_tool, extract_and_summarize_file_tool
from src.edms_assistant.infrastructure.llm.llm import get_llm


class DocumentAgent(BaseAgent):
    """Агент для работы с документами EDMS"""

    def __init__(self):
        super().__init__()
        self.llm = get_llm()
        self.tools = [
            get_document_tool,
            search_documents_tool,
            find_responsible_tool,
            get_employee_by_id_tool,
            summarize_attachment_tool,
            extract_and_summarize_file_tool,
        ]

    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        """Обработка запроса к документам"""
        try:
            user_message = state.user_message

            # Если есть загруженный файл — анализируем его
            if state.uploaded_file_path:
                tool_input = {"file_path": state.uploaded_file_path, "service_token": state.service_token}
                summary_result = await extract_and_summarize_file_tool.ainvoke(tool_input)
                return {
                    "messages": [HumanMessage(content=user_message),
                                 AIMessage(content=summary_result)],
                    "requires_execution": False,
                    "requires_clarification": False
                }

            # Если есть ID документа — получаем его
            elif state.document_id:
                tool_input = {"document_id": state.document_id, "service_token": state.service_token}
                doc_result = await get_document_tool.ainvoke(tool_input)
                return {
                    "messages": [HumanMessage(content=user_message),
                                 AIMessage(content=doc_result)],
                    "requires_execution": False,
                    "requires_clarification": False
                }

            else:
                tool_input = {"query": user_message, "service_token": state.service_token}
                search_result = await search_documents_tool.ainvoke(tool_input)
                return {
                    "messages": [HumanMessage(content=user_message),
                                 AIMessage(content=search_result)],
                    "requires_execution": False,
                    "requires_clarification": False
                }

        except Exception as e:
            error_msg = f"Ошибка обработки документа: {str(e)}"
            return {
                "messages": [HumanMessage(content=user_message),
                             AIMessage(content=error_msg)],
                "requires_execution": False,
                "requires_clarification": False,
                "error": str(e)
            }