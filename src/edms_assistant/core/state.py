# В файле src/edms_assistant/core/state.py

from typing import List, Dict, Any, Optional, Union
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from uuid import UUID


class GlobalState(BaseModel):
    # === Идентификация и авторизация ===
    user_id: UUID
    service_token: str
    document_id: Optional[str] = None

    # === Входные данные от пользователя ===
    user_message: str
    uploaded_file_path: Optional[str] = None

    # === История диалога (LangGraph) ===
    messages: List[BaseMessage] = []

    # === Состояние выполнения ===
    pending_plan: Optional[Dict[str, Any]] = None
    requires_execution: bool = False

    # === Прерывания и уточнения ===
    requires_clarification: bool = False
    clarification_context: Optional[Dict[str, Any]] = Field(default=None)
    next_node_after_clarification: Optional[str] = None

    # === Ошибки ===
    error: Optional[str] = None

    # === Новое: для расширяемости ===
    current_agent: str = "main_planner_agent"  # Текущий активный агент
    agent_context: Dict[str, Any] = Field(default_factory=dict)  # Контекст для конкретного агента
    available_agents: List[str] = Field(default_factory=list)  # Доступные агенты