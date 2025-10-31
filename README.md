# edms-assistant

## Описание
Данный микросервис является компонентом системы электронного документооборота АИС МВ.

## Установка
### - uv
pipx install uv

### Автоматическое добавление 'uv' в переменное окружения PATH
pipx ensurepath

### Выполните проверку
$env:PATH -split ';'

### Проверить версию 'uv'
uv --version

### Создаст pyproject.toml, если его нет, и uv.lock
uv init

uv venv
.venv\Scripts\activate  # (source .venv/Scripts/Activate.ps1)
uv pip install -e .

### Проверить зависимости
uv pip list | findstr pydantic

### 'uv' сам создаст venv (обычно .venv в корне проекта) и установит зависимости
uv sync --group dev
uv sync --all-extras --dev

## Подготовка llama-server
### Скачивание llama.cpp:
Клонируйте репозиторий: git clone https://github.com/ggerganov/llama.cpp.git
Перейдите в папку: cd llama.cpp

### Компиляция llama-server
mkdir build
cd build
cmake .. -DLLAMA_CUDA=ON -DLLAMA_SERVER=ON -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF ( dxdiag Откроется "Средство диагностики DirectX" )
cmake --build . --config Release --parallel 4

### Запуск сервера
Get-ChildItem -Path "D:\project\edms-ai-agent\llama.cpp" -Name
D:\project\edms-ai-agent\llama.cpp\build\bin\Release\llama-server.exe -m "D:\project\edms-ai-agent\models\Qwen3-4B-Instruct-2507\Qwen3-4B-Instruct-2507.Q5_K_M.gguf" -ngl 33 -c 4096 --port 8080
D:\project\edms-ai-agent\llama.cpp\build\bin\Release\llama-server.exe -m "D:\project\edms-ai-agent\models\Qwen3-4B-Instruct-2507\Qwen3-4B-Instruct-2507.Q5_K_M.gguf" -ngl 99 -c 2048 -t 8 --port 8080
--------
uv pip install openai


### Установка зависимостей из pyproject.toml
uv sync
uv pip install -e .         - установка в editable-режиме
uv pip install -e .[dev]    - с dev-зависимостями
uv pip install -e .[nlp]    - с дополнительной группой (если объявлена)
uv pip install              - установка зависимости по названию
uv add
uv add --group dev          - добавить в dev-группу

#### Запуск dev-зависимостей
ruff check .
black .
pytest

#### Удаление зависимостей
uv remove  
uv cache clean

### Полная переустановка
Remove-Item -Recurse -Force .venv
uv venv
.venv\Scripts\Activate.ps1
uv pip install -e .
#### Очистка кэша
Remove-Item -Recurse -Force src\edms_assistant\__pycache__
Remove-Item -Recurse -Force src\edms_assistant\config\__pycache__

### Обновить все зависимости
uv pip install -U -e .
uv sync --upgrade           # обновить по pyproject.toml + lock
uv lock --upgrade           # обновить все

## Точка входа для запуска uvicorn
uvicorn ai_agent.main:app --host 0.0.0.0 --port 8000 --reload

## Запуск
python run.py
python src/edms_assistant/main.py  