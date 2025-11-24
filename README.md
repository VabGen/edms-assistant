## Installation

uv pip install -r backend/requirements.txt

uv sync --extra dev

New-Item -ItemType Directory -Path "data/documents", "data/vector_stores", "data/cache", "data/redis" -Force

# Запускаем всё
docker-compose up --build

uv pip install faiss-cpu

set PYTHONPATH=src
uvicorn main:app --host 0.0.0.0 --port 8000 --reload