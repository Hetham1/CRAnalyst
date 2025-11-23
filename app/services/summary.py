"""Higher-level market insight services (pulse + comparisons)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Sequence
import logging
import time

import requests

from ..market import MarketDataService
from .news import CryptoNewsService
from .reference import get_reference

logger = logging.getLogger(__name__)


class MarketPulseService:
    def __init__(self, market_service: MarketDataService, news_service: CryptoNewsService) -> None:
        self.market_service = market_service
        self.news_service = news_service
        self._fear_cache: tuple[float, dict] | None = None
        self.fear_cache_ttl = 600.0

    def build_pulse(self, currency: str) -> dict:
        markets = self.market_service.fetch_markets(currency, per_page=50)
        global_stats = self.market_service.get_global_snapshot(currency)
        gainers = sorted(
            markets,
            key=lambda coin: coin.get("price_change_percentage_24h_in_currency") or 0,
            reverse=True,
        )[:3]
        losers = sorted(
            markets,
            key=lambda coin: coin.get("price_change_percentage_24h_in_currency") or 0,
        )[:3]
        categories = self._category_performance(markets)
        news_items = self.news_service.fetch_news(limit=3)
        sentiment = self.news_service.summarize_sentiment(news_items)
        fear_greed = self._fetch_fear_greed()
        return {
            "global": global_stats,
            "gainers": _slim_markets(gainers),
            "losers": _slim_markets(losers),
            "categories": categories,
            "news": [
                {
                    "title": item.title,
                    "source": item.source,
                    "url": item.url,
                    "published_at": item.published_at,
                }
                for item in news_items
            ],
            "sentiment": {
                "news": sentiment,
                "fear_greed": fear_greed,
            },
        }

    def _category_performance(self, markets: Sequence[dict]) -> List[dict]:
        buckets: dict[str, dict] = {}
        for coin in markets:
            ref = get_reference(coin.get("id", ""))
            category = ref.get("category") if ref else "other"
            bucket = buckets.setdefault(
                category,
                {"category": category, "market_cap": 0.0, "avg_change": 0.0, "count": 0},
            )
            bucket["market_cap"] += coin.get("market_cap") or 0.0
            bucket["avg_change"] += coin.get("price_change_percentage_24h_in_currency") or 0.0
            bucket["count"] += 1
        for bucket in buckets.values():
            count = bucket["count"] or 1
            bucket["avg_change"] = round(bucket["avg_change"] / count, 2)
        return sorted(buckets.values(), key=lambda item: item["market_cap"], reverse=True)[:6]

    def _fetch_fear_greed(self) -> dict:
        now = time.time()
        if self._fear_cache and now - self._fear_cache[0] < self.fear_cache_ttl:
            return self._fear_cache[1]
        try:
            response = requests.get(
                "https://api.alternative.me/fng/?limit=1&format=json", timeout=8
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", [{}])[0]
            gauge = {
                "value": int(data.get("value", 50)),
                "classification": data.get("value_classification", "Neutral"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        except requests.RequestException:
            gauge = {"value": 50, "classification": "Neutral", "updated_at": None}
        self._fear_cache = (now, gauge)
        return gauge


class AdvancedComparisonService:
    def __init__(self, market_service: MarketDataService) -> None:
        self.market_service = market_service

    def compare(self, assets: Sequence[str], currency: str) -> dict:
        resolved = [self.market_service.resolve_symbol(asset) for asset in assets]
        normalized = self.market_service.normalized_history(resolved, currency, days=90)
        metrics: list[dict] = []
        for asset_id in resolved:
            ref = get_reference(asset_id) or {}
            performance = next(
                (series for series in normalized if series["asset"] == asset_id), None
            )
            ninety_day = performance["series"][-1]["value"] if performance and performance["series"] else 0.0
            metrics.append(
                {
                    "asset": asset_id,
                    "transaction_speed_tps": ref.get("transaction_speed_tps"),
                    "developer_activity_score": ref.get("developer_activity_score"),
                    "avg_fee_usd": ref.get("avg_fee_usd"),
                    "consensus": ref.get("consensus"),
                    "narrative": ref.get("narrative"),
                    "performance_90d_pct": round(ninety_day, 2),
                }
            )
        return {
            "currency": currency,
            "normalized_history": normalized,
            "metrics": metrics,
        }


def _slim_markets(entries: Sequence[dict]) -> List[dict]:
    results = []
    for coin in entries:
        results.append(
            {
                "id": coin.get("id"),
                "symbol": coin.get("symbol"),
                "name": coin.get("name"),
                "price": coin.get("current_price"),
                "change_24h": coin.get("price_change_percentage_24h_in_currency"),
                "market_cap": coin.get("market_cap"),
            }
        )
    return results
