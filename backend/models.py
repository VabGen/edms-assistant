from pydantic import BaseModel
from typing import List, Optional

class User(BaseModel):
    id: int
    username: str
    email: str
    role: str

class Message(BaseModel):
    role: str
    content: str
    timestamp: str

class ChatSession(BaseModel):
    id: str
    user_id: int
    messages: List[Message]

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class FileUploadResponse(BaseModel):
    filename: str
    status: str
    message: str

class AuthRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: User