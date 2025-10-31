# run.py
import logging
import os
import sys
import tempfile
import atexit
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

PROJECT_ROOT = Path(__file__).resolve().parent

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

UPLOAD_DIR = Path(tempfile.gettempdir()) / "edms_agent_uploads"


def cleanup_temp_dir():
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)
        UPLOAD_DIR.mkdir(exist_ok=True)


atexit.register(cleanup_temp_dir)

from edms_assistant.config.settings import settings
from edms_assistant.presentation.api import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "edms_assistant.presentation.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level=settings.logging_level.lower(),
    )
