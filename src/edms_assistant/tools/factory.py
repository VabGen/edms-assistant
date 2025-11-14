# src/edms_assistant/tools/factory.py
from typing import List
from langchain_core.tools import BaseTool
from src.edms_assistant.tools.employee import (
    get_employee_by_id_tool,
    find_responsible_tool,
    add_responsible_to_document_tool
)
from src.edms_assistant.tools.document import (
    get_document_tool,
    search_documents_tool,
    create_document_tool,
    update_document_tool
)
from src.edms_assistant.tools.attachment import (
    summarize_attachment_tool,
    extract_and_summarize_file_tool
)


def get_tools_for_agent(agent_name: str) -> List[BaseTool]:
    """
    Фабрика инструментов: возвращает список инструментов для конкретного агента.
    Это позволяет легко добавлять/удалять инструменты без изменения кода агента.
    """
    tool_map = {
        "employee_agent": [
            get_employee_by_id_tool,
            find_responsible_tool,
            add_responsible_to_document_tool,
        ],
        "document_agent": [
            get_document_tool,
            search_documents_tool,
            create_document_tool,
            update_document_tool,
            find_responsible_tool, # Может потребоваться для документов
            get_employee_by_id_tool # Для получения ответственных
        ],
        "attachment_agent": [
            summarize_attachment_tool,
            extract_and_summarize_file_tool,
            get_document_tool # Для получения вложений документа
        ],
        "main_planner_agent": [
            get_document_tool,
            search_documents_tool,
            get_employee_by_id_tool,
            find_responsible_tool,
            summarize_attachment_tool,
            extract_and_summarize_file_tool,
        ]
    }

    return tool_map.get(agent_name, [])


def register_all_tools():
    """
    Опционально: функция для предварительной инициализации/валидации всех инструментов.
    """
    for agent_name, tools in get_tools_for_agent.items():
        for tool in tools:
            # Пример валидации
            if not callable(getattr(tool, 'ainvoke', None)):
                raise ValueError(f"Tool {tool} does not have a callable ainvoke method")