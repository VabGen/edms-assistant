from fastapi import APIRouter, UploadFile, File
from pathlib import Path
import shutil
from src.edms_assistant.rag.indexer import index_single_file
from edms_assistant.core.settings import settings

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    upload_dir = Path(settings.paths.documents_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    await index_single_file(str(file_path))

    from src.edms_assistant.rag.indexer import VECTOR_STORES
    return {
        "filename": file.filename,
        "status": "success",
        "loaded_files": list(VECTOR_STORES.keys())
    }