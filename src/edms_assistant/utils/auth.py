# src/edms_assistant/utils/auth.py
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Dict, Any
import jwt
from edms_assistant.core.settings import settings

security = HTTPBearer()


def verify_and_extract_user_info(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
    token = credentials.credentials
    try:
        # Декодируем токен (предполагаем, что он подписан тем же ключом, что и в EDMS)
        # В реальности, ты должен использовать публичный ключ от EDMS или вызывать /auth/validate
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user ID")
        return {"user_id": user_id, "token": token}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
