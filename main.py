import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

from starlette.middleware.cors import CORSMiddleware

from edms_assistant.core.settings import settings
from src.edms_assistant.rag.indexer import index_all_documents
from src.edms_assistant.core.redis_client import redis_client

logging.basicConfig(level=settings.logging_level)

from edms_assistant.core.settings import settings
print("Redis URL:", settings.redis.url)
print("Documents dir:", settings.paths.documents_dir)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_client.connect()
    await index_all_documents()
    yield
    await redis_client.disconnect()

app = FastAPI(lifespan=lifespan, title="RAG Test Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.edms_assistant.api.routes import chat, files
app.include_router(chat.router, prefix="/api/chat")
app.include_router(files.router, prefix="/api/files")

@app.get("/health")
def health():
    from src.edms_assistant.rag.indexer import VECTOR_STORES
    return {
        "status": "ok",
        "redis_enabled": redis_client.enabled,
        "loaded_files": list(VECTOR_STORES.keys())
    }