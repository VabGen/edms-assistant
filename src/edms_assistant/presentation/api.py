# src/edms_assistant/presentation/api.py
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from src.edms_assistant.graph.graph import create_agent_graph

logger = logging.getLogger(__name__)

# Директория для загрузок
UPLOAD_DIR = Path(tempfile.gettempdir()) / "edms_agent_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="EDMS Assistant API",
    description="API for interacting with the EDMS document management agent. Accepts text and files.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    user_id: str = Form(...),
    service_token: str = Form(...),
    message: str = Form(...),
    document_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    attachment_id: Optional[str] = Form(None),
):
    # === 1. Валидация user_id ===
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid user_id format. Must be a valid UUID."
        )

    # === 2. Валидация service_token (минимальная) ===
    if not service_token or len(service_token) < 10:
        raise HTTPException(status_code=400, detail="Invalid or missing service_token.")

    # === 3. Обработка файла (если есть) ===
    file_path: Optional[Path] = None
    if file:
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

    # === 4. Логирование (без токена!) ===
    masked_token = (
        f"{service_token[:6]}***{service_token[-4:]}" if service_token else "N/A"
    )
    logger.info(
        f"Incoming request: user_id={user_uuid}, document_id={document_id}, "
        f"message_preview='{message[:50]}...', file={file_path is not None}, token={masked_token}"
    )

    try:
        graph = create_agent_graph()
        initial_state = {
            "user_id": user_uuid,
            "service_token": service_token,
            "document_id": document_id,
            "user_message": message,
            "messages": [{"role": "user", "content": message}],
            "uploaded_file_path": str(file_path) if file_path else None,
            "uploaded_file_name": file.filename if file else None,
            "attachment_id": attachment_id,
            "attachment_name": None,
        }
        result = await graph.ainvoke(
            initial_state, config={"configurable": {"thread_id": str(user_uuid)}}
        )
        last_message = result["messages"][-1]
        content = getattr(last_message, "content", "Нет ответа.")

        # Удаляем файл ТОЛЬКО после успешной обработки
        if file_path:
            background_tasks.add_task(_cleanup_file, file_path)

        return {"response": content}

    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        # Удаляем файл даже при ошибке
        if file_path:
            background_tasks.add_task(_cleanup_file, file_path)
        raise HTTPException(status_code=500, detail="Agent error")


# # src/edms_assistant/presentation/api.py
# import logging
# import tempfile
# import uuid
# from pathlib import Path
# from typing import Optional
# from fastapi.middleware.cors import CORSMiddleware
# from src.edms_assistant.graph.graph import create_agent_graph
# from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
#
# logger = logging.getLogger(__name__)
#
# # директория для загрузок
# UPLOAD_DIR = Path(tempfile.gettempdir()) / "edms_agent_uploads"
# UPLOAD_DIR.mkdir(exist_ok=True)
#
# app = FastAPI(
#     title="EDMS Assistant API",
#     description="API for interacting with the EDMS document management agent. Accepts text and files.",
#     version="0.1.0",
# )
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
#
# def _cleanup_file(file_path: Path):
#     """Фоновая задача для удаления временного файла."""
#     try:
#         file_path.unlink(missing_ok=True)
#         logger.debug(f"Cleaned up temporary file: {file_path}")
#     except Exception as e:
#         logger.warning(f"Failed to clean up {file_path}: {e}")
#
#
# @app.post("/chat")
# async def assistant_chat(
#     background_tasks: BackgroundTasks,
#     user_id: str = Form(...),
#     service_token: str = Form(...),
#     message: str = Form(...),
#     document_id: Optional[str] = Form(None),
#     file: Optional[UploadFile] = File(None),
#     attachment_id: Optional[str] = Form(None),
# ):
#     # === 1. Валидация user_id ===
#     try:
#         user_uuid = uuid.UUID(user_id)
#     except ValueError:
#         raise HTTPException(
#             status_code=400, detail="Invalid user_id format. Must be a valid UUID."
#         )
#
#     # === 2. Валидация service_token (минимальная) ===
#     if not service_token or len(service_token) < 10:
#         raise HTTPException(status_code=400, detail="Invalid or missing service_token.")
#
#     file_path: Optional[Path] = None
#     if file:
#         safe_filename = Path(file.filename).name
#         if not safe_filename:
#             raise HTTPException(status_code=400, detail="Invalid file name.")
#
#         file_path = UPLOAD_DIR / f"{user_uuid}_{safe_filename}"
#         try:
#             with open(file_path, "wb") as f:
#                 content = await file.read()
#                 f.write(content)
#             logger.info(f"Saved uploaded file to {file_path}")
#             # НЕ удаляем файл здесь!
#         except Exception as e:
#             logger.error(f"File save error: {e}")
#             raise HTTPException(
#                 status_code=500, detail="Failed to process uploaded file."
#             )
#
#     try:
#         graph = create_agent_graph()
#         initial_state = {
#             "user_id": user_uuid,
#             "service_token": service_token,
#             "document_id": document_id,
#             "user_message": message,
#             "messages": [{"role": "user", "content": message}],
#             "uploaded_file_path": str(file_path) if file_path else None,
#             "attachment_id": attachment_id,
#             "attachment_name": None,
#         }
#         result = await graph.ainvoke(
#             initial_state, config={"configurable": {"thread_id": str(user_uuid)}}
#         )
#         last_message = result["messages"][-1]
#         content = getattr(last_message, "content", "Нет ответа.")
#
#         # Удаляем файл ТОЛЬКО ПОСЛЕ успешной обработки
#         if file_path:
#             background_tasks.add_task(_cleanup_file, file_path)
#
#         return {"response": content}
#
#     except Exception as e:
#         logger.error(f"Agent execution failed: {e}", exc_info=True)
#         # Удаляем файл даже при ошибке
#         if file_path:
#             background_tasks.add_task(_cleanup_file, file_path)
#             raise HTTPException(status_code=500, detail="Agent error")
#
#     # === 4. Логируем (без токена!) ===
#     masked_token = (
#         f"{service_token[:6]}***{service_token[-4:]}" if service_token else "N/A"
#     )
#     logger.info(
#         f"Incoming request: user_id={user_uuid}, document_id={document_id}, "
#         f"message_preview='{message[:50]}...', file={file_path is not None}, token={masked_token}"
#     )
#     try:
#         graph = create_agent_graph()
#         initial_state = {
#             "user_id": user_uuid,
#             "service_token": service_token,
#             "document_id": document_id,
#             "user_message": message,
#             "messages": [{"role": "user", "content": message}],
#             "uploaded_file_path": str(file_path) if file_path else None,
#             "requires_human_input": False,
#             "attachment_id": attachment_id,
#             "attachment_name": None,
#             "error": None,
#         }
#         result = await graph.ainvoke(
#             initial_state, config={"configurable": {"thread_id": str(user_uuid)}}
#         )
#         last_message = result["messages"][-1]
#         if isinstance(last_message, dict):
#             content = last_message.get("content", "Нет ответа.")
#         else:
#             content = getattr(last_message, "content", "Нет ответа.")
#         return {"response": content}
#
#     except Exception as e:
#         logger.error(f"Agent execution failed: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail="Agent error")
