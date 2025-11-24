from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from pathlib import Path
import shutil

from backend.models import FileUploadResponse
from backend.rag_graph_advanced import load_and_index_all_documents, VECTOR_STORES

router = APIRouter()

UPLOAD_DIR = Path("data/documents")

class FileUploadResponse(BaseModel):
    filename: str
    status: str
    message: str

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not UPLOAD_DIR.exists():
        UPLOAD_DIR.mkdir(parents=True)

    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Перезагружаем индексы
    await load_and_index_all_documents()

    return FileUploadResponse(
        filename=file.filename,
        status="success",
        message=f"Файл {file.filename} загружен и проиндексирован."
    )