import logging
import json
from langgraph.graph import StateGraph, END
from src.edms_assistant.state.state import GlobalState
from src.edms_assistant.infrastructure.llm.llm import get_llm
from src.edms_assistant.tools.document import get_document_tool, search_documents_tool
from src.edms_assistant.tools.attachment import summarize_attachment_tool, extract_and_summarize_file_tool
from src.edms_assistant.tools.employee import find_responsible_tool, add_responsible_to_document_tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from typing import Dict, Any, Optional, List
import asyncio

logger = logging.getLogger(__name__)

# --- Инициализация LLM ---
llm = get_llm()

# --- Словарь инструментов ---
TOOLS_MAP = {
    "get_document": get_document_tool,
    "search_documents": search_documents_tool,
    "summarize_attachment": summarize_attachment_tool,
    "extract_and_summarize_file": extract_and_summarize_file_tool,
    "find_responsible": find_responsible_tool,
    "add_responsible_to_document": add_responsible_to_document_tool,
}

# --- LangGraph Agent ---
def create_agent_graph():
    # Подготовка системного сообщения
    system_prompt_content = """
    Ты — интеллектуальный ассистент для системы управления документами (EDMS).
    Твоя задача — понять запрос пользователя и сформировать план действий.
    Используй доступные инструменты, чтобы получить информацию или выполнить действия.

    ВАЖНО:
    - Если в сообщении пользователя упоминается документ и 'document_id' доступен в состоянии, используй его автоматически при вызове инструментов.
    - Используй 'service_token' из состояния для всех вызовов инструментов.
    - Если нужно обработать *загруженный пользователем файл*, используй 'uploaded_file_path' из состояния и вызови инструмент 'extract_and_summarize_file'.
    - Если тебе нужно получить содержимое вложения документа:
      1. Сначала вызови 'get_document', передав ему 'document_id'.
      2. После получения результата 'get_document', проанализируй его. Если он содержит список вложений ('attachmentDocument'), выбери подходящее вложение.
      3. Затем вызови 'summarize_attachment', передав ему 'document_id', 'attachment_id' и 'attachment_name' выбранного вложения.
    - После получения РЕЗУЛЬТАТА инструмента (ToolMessage в истории) внимательно проанализируй его.
      - Если РЕЗУЛЬТАТ отвечает на вопрос пользователя (например, 'get_document' вернул всю информацию: статус, краткое содержание, автор, вложения), СФОРМИРУЙ ФИНАЛЬНЫЙ ОТВЕТ пользователю.
      - НЕ вызывай снова инструмент, который уже был успешно выполнен и дал ответ на запрос.
      - Если результат указывает на следующий необходимый шаг (например, 'get_document' вернул вложения, и пользователь хочет их содержимое), вызови соответствующий инструмент (например, 'summarize_attachment').
    - Если действие не требует инструментов, сформируй финальный ответ пользователю.
    """

    # Создаем ChatPromptTemplate
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt_content),
        MessagesPlaceholder(variable_name="messages"),
        ("human", "{user_input}")
    ])

    # Привязываем инструменты к LLM
    # llm_with_tools = llm.bind_tools(list(TOOLS_MAP.values()))
    llm_with_tools = llm.bind_tools(list(TOOLS_MAP.values()), tool_choice="none")
    # llm_with_tools = llm.bind_tools(list(TOOLS_MAP.values()),
    #                                 tool_choice={"type": "function", "function": {"name": "get_document"}})
    # llm_with_tools = llm.bind_tools(list(TOOLS_MAP.values()), tool_choice="auto")

    # Цепочка: принимает state, извлекает user_input, подставляет в шаблон, вызывает LLM с инструментами
    def agent_runnable(state: GlobalState):
        user_input = state.user_message
        messages = state.messages
        input_for_runnable = {
            "messages": messages,
            "user_input": user_input
        }
        prompt = prompt_template.invoke(input_for_runnable)
        return llm_with_tools.invoke(prompt)

    # Создание графа
    workflow = StateGraph(GlobalState)

    # Узел планировщика (LLM)
    async def agent_node(state: GlobalState):
        logger.info(f"Agent node received user_input: {state.user_message}")
        logger.info(f"Agent node received {len(state.messages)} messages in history.")
        logger.info(f"Agent node sees document_id in state: {state.document_id}")

        result = agent_runnable(state)
        logger.info(f"LLM generated message: {result}")
        return {"messages": state.messages + [result]}

    # Узел исполнителя (ToolNode)
    async def executor_node(state: GlobalState):
        # Извлекаем последнее сообщение (с tool_calls)
        messages = state.messages
        last_message = messages[-1] if messages else None
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            logger.warning("No tool calls found in last message.")
            return state

        # Извлекаем вызовы инструментов и вызываем их
        tool_calls = last_message.tool_calls
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            args = tool_call["args"]

            # Добавляем данные из состояния в аргументы, если нужно
            if tool_name in ["get_document", "summarize_attachment"]:
                if state.document_id and "document_id" not in args:
                    args["document_id"] = state.document_id
            if state.service_token and "service_token" not in args:
                args["service_token"] = state.service_token
            if tool_name == "extract_and_summarize_file" and state.uploaded_file_path:
                args["file_path"] = state.uploaded_file_path

            # Получаем инструмент и вызываем его
            tool = TOOLS_MAP.get(tool_name)
            if not tool:
                logger.error(f"Tool {tool_name} not found.")
                continue

            try:
                result = await tool.ainvoke(args) if hasattr(tool, 'ainvoke') else tool(**args)
                results.append(ToolMessage(content=result, name=tool_name, tool_call_id=tool_call["id"]))
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                results.append(ToolMessage(content=f"Error: {str(e)}", name=tool_name, tool_call_id=tool_call["id"]))

        # Проверим результаты на неоднозначность
        for res_msg in results:
            try:
                result_json = json.loads(res_msg.content)
                if res_msg.name == "find_responsible" and isinstance(result_json, list) and len(result_json) > 1:
                    logger.info(f"Tool '{res_msg.name}' returned multiple candidates. Requires clarification.")
                    return {
                        "messages": state.messages + results,
                        "requires_clarification": True,
                        "clarification_context": {
                            "type": "candidate_selection",
                            "candidates": result_json,
                            "original_action": res_msg.name,
                        },
                        "next_node_after_clarification": "agent"
                    }
            except json.JSONDecodeError:
                logger.warning(f"Tool result from '{res_msg.name}' is not valid JSON. Skipping ambiguity check.")

        return {"messages": state.messages + results, "requires_clarification": False, "clarification_context": None}

    # Функция маршрутизации после executor_node
    def route_after_executor(state: GlobalState) -> str:
        if state.requires_clarification:
            return END

        messages = state.messages
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage) and not last_message.tool_calls:
                logger.info("Final response generated by LLM, ending.")
                return END
        logger.info("Tool executed, returning to planner with result.")
        return "agent"

    # Функция маршрутизации после agent_node
    def route_after_agent(state: GlobalState) -> str:
        messages = state.messages
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                logger.info("LLM generated tool calls, going to executor.")
                return "executor"
            elif isinstance(last_message, AIMessage) and not last_message.tool_calls:
                logger.info("LLM generated final response without tool calls, ending.")
                return END
        logger.warning("Agent did not generate tool calls or final response correctly.")
        return END

    # Добавление узлов
    workflow.add_node("agent", agent_node)
    workflow.add_node("executor", executor_node)

    # Установка точки входа
    workflow.set_entry_point("agent")

    # Ребра
    workflow.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "executor": "executor",
            END: END
        }
    )

    workflow.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "agent": "agent",
            END: END
        }
    )

    # --- Настройка чекпоинтера ---
    checkpointer = MemorySaver()  # <--- Теперь используем MemorySaver

    return workflow.compile(checkpointer=checkpointer)