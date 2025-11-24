import os
import logging
import pickle
from pathlib import Path
from typing import Dict, List
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from edms_assistant.core.settings import settings
from src.edms_assistant.rag.loader import get_loader

logger = logging.getLogger(__name__)

VECTOR_STORES: Dict[str, FAISS] = {}
CHUNKS_BY_FILE: Dict[str, List[Document]] = {}


def init_embeddings():
    return OpenAIEmbeddings(
        api_key="not-needed",
        base_url=str(settings.vllm.embedding_base_url),
        model=settings.vllm.embedding_model,
    )


async def index_single_file(file_path: str) -> str:
    filename = os.path.basename(file_path)
    embeddings = init_embeddings()

    store_dir = os.path.join(settings.paths.vector_stores_dir, Path(filename).stem)
    os.makedirs(store_dir, exist_ok=True)

    index_file = os.path.join(store_dir, "index.faiss")
    chunks_path = os.path.join(store_dir, "chunks.pkl")

    # Попытка загрузить существующий индекс И чанки
    if os.path.exists(index_file) and os.path.exists(chunks_path):
        try:
            vector_store = FAISS.load_local(
                store_dir, embeddings, allow_dangerous_deserialization=True
            )
            with open(chunks_path, "rb") as f:
                chunks = pickle.load(f)
            VECTOR_STORES[filename] = vector_store
            CHUNKS_BY_FILE[filename] = chunks
            logger.info(f"✅ Загружен индекс и чанки: {filename}")
            return filename
        except Exception as e:
            logger.warning(f"⚠️ Пересоздаём индекс для {filename}: {e}")

    # === Загрузка и индексация (если не загрузилось) ===
    loader = get_loader(file_path)
    docs = loader.load()

    cleaned_docs = []
    for doc in docs:
        if doc.metadata.get("type") == "table":
            table_text = doc.page_content.replace("\n", " | ").replace("  ", " ")
            cleaned_docs.append(
                type(doc)(
                    page_content=f"Таблица из {filename}:\n{table_text}",
                    metadata={**doc.metadata, "source": filename, "type": "table"}
                )
            )
        else:
            cleaned_docs.append(doc)
    docs = cleaned_docs

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap
    )
    split_docs = text_splitter.split_documents(docs)

    # Сохраняем чанки
    with open(chunks_path, "wb") as f:
        pickle.dump(split_docs, f)

    # Индексация FAISS
    vector_store = None
    for i in range(0, len(split_docs), settings.rag_batch_size):
        batch = split_docs[i:i + settings.rag_batch_size]
        if vector_store is None:
            vector_store = FAISS.from_documents(batch, embeddings)
        else:
            vector_store.add_documents(batch)

    if vector_store is None:
        raise RuntimeError(f"Не удалось создать индекс для {filename}")

    vector_store.save_local(store_dir)
    VECTOR_STORES[filename] = vector_store
    CHUNKS_BY_FILE[filename] = split_docs
    logger.info(f"✅ Проиндексирован и сохранены чанки: {filename}")
    return filename


async def index_all_documents():
    os.makedirs(settings.paths.documents_dir, exist_ok=True)
    os.makedirs(settings.paths.vector_stores_dir, exist_ok=True)

    for filename in os.listdir(settings.paths.documents_dir):
        file_path = os.path.join(settings.paths.documents_dir, filename)
        if os.path.isfile(file_path):
            try:
                await index_single_file(file_path)
            except Exception as e:
                logger.error(f"❌ Ошибка индексации {filename}: {e}")
