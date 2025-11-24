# srccc/edms_assistant/agents/main_planner_agent.py
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from srccc.edms_assistant.agents.base_agent import BaseAgent
from srccc.edms_assistant.core.state import GlobalState
from srccc.edms_assistant.infrastructure.llm.llm import get_llm
import json
import logging

logger = logging.getLogger(__name__)


class MainPlannerAgent(BaseAgent):
    """
    Планирующий агент: анализирует запрос, формирует план, запускает агентов, собирает результаты.
    """

    def __init__(self, llm=None, agent_name: str = "main_planner_agent"):
        super().__init__(llm, agent_name)

    async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
        """Основной процесс: планирование -> передача управления графу или генерация ответа"""
        user_message = state.user_message
        logger.info(f"[AGENT] MainPlannerAgent.process: Received message: '{user_message[:50]}...', waiting_for_hitl_response: {state.waiting_for_hitl_response}")
        rag_context = kwargs.get("rag_context", [])  # Получаем RAG-контекст из graph.py

        if state.waiting_for_hitl_response:
            logger.info("[AGENT] MainPlannerAgent: Skipping planning, waiting for HITL response.")
            return {"messages": [HumanMessage(content=user_message)], "requires_execution": False}

        # Если есть RAG-контекст, генерируем ответ с его учётом
        if rag_context:
            logger.info(f"[AGENT] MainPlannerAgent: Generating response with RAG context containing {len(rag_context)} items.")
            response_text = await self._generate_response_with_rag(user_message, rag_context)
            logger.info(f"[AGENT] MainPlannerAgent: Generated RAG-based response.")
            return {
                "messages": [HumanMessage(content=user_message), AIMessage(content=response_text)],
                "requires_execution": False,
                "requires_clarification": False
            }

        # Иначе, планируем действия
        try:
            logger.info("[AGENT] MainPlannerAgent: Starting plan_actions.")
            plan = await self.plan_actions(state)
            logger.info(f"[AGENT] MainPlannerAgent: Plan generated: {plan}")
            # В реальной системе, тут может быть логика выполнения плана
            # Но в LangGraph, выполнение - это вызов других узлов
            # Поэтому планировщик может вернуть next_node или просто сообщение
            # Для простоты, генерируем ответ на основе плана
            actions_desc = [a.get('action', 'Unknown action') for a in plan.get('actions', [])]
            if actions_desc:
                response_text = f"Планирую выполнение следующих действий: {', '.join(actions_desc)}."
            else:
                # Если план пуст, но это не RAG, пробуем дать общий ответ
                response_text = f"Я получил ваш запрос: '{user_message}'. Пока не знаю, что с ним делать, так как нет подходящего инструмента или агента. Попробуйте уточнить."
            logger.info(f"[AGENT] MainPlannerAgent: Generated planning response: '{response_text[:100]}...'")
            return {
                "messages": [HumanMessage(content=user_message), AIMessage(content=response_text)],
                "requires_execution": False,  # Планировщик не требует выполнения в графе, он планирует
                "requires_clarification": False
            }
        except Exception as e:
            logger.error(f"[AGENT] Ошибка планирования: {e}", exc_info=True)
            error_msg = f"Ошибка планирования: {str(e)}"
            logger.info(f"[AGENT] MainPlannerAgent: Generated error response: '{error_msg}'")
            return {
                "messages": [HumanMessage(content=state.user_message), AIMessage(content=error_msg)],
                "requires_execution": False,
                "requires_clarification": False,
                "error": str(e),
            }

    async def _generate_response_with_rag(self, user_message: str, rag_context: List[Dict[str, Any]]) -> str:
        """
        Генерирует ответ, используя RAG-контекст.
        """
        logger.info(f"[AGENT] _generate_response_with_rag: Formatting RAG context for LLM.")
        context_str = "\n".join(
            [f"- {item['content']} (Источник: {item['metadata'].get('source', 'N/A')})" for item in rag_context])
        system_prompt = f"""
        Ты - помощник, который отвечает на вопросы пользователей, используя предоставленный контекст из документов.
        ВАЖНО: Если в контексте нет информации для ответа, скажи, что информации недостаточно.
        Контекст:
        {context_str}

        Вопрос пользователя: "{user_message}"
        """
        logger.info(f"[AGENT] _generate_response_with_rag: Calling LLM with prompt (first 100 chars): '{system_prompt[:100]}...'")
        response = await self.llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=user_message)])
        content = str(response.content)
        logger.info(f"[AGENT] _generate_response_with_rag: LLM responded with (first 100 chars): '{content[:100]}...'")
        return content

    async def plan_actions(self, state: GlobalState) -> Dict[str, Any]:
        """Формирует план действий на основе сообщения пользователя"""
        user_message = state.user_message
        logger.info(f"[AGENT] plan_actions: Analyzing message: '{user_message[:50]}...' with context (doc_id: {state.document_id}, user_id: {state.user_id})")
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
        {{"actions": [
            {{"agent": "имя_агента", "action": "описание_действия", "params": {{...}} }}
        ],
        "reasoning": "обоснование выбора"}}
        """

        logger.info(f"[AGENT] plan_actions: Calling LLM with prompt (first 100 chars): '{system_prompt[:100]}...'")
        response = await self.llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=user_message)])
        try:
            response_content = str(response.content)
            logger.info(f"[AGENT] plan_actions: LLM returned raw content (first 100 chars): '{response_content[:100]}...'")
            plan = json.loads(response_content)
            logger.info(f"[AGENT] plan_actions: Successfully parsed plan: {plan}")
            return plan
        except json.JSONDecodeError:
            logger.warning(f"[AGENT] plan_actions: Failed to parse LLM response as JSON. Raw: {response_content}")
            # Резервная логика
            if "сотрудник" in user_message.lower() or "работник" in user_message.lower():
                logger.info("[AGENT] plan_actions: Fallback logic matched 'employee'.")
                return {
                    "actions": [{"agent": "employee_agent", "action": "find_employee", "params": {}}],
                    "reasoning": "Запрос связан с сотрудником",
                }
            elif "документ" in user_message.lower() or "файл" in user_message.lower():
                logger.info("[AGENT] plan_actions: Fallback logic matched 'document'.")
                return {
                    "actions": [{"agent": "document_agent", "action": "get_document_info", "params": {}}],
                    "reasoning": "Запрос связан с документом",
                }
            elif "вложение" in user_message.lower() or "attachment" in user_message.lower():
                logger.info("[AGENT] plan_actions: Fallback logic matched 'attachment'.")
                return {
                    "actions": [{"agent": "attachment_agent", "action": "analyze_attachment", "params": {}}],
                    "reasoning": "Запрос связан с вложением",
                }
            else:
                logger.info("[AGENT] plan_actions: Fallback logic matched 'default'.")
                return {
                    "actions": [{"agent": "document_agent", "action": "get_document_info", "params": {}}],
                    "reasoning": "По умолчанию",
                }