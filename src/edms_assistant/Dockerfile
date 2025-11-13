# Dockerfile
FROM python:3.13-slim

# Установка uv
RUN pip install uv

# Установка зависимостей системы
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование зависимостей
COPY pyproject.toml poetry.lock* ./

# Установка зависимостей через uv
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Установка приложения
RUN pip install -e .

EXPOSE 8000

CMD ["uvicorn", "src.edms_assistant.presentation.api:app", "--host", "0.0.0.0", "--port", "8000"]