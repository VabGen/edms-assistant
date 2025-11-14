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
from langchain_core.messages import HumanMessage
from starlette import status
from starlette.middleware.cors import CORSMiddleware
from langgraph.types import Command, Interrupt  # Импортируем Interrupt

from src.edms_assistant.agents.agent import create_agent_graph
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.config.settings import settings
from src.edms_assistant.core.registry import agent_registry
from src.edms_assistant.agents.agent_factory import register_all_agents
# УБРАНО: from src.edms_assistant.presentation.auth.jwt_auth import verify_and_extract_user_info
# ВМЕСТО ЭТОГО, импортируем саму функцию verify_edms_token
from src.edms_assistant.presentation.auth.jwt_auth import verify_edms_token
from src.edms_assistant.utils.file_utils import save_uploaded_file

logger = logging.getLogger(__name__)

app = FastAPI(
    title="EDMS Assistant API",
    version="3.0.0",
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
        edms_token: str = Form(..., description="Токен пользователя из EDMS"), # <-- Принимаем токен как Form параметр
        document_id: Optional[str] = Form(None, description="ID документа для взаимодействия"),
        agent_type: str = Form("main_planner_agent", description="Тип агента для обработки"),
        thread_id: Optional[str] = Form(None, description="ID диалога для продолжения"),
        file: Optional[UploadFile] = File(None, description="Файл для обработки"),
        # УБРАНО: user_info: dict = Depends(verify_and_extract_user_info)
        # ВМЕСТО ЭТОГО: ВАЛИДИРУЕМ ТОКЕН ВНУТРИ ФУНКЦИИ
):
    """
    Универсальный эндпоинт чата с поддержкой:
    - EDMS аутентификации
    - Загрузки файлов
    - Прерываний (уточнений и HITL) через interrupt
    """

    # --- НОВАЯ АУТЕНТИФИКАЦИЯ: Валидируем токен напрямую ---
    try:
        user_info_from_token = verify_edms_token(edms_token)
    except HTTPException:
        # Если verify_edms_token выбросит HTTPException (например, expired), она автоматически передастся клиенту
        raise
    except Exception:
        # На всякий случай, если verify_edms_token выбросит что-то другое
        raise HTTPException(status_code=401, detail="Invalid token")

    # --- ПРОВЕРКА: user_id из формы совпадает с user_id из токена ---
    token_user_id = user_info_from_token.get("sub") or user_info_from_token.get("id")
    if not token_user_id:
        raise HTTPException(status_code=401, detail="Token does not contain user_id")

    if user_id != token_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID mismatch"
        )
    # ---

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

    # --- ВОССТАНОВЛЕНИЕ СОСТОЯНИЯ ИЗ ЧЕКПОИНТЕРА ---
    agent_graph_instance = create_agent_graph() # <-- ИСПРАВЛЕНО: переименовал переменную

    try:
        checkpoint_tuple = await agent_graph_instance.checkpointer.aget_tuple(config) # <-- ИСПРАВЛЕНО: использую instance
        if checkpoint_tuple and checkpoint_tuple.state:
            # Восстанавливаем состояние из чекпоинтера
            saved_state_values = checkpoint_tuple.state.get("values", {})
            restored_state = GlobalState(**saved_state_values)

            # --- ОБНОВЛЕНИЕ ТОЛЬКО НЕОБХОДИМЫХ ПОЛЕЙ ---
            restored_state.user_message = user_message
            restored_state.messages.append(HumanMessage(content=user_message))
            if uploaded_file_path:
                restored_state.uploaded_file_path = uploaded_file_path
            if document_id:
                restored_state.document_id = document_id
            # service_token и user_id уже проверены выше
            # restored_state.service_token = edms_token # <-- НЕ ОБНОВЛЯЕМ, если не нужно
            # restored_state.user_id = UUID(user_id) # <-- НЕ ОБНОВЛЯЕМ, если не нужно

            initial_state = restored_state # <-- ИСПРАВЛЕНО: переименовал переменную
            logger.info(f"State restored from checkpoint for thread {thread_id}, hitl_request: {restored_state.hitl_request is not None}")
        else:
            # Если состояние не найдено, создаем новое
            logger.info(f"No checkpoint found for thread {thread_id}, creating initial state")
            initial_state = GlobalState( # <-- ИСПРАВЛЕНО: переименовал переменную
                user_id=UUID(user_id),
                service_token=edms_token,
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
                hitl_decisions=[],
                nlu_intent=None,
                nlu_entities={},
                rag_context=None,
                next_step_context=None
            )
    except Exception as e:
        logger.error(f"Error restoring state from checkpoint: {e}", exc_info=True)
        logger.warning("Using initial state due to checkpoint error")
        initial_state = GlobalState( # <-- ИСПРАВЛЕНО: переименовал переменную
            user_id=UUID(user_id),
            service_token=edms_token,
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
            hitl_decisions=[],
            nlu_intent=None,
            nlu_entities={},
            rag_context=None,
            next_step_context=None
        )

    try:
        # Запуск графа агента с восстановленным или новым состоянием
        # ПЕРЕХВАТЫВАЕМ Interrupt ИСКЛЮЧЕНИЕ - УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК
        try:
            result = await agent_graph_instance.ainvoke(initial_state, config=config) # <-- ИСПРАВЛЕНО: использую instance
        except Interrupt as e: # <-- ПЕРЕХВАТЫВАЕМ Interrupt
            # Если произошло прерывание, возвращаем информацию клиенту
            interrupt_value = e.value # <-- ИСПРАВЛЕНО: использую e.value
            interrupt_type = interrupt_value.get("type", "")

            # Пример обработки разных типов прерываний
            if interrupt_type == "employee_selection":
                candidates = interrupt_value.get("candidates", [])
                message = interrupt_value.get("message", "Требуется выбор сотрудника")

                return {
                    "requires_clarification": True,
                    "clarification_type": "employee_selection",
                    "message": message,
                    "candidates": candidates,
                    "thread_id": config["configurable"]["thread_id"],
                    "status": "awaiting_selection"
                }
            elif interrupt_type == "hitl_decision":
                # Это прерывание для HITL решения
                return {
                    "requires_hitl_decision": True,
                    "hitl_request": interrupt_value, # <-- ИСПРАВЛЕНО: использую interrupt_value
                    "thread_id": config["configurable"]["thread_id"],
                    "user_info": {
                        "user_id": user_info_from_token.get("sub", user_id), # Используем из токена или из формы
                        "permissions": user_info_from_token.get("permissions", ["document:read"]) # Базовые права
                    },
                    "status": "awaiting_decision"
                }
            else:
                # Неизвестный тип прерывания - универсальный обработчик
                message = interrupt_value.get("message", "Требуется уточнение")

                return {
                    "requires_clarification": True,
                    "clarification_type": "generic",
                    "message": message,
                    "interrupt_value": interrupt_value,  # Возвращаем полное значение для гибкости
                    "thread_id": config["configurable"]["thread_id"],
                    "status": "awaiting_input"
                }

        # Если interrupt не произошло, обрабатываем обычный результат
        # Возвращаем финальный ответ (если выполнение завершилось без прерывания)
        final_messages = result.get("messages", [])
        if final_messages:
            last_ai_message = [m for m in final_messages if hasattr(m, 'content')]
            if last_ai_message:
                response_text = last_ai_message[-1].content
            else:
                response_text = str(final_messages[-1])
        else:
            response_text = "Агент не смог сгенерировать ответ."

        return {
            "response": response_text,
            "requires_clarification": False,
            "requires_hitl_decision": False,
            "thread_id": config["configurable"]["thread_id"],
            "status": "completed"
        }

    except Exception as e:
        logger.error(f"Error during agent execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


@app.post("/resume")
async def resume_endpoint(
        decisions: list = Form(..., description="Решения пользователя для HITL/уточнений"),
        thread_id: str = Form(..., description="ID диалога для возобновления"),
        user_id: str = Form(..., description="ID пользователя из EDMS"),
        edms_token: str = Form(..., description="Токен пользователя из EDMS"),
        # УБРАНО: user_info: dict = Depends(verify_and_extract_user_info)
        # ВМЕСТО ЭТОГО: ВАЛИДИРУЕМ ТОКЕН ВНУТРИ ФУНКЦИИ
):
    """
    Универсальный эндпоинт для возобновления выполнения после прерывания (уточнений или HITL)
    """
    try:
        # --- АУТЕНТИФИКАЦИЯ ДЛЯ RESUME ---
        try:
            user_info_from_token = verify_edms_token(edms_token) # <-- ИСПРАВЛЕНО: переименовал переменную
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token for resume")

        # --- ПРОВЕРКА: user_id совпадает ---
        token_user_id = user_info_from_token.get("sub") or user_info_from_token.get("id") # <-- ИСПРАВЛЕНО: переименовал переменную
        if not token_user_id:
            raise HTTPException(status_code=401, detail="Token does not contain user_id")

        if user_id != token_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User ID mismatch for resume"
            )
        # ---

        # Проверяем thread_id
        UUID(thread_id)

        # Подготовка конфигурации
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id
            }
        }

        # Подготовка команды для возобновления
        command = Command(resume={"decisions": decisions})
        agent_graph_instance = create_agent_graph() # <-- ИСПРАВЛЕНО: переименовал переменную
        result = await agent_graph_instance.ainvoke(command, config=config) # <-- ИСПРАВЛЕНО: использую instance

        # Возвращаем результат
        final_messages = result.get("messages", [])
        if final_messages:
            last_ai_message = [m for m in final_messages if hasattr(m, 'content')]
            if last_ai_message:
                response_text = last_ai_message[-1].content
            else:
                response_text = str(final_messages[-1])
        else:
            response_text = "Агент завершил обработку после принятия решений."

        return {
            "response": response_text,
            "thread_id": thread_id, # <-- ИСПРАВЛЕНО: использую thread_id, а не threadId
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
        "version": "3.0.0"  # Версия API
    }