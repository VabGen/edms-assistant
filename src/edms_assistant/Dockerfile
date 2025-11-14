FROM python:3.13-slim

RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN pip install uv && uv pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.edms_assistant.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]