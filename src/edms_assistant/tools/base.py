# src/edms_assistant/tools/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict
from langchain_core.tools import BaseTool


class BaseEDMSTool(BaseTool, ABC):
    """Абстрактный базовый класс для всех инструментов EDMS."""

    name: str
    description: str
    # service_token будет передаваться как аргумент, не хранится в объекте инструмента

    @abstractmethod
    async def _arun(self, **kwargs: Any) -> Any:
        """Асинхронная реализация инструмента."""
        pass

    def _run(self, **kwargs: Any) -> Any:
        """Синхронная реализация инструмента (не используется в асинхронном агенте)."""
        raise NotImplementedError("Use async version `_arun` instead.")
