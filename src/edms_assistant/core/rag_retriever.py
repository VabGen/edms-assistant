# src/edms_assistant/core/rag_retriever.py
from typing import List, Dict, Any, Optional
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS  # Используем FAISS
from langchain_core.documents import Document
from src.edms_assistant.core.settings import settings
from src.edms_assistant.core.document_indexer import DocumentIndexer
import logging

logger = logging.getLogger(__name__)

class RAGRetriever:
    """
    Класс для выполнения RAG (Retrieval-Augmented Generation).
    Поиск релевантных фрагментов текста из документов по запросу пользователя.
    Теперь использует FAISS.
    """
    def __init__(self, embeddings: Embeddings, indexer: Optional[DocumentIndexer] = None):
        self.embeddings = embeddings
        self.indexer = indexer or DocumentIndexer(self.embeddings)
        # Загружаем векторный индекс при инициализации
        self.vector_store: Optional[FAISS] = self.indexer.load_vector_store()
        if not self.vector_store:
            logger.warning(f"Векторный индекс по умолчанию не найден. Используется пустой индекс.")

    async def asearch(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Асинхронный поиск релевантных фрагментов по запросу.
        Возвращает список словарей с контентом и метаданными.
        """
        logger.info(f"RAG search for query: '{query[:50]}...' (top_k={top_k})")
        if not self.vector_store:
            logger.warning("Векторный индекс не загружен. Возвращаю пустой результат.")
            return []

        try:
            # Выполняем поиск
            documents = await self.vector_store.asimilarity_search(query, k=top_k)
            results = [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in documents
            ]
            logger.info(f"RAG search returned {len(results)} results.")
            return results
        except Exception as e:
            logger.error(f"Error during RAG search: {e}", exc_info=True)
            return []

# Глобальный экземпляр (опционально, можно создавать по требованию)
# rag_retriever = RAGRetriever()