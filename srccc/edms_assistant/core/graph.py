# srccc/edms_assistant/core/graph.py
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # Импортируем
from srccc.edms_assistant.core.state import GlobalState
from srccc.edms_assistant.core.agent_registry import agent_registry  # Импортируем
from srccc.edms_assistant.agents.agent_factory import AgentFactory  # Импортируем *класс*
from srccc.edms_assistant.core.nlu_classifier import NLUClassifier
from srccc.edms_assistant.core.rag_retriever import RAGRetriever
from srccc.edms_assistant.infrastructure.llm.llm import get_llm, get_embeddings
from srccc.edms_assistant.core.settings import settings  # Импортируем настройки
import logging

logger = logging.getLogger(__name__)

# Инициализация NLU, RAG
nlu_classifier = NLUClassifier()
rag_retriever = RAGRetriever(embeddings=get_embeddings())  # Передаём embeddings

# agent_factory больше нет, используем AgentFactory (класс) или agent_registry напрямую

async def nlu_node(state: GlobalState) -> dict:
    """
    Узел для Natural Language Understanding.
    Определяет намерение пользователя и может выполнить RAG поиск.
    """
    user_message = state.user_message
    logger.info(f"[GRAPH] nlu_node: Processing message: '{user_message[:50]}...'")
    nlu_result = await nlu_classifier.classify_intent(user_message)
    intent = nlu_result.get("intent", "general_query")
    confidence = nlu_result.get("confidence", 0.0)

    logger.info(f"[GRAPH] NLU classified intent: {intent} (confidence: {confidence:.2f})")

    # Выполняем RAG поиск, если намерение подходит
    rag_context = []
    if intent in ["search_contract_terms", "find_document_content", "general_query"]:
        logger.info("[GRAPH] Performing RAG search...")
        rag_context = await rag_retriever.asearch(user_message, top_k=3)
        logger.info(f"[GRAPH] RAG search returned {len(rag_context)} results.")

    # Карта намерений на агентов
    intent_to_agent_map = {
        "find_employee": "employee_agent",
        "find_document": "document_agent",
        "analyze_attachment": "attachment_agent",
        "search_contract_terms": "main_planner_agent",  # Планировщик использует RAG
        "find_document_content": "main_planner_agent",  # Планировщик использует RAG
        "general_query": "main_planner_agent",
    }
    agent = intent_to_agent_map.get(intent, "main_planner_agent")

    logger.info(f"[GRAPH] Routing to agent: {agent} based on intent: {intent}")
    return {
        "current_agent": agent,
        "nlu_intent": intent,
        "nlu_confidence": confidence,
        "rag_context": rag_context,
    }

async def routing_node(state: GlobalState) -> dict:
    logger.info(f"[GRAPH] routing_node: Current agent is '{state.current_agent}', waiting_for_hitl_response: {state.waiting_for_hitl_response}")
    # Если ожидаем HITL, направляем к прерванному агенту
    if state.waiting_for_hitl_response:
        last_interrupted_agent = state.hitl_request.get("initiated_by_agent", "employee") if state.hitl_request else "employee"
        agent_to_node_map = {
            "employee_agent": "employee",
            "document_agent": "document",
            "attachment_agent": "attachment",
        }
        next_node = agent_to_node_map.get(last_interrupted_agent, "employee")
        logger.info(f"[GRAPH] Routing to '{next_node}' because waiting for HITL response from '{last_interrupted_agent}'.")
        return {"next_node": next_node, "current_agent": last_interrupted_agent}

    # Иначе, используем текущего агента из NLU
    agent = state.current_agent or "main_planner_agent"
    agent_to_node_map = {
        "employee_agent": "employee",
        "document_agent": "document",
        "attachment_agent": "attachment",
        "main_planner_agent": "planning",
    }
    next_node = agent_to_node_map.get(agent, "planning")
    logger.info(f"[GRAPH] Routing to '{next_node}' based on current agent: '{agent}'.")
    return {"next_node": next_node, "current_agent": agent}

async def planning_node(state: GlobalState) -> dict:
    logger.info(f"[GRAPH] planning_node: Calling AgentFactory.get_agent('main_planner_agent')")
    agent = AgentFactory.get_agent("main_planner_agent")
    if not agent:
        logger.error("MainPlannerAgent not found in factory")
        raise ValueError("MainPlannerAgent not found in factory")
    logger.info(f"[GRAPH] planning_node: Calling agent.process with rag_context length: {len(state.rag_context)}")
    result = await agent.process(state, rag_context=state.rag_context)
    logger.info(f"[GRAPH] planning_node: Agent returned result keys: {list(result.keys())}")
    return result

async def employee_node(state: GlobalState) -> dict:
    logger.info(f"[GRAPH] employee_node: Calling AgentFactory.get_agent('employee_agent')")
    agent = AgentFactory.get_agent("employee_agent")
    if not agent:
        logger.error("EmployeeAgent not found in factory")
        raise ValueError("EmployeeAgent not found in factory")
    logger.info(f"[GRAPH] employee_node: Calling agent.process")
    result = await agent.process(state)
    logger.info(f"[GRAPH] employee_node: Agent returned result keys: {list(result.keys())}")
    # Добавь эту строку:
    logger.info(f"[GRAPH] employee_node: Agent returned messages: {result.get('messages', [])}")
    return result

async def document_node(state: GlobalState) -> dict:
    logger.info(f"[GRAPH] document_node: Calling AgentFactory.get_agent('document_agent')")
    agent = AgentFactory.get_agent("document_agent")
    if not agent:
        logger.error("DocumentAgent not found in factory")
        raise ValueError("DocumentAgent not found in factory")
    logger.info(f"[GRAPH] document_node: Calling agent.process")
    result = await agent.process(state)
    logger.info(f"[GRAPH] document_node: Agent returned result keys: {list(result.keys())}")
    return result

async def attachment_node(state: GlobalState) -> dict:
    logger.info(f"[GRAPH] attachment_node: Calling AgentFactory.get_agent('attachment_agent')")
    agent = AgentFactory.get_agent("attachment_agent")
    if not agent:
        logger.error("AttachmentAgent not found in factory")
        raise ValueError("AttachmentAgent not found in factory")
    logger.info(f"[GRAPH] attachment_node: Calling agent.process")
    result = await agent.process(state)
    logger.info(f"[GRAPH] attachment_node: Agent returned result keys: {list(result.keys())}")
    return result

def create_agent_graph():
    logger.info("[GRAPH] Creating agent graph...")
    graph = StateGraph(GlobalState) # <-- Убедись, что передаёшь именно класс GlobalState

    graph.add_node("nlu", nlu_node)
    graph.add_node("routing", routing_node)
    graph.add_node("planning", planning_node)
    graph.add_node("employee", employee_node)
    graph.add_node("document", document_node)
    graph.add_node("attachment", attachment_node)

    graph.add_edge("__start__", "nlu")

    def route_after_routing(state: GlobalState) -> str:
        logger.info(f"[GRAPH] route_after_routing: Checking HITL state. waiting_for_hitl_response: {state.waiting_for_hitl_response}")
        if state.waiting_for_hitl_response:
            last_interrupted_agent = state.hitl_request.get("initiated_by_agent", "employee") if state.hitl_request else "employee"
            agent_to_node_map = {
                "employee_agent": "employee",
                "document_agent": "document",
                "attachment_agent": "attachment",
            }
            next_node = agent_to_node_map.get(last_interrupted_agent, "employee")
            logger.info(f"[GRAPH] route_after_routing: Returning '{next_node}' for HITL.")
            return next_node
        logger.info(f"[GRAPH] route_after_routing: Returning '{state.next_node}' based on normal routing.")
        return state.next_node

    graph.add_conditional_edges(
        "routing",
        route_after_routing,
        {
            "planning": "planning",
            "employee": "employee",
            "document": "document",
            "attachment": "attachment"
        }
    )

    graph.add_edge("planning", "__end__")
    graph.add_edge("employee", "__end__")
    graph.add_edge("document", "__end__")
    graph.add_edge("attachment", "__end__")

    # --- AsyncPostgresSaver ---
    if settings.checkpointer_type == "postgres":
        logger.info("[GRAPH] Using AsyncPostgresSaver.")
        checkpointer = AsyncPostgresSaver.from_conn_string(settings.postgres_connection_string)
    else:
        logger.info("[GRAPH] Using MemorySaver.")
        checkpointer = MemorySaver()  # Fallback

    compiled_graph = graph.compile(checkpointer=checkpointer)
    logger.info("[GRAPH] Agent graph created and compiled successfully.")
    return compiled_graph