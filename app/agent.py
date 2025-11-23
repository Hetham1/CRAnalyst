"""LangGraph agent factory."""

from __future__ import annotations

from typing import Iterable
import logging

from langchain_core.language_models import FakeListChatModel
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from .config import Settings
from .state import AgentState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Crypto Analyst Agent: a proactive market strategist for traders.
You orchestrate data from CoinGecko, CryptoCompare news, Blockchair on-chain stats, and user portfolios via tools.

Response contract:
- Always return valid JSON that matches:
  {{"summary": "<concise headline>", "responses": [ {{ "type": "...", "content": "...", "data": {{...}}, "chart_type": "...", "options": {{...}} }} ]}}
- Supported component types: "text", "table", "chart", "metric_grid", "news_list", "alerts_panel", "portfolio", "watchlist", "follow_up".
- Prefer a text component for narrative, a table for static comparisons, chart for time-series (line for normalized performance, candlestick+indicator for TA, donut for allocation).
- Finish with a `follow_up` component that suggests the next best two prompts (e.g., "See ETH news", "Set RSI alert").

Tooling heuristics:
- Call `market_pulse` for top-level "what's happening" or category heatmap questions.
- Call `asset_intel` when the user references any specific asset; it already bundles price, news, sentiment, and on-chain context.
- Use `advanced_compare` for multi-asset performance/dev-activity/TPS requests; pair with a normalized performance chart.
- Use `technical_analysis` for RSI/MACD style prompts (currently RSI). Describe whether the signal is overbought/oversold.
- Use `onchain_activity` when the user explicitly asks about whales or network growth (BTC/ETH/LTC/DOGE/BCH).
- When portfolio/watchlist/alert questions surface, consult `portfolio_snapshot`, `watchlist_status`, or `alert_status` (pass the current thread_id as user_id).
- Fall back to `get_price_quotes`, `asset_overview`, or `fundamentals_snapshot` when lightweight stats are sufficient.

Conversation style:
- Interpret the numbers: never dump data without context. Highlight causes (news, flows, category rotations).
- If a tool errors or data is missing, explain the limitation and steer the user to an actionable alternative.
- Keep tone confident, precise, and oriented toward next steps."""


class TestingToolAwareChatModel(FakeListChatModel):
    """Fake chat model that no-ops tool binding for tests."""

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        self._bound_tools = list(tools)
        return self


def build_agent(
    settings: Settings,
    tools: Iterable,
    llm: BaseChatModel | None = None,
    *,
    checkpointer: BaseCheckpointSaver,
):
    """Compile the LangGraph agent with SQLite checkpointing."""

    if llm is None:
        if settings.testing:
            logger.info("Initializing testing chat model")
            llm = TestingToolAwareChatModel(responses=["Testing response."])
        else:
            if not settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY is required unless TESTING=1.")
            logger.info("Initializing Gemini model=%s", settings.gemini_model)
            llm = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                temperature=0.2,
                google_api_key=settings.google_api_key,
            )

    llm_with_tools = llm.bind_tools(list(tools))

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    def agent_node(state: AgentState):
        logger.debug("Agent node executing with %s messages", len(state.get("messages", [])))
        rendered = prompt.format_messages(messages=state["messages"])
        response: BaseMessage = llm_with_tools.invoke(rendered)
        return {"messages": [response]}

    tool_node = ToolNode(list(tools))
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    graph.set_entry_point("agent")

    logger.info("LangGraph compiled with %s tools", len(list(tools)))
    return graph.compile(checkpointer=checkpointer)
