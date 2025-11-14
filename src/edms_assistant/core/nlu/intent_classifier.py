# src/edms_assistant/core/nlu/intent_classifier.py
import json
from typing import Dict, Any
from src.edms_assistant.infrastructure.llm.llm import get_llm


class IntentClassifier:
    """
    Классификатор намерений на основе LLM.
    """
    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    async def classify(self, message: str) -> Dict[str, Any]:
        """
        Классифицирует намерение пользователя и извлекает сущности.
        """
        system_prompt = f"""
        Ты - классификатор намерений для системы управления документами (EDMS).
        Твоя задача - определить намерение пользователя в сообщении и извлечь сущности.

        Возможные намерения:
        - find_employee: Поиск сотрудника (например, "найти Иванова", "кто ответственный за X")
        - get_document_info: Получить информацию о документе (например, "информация о документе 123")
        - search_documents: Поиск документов (например, "найти документы по контракту X")
        - analyze_attachment: Анализ вложения (например, "проанализируй загруженный файл")
        - unknown: Неизвестное намерение

        Сообщение пользователя: "{message}"

        Верни JSON в формате:
        {{
            "intent": "find_employee | get_document_info | search_documents | analyze_attachment | unknown",
            "confidence": 0.0-1.0,
            "entities": {{
                "employee_name": "...",
                "document_id": "...",
                "keyword": "..."
            }}
        }}
        """

        try:
            response = await self.llm.ainvoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ])

            response_content = str(response.content)
            # Парсим JSON ответа
            classification_data = json.loads(response_content)

            # Валидация
            required_keys = ["intent", "confidence", "entities"]
            if not all(key in classification_data for key in required_keys):
                raise ValueError("Invalid response format from LLM classifier")

            return classification_data

        except json.JSONDecodeError:
            # Если LLM не вернул JSON, используем резервный парсинг
            message_lower = message.lower()
            if "найти" in message_lower and "сотрудник" in message_lower:
                return {"intent": "find_employee", "confidence": 0.8, "entities": {}}
            elif "документ" in message_lower and ("info" in message_lower or "информация" in message_lower):
                return {"intent": "get_document_info", "confidence": 0.7, "entities": {}}
            elif "поиск" in message_lower and "документ" in message_lower:
                return {"intent": "search_documents", "confidence": 0.7, "entities": {}}
            elif "анализ" in message_lower and "файл" in message_lower:
                return {"intent": "analyze_attachment", "confidence": 0.8, "entities": {}}
            else:
                return {"intent": "unknown", "confidence": 0.5, "entities": {}}
        except Exception as e:
            # В случае ошибки, возвращаем "unknown"
            print(f"NLU classification error: {e}")
            return {"intent": "unknown", "confidence": 0.0, "entities": {}}


# Глобальный экземпляр
nlu_classifier = IntentClassifier()