import json

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from typing import Optional
from uuid import UUID
import tempfile
import shutil
import os

from langchain_core.messages import AIMessage, HumanMessage
from starlette.middleware.cors import CORSMiddleware

from edms_assistant.agents.agent import create_agent_graph
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.config.settings import settings
from src.edms_assistant.core.registry import agent_registry
from src.edms_assistant.agents.agent_factory import register_all_agents
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

# Регистрируем все агенты при запуске
register_all_agents()


@app.post("/chat")
async def chat_endpoint(
        user_message: str = Form(..., description="Сообщение пользователя"),
        file: Optional[UploadFile] = File(None, description="Загруженный файл (опционально)"),
        service_token: str = Form(..., description="JWT-токен для авторизации в EDMS"),
        user_id: str = Form(..., description="UUID пользователя в EDMS"),
        document_id: Optional[str] = Form(None,
                                          description="ID документа, с которым идет взаимодействие (опционально)"),
        agent_type: str = Form("main_planner_agent",
                               description="Тип агента для обработки запроса (по умолчанию планирующий)"),
        thread_id: Optional[str] = Form(None, description="ID диалога для продолжения (опционально)")
):
    # Валидация user_id
    try:
        validated_user_id = UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid user_id format: {e}")

    # Подготовка конфигурации для LangGraph
    config = {"configurable": {"thread_id": thread_id or str(validated_user_id)}}

    # Подготовка начального состояния
    initial_state = GlobalState(
        user_id=validated_user_id,
        service_token=service_token,
        document_id=document_id,
        user_message=user_message,
        uploaded_file_path=None,
        messages=[],
        pending_plan=None,
        requires_execution=False,
        requires_clarification=False,
        clarification_context=None,
        error=None,
        current_agent=agent_type,
        available_agents=agent_registry.get_all_agent_names()
    )

    try:
        # Запуск графа
        agent_graph = create_agent_graph()
        result = await agent_graph.ainvoke(initial_state, config=config)

        # ПРОВЕРКА ПРЕРЫВАНИЯ - как в документации LangChain
        if "__interrupt__" in result:
            interrupt_data = result["__interrupt__"][0].value
            if interrupt_data.get("type") == "clarification":
                candidates = interrupt_data["candidates"]
                options = "\n".join(
                    f"{i + 1}. {c['last_name']} {c['first_name']} {c['middle_name']} (ID: {c['id']})"
                    for i, c in enumerate(candidates)
                )
                return {
                    "response": f"Найдено несколько сотрудников:\n{options}\n\nУточните выбор (укажите номер или ID):",
                    "requires_clarification": True,
                    "thread_id": thread_id or str(validated_user_id),
                    "candidates": candidates,
                }

        # Возвращаем финальный ответ
        final_messages = result.get("messages", [])
        if final_messages:
            last_message = final_messages[-1]
            response_text = getattr(last_message, "content", str(last_message))
        else:
            response_text = "Агент не смог сгенерировать ответ."

        return {
            "response": response_text,
            "requires_clarification": False,
            "thread_id": thread_id or str(validated_user_id)
        }

    except Exception as e:
        logger.error(f"Error during agent execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


@app.get("/agents")
async def list_agents():
    """Получение списка доступных агентов"""
    return {"agents": agent_registry.get_all_agent_names()}