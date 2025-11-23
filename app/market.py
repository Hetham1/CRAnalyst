"""Market data client abstractions backed by CoinGecko."""

from __future__ import annotations

import statistics
import time
from datetime import datetime, timezone
from typing import Iterable, List, Sequence
import logging

import requests
from requests import Response

from .models import MarketComparison, PriceQuote, TrendingCoin

logger = logging.getLogger(__name__)


class MarketDataError(RuntimeError):
    """Raised when market data cannot be retrieved."""


class CoinGeckoClient:
    """Lightweight CoinGecko REST client."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 15,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests.Session()

    def _request(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["x-cg-pro-api-key"] = self.api_key
        try:
            logger.info("CoinGecko request path=%s params=%s", path, params)
            response: Response = self.session.get(
                url, params=params, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            logger.debug("CoinGecko response status=%s path=%s", response.status_code, path)
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else ""
            logger.error("CoinGecko HTTP error %s body=%s", exc.response.status_code if exc.response else "?", body)
            raise MarketDataError(f"CoinGecko request failed: {exc} body={body}") from exc
        except requests.RequestException as exc:  # pragma: no cover - thin wrapper
            raise MarketDataError(f"CoinGecko request failed: {exc}") from exc
        try:
            return response.json()
        except ValueError as exc:  # pragma: no cover - invalid payload
            raise MarketDataError("CoinGecko returned invalid JSON") from exc

    def get_simple_price(self, assets: Sequence[str], currency: str) -> List[PriceQuote]:
        params = {
            "ids": ",".join(assets),
            "vs_currencies": currency,
            "include_24hr_change": "true",
            "include_market_cap": "true",
        }
        payload = self._request("simple/price", params=params)
        logger.debug("Parsed price payload for assets=%s", assets)
        quotes: list[PriceQuote] = []
        for asset, metrics in payload.items():
            price = metrics.get(currency)
            if price is None:
                continue
            quotes.append(
                PriceQuote(
                    asset=asset,
                    currency=currency,
                    price=float(price),
                    change_24h=metrics.get(f"{currency}_24h_change"),
                    market_cap=metrics.get(f"{currency}_market_cap"),
                )
            )
        return quotes

    def get_trending(self) -> List[TrendingCoin]:
        payload = self._request("search/trending")
        logger.debug("Trending payload entries=%s", len(payload.get("coins", [])))
        coins = payload.get("coins", [])
        trending: list[TrendingCoin] = []
        for entry in coins:
            item = entry.get("item", {})
            trending.append(
                TrendingCoin(
                    name=item.get("name", "Unknown"),
                    symbol=item.get("symbol", "").upper(),
                    score=entry.get("score", 0),
                    slug=item.get("id", ""),
                )
            )
        return trending

    def get_market_chart(self, asset: str, currency: str, days: int = 7) -> dict:
        params = {"vs_currency": currency, "days": days}
        return self._request(f"coins/{asset}/market_chart", params=params)

    def get_ohlc_chart(self, asset: str, currency: str, days: int = 7) -> list[list[float]]:
        params = {"vs_currency": currency, "days": days}
        return self._request(f"coins/{asset}/ohlc", params=params)

    def list_coins(self) -> list[dict]:
        params = {"include_platform": "false"}
        return self._request("coins/list", params=params)

    def get_coin_detail(self, asset: str) -> dict:
        params = {
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "false",
            "developer_data": "false",
            "sparkline": "false",
        }
        return self._request(f"coins/{asset}", params=params)

    def get_global_data(self) -> dict:
        return self._request("global")

    def get_markets(
        self,
        currency: str,
        *,
        per_page: int = 50,
        page: int = 1,
    ) -> list[dict]:
        per_page = min(max(per_page, 1), 250)
        params = {
            "vs_currency": currency,
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d",
        }
        return self._request("coins/markets", params=params)


COMMON_ASSET_OVERRIDES = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "ada": "cardano",
    "doge": "dogecoin",
    "matic": "polygon-pos",
    "dot": "polkadot",
    "bnb": "binancecoin",
    "xrp": "ripple",
    "ltc": "litecoin",
}


class MarketDataService:
    """High-level helpers that transform CoinGecko responses."""

    def __init__(self, client: CoinGeckoClient) -> None:
        self.client = client
        self._symbol_cache: dict[str, list[str]] = {}
        self._coin_ids: set[str] = set()
        self._cache_expiry = 0.0
        self.cache_ttl_seconds = 3600
        self._overview_cache: dict[tuple[str, str, int], tuple[float, dict]] = {}
        self.overview_cache_ttl = 60
        self._comparison_cache: dict[
            tuple[str, tuple[str, ...], str], tuple[float, list[MarketComparison]]
        ] = {}
        self.comparison_cache_ttl = 60

    def summarize_prices(self, assets: Sequence[str], currency: str) -> list[PriceQuote]:
        assets = self._resolve_assets(assets)
        if not assets:
            raise ValueError("At least one asset symbol is required.")
        logger.info("Summarize prices assets=%s currency=%s", assets, currency)
        return self.client.get_simple_price(assets, currency)

    def get_trending(self) -> list[TrendingCoin]:
        logger.info("Fetching trending coins")
        return self.client.get_trending()

    def resolve_symbol(self, asset: str) -> str:
        resolved = self._resolve_assets([asset])
        if not resolved:
            raise ValueError(f"Unknown asset symbol '{asset}'.")
        return resolved[0]

    def fetch_markets(self, currency: str, *, per_page: int = 50) -> list[dict]:
        logger.info("Fetching market board currency=%s per_page=%s", currency, per_page)
        return self.client.get_markets(currency, per_page=per_page)

    def get_global_snapshot(self, currency: str) -> dict:
        payload = self.client.get_global_data().get("data", {})
        total_mc = payload.get("total_market_cap", {}).get(currency, 0.0)
        total_vol = payload.get("total_volume", {}).get(currency, 0.0)
        dominance = payload.get("market_cap_percentage", {})
        return {
            "currency": currency,
            "market_cap": total_mc,
            "volume_24h": total_vol,
            "market_cap_change_24h_pct": payload.get("market_cap_change_percentage_24h_usd"),
            "active_cryptocurrencies": payload.get("active_cryptocurrencies"),
            "btc_dominance": dominance.get("btc"),
            "eth_dominance": dominance.get("eth"),
        }

    def normalized_history(self, assets: Sequence[str], currency: str, days: int = 90) -> list[dict]:
        series_collection: list[dict] = []
        for asset in assets:
            chart = self.client.get_market_chart(asset, currency, days)
            prices = chart.get("prices", [])
            if not prices:
                continue
            base = prices[0][1] or 1.0
            normalized: list[dict] = []
            for ts, price in prices:
                value = ((price - base) / base) * 100 if base else 0.0
                try:
                    iso = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
                except (ValueError, TypeError):
                    continue
                normalized.append({"timestamp": iso, "value": round(value, 2)})
            if normalized:
                series_collection.append({"asset": asset, "series": normalized})
        return series_collection

    def compare_assets(
        self, base: str, targets: Sequence[str], currency: str
    ) -> list[MarketComparison]:
        resolved = self._resolve_assets([base, *targets])
        base_id, target_ids = resolved[0], resolved[1:]
        logger.info("Comparing base=%s targets=%s currency=%s", base, targets, currency)
        assets = [base_id, *target_ids]
        cache_key = (base_id, tuple(target_ids), currency)
        now = time.time()
        cached = self._comparison_cache.get(cache_key)
        try:
            quotes = {
                quote.asset: quote
                for quote in self.client.get_simple_price(assets, currency)
            }
        except MarketDataError as exc:
            if cached and now - cached[0] < self.comparison_cache_ttl:
                logger.warning(
                    "CoinGecko compare failed (%s); serving cached data for %s/%s",
                    exc,
                    base_id,
                    currency,
                )
                return cached[1]
            raise
        comparisons: list[MarketComparison] = []
        base_quote = quotes.get(base_id)
        for target, target_id in zip(targets, target_ids):
            target_quote = quotes.get(target_id)
            spread = None
            if base_quote and target_quote and target_quote.price:
                spread = base_quote.price - target_quote.price
            comparisons.append(
                MarketComparison(
                    base=base_id,
                    target=target_id,
                    base_price=base_quote.price if base_quote else None,
                    target_price=target_quote.price if target_quote else None,
                    spread=spread,
                )
            )
        self._comparison_cache[cache_key] = (now, comparisons)
        return comparisons

    def fundamentals_snapshot(
        self, asset: str, currency: str, lookback_days: int = 7
    ) -> dict:
        asset_id = self._resolve_assets([asset])[0]
        chart = self.client.get_market_chart(asset_id, currency, lookback_days)
        logger.info(
            "Building fundamentals snapshot asset=%s currency=%s lookback=%s",
            asset,
            currency,
            lookback_days,
        )
        prices = [point[1] for point in chart.get("prices", [])]
        market_caps = [point[1] for point in chart.get("market_caps", [])]
        volumes = [point[1] for point in chart.get("total_volumes", [])]

        def _stats(series: Iterable[float]) -> dict:
            series = list(series)
            if not series:
                return {"min": None, "max": None, "avg": None}
            return {
                "min": min(series),
                "max": max(series),
                "avg": round(statistics.fmean(series), 4),
            }

        def _series(points: Iterable[List[float]]) -> list[dict]:
            data: list[dict] = []
            for ts, value in points:
                try:
                    iso = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
                except (ValueError, TypeError):
                    continue
                data.append({"timestamp": iso, "value": value})
            return data

        snapshot = {
            "asset": asset_id,
            "currency": currency,
            "price_stats": _stats(prices),
            "market_cap_stats": _stats(market_caps),
            "volume_stats": _stats(volumes),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "series": {
                "prices": _series(chart.get("prices", [])),
                "market_caps": _series(chart.get("market_caps", [])),
                "volumes": _series(chart.get("total_volumes", [])),
            },
        }
        return snapshot

    def asset_overview(self, asset: str, currency: str, lookback_days: int = 7) -> dict:
        asset_id = self._resolve_assets([asset])[0]
        cache_key = (asset_id, currency, lookback_days)
        now = time.time()
        cached = self._overview_cache.get(cache_key)
        if cached and now - cached[0] < self.overview_cache_ttl:
            logger.debug("Serving cached overview for %s/%s", asset_id, currency)
            return cached[1]

        logger.info("Building asset overview for asset=%s currency=%s", asset, currency)
        quotes = self.client.get_simple_price([asset_id], currency)
        quote = quotes[0] if quotes else None
        fundamentals = self.fundamentals_snapshot(asset, currency, lookback_days)
        detail = self.client.get_coin_detail(asset_id)
        market_data = detail.get("market_data", {})

        # Fetch OHLC data
        ohlc_data = self.client.get_ohlc_chart(asset_id, currency, lookback_days)
        ohlc_series = [
            {"timestamp": p[0], "open": p[1], "high": p[2], "low": p[3], "close": p[4]}
            for p in ohlc_data
        ]

        def _value(path, default=None):
            try:
                data = market_data
                for key in path:
                    data = data[key]
                return data
            except (KeyError, TypeError):
                return default

        current_price = quote.price if quote else _value(["current_price", currency])
        change_24h = quote.change_24h if quote else _value(["price_change_percentage_24h"])
        market_cap = quote.market_cap if quote else _value(["market_cap", currency])
        sparkline = market_data.get("sparkline_7d", {}).get("price", [])

        overview = {
            "asset": asset_id,
            "symbol": detail.get("symbol", "").upper(),
            "name": detail.get("name"),
            "currency": currency,
            "price": current_price,
            "change_24h": change_24h,
            "market_cap": market_cap,
            "volume_24h": _value(["total_volume", currency]),
            "market_cap_rank": market_data.get("market_cap_rank"),
            "circulating_supply": market_data.get("circulating_supply"),
            "total_supply": market_data.get("total_supply"),
            "max_supply": market_data.get("max_supply"),
            "ath_price": _value(["ath", currency]),
            "ath_change_pct": _value(["ath_change_percentage", currency]),
            "atl_price": _value(["atl", currency]),
            "atl_change_pct": _value(["atl_change_percentage", currency]),
            "last_updated": detail.get("last_updated"),
            "fundamentals": fundamentals,
            "sparkline": sparkline,
            "series": fundamentals.get("series", {}),
            "ohlc_series": ohlc_series,  # NEW: Add OHLC series here
        }
        self._overview_cache[cache_key] = (now, overview)
        return overview

    def _resolve_assets(self, assets: Sequence[str]) -> list[str]:
        cleaned = [asset.lower().strip() for asset in assets if asset]
        if not cleaned:
            return []
        resolved: list[str] = []
        for asset in cleaned:
            resolved.append(self._resolve_single_asset(asset))
        return resolved

    def _resolve_single_asset(self, asset: str) -> str:
        if asset in COMMON_ASSET_OVERRIDES:
            return COMMON_ASSET_OVERRIDES[asset]
        self._ensure_registry()
        if asset in self._coin_ids:
            return asset
        candidates = self._symbol_cache.get(asset)
        if not candidates:
            return asset
        choice = self._pick_candidate(asset, candidates)
        logger.debug("Resolved symbol %s -> %s", asset, choice)
        return choice

    def _pick_candidate(self, symbol: str, candidates: list[str]) -> str:
        for candidate in candidates:
            if candidate.startswith(symbol):
                return candidate
        return sorted(candidates)[0]

    def _ensure_registry(self) -> None:
        now = time.time()
        if now < self._cache_expiry and self._symbol_cache:
            return
        try:
            coins = self.client.list_coins()
        except MarketDataError as exc:
            logger.warning("Could not refresh coin cache: %s", exc)
            self._cache_expiry = now + 120  # retry soon
            return
        symbol_map: dict[str, list[str]] = {}
        id_set: set[str] = set()
        for entry in coins:
            coin_id = entry.get("id", "").lower()
            symbol = entry.get("symbol", "").lower()
            if coin_id:
                id_set.add(coin_id)
            if symbol and coin_id:
                symbol_map.setdefault(symbol, []).append(coin_id)
        self._symbol_cache = symbol_map
        self._coin_ids = id_set
        self._cache_expiry = now + self.cache_ttl_seconds
        logger.info("Loaded %s coin identifiers into cache", len(id_set))
