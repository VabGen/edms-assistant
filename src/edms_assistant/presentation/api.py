# src\edms_assistant\presentation\api.py
import logging
import tempfile
import uuid
import json
from pathlib import Path
from typing import Optional
from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
    Body,
)
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from src.edms_assistant.core.orchestrator.orchestrator import create_orchestrator_graph
from src.edms_assistant.core.agents.employee_agent import create_employee_agent_graph

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(tempfile.gettempdir()) / "edms_agent_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="EDMS Assistant API",
    description="API for interacting with the EDMS document management agent. Accepts text and files.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _cleanup_file(file_path: Path):
    """Фоновая задача для удаления временного файла."""
    try:
        file_path.unlink(missing_ok=True)
        logger.debug(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to clean up {file_path}: {e}")

@app.post("/chat")
async def assistant_chat(
        background_tasks: BackgroundTasks,
        user_id: str = Form(None),
        service_token: str = Form(None),
        message: str = Form(None),
        selected_candidate_id: str = Form(None),
        document_id: Optional[str] = Form(None),
        file: Optional[UploadFile] = File(None),
        thread_id: Optional[str] = Form(None),
):
    logger.info(f"API received: user_id={user_id}, document_id={document_id}, message={message}, selected_candidate_id={selected_candidate_id}")

    # === 1. Валидация thread_id ===
    if thread_id:
        try:
            user_uuid = uuid.UUID(thread_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid thread_id format. Must be a valid UUID."
            )
    else:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required if no thread_id provided.")
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid user_id format. Must be a valid UUID."
            )

    # === 2. Валидация service_token (если есть) ===
    if service_token and len(service_token) < 10:
        raise HTTPException(status_code=400, detail="Invalid service_token.")

    # === 3. Обработка файла (если есть и это новый запрос) ===
    file_path: Optional[Path] = None
    if file and not selected_candidate_id:  # Только если это не уточнение
        safe_filename = Path(file.filename).name
        if not safe_filename:
            raise HTTPException(status_code=400, detail="Invalid file name.")

        file_path = UPLOAD_DIR / f"{user_uuid}_{safe_filename}"
        try:
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            logger.info(f"Saved uploaded file to {file_path}")
        except Exception as e:
            logger.error(f"File save error: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to process uploaded file."
            )

    config = {"configurable": {"thread_id": str(user_uuid)}}

    # === 4. Если пришло уточнение, вызываем employee_agent отдельно ===
    if selected_candidate_id:
        if not service_token:
            raise HTTPException(status_code=400, detail="service_token is required for clarification.")

        employee_graph = create_employee_agent_graph()

        # Создаём ToolMessage с ID кандидата
        tool_msg = ToolMessage(
            content=json.dumps({"id": selected_candidate_id}), tool_call_id="mock"
        )

        # Вызываем employee_agent_graph с ToolMessage
        result = await employee_graph.ainvoke(
            {
                "messages": [tool_msg],
                "service_token": service_token,
                "user_message": "",
            },
            config=config
        )

        last_message = result["messages"][-1]
        content = getattr(last_message, "content", "Нет ответа.")
        return {"response": content}

    # === 5. Иначе — обычный запуск оркестратора ===
    if not message:
        raise HTTPException(status_code=400, detail="Message is required for new request.")

    graph = create_orchestrator_graph()

    initial_state = {
        "user_id": user_uuid,
        "service_token": service_token,
        "document_id": document_id,
        "user_message": message,
        "messages": [{"role": "user", "content": message}],
        "uploaded_file_path": str(file_path) if file_path else None,
        "uploaded_file_name": file.filename if file else None,
        "next_agent": None,
        "agent_input": None,
        "requires_clarification": False,
        "sub_agent_result": None,
        "requires_human_input": False,
        "error": None,
        "attachment_id": None,
        "attachment_name": None,
        "current_document": None,
        # Поля для employee_agent
        "should_add_responsible_after_clarification": False,
        "document_id_to_add": None,
        "selected_candidate_id": None,
        "next_node": None,
    }

    try:
        result = await graph.ainvoke(initial_state, config=config)

        # === ПРОВЕРКА ПРЕРЫВАНИЯ ===
        if "__interrupt__" in result:
            interrupt_data = result["__interrupt__"][0].value
            if interrupt_data.get("type") == "clarification":
                candidates = interrupt_data["candidates"]
                options = "\n".join(
                    f"{i + 1}. {c['last_name']} {c['first_name']} {c['middle_name']} (ID: {c['id']})"
                    for i, c in enumerate(candidates)
                )
                return {
                    "response": f"Найдено несколько ответственных:\n{options}\n\nУточните выбор (укажите номер или ID):",
                    "requires_clarification": True,
                    "thread_id": str(user_uuid),
                    "candidates": candidates,
                }

        last_message = result["messages"][-1]
        content = getattr(last_message, "content", "Нет ответа.")

        if file_path:
            background_tasks.add_task(_cleanup_file, file_path)

        return {"response": content}

    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        if file_path:
            background_tasks.add_task(_cleanup_file, file_path)
        raise HTTPException(status_code=500, detail="Agent error")