# src/edms_assistant/tools/document.py
import json
import logging
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.edms_assistant.infrastructure.api_clients.document_client import DocumentClient
from src.edms_assistant.utils.api_utils import validate_document_id


logger = logging.getLogger(__name__)


class GetDocumentInput(BaseModel):
    document_id: str = Field(..., description="UUID документа в EDMS")
    service_token: str = Field(..., description="JWT-токен для авторизации в EDMS")


class SearchDocumentsInput(BaseModel):
    query: Optional[str] = Field(None, description="Текст для поиска в документах")
    doc_type: Optional[str] = Field(None, description="Тип документа для фильтрации")
    status: Optional[str] = Field(None, description="Статус документа для фильтрации")
    service_token: str = Field(..., description="JWT-токен для авторизации в EDMS")


class CreateDocumentInput(BaseModel):
    profile_id: str = Field(..., description="ID профиля документа для создания")
    service_token: str = Field(..., description="JWT-токен для авторизации в EDMS")


class UpdateDocumentInput(BaseModel):
    document_id: str = Field(..., description="UUID документа в EDMS")
    update_data: Dict[str, Any] = Field(
        ..., description="Данные для обновления документа"
    )
    service_token: str = Field(..., description="JWT-токен для авторизации в EDMS")


@tool(
    args_schema=GetDocumentInput,
    name_or_callable="get_document",
    description="Получить документ по ID из EDMS. Возвращает сырой JSON-ответ от Java API.",
)
async def get_document_tool(document_id: str, service_token: str) -> str:
    """Получить документ по ID из EDMS"""
    doc_uuid = validate_document_id(document_id)
    if doc_uuid is None:
        return json.dumps(
            {
                "error": "invalid_document_id",
                "message": f"Неверный формат ID документа: '{document_id}'.",
            }
        )

    try:
        async with DocumentClient(service_token=service_token) as client:
            doc_model = await client.get_document(doc_uuid)

        if doc_model is None:
            return json.dumps(
                {
                    "error": "document_not_found",
                    "message": f"Документ с ID {document_id} не найден.",
                }
            )

        return json.dumps(
            doc_model.model_dump(mode="json", exclude_unset=True), ensure_ascii=False
        )

    except Exception as e:
        logger.error(
            f"Ошибка при получении документа {document_id}: {e}", exc_info=True
        )
        return json.dumps(
            {"error": "api_error", "message": f"Не удалось получить документ: {str(e)}"}
        )


@tool(
    args_schema=SearchDocumentsInput,
    name_or_callable="search_documents",
    description="Поиск документов в EDMS. Возвращает список найденных документов.",
)
async def search_documents_tool(
    query: Optional[str] = None,
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    service_token: str = "",
) -> str:
    """Поиск документов в EDMS"""
    try:
        filters = {}
        if query:
            filters["query"] = query
        if doc_type:
            filters["type"] = doc_type
        if status:
            filters["status"] = status

        async with DocumentClient(service_token=service_token) as client:
            response = await client.search_documents(filters)

        if not response or "content" not in response:
            return json.dumps({"error": "Пустой ответ от EDMS"})

        return json.dumps(response["content"], ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка поиска документов: {e}", exc_info=True)
        return json.dumps({"error": f"Не удалось выполнить поиск: {str(e)}"})


@tool(
    args_schema=CreateDocumentInput,
    name_or_callable="create_document",
    description="Создать новый документ в EDMS. Возвращает информацию о созданном документе.",
)
async def create_document_tool(profile_id: str, service_token: str) -> str:
    """Создать новый документ в EDMS"""
    try:
        profile_uuid = validate_document_id(profile_id)
        if profile_uuid is None:
            return json.dumps(
                {
                    "error": "invalid_profile_id",
                    "message": f"Неверный формат ID профиля: '{profile_id}'.",
                }
            )

        async with DocumentClient(service_token=service_token) as client:
            response = await client.create_document(profile_uuid)

        if not response:
            return json.dumps({"error": "Не удалось создать документ"})

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка создания документа: {e}", exc_info=True)
        return json.dumps({"error": f"Не удалось создать документ: {str(e)}"})


@tool(
    args_schema=UpdateDocumentInput,
    name_or_callable="update_document",
    description="Обновить документ в EDMS. Возвращает информацию об обновленном документе.",
)
async def update_document_tool(
    document_id: str, update_data: Dict[str, Any], service_token: str
) -> str:
    """Обновить документ в EDMS"""
    doc_uuid = validate_document_id(document_id)
    if doc_uuid is None:
        return json.dumps(
            {
                "error": "invalid_document_id",
                "message": f"Неверный формат ID документа: '{document_id}'.",
            }
        )

    try:
        # В EDMS обновление обычно происходит через версии
        async with DocumentClient(service_token=service_token) as client:
            # Сначала получаем текущую версию
            current_doc = await client.get_document(doc_uuid)
            if not current_doc:
                return json.dumps({"error": "Документ не найден для обновления"})

            # Создаем новую версию с обновленными данными
            version_data = {"documentId": str(doc_uuid), "changes": update_data}
            response = await client.create_document_version(doc_uuid, version_data)

        if not response:
            return json.dumps({"error": "Не удалось обновить документ"})

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка обновления документа {document_id}: {e}", exc_info=True)
        return json.dumps({"error": f"Не удалось обновить документ: {str(e)}"})
