# srccc/edms_assistant/core/nlu_classifier.py
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage as LC_HumanMessage, HumanMessage
from srccc.edms_assistant.infrastructure.llm.llm import get_llm
import json
import logging

logger = logging.getLogger(__name__)


class NLUClassifier:
    """
    Класс для классификации намерений пользователя.
    """

    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    async def classify_intent(self, user_message: str) -> Dict[str, Any]:
        """
        Определяет намерение пользователя с помощью LLM.
        Возвращает словарь с 'intent' и 'confidence'.
        """
        system_prompt = f"""
        Ты - помощник, который определяет намерение пользователя из его сообщения.
        Сообщение пользователя: "{user_message}"
        Доступные намерения:
        - find_employee
        - find_document
        - analyze_attachment
        - general_query
        - search_contract_terms
        Верни JSON в формате: {{"intent": "имя_намерения", "confidence": 0.95}}
        """
        try:
            response = await self.llm.ainvoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_message)])
            content_str = str(response.content)
            start = content_str.find('{')
            end = content_str.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = content_str[start:end]
                nlu_result = json.loads(json_str)
                logger.info(f"NLU classified '{user_message}' as {nlu_result}")
                return nlu_result
            else:
                logger.warning(f"NLU returned non-JSON: {content_str}")
                return {"intent": "general_query", "confidence": 0.5}
        except json.JSONDecodeError:
            logger.error(f"Failed to parse NLU response: {content_str}")
            return {"intent": "general_query", "confidence": 0.5}
        except Exception as e:
            logger.error(f"Error in NLU classification: {e}", exc_info=True)
            return {"intent": "general_query", "confidence": 0.5}
