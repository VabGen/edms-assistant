# srccc/edms_assistant/agents/employee_agent.py
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from srccc.edms_assistant.agents.base_agent import BaseAgent
from srccc.edms_assistant.core.state import GlobalState
from srccc.edms_assistant.tools.employee import find_responsible_tool
from langgraph.types import interrupt
import json
import logging
import re

logger = logging.getLogger(__name__)

class EmployeeAgent(BaseAgent):
    def __init__(self, llm=None, agent_name: str = "employee_agent"):
        super().__init__(llm, agent_name)
        # Инструменты автоматически загружаются через BaseAgent и tool_registry

    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        user_message = state.user_message
        logger.info(
            f"[AGENT] EmployeeAgent.process: Received message: '{user_message[:50]}...', waiting_for_hitl_response: {state.waiting_for_hitl_response}")

        # --- Проверяем, ждём ли мы ответ на прерывание ---
        if state.waiting_for_hitl_response and user_message.isdigit():
            logger.info("[AGENT] EmployeeAgent: Handling HITL response.")
            choice_num = int(user_message)
            last_hitl_request = state.hitl_request
            if last_hitl_request and last_hitl_request.get("type") == "employee_selection":
                candidates = last_hitl_request.get("candidates", [])
                if 1 <= choice_num <= len(candidates):
                    selected_employee = candidates[choice_num - 1]
                    response_text = f"Выбран сотрудник: {selected_employee.get('first_name')} {selected_employee.get('last_name')} ({selected_employee.get('position')})."
                    return {
                        "messages": [HumanMessage(content=user_message), AIMessage(content=response_text)],
                        "waiting_for_hitl_response": False,
                        "hitl_request": None,
                        "requires_clarification": False,
                        "hitl_pending": False,
                    }
                else:
                    return {
                        "messages": [HumanMessage(content=user_message), AIMessage(content="Неверный номер. Пожалуйста, выберите из списка.")],
                        "requires_clarification": True,
                    }
            else:
                return {
                    "messages": [HumanMessage(content=user_message), AIMessage(content="Не ожидалось числовое сообщение. Пожалуйста, уточните запрос.")],
                    "requires_clarification": True
                }

        # --- Оригинальная логика ---
        try:
            name_parts = await self._extract_name_with_llm(user_message)
            search_query = f"{name_parts.get('first_name', '')} {name_parts.get('last_name', '')}".strip()

            if not search_query:
                logger.warning("[AGENT] EmployeeAgent: Could not extract name from message.")
                return {
                    "messages": [HumanMessage(content=user_message), AIMessage(
                        content="Не удалось извлечь имя сотрудника из сообщения. Пожалуйста, уточните.")],
                    "requires_clarification": True,
                }

            logger.info(f"[AGENT] EmployeeAgent: Searching for employees with query: '{search_query}'")
            search_result = await find_responsible_tool.ainvoke({
                "query": search_query,
                "service_token": state.service_token
            })

            logger.info(
                f"[AGENT] EmployeeAgent: Raw search result: {search_result[:200]}...")  # Логируем начало результата

            search_data = json.loads(search_result)
            logger.info(f"[AGENT] EmployeeAgent: Parsed search data: {search_data}")

            if isinstance(search_data, list) and len(search_data) > 0:
                if len(search_data) > 1:
                    logger.info(
                        f"[AGENT] EmployeeAgent: Found multiple employees ({len(search_data)}), triggering interrupt.")
                    candidates_list = "".join([
                        f"{i + 1}. {emp.get('first_name', '')} {emp.get('last_name', '')} ({emp.get('position', '')})\n"
                        for i, emp in enumerate(search_data)
                    ])
                    return interrupt({
                        "type": "employee_selection",
                        "candidates": search_data,
                        "message": f"В организации работает несколько человек с подходящими данными. Уточните, пожалуйста, о ком именно вы спрашиваете. Вот варианты:\n{candidates_list}Отправьте номер (например, '1', '2').",
                        "initiated_by_agent": "employee_agent"
                    })
                else:
                    logger.info(f"[AGENT] EmployeeAgent: Found single employee: {search_data[0]}")
                    employee_info = search_data[0]
                    response_text = f"Найден сотрудник: {employee_info.get('first_name')} {employee_info.get('last_name')} ({employee_info.get('position')})"
                    return {
                        "messages": [HumanMessage(content=user_message), AIMessage(content=response_text)],
                        "requires_clarification": False
                    }
            else:
                logger.info("[AGENT] EmployeeAgent: No employees found.")
                return {
                    "messages": [HumanMessage(content=user_message), AIMessage(content="Сотрудник не найден.")],
                    "requires_clarification": False
                }

        except Exception as e:
            logger.error(f"[AGENT] Ошибка обработки сотрудника: {e}", exc_info=True)
            error_msg = f"Ошибка обработки сотрудника: {str(e)}"
            return {
                "messages": [HumanMessage(content=user_message), AIMessage(content=error_msg)],
                "requires_clarification": False,
                "error": str(e)
            }

    async def _extract_name_with_llm(self, message: str) -> Dict[str, str]:
        from langchain_core.messages import SystemMessage, HumanMessage as LC_HumanMessage
        system_prompt = f"""
        Ты - помощник, который извлекает компоненты имени из сообщения пользователя.
        Извлекай только имя и фамилию, игнорируя другие слова.
        Возвращай JSON в формате: {{"first_name": "...", "last_name": "..."}}
        Если имя или фамилия не найдены, верни пустую строку для соответствующего поля.
        """
        response = await self.llm.ainvoke([SystemMessage(content=system_prompt), LC_HumanMessage(content=message)])
        try:
            content_str = str(response.content)
            start = content_str.find('{')
            end = content_str.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = content_str[start:end]
                extracted = json.loads(json_str)
                return extracted
            else:
                import re
                words = message.split()
                names = [word for word in words if len(word) > 2 and word[0].isupper() and re.match(r'^[А-ЯЁ][а-яё]+$', word, re.IGNORECASE)]
                if len(names) >= 2:
                    return {"first_name": names[0], "last_name": names[1]}
                elif len(names) == 1:
                    return {"last_name": names[0]}
                else:
                    return {}
        except json.JSONDecodeError:
            import re
            words = message.split()
            for word in words:
                if len(word) > 2 and word[0].isupper() and re.match(r'^[А-ЯЁ][а-яё]+$', word, re.IGNORECASE):
                    return {"last_name": word}
            return {}