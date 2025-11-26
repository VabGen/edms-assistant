# src/edms_assistant/rag/graph.py
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from src.edms_assistant.rag.router import route_question_to_file
from src.edms_assistant.rag.retriever import retrieve_and_generate
from src.edms_assistant.rag.indexer import index_manager
import logging

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    question: str
    chat_history: List[Dict[str, Any]]
    selected_file: str
    answer: str
    retry_count: int


async def decide_file_node(state: AgentState) -> AgentState:
    files = list(index_manager.vector_stores.keys())
    if not files:
        raise RuntimeError("Нет загруженных документов")
    filename = await route_question_to_file(state["question"], state["chat_history"], files)
    return {**state, "selected_file": filename}


async def retrieve_node(state: AgentState) -> AgentState:
    vs = index_manager.vector_stores.get(state["selected_file"])
    if not vs:
        return {**state, "answer": "Файл не найден"}
    answer = await retrieve_and_generate(
        state["question"],
        state["selected_file"],
        state["chat_history"],
        vs
    )
    return {**state, "answer": answer}


async def reflect_node(state: AgentState) -> AgentState:
    current_file = state["selected_file"]
    other_files = [f for f in index_manager.vector_stores.keys() if f != current_file]
    if not other_files:
        return {**state, "answer": "Я не нашёл информацию в доступных документах."}

    for alt_file in other_files:
        vs = index_manager.vector_stores[alt_file]
        answer = await retrieve_and_generate(
            state["question"], alt_file, state["chat_history"], vs
        )
        if answer != "REFLECT: Не найдено в этом файле" and len(answer) > 20:
            return {**state, "answer": answer, "selected_file": alt_file}

    return {**state, "answer": "Я не нашёл информацию в доступных документах."}


def should_reflect(state: AgentState) -> str:
    if state["answer"] == "REFLECT: Не найдено в этом файле" and state["retry_count"] < 1:
        return "reflect"
    return "end"


def create_rag_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("decide_file", decide_file_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("reflect", reflect_node)

    workflow.set_entry_point("decide_file")
    workflow.add_edge("decide_file", "retrieve")
    workflow.add_conditional_edges("retrieve", should_reflect, {"reflect": "reflect", "end": END})
    workflow.add_edge("reflect", END)

    return workflow.compile()
