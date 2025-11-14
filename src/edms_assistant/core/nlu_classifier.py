# src/edms_assistant/core/nlu_classifier.py
import json
from typing import Dict, Any
from src.edms_assistant.infrastructure.llm.llm import get_llm


class NLUClassifier:
    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    async def classify_intent(self, message: str) -> Dict[str, Any]:
        system_prompt = f"""
        Классифицируй намерение пользователя в системе управления документами (EDMS).
        Возможные намерения:
        - employee_search: Поиск сотрудника (например, "найти Иванова", "кто ответственный за X")
        - document_search: Поиск документа (например, "найти документ X", "где находится Y")
        - document_creation: Создание документа (например, "создай договор", "новый акт")
        - document_approval: Согласование документа (например, "подписать", "утвердить")
        - general_question: Общий вопрос (например, "что ты умеешь", "как дела")
        - unknown: Неизвестное намерение

        Сообщение пользователя: "{message}"

        Верни JSON:
        {{
            "intent": "employee_search | document_search | document_creation | document_approval | general_question | unknown",
            "confidence": 0.0-1.0,
            "entities": {{...}} // Извлеченные сущности (например, ID документа, имя сотрудника)
        }}
        """

        try:
            response = await self.llm.ainvoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ])
            return json.loads(str(response.content))
        except Exception as e:
            print(f"NLU classification error: {e}")
            return {"intent": "unknown", "confidence": 0.0, "entities": {}}


nlu_classifier = NLUClassifier()