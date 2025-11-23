"""LangChain tool definitions for the Crypto Analyst agent."""

from __future__ import annotations

from typing import List
import logging

from langchain_core.tools import tool

from .market import MarketDataError, MarketDataService
from .services import (
    AlertService,
    AdvancedComparisonService,
    CryptoNewsService,
    MarketPulseService,
    OnChainService,
    PortfolioService,
    TechnicalAnalysisService,
)

logger = logging.getLogger(__name__)


def _serialize_quotes(quotes):
    return [
        {
            "asset": quote.asset,
            "currency": quote.currency,
            "price": quote.price,
            "change_24h": quote.change_24h,
            "market_cap": quote.market_cap,
        }
        for quote in quotes
    ]


def _serialize_trending(entries):
    return [
        {"name": item.name, "symbol": item.symbol, "score": item.score, "slug": item.slug}
        for item in entries
    ]


def build_market_tools(
    market_service: MarketDataService,
    *,
    news_service: CryptoNewsService,
    onchain_service: OnChainService,
    technical_service: TechnicalAnalysisService,
    portfolio_service: PortfolioService,
    alert_service: AlertService,
    pulse_service: MarketPulseService,
    comparison_service: AdvancedComparisonService,
):
    """Return the full list of LangChain tools backed by market + user services."""

    @tool("market_pulse")
    def market_pulse(currency: str = "usd") -> dict:
        """Return a global view of market cap, movers, news, and sentiment."""

        try:
            return pulse_service.build_pulse(currency)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("market_pulse failed: %s", exc)
            return {"error": str(exc)}

    @tool("asset_intel")
    def asset_intel(asset: str, currency: str = "usd") -> dict:
        """Return price, fundamentals, news, sentiment, and on-chain context for an asset."""

        try:
            overview = market_service.asset_overview(asset, currency, lookback_days=7)
        except (ValueError, MarketDataError) as exc:
            return {"error": str(exc)}
        news_items = news_service.fetch_for_asset(asset, limit=3)
        sentiment = news_service.summarize_sentiment(news_items)
        try:
            onchain = onchain_service.snapshot(asset)
        except ValueError:
            onchain = None

        # Extract candlestick data if available from the overview
        candlestick_series = []
        if overview and overview.get("ohlc_series"):
            candlestick_series = overview["ohlc_series"]

        response_data = {
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

        if candlestick_series:
            response_data["chart_type"] = "candlestick"
            response_data["series"] = candlestick_series

        return response_data

    @tool("get_price_quotes")
    def get_price_quotes(assets: List[str], currency: str = "usd") -> dict:
        """Return latest price, market cap, and 24h change for the requested assets."""

        try:
            quotes = market_service.summarize_prices(assets, currency)
        except (ValueError, MarketDataError) as exc:
            logger.warning("get_price_quotes failed: %s", exc)
            return {"error": str(exc)}
        logger.info("get_price_quotes served %s assets", len(quotes))
        return {"quotes": _serialize_quotes(quotes), "currency": currency}

    @tool("compare_assets")
    def compare_assets(base: str, targets: List[str], currency: str = "usd") -> dict:
        """Compare base asset price against a list of targets."""

        try:
            comparisons = market_service.compare_assets(base, targets, currency)
        except (ValueError, MarketDataError) as exc:
            logger.warning("compare_assets failed: %s", exc)
            return {"error": str(exc)}
        logger.info("compare_assets base=%s comparisons=%s", base, len(comparisons))
        return {
            "base": base,
            "comparisons": [
                {
                    "target": item.target,
                    "base_price": item.base_price,
                    "target_price": item.target_price,
                    "spread": item.spread,
                }
                for item in comparisons
            ],
            "currency": currency,
        }

    @tool("advanced_compare")
    def advanced_compare(assets: List[str], currency: str = "usd") -> dict:
        """Return multi-metric comparison (TPS, dev activity, 90d performance)."""

        if len(assets) < 2:
            return {"error": "Provide at least two assets for advanced comparison."}
        try:
            return comparison_service.compare(assets, currency)
        except Exception as exc:  # pragma: no cover - upstream API error
            logger.warning("advanced_compare failed: %s", exc)
            return {"error": str(exc)}

    @tool("technical_analysis")
    def technical_analysis(asset: str, indicator: str = "rsi", timeframe: str = "4h", currency: str = "usd") -> dict:
        """Return indicator readings (currently RSI) with candlestick series."""

        try:
            return technical_service.analyze(
                asset=asset,
                currency=currency,
                indicator=indicator,
                timeframe=timeframe,
            )
        except Exception as exc:
            logger.warning("technical_analysis failed: %s", exc)
            return {"error": str(exc)}

    @tool("fundamentals_snapshot")
    def fundamentals_snapshot(asset: str, currency: str = "usd", lookback_days: int = 7) -> dict:
        """Return recent price, market cap, and volume stats for the asset."""

        try:
            snapshot = market_service.fundamentals_snapshot(asset, currency, lookback_days)
        except MarketDataError as exc:
            logger.warning("fundamentals_snapshot failed: %s", exc)
            return {"error": str(exc)}
        logger.info("fundamentals_snapshot asset=%s currency=%s", asset, currency)
        return snapshot

    @tool("asset_overview")
    def asset_overview(asset: str, currency: str = "usd", lookback_days: int = 7) -> dict:
        """Return a comprehensive view (price, change, market cap, supply, 7d stats)."""

        try:
            overview = market_service.asset_overview(asset, currency, lookback_days)
        except (ValueError, MarketDataError) as exc:
            logger.warning("asset_overview failed: %s", exc)
            return {"error": str(exc)}
        return overview

    @tool("onchain_activity")
    def onchain_activity(asset: str) -> dict:
        """Return whale + network growth heuristics for BTC/ETH-family chains."""

        try:
            return onchain_service.snapshot(asset)
        except ValueError as exc:
            return {"error": str(exc)}

    @tool("portfolio_snapshot")
    def portfolio_snapshot(user_id: str, currency: str = "usd") -> dict:
        """Return holdings, totals, and allocation breakdown for a user."""

        return portfolio_service.summarize_portfolio(user_id, currency)

    @tool("watchlist_status")
    def watchlist_status(user_id: str) -> dict:
        """Return the user's pinned watchlist symbols."""

        return {"user_id": user_id, "watchlist": portfolio_service.get_watchlist(user_id)}

    @tool("alert_status")
    def alert_status(user_id: str, currency: str = "usd") -> dict:
        """Evaluate pending alerts (price moves, indicator thresholds)."""

        alerts = alert_service.evaluate_alerts(user_id, currency)
        return {"user_id": user_id, "alerts": alerts}

    return [
        market_pulse,
        asset_intel,
        get_price_quotes,
        compare_assets,
        advanced_compare,
        technical_analysis,
        fundamentals_snapshot,
        asset_overview,
        onchain_activity,
        portfolio_snapshot,
        watchlist_status,
        alert_status,
    ]
