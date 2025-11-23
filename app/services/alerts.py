"""Alert engine that evaluates price + indicator conditions on demand."""

from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import Dict, List
import uuid

from ..market import MarketDataService
from .portfolio import AgentDataStore, PortfolioService
from .technical import TechnicalAnalysisService


class AlertService:
    def __init__(
        self,
        store: AgentDataStore,
        market_service: MarketDataService,
        technical_service: TechnicalAnalysisService,
        portfolio_service: PortfolioService,
    ) -> None:
        self.store = store
        self.market_service = market_service
        self.technical_service = technical_service
        self.portfolio_service = portfolio_service

    def add_alert(self, user_id: str, description: str, condition: Dict) -> Dict:
        state = self.store.get_user_state(user_id)
        alerts = state.setdefault("alerts", [])
        alert = {
            "id": uuid.uuid4().hex,
            "description": description,
            "condition": condition,
            "status": "armed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_observed": None,
            "triggered_at": None,
        }
        alerts.append(alert)
        self.store.update_user_state(user_id, state)
        return alert

    def delete_alert(self, user_id: str, alert_id: str) -> None:
        state = self.store.get_user_state(user_id)
        alerts = state.setdefault("alerts", [])
        state["alerts"] = [alert for alert in alerts if alert.get("id") != alert_id]
        self.store.update_user_state(user_id, state)

    def list_alerts(self, user_id: str) -> List[Dict]:
        state = self.store.get_user_state(user_id)
        return state.get("alerts", [])

    def evaluate_alerts(self, user_id: str, currency: str) -> List[Dict]:
        state = self.store.get_user_state(user_id)
        alerts = state.get("alerts", [])
        evaluated: list[dict] = []
        for alert in alerts:
            condition = alert.get("condition", {})
            if condition.get("type") == "price_move":
                result = self._evaluate_price_alert(condition, currency, user_id)
            elif condition.get("type") == "indicator_threshold":
                result = self._evaluate_indicator_alert(condition, currency)
            else:
                result = {"status": "unsupported", "condition": condition}
            alert["status"] = result.get("status", alert.get("status"))
            alert["last_observed"] = result.get("observed_value")
            if result.get("triggered_at"):
                alert["triggered_at"] = result["triggered_at"]
            alert["context"] = result.get("context")
            evaluated.append(alert)
        state["alerts"] = alerts
        self.store.update_user_state(user_id, state)
        return evaluated

    def _evaluate_price_alert(self, condition: Dict, currency: str, user_id: str) -> Dict:
        direction = condition.get("direction", "drop")
        percentage = float(condition.get("percentage") or 0)
        asset = condition.get("asset") or "*"
        window = int(condition.get("window_minutes") or 60)
        targets: list[str]
        if asset == "*":
            snapshot = self.portfolio_service.summarize_portfolio(user_id, currency)
            targets = [row["asset"] for row in snapshot.get("positions", [])]
        else:
            targets = [asset]
        triggered_assets: list[dict] = []
        for symbol in targets:
            change_pct, latest = self._price_change(symbol, currency, window)
            condition_met = (
                change_pct <= -percentage if direction == "drop" else change_pct >= percentage
            )
            if condition_met:
                triggered_assets.append(
                    {
                        "asset": symbol,
                        "change_pct": change_pct,
                        "price": latest,
                    }
                )
        now_iso = datetime.now(timezone.utc).isoformat()
        if triggered_assets:
            return {
                "status": "triggered",
                "observed_value": triggered_assets[0]["change_pct"],
                "context": {"matches": triggered_assets},
                "triggered_at": now_iso,
            }
        return {
            "status": "armed",
            "observed_value": None,
            "context": {"checked_assets": targets},
        }

    def _evaluate_indicator_alert(self, condition: Dict, currency: str) -> Dict:
        indicator = condition.get("indicator", "rsi")
        timeframe = condition.get("timeframe", "4h")
        operator = condition.get("operator", "lt")
        threshold = float(condition.get("threshold") or 0)
        asset = condition.get("asset")
        analysis = self.technical_service.analyze(
            asset=asset,
            currency=currency,
            indicator=indicator,
            timeframe=timeframe,
        )
        value = analysis.get("value")
        triggered = False
        if value is not None:
            triggered = value < threshold if operator == "lt" else value > threshold
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "status": "triggered" if triggered else "armed",
            "observed_value": value,
            "context": {"analysis": analysis},
            "triggered_at": now_iso if triggered else None,
        }

    def _price_change(self, asset: str, currency: str, window_minutes: int) -> tuple[float, float]:
        resolved = self.market_service.resolve_symbol(asset)
        days = max(1, ceil(window_minutes / (60 * 24)))
        chart = self.market_service.client.get_market_chart(resolved, currency, days)
        series = chart.get("prices", [])
        if not series:
            return 0.0, 0.0
        cutoff = series[-1][0] - window_minutes * 60 * 1000
        window_series = [point for point in series if point[0] >= cutoff]
        if len(window_series) < 2:
            window_series = series[-2:]
        start_price = window_series[0][1]
        end_price = window_series[-1][1]
        change_pct = ((end_price - start_price) / start_price * 100) if start_price else 0.0
        return change_pct, end_price
