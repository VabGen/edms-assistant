# src/edms_assistant/api/routes/files.py
from fastapi import APIRouter, UploadFile, File
from pathlib import Path
import shutil
from src.edms_assistant.rag.indexer import index_manager
from edms_assistant.core.settings import settings

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    upload_dir = Path(settings.paths.documents_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Вызываем метод у экземпляра
    await index_manager.index_single_file(str(file_path))
    return {
        "filename": file.filename,
        "status": "success",
        "loaded_files": list(index_manager.vector_stores.keys())
    }