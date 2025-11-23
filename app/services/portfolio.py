"""Persistent portfolio + watchlist helpers backed by a JSON store."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
import threading
import uuid

from ..market import MarketDataService


class AgentDataStore:
    """Minimal JSON store (thread-safe) for user specific data."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self.path.exists():
            self._write({"users": {}})

    def _read(self) -> Dict:
        with self._lock:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {"users": {}}
            return data

    def _write(self, data: Dict) -> None:
        with self._lock:
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_user_state(self, user_id: str) -> Dict:
        data = self._read()
        users = data.setdefault("users", {})
        state = users.setdefault(
            user_id,
            {"portfolio": {"positions": []}, "watchlist": [], "alerts": []},
        )
        return state

    def update_user_state(self, user_id: str, state: Dict) -> None:
        data = self._read()
        data.setdefault("users", {})[user_id] = state
        self._write(data)


class PortfolioService:
    """Business logic for holdings, watchlists, and valuations."""

    def __init__(self, store: AgentDataStore, market_service: MarketDataService) -> None:
        self.store = store
        self.market_service = market_service

    def add_position(self, user_id: str, asset: str, amount: float, cost_basis: float) -> Dict:
        state = self.store.get_user_state(user_id)
        positions: list[dict] = state.setdefault("portfolio", {}).setdefault("positions", [])
        position = {
            "id": uuid.uuid4().hex,
            "asset": asset.lower(),
            "amount": amount,
            "cost_basis": cost_basis,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        positions.append(position)
        self.store.update_user_state(user_id, state)
        return position

    def delete_position(self, user_id: str, position_id: str) -> None:
        state = self.store.get_user_state(user_id)
        positions = state.setdefault("portfolio", {}).setdefault("positions", [])
        state["portfolio"]["positions"] = [pos for pos in positions if pos.get("id") != position_id]
        self.store.update_user_state(user_id, state)

    def add_watch_asset(self, user_id: str, asset: str) -> List[str]:
        state = self.store.get_user_state(user_id)
        watchlist = state.setdefault("watchlist", [])
        symbol = asset.lower()
        if symbol not in watchlist:
            watchlist.append(symbol)
        self.store.update_user_state(user_id, state)
        return watchlist

    def remove_watch_asset(self, user_id: str, asset: str) -> List[str]:
        state = self.store.get_user_state(user_id)
        watchlist = state.setdefault("watchlist", [])
        symbol = asset.lower()
        state["watchlist"] = [item for item in watchlist if item != symbol]
        self.store.update_user_state(user_id, state)
        return state["watchlist"]

    def get_watchlist(self, user_id: str) -> List[str]:
        state = self.store.get_user_state(user_id)
        return state.get("watchlist", [])

    def summarize_portfolio(self, user_id: str, currency: str) -> Dict:
        state = self.store.get_user_state(user_id)
        positions = state.get("portfolio", {}).get("positions", [])
        assets = sorted({pos["asset"] for pos in positions})
        quotes = self._fetch_quotes(assets, currency)
        rows = []
        total_value = 0.0
        total_cost = 0.0
        for pos in positions:
            quote = quotes.get(pos["asset"])
            price = quote.price if quote else 0.0
            current_value = price * pos["amount"]
            cost_value = pos["amount"] * pos["cost_basis"]
            pnl_abs = current_value - cost_value
            pnl_pct = (pnl_abs / cost_value * 100) if cost_value else 0.0
            total_value += current_value
            total_cost += cost_value
            rows.append(
                {
                    "id": pos["id"],
                    "asset": pos["asset"],
                    "amount": pos["amount"],
                    "cost_basis": pos["cost_basis"],
                    "current_price": price,
                    "current_value": current_value,
                    "pnl_abs": pnl_abs,
                    "pnl_pct": pnl_pct,
                }
            )
        total_change = total_value - total_cost
        totals = {
            "invested": total_cost,
            "value": total_value,
            "pnl_abs": total_change,
            "pnl_pct": (total_change / total_cost * 100) if total_cost else 0.0,
        }
        breakdown = [
            {
                "asset": row["asset"],
                "value": row["current_value"],
                "weight_pct": (row["current_value"] / total_value * 100) if total_value else 0,
            }
            for row in rows
        ]
        return {
            "user_id": user_id,
            "currency": currency,
            "positions": rows,
            "totals": totals,
            "breakdown": breakdown,
            "watchlist": state.get("watchlist", []),
        }

    def _fetch_quotes(self, assets: List[str], currency: str):
        if not assets:
            return {}
        quotes = self.market_service.summarize_prices(assets, currency)
        return {quote.asset: quote for quote in quotes}
