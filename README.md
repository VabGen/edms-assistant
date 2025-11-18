## Installation
```bash
# Clone repository
git clone <repository-url>
cd edms-assistant

# Install uv if not already installed
pip install uv

# Install dependencies
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uv pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your configuration

# Показать помощь
edms-assistant --help

# Запустить индексацию (передав токен)
edms-assistant index --token your_edms_service_token

# Указать путь к индексу
edms-assistant index --token your_edms_service_token --path ./my_custom_index

# Проверить состояние
edms-assistant health