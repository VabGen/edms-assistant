# src/edms_assistant/rag/hybrid_search.py
import logging
from typing import List, Tuple
from pathlib import Path
import re

import numpy as np
from sklearn.preprocessing import MinMaxScaler
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

logger = logging.getLogger(__name__)


class HybridSearch:
    def __init__(self, vector_store: FAISS, chunks: List[Document]):
        self.vector_store = vector_store
        self.chunks = chunks

        # Подготавливаем BM25: токенизируем все чанки
        tokenized_corpus = [
            self._tokenize(doc.page_content) for doc in chunks
        ]
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"✅ BM25 инициализирован для {len(chunks)} чанков")

    def _tokenize(self, text: str) -> List[str]:
        """
        Простая токенизация для русского и английского текста.
        Удаляет пунктуацию, приводит к нижнему регистру, разбивает на слова.
        """
        # Удаляем всё, кроме букв, цифр и пробелов
        text = re.sub(r"[^а-яА-ЯёЁa-zA-Z0-9\s]", " ", text)
        # Приводим к нижнему регистру и разбиваем
        tokens = text.lower().split()
        return tokens

    def search(
        self,
        query: str,
        k: int = 5,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4
    ) -> List[Tuple[Document, float]]:
        """
        Выполняет гибридный поиск: комбинирует результаты FAISS (семантический поиск)
        и BM25 (по ключевым словам).

        Возвращает список кортежей (документ, гибридный_скор), отсортированный по убыванию релевантности.
        """
        # === 1. Семантический поиск (FAISS) ===
        # FAISS возвращает L2-дистанцию: чем меньше — тем ближе
        semantic_results = self.vector_store.similarity_search_with_score(query, k=k * 2)

        # Преобразуем дистанцию в схожесть: similarity = 1 / (1 + dist)
        semantic_scores = {}
        for doc, dist in semantic_results:
            similarity = 1.0 / (1.0 + float(dist))
            semantic_scores[id(doc)] = similarity

        # === 2. Поиск по ключевым словам (BM25) ===
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)

        # === 3. Комбинируем скоры ===
        combined = []
        for i, doc in enumerate(self.chunks):
            sem_score = semantic_scores.get(id(doc), 0.0)
            kw_score = float(bm25_scores[i])

            # Взвешенная сумма
            hybrid_score = semantic_weight * sem_score + keyword_weight * kw_score
            combined.append((doc, hybrid_score))

        # Сортируем по убыванию гибридного скоринга
        combined.sort(key=lambda x: x[1], reverse=True)
        return combined[:k]