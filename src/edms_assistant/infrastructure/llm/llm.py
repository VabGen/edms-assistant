# src/edms_assistant/infrastructure/llm/llm.py
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from src.edms_assistant.core.settings import settings
import logging

logger = logging.getLogger(__name__)


def get_llm() -> ChatOpenAI:
    logger.info(
        f"Initializing ChatOpenAI with model: {settings.vllm.generative_model} "
        f"at {settings.vllm.generative_base_url}"
    )

    if not settings.vllm.generative_model or not settings.vllm.generative_base_url:
        raise ValueError("Missing vLLM model or base URL in settings")

    llm = ChatOpenAI(
        api_key=settings.vllm.api_key or "not-needed",
        base_url=str(settings.vllm.generative_base_url),
        model=settings.vllm.generative_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.max_tokens,
        timeout=settings.vllm_timeout,
        max_retries=2,
    )
    logger.info(f"LLM initialized: {llm}")
    return llm

def get_embeddings() -> OpenAIEmbeddings:
    logger.info(
        f"Initializing OpenAIEmbeddings with model: {settings.vllm.embedding_model} "
        f"at {settings.vllm.embedding_base_url}"
    )

    if not settings.vllm.embedding_model or not settings.vllm.embedding_base_url:
        raise ValueError("Missing vLLM embedding model or base URL in settings")

    embeddings = OpenAIEmbeddings(
        api_key=settings.vllm.api_key or "not-needed",
        base_url=str(settings.vllm.embedding_base_url),
        model=settings.vllm.embedding_model,
        # timeout=settings.vllm_timeout, # OpenAIEmbeddings может не поддерживать timeout напрямую
        max_retries=2,
    )
    logger.info(f"Embeddings initialized: {embeddings}")
    return embeddings