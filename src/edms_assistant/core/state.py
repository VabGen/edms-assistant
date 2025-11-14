# src/edms_assistant/core/state.py
from typing import List, Dict, Any, Optional, Union
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
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

    # === История сообщений (LangGraph) ===
    messages: List[BaseMessage] = Field(default_factory=list)

    # === Состояние выполнения ===
    pending_plan: Optional[Dict[str, Any]] = None
    requires_execution: bool = False

    # === Уточнения и прерывания ===
    requires_clarification: bool = False
    clarification_context: Optional[Dict[str, Any]] = Field(default=None)

    # === Human-in-the-Loop (HITL) ===
    hitl_pending: bool = False
    hitl_request: Optional[Dict[str, Any]] = Field(default=None)
    hitl_decisions: List[Dict[str, Any]] = Field(default_factory=list)

    # === Ошибки ===
    error: Optional[str] = None

    # === Агенты ===
    current_agent: str = "main_planner_agent"
    available_agents: List[str] = Field(default_factory=list)

    # === NLU и RAG ===
    nlu_intent: Optional[str] = None
    nlu_entities: Dict[str, Any] = Field(default_factory=dict)
    rag_context: Optional[Dict[str, Any]] = Field(default=None)

    # === Контекст для следующего шага (например, после уточнения) ===
    next_node: Optional[str] = Field(default="planning") # Для использования в routing_node

    # === Дополнительно для универсальности ===
    agent_context: Dict[str, Any] = Field(default_factory=dict) # Для хранения данных конкретного агента
    execution_history: List[Dict[str, Any]] = Field(default_factory=list) # Лог выполнения шагов

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            UUID: str,
            BaseMessage: lambda m: m.model_dump(mode="json", exclude_unset=True)
        }