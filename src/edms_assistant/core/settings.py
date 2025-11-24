from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class VLLMConfig(BaseModel):
    generative_base_url: HttpUrl = Field(default="http://model-generative.shared.du.iba/v1")
    generative_model: str = Field(default="generative-model")
    embedding_base_url: HttpUrl = Field(default="http://model-embedding.shared.du.iba/v1")
    embedding_model: str = Field(default="embedding-model")
    api_key: str = Field(default="")

class RedisConfig(BaseModel):
    enabled: bool = Field(default=True)
    url: str = Field(default="redis://localhost:6379/0")

class PathsConfig(BaseModel):
    documents_dir: str = Field(default="data/documents")
    vector_stores_dir: str = Field(default="data/vector_stores")

class Settings(BaseSettings):
    vllm: VLLMConfig
    redis: RedisConfig
    paths: PathsConfig

    logging_level: str = Field(default="INFO")
    rag_batch_size: int = Field(default=10)
    rag_chunk_size: int = Field(default=500)
    rag_chunk_overlap: int = Field(default=100)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_nested_delimiter="__")

settings = Settings()