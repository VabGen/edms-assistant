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
    document_id: str = Field(..., description="UUID документа в EDMS.")
    service_token: str = Field(..., description="JWT-токен для авторизации в EDMS.")


class SearchDocumentsInput(BaseModel):
    query: Optional[str] = Field(None, description="Текст для поиска в документах.")
    doc_type: Optional[str] = Field(None, description="Тип документа для фильтрации.")
    status: Optional[str] = Field(None, description="Статус документа для фильтрации.")
    service_token: str = Field(..., description="JWT-токен для авторизации в EDMS.")


# @tool(
#     "get_document",
#     args_schema=GetDocumentInput,
#     # name_or_callable="get_document",
#     description="Получить документ по ID из EDMS. Возвращает сырой JSON-ответ от Java API в виде строки.",
# )
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
    args_schema=GetDocumentInput,
    name_or_callable="get_document",
    description="Получить документ по ID из EDMS. Возвращает сырой JSON-ответ от Java API в виде строки.",
)
async def get_document_tool(document_id: str, service_token: str) -> str:
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
