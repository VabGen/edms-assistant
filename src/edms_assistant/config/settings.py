# src/edms_assistant/config/settings.py
from pydantic import BaseModel, Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings
from typing import Optional, Literal
import uuid


class DatabaseConfig(BaseModel):
    url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/edms_assistant_db",
        description="Connection string for PostgreSQL database"
    )


class VLLMConfig(BaseModel):
    generative_base_url: HttpUrl = Field(
        default="http://model-generative.shared.du.iba/v1",
        description="Base URL for generative model API"
    )
    generative_model: str = Field(
        default="generative-model",  # Обновлено на актуальное имя
        description="Generative model identifier"
    )
    embedding_base_url: HttpUrl = Field(
        default="http://model-embedding.shared.du.iba/v1",
        description="Base URL for embedding model API"
    )
    embedding_model: str = Field(
        default="Qwen/Qwen3-Embedding-8B",
        description="Embedding model identifier"
    )
    api_key: str = Field(default="", description="API key for model access")


class EDMSConfig(BaseModel):
    base_url: HttpUrl = Field(
        default="http://127.0.0.1:8098",
        description="Base URL for EDMS API"
    )
    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Request timeout in seconds"
    )
    service_token: str = Field(
        ...,
        min_length=10,
        description="JWT token for EDMS authentication"
    )
    user_id: uuid.UUID = Field(
        ...,
        description="UUID of user in EDMS"
    )


class TelemetryConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable telemetry collection")
    endpoint: Optional[HttpUrl] = Field(
        default="http://127.0.0.1:8098",
        description="Telemetry endpoint URL"
    )

    @field_validator("enabled", mode="before")
    @classmethod
    def validate_enabled(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)


class SecurityConfig(BaseModel):
    jwt_secret: str = Field(..., description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_minutes: int = Field(default=60, description="JWT expiration in minutes")
    rbac_enabled: bool = Field(default=True, description="Enable Role-Based Access Control")


class Settings(BaseSettings):
    # LangSmith
    langsmith_api_key: Optional[str] = Field(default=None, description="LangSmith API key")
    langsmith_tracing: bool = Field(default=False, description="Enable LangSmith tracing")
    langsmith_project: str = Field(default="edms-agent", description="LangSmith project name")

    # vLLM
    vllm: VLLMConfig

    # EDMS
    edms: EDMSConfig

    # Security
    security: SecurityConfig

    # Database
    database: DatabaseConfig

    # Agent
    agent_enable_tracing: bool = Field(default=True, description="Enable agent tracing")
    agent_log_level: str = Field(default="INFO", description="Agent logging level")
    agent_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for agent operations"
    )

    # Logging
    logging_level: str = Field(default="INFO", description="Logging level")
    logging_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Logging format string"
    )

    # OpenAI
    max_tokens: int = Field(default=2048, description="Maximum tokens for LLM")
    telemetry: TelemetryConfig
    vllm_timeout: int = Field(
        default=120,
        ge=1,
        le=600,
        description="vLLM timeout in seconds"
    )
    llm_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="LLM temperature for generation"
    )

    # Storage & Checkpointing
    store_type: Literal["memory", "sqlite", "postgres"] = Field(
        default="memory",  # Для продакшена использовать postgres
        description="Type of state storage to use"
    )
    checkpointer_type: Literal["memory", "sqlite", "postgres"] = Field(
        default="memory",  # Для продакшена использовать postgres
        description="Type of checkpoint storage to use"
    )
    postgres_connection_string: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection string for persistent storage"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_nested_delimiter": "__",
        "extra": "ignore",
    }


settings = Settings()
