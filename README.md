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