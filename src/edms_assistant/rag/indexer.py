# src/edms_assistant/rag/indexer.py
import logging
import os
import pickle
from pathlib import Path
from typing import Dict, List, Optional
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from edms_assistant.core.settings import settings
from src.edms_assistant.rag.loader import get_loader

logger = logging.getLogger(__name__)


class IndexManager:
    def __init__(self):
        self.vector_stores: Dict[str, FAISS] = {}
        self.file_descriptions: Dict[str, str] = {}
        self._embeddings = None

    def get_embeddings(self):
        if self._embeddings is None:
            try:
                self._embeddings = OpenAIEmbeddings(
                    api_key="not-needed",
                    base_url=str(settings.vllm.embedding_base_url),
                    model=settings.vllm.embedding_model,
                )
            except:
                # Fallback на CPU
                from langchain_community.embeddings import HuggingFaceEmbeddings
                self._embeddings = HuggingFaceEmbeddings(model_name="cointegrated/rubert-tiny2")
        return self._embeddings

    async def index_single_file(self, file_path: str) -> str:
        filename = os.path.basename(file_path)
        store_dir = Path(settings.paths.vector_stores_dir) / Path(filename).stem
        store_dir.mkdir(parents=True, exist_ok=True)

        index_file = store_dir / "index.faiss"
        chunks_file = store_dir / "chunks.pkl"

        # Попытка загрузки
        if index_file.exists() and chunks_file.exists():
            try:
                vs = FAISS.load_local(store_dir, self.get_embeddings(), allow_dangerous_deserialization=True)
                with open(chunks_file, "rb") as f:
                    chunks = pickle.load(f)

                desc_path = store_dir / "description.txt"
                description = desc_path.read_text(encoding="utf-8") if desc_path.exists() else "Описание отсутствует"
                self.file_descriptions[filename] = description

                self.vector_stores[filename] = vs
                logger.info(f"✅ Загружен индекс: {filename}")
                return filename
            except Exception as e:
                logger.warning(f"⚠️ Пересоздаём индекс для {filename}: {e}")

        # Загрузка и обработка
        loader = get_loader(file_path)
        docs = loader.load()

        full_text = "\n".join(doc.page_content for doc in docs)
        description = " ".join(full_text[:300].split()) + "..."

        desc_path = store_dir / "description.txt"
        with open(desc_path, "w", encoding="utf-8") as f:
            f.write(description)

        cleaned_docs = []
        for doc in docs:
            if doc.metadata.get("type") == "table":
                text = doc.page_content.replace("\n", " | ").replace("  ", " ")
                cleaned_docs.append(
                    type(doc)(
                        page_content=f"Таблица из {filename}:\n{text}",
                        metadata={**doc.metadata, "source": filename, "type": "table"}
                    )
                )
            else:
                cleaned_docs.append(doc)
        docs = cleaned_docs

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap
        )
        chunks = splitter.split_documents(docs)

        with open(chunks_file, "wb") as f:
            pickle.dump(chunks, f)

        # === НОВАЯ BATCH-ИНДЕКСАЦИЯ ===
        logger.info(f"Индексация {len(chunks)} чанков пакетами по {settings.rag_embedding_batch_size}...")
        embeddings = self.get_embeddings()
        batch_size = getattr(settings, 'rag_embedding_batch_size', 5)

        # Создаём FAISS индекс по частям
        vs = None
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            if vs is None:
                vs = FAISS.from_documents(batch, embeddings)
            else:
                vs.add_documents(batch)
            logger.debug(f"  → Обработано чанков: {min(i + batch_size, len(chunks))}/{len(chunks)}")

        # Сохраняем индекс
        vs.save_local(store_dir)
        self.vector_stores[filename] = vs
        self.file_descriptions[filename] = description
        logger.info(f"✅ Проиндексирован: {filename}")
        return filename

    async def index_all_documents(self):
        docs_dir = Path(settings.paths.documents_dir)
        docs_dir.mkdir(parents=True, exist_ok=True)
        vector_dir = Path(settings.paths.vector_stores_dir)
        vector_dir.mkdir(parents=True, exist_ok=True)

        for item in docs_dir.iterdir():
            if item.is_file():
                try:
                    await self.index_single_file(str(item))
                except Exception as e:
                    logger.error(f"Ошибка индексации {item.name}: {e}")


# Единый экземпляр
index_manager = IndexManager()
index_all_documents = index_manager.index_all_documents
