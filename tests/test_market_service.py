from app.market import MarketDataService
from app.models import PriceQuote, TrendingCoin


class StubClient:
    def __init__(self):
        self.simple_price_calls = []

    def get_simple_price(self, assets, currency):
        self.simple_price_calls.append((tuple(assets), currency))
        return [
            PriceQuote(asset="bitcoin", currency=currency, price=68000.0, change_24h=1.2, market_cap=1.3e12),
            PriceQuote(asset="ethereum", currency=currency, price=3400.0, change_24h=-0.5, market_cap=4.1e11),
        ]

    def get_trending(self):
        return [
            TrendingCoin(name="Bitcoin", symbol="BTC", score=0, slug="bitcoin"),
            TrendingCoin(name="Ethereum", symbol="ETH", score=1, slug="ethereum"),
        ]

    def get_market_chart(self, asset, currency, days):
        base = [
            [0, 100],
            [1, 200],
            [2, 300],
        ]
        return {"prices": base, "market_caps": base, "total_volumes": base}

    def list_coins(self):
        return [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
            {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
            {"id": "batcat", "symbol": "btc", "name": "Bat Cat"},
        ]

    def get_coin_detail(self, asset):
        return {
            "id": asset,
            "symbol": "btc",
            "name": "Bitcoin",
            "market_data": {
                "current_price": {"usd": 100.0},
                "price_change_percentage_24h": 1.5,
                "market_cap": {"usd": 2_000_000},
                "total_volume": {"usd": 500_000},
                "market_cap_rank": 1,
                "circulating_supply": 19000000,
                "total_supply": 21000000,
                "max_supply": 21000000,
                "ath": {"usd": 69000},
                "ath_change_percentage": {"usd": -10},
                "atl": {"usd": 65},
                "atl_change_percentage": {"usd": 99999},
            },
            "last_updated": "2024-01-01T00:00:00Z",
        }


def test_summarize_prices_returns_quotes():
    service = MarketDataService(StubClient())
    quotes = service.summarize_prices(["BTC", "ETH"], "usd")
    assert len(quotes) == 2
    assert quotes[0].asset == "bitcoin"


def test_trending_returns_items():
    service = MarketDataService(StubClient())
    trending = service.get_trending()
    assert len(trending) == 2
    assert trending[0].symbol == "BTC"


def test_fundamentals_snapshot_has_stats():
    service = MarketDataService(StubClient())
    snapshot = service.fundamentals_snapshot("bitcoin", "usd", 3)
    assert snapshot["price_stats"]["avg"] == 200.0


def test_symbol_resolution_prefers_primary_coin():
    service = MarketDataService(StubClient())
    service.summarize_prices(["BTC"], "usd")
    assets, _ = service.client.simple_price_calls[0]
    assert assets == ("bitcoin",)


def test_asset_overview_merges_detail_and_fundamentals():
    service = MarketDataService(StubClient())
    overview = service.asset_overview("bitcoin", "usd", 3)
    assert overview["price"] == 68000.0  # from simple price stub
    assert overview["fundamentals"]["price_stats"]["avg"] == 200.0
    assert overview["circulating_supply"] == 19000000
