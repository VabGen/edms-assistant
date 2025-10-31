# src/edms_assistant/graph/state.py
from typing import Annotated, Optional, Sequence, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from src.edms_assistant.infrastructure.resources_openapi import DocumentDto
import uuid


class AgentState(TypedDict):
    # Идентификация сессии и авторизация
    user_id: uuid.UUID
    service_token: str  # передаётся в инструменты, но не сохраняется в логах/чекпоинтах

    # Входные данные от фронта
    document_id: Optional[str]  #
    user_message: str

    # История диалога (для памяти агента)
    messages: Annotated[Sequence[dict], add_messages]

    # Документ (если загружен)
    current_document: Optional[Any]

    attachment_summary: Optional[str]

    # Файл (если загружен)
    uploaded_file_path: Optional[str]

    needs_attachment_summary: bool
    attachment_id: Optional[str]
    attachment_name: Optional[str]

    # Результат суммаризации
    final_summary: Optional[str]

    # Внутренние флаги
    requires_human_input: bool
    error: Optional[str]
