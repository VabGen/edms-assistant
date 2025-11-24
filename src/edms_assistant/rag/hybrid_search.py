# src/edms_assistant/rag/hybrid_search.py
import logging
from typing import List, Tuple, Dict, Any
from pathlib import Path
import pickle
import os

import numpy as np
from sklearn.preprocessing import MinMaxScaler
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from edms_assistant.core.settings import settings

logger = logging.getLogger(__name__)


class HybridSearch:
    def __init__(self, vector_store: FAISS, chunks: List[Document]):
        self.vector_store = vector_store
        self.chunks = chunks

        # Подготавливаем BM25
        tokenized_corpus = [
            self._tokenize(doc.page_content) for doc in chunks
        ]
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"✅ BM25 инициализирован для {len(chunks)} чанков")

    def _tokenize(self, text: str) -> List[str]:
        """Простая токенизация для русского языка"""
        # Удаляем пунктуацию и разбиваем на слова
        import re
        text = re.sub(r"[^\w\s]", " ", text.lower())
        return text.split()

    def search(
            self,
            query: str,
            k: int = 5,
            semantic_weight: float = 0.6,
            keyword_weight: float = 0.4
    ) -> List[Tuple[Document, float]]:
        """
        Возвращает список (документ, гибридный_скор), отсортированный по убыванию релевантности.
        """
        # 1. Semantic search (FAISS)
        semantic_results = self.vector_store.similarity_search_with_score(query, k=k * 2)
        # FAISS возвращает L2 distance → преобразуем в similarity: sim = 1 / (1 + dist)
        semantic_scores = {}
        for doc, dist in semantic_results:
            sim = 1.0 / (1.0 + dist)
            semantic_scores[id(doc)] = sim

        # 2. Keyword search (BM25)
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)

        # 3. Комбинируем
        combined = []
        for i, doc in enumerate(self.chunks):
            sem_score = semantic_scores.get(id(doc), 0.0)
            kw_score = bm25_scores[i]

            hybrid_score = semantic_weight * sem_score + keyword_weight * kw_score
            combined.append((doc, hybrid_score))

        combined.sort(key=lambda x: x[1], reverse=True)

        logger.debug(f"🔍 Гибридный поиск по запросу: {query}")
        for i, (doc, score) in enumerate(combined[:3]):
            logger.debug(f"  Топ-{i + 1} (score={score:.3f}): {doc.page_content[:80]}...")
        return combined[:k]