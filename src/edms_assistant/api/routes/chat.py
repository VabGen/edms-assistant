from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
from src.edms_assistant.rag.graph import create_rag_graph
from src.edms_assistant.core.redis_client import redis_client

router = APIRouter()

CHAT_TTL = 3600

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class Message(BaseModel):
    role: str
    content: str
    timestamp: str

class ChatResponse(BaseModel):
    answer: str
    session_id: str

def _build_session_key(session_id: str) -> str:
    return f"chat:session:{session_id}"

@router.post("/ask")
async def ask_question(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())
    session_key = _build_session_key(session_id)

    chat_history = await redis_client.get(session_key) or []

    new_user_msg = Message(
        role="user",
        content=request.question,
        timestamp=datetime.now().isoformat()
    )
    chat_history.append(new_user_msg.dict())

    app = create_rag_graph()
    inputs = {
        "question": request.question,
        "chat_history": [msg for msg in chat_history[:-1]],
        "selected_file": "",
        "answer": "",
        "retry_count": 0
    }

    final_state = await app.ainvoke(inputs)
    answer = final_state["answer"]

    new_ai_msg = Message(
        role="assistant",
        content=answer,
        timestamp=datetime.now().isoformat()
    )
    chat_history.append(new_ai_msg.dict())

    await redis_client.set(session_key, chat_history, expire=CHAT_TTL)

    return ChatResponse(answer=answer, session_id=session_id)

@router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    session_key = _build_session_key(session_id)
    history = await redis_client.get(session_key)
    if history is None:
        return {"error": "Сессия не найдена"}
    return {"session_id": session_id, "messages": history}