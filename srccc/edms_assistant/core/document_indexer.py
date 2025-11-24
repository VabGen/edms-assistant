# srccc/edms_assistant/core/document_indexer.py
from typing import List, Dict, Any, Optional
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from srccc.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from srccc.edms_assistant.infrastructure.api_clients.attachment_client import AttachmentClient
from srccc.edms_assistant.core.settings import settings
import logging
import asyncio
import os

logger = logging.getLogger(__name__)

class DocumentIndexer:
    """
    Класс для индексации документов из EDMS в векторное хранилище (FAISS).
    """
    def __init__(self, embeddings: Embeddings, vector_store_path: str = "data/faiss_index"):
        self.embeddings = embeddings
        self.vector_store_path = vector_store_path
        # Используем EDMS Config из settings
        self.document_client = DocumentClient(base_url=str(settings.edms.base_url), timeout=settings.edms.timeout)
        self.attachment_client = AttachmentClient(base_url=str(settings.edms.base_url), timeout=settings.edms.timeout)

    async def index_all_documents(self, service_token: str):
        """
        Индексирует *все* доступные документы.
        В реальности, тут может быть фильтрация, пагинация, дельта-синхронизация.
        """
        logger.info("Начинаю индексацию всех документов...")
        try:
            # Получаем список всех документов (или пагинированный список)
            # document_list = await self.document_client.get_all_documents(service_token=service_token) # <-- РЕАЛЬНЫЙ ВЫЗОВ
            # Имитация получения документов
            document_list = await self._mock_get_all_documents(service_token)

            documents_to_index: List[Document] = []
            processed_count = 0
            for doc_info in document_list:
                doc_id = doc_info["id"]
                doc_title = doc_info.get("title", "Без названия")
                # Получаем *содержимое* документа
                content = await self._extract_content_from_document(doc_id, service_token)
                if content:
                    full_content = f"Документ: {doc_title}. Текст: {content}"
                    documents_to_index.append(Document(
                        page_content=full_content,
                        metadata={"source": f"document_{doc_id}", "title": doc_title, "id": doc_id}
                    ))
                    processed_count += 1
                    if processed_count % 10 == 0:  # Логируем прогресс
                        logger.info(f"Обработано {processed_count} документов...")
                else:
                    logger.warning(f"Не удалось извлечь контент для документа {doc_id}")

            if documents_to_index:
                logger.info(f"Индексирую {len(documents_to_index)} документов в FAISS...")
                # Создаём FAISS индекс
                vector_store = FAISS.from_documents(documents_to_index, self.embeddings)
                # Сохраняем индекс
                vector_store.save_local(self.vector_store_path)
                logger.info(f"Индекс успешно сохранён в {self.vector_store_path}")
            else:
                logger.warning("Нет документов для индексации.")

        except Exception as e:
            logger.error(f"Ошибка при индексации: {e}", exc_info=True)
            raise  # Передаём ошибку выше, чтобы CLI мог её перехватить

    async def _extract_content_from_document(self, doc_id: str, service_token: str) -> Optional[str]:
        """
        Извлекает текст из документа и его вложений.
        """
        try:
            # Получаем информацию о документе
            doc_data = await self.document_client.get_document(doc_id, service_token=service_token) # <-- РЕАЛЬНЫЙ ВЫЗОВ
            content_parts = []

            # Добавляем краткое содержание (если есть в API)
            # if doc_data.get("summary"):
            #     content_parts.append(doc_data["summary"])

            # Добавляем вложения
            attachments = doc_data.get("attachments", [])
            for att in attachments:
                att_id = att.get("id")
                att_name = att.get("name", "attachment")
                if att_id:
                    try:
                        # Получаем *байты* вложения
                        file_bytes = await self.attachment_client.download_attachment(doc_id, att_id, service_token=service_token) # <-- РЕАЛЬНЫЙ ВЫЗОВ
                        if file_bytes:
                            from srccc.edms_assistant.utils.file_utils import extract_text_from_bytes
                            text = extract_text_from_bytes(file_bytes, att_name)
                            if text:
                                content_parts.append(text)
                    except Exception as e:
                        logger.warning(f"Не удалось извлечь текст вложения {att_id}: {e}")

            return " ".join(content_parts)
        except Exception as e:
            logger.error(f"Ошибка при извлечении контента документа {doc_id}: {e}")
            return None

    async def _mock_get_all_documents(self, service_token: str) -> List[Dict[str, Any]]:
        """
        Имитация получения списка документов от API.
        В реальности, это будет вызов DocumentClient.
        """
        # В продакшене: return await self.document_client.get_all_documents(service_token=service_token)
        await asyncio.sleep(0.1)  # Имитация задержки
        return [
            {"id": "doc1", "title": "Договор поставки 2025", "summary": "Договор на поставку товаров"},
            {"id": "doc2", "title": "Положение об отделе ИТ", "summary": "Внутреннее положение"},
        ]

    def load_vector_store(self) -> Optional[FAISS]:
        """
        Загружает существующий векторный индекс.
        """
        if os.path.exists(self.vector_store_path):
            logger.info(f"Загружаю векторный индекс из {self.vector_store_path}")
            return FAISS.load_local(self.vector_store_path, self.embeddings, allow_dangerous_deserialization=True)
        else:
            logger.warning(f"Индекс {self.vector_store_path} не найден. Создайте его сначала.")
            return None