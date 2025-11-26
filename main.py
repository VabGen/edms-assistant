import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from starlette.middleware.cors import CORSMiddleware

from edms_assistant.core.settings import settings
from src.edms_assistant.core.redis_client import redis_client
from src.edms_assistant.rag.indexer import index_all_documents

# Настройка логирования
logging.basicConfig(
    level=settings.logging_level,
    format=settings.logging_format or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск приложения...")
    try:
        await redis_client.connect()
    except Exception as e:
        logger.error(f"Ошибка подключения к Redis: {e}")
        if redis_client.enabled:
            raise
    await index_all_documents()
    yield
    await redis_client.disconnect()
    logger.info("Приложение остановлено.")


app = FastAPI(
    title="RAG Assistant",
    description="Интеллектуальный ассистент документооборота",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: ТОЛЬКО доверенные домены
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роуты
from src.edms_assistant.api.routes import chat, files

app.include_router(chat.router, prefix="/api/chat")
app.include_router(files.router, prefix="/api/files")


@app.get("/health")
async def health():
    from src.edms_assistant.rag.indexer import index_manager
    return {
        "status": "ok",
        "redis_enabled": redis_client.enabled,
        "loaded_files": list(index_manager.vector_stores.keys())
    }