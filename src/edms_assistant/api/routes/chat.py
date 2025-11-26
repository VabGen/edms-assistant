from fastapi import APIRouter, Request, Response, Cookie, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Annotated
from datetime import datetime
import uuid
from src.edms_assistant.rag.graph import create_rag_graph
from src.edms_assistant.core.redis_client import redis_client

router = APIRouter()

# Константы
SESSION_COOKIE_NAME = "rag_chat_session"  # Идентификатор "пользователя" (временный)
CHAT_TTL = 3600  # 1 час
MAX_CHATS_PER_USER = 20  # Макс. чатов на пользователя


class ChatRequest(BaseModel):
    question: str


class Message(BaseModel):
    role: str
    content: str
    timestamp: str


class ChatResponse(BaseModel):
    answer: str


def _build_session_key(chat_id: str) -> str:
    """Ключ для истории конкретного чата"""
    return f"chat:session:{chat_id}"


def _build_user_chats_key(user_session_id: str) -> str:
    """Ключ для списка чатов пользователя (временно по session_id)"""
    return f"user:chats:{user_session_id}"


# === ЭНДПОИНТЫ ===

@router.post("/new")
async def create_new_chat(
        request: Request,
        response: Response,
        session_id: Annotated[Optional[str], Cookie(alias=SESSION_COOKIE_NAME)] = None,
):
    """Создаёт новый чат и возвращает его chat_id"""
    # Убедимся, что есть основная сессия пользователя
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            httponly=True,
            max_age=CHAT_TTL * 24,  # Дольше, чем чаты
            samesite="lax",
            secure=False
        )

    # Создаём новый чат
    new_chat_id = str(uuid.uuid4())
    chat_key = _build_session_key(new_chat_id)
    await redis_client.set(chat_key, [], expire=CHAT_TTL)

    # Добавляем в список пользователя
    user_chats_key = _build_user_chats_key(session_id)
    user_chats = await redis_client.get(user_chats_key) or []
    if len(user_chats) >= MAX_CHATS_PER_USER:
        # Удаляем самый старый чат
        oldest_chat_id = user_chats.pop(0)
        await redis_client._client.delete(_build_session_key(oldest_chat_id))
    user_chats.append(new_chat_id)
    await redis_client.set(user_chats_key, user_chats, expire=CHAT_TTL * 24)

    return {"chat_id": new_chat_id}


@router.get("/list")
async def list_user_chats(
        session_id: Annotated[Optional[str], Cookie(alias=SESSION_COOKIE_NAME)] = None,
):
    """Возвращает список чатов с preview"""
    if not session_id:
        return {"chats": []}

    user_chats_key = _build_user_chats_key(session_id)
    chat_ids = await redis_client.get(user_chats_key) or []

    chats = []
    for chat_id in chat_ids:
        chat_key = _build_session_key(chat_id)
        history = await redis_client.get(chat_key) or []
        preview = "Новый чат"
        if history:
            last_msg = history[-1]
            content = last_msg.get("content", "")
            preview = (content[:50] + "...") if len(content) > 50 else content

        created_at = history[0]["timestamp"] if history else datetime.now().isoformat()
        chats.append({
            "chat_id": chat_id,
            "preview": preview,
            "created_at": created_at
        })

    chats.sort(key=lambda x: x["created_at"], reverse=True)
    return {"chats": chats}


@router.get("/{chat_id}/history")
async def get_chat_history_by_id(chat_id: str):
    """Получает историю чата по chat_id"""
    chat_key = _build_session_key(chat_id)
    history = await redis_client.get(chat_key) or []
    return {"messages": history}

@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: str,
    session_id: Annotated[Optional[str], Cookie(alias=SESSION_COOKIE_NAME)] = None,
):
    """
    Удаляет чат по chat_id.
    Удаляет:
      - историю чата из Redis,
      - запись о чате из списка пользователя.
    """
    if not session_id:
        raise HTTPException(status_code=403, detail="Сессия не найдена")

    # 1. Удаляем саму историю чата
    chat_key = _build_session_key(chat_id)
    await redis_client._client.delete(chat_key)

    # 2. Удаляем chat_id из списка чатов пользователя
    user_chats_key = _build_user_chats_key(session_id)
    user_chats = await redis_client.get(user_chats_key) or []
    if chat_id in user_chats:
        user_chats.remove(chat_id)
        await redis_client.set(user_chats_key, user_chats, expire=CHAT_TTL * 24)

    return {"status": "deleted", "chat_id": chat_id}


@router.post("/{chat_id}/ask")
async def ask_question_in_chat(
        request: Request,
        response: Response,
        chat_id: str,
        chat_request: ChatRequest,
        session_id: Annotated[Optional[str], Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> ChatResponse:
    """
    Отправляет вопрос в указанный чат.
    Автоматически привязывает чат к пользователю при первом запросе.
    """
    # Привязка чата к пользователю (защита от прямого доступа)
    if session_id:
        user_chats_key = _build_user_chats_key(session_id)
        user_chats = await redis_client.get(user_chats_key) or []
        if chat_id not in user_chats:
            user_chats.append(chat_id)
            await redis_client.set(user_chats_key, user_chats, expire=CHAT_TTL * 24)

    chat_key = _build_session_key(chat_id)
    chat_history: List[dict] = await redis_client.get(chat_key) or []

    # Добавляем вопрос
    user_msg = {
        "role": "user",
        "content": chat_request.question,
        "timestamp": datetime.now().isoformat()
    }
    chat_history.append(user_msg)

    # Запускаем агент
    inputs = {
        "question": chat_request.question,
        "chat_history": chat_history[:-1],
        "selected_file": "",
        "answer": "",
        "retry_count": 0
    }
    final_state = await create_rag_graph().ainvoke(inputs)
    answer = final_state["answer"]

    # Добавляем ответ
    ai_msg = {
        "role": "assistant",
        "content": answer,
        "timestamp": datetime.now().isoformat()
    }
    chat_history.append(ai_msg)

    # Сохраняем
    await redis_client.set(chat_key, chat_history, expire=CHAT_TTL)

    return ChatResponse(answer=answer)
