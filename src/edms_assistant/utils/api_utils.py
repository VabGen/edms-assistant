# src/edms_assistant/utils/api_utils.py
import uuid

import httpx
import logging
from typing import Optional, Dict, Any, List

from fastapi import HTTPException

logger = logging.getLogger(__name__)


# --- Обработка ошибок API ---
async def handle_api_error(response: httpx.Response, operation_name: str = "API call"):
    """
    Вспомогательная функция для обработки ошибок HTTP-ответа API.

    Args:
        response: Объект httpx.Response.
        operation_name: Имя операции для логирования.
    """
    if response.is_error:
        error_details = ""
        try:
            error_json = response.json()
            error_details = f" Error details: {error_json}"
        except Exception:
            # Если не удалось распарсить JSON, используем текст
            error_details = f" Error text: {response.text}"

        logger.error(
            f"{operation_name} failed with status {response.status_code}."
            f"{error_details}"
        )
        response.raise_for_status()  # Поднимает исключение httpx
    else:
        logger.debug(f"{operation_name} successful, status {response.status_code}.")


# --- Подготовка заголовков ---
def prepare_auth_headers(token: str) -> Dict[str, str]:
    """
    Подготавливает заголовки авторизации.

    Args:
        token: Токен аутентификации.

    Returns:
        Словарь заголовков.
    """
    return {"Authorization": f"Bearer {token}"}


# --- Валидация данных (простой пример) ---
def validate_document_data(data: Dict[str, Any]) -> bool:
    """
    Простая валидация данных документа перед отправкой в API.

    Args:
        data: Словарь с данными документа.

    Returns:
        True, если данные валидны, иначе False.
    """
    required_fields = ["name", "type"]
    for field in required_fields:
        if field not in data or not data[field]:
            logger.error(
                f"Validation failed: Missing or empty required field '{field}' in document data: {data}"
            )
            return False
    return True


# --- Валидация идентификатора документа ---
def validate_document_id(doc_id: Optional[str]) -> Optional[uuid.UUID]:
    if doc_id is None:
        return None
    try:
        return uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document_id format")


# --- функция для обработки paginated response ---
async def fetch_all_pages(
    client: httpx.AsyncClient,
    base_url: str,
    endpoint: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    page_param: str = "page",
    page_start: int = 0,
    size_param: str = "size",
    default_page_size: int = 20,
) -> List[Dict[str, Any]]:
    """
    Асинхронно извлекает все страницы paginated API-ответа.

    Поддерживает:
    - Начало с любой страницы (`page_start`)
    - Настройку имени параметров пагинации
    - Безопасную работу с параметрами (не мутирует входные данные)

    Args:
        client: Экземпляр httpx.AsyncClient.
        base_url: Базовый URL API (ожидается строка).
        endpoint: Конечная точка API.
        headers: Заголовки для запроса.
        params: Базовые параметры запроса (не должны содержать page/size, если не нужно).
        page_param: Имя параметра для номера страницы (по умолчанию "page").
        page_start: Стартовый номер страницы (обычно 0 или 1).
        size_param: Имя параметра размера страницы.
        default_page_size: Размер страницы, если не задан в params.

    Returns:
        Список всех элементов из всех страниц.
    """
    all_items = []
    base_params = params.copy() if params else {}

    if size_param not in base_params:
        base_params[size_param] = default_page_size

    page = page_start

    while True:
        request_params = {**base_params, page_param: page}
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        try:
            response = await client.get(url, headers=headers, params=request_params)
            await handle_api_error(response, f"Fetch {page_param}={page} of {endpoint}")
            data = response.json()

            items = data.get("content", [])
            if not items:
                items = data.get("items", [])
            if not items:
                items = data.get("results", [])

            total_pages = data.get("totalPages")
            total_elements = data.get("totalElements")

            all_items.extend(items)

            if not items:
                break

            if total_pages is not None:
                if page >= total_pages - 1:
                    break
            elif total_elements is not None:
                fetched = len(all_items)
                if fetched >= total_elements:
                    break
            else:
                if len(items) < base_params[size_param]:
                    break

            page += 1

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {page_param}={page} of {endpoint}: {e}")
            break
        except Exception as e:
            logger.error(
                f"Unexpected error fetching {page_param}={page} of {endpoint}: {e}"
            )
            break

    return all_items
