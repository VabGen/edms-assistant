# src/edms_assistant/agents/employee_agent.py
import re
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import interrupt
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.core.base_agent import BaseAgent
from src.edms_assistant.infrastructure.llm.llm import get_llm
from src.edms_assistant.tools.employee import (
    get_employee_by_id_tool,
    find_responsible_tool,
    add_responsible_to_document_tool
)
import json


class EmployeeAgent(BaseAgent):
    """Агент для работы с сотрудниками и персоналом"""

    def __init__(self, llm=None, tools=None):
        super().__init__(llm or get_llm(), tools)
        self.llm = llm or get_llm()
        # Добавляем инструменты
        self.add_tool(get_employee_by_id_tool)
        self.add_tool(find_responsible_tool)
        self.add_tool(add_responsible_to_document_tool)

    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        """Обработка запроса к сотрудникам"""
        try:
            user_message = state.user_message

            # Проверяем, является ли сообщение UUID сотрудника
            uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
            employee_ids = re.findall(uuid_pattern, user_message.lower())

            if employee_ids:
                # Если найден ID сотрудника - получаем информацию о нем
                employee_id = employee_ids[0]
                tool_input = {
                    "employee_id": employee_id,
                    "service_token": state.service_token
                }
                employee_result = await get_employee_by_id_tool.ainvoke(tool_input)
                return {
                    "messages": [HumanMessage(content=user_message), AIMessage(content=employee_result)],
                    "requires_execution": False,
                    "requires_clarification": False
                }

            # Проверяем, является ли сообщение числовым уточнением (например, "2")
            if user_message.strip().isdigit():
                selected_number = int(user_message.strip())

                # Проверяем, есть ли в состоянии предыдущий контекст уточнения
                if state.clarification_context:
                    candidates = state.clarification_context.get('candidates', [])
                    if candidates and 1 <= selected_number <= len(candidates):
                        selected_candidate = candidates[selected_number - 1]

                        # Получаем информацию о выбранном сотруднике
                        tool_input = {
                            "employee_id": selected_candidate["id"],
                            "service_token": state.service_token
                        }
                        employee_result = await get_employee_by_id_tool.ainvoke(tool_input)

                        return {
                            "messages": [HumanMessage(content=user_message), AIMessage(
                                content=f"Выбран сотрудник: {selected_candidate.get('first_name', '')} {selected_candidate.get('middle_name', '')} {selected_candidate.get('last_name', '')}\n{employee_result}"
                            )],
                            "requires_execution": False,
                            "requires_clarification": False
                        }

                # Если не удалось обработать выбор - возвращаем сообщение об ошибке
                return {
                    "messages": [HumanMessage(content=user_message), AIMessage(content="Пожалуйста, укажите корректный номер из списка.")],
                    "requires_execution": False,
                    "requires_clarification": False
                }

            # Проверяем, есть ли в сообщении запрос на поиск сотрудника
            search_keywords = ["найти", "поиск", "сотрудник", "человек", "ответственный", "работник"]
            if any(keyword in user_message.lower() for keyword in search_keywords):
                # Извлекаем компоненты имени с помощью LLM
                name_components = await self._extract_name_with_llm(user_message)

                if name_components and name_components.get("last_name"):
                    # Подготавливаем параметры для инструмента
                    tool_input = {
                        "last_name": name_components.get("last_name", ""),
                        "first_name": name_components.get("first_name", ""),
                        "service_token": state.service_token
                    }

                    # Убираем пустые значения, но оставляем хотя бы last_name
                    tool_input = {k: v for k, v in tool_input.items() if v}

                    search_result = await find_responsible_tool.ainvoke(tool_input)

                    # Парсим результат
                    try:
                        search_data = json.loads(search_result)

                        if "error" in search_data:
                            return {
                                "messages": [HumanMessage(content=user_message), AIMessage(content=f"Ошибка поиска: {search_data['error']}")],
                                "requires_execution": False,
                                "requires_clarification": False
                            }

                        # Проверяем, есть ли найденные сотрудники
                        if isinstance(search_data, list) and len(search_data) > 0:
                            # Если найдено несколько сотрудников - ВСЕГДА ВЫЗЫВАЕМ ПРЕРЫВАНИЕ LANGGRAPH
                            if len(search_data) > 1:
                                # ВАЖНО: ВСЕГДА вызываем interrupt() как в документации LangChain
                                return interrupt({
                                    "type": "clarification",
                                    "candidates": search_data,
                                    "original_query": name_components,
                                    "message": f"Найдено несколько сотрудников с фамилией {name_components.get('last_name', '')}. Пожалуйста, уточните, о ком именно вы спрашиваете."
                                })
                            else:
                                # Если найден один сотрудник - возвращаем его данные
                                employee_info = search_data[0]
                                full_name = f"{employee_info.get('last_name', '')} {employee_info.get('first_name', '')} {employee_info.get('middle_name', '')}".strip()
                                return {
                                    "messages": [HumanMessage(content=user_message), AIMessage(
                                        content=f"Найден сотрудник: {full_name}, ID: {employee_info.get('id')}"
                                    )],
                                    "requires_execution": False,
                                    "requires_clarification": False
                                }
                        else:
                            # Если ничего не найдено
                            query_desc = ", ".join([f"{k}: {v}" for k, v in name_components.items() if v])
                            return {
                                "messages": [HumanMessage(content=user_message), AIMessage(
                                    content=f"Сотрудников с параметрами '{query_desc}' не найдено."
                                )],
                                "requires_execution": False,
                                "requires_clarification": False
                            }
                    except json.JSONDecodeError:
                        return {
                            "messages": [HumanMessage(content=user_message), AIMessage(content=f"Ошибка обработки результата поиска: {search_result}")],
                            "requires_execution": False,
                            "requires_clarification": False
                        }
                else:
                    # Если не удалось извлечь имя, возвращаем сообщение о необходимости уточнения
                    return {
                        "messages": [HumanMessage(content=user_message)],
                        "requires_execution": False,
                        "requires_clarification": True,
                        "clarification_context": {
                            "type": "employee_search_needed",
                            "message": "Пожалуйста, укажите фамилию, имя или другую информацию для поиска сотрудника."
                        }
                    }

            # По умолчанию - возвращаем сообщение о необходимости уточнения
            return {
                "messages": [HumanMessage(content=user_message)],
                "requires_execution": False,
                "requires_clarification": True,
                "clarification_context": {
                    "type": "employee_search_needed",
                    "message": "Пожалуйста, уточните, кого именно вы ищете (фамилия, имя, должность и т.д.)."
                }
            }

        except Exception as e:
            # Обработка Interrupt исключений
            from langgraph.types import Interrupt
            if isinstance(e, Interrupt):
                # Это прерывание - возвращаем его как результат
                return interrupt(e.value)

            error_msg = f"Ошибка обработки сотрудника: {str(e)}"
            return {
                "messages": [HumanMessage(content=user_message), AIMessage(content=error_msg)],
                "requires_execution": False,
                "requires_clarification": False,
                "error": str(e)
            }

    async def _extract_name_with_llm(self, message: str) -> Dict[str, str]:
        """Использует LLM для извлечения компонентов имени из сообщения пользователя"""
        system_prompt = f"""
        Ты - ассистент для извлечения информации о сотруднике из сообщения пользователя.
        Твоя задача - извлечь фамилию, имя и отчество (если есть) из сообщения.

        Сообщение пользователя: "{message}"

        Верни JSON в формате:
        {{
            "last_name": "фамилия",
            "first_name": "имя", 
            "middle_name": "отчество"
        }}

        Если компонент не найден, используй пустую строку.
        Если в сообщении несколько возможных имен, выбери наиболее вероятное.
        """

        try:
            response = await self.llm.ainvoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ])

            response_content = str(response.content)
            # Парсим JSON ответа
            extracted_data = json.loads(response_content)

            # Убираем пустые значения
            return {k: v for k, v in extracted_data.items() if v}

        except Exception as e:
            # Если LLM не вернул JSON, пробуем простой парсинг
            import re
            search_keywords = ["найти", "поиск", "сотрудник", "человек", "ответственный", "работник", "искать"]
            message_lower = message.lower()

            for keyword in search_keywords:
                if keyword in message_lower:
                    pos = message_lower.find(keyword)
                    remaining = message[pos + len(keyword):].strip()
                    words = remaining.split()
                    for word in words:
                        if len(word) > 2 and word[0].isupper() and re.match(r'^[А-ЯЁ][а-яё]+', word):
                            return {"last_name": word}

            return {}
