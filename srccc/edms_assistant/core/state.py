# srccc/edms_assistant/core/state.py
from typing import Dict, Any, List, Optional, Annotated
from pydantic import BaseModel, Field
from uuid import UUID
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import add_messages  # Убедимся, что импортирован


class HitlOptions(BaseModel):
    question: str
    options: List[str]
    action: str


class GlobalState(BaseModel):
    # === Основные поля ===
    user_id: UUID
    service_token: str
    document_id: Optional[UUID] = None
    user_message: str
    uploaded_file_path: Optional[str] = None

    # === LangGraph Messages (важно для совместимости) ===
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)

    # === План и выполнение ===
    pending_plan: Optional[Dict[str, Any]] = None
    requires_execution: bool = False

    # === Уточнения (Clarification) ===
    requires_clarification: bool = False
    clarification_context: Optional[Dict[str, Any]] = None

    # === HITL (Human-in-the-Loop) ===
    hitl_pending: bool = False
    hitl_request: Optional[Dict[str, Any]] = None
    hitl_decisions: List[Dict[str, Any]] = Field(default_factory=list)

    # === Ошибки ===
    error: Optional[str] = None

    # === Текущий агент ===
    current_agent: Optional[str] = None
    available_agents: List[str] = Field(default_factory=list)

    # === LangGraph State ===
    next_node: Optional[str] = None
    waiting_for_hitl_response: bool = False

    # === NLU и RAG ===
    nlu_intent: Optional[str] = None
    nlu_confidence: Optional[float] = 0.0
    rag_context: List[Dict[str, Any]] = Field(default_factory=list)  # Результаты RAG

    class Config:
        arbitrary_types_allowed = True
