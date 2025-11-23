"""Pydantic models shared across the application."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PriceQuote(BaseModel):
    asset: str = Field(..., description="CoinGecko asset identifier or symbol.")
    currency: str = Field(..., description="Fiat or crypto currency for the quote.")
    price: float
    change_24h: Optional[float] = Field(
        default=None, description="24 hour percentage change when available."
    )
    market_cap: Optional[float] = None


class MarketComparison(BaseModel):
    base: str
    target: str
    base_price: Optional[float]
    target_price: Optional[float]
    spread: Optional[float]


class TrendingCoin(BaseModel):
    name: str
    symbol: str
    score: int
    slug: str


class ChatMetadata(BaseModel):
    """Arbitrary metadata that can ride along with chat requests."""

    intent: Optional[str] = None
    currency: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    thread_id: Optional[str] = Field(
        default=None, description="Identifier used for checkpoint persistence."
    )
    metadata: Optional[ChatMetadata] = None


ComponentType = Literal[
    "text",
    "table",
    "chart",
    "metric_grid",
    "news_list",
    "alerts_panel",
    "portfolio",
    "watchlist",
    "follow_up",
    "asset_intel",
    "asset_overview",
    "compare_assets",
    "fundamentals_snapshot",
    "price_quotes",
    "trending_coins",
    "technical_analysis",
    "market_pulse",
]


class UIComponent(BaseModel):
    """Declarative UI block emitted by the agent."""

    type: ComponentType
    content: Optional[str] = None
    data: Dict[str, Any] | None = None
    chart_type: Optional[str] = Field(
        default=None,
        description="When type=chart, indicates line|area|candlestick|bar|donut.",
    )
    options: Dict[str, Any] | None = Field(
        default=None, description="Rendering hints such as currency, timeframe."
    )


class AgentStructuredResponse(BaseModel):
    """Top-level payload describing how the frontend should render the answer."""

    summary: Optional[str] = Field(
        default=None, description="Optional plain-language overview of the response."
    )
    responses: List[UIComponent] = Field(default_factory=list)


class ChatResponse(BaseModel):
    thread_id: str
    content: str
    used_tools: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    structured: AgentStructuredResponse | None = None


class PortfolioPosition(BaseModel):
    asset: str = Field(..., min_length=2, max_length=32)
    amount: float = Field(..., gt=0)
    cost_basis: float = Field(..., gt=0)


class PortfolioUpsertRequest(BaseModel):
    user_id: str = Field(..., min_length=3, max_length=64)
    position: PortfolioPosition


class PortfolioDeleteRequest(BaseModel):
    user_id: str
    position_id: str


class WatchlistRequest(BaseModel):
    user_id: str
    asset: str = Field(..., min_length=2, max_length=32)


class AlertCondition(BaseModel):
    type: Literal["price_move", "indicator_threshold"]
    asset: str = Field(..., min_length=1, max_length=32)
    window_minutes: Optional[int] = Field(default=60, ge=5, le=1440)
    percentage: Optional[float] = Field(default=None, ge=0.1, le=100)
    direction: Optional[Literal["drop", "rise"]] = None
    indicator: Optional[str] = None
    timeframe: Optional[str] = None
    operator: Optional[Literal["lt", "gt"]] = None
    threshold: Optional[float] = None


class AlertRequest(BaseModel):
    user_id: str
    description: str = Field(..., min_length=3, max_length=160)
    condition: AlertCondition
