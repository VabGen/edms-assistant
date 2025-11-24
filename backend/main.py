from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uuid
from contextlib import asynccontextmanager

from backend.rag_graph_advanced import load_and_index_all_documents, VECTOR_STORES
from backend.models import ChatSession

# Серверный кэш чатов
chat_sessions = {}


# === Lifespan для замены deprecated @app.on_event("startup") ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Старт приложения
    print("🚀 Загрузка документов...")
    try:
        # Уменьшаем размер батча для предотвращения CUDA OOM
        await load_and_index_all_documents(
            batch_size=1,  # Критически важно для предотвращения OOM
            chunk_size=500,  # Меньше размер чанков
            chunk_overlap=100
        )
        print(f"✅ Загружено {len(VECTOR_STORES)} файлов")
    except Exception as e:
        print(f"❌ Ошибка при загрузке документов: {e}")
        print("⚠️ Приложение запускается без документов")
    yield
    # Завершение работы приложения (опционально)


app = FastAPI(
    title="EDMS AI Assistant",
    version="1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === ЗАГРУЖАЕМ РОУТЫ (после объявления `chat_sessions`) ===
from backend.routes import auth, files
from backend.routes import chat

# Передаем chat_sessions в модуль chat
chat.set_chat_sessions(chat_sessions)

# Подключаем роуты
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(files.router, prefix="/api/files", tags=["files"])


# Мониторинг
@app.get("/health")
def health():
    return {
        "status": "ok",
        "loaded_files": len(VECTOR_STORES),
        "files": list(VECTOR_STORES.keys())
    }


# Для раздачи статики (React)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os

# Путь к сборке React
frontend_build_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "build")

if os.path.exists(frontend_build_dir):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_build_dir, "assets")), name="static")


    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Раздача React-приложения для всех маршрутов"""
        if "." in full_path or full_path.startswith("api/"):
            # Если запрос к API или к файлу с расширением - не обрабатываем как страницу
            return None
        index_path = os.path.join(frontend_build_dir, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
else:
    print(f"⚠️ Директория сборки React не найдена: {frontend_build_dir}")
    print("💡 Запустите 'npm run build' в директории frontend для создания сборки")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)