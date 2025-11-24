import uuid

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel
from datetime import datetime

from backend.models import ChatRequest, ChatSession, Message
from backend.rag_graph_advanced import create_rag_graph, cache_manager, VECTOR_STORES

router = APIRouter()


# Передаём `chat_sessions` извне
def set_chat_sessions(sessions):
    global chat_sessions
    chat_sessions = sessions


@router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Чат не найден")
    return chat_sessions[session_id]


@router.post("/ask")
async def ask_question(request: ChatRequest):
    # Создаём сессию, если не задана
    if not request.session_id:
        request.session_id = str(uuid.uuid4())

    if request.session_id not in chat_sessions:
        chat_sessions[request.session_id] = ChatSession(
            id=request.session_id,
            user_id=1,
            messages=[]
        )

    # Добавляем вопрос в историю
    chat_sessions[request.session_id].messages.append(
        Message(role="user", content=request.question, timestamp=datetime.now().isoformat())
    )

    # Запускаем LangGraph
    app = create_rag_graph()
    inputs = {
        "question": request.question,
        "chat_history": chat_sessions[request.session_id].messages[:-1],
        "selected_file": "",
        "answer": "",
        "retry_count": 0
    }

    try:
        final_state = await app.ainvoke(inputs)
        answer = final_state["answer"]

        # Добавляем ответ в историю
        chat_sessions[request.session_id].messages.append(
            Message(role="assistant", content=answer, timestamp=datetime.now().isoformat())
        )

        # Кэшируем
        cache_manager.set(
            key=f"qa:{request.question}:{str(chat_sessions[request.session_id].messages[:-1])}",
            value=answer,
            ttl=3600
        )

        return {"answer": answer, "session_id": request.session_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")