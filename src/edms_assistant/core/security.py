from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer
from src.edms_assistant.config.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

# --- НОВАЯ ФУНКЦИЯ: Получение токена из запроса ---
async def get_token_from_request(request: Request) -> str:
    # Сначала пробуем получить токен из заголовка Authorization
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Убираем "Bearer "
        return token

    # Если в заголовке нет, пробуем получить из body (form-data)
    form_data = await request.form()
    token = form_data.get("edms_token")  # Имя поля, как в Swagger UI
    if token:
        return token

    # Если ни в одном месте не нашли
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token not found in header or form-data",
        headers={"WWW-Authenticate": "Bearer"},
    )

# --- Обновлённая функция verify_token ---
async def verify_token(request: Request = Depends(), token: str = Depends(get_token_from_request)):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token decode failed")