import asyncio
import os
from datetime import datetime, timezone

os.environ.setdefault("TESTING", "1")

import pytest
from fastapi.testclient import TestClient

from app.agent import TestingToolAwareChatModel
from app.config import Settings
from app.main import create_app
from app.models import MarketComparison, PriceQuote, TrendingCoin


class StubMarketService:
    def __init__(self):
        self.client = self

    def summarize_prices(self, assets, currency):
        return [
            PriceQuote(
                asset=asset,
                currency=currency,
                price=68000.0,
                change_24h=1.2,
                market_cap=1_000_000_000,
            )
            for asset in assets
        ]

    def compare_assets(self, base, targets, currency):
        return [
            MarketComparison(
                base=base,
                target=target,
                base_price=68000.0,
                target_price=3400.0,
                spread=64600.0,
            )
            for target in targets
        ]

    def get_trending(self):
        return [
            TrendingCoin(name="Bitcoin", symbol="BTC", score=1, slug="bitcoin"),
            TrendingCoin(name="Ethereum", symbol="ETH", score=2, slug="ethereum"),
        ]

    def fetch_markets(self, currency, per_page=50):
        return [
            {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "current_price": 68000.0,
                "price_change_percentage_24h_in_currency": 2.1,
                "market_cap": 1_200_000_000_000,
            },
            {
                "id": "ethereum",
                "symbol": "eth",
                "name": "Ethereum",
                "current_price": 3400.0,
                "price_change_percentage_24h_in_currency": -1.0,
                "market_cap": 420_000_000_000,
            },
        ]

    def get_global_snapshot(self, currency):
        return {
            "currency": currency,
            "market_cap": 2_300_000_000_000,
            "volume_24h": 52_000_000_000,
            "market_cap_change_24h_pct": 1.4,
            "active_cryptocurrencies": 12000,
            "btc_dominance": 55.0,
            "eth_dominance": 18.0,
        }

    def normalized_history(self, assets, currency, days=90):
        data = []
        for asset in assets:
            data.append(
                {
                    "asset": asset,
                    "series": [
                        {"timestamp": "2024-01-01T00:00:00Z", "value": 0},
                        {"timestamp": "2024-02-01T00:00:00Z", "value": 10},
                    ],
                }
            )
        return data

    def resolve_symbol(self, asset):
        return asset

    def fundamentals_snapshot(self, asset, currency, lookback_days=7):
        series_point = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "value": 100.0,
        }
        return {
            "asset": asset,
            "currency": currency,
            "price_stats": {"avg": 100.0, "min": 95.0, "max": 105.0},
            "market_cap_stats": {"avg": 200.0, "min": 190.0, "max": 210.0},
            "volume_stats": {"avg": 300.0, "min": 250.0, "max": 320.0},
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "series": {
                "prices": [series_point],
                "market_caps": [series_point],
                "volumes": [series_point],
            },
        }

    def asset_overview(self, asset, currency, lookback_days=7):
        fundamentals = self.fundamentals_snapshot(asset, currency, lookback_days)
        return {
            "asset": "bitcoin",
            "symbol": "BTC",
            "name": "Bitcoin",
            "currency": currency,
            "price": 68000.0,
            "change_24h": 2.0,
            "market_cap": 2_000_000_000,
            "volume_24h": 500_000_000,
            "market_cap_rank": 1,
            "circulating_supply": 19000000,
            "total_supply": 21000000,
            "max_supply": 21000000,
            "ath_price": 69000.0,
            "ath_change_pct": -2.0,
            "atl_price": 65.0,
            "atl_change_pct": 99999.0,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "fundamentals": fundamentals,
            "sparkline": [p["value"] for p in fundamentals["series"]["prices"]],
            "series": fundamentals["series"],
        }

    def get_market_chart(self, asset, currency, days):
        base_series = [[0, 100.0], [1, 102.0], [2, 105.0], [3, 107.0]]
        return {"prices": base_series}


class StubNewsService:
    def fetch_news(self, limit=3, categories=None, assets=None):
        return []

    def fetch_for_asset(self, asset, limit=3):
        return []

    def summarize_sentiment(self, items):
        return {"score": 0, "label": "neutral", "keywords": []}


class StubOnChainService:
    def snapshot(self, asset: str):
        return {
            "asset": asset,
            "network": asset,
            "whale_activity": {"state": "balanced"},
            "network_growth": {"state": "steady"},
        }


class StubPulseService:
    def build_pulse(self, currency: str):
        return {
            "global": {
                "currency": currency,
                "market_cap": 1_000_000,
                "volume_24h": 10_000,
                "market_cap_change_24h_pct": 0.5,
                "btc_dominance": 50,
                "eth_dominance": 20,
            },
            "gainers": [],
            "losers": [],
            "categories": [],
            "news": [],
            "sentiment": {"news": {"label": "neutral"}, "fear_greed": {"value": 50}},
        }


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def test_app(tmp_path):
    os.environ["TESTING"] = "1"
    sqlite_path = tmp_path / "agent.db"
    settings = Settings(
        testing=True,
        sqlite_db_path=str(sqlite_path),
        default_thread_id="test-thread",
        google_api_key=None,
    )
    test_llm = TestingToolAwareChatModel(responses=["Mock crypto insight."])
    market_service = StubMarketService()
    news_service = StubNewsService()
    onchain_service = StubOnChainService()
    pulse_service = StubPulseService()
    app = create_app(
        settings_override=settings,
        llm_override=test_llm,
        market_service_override=market_service,
    )
    app.state.market_service = market_service
    app.state.news_service = news_service
    app.state.onchain_service = onchain_service
    app.state.pulse_service = pulse_service
    with TestClient(app) as client:
        yield client
