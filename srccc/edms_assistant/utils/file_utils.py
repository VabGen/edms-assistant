# srccc/edms_assistant/utils/file_utils.py
import io
from typing import Optional
import logging
from pathlib import Path
import tempfile
import shutil
from fastapi import UploadFile

logger = logging.getLogger(__name__)

try:
    import docx2txt
    from PyPDF2 import PdfReader
except ImportError:
    logger.warning("Не удалось импортировать модули doc и PyPDF2")
    docx2txt = None
    PdfReader = None


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> Optional[str]:
    """
    Извлекает текст из байтов файла (поддержка .docx, .pdf, .txt).
    """
    try:
        file_stream = io.BytesIO(file_bytes)
        ext = filename.lower().split(".")[-1] if "." in filename else ""

        if ext == "pdf" and PdfReader:
            reader = PdfReader(file_stream)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text.strip()

        elif ext == "docx" and docx2txt:
            return docx2txt.process(file_stream)

        elif ext == "txt":
            return file_bytes.decode("utf-8", errors="ignore").strip()

        else:
            logger.warning(f"Неподдерживаемый формат файла: {ext}")
            return None

    except Exception as e:
        logger.error(f"Ошибка извлечения текста из {filename}: {e}")
        return None


async def save_uploaded_file(file: UploadFile) -> str:
    """
    Сохраняет загруженный файл во временный каталог
    """
    try:
        # Создаем временный файл
        temp_dir = Path(tempfile.gettempdir()) / "edms_agent_uploads"
        temp_dir.mkdir(exist_ok=True)

        # Генерируем уникальное имя файла
        import uuid

        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = temp_dir / unique_filename

        # Сохраняем файл
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return str(file_path)
    except Exception as e:
        logger.error(f"Ошибка сохранения загруженного файла: {e}")
        raise


def cleanup_temp_file(file_path: str):
    """
    Удаляет временный файл
    """
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception as e:
        logger.error(f"Ошибка удаления временного файла {file_path}: {e}")


def validate_file_type(filename: str) -> bool:
    """
    Проверяет, поддерживается ли тип файла
    """
    supported_extensions = {".pdf", ".docx", ".txt", ".doc", ".rtf", ".odt"}
    ext = Path(filename).suffix.lower()
    return ext in supported_extensions
