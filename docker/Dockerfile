# Используем официальный образ Python 3.14 (предполагая, что он существует или будет доступен)
# Если нет, используем 3.13 и укажем в requirements, что нужен 3.14+
FROM python:3.14-slim

# Устанавливаем uv
RUN pip install --no-cache-dir uv

# Устанавливаем системные зависимости (если нужны, например, для компиляции)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем pyproject.toml и uv.lock (или requirements.txt)
COPY ../pyproject.toml uv.lock ./

# Устанавливаем зависимости через pip из pyproject.toml
COPY ../src/edms_assistant .
RUN pip install --no-cache-dir .[dev] # или без [dev] для продакшена

# Копируем оставшийся код
COPY ../src/edms_assistant .

# Создаём пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Указываем команду запуска
CMD ["uvicorn", "src.edms_assistant.presentation.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]