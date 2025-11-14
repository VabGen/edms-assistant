# src/edms_assistant/core/rag_retriever.py
from typing import List, Dict, Any
from src.edms_assistant.infrastructure.vector_store.pgvector_store import PGVectorStore
from src.edms_assistant.infrastructure.llm.llm import get_llm


class RAGRetriever:
    def __init__(self, vector_store: PGVectorStore = None):
        self.vector_store = vector_store or PGVectorStore()
        self.embedding_model = get_llm()

    async def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Поиск релевантных документов/фрагментов по запросу пользователя.
        """
        query_embedding = await self.embedding_model.embed_query(query)
        results = await self.vector_store.asimilarity_search_by_vector(query_embedding, k=top_k)
        # Преобразуем результаты в удобный формат
        return [{"content": doc.page_content, "metadata": doc.metadata} for doc in results]


rag_retriever = RAGRetriever()