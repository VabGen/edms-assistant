# src/edms_assistant/main.py
import asyncio
import logging
from dotenv import load_dotenv
from src.edms_assistant.core.orchestrator.orchestrator import create_orchestrator_graph
from src.edms_assistant.config.settings import settings
from src.edms_assistant.utils.logging import setup_logging

load_dotenv()
setup_logging()

logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting EDMS Assistant with orchestrator...")
    graph = create_orchestrator_graph()

    initial_state = {
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "service_token": settings.edms.service_token,
        "user_message": "Покажи документ с ID 123",
        "messages": [{"role": "user", "content": "Покажи документ с ID 123"}],
        "plan": None,
    }

    result = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": "test"}})
    print("Final state:", result)

if __name__ == "__main__":
    asyncio.run(main())