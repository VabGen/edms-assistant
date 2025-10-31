# src\edms_assistant\main.py
import asyncio
import logging
from dotenv import load_dotenv
from edms_assistant.infrastructure.llm.llm import get_llm
from langchain_core.messages import HumanMessage

# from edms_assistant.core.agent import create_agent_graph
from edms_assistant.config.settings import settings

# from edms_assistant.core.state import EDMSAgentState
from langgraph.types import Command

load_dotenv()

logging.basicConfig(level=getattr(logging, settings.logging_level))
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting EDMS Assistant.")

    try:
        llm = get_llm()
        logger.info("Invoking LLM with test prompt...")

        response = await llm.ainvoke("привет")
        logger.info("✅ LLM responded successfully.")
        print("\n--- LLM Response ---")
        print(response.content)
        print("--------------------\n")

    except Exception as e:
        logger.error(f"❌ LLM call failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
