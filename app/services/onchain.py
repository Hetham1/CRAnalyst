"""On-chain heuristics built on top of Blockchair stats."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict
import logging

import requests
from requests import Response

logger = logging.getLogger(__name__)


NETWORK_MAP = {
    "btc": "bitcoin",
    "bitcoin": "bitcoin",
    "eth": "ethereum",
    "ethereum": "ethereum",
    "ltc": "litecoin",
    "litecoin": "litecoin",
    "doge": "dogecoin",
    "dogecoin": "dogecoin",
    "bch": "bitcoin-cash",
    "bitcoin-cash": "bitcoin-cash",
}


class OnChainService:
    """Fetch lightweight whale + network growth signals."""

    def __init__(
        self,
        base_url: str = "https://api.blockchair.com",
        api_key: str | None = None,
        timeout: int = 10,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._cache: dict[str, tuple[float, dict]] = {}
        self.cache_ttl = 180.0

    def _resolve_network(self, asset: str) -> str:
        symbol = (asset or "").lower()
        if symbol in NETWORK_MAP:
            return NETWORK_MAP[symbol]
        raise ValueError(f"On-chain data is not available for {asset}.")

    def _request(self, network: str) -> Dict:
        url = f"{self.base_url}/{network}/stats"
        params = {"key": self.api_key} if self.api_key else None
        try:
            response: Response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.HTTPError as exc:
            logger.warning("Blockchair request failed network=%s status=%s", network, exc.response.status_code if exc.response else "?")
            raise
        return response.json()

    def snapshot(self, asset: str) -> dict:
        network = self._resolve_network(asset)
        cache_key = network
        now = datetime.now(timezone.utc).timestamp()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < self.cache_ttl:
            return cached[1]

        payload = self._request(network)
        stats = payload.get("data", {})
        context = payload.get("context", {})

        market_cap = float(stats.get("market_cap_usd") or 0.0)
        largest_tx = stats.get("largest_transaction_24h") or {}
        largest_tx_usd = float(largest_tx.get("value_usd") or 0.0)
        whale_ratio = 0.0
        if market_cap > 0 and largest_tx_usd:
            whale_ratio = largest_tx_usd / market_cap
        mempool_tps = float(stats.get("mempool_tps") or 0.0)
        mempool_tx = float(stats.get("mempool_transactions") or 0.0)
        tx_24h = float(stats.get("transactions_24h") or 0.0)
        hodlers = int(stats.get("hodling_addresses") or 0)

        if whale_ratio > 0.004:
            whale_state = "aggressive accumulation"
        elif whale_ratio > 0.0015:
            whale_state = "steady accumulation"
        elif whale_ratio < 0.0003 and largest_tx_usd:
            whale_state = "distribution"
        else:
            whale_state = "balanced"

        network_heat = 0.0
        if tx_24h:
            network_heat = (mempool_tx / tx_24h) * 100

        if network_heat > 40:
            growth_state = "network demand is spiking"
        elif network_heat > 20:
            growth_state = "usage is trending higher"
        elif network_heat < 10:
            growth_state = "activity is subdued"
        else:
            growth_state = "activity is steady"

        snapshot = {
            "asset": asset.lower(),
            "network": network,
            "whale_activity": {
                "state": whale_state,
                "largest_transaction_usd": largest_tx_usd,
                "market_cap_usd": market_cap,
                "ratio": round(whale_ratio, 6),
                "mempool_tps": mempool_tps,
            },
            "network_growth": {
                "state": growth_state,
                "mempool_transactions": mempool_tx,
                "transactions_24h": tx_24h,
                "hodling_addresses": hodlers,
                "heat_pct": round(network_heat, 2),
            },
            "best_block_time": stats.get("best_block_time") or context.get("time"),
        }
        self._cache[cache_key] = (now, snapshot)
        return snapshot
