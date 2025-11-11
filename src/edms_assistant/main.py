# src/edms_assistant/main.py
import asyncio
import logging
from dotenv import load_dotenv
from src.edms_assistant.utils.logging import setup_logging
from src.edms_assistant.config.settings import settings
from src.edms_assistant.presentation.api import app

load_dotenv()
setup_logging()

logger = logging.getLogger(__name__)

async def initialize_agent():
    logger.info("Initializing EDMS Assistant Agent...")
    logger.info("EDMS Assistant Agent initialized.")

async def main():
    logger.info("Starting EDMS Assistant...")
    await initialize_agent()

if __name__ == "__main__":
    asyncio.run(main())