# run.py
import logging
import uvicorn
from src.edms_assistant.presentation.api import app

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    # Установи уровень для uvicorn, если нужно
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")