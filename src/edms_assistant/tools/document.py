# src/edms_assistant/tools/document.py
from langchain_core.tools import tool
from typing import Optional
import json
import logging
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient

logger = logging.getLogger(__name__)


@tool
def get_document_tool(document_id: str, service_token: str) -> str:
    """Инструмент для получения информации о документе по ID."""
    logger.info(f"Вызов get_document_tool с document_id: {document_id}")
    try:
        client = DocumentClient()
        import asyncio
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(client.get_document(document_id, service_token))
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка в get_document_tool: {e}")
        return json.dumps({"error": str(e)})


@tool
def search_documents_tool(filters: dict, service_token: str) -> str:
    """Инструмент для поиска документов."""
    logger.info(f"Вызов search_documents_tool с filters: {filters}")
    try:
        client = DocumentClient()
        import asyncio
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(client.search_documents(filters, service_token))
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка в search_documents_tool: {e}")
        return json.dumps({"error": str(e)})
