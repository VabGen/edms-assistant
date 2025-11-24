"""
EDMS Employee Client — асинхронный клиент для взаимодействия с EDMS API (сотрудники).
"""
import json

import httpx
from typing import Optional, Dict, Any, List
from uuid import UUID
from srccc.edms_assistant.core.settings import settings
from srccc.edms_assistant.utils.retry_utils import async_retry
from srccc.edms_assistant.utils.api_utils import (
    handle_api_error,
    prepare_auth_headers,
)
import logging

logger = logging.getLogger(__name__)


class EmployeeClient:
    """
    Асинхронный клиент для работы с EDMS Employee API (только сотрудники).

    Поддерживает:
    - Поиск сотрудников
    - Получение сотрудника по ID
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

    # === Сотрудники (возвращают JSON) ===
    async def search_employees(self, query: str, service_token: str) -> List[Dict[str, Any]]:
        """Инструмент для поиска сотрудников по запросу."""
        logger.info(f"Вызов find_responsible_tool с query: {query}")
        try:
            # Используем API клиент
            client = EmployeeClient()
            import asyncio
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(client.search_employees(query, service_token))
            return json.loads(result)
        except Exception as e:
            logger.error(f"Ошибка в find_responsible_tool: {e}")
            return json.dumps({"error": str(e)})

    async def get_employee_by_id(self, employee_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Получить сотрудника по ID. Возвращает JSON.
        """
        return await self._make_request("GET", f"api/employee/{employee_id}")
