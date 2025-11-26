import json
import logging
from typing import Optional, Any
from redis.asyncio import Redis
from edms_assistant.core.settings import settings

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self):
        self._client: Optional[Redis] = None
        self.enabled = settings.redis.enabled

    async def connect(self):
        if not self.enabled:
            logger.info("⚠️ Redis отключён")
            return
        try:
            self._client = Redis.from_url(settings.redis.url, decode_responses=True)
            await self._client.ping()
            logger.info(f"✅ Подключено к Redis: {settings.redis.url}")
        except Exception as e:
            logger.error(f"❌ Не удалось подключиться к Redis: {e}")
            self.enabled = False

    async def disconnect(self):
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Optional[Any]:
        if not self.enabled or not self._client:
            return None
        try:
            data = await self._client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"⚠️ Ошибка чтения из Redis ({key}): {e}")
            return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        if not self.enabled or not self._client:
            return
        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            await self._client.setex(key, expire, serialized)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка записи в Redis ({key}): {e}")
            logger.debug(f"Значение для записи: {value}")


redis_client = RedisClient()
