"""Technical indicator calculations built on CoinGecko market charts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

from ..market import MarketDataService


TIMEFRAME_TO_MINUTES = {
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "6h": 360,
    "12h": 720,
    "1d": 1440,
}


class TechnicalAnalysisService:
    def __init__(self, market_service: MarketDataService) -> None:
        self.market_service = market_service

    def analyze(
        self,
        *,
        asset: str,
        currency: str,
        indicator: str = "rsi",
        timeframe: str = "4h",
        period: int = 14,
    ) -> dict:
        symbol = self.market_service.resolve_symbol(asset)
        minutes = TIMEFRAME_TO_MINUTES.get(timeframe, 240)
        days = max(1, minutes // 1440 + 1)
        chart = self.market_service.client.get_market_chart(symbol, currency, days)
        prices = chart.get("prices", [])
        candles = self._build_candles(prices, minutes)
        closes = [candle["close"] for candle in candles]
        value = None
        interpretation = "insufficient data"
        state = "unknown"
        if indicator.lower() == "rsi" and len(closes) >= period + 2:
            value = self._compute_rsi(closes, period)
            if value >= 70:
                state = "overbought"
                interpretation = f"RSI is {value:.1f}, historically stretched; upside momentum may fade."
            elif value <= 30:
                state = "oversold"
                interpretation = f"RSI is {value:.1f}, indicating potential relief if buyers return."
            else:
                state = "neutral"
                interpretation = f"RSI sits at {value:.1f}, showing balanced momentum."
        return {
            "asset": symbol,
            "currency": currency,
            "indicator": indicator,
            "timeframe": timeframe,
            "value": round(value, 2) if value is not None else None,
            "state": state,
            "interpretation": interpretation,
            "series": candles[-90:],
        }

    def _build_candles(self, prices: List[List[float]], bucket_minutes: int) -> List[dict]:
        if not prices:
            return []
        bucket_ms = bucket_minutes * 60 * 1000
        candles: list[dict] = []
        current_bucket = None
        for timestamp, price in prices:
            bucket = int(timestamp // bucket_ms * bucket_ms)
            if current_bucket != bucket:
                candle = {
                    "timestamp": datetime.fromtimestamp(bucket / 1000, tz=timezone.utc).isoformat(),
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                }
                candles.append(candle)
                current_bucket = bucket
            else:
                candle = candles[-1]
                candle["high"] = max(candle["high"], price)
                candle["low"] = min(candle["low"], price)
                candle["close"] = price
        return candles

    def _compute_rsi(self, closes: List[float], period: int) -> float:
        gains = []
        losses = []
        for prev, curr in self._pairwise(closes[-(period + 15):]):
            change = curr - prev
            (gains if change > 0 else losses).append(abs(change))
        avg_gain = sum(gains[-period:]) / period if gains[-period:] else 0.0
        avg_loss = sum(losses[-period:]) / period if losses[-period:] else 0.0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

    def _pairwise(self, sequence: List[float]) -> List[Tuple[float, float]]:
        return list(zip(sequence[:-1], sequence[1:]))
