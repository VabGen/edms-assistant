# src/edms_assistant/infrastructure/llm/llm.py
from gc import enable

from langchain_openai import ChatOpenAI
from edms_assistant.config.settings import settings
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
