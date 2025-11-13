# src/edms_assistant/agents/main_planner_agent.py
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.core.base_agent import BaseAgent
from src.edms_assistant.infrastructure.llm.llm import get_llm
from src.edms_assistant.core.registry import agent_registry
import json
import logging


logger = logging.getLogger(__name__)


class MainPlannerAgent(BaseAgent):
    """Планирующий агент: анализирует запрос, формирует план, запускает агентов, собирает результаты"""

    def __init__(self, llm=None, tools=None):
        super().__init__(llm or get_llm(), tools)
        self.llm = llm or get_llm()

    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        """Основной процесс: планирование -> выполнение -> ответ"""
        try:
            user_message = state.user_message

            # Проверяем, является ли сообщение числовым уточнением (например, "2")
            if user_message.strip().isdigit() and state.clarification_context:
                # Это уточнение - передаем в employee_agent напрямую
                employee_agent = agent_registry.get_agent_instance("employee_agent")
                if employee_agent:
                    result = await employee_agent.process(state)
                    return result

            # Формируем план действий (если это не уточнение)
            plan = await self.plan_actions(state)

            # Выполняем план (запускаем агентов)
            results = await self.execute_plan(plan, state)

            # Формируем финальный ответ
            final_response = await self.generate_final_response(
                user_message, plan, results
            )

            return {
                "messages": [
                    HumanMessage(content=user_message),
                    AIMessage(content=final_response),
                ],
                "requires_execution": False,
                "requires_clarification": False,
                "plan": plan,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Ошибка планирования: {e}", exc_info=True)
            error_msg = f"Ошибка планирования: {str(e)}"
            return {
                "messages": [
                    HumanMessage(content=state.user_message),
                    AIMessage(content=error_msg),
                ],
                "requires_execution": False,
                "requires_clarification": False,
                "error": str(e),
            }

    async def plan_actions(self, state: GlobalState) -> Dict[str, Any]:
        """Формирует план действий на основе сообщения пользователя"""
        user_message = state.user_message

        system_prompt = f"""
        Ты - планирующий агент для системы управления документами.
        Проанализируй запрос пользователя и сформируй план действий.

        Запрос пользователя: "{user_message}"
        Контекст: 
        - document_id: {state.document_id}
        - uploaded_file_path: {state.uploaded_file_path}
        - user_id: {state.user_id}

        Доступные агенты:
        - document_agent: для работы с документами
        - employee_agent: для работы с сотрудниками  
        - attachment_agent: для работы с вложениями

        Верни JSON в формате:
        {{
            "actions": [
                {{
                    "agent": "имя_агента",
                    "action": "описание_действия",
                    "params": {{...}}  // дополнительные параметры для агента
                }}
            ],
            "reasoning": "обоснование выбора"
        }}
        """

        response = await self.llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
        )

        try:
            # Парсим JSON ответа
            response_content = str(response.content)
            plan = json.loads(response_content)
            return plan
        except json.JSONDecodeError:
            # Резервный парсинг если LLM не вернул чистый JSON
            if "document_agent" in response_content.lower():
                return {
                    "actions": [
                        {
                            "agent": "document_agent",
                            "action": "get_document_info",
                            "params": {},
                        }
                    ],
                    "reasoning": "Запрос связан с документом",
                }
            elif "employee_agent" in response_content.lower():
                return {
                    "actions": [
                        {
                            "agent": "employee_agent",
                            "action": "find_employee",
                            "params": {},
                        }
                    ],
                    "reasoning": "Запрос связан с сотрудником",
                }
            elif "attachment_agent" in response_content.lower():
                return {
                    "actions": [
                        {
                            "agent": "attachment_agent",
                            "action": "analyze_attachment",
                            "params": {},
                        }
                    ],
                    "reasoning": "Запрос связан с вложением",
                }
            else:
                return {
                    "actions": [
                        {
                            "agent": "document_agent",
                            "action": "get_document_info",
                            "params": {},
                        }
                    ],
                    "reasoning": "По умолчанию",
                }

    async def execute_plan(self, plan: Dict[str, Any], state: GlobalState) -> list:
        """Выполняет план действий - запускает агентов через registry"""
        results = []

        for action in plan.get("actions", []):
            agent_name = action["agent"]
            action_type = action["action"]
            params = action.get("params", {})

            # Получаем агента из registry
            agent = agent_registry.get_agent_instance(agent_name)
            if agent:
                try:
                    # Обновляем состояние с параметрами действия
                    action_state = state.model_copy(update=params)
                    result = await agent.process(action_state)

                    # Очищаем результат для JSON сериализации
                    cleaned_result = self._clean_result_for_json(result)
                    results.append(
                        {
                            "agent": agent_name,
                            "action": action_type,
                            "result": cleaned_result,
                            "success": True,
                        }
                    )
                except Exception as e:
                    results.append(
                        {
                            "agent": agent_name,
                            "action": action_type,
                            "result": {"error": str(e)},
                            "success": False,
                        }
                    )
            else:
                results.append(
                    {
                        "agent": agent_name,
                        "action": action_type,
                        "result": {"error": f"Агент {agent_name} не найден"},
                        "success": False,
                    }
                )

        return results

    async def generate_final_response(
        self, user_message: str, plan: Dict[str, Any], results: list
    ) -> str:
        """Формирует финальный ответ на основе результатов агентов"""
        system_prompt = f"""
        Ты - ассистент для управления документами.
        Пользователь спросил: "{user_message}"

        Был сформирован план:
        {json.dumps(plan, ensure_ascii=False, indent=2)}

        Результаты выполнения:
        {json.dumps(results, ensure_ascii=False, indent=2)}

        На основе этих данных сформируй понятный ответ для пользователя на русском языке.
        """

        response = await self.llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
        )

        return str(response.content)

    def _clean_result_for_json(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Очищает результат для JSON сериализации"""
        if not isinstance(result, dict):
            return {"raw_result": str(result)}

        cleaned = {}
        for key, value in result.items():
            if isinstance(value, (list, tuple)):
                cleaned[key] = []
                for item in value:
                    if hasattr(item, "content"):
                        # Это сообщение LangChain - извлекаем только содержимое
                        cleaned[key].append(str(item.content))
                    else:
                        cleaned[key].append(item)
            elif hasattr(value, "content"):
                # Это сообщение LangChain - извлекаем только содержимое
                cleaned[key] = str(value.content)
            elif isinstance(value, dict):
                cleaned[key] = self._clean_result_for_json(value)
            else:
                cleaned[key] = value
        return cleaned
