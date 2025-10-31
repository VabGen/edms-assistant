# src/edms_assistant/infrastructure/api_clients/document_client.py
"""
EDMS Document Client — асинхронный клиент для взаимодействия с EDMS API.

Все методы, кроме помеченных как бинарные, возвращают JSON-ответы (Dict[str, Any] или List[Dict]).
Бинарные методы возвращают bytes или AsyncIterator[bytes].
"""
import httpx
from typing import Optional, Dict, Any, List, AsyncIterator
from uuid import UUID
from src.edms_assistant.config.settings import settings
from src.edms_assistant.utils.retry_utils import async_retry
from src.edms_assistant.infrastructure.resources_openapi import DocumentDto
from src.edms_assistant.utils.api_utils import (
    handle_api_error,
    prepare_auth_headers,
)
import logging

logger = logging.getLogger(__name__)


class DocumentClient:
    """
    Асинхронный клиент для работы с EDMS Document API.

    Поддерживает:
    - Все CRUD-операции с документами
    - Работу с версиями, историей, адресатами, статусами
    - Выполнение операций (согласование, подписание и т.д.)
    - Загрузку файлов (бинарные методы)

    Безопасность:
    - service_token передаётся только в заголовках
    - Не сохраняется в логах или состоянии
    - Автоматические retry при временных ошибках
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

        Args:
            method: HTTP-метод (GET, POST, PUT и т.д.)
            endpoint: Путь эндпоинта (например, "api/document/123")
            **kwargs: Дополнительные параметры для httpx (json, params и т.д.)

        Returns:
            Dict[str, Any] — JSON-ответ от сервера, или {} если ответ пустой (например, 204 No Content)
            None — при необрабатываемой ошибке (не рекомендуется, лучше исключение)
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

    # === Документы (все методы возвращают JSON) ===
    # async def get_document(self, document_id: UUID) -> Optional[Dict[str, Any]]:
    #     """Получить документ по ID. Возвращает JSON."""
    #     return await self._make_request("GET", f"api/document/{document_id}")

    async def get_document(self, document_id: UUID) -> Optional[DocumentDto]:
        """Получить документ по ID. Возвращает типизированную модель."""
        data = await self._make_request("GET", f"api/document/{document_id}")
        if data is None:
            return None
        try:
            return DocumentDto(**data)
        except Exception as e:
            logger.error(f"Ошибка валидации документа {document_id}: {e}")
            return None

    async def create_document(self, profile_id: UUID) -> Optional[Dict[str, Any]]:
        """Создать новый документ. Возвращает JSON."""
        data = {"id": str(profile_id)}
        return await self._make_request("POST", "api/document", json=data)

    async def search_documents(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Поиск документов с фильтрацией. Возвращает JSON."""
        params = filters or {}
        return await self._make_request("GET", "api/document", params=params)

    # === Версии (все методы возвращают JSON) ===
    async def create_document_version(
        self, document_id: UUID, body: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Создать новую версию документа. Возвращает JSON."""
        return await self._make_request(
            "POST", f"api/document/{document_id}/version", json=body
        )

    async def get_all_versions(
        self, document_id: UUID
    ) -> Optional[List[Dict[str, Any]]]:
        """Получить все версии документа. Возвращает JSON (список)."""
        return await self._make_request("GET", f"api/document/{document_id}/version")

    # === История (возвращает JSON) ===
    async def get_document_history(self, document_id: UUID) -> Optional[Dict[str, Any]]:
        """Получить историю документа. Возвращает JSON."""
        return await self._make_request("GET", f"api/document/{document_id}/history/v2")

    # === Адресаты (возвращают JSON) ===
    async def get_document_recipients(
        self, document_id: UUID
    ) -> Optional[List[Dict[str, Any]]]:
        """Получить список адресатов документа. Возвращает JSON (список)."""
        return await self._make_request("GET", f"api/document/{document_id}/recipient")

    async def get_correspondents(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Получить список контрагентов. Возвращает JSON (список)."""
        params = filters or {}
        return await self._make_request("GET", "api/document/recipient", params=params)

    # === Статусы (возвращают JSON) ===
    async def get_document_statuses(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Получить статусы документов. Возвращает JSON (список)."""
        params = filters or {}
        return await self._make_request("GET", "api/document/status", params=params)

    async def get_status_groups(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Получить группировку по статусам. Возвращает JSON (список)."""
        params = filters or {}
        return await self._make_request(
            "GET", "api/document/status-group", params=params
        )

    # === Операции (возвращает JSON-совместимый результат) ===
    async def execute_document_operations(
        self, document_id: UUID, operations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Выполнить операции над документом (согласование, подписание и т.д.).
        EDMS возвращает 204 No Content, но метод адаптирует ответ к JSON.
        Всегда возвращает JSON.
        """
        try:
            result = await self._make_request(
                "POST", f"api/document/{document_id}/execute", json=operations
            )
            # Если в будущем EDMS начнёт возвращать тело — используем его
            if result is not None:
                return result
            # Для 204 No Content возвращаем стандартный успех
            return {"status": "success", "message": "Operations executed successfully"}
        except Exception as e:
            logger.error(f"Failed to execute operations on document {document_id}: {e}")
            return {"status": "error", "message": str(e)}

    # === Автор (возвращает JSON) ===
    async def change_document_author(
        self, document_id: UUID, new_author_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Изменить автора документа. Возвращает JSON."""
        data = {"id": str(new_author_id)}
        return await self._make_request(
            "PUT", f"api/document/{document_id}/change-document-author", json=data
        )

    # === Свойства (возвращает JSON) ===
    async def get_document_properties(
        self, document_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Получить свойства документа. Возвращает JSON."""
        return await self._make_request("GET", f"api/document/{document_id}/properties")

    # === Ответственные (договоры) (возвращают JSON) ===
    async def get_contract_responsibles(
        self, document_id: UUID
    ) -> Optional[List[Dict[str, Any]]]:
        """Получить ответственных по договору. Возвращает JSON (список)."""
        return await self._make_request(
            "GET", f"api/document/{document_id}/responsible"
        )

    async def get_contract_version_info(
        self, document_id: UUID
    ) -> Optional[List[Dict[str, Any]]]:
        """Получить информацию о версиях договора. Возвращает JSON (список)."""
        return await self._make_request(
            "GET", f"api/document/{document_id}/contract-version-info"
        )

    # === ФАЙЛОВЫЕ МЕТОДЫ (возвращают БАЙТЫ, НЕ JSON) ===
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


# # ------------------------------------------------------------------------------
#     async def download_attachment(
#             self, document_id: UUID, version_id: UUID, attach_id: UUID
#     ) -> Optional[bytes]:
#         """
#         Скачать вложение (файл) как байты.
#
#         ⚠️ Этот метод возвращает bytes, а не JSON!
#         Используйте только для загрузки файлов.
#
#         Returns:
#             bytes — содержимое файла, или None в случае ошибки.
#         """
#         endpoint = f"api/document/{document_id}/contract-version-info/{version_id}/attachment/{attach_id}/download"
#         url = f"{self.base_url}/{endpoint.lstrip('/')}"
#         headers = self._get_headers()
#         try:
#             response = await self.client.get(url, headers=headers)
#             await handle_api_error(response, f"GET (binary) {url}")
#             return response.content
#         except Exception as e:
#             logger.error(f"Failed to download attachment: {e}")
#             return None
#
#     async def stream_zip_attachment(
#             self, document_id: UUID, version_id: UUID
#     ) -> AsyncIterator[bytes]:
#         """
#         Потоковая загрузка ZIP-архива вложений.
#
#         ⚠️ Этот метод возвращает AsyncIterator[bytes], а не JSON!
#         Используйте только для потоковой загрузки файлов.
#
#         Yields:
#             bytes — фрагменты ZIP-файла.
#         """
#         endpoint = f"api/document/{document_id}/contract-version-info/{version_id}/attachment/zip/download-stream"
#         url = f"{self.base_url}/{endpoint.lstrip('/')}"
#         headers = self._get_headers()
#         async with self.client.stream("GET", url, headers=headers) as response:
#             await handle_api_error(response, f"STREAM (binary) {url}")
#             async for chunk in response.aiter_bytes():
#                 yield chunk
