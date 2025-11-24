# srccc/edms_assistant/utils/retry_utils.py
import asyncio
import logging
from functools import wraps
from typing import Callable, Type, Tuple

logger = logging.getLogger(__name__)


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Декоратор для выполнения асинхронной функции с повторными попытками.

    Args:
        max_attempts: Максимальное количество попыток.
        delay: Начальная задержка между попытками в секундах.
        backoff: Множитель для увеличения задержки после каждой неудачной попытки.
        exceptions: Кортеж типов исключений, при которых следует повторять попытку.
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {current_delay}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}. Last error: {e}"
                        )

            # Если все попытки исчерпаны, поднимаем последнее исключение
            raise last_exception

        return wrapper

    return decorator
