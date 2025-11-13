# src/edms_assistant/core/middleware/hitl_middleware.py
from typing import Dict, Any, List, Optional, Union
from langchain_core.tools import BaseTool
from langgraph.types import interrupt
from langchain.agents import AgentState
import logging


class HumanInTheLoopMiddleware:
    """
    Middleware для Human-in-the-Loop интеграции с LangGraph
    Позволяет приостанавливать выполнение и ожидать решения пользователя
    """

    def __init__(
        self,
        interrupt_on: Dict[str, Union[bool, Dict[str, Any]]],
        description_prefix: str = "Tool execution pending approval",
        checkpointer: Optional[Any] = None,
    ):
        """
        Args:
            interrupt_on: Словарь инструментов и политик прерываний
            description_prefix: Префикс для сообщений прерываний
            checkpointer: Чекпоинтер для сохранения состояния
        """
        self.interrupt_on = interrupt_on
        self.description_prefix = description_prefix
        self.checkpointer = checkpointer
        self.logger = logging.getLogger(self.__class__.__name__)

    def should_interrupt(self, tool_name: str, tool_args: Dict[str, Any]) -> bool:
        """Проверяет, нужно ли прерывать выполнение для инструмента"""
        policy = self.interrupt_on.get(tool_name)

        if policy is None:
            return False
        elif policy is True:
            return True
        elif isinstance(policy, dict):
            return True
        else:
            return bool(policy)

    def get_allowed_decisions(self, tool_name: str) -> List[str]:
        """Получает разрешенные решения для инструмента"""
        policy = self.interrupt_on.get(tool_name)

        if policy is True:
            return ["approve", "edit", "reject"]
        elif isinstance(policy, dict):
            return policy.get("allowed_decisions", ["approve", "edit", "reject"])
        else:
            return []

    async def process_tool_call(
        self, tool_name: str, tool_args: Dict[str, Any], agent_state: Any
    ) -> Dict[str, Any]:
        """Обрабатывает вызов инструмента с проверкой прерываний"""

        if self.should_interrupt(tool_name, tool_args):
            # Формируем запрос HITL
            hitl_request = {
                "action_requests": [
                    {
                        "name": tool_name,
                        "arguments": tool_args,
                        "description": f"{self.description_prefix}\n\nTool: {tool_name}\nArgs: {tool_args}",
                    }
                ],
                "review_configs": [
                    {
                        "action_name": tool_name,
                        "allowed_decisions": self.get_allowed_decisions(tool_name),
                    }
                ],
            }

            # Обновляем состояние агента
            agent_state.hitl_pending = True
            agent_state.hitl_request = hitl_request

            # Вызываем прерывание LangGraph
            return interrupt(hitl_request)

        # Если прерывание не нужно, возвращаем нормальный результат
        return {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "execute_immediately": True,
        }

    async def handle_resume(
        self, decisions: List[Dict[str, Any]], agent_state: Any
    ) -> Dict[str, Any]:
        """Обрабатывает решения пользователя при возобновлении"""

        agent_state.hitl_pending = False
        agent_state.hitl_request = None
        agent_state.hitl_decisions = decisions

        results = []

        for decision in decisions:
            decision_type = decision.get("type")

            if decision_type == "approve":
                # Утверждение - продолжаем выполнение
                results.append({"status": "approved", "decision": decision})

            elif decision_type == "edit":
                # Редактирование - изменяем аргументы инструмента
                edited_action = decision.get("edited_action", {})
                results.append(
                    {
                        "status": "edited",
                        "original_decision": decision,
                        "edited_action": edited_action,
                    }
                )

            elif decision_type == "reject":
                # Отклонение - добавляем сообщение в диалог
                message = decision.get("message", "Action was rejected")
                results.append(
                    {"status": "rejected", "message": message, "decision": decision}
                )

        return {"hitl_results": results, "requires_execution": True}
