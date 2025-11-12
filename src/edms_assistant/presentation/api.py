# src/edms_assistant/presentation/api.py
from anyio.streams import file
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Path
from typing import Optional
from uuid import UUID
import tempfile
import shutil
import os

from langchain_core.messages import HumanMessage, AIMessage
from starlette.middleware.cors import CORSMiddleware
from langgraph.types import Command

from edms_assistant.agents.agent import create_agent_graph
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.config.settings import settings
from src.edms_assistant.core.registry import agent_registry
from src.edms_assistant.agents.agent_factory import register_all_agents
import logging

logger = logging.getLogger(__name__)

# UPLOAD_DIR = Path(tempfile.gettempdir()) / "edms_agent_uploads"
# UPLOAD_DIR.mkdir(exist_ok=True)
app = FastAPI(title="EDMS Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_all_agents()


@app.post("/chat")
async def chat_endpoint(
        user_message: str = Form(..., description="Сообщение пользователя"),
        file: Optional[UploadFile] = File(None, description="Загруженный файл (опционально)"),
        # ✅ Добавлен параметр file
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


    uploaded_file_path = None

    try:
        if file:
            if hasattr(file, 'filename') and file.filename:
                safe_filename = file.filename
            else:
                safe_filename = "unnamed_file"

            temp_file_path = tempfile.mktemp(suffix=f"_{safe_filename}")
            try:
                with open(temp_file_path, 'wb') as buffer:
                    shutil.copyfileobj(file.file, buffer)
                uploaded_file_path = temp_file_path
                logger.info(f"Saved uploaded file to {uploaded_file_path}")
            except Exception as e:
                logger.error(f"File save error: {e}")
                raise HTTPException(
                    status_code=500, detail="Failed to process uploaded file."
                )

        # Подготовка начального состояния
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
            current_agent=agent_type,
            available_agents=agent_registry.get_all_agent_names()
        )

        # Запуск графа
        agent_graph = create_agent_graph()
        result = await agent_graph.ainvoke(initial_state, config=config)

        # ПРОВЕРКА ПРЕРЫВАНИЯ (согласно документации LangGraph Python)
        if "__interrupt__" in result:
            interrupt_data = result["__interrupt__"][0].value  # ✅ .value как в документации
            if interrupt_data.get("type") == "clarification":
                candidates = interrupt_data["candidates"]
                candidates_list = "\n".join([
                    f"{i + 1}. {cand.get('first_name', '')} {cand.get('middle_name', '')} {cand.get('last_name', '')}"
                    for i, cand in enumerate(candidates)
                ])

                return {
                    "requires_clarification": True,
                    "clarification_type": "employee_selection",
                    "message": "Найдено несколько кандидатов. Пожалуйста, уточните, о ком именно идет речь:",
                    "candidates": candidates,
                    "candidates_list": candidates_list,
                    "thread_id": thread_id or str(validated_user_id)
                }

        # Возвращаем финальный ответ (если не было прерывания)
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
            "requires_clarification": False,
            "thread_id": thread_id or str(validated_user_id)
        }

    except Exception as e:
        logger.error(f"Error during agent execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")

    finally:
        # ✅ Удаляем временный файл после обработки
        # Теперь uploaded_file_path всегда определена (может быть None)
        if uploaded_file_path and os.path.exists(uploaded_file_path):
            try:
                os.unlink(uploaded_file_path)
                logger.info(f"Deleted temporary file: {uploaded_file_path}")
            except OSError as e:
                logger.warning(f"Could not delete temp file {uploaded_file_path}: {e}")
