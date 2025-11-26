# src/edms_assistant/api/routes/files.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import shutil
from src.edms_assistant.rag.indexer import index_manager
from edms_assistant.core.settings import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не имеет имени")

    # Ограничение: 10 МБ
    if file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 10 МБ)")

    # Создаем директорию для загрузок
    upload_dir = Path(settings.paths.documents_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / file.filename
    try:
        # Сохраняем файл
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Индексируем
        await index_manager.index_single_file(str(file_path))

        return {
            "filename": file.filename,
            "status": "success",
            "loaded_files": list(index_manager.vector_stores.keys())
        }

    except Exception as e:
        # Удаляем файл при ошибке (без maybe_missing)
        if file_path.exists():
            file_path.unlink()
        logger.error(f"Ошибка индексации {file.filename}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось проиндексировать файл: {str(e)[:200]}..."
        )
