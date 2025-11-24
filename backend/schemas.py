from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class FileMetadata(BaseModel):
    filename: str
    size: int
    uploaded_at: datetime
    extension: str