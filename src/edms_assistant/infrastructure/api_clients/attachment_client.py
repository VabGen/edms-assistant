"""
EDMS Attachment Client — асинхронный клиент для взаимодействия с EDMS API (вложения).
"""
import httpx
from typing import Optional, Dict, Any, List
from uuid import UUID
from src.edms_assistant.core.settings import settings
from src.edms_assistant.utils.retry_utils import async_retry
from src.edms_assistant.utils.api_utils import (
    handle_api_error,
    prepare_auth_headers,
)
import logging

logger = logging.getLogger(__name__)


class AttachmentClient:
    """
    Асинхронный клиент для работы с EDMS Attachment API (только вложения).

    Поддерживает:
    - Скачивание вложений
    - Получение списка вложений документа
    """

    def __init__(
            self,
            base_url: Optional[str] = None,
            timeout: Optional[int] = None,
            service_token: Optional[str] = None,
    ):
        resolved_base_url = base_url or str(settings.edms.base_url)
        self.base_url = resolved_base_url.rstrip("/")
        self.timeout = timeout or settings.edms.timeout
        self.service_token = service_token
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """Закрывает HTTP-клиент."""
        await self.client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        """Возвращает заголовки с авторизацией."""
        return prepare_auth_headers(self.service_token)

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(httpx.RequestError, httpx.HTTPStatusError),
    )
    async def _make_request(
            self,
            method: str,
            endpoint: str,
            **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Выполняет HTTP-запрос и возвращает JSON-ответ.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = kwargs.pop("headers", {}) or self._get_headers()

        try:
            response = await self.client.request(method, url, headers=headers, **kwargs)
            await handle_api_error(response, f"{method} {url}")
            return response.json() if response.content else {}
        except httpx.HTTPStatusError:
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {method} {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {method} {url}: {e}")
            return None

    # === Вложения (бинарные методы возвращают bytes) ===
    async def download_attachment(
            self, document_id: UUID, attachment_id: UUID
    ) -> Optional[bytes]:
        """
        Скачивает вложение документа как байты.
        """
        endpoint = f"api/document/{document_id}/attachment/{attachment_id}"
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()
        logger.debug(f"GET (binary) {url}")
        try:
            response = await self.client.get(url, headers=headers)
            await handle_api_error(response, f"GET (binary) {url}")
            return response.content
        except Exception as e:
            logger.error(f"Ошибка загрузки вложения {attachment_id}: {e}")
            return None

    # === Вложения (возвращают JSON) ===
    async def get_document_attachments(
            self, document_id: UUID
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Получить список вложений документа. Возвращает JSON (список).
        """
        return await self._make_request("GET", f"api/document/{document_id}/attachment")
