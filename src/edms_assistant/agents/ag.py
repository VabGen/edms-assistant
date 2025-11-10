# # src/edms_assistant/core/agent.py
# import logging
# import json
# from langgraph.graph import StateGraph, END
# from src.edms_assistant.state.state import GlobalState
# from src.edms_assistant.infrastructure.llm.llm import get_llm
# from src.edms_assistant.tools.document import get_document_tool, search_documents_tool
# from src.edms_assistant.tools.attachment import summarize_attachment_tool, extract_and_summarize_file_tool
# from src.edms_assistant.tools.employee import find_responsible_tool, add_responsible_to_document_tool
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
# from langchain_core.runnables import RunnableLambda, RunnablePassthrough
# from langgraph.checkpoint.memory import MemorySaver
# from typing import Dict, Any, Optional, List
# from uuid import UUID
# import asyncio
#
# logger = logging.getLogger(__name__)
#
# # --- Инициализация LLM ---
# llm = get_llm()
#
# # --- Словарь инструментов ---
# TOOLS_MAP = {
#     "get_document": get_document_tool,
#     "search_documents": search_documents_tool,
#     "summarize_attachment": summarize_attachment_tool,
#     "extract_and_summarize_file": extract_and_summarize_file_tool,
#     "find_responsible": find_responsible_tool,
#     "add_responsible_to_document": add_responsible_to_document_tool,
# }
#
# # --- Формирование описания инструментов для промпта ---
# def get_tools_description() -> str:
#     """Генерирует строку с описанием инструментов, экранируя фигурные скобки."""
#     descriptions = []
#     for name, tool in TOOLS_MAP.items():
#         desc = f"- {name}: {tool.description}"
#         if hasattr(tool, 'args_schema'):
#             schema = tool.args_schema.model_json_schema()
#             import json
#             params_desc_str = json.dumps(schema.get("properties", {}), indent=2, ensure_ascii=False)
#             # Экранируем ВСЕ фигурные скобки в JSON-строке ДО вставки в основной промпт
#             params_desc_str = params_desc_str.replace('{', '{{').replace('}', '}}')
#             desc += f"\n  Args schema (JSON): {params_desc_str}"
#         descriptions.append(desc)
#     return "\n".join(descriptions)
#
# # --- LangGraph Agent ---
# def create_agent_graph():
#     # Подготовка частей промпта
#     # ВАЖНО: встраиваем описание инструментов в системный промпт один раз при создании runnable
#     tools_desc_str = get_tools_description()
#     # tools_desc_str теперь содержит экранированные {{ и }}
#
#     # Формируем СТРОКУ системного промпта, ВКЛЮЧАЯ экранированное описание инструментов
#     # ИСПОЛЬЗУЕМ тройные кавычки и f-строку, но ВНУТРИ НЕЁ ВСЁ, ЧТО ЯВЛЯЕТСЯ ЧАСТЬЮ JSON ВНУТРИ СТРОКИ,
#     # ДОЛЖНО БЫТЬ ЭКРАНИРОВАНО. ПРОВЕРЬМ ПРИМЕРЫ ВНУТРИ.
#     # Правильное экранирование для JSON-подобных строк внутри f-строки:
#     # Вместо: "args": {"content": "..."} -> это может быть интерпретировано как {"content"}
#     # Используем: "args": {{"content": "..."}}
#     # Или, как в предыдущем анализе, убедимся, что ВСЁ, что может быть воспринято как плейсхолдер, экранировано.
#     # Особенно аккуратно с примерами JSON.
#     # Пример: "args": {{"content": "..."}}
#     # Должно стать: "args": {{"{{"content"}}": "..."}}
#     # НЕТ! Это испортит JSON. Правильно:
#     # "args": {{"\"content\"": "..."}}
#     # Или, если LLM должен увидеть {"content": "..."}, то в строке должно быть {{"content": "..."}},
#     # но внутри ChatPromptTemplate это будет интерпретировано как плейсхолдер "content", если не экранировать.
#
#     # ПРАВИЛЬНЫЙ ПОДХОД:
#     # 1. Подготовить системное сообщение как строку, НЕ ИСПОЛЬЗУЯ НИКАКИХ ПЛЕЙСХОЛДЕРОВ, КРОМЕ ТЕХ, КОТОРЫЕ БУДУТ В ChatPromptTemplate.
#     # 2. ChatPromptTemplate будет ожидать ТОЛЬКО 'messages' и 'user_input'.
#     # 3. 'tools_description' вставляется в строку СИСТЕМНОГО СООБЩЕНИЯ как ЭКРАНИРОВАННАЯ строка.
#     # 4. 'system_message_content' передаётся в ChatPromptTemplate как статичная строка.
#
#     # СОЗДАЁМ строку ВНЕ ChatPromptTemplate
#     system_message_content = f"""
#     Ты — интеллектуальный ассистент для системы управления документами (EDMS).
#     Твоя задача — понять запрос пользователя и сформировать план действий.
#     План должен быть представлен в формате JSON со следующими полями:
#     - "action": имя инструмента для вызова (одно из доступных).
#     - "args": словарь аргументов для вызова инструмента.
#
#     Доступные инструменты:
#     {tools_desc_str}
#
#     ВАЖНО:
#     - Заполняй все обязательные аргументы инструмента.
#     - Если в сообщении пользователя упоминается документ, используй его ID из поля 'document_id' состояния, если он есть.
#     - Используй 'service_token' из состояния для всех вызовов инструментов.
#     - Если нужно обработать *загруженный пользователем файл*, используй 'uploaded_file_path' из состояния и вызови инструмент 'extract_and_summarize_file'.
#     - Если тебе нужно получить содержимое вложения документа:
#       1. Сначала вызови 'get_document', передав ему 'document_id'.
#       2. После получения результата 'get_document', проанализируй его. Если он содержит список вложений ('attachmentDocument'), выбери подходящее вложение.
#       3. Затем вызови 'summarize_attachment', передав ему 'document_id', 'attachment_id' и 'attachment_name' выбранного вложения.
#     - После получения РЕЗУЛЬТАТА инструмента (ToolMessage в истории) внимательно проанализируй его.
#       - Если РЕЗУЛЬТАТ отвечает на вопрос пользователя (например, 'get_document' вернул всю информацию: статус, краткое содержание, автор, вложения), СФОРМИРУЙ ФИНАЛЬНЫЙ ОТВЕТ, установив "action": "respond" и "args": {{"\\"content\\"": "Теперь я знаю о документе f38db809-afe8-11f0-82d9-6a58e1e2a181: статус NEW, краткое содержание 'О продлении контракта', автор Хомиченок А.В., вложения: Договор оказания услуг.docx."}}.
#       - НЕ вызывай снова инструмент, который уже был успешно выполнен и дал ответ на запрос.
#       - Если результат указывает на следующий необходимый шаг (например, 'get_document' вернул вложения, и пользователь хочет их содержимое), вызови соответствующий инструмент (например, 'summarize_attachment').
#     - Если действие не требует инструментов, установи "action": "respond" и "args": {{"\\"content\\"": "твой ответ пользователю"}}.
#     """
#
#     # --- КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ ---
#     # 1. Создаем объект SystemMessage ВНЕ ChatPromptTemplate
#     initial_system_message = SystemMessage(content=system_message_content)
#
#     # 2. Создаем ChatPromptTemplate ТОЛЬКО для 'messages' и 'user_input'
#     # Он НЕ будет включать строку system_message_content напрямую как шаблон.
#     # LangGraph (и ChatPromptTemplate) должны воспринимать ("system", system_message_content) как готовое сообщение.
#     # Оно не будет искать плейсхолдеры ВНУТРИ system_message_content, потому что это не шаблон, а статичный текст.
#     prompt_template = ChatPromptTemplate.from_messages([
#         # ("system", system_message_content), # <-- УБРАНО ИЗ ШАБЛОНА
#         MessagesPlaceholder(variable_name="messages"),
#         ("human", "{user_input}")  # Плейсхолдер для user_input
#     ])
#
#     # 3. Создаем цепочку, которая ДОБАВИТ системное сообщение к списку сообщений перед передачей в LLM
#     # Это обходит проблему с парсингом system_message_content внутри ChatPromptTemplate
#     # Мы передаем список сообщений, включающий SystemMessage, в LLM напрямую.
#     # LangChain LLM (например, ChatOpenAI) принимает список BaseMessage.
#     from langchain_core.runnables import RunnableLambda
#
#     def prepare_messages_for_llm(state_with_user_input):
#         # state_with_user_input содержит 'messages', 'user_input', 'tools_description', 'user_input'
#         # Нам нужны 'messages' и 'user_input' для шаблона, и SystemMessage для LLM
#         messages_for_template = state_with_user_input.get("messages", [])
#         user_input = state_with_user_input.get("user_input", "")
#
#         # Формируем финальный список сообщений для LLM
#         # 1. Системное сообщение (готовый объект)
#         # 2. История сообщений (из state)
#         # 3. Новое сообщение от пользователя (из user_input)
#         final_messages_for_llm = [initial_system_message] + messages_for_template + [HumanMessage(content=user_input)]
#         return final_messages_for_llm
#
#     # Цепочка: принимает state (с messages, user_input), готовит список сообщений для LLM, вызывает LLM
#     agent_runnable = (
#         RunnablePassthrough.assign(
#             user_input=lambda x: x["user_message"],
#             tools_description=lambda x: get_tools_description() # Добавляем для контекста, если LLM его использует (маловероятно в данном случае)
#         )
#         | RunnableLambda(prepare_messages_for_llm)
#         | llm
#     )
#
#     # Создание графа
#     workflow = StateGraph(GlobalState)
#
#     # Узел планировщика (LLM) - БЕЗ жестких правил
#     async def agent_node(state: GlobalState):
#         # Подготовим словарь для цепочки
#         # Он должен содержать 'messages', 'user_message', которые используются в assign и prepare_messages_for_llm
#         input_for_runnable = {
#             "messages": state.get("messages", []),
#             "user_message": state.get("user_message", "")
#             # 'tools_description' будет добавлено assign
#             # 'user_input' будет добавлено assign
#         }
#         logger.info(f"Agent node received user_input: {input_for_runnable['user_message']}")
#         logger.info(f"Agent node received {len(input_for_runnable['messages'])} messages in history.")
#         logger.info(f"Agent node sees document_id in state: {state.get('document_id')}")
#
#         # Вызываем цепочку
#         result = await agent_runnable.ainvoke(input_for_runnable)
#         # LLM возвращает сообщение (например, AIMessage) с content (обычно строка)
#         # Пытаемся распарсить его как JSON план
#         content_str = result.content
#         logger.info(f"LLM generated content: {content_str}")
#         try:
#             plan = json.loads(content_str)
#             # Добавляем план в состояние для следующего узла
#             # Также добавляем флаг, что нужно выполнить действие
#             return {**state, "pending_plan": plan, "requires_execution": True, "requires_clarification": False,
#                     "clarification_context": None}
#         except json.JSONDecodeError:
#             logger.info("LLM did not return valid JSON, treating as final response.")
#             # Если не JSON, считаем это финальным ответом
#             # LangGraph ожидает BaseMessage в 'messages'
#             return {**state, "requires_execution": False, "requires_clarification": False,
#                     "clarification_context": None, "messages": state.get("messages", []) + [AIMessage(content=content_str)]}
#
#     # Узел исполнителя (Executor) - остался без изменений
#     async def executor_node(state: GlobalState):
#         plan = state.get("pending_plan")
#         if not plan or not isinstance(plan, dict):
#              logger.warning("No valid plan found in state for execution.")
#              return {**state, "requires_execution": False, "requires_clarification": False,
#                      "clarification_context": None, "messages": state.get("messages", []) + [
#                      AIMessage(content="Ошибка: Не удалось сформировать план действий.")]}
#
#         action_name = plan.get("action")
#         args = plan.get("args", {})
#
#         if action_name == "respond":
#             # Специальное действие для финального ответа
#             response_content = args.get("content", "Не удалось сформулировать ответ.")
#             return {**state, "requires_execution": False, "requires_clarification": False,
#                     "clarification_context": None,
#                     "messages": state.get("messages", []) + [AIMessage(content=response_content)]}
#
#         if action_name not in TOOLS_MAP:
#             logger.error(f"Unknown action requested: {action_name}")
#             return {**state, "requires_execution": False, "requires_clarification": False,
#                     "clarification_context": None, "messages": state.get("messages", []) + [
#                     AIMessage(content=f"Ошибка: Неизвестное действие '{action_name}'")]}
#
#         tool_func = TOOLS_MAP[action_name]
#
#         # Заполняем обязательные аргументы из состояния, если они не указаны в плане
#         required_args = tool_func.args_schema.model_json_schema().get("required", [])
#         for arg_name in required_args:
#             if arg_name not in args:
#                 if arg_name == "service_token":
#                     args[arg_name] = state["service_token"]
#                 elif arg_name == "document_id" and state.get("document_id"):
#                     args[arg_name] = state["document_id"]
#                 elif arg_name == "file_path" and state.get("uploaded_file_path"):
#                     args[arg_name] = state["uploaded_file_path"]
#
#         logger.info(f"Executing tool '{action_name}' with args: {args}")
#         try:
#             # Вызов инструмента
#             tool_func_impl = tool_func.func
#             result_str = await tool_func_impl(**args)
#
#             logger.info(f"Tool '{action_name}' executed successfully. Result length: {len(result_str)} characters.")
#
#             # --- Проверка результата на неоднозначность (для уточнений) ---
#             # Пример: find_responsible_tool возвращает список
#             try:
#                 result_json = json.loads(result_str)
#                 if action_name == "find_responsible" and isinstance(result_json, list) and len(result_json) > 1:
#                     logger.info(f"Tool '{action_name}' returned multiple candidates. Requires clarification.")
#                     return {
#                         **state,
#                         "requires_clarification": True,
#                         "clarification_context": {
#                             "type": "candidate_selection",
#                             "candidates": result_json,
#                             "original_action": action_name,
#                             "original_args": args
#                         },
#                         "next_node_after_clarification": "agent" # После уточнения снова к планировщику
#                     }
#                 # Пример: get_document возвращает вложения
#                 elif action_name == "get_document":
#                     attachments = result_json.get("attachmentDocument", [])
#                     if attachments:
#                          logger.info(
#                              f"Tool '{action_name}' returned {len(attachments)} attachments. LLM should decide next step.")
#                          # LLM должен сам решить, нужно ли вызывать summarize_attachment
#                          # executor_node просто возвращает результат инструмента
#                          pass
#             except json.JSONDecodeError:
#                 # Если результат не JSON, пропускаем проверку на неоднозначность
#                 logger.warning(f"Tool '{action_name}' result is not valid JSON. Skipping ambiguity check.")
#                 pass
#             # --- /Проверка ---
#
#             # Возвращаем результат выполнения инструмента как сообщение для LLM
#             import uuid
#             fake_tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
#             return {**state, "messages": state.get("messages", []) + [
#                 ToolMessage(content=result_str, name=action_name, tool_call_id=fake_tool_call_id)],
#                     "requires_execution": False, "requires_clarification": False, "clarification_context": None}
#
#         except Exception as e:
#             logger.error(f"Error executing tool '{action_name}': {e}", exc_info=True)
#             error_msg = f"Ошибка выполнения инструмента '{action_name}': {str(e)}"
#             return {**state, "messages": state.get("messages", []) + [
#                 ToolMessage(content=error_msg, name=action_name, tool_call_id=f"call_error_{uuid.uuid4().hex[:8]}")],
#                     "requires_execution": False, "requires_clarification": False, "clarification_context": None}
#
#     # Функция маршрутизации после executor_node - осталась без изменений
#     def route_after_executor(state: GlobalState) -> str:
#         # Проверяем, требуется ли уточнение
#         if state.get("requires_clarification"):
#             logger.info("Clarification required, stopping execution.")
#             return END
#
#         # Если executor_node не указал, что требуется выполнение, возвращаемся к планировщику
#         # Это может произойти, если executor вернул финальный ответ или ошибку
#         # Проверим, есть ли финальное сообщение от ассистента
#         messages = state.get("messages", [])
#         if messages and isinstance(messages[-1], AIMessage):
#              logger.info("Final response generated by executor, ending.")
#              return END
#         # Иначе, если было выполнение инструмента, возвращаемся к планировщику с результатом
#         logger.info("Tool executed, returning to planner with result.")
#         return "agent"
#
#     # Добавление узлов
#     workflow.add_node("agent", agent_node)
#     workflow.add_node("executor", executor_node)
#
#     # Установка точки входа
#     workflow.set_entry_point("agent")
#
#     # Ребра
#     # agent -> executor (если есть план для выполнения)
#     # agent -> END (если финальный ответ сразу)
#     def route_after_agent(state: GlobalState) -> str:
#         if state.get("requires_execution", False):
#             return "executor"
#         else:
#             # Если не нужно выполнение, значит, это финальный ответ от LLM или ошибка
#             # Проверим, есть ли финальное сообщение
#             messages = state.get("messages", [])
#             if messages and isinstance(messages[-1], AIMessage):
#                 logger.info("Agent generated final response immediately, ending.")
#                 return END
#             else:
#                 # Это неожиданный случай, если LLM не сгенерировал финальный ответ, но и не указал выполнение
#                 logger.warning("Agent did not generate plan or final response.")
#                 return END
#
#     workflow.add_conditional_edges(
#         "agent",
#         route_after_agent,
#         {
#             "executor": "executor",
#             END: END
#         }
#     )
#
#     workflow.add_conditional_edges(
#         "executor",
#         route_after_executor,
#         {
#             "agent": "agent", # Вернуться к планировщику с результатом инструмента
#             END: END
#         }
#     )
#
#     # --- Настройка чекпоинтера ---
#     checkpointer = MemorySaver()
#
#     return workflow.compile(checkpointer=checkpointer)