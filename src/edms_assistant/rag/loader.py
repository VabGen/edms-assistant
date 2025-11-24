from pathlib import Path
from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredExcelLoader,
)

def get_loader(file_path: str):
    ext = Path(file_path).suffix.lower().lstrip(".")
    if ext == "docx":
        return Docx2txtLoader(file_path)
    elif ext == "pdf":
        return PyPDFLoader(file_path)
    elif ext in ("txt", "md"):
        return TextLoader(file_path, encoding="utf-8")
    elif ext in ("xlsx", "xls"):
        return UnstructuredExcelLoader(file_path, mode="elements")
    else:
        raise ValueError(f"Формат .{ext} не поддерживается")