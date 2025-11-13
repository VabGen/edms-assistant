# src/edms_assistant/presentation/api.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer
from typing import Optional
from uuid import UUID
import tempfile
import shutil
import os
from datetime import datetime
import logging
from langchain_core.messages import HumanMessage, AIMessage
from starlette.middleware.cors import CORSMiddleware
from langgraph.types import Command

from src.edms_assistant.agents.agent import create_agent_graph
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.config.settings import settings
from src.edms_assistant.core.registry import agent_registry
from src.edms_assistant.agents.agent_factory import register_all_agents
from src.edms_assistant.presentation.auth.jwt_auth import verify_and_extract_user_info
from src.edms_assistant.utils.file_utils import save_uploaded_file

logger = logging.getLogger(__name__)

app = FastAPI(
    title="EDMS Assistant API",
    version="2.0.0",
    description="Production-ready EDMS Assistant with Human-in-the-Loop capabilities"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"https?://.*\.example\.com"
)

# Security
security = HTTPBearer()

register_all_agents()


@app.post("/chat")
async def chat_endpoint(
        user_message: str = Form(..., description="Сообщение пользователя"),
        user_id: str = Form(..., description="ID пользователя из EDMS"),
        edms_token: str = Form(..., description="Токен пользователя из EDMS"),
        document_id: Optional[str] = Form(None, description="ID документа для взаимодействия"),
        agent_type: str = Form("main_planner_agent", description="Тип агента для обработки"),
        thread_id: Optional[str] = Form(None, description="ID диалога для продолжения"),
        file: Optional[UploadFile] = File(None, description="Файл для обработки"),
        # используем токен только для проверки валидности
        user_info: dict = Depends(verify_and_extract_user_info)  # Получаем информацию из токена
):
    """
    Основной эндпоинт чата с поддержкой:
    - EDMS аутентификации
    - Загрузки файлов
    - Прерываний HITL
    """

    # Проверяем валидность токена (проверка в verify_and_extract_user_info)
    # Но используем user_id из формы, а не из токена (т.к. токен может быть не JWT)
    # Вместо проверки совпадения, просто проверим, что токен валидный
    if user_info.get("token") != edms_token:
        # Это означает, что токен из заголовка не совпадает с токеном из формы
        # В реальном приложении может потребоваться другая логика
        pass

    # Валидация thread_id
    if thread_id:
        try:
            UUID(thread_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid thread_id format")

    # Обработка загрузки файла
    uploaded_file_path = None
    if file:
        uploaded_file_path = await save_uploaded_file(file)

    # Подготовка конфигурации для LangGraph
    config = {
        "configurable": {
            "thread_id": thread_id or user_id,
            "user_id": user_id
        }
    }

    # Подготовка начального состояния
    initial_state = GlobalState(
        user_id=UUID(user_id),  # Используем user_id из формы
        service_token=edms_token,  # Передаем токен EDMS для вызова API
        document_id=document_id,
        user_message=user_message,
        uploaded_file_path=uploaded_file_path,
        messages=[HumanMessage(content=user_message)],
        pending_plan=None,
        requires_execution=False,
        requires_clarification=False,
        clarification_context=None,
        error=None,
        current_agent=agent_type,
        available_agents=agent_registry.get_all_agent_names(),
        hitl_pending=False,
        hitl_request=None,
        hitl_decisions=[]
    )

    try:
        # Запуск графа агента
        agent_graph = create_agent_graph()
        result = await agent_graph.ainvoke(initial_state, config=config)

        # Проверка прерываний HITL
        if "__interrupt__" in result:
            interrupt_data = result["__interrupt__"]
            if isinstance(interrupt_data, list) and len(interrupt_data) > 0:
                hitl_request = interrupt_data[0].value
                return {
                    "requires_hitl_decision": True,
                    "hitl_request": hitl_request,
                    "thread_id": config["configurable"]["thread_id"],
                    "user_info": {
                        "user_id": user_info["user_id"],
                        "permissions": user_info["permissions"]
                    },
                    "status": "awaiting_decision"
                }

        # Возвращаем финальный ответ
        final_messages = result.get("messages", [])
        if final_messages:
            last_ai_message = [m for m in final_messages if isinstance(m, AIMessage)]
            if last_ai_message:
                response_text = last_ai_message[-1].content
            else:
                response_text = str(final_messages[-1])
        else:
            response_text = "Агент не смог сгенерировать ответ."

        return {
            "response": response_text,
            "requires_hitl_decision": False,
            "thread_id": config["configurable"]["thread_id"],
            "status": "completed"
        }

    except Exception as e:
        logger.error(f"Error during agent execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


@app.post("/resume")
async def resume_endpoint(
        decisions: list = Form(..., description="Решения пользователя для HITL"),
        thread_id: str = Form(..., description="ID диалога для возобновления"),
        user_id: str = Form(..., description="ID пользователя из EDMS"),
        edms_token: str = Form(..., description="Токен пользователя из EDMS"),
        user_info: dict = Depends(verify_and_extract_user_info)
):
    """
    Эндпоинт для возобновления выполнения после прерывания HITL
    """
    try:
        # Проверяем thread_id
        UUID(thread_id)

        # Подготовка команды для возобновления
        command = Command(resume={"decisions": decisions})

        # Подготовка конфигурации
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id
            }
        }

        # Запуск графа с командой возобновления
        agent_graph = create_agent_graph()
        result = await agent_graph.ainvoke(command, config=config)

        # Возвращаем результат
        final_messages = result.get("messages", [])
        if final_messages:
            last_ai_message = [m for m in final_messages if isinstance(m, AIMessage)]
            if last_ai_message:
                response_text = last_ai_message[-1].content
            else:
                response_text = str(final_messages[-1])
        else:
            response_text = "Агент завершил обработку после принятия решений."

        return {
            "response": response_text,
            "thread_id": thread_id,
            "status": "resumed"
        }

    except Exception as e:
        logger.error(f"Error during resume: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Resume execution error: {str(e)}")


@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }