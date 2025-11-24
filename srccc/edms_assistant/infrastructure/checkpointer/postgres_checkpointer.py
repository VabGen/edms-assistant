# srccc/edms_assistant/infrastructure/checkpointer/postgres_checkpointer.py
from langgraph.checkpoint.memory import MemorySaver # Импортируем MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver # Пока оставим, на случай если заработает
from edms_assistant.core.settings import settings
import logging

logger = logging.getLogger(__name__)


def get_checkpointer():
    """
    Создает и возвращает экземпляр чекпоинтера.
    В проде используем AsyncPostgresSaver.
    Для локальной разработки можно использовать MemorySaver.
    """
    # --- ВРЕМЕННОЕ РЕШЕНИЕ: Используем MemorySaver если не удается инициализировать Postgres ---
    try:
        # Пробуем создать AsyncPostgresSaver
        checkpointer = AsyncPostgresSaver.from_conn_string(settings.database.url)
        logger.info("AsyncPostgresSaver initialized successfully.")
        return checkpointer
    except ImportError as e:
        # Если ошибка связана с отсутствием psycopg
        if "pq wrapper" in str(e) or "psycopg" in str(e):
            logger.warning(f"Failed to initialize AsyncPostgresSaver due to psycopg issue: {e}. Falling back to MemorySaver.")
            # Используем MemorySaver
            checkpointer = MemorySaver()
            logger.info("MemorySaver initialized as fallback.")
            return checkpointer
        else:
            # Если другая ошибка ImportError
            logger.error(f"Import error unrelated to psycopg: {e}")
            raise e # Пробрасываем, если это не проблема с psycopg
    except Exception as e:
        # Любая другая ошибка при инициализации (например, неверный URL)
        logger.error(f"Failed to initialize AsyncPostgresSaver: {e}")
        # Опционально: можно также попробовать MemorySaver как fallback для других ошибок
        # Но обычно, если URL неверный, это ошибка конфигурации.
        # Для демонстрации, снова попробуем MemorySaver
        logger.warning("Falling back to MemorySaver due to initialization error.")
        checkpointer = MemorySaver()
        logger.info("MemorySaver initialized as fallback after error.")
        return checkpointer

# global_checkpointer = get_checkpointer() # Не инициализируем сразу, а создаем при каждом вызове create_agent_graph