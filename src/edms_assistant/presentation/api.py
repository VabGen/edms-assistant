# src/edms_assistant/presentation/api.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from typing import Optional
from uuid import UUID
import tempfile
import shutil
import os

from langchain_core.messages import AIMessage
from starlette.middleware.cors import CORSMiddleware

from src.edms_assistant.agents.agent import create_agent_graph
from src.edms_assistant.state.state import GlobalState
from src.edms_assistant.config.settings import settings
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="EDMS Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Глобальный граф агента ---
agent_graph = create_agent_graph()

@app.post("/chat")
async def chat_endpoint(
    user_message: str = Form(..., description="Сообщение пользователя"),
    file: Optional[UploadFile] = File(None, description="Загруженный файл (опционально)"),
    service_token: str = Form(..., description="JWT-токен для авторизации в EDMS"),
    user_id: str = Form(..., description="UUID пользователя в EDMS"),
    document_id: Optional[str] = Form(None, description="ID документа, с которым идет взаимодействие (опционально)")
):
    # Валидация user_id
    try:
        validated_user_id = UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid user_id format: {e}")

    # Обработка загруженного файла
    uploaded_file_path = None
    if file:
        temp_file_path = tempfile.mktemp(suffix=f"_{file.filename}")
        try:
            with open(temp_file_path, 'wb') as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_file_path = temp_file_path
        except Exception as e:
            logger.error(f"Error saving uploaded file: {e}")
            raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Подготовка начального состояния для агента
    initial_state = GlobalState(
        user_id=validated_user_id,
        service_token=service_token,
        document_id=document_id,
        user_message=user_message,
        uploaded_file_path=uploaded_file_path,
        messages=[],
        pending_plan=None,
        requires_execution=False,
        requires_clarification=False,
        clarification_context=None,
        error=None,
    )

    # Запуск агента
    try:
        config = {"configurable": {"thread_id": str(validated_user_id)}}
        result = await agent_graph.ainvoke(initial_state, config=config)

        # Проверяем, возвращён ли словарь или BaseModel
        if hasattr(result, 'requires_clarification'):
            # Если это BaseModel (Pydantic)
            requires_clarification = result.requires_clarification
            clarification_context = result.clarification_context
            final_messages = result.messages
        else:
            # Если это словарь
            requires_clarification = result.get("requires_clarification", False)
            clarification_context = result.get("clarification_context", None)
            final_messages = result.get("messages", [])

        # Проверяем, требуется ли уточнение
        if requires_clarification:
            context = clarification_context
            clarification_type = context.get("type")
            if clarification_type == "candidate_selection":
                candidates = context.get("candidates", [])
                candidate_list_str = "\n".join([f"- {c.get('last_name', '')} {c.get('first_name', '')} ({c.get('id')})" for c in candidates])
                return {
                    "requires_clarification": True,
                    "clarification_type": "candidate_selection",
                    "message": "Найдено несколько кандидатов. Пожалуйста, уточните, о ком именно идет речь:",
                    "candidates": candidates,
                    "original_action": context.get("original_action"),
                    "original_args": context.get("original_args")
                }
            # Добавьте другие типы уточнений здесь
            else:
                return {"error": f"Тип уточнения '{clarification_type}' не поддерживается."}

        # Возвращаем финальный ответ агента
        if final_messages:
            last_ai_message = [m for m in final_messages if isinstance(m, AIMessage)][-1]
            if hasattr(last_ai_message, 'content'):
                 response_text = last_ai_message.content
            else:
                 response_text = str(last_ai_message)
        else:
             response_text = "Агент не смог сгенерировать ответ."

        return {"response": response_text, "requires_clarification": False}

    except Exception as e:
        logger.error(f"Error during agent execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")

    finally:
        # Удаляем временный файл после обработки
        if uploaded_file_path and os.path.exists(uploaded_file_path):
            try:
                os.unlink(uploaded_file_path)
            except OSError as e:
                logger.warning(f"Could not delete temp file {uploaded_file_path}: {e}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}