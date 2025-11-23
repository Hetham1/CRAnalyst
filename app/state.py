"""Typed state definitions shared across LangGraph nodes."""

from __future__ import annotations

from typing import Annotated, Any, Dict, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Conversation state tracked by LangGraph."""

    messages: Annotated[list[BaseMessage], add_messages]
    metadata: Dict[str, Any]
