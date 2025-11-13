# run.py
import logging
import os
import sys
import tempfile
import atexit
import shutil
from pathlib import Path
from dotenv import load_dotenv
from uvicorn import run as uvicorn_run
from src.edms_assistant.presentation.api import app
from src.edms_assistant.config.settings import settings

# Загрузка переменных окружения
load_dotenv()

# Создание директории для логов
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Настройка логирования с безопасностью
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/edms_assistant.log"),
        logging.StreamHandler()
    ]
)

# Настройка путей
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Создание временных директорий
UPLOAD_DIR = Path(tempfile.gettempdir()) / "edms_agent_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


# Функция очистки временных файлов
def cleanup_temp_dir():
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR, ignore_errors=True)


atexit.register(cleanup_temp_dir)

if __name__ == "__main__":
    print("Starting EDMS Assistant with universal interrupt system...")
    print(f"Security enabled: JWT, RBAC, parameter sanitization")
    print(f"API available at: http://127.0.0.1:8000")
    print(f"Health check: http://127.0.0.1:8000/health")
    print(f"Store type: {settings.store_type}")
    print(f"Checkpointer type: {settings.checkpointer_type}")

    if settings.checkpointer_type == "postgres":
        print(f"PostgreSQL connection: {settings.postgres_connection_string}")

    # Запуск приложения
    uvicorn_run(
        "src.edms_assistant.presentation.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level=settings.logging_level.lower(),
        workers=1,
        timeout_keep_alive=300,
        loop="asyncio",
        http="auto",
        forwarded_allow_ips="*",
        proxy_headers=True
    )