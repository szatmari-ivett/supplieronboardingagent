from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list[dict], add_messages]
    user_message: str
    session_id: str
    plan: dict
    tool_name: str | None
    tool_args: dict
    tool_result: dict | None
    response_text: str
    metadata: dict
    awaiting_confirmation: bool
