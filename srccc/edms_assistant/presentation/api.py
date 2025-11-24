# srccc/edms_assistant/presentation/api.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.security import HTTPBearer
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Interrupt
from srccc.edms_assistant.core.state import GlobalState, HitlOptions
from srccc.edms_assistant.core.graph import create_agent_graph
from srccc.edms_assistant.agents.agent_factory import AgentFactory
from srccc.edms_assistant.utils.auth import verify_and_extract_user_info
from srccc.edms_assistant.utils.file_utils import save_uploaded_file, validate_file_type, cleanup_temp_file
import uuid
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="EDMS Assistant API", version="1.0.0")

security = HTTPBearer()


# === Модель для ответа ===
class ChatResponse(BaseModel):
    response: Optional[str] = None
    requires_clarification: bool = False
    clarification_type: Optional[str] = None
    message: Optional[str] = None
    candidates: Optional[List[Dict[str, Any]]] = None
    requires_hitl_decision: bool = False
    hitl_request: Optional[Dict[str, Any]] = None
    thread_id: str
    status: str = "success"


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
        user_message: str = Form(..., description="Сообщение пользователя"),
        user_id: str = Form(..., description="ID пользователя из EDMS"),
        edms_token: str = Form(..., description="Токен пользователя из EDMS"),
        document_id: Optional[str] = Form(None, description="ID документа для взаимодействия"),
        agent_type: str = Form("main_planner_agent", description="Тип агента для обработки"),
        thread_id: Optional[str] = Form(None, description="ID диалога для продолжения"),
        uploaded_file: Optional[UploadFile] = File(None, description="Загруженный файл для анализа")
):
    logger.info(
        f"[API] chat_endpoint called with user_message: '{user_message[:50]}...', user_id: {user_id}, thread_id: {thread_id}")

    # Валидация thread_id
    if not thread_id:
        thread_id = str(uuid.uuid4())
        logger.info(f"[API] Generated new thread_id: {thread_id}")

    # Подготовка конфигурации
    config = {"configurable": {"thread_id": thread_id, "user_id": str(user_id)}}

    # Подготовка состояния
    try:
        user_uuid = UUID(user_id)
        doc_uuid = UUID(document_id) if document_id else None
    except ValueError:
        logger.error(f"[API] Invalid user_id or document_id format: user_id={user_id}, document_id={document_id}")
        raise HTTPException(status_code=400, detail="Invalid user_id or document_id format")

    uploaded_file_path = None
    if uploaded_file:
        if not validate_file_type(uploaded_file.filename):
            logger.error(f"[API] Unsupported file type: {uploaded_file.filename}")
            raise HTTPException(status_code=400, detail="Unsupported file type")
        uploaded_file_path = await save_uploaded_file(uploaded_file)
        logger.info(f"[API] File uploaded to: {uploaded_file_path}")

    agent_graph = create_agent_graph()  # Создаём граф
    logger.info(f"[API] Created agent graph instance.")

    try:
        checkpoint_tuple = await agent_graph.checkpointer.aget_tuple(config)
        logger.info(f"[API] Retrieved checkpoint tuple: {checkpoint_tuple is not None}")
        if checkpoint_tuple and checkpoint_tuple.state:
            saved_state_values = checkpoint_tuple.state.get("values", {})
            logger.info(f"[API] Found saved state values keys: {list(saved_state_values.keys())}")
            # Восстанавливаем состояние
            restored_state = GlobalState(**saved_state_values)
            restored_state.user_message = user_message
            restored_state.messages.append(HumanMessage(content=user_message))
            if uploaded_file_path:
                restored_state.uploaded_file_path = uploaded_file_path
            if document_id:
                restored_state.document_id = UUID(document_id)
            restored_state.service_token = edms_token
            initial_state = restored_state
            logger.info(f"[API] Restored state from checkpoint for thread {thread_id}.")
        else:
            # Создаём новое состояние
            initial_state = GlobalState(
                user_id=user_uuid,
                service_token=edms_token,
                document_id=doc_uuid,
                user_message=user_message,
                uploaded_file_path=uploaded_file_path,
                messages=[HumanMessage(content=user_message)],
                pending_plan=None,
                requires_execution=False,
                requires_clarification=False,
                clarification_context=None,
                error=None,
                current_agent=agent_type,
                available_agents=AgentFactory.get_available_agents(),  # Используем фабрику
                hitl_pending=False,
                hitl_request=None,
                hitl_decisions=[],
                next_node="planning",
                waiting_for_hitl_response=False,
                nlu_intent=None,
                nlu_confidence=0.0,
                rag_context=[],
            )
            logger.info(f"[API] Created new initial state for thread {thread_id}.")
    except Exception as e:
        logger.error(f"[API] Error restoring state from checkpoint: {e}", exc_info=True)
        initial_state = GlobalState(
            user_id=user_uuid,
            service_token=edms_token,
            document_id=doc_uuid,
            user_message=user_message,
            uploaded_file_path=uploaded_file_path,
            messages=[HumanMessage(content=user_message)],
            pending_plan=None,
            requires_execution=False,
            requires_clarification=False,
            clarification_context=None,
            error=None,
            current_agent=agent_type,
            available_agents=AgentFactory.get_available_agents(),  # Используем фабрику
            hitl_pending=False,
            hitl_request=None,
            hitl_decisions=[],
            next_node="planning",
            waiting_for_hitl_response=False,
            nlu_intent=None,
            nlu_confidence=0.0,
            rag_context=[],
        )
        logger.info(f"[API] Created fallback initial state for thread {thread_id} after error.")

    logger.info(
        f"[API] About to invoke graph with initial state messages count: {len(initial_state.messages)}, user_message: '{initial_state.user_message[:50]}...'")

    try:
        # --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Ловим Interrupt ---
        result = await agent_graph.ainvoke(initial_state, config=config)
        logger.info(
            f"[API] Graph invocation successful. Result type: {type(result)}, keys: {getattr(result, '__dict__', dir(result)) if hasattr(result, '__dict__') else 'No __dict__'}")
    except Interrupt as e:
        logger.info(f"[API] Caught interrupt during graph invocation: {e.value}")
        # ... (обработка прерывания как раньше) ...
        interrupt_value = e.value
        interrupt_type = interrupt_value.get("type", "")

        if interrupt_type in ["employee_selection", "document_selection", "attachment_selection"]:
            message = interrupt_value.get("message", "Требуется уточнение")
            candidates = interrupt_value.get("candidates",
                                             interrupt_value.get("documents", interrupt_value.get("attachments", [])))
            updated_state_for_checkpoint = initial_state.model_copy(update={
                "waiting_for_hitl_response": True,
                "hitl_request": interrupt_value
            })
            await agent_graph.aupdate_state(config, updated_state_for_checkpoint)
            logger.info(
                f"State explicitly saved to checkpoint for thread {thread_id} after {interrupt_type} interrupt.")

            return ChatResponse(
                requires_clarification=True,
                clarification_type=interrupt_type,
                message=message,
                candidates=candidates,
                thread_id=thread_id,
                status="awaiting_selection"
            )
        else:
            return ChatResponse(
                requires_clarification=True,
                clarification_type="generic",
                message=interrupt_value.get("message", "Требуется уточнение"),
                thread_id=thread_id,
                status="awaiting_input"
            )
    except Exception as e:
        logger.error(f"[API] Error during graph invocation: {e}", exc_info=True)
        # Возвращаем ответ с ошибкой
        return ChatResponse(
            response="Произошла ошибка при обработке запроса.",
            requires_clarification=False,
            thread_id=thread_id,
            status="error"
        )

        # --- ИСПРАВЛЕНО: Работаем с result как с GlobalState или Dict ---
        # LangGraph должен вернуть GlobalState, но если возвращается Dict, обрабатываем оба случая.
    if isinstance(result, GlobalState):
        logger.info(f"[API] Result is GlobalState. Messages count: {len(result.messages)}")
        final_messages = result.messages  # Получаем из экземпляра GlobalState
    elif isinstance(result, dict):
        logger.info(f"[API] Result is dict. Keys: {list(result.keys())}")
        # Если возвращается dict, ищем ключ 'messages'
        final_messages = result.get("messages", [])
        logger.info(f"[API] Final messages from result dict: {final_messages}")
        logger.info(f"[API] Types of messages in final_messages: {[type(m) for m in final_messages]}")
        # Добавь эту строку:
        logger.info(
            f"[API] Content of messages in final_messages: {[getattr(m, 'content', 'NO_CONTENT_ATTR') for m in final_messages]}")
    else:
        # Если что-то другое - ошибка
        logger.error(f"[API] Graph returned unexpected type: {type(result)}")
        return ChatResponse(
            response="Агент вернул неожиданный тип данных.",
            requires_clarification=False,
            thread_id=thread_id,
            status="error"
        )

    last_ai_message = [m for m in final_messages if isinstance(m, AIMessage)]
    if last_ai_message:
        response_text = last_ai_message[-1].content
        logger.info(f"[API] Generated response text: '{response_text[:100]}...'")
    else:
        response_text = "Агент не смог сгенерировать ответ."
        logger.warning(f"[API] No AIMessage found in final_messages. Returned default response.")

    # Удаляем файл после обработки (если был)
    if uploaded_file_path:
        cleanup_temp_file(uploaded_file_path)
        logger.info(f"[API] Cleaned up uploaded file: {uploaded_file_path}")

    return ChatResponse(
        response=response_text,
        requires_clarification=False,
        thread_id=thread_id,
        status="completed"
    )
