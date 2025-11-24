# srccc/edms_assistant/tools/__init__.py
# Регистрация инструментов в реестре при импорте модуля tools
from srccc.edms_assistant.core.tool_registry import tool_registry

# Импорты инструментов
from .employee import find_responsible_tool, get_employee_by_id_tool
from .document import get_document_tool, search_documents_tool
from .attachment import summarize_attachment_tool, extract_and_summarize_file_tool

# Регистрация
tool_registry.register_for_agent("employee_agent", [find_responsible_tool, get_employee_by_id_tool])
tool_registry.register_for_agent("document_agent", [get_document_tool, search_documents_tool])
tool_registry.register_for_agent("attachment_agent", [summarize_attachment_tool, extract_and_summarize_file_tool])