# src/edms_assistant/main.py

import asyncio
import logging
import uuid
from dotenv import load_dotenv
from src.edms_assistant.core.orchestrator.orchestrator import create_orchestrator_graph
from src.edms_assistant.config.settings import settings
from src.edms_assistant.utils.logging import setup_logging
from src.edms_assistant.core.state.global_state import GlobalState

load_dotenv()
setup_logging()

logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting EDMS Assistant with orchestrator...")

    graph = create_orchestrator_graph()

    user_uuid = uuid.uuid4()

    # Пример начального состояния
    initial_state: GlobalState = {
        "user_id": user_uuid,
        "service_token": settings.edms.service_token,  # из .env
        "user_message": "найди специалиста Иванов и добавь в документ",
        "messages": [{"role": "user", "content": "найди специалиста Иванов и добавь в документ"}],
        "document_id": "f38db809-afe8-11f0-82d9-6a58e1e2a181",
        "uploaded_file_path": None,
        "uploaded_file_name": None,
        # Поля, устанавливаемые orchestrator_planner
        "next_agent": None,
        "agent_input": {},
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

    config = {"configurable": {"thread_id": str(user_uuid)}}

    try:
        # Запускаем оркестратор с начальным состоянием
        result = await graph.ainvoke(initial_state, config=config)

        print("Final state keys:", list(result.keys()))
        last_message = result.get("messages", [])[-1] if result.get("messages") else None
        if last_message:
            content = getattr(last_message, "content", "Нет ответа.")
            print("Last message content:", content)
        else:
            print("No messages in result.")

        if "__interrupt__" in result:
            interrupt_data = result["__interrupt__"][0].value
            if interrupt_data.get("type") == "clarification":
                candidates = interrupt_data["candidates"]
                print("Candidates for clarification:")
                for i, c in enumerate(candidates):
                    print(f"  {i + 1}. {c['last_name']} {c['first_name']} {c['middle_name']} (ID: {c['id']})")

                selected_id = candidates[0]["id"]

                from langgraph.types import Command
                from langchain_core.messages import ToolMessage
                import json

                tool_msg = ToolMessage(
                    content=json.dumps({"id": selected_id}),
                    tool_call_id="mock"
                )

                resume_result = await graph.ainvoke({"messages": [tool_msg]}, config=config)
                print("Resume result:")
                last_msg_after_resume = resume_result.get("messages", [])[-1] if resume_result.get("messages") else None
                if last_msg_after_resume:
                    content_after_resume = getattr(last_msg_after_resume, "content", "Нет ответа.")
                    print("Last message after resume:", content_after_resume)
                else:
                    print("No messages after resume.")

    except Exception as e:
        logger.error(f"Orchestrator execution failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())