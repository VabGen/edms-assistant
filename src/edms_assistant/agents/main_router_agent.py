# from typing import Dict, Any
# from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
# from src.edms_assistant.core.state import GlobalState
# from src.edms_assistant.core.registry import BaseAgent, agent_registry
# from src.edms_assistant.infrastructure.llm.llm import get_llm
#
#
# class MainRouterAgent(BaseAgent):
#     """LLM-маршрутизирующий агент, который использует LLM для принятия решений и вызывает реальные агенты"""
#
#     def __init__(self):
#         super().__init__()
#         self.llm = get_llm()
#         self.tools = []
#
#     async def process(self, state: GlobalState, **kwargs) -> Dict[str, Any]:
#         """LLM-управляемая обработка запроса с реальными вызовами агентов"""
#         try:
#             user_message = state.user_message
#
#             # Определяем, какой агент подходит для запроса
#             routing_prompt = f"""
#             Проанализируй запрос пользователя: "{user_message}"
#
#             Доступные агенты:
#             - document_agent: для работы с документами (поиск, получение информации, анализ)
#             - employee_agent: для работы с сотрудниками
#             - attachment_agent: для работы с вложениями и файлами
#
#             Учитывай контекст:
#             - document_id: {state.document_id}
#             - uploaded_file_path: {state.uploaded_file_path}
#
#             Ответь в формате JSON:
#             {{"agent": "имя_агента", "reason": "причина выбора"}}
#             """
#
#             routing_response = await self.llm.ainvoke([
#                 SystemMessage(content=routing_prompt),
#                 HumanMessage(content=user_message)
#             ])
#
#             # Парсим ответ (в реальном проекте JSON-схему)
#             response_text = str(routing_response.content)
#             if "document_agent" in response_text.lower() or "document" in response_text.lower():
#                 target_agent_name = "document_agent"
#             elif "employee_agent" in response_text.lower() or "employee" in response_text.lower():
#                 target_agent_name = "employee_agent"
#             elif "attachment_agent" in response_text.lower() or "attachment" in response_text.lower():
#                 target_agent_name = "attachment_agent"
#             else:
#                 target_agent_name = "document_agent"  # по умолчанию
#
#             # Вызываем целевой агент
#             target_agent = agent_registry.get_agent_instance(target_agent_name)
#             if target_agent:
#                 # Обновляем текущего агента в состоянии
#                 state.current_agent = target_agent_name
#                 result = await target_agent.process(state)
#
#                 # Возвращаем результат целевого агента
#                 return result
#             else:
#                 return {
#                     "messages": [HumanMessage(content=user_message),
#                                  AIMessage(content=f"Агент '{target_agent_name}' не найден")],
#                     "requires_execution": False,
#                     "requires_clarification": False
#                 }
#
#         except Exception as e:
#             error_msg = f"Ошибка маршрутизации: {str(e)}"
#             return {
#                 "messages": [HumanMessage(content=state.user_message),
#                              AIMessage(content=error_msg)],
#                 "requires_execution": False,
#                 "requires_clarification": False,
#                 "error": str(e)
#             }