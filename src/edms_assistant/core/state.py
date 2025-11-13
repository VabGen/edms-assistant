# src/edms_assistant/core/state.py
from typing import List, Dict, Any, Optional, Union, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from pydantic import BaseModel, Field
from uuid import UUID


class GlobalState(BaseModel):
    # === Идентификация и авторизация ===
    user_id: UUID = Field(description="ID пользователя в системе")
    service_token: str = Field(description="JWT токен для EDMS")
    document_id: Optional[str] = Field(
        default=None, description="ID документа для взаимодействия"
    )

    # === Входные данные от пользователя ===
    user_message: str = Field(description="Сообщение пользователя")
    uploaded_file_path: Optional[str] = Field(
        default=None, description="Путь к загруженному файлу"
    )

    # === История диалога (LangGraph) ===
    messages: List[BaseMessage] = Field(
        default_factory=list, description="История сообщений"
    )

    # === Состояние выполнения ===
    pending_plan: Optional[Dict[str, Any]] = Field(
        default=None, description="План действий в ожидании"
    )
    requires_execution: bool = Field(
        default=False, description="Требуется выполнение действий"
    )
    requires_clarification: bool = Field(
        default=False, description="Требуется уточнение"
    )

    # === Прерывания и уточнения ===
    clarification_context: Optional[Dict[str, Any]] = Field(
        default=None, description="Контекст уточнения"
    )
    next_node_after_clarification: Optional[str] = Field(
        default=None, description="Следующий узел после уточнения"
    )

    # === Ошибки ===
    error: Optional[str] = Field(default=None, description="Сообщение об ошибке")

    # === Новое: для расширяемости ===
    current_agent: str = Field(
        default="main_planner_agent", description="Текущий активный агент"
    )
    agent_context: Dict[str, Any] = Field(
        default_factory=dict, description="Контекст для конкретного агента"
    )
    available_agents: List[str] = Field(
        default_factory=list, description="Доступные агенты"
    )
    execution_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="История выполнения"
    )
    tool_results: List[ToolMessage] = Field(
        default_factory=list, description="Результаты инструментов"
    )

    # === Human-in-the-Loop ===
    hitl_pending: bool = Field(
        default=False, description="Ожидание решения пользователя"
    )
    hitl_request: Optional[Dict[str, Any]] = Field(
        default=None, description="Запрос HITL"
    )
    hitl_decisions: List[Dict[str, Any]] = Field(
        default_factory=list, description="Решения HITL"
    )

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {UUID: str, BaseMessage: lambda m: m.model_dump()}
