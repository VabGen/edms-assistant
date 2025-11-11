# import logging
# import json
# from langgraph.graph import StateGraph, END
# from src.edms_assistant.core.core import GlobalState
# from src.edms_assistant.infrastructure.llm.llm import get_llm
# from src.edms_assistant.tools.document import get_document_tool, search_documents_tool
# from src.edms_assistant.tools.attachment import summarize_attachment_tool, extract_and_summarize_file_tool
# from src.edms_assistant.tools.employee import find_responsible_tool, add_responsible_to_document_tool
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
# from langgraph.checkpoint.memory import MemorySaver
# from typing import Dict, Any, Optional, List
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
# # --- Генерация описания инструментов ---
# def format_tools_description(tools_map):
#     descriptions = []
#     for name, tool in tools_map.items():
#         # Получаем описание из tool.description
#         description = getattr(tool, 'description', 'No description available.')
#         # Получаем схему аргументов
#         schema = tool.args_schema.model_json_schema() if hasattr(tool, 'args_schema') else {}
#         params = schema.get('properties', {})
#         required = schema.get('required', [])
#         # Экранируем фигурные скобки, чтобы f-string не интерпретировал их
#         params_str = ", ".join([f"{k} (required)" if k in required else f"{k} (optional)" for k in params.keys()])
#         # Выводим описания параметров отдельно, чтобы не было фигурных скобок в f-string
#         param_details = []
#         for k, v in params.items():
#             desc = v.get('description', 'No description')
#             # Экранируем фигурные скобки в описании
#             desc_escaped = desc.replace("{", "{{").replace("}", "}}")
#             param_details.append(f"    {k} ({'required' if k in required else 'optional'}): {desc_escaped}")
#         param_details_str = "\n".join(param_details)
#         descriptions.append(f"- {name}: {description}\n  Args: {params_str if params_str else 'No arguments required'}\n{param_details_str if param_details_str else ''}")
#     return "\n".join(descriptions)
#
# TOOLS_DESCRIPTION = format_tools_description(TOOLS_MAP)
#
# # --- LangGraph Agent ---
# def create_agent_graph():
#     # Создаем ChatPromptTemplate
#     prompt_template = ChatPromptTemplate.from_messages([
#         ("system", "{system_prompt}"),  # <-- Теперь это переменная
#         MessagesPlaceholder(variable_name="messages"),
#         ("human", "{user_input}")
#     ])
#
#     # Привязываем инструменты к LLM (без bind_tools)
#     llm_with_tools = llm  # <--- Не используем bind_tools
#
#     # Цепочка: принимает core, извлекает user_input, подставляет в шаблон, вызывает LLM
#     def agent_runnable(core: GlobalState):
#         user_input = core.user_message
#         messages = core.messages
#
#         # Подготовим системное сообщение с инструментами
#         system_prompt_content = f"""
#         Ты — интеллектуальный ассистент для системы управления документами (EDMS).
#         Твоя задача — понять запрос пользователя и сформировать план действий.
#         Доступные инструменты:
#
#         {TOOLS_DESCRIPTION}
#
#         ВАЖНО:
#         - Если в сообщении пользователя упоминается документ и 'document_id' доступен в состоянии, используй его автоматически при вызове инструментов.
#         - Используй 'service_token' из состояния для всех вызовов инструментов.
#         - Если нужно обработать *загруженный пользователем файл*, используй 'uploaded_file_path' из состояния и вызови инструмент 'extract_and_summarize_file'.
#         - Если тебе нужно получить содержимое вложения документа:
#           1. Сначала вызови 'get_document', передав ему 'document_id'.
#           2. После получения результата 'get_document', проанализируй его. Если он содержит список вложений ('attachmentDocument'), выбери подходящее вложение.
#           3. Затем вызови 'summarize_attachment', передав ему 'document_id', 'attachment_id' и 'attachment_name' выбранного вложения.
#         - После получения РЕЗУЛЬТАТА инструмента (ToolMessage в истории) внимательно проанализируй его.
#           - Если РЕЗУЛЬТАТ отвечает на вопрос пользователя (например, 'get_document' вернул всю информацию: статус, краткое содержание, автор, вложения), СФОРМИРУЙ ФИНАЛЬНЫЙ ОТВЕТ пользователю.
#           - НЕ вызывай снова инструмент, который уже был успешно выполнен и дал ответ на запрос.
#           - Если результат указывает на следующий необходимый шаг (например, 'get_document' вернул вложения, и пользователь хочет их содержимое), вызови соответствующий инструмент (например, 'summarize_attachment').
#         - Если действие не требует инструментов, сформируй финальный ответ пользователю.
#
#         Формат вызова инструмента: TOOL_CALL::имя_инструмента::{{"аргументы": "в формате JSON"}}
#         Пример: TOOL_CALL::get_document::{{"document_id": "123", "service_token": "abc"}}
#         Формат финального ответа: FINAL_ANSWER::ответ для пользователя
#         """
#
#         input_for_runnable = {
#             "messages": messages,
#             "user_input": user_input,
#             "system_prompt": system_prompt_content  # <-- Добавляем переменную
#         }
#         prompt = prompt_template.invoke(input_for_runnable)
#         return llm_with_tools.invoke(prompt)
#
#     # Создание графа
#     workflow = StateGraph(GlobalState)
#
#     # Узел планировщика (LLM)
#     async def agent_node(core: GlobalState):
#         logger.info(f"Agent node received user_input: {core.user_message}")
#         logger.info(f"Agent node received {len(core.messages)} messages in history.")
#         logger.info(f"Agent node sees document_id in core: {core.document_id}")
#
#         # Проверяем, есть ли уже результат get_document в последнем сообщении
#         messages = core.messages
#         last_message = messages[-1] if messages else None
#         if isinstance(last_message, ToolMessage) and last_message.name == "get_document":
#             logger.info("Found result of 'get_document' in last message, passing to LLM for final answer.")
#             # Теперь LLM должен сформировать ответ на основе результата инструмента
#             result = agent_runnable(core)
#             logger.info(f"LLM generated message: {result}")
#
#             content = result.content
#             if content.startswith("FINAL_ANSWER::"):
#                 final_content = content[len("FINAL_ANSWER::"):]
#                 return {"messages": core.messages + [AIMessage(content=final_content)]}
#             else:
#                 # Если LLM снова что-то сгенерировал, добавляем это
#                 return {"messages": core.messages + [result]}
#
#         # Если последнее сообщение НЕ результат get_document, проверяем автовызов
#         user_input_lower = core.user_message.lower()
#         if core.document_id and any(phrase in user_input_lower for phrase in ["о документе", "расскажи о документе", "что в документе", "содержание документа", "информация о документе"]):
#             logger.info(f"Auto-triggering 'get_document' for document_id: {core.document_id}")
#             # Вызываем инструмент напрямую
#             tool_name = "get_document"
#             tool = TOOLS_MAP.get(tool_name)
#             if not tool:
#                 logger.error(f"Tool {tool_name} not found.")
#                 return {"messages": core.messages + [ToolMessage(content=f"Error: Tool {tool_name} not found.", name=tool_name, tool_call_id="unknown")]}
#
#             args = {"document_id": core.document_id, "service_token": core.service_token}
#             try:
#                 tool_result = await tool.ainvoke(args) if hasattr(tool, 'ainvoke') else tool(**args)
#                 return {"messages": core.messages + [ToolMessage(content=tool_result, name=tool_name, tool_call_id="auto_call")]}
#             except Exception as e:
#                 logger.error(f"Error executing auto-tool call: {e}")
#                 return {"messages": core.messages + [ToolMessage(content=f"Error: {str(e)}", name=tool_name, tool_call_id="auto_error")]}
#
#         # Если не сработал автовызов, идём к LLM
#         result = agent_runnable(core)
#         logger.info(f"LLM generated message: {result}")
#
#         content = result.content
#
#         # Проверяем, содержит ли ответ вызов инструмента
#         if content.startswith("TOOL_CALL::"):
#             # Пример: TOOL_CALL::get_document::{"document_id": "...", "service_token": "..."}
#             try:
#                 parts = content.split("::", 2)
#                 tool_name = parts[1]
#                 args_str = parts[2]
#                 args = json.loads(args_str)
#
#                 # Добавляем данные из состояния, если нужно
#                 if tool_name in ["get_document", "summarize_attachment"]:
#                     if core.document_id and "document_id" not in args:
#                         args["document_id"] = core.document_id
#                 if core.service_token and "service_token" not in args:
#                     args["service_token"] = core.service_token
#                 if tool_name == "extract_and_summarize_file" and core.uploaded_file_path:
#                     args["file_path"] = core.uploaded_file_path
#
#                 # Вызываем инструмент
#                 tool = TOOLS_MAP.get(tool_name)
#                 if not tool:
#                     logger.error(f"Tool {tool_name} not found.")
#                     return {"messages": core.messages + [ToolMessage(content=f"Error: Tool {tool_name} not found.", name=tool_name, tool_call_id="unknown")]}
#
#                 tool_result = await tool.ainvoke(args) if hasattr(tool, 'ainvoke') else tool(**args)
#                 return {"messages": core.messages + [ToolMessage(content=tool_result, name=tool_name, tool_call_id="manual_call")]}
#
#             except Exception as e:
#                 logger.error(f"Error parsing or executing tool call: {e}")
#                 return {"messages": core.messages + [ToolMessage(content=f"Error: {str(e)}", name="unknown", tool_call_id="error")]}
#
#         elif content.startswith("FINAL_ANSWER::"):
#             # Формируем финальный ответ
#             final_content = content[len("FINAL_ANSWER::"):]
#             return {"messages": core.messages + [AIMessage(content=final_content)]}
#
#         else:
#             # Если LLM не сгенерировал ни инструмент, ни финальный ответ — просто добавляем его сообщение
#             return {"messages": core.messages + [result]}
#
#     # Функция маршрутизации после agent_node
#     def route_after_agent(core: GlobalState) -> str:
#         messages = core.messages
#         if not messages:
#             return END
#
#         last_message = messages[-1]
#         if isinstance(last_message, ToolMessage):
#             # Был вызов инструмента, возвращаемся к агенту для следующего шага (обработки результата)
#             logger.info("Tool was called, returning to agent for next step.")
#             return "agent"
#         elif isinstance(last_message, AIMessage) and not last_message.content.startswith("TOOL_CALL"):
#             logger.info("LLM generated final response without tool calls, ending.")
#             return END
#         else:
#             logger.warning("Agent did not generate tool calls or final response correctly.")
#             return END
#
#     # Добавление узлов
#     workflow.add_node("agent", agent_node)
#
#     # Установка точки входа
#     workflow.set_entry_point("agent")
#
#     # Ребра
#     workflow.add_conditional_edges(
#         "agent",
#         route_after_agent,
#         {
#             "agent": "agent", # Возвращаемся к агенту после вызова инструмента
#             END: END
#         }
#     )
#
#     # --- Настройка чекпоинтера ---
#     checkpointer = MemorySaver()
#
#     return workflow.compile(checkpointer=checkpointer)