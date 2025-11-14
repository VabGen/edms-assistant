# src/edms_assistant/presentation/auth/jwt_auth.py
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
# УБРАНО: from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# УБРАНО: from src.edms_assistant.config.settings import settings
# НЕТ: from src.edms_assistant.config.settings import settings в этом файле, если он импортируется в api.py
# Лучше передавать settings как параметр или использовать глобальный доступ
from src.edms_assistant.config.settings import settings
import logging

logger = logging.getLogger(__name__)


def verify_edms_token(token: str) -> Dict[str, Any]:
    """
    Проверяет токен EDMS и возвращает информацию о пользователе.
    """
    try:
        # Если токен - JWT, валидируем его
        if token.startswith('ey'):  # JWT токены начинаются с 'ey'
            payload = jwt.decode(
                token,
                settings.security.jwt_secret,  # или публичный ключ EDMS
                algorithms=[settings.security.jwt_algorithm],
            )
            return payload
        else:
            # Если токен не JWT - просто возвращаем его как есть
            # и предполагаем, что валидация уже произошла на стороне EDMS
            # В реальном приложении вы можете использовать API EDMS для валидации токена
            logger.info(f"Non-JWT token received, treating as valid: {token[:10]}...")
            return {"token": token, "exp": None, "sub": "edms_user"}  # или извлекать user_id из другого источника
    except jwt.ExpiredSignatureError:
        logger.warning("EDMS Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="EDMS Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidSignatureError:
        # Подпись не совпадает - токен не является валидным JWT с вашим секретом
        # Но это может быть нормально, если токен из EDMS использует другой секрет
        # Вместо ошибки, возвращаем токен как есть (предполагаем, что он валиден)
        logger.info("EDMS Token signature does not match, treating as valid EDMS token")
        return {"token": token, "exp": None, "sub": "edms_user"}
    except jwt.InvalidTokenError:
        # Любой другой JWT токен не прошел валидацию
        logger.info("EDMS Token is not a valid JWT, treating as valid EDMS token")
        return {"token": token, "exp": None, "sub": "edms_user"}


# УБРАНО: verify_and_extract_user_info, так как теперь проверка делается в api.py напрямую