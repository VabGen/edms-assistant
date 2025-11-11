from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.core.registry import BaseAgent, agent_registry
from src.edms_assistant.infrastructure.llm.llm import get_llm
import json


class MainPlannerAgent(BaseAgent):
    """Планирующий агент: анализирует запрос, формирует план, запускает агентов, собирает результаты"""

    def __init__(self):
        super().__init__()
        self.llm = get_llm()
        self.tools = []

    def _clean_result_for_json(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Очищает результат для JSON сериализации"""
        if not isinstance(result, dict):
            return {"raw_result": str(result)}

        cleaned = {}
        for key, value in result.items():
            if isinstance(value, (list, tuple)):
                cleaned[key] = []
                for item in value:
                    if hasattr(item, 'content'):
                        # Это сообщение LangChain - извлекаем только содержимое
                        cleaned[key].append(str(item.content))
                    else:
                        cleaned[key].append(item)
            elif hasattr(value, 'content'):
                # Это сообщение LangChain - извлекаем только содержимое
                cleaned[key] = str(value.content)
            elif isinstance(value, dict):
                cleaned[key] = self._clean_result_for_json(value)
            else:
                cleaned[key] = value
        return cleaned

    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        """Основной процесс: проверяем уточнение -> планирование -> выполнение -> ответ"""
        try:
            user_message = state.user_message

            # ПРОВЕРКА: если есть предыдущий контекст уточнения, обрабатываем его
            if state.clarification_context:
                clarification_type = state.clarification_context.get("type")

                # Если это выбор сотрудника и сообщение - число
                if clarification_type == "employee_selection" and user_message.strip().isdigit():
                    # Это уточнение - передаем в employee_agent напрямую
                    employee_agent = agent_registry.get_agent_instance("employee_agent")
                    if employee_agent:
                        result = await employee_agent.process(state, **kwargs)
                        return result

            # 1. Формируем план действий (если нет уточнения)
            plan = await self.plan_actions(state)

            # 2. Выполняем план (запускаем агентов)
            results = await self.execute_plan(plan, state)

            # Проверяем, есть ли результаты с уточнением
            for result in results:
                if result.get("requires_clarification", False):
                    clarification_context = result.get("clarification_context", {})
                    # ВАЖНО: возвращаем результат с уточнением, а не формируем ответ через LLM
                    return {
                        "messages": [HumanMessage(content=user_message)],
                        "requires_execution": False,
                        "requires_clarification": True,
                        "clarification_context": clarification_context,
                        "plan": plan,
                        "results": result
                    }

            # 3. Формируем финальный ответ
            final_response = await self.generate_final_response(user_message, plan, results)

            return {
                "messages": [HumanMessage(content=user_message),
                             AIMessage(content=final_response)],
                "requires_execution": False,
                "requires_clarification": False,
                "plan": plan,
                "results": results
            }

        except Exception as e:
            error_msg = f"Ошибка планирования: {str(e)}"
            return {
                "messages": [HumanMessage(content=state.user_message),
                             AIMessage(content=error_msg)],
                "requires_execution": False,
                "requires_clarification": False,
                "error": str(e)
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

        response = await self.llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])

        try:
            # Парсим JSON ответа
            response_content = str(response.content)
            plan = json.loads(response_content)
            return plan
        except json.JSONDecodeError:
            # Резервный парсинг если LLM не вернул чистый JSON
            if "document_agent" in response_content.lower():
                return {
                    "actions": [{"agent": "document_agent", "action": "get_document_info", "params": {}}],
                    "reasoning": "Запрос связан с документом"
                }
            elif "employee_agent" in response_content.lower():
                return {
                    "actions": [{"agent": "employee_agent", "action": "find_employee", "params": {}}],
                    "reasoning": "Запрос связан с сотрудником"
                }
            elif "attachment_agent" in response_content.lower():
                return {
                    "actions": [{"agent": "attachment_agent", "action": "analyze_attachment", "params": {}}],
                    "reasoning": "Запрос связан с вложением"
                }
            else:
                return {
                    "actions": [{"agent": "document_agent", "action": "get_document_info", "params": {}}],
                    "reasoning": "По умолчанию"
                }

    async def execute_plan(self, plan: Dict[str, Any], state: GlobalState) -> List[Dict[str, Any]]:
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
                    # Обновляем состояние, если нужно
                    result = await agent.process(state)

                    # Проверяем, требует ли результат уточнения
                    if result.get("requires_clarification", False):
                        # Если агент требует уточнения - возвращаем это сразу
                        return [{
                            "agent": agent_name,
                            "action": action_type,
                            "result": self._clean_result_for_json(result),
                            "requires_clarification": True,
                            "clarification_context": result.get("clarification_context")
                        }]

                    # Очищаем результат для JSON сериализации
                    cleaned_result = self._clean_result_for_json(result)
                    results.append({
                        "agent": agent_name,
                        "action": action_type,
                        "result": cleaned_result,
                        "success": True
                    })
                except Exception as e:
                    results.append({
                        "agent": agent_name,
                        "action": action_type,
                        "result": {"error": str(e)},
                        "success": False
                    })
            else:
                results.append({
                    "agent": agent_name,
                    "action": action_type,
                    "result": {"error": f"Агент {agent_name} не найден"},
                    "success": False
                })

        return results

    async def generate_final_response(self, user_message: str, plan: Dict[str, Any],
                                      results: List[Dict[str, Any]]) -> str:
        """Формирует финальный ответ на основе результатов агентов"""
        # Проверяем, есть ли результаты с уточнением
        for result in results:
            if result.get("requires_clarification", False):
                clarification_context = result.get("clarification_context", {})
                if clarification_context:
                    # Формируем ответ с уточнением
                    if clarification_context.get("type") == "employee_selection":
                        candidates = clarification_context.get("candidates", [])
                        if candidates:
                            candidates_list = "\n".join([
                                f"{i + 1}. {cand.get('first_name', '')} {cand.get('middle_name', '')} {cand.get('last_name', '')}"
                                for i, cand in enumerate(candidates)
                            ])
                            return f"Найдено несколько сотрудников с фамилией Иванов. Пожалуйста, уточните, о ком именно вы спрашиваете:\n\n{candidates_list}"

                    # Возвращаем сообщение из clarification_context
                    return clarification_context.get("message", "Требуется уточнение")

        system_prompt = f"""
        Ты - ассистент для управления документами.
        Пользователь спросил: "{user_message}"

        Был сформирован план:
        {json.dumps(plan, ensure_ascii=False, indent=2)}

        Результаты выполнения:
        {json.dumps(results, ensure_ascii=False, indent=2)}

        На основе этих данных сформируй понятный ответ для пользователя на русском языке.
        """

        response = await self.llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])

        return str(response.content)