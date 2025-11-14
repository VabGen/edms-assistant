# src/edms_assistant/config/db.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from src.edms_assistant.config.settings import settings


DATABASE_URL = settings.database.url # "postgresql+asyncpg://user:pass@localhost/dbname"

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_checkpointer():
    # Создаем checkpointer для LangGraph
    return AsyncPostgresSaver.from_conn_string(DATABASE_URL)