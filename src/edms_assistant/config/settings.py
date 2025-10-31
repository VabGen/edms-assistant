# src/edms_assistant/config/settings.py
from pydantic import BaseModel, Field, HttpUrl, PostgresDsn, field_validator
from pydantic_settings import BaseSettings
from typing import Optional
import uuid


class VLLMConfig(BaseModel):
    generative_base_url: HttpUrl = "http://model-generative.shared.du.iba/v1"
    generative_model: str = "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8"
    embedding_base_url: HttpUrl = "http://model-embedding.shared.du.iba/v1"
    embedding_model: str = "Qwen/Qwen3-Embedding-8B"
    api_key: str = ""


class EDMSConfig(BaseModel):
    base_url: HttpUrl = "http://127.0.0.1:8098"
    timeout: int = Field(30, ge=1, le=300)
    service_token: str = Field(..., min_length=10, description="JWT-токен для EDMS")
    user_id: uuid.UUID = Field(..., description="UUID пользователя в EDMS")


class TelemetryConfig(BaseModel):
    enabled: bool = True
    endpoint: Optional[HttpUrl] = "http://127.0.0.1:8098"

    @classmethod
    def _str_to_bool(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("enabled", mode="before")
    def validate_enabled(cls, v):
        return cls._str_to_bool(v)


class Settings(BaseSettings):
    # LangSmith
    langsmith_api_key: Optional[str] = None
    langsmith_tracing: bool = False
    langsmith_project: str = "edms-agent"

    # vLLM
    vllm: VLLMConfig

    # EDMS
    edms: EDMSConfig

    # Agent
    agent_enable_tracing: bool = True
    agent_log_level: str = "INFO"
    agent_max_retries: int = Field(3, ge=0, le=10)

    # Logging
    logging_level: str = "INFO"
    logging_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # OpenAI
    max_tokens: int = 2048
    telemetry: TelemetryConfig
    vllm_timeout: int = Field(120, ge=1, le=600)
    llm_temperature: float = Field(0.0, ge=0.0, le=1.0)

    # Storage & Checkpointing
    store_type: str = "memory"
    checkpointer_type: str = "postgres"
    checkpointer_postgres_url: PostgresDsn = Field(
        ..., description="PostgreSQL DSN для LangGraph Checkpointer"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_nested_delimiter": "__",
        "extra": "ignore",
    }


settings = Settings()
