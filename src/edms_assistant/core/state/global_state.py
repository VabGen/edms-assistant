# src/edms_assistant/core/state/global_state.py

from typing import Annotated, Optional, Sequence, Literal, List, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from uuid import UUID

class GlobalState(TypedDict):
    # === Идентификация и авторизация ===
    user_id: UUID
    service_token: str

    # === Входные данные от пользователя ===
    user_message: str  # Сообщение от пользователя
    document_id: Optional[str]  # ID документа из формы (если есть)
    uploaded_file_path: Optional[str]  # Путь к загруженному файлу
    uploaded_file_name: Optional[str]  # Имя загруженного файла

    # === История диалога (LangGraph) ===
    messages: Annotated[Sequence[dict], add_messages]

    # === Оркестрация ===
    next_agent: Optional[Literal["document", "attachment", "employee", "default"]]
    agent_input: Optional[Dict[str, Any]]  # Входные данные для под-агента

    # === Состояние выполнения ===
    requires_clarification: Optional[bool]  # Нужно ли уточнение (например, выбор кандидата)
    sub_agent_result: Optional[Dict[str, Any]]  # Результат под-агента (если используется)
    requires_human_input: bool  # Флаг, что ожидается ввод от человека (для UI)
    error: Optional[str]  # Ошибка (если была)

    # === Специфичные для агентов поля ===
    # attachment_agent
    attachment_id: Optional[str]
    attachment_name: Optional[str]

    # document_agent
    current_document: Optional[Dict[str, Any]]

    # employee_agent
    selected_candidate_id: Optional[str]  # ID выбранного кандидата (после interrupt)
    document_id_to_add: Optional[str]  # ID документа, в который нужно добавить (для add_responsible)
    should_add_responsible_after_clarification: Optional[bool]  # Флаг: нужно добавить после уточнения
    clarification_candidates: Optional[List[Dict[str, Any]]]  # Кандидаты, показанные для уточнения
    next_node: Optional[str]  # Указывает, какую ноду вызвать следующей (для conditional_edges)
