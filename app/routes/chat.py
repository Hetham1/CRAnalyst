"""Chat API routes."""

from __future__ import annotations

import json
import logging
import re
import re
from typing import Any, AsyncGenerator, Dict, Iterable, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
)

from pydantic import ValidationError

from ..models import AgentStructuredResponse, ChatRequest, ChatResponse, UIComponent
from ..market import COMMON_ASSET_OVERRIDES

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)

def _shorten(value: Any, limit: int = 160) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


def _extract_ai_content(messages: Iterable) -> tuple[str, List[str]]:
    """Return the last AI message content and tool usage."""

    content = ""
    tools_used: list[str] = []
    for message in reversed(list(messages)):
        if isinstance(message, AIMessage):
            content = _stringify_content(message.content)
            tool_calls = message.additional_kwargs.get("tool_calls", [])
            for call in tool_calls:
                if isinstance(call, dict) and call.get("function"):
                    tools_used.append(call["function"].get("name"))
            break
    return content, tools_used


def _stringify_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        fragments: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                fragments.append(item.get("text", ""))
        return "".join(fragments)
    if isinstance(content, dict):
        return content.get("text", "")
    return ""


def _jsonify(value: Any):
    if isinstance(value, BaseMessage):
        return {
            "type": value.type,
            "content": _stringify_content(value.content),
            "additional_kwargs": value.additional_kwargs,
        }
    if isinstance(value, dict):
        return {key: _jsonify(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_jsonify(item) for item in value]
    return value


TOOL_EVENT_MAP = {
    "asset_overview": "asset_overview",
    "compare_assets": "compare_assets",
    "fundamentals_snapshot": "fundamentals_snapshot",
    "get_price_quotes": "price_quotes",
    "get_trending_coins": "trending_coins",
    "market_pulse": "market_pulse",
    "asset_intel": "asset_intel",
    "advanced_compare": "advanced_compare",
    "technical_analysis": "technical_analysis",
    "onchain_activity": "onchain_activity",
    "portfolio_snapshot": "portfolio_snapshot",
    "watchlist_status": "watchlist_status",
    "alert_status": "alert_status",
}

COMPONENT_HYDRATORS: dict[str, Any] = {}

COMMON_NAME_OVERRIDES = {
    "bitcoin": "bitcoin",
    "ethereum": "ethereum",
    "solana": "solana",
    "cardano": "cardano",
    "dogecoin": "dogecoin",
    "polygon": "polygon-pos",
    "polkadot": "polkadot",
    "binance": "binancecoin",
    "ripple": "ripple",
    "litecoin": "litecoin",
    "avalanche": "avalanche",
    "toncoin": "toncoin",
}

CONTENT_TICKER_PATTERN = re.compile(r"\(([A-Z]{2,6})\)")
UPPER_TICKER_PATTERN = re.compile(r"\b([A-Z]{2,6})\b")


def _register_hydrator(component_type: str):
    def decorator(func):
        COMPONENT_HYDRATORS[component_type] = func
        return func

    return decorator


def _determine_asset(component: UIComponent) -> Optional[str]:
    data = component.data or {}
    options = component.options or {}
    candidates = [
        data.get("asset"),
        data.get("symbol"),
        options.get("asset"),
        options.get("symbol"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            cleaned = candidate.strip()
            if cleaned:
                return cleaned.lower()

    content = (component.content or "").strip()
    if content:
        match = CONTENT_TICKER_PATTERN.search(content)
        if match:
            return match.group(1).lower()
        match = UPPER_TICKER_PATTERN.search(content)
        if match:
            token = match.group(1).lower()
            if token in COMMON_ASSET_OVERRIDES:
                return token
        lowered = content.lower()
        for name, slug in COMMON_NAME_OVERRIDES.items():
            if name in lowered:
                return slug
    return None


@_register_hydrator("asset_intel")
def _hydrate_asset_intel(component: UIComponent, state) -> Optional[dict]:
    asset = _determine_asset(component)
    if not asset:
        return component.data

    market = getattr(state, "market_service", None)
    news_service = getattr(state, "news_service", None)
    onchain_service = getattr(state, "onchain_service", None)
    if not market or not news_service:
        logger.warning("Hydration skipped for asset_intel; services missing.")
        return component.data

    currency = (component.options or {}).get("currency") or (component.data or {}).get("currency") or "usd"
    errors: list[str] = []
    try:
        overview = market.asset_overview(asset, currency, lookback_days=7)
    except Exception as exc:  # pragma: no cover - upstream dependency
        logger.warning("asset_intel hydration failed fetching overview: %s", exc)
        overview = (component.data or {}).get("overview")
        errors.append("Live price data unavailable (CoinGecko rate limit).")

    news_items = []
    sentiment = (component.data or {}).get("sentiment")
    try:
        news_items = news_service.fetch_for_asset(asset, limit=3)
        sentiment = news_service.summarize_sentiment(news_items)
    except Exception as exc:  # pragma: no cover
        logger.warning("asset_intel hydration news failed: %s", exc)
        if not news_items:
            errors.append("News feed unavailable.")

    try:
        onchain = onchain_service.snapshot(asset) if onchain_service else (component.data or {}).get("onchain")
    except ValueError:
        onchain = (component.data or {}).get("onchain")
        errors.append("On-chain data unavailable for this asset.")

    response_data = dict(component.data or {})
    response_data.update(
        {
            "asset": asset,
            "overview": overview,
            "news": [
                {
                    "title": item.title,
                    "source": item.source,
                    "url": item.url,
                    "published_at": item.published_at,
                }
                for item in news_items
            ],
            "sentiment": sentiment,
            "onchain": onchain,
        }
    )

    candlestick_series = []
    if overview and overview.get("ohlc_series"):
        candlestick_series = overview["ohlc_series"]
    if candlestick_series:
        response_data["series"] = candlestick_series
        component.chart_type = "candlestick"

    response_data["_hydrated"] = True
    existing_errors = response_data.get("errors") or []
    response_data["errors"] = [*existing_errors, *errors]

    return response_data


def _hydrate_structured(structured: AgentStructuredResponse, state) -> AgentStructuredResponse:
    if not structured or not structured.responses:
        return structured
    for component in structured.responses:
        hydrator = COMPONENT_HYDRATORS.get(component.type)
        if hydrator:
            try:
                hydrated = hydrator(component, state)
                if hydrated:
                    component.data = hydrated
            except Exception as exc:
                logger.warning("Component hydration failed type=%s error=%s", component.type, exc)
    return structured


def _serialize_tool_payload(tool_name: str, payload: Any) -> Dict[str, Any]:
    extracted = payload
    if isinstance(payload, BaseMessage):
        extracted = payload.additional_kwargs.get("output", payload.content)
    if isinstance(extracted, str):
        stripped = extracted.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("[") and stripped.endswith("]")
        ):
            try:
                extracted = json.loads(stripped)
            except json.JSONDecodeError:
                pass
    return {
        "type": TOOL_EVENT_MAP.get(tool_name, tool_name),
        "payload": _jsonify(extracted),
    }


CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]+?)\s*```", re.IGNORECASE)


def _strip_code_fences(value: str) -> str:
    """Remove code fences and loose JSON prefixes before parsing."""

    if not value:
        return ""
    trimmed = value.strip()
    match = CODE_BLOCK_PATTERN.search(trimmed)
    candidate = match.group(1) if match else trimmed
    candidate = re.sub(r"^json\b[:=\s-]*", "", candidate, flags=re.IGNORECASE)
    return candidate.strip()


def _ensure_structured(content: str) -> AgentStructuredResponse:
    if not content:
        logger.warning("Structured response fallback: empty content.")
        return AgentStructuredResponse(responses=[])
    try:
        cleaned = _strip_code_fences(content)
        structured = AgentStructuredResponse.model_validate_json(cleaned)
        logger.debug(
            "Structured payload parsed summary=%s responses=%s",
            structured.summary,
            len(structured.responses),
        )
        return structured
    except (ValidationError, ValueError, TypeError):
        logger.exception("Structured payload parsing failed; falling back to text.")
        cleaned = _strip_code_fences(content)
        fallback_text = cleaned or "No response generated."
        component = UIComponent(type="text", content=fallback_text)
        return AgentStructuredResponse(summary=fallback_text, responses=[component])


@router.post("", response_model=ChatResponse)
async def invoke_chat(payload: ChatRequest, request: Request):
    graph = getattr(request.app.state, "graph", None)
    settings = getattr(request.app.state, "settings", None)
    if not graph or not settings:
        logger.error("Chat invocation rejected: agent not initialized.")
        raise HTTPException(status_code=503, detail="Agent is not initialized.")

    thread_id = payload.thread_id or settings.default_thread_id
    metadata = payload.metadata.dict() if payload.metadata else {}
    metadata["thread_id"] = thread_id
    logger.info("Chat request thread=%s text=%s", thread_id, payload.message[:120])
    inputs = {
        "messages": [
            HumanMessage(
                content=payload.message,
                additional_kwargs={"metadata": metadata},
            )
        ]
    }
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(inputs, config=config)
    messages = result.get("messages", [])
    content, tools_used = _extract_ai_content(messages)
    if not content:
        logger.error("Empty response from agent thread=%s", thread_id)
        raise HTTPException(status_code=500, detail="Agent returned an empty response.")
    structured = _ensure_structured(content)
    structured = _hydrate_structured(structured, request.app.state)
    logger.info(
        "Chat response thread=%s chars=%s tools=%s",
        thread_id,
        len(content),
        tools_used,
    )
    return ChatResponse(
        thread_id=thread_id,
        content=content,
        used_tools=[tool for tool in tools_used if tool],
        metadata={"message_count": len(messages)},
        structured=structured,
    )


async def _langgraph_event_stream(
    graph, state, message: str, thread_id: str
) -> AsyncGenerator[str, None]:
    logger.info("Starting SSE stream for thread=%s", thread_id)
    inputs = {"messages": [HumanMessage(content=message)]}
    config = {"configurable": {"thread_id": thread_id}}
    yielded = False
    buffer: list[str] = []
    async for event in graph.astream_events(inputs, config=config, version="v1"):
        kind = event.get("event")
        if kind == "on_chat_model_stream":
            chunk: AIMessageChunk = event["data"]["chunk"]
            text = _stringify_content(chunk.content)
            if text:
                buffer.append(text)
                logger.debug(
                    "SSE chunk thread=%s size=%s preview=%s",
                    thread_id,
                    len(text),
                    _shorten(text),
                )
                payload = json.dumps({"chunk": text, "thread_id": thread_id})
                yield f"data: {payload}\n\n"
                yielded = True
        elif kind == "on_tool_start":
            tool_name = event.get("name") or event.get("metadata", {}).get("name", "tool")
            logger.info("Tool start thread=%s tool=%s", thread_id, tool_name)
            status_payload = json.dumps(
                {"tool": tool_name, "message": f"Running {tool_name}"}
            )
            yield f"event: status\ndata: {status_payload}\n\n"
        elif kind == "on_tool_end":
            tool_name = event.get("name") or event.get("metadata", {}).get("name", "tool")
            tool_output = event.get("data", {}).get("output")
            logger.info(
                "Tool end thread=%s tool=%s payload_preview=%s",
                thread_id,
                tool_name,
                _shorten(tool_output),
            )
            payload = json.dumps(_serialize_tool_payload(tool_name, tool_output))
            yield f"event: visual\ndata: {payload}\n\n"
    if not yielded:
        logger.warning(
            "Model produced no streaming chunks; falling back to ainvoke thread=%s",
            thread_id,
        )
        result = await graph.ainvoke(inputs, config=config)
        content, _ = _extract_ai_content(result.get("messages", []))
        buffer.append(content or "")
        if content:
            payload = json.dumps({"chunk": content, "thread_id": thread_id})
            yield f"data: {payload}\n\n"
    structured = _ensure_structured("".join(buffer))
    structured = _hydrate_structured(structured, state)
    layout_payload = json.dumps(structured.model_dump())
    logger.info(
        "Emitting layout thread=%s summary=%s components=%s",
        thread_id,
        structured.summary,
        len(structured.responses),
    )
    yield f"event: layout\ndata: {layout_payload}\n\n"
    yield 'data: {"event":"end"}\n\n'


@router.post("/stream")
async def stream_chat(payload: ChatRequest, request: Request):
    graph = getattr(request.app.state, "graph", None)
    settings = getattr(request.app.state, "settings", None)
    if not graph or not settings:
        logger.error("Stream request rejected: agent not initialized.")
        raise HTTPException(status_code=503, detail="Agent is not initialized.")

    thread_id = payload.thread_id or settings.default_thread_id
    generator = _langgraph_event_stream(graph, request.app.state, payload.message, thread_id)
    return StreamingResponse(generator, media_type="text/event-stream")
