import sqlite3
from collections.abc import Iterator
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import act_node, respond_node, router_node
from app.agent.state import AgentState
from app.config import settings

_checkpointer_conn: sqlite3.Connection | None = None
_checkpointer: SqliteSaver | None = None
_agent_graph: Any | None = None

_NODE_LABELS = {
    "router": "Planning next step",
    "act": "Calling backend tool",
    "respond": "Preparing response",
}


def _create_checkpointer() -> SqliteSaver:
    global _checkpointer_conn, _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    _checkpointer_conn = sqlite3.connect(str(settings.checkpoint_path), check_same_thread=False)
    _checkpointer = SqliteSaver(_checkpointer_conn)
    _checkpointer.setup()
    return _checkpointer


def reset_agent_graph() -> None:
    global _agent_graph, _checkpointer, _checkpointer_conn
    _agent_graph = None
    if _checkpointer_conn is not None:
        _checkpointer_conn.close()
    _checkpointer_conn = None
    _checkpointer = None


def _route_after_plan(state: AgentState) -> str:
    plan = state.get("plan", {})
    if plan.get("intent") == "help" and not plan.get("tool"):
        return "respond"
    if not state.get("tool_name"):
        return "respond"
    return "act"


def build_graph(checkpointer: SqliteSaver | None = None):
    graph = StateGraph(AgentState)
    graph.add_node("router", router_node)
    graph.add_node("act", act_node)
    graph.add_node("respond", respond_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _route_after_plan,
        {"act": "act", "respond": "respond"},
    )
    graph.add_edge("act", "respond")
    graph.add_edge("respond", END)

    memory = checkpointer or _create_checkpointer()
    return graph.compile(checkpointer=memory)


def get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_graph()
    return _agent_graph


def _build_result(state: AgentState, session_id: str) -> dict:
    return {
        "response": state.get("response_text", ""),
        "metadata": state.get("metadata", {}),
        "session_id": session_id,
    }


def run_agent(message: str, session_id: str = "default") -> dict:
    config = {"configurable": {"thread_id": session_id}}
    result = get_agent_graph().invoke(
        {"user_message": message, "session_id": session_id},
        config=config,
    )
    return _build_result(result, session_id)


def run_agent_stream(message: str, session_id: str = "default") -> Iterator[dict]:
    """Yield progress events per completed graph node, then the final response."""
    config = {"configurable": {"thread_id": session_id}}
    inputs = {"user_message": message, "session_id": session_id}
    final_state: AgentState = {}
    seen_router = False
    seen_act = False
    seen_respond = False

    for state in get_agent_graph().stream(inputs, config=config, stream_mode="values"):
        final_state = state
        if state.get("plan") and not seen_router:
            seen_router = True
            yield _progress_event("router", state)
        if state.get("tool_result") is not None and not seen_act:
            seen_act = True
            yield _progress_event("act", state)
        if state.get("response_text") and not seen_respond:
            seen_respond = True
            yield _progress_event("respond", state)

    yield {"type": "message", **_build_result(final_state, session_id)}
    yield {"type": "done"}


def _progress_event(node: str, state: AgentState) -> dict:
    return {
        "type": "progress",
        "node": node,
        "label": _NODE_LABELS[node],
        "tool": state.get("tool_name"),
    }
