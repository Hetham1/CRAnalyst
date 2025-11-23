"""User-centric endpoints (portfolio, watchlist, alerts)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..models import AlertRequest, PortfolioDeleteRequest, PortfolioUpsertRequest, WatchlistRequest

router = APIRouter(prefix="/api/user", tags=["user"])


def _require_service(request: Request, name: str):
    service = getattr(request.app.state, name, None)
    if not service:
        raise HTTPException(status_code=503, detail=f"{name} is not initialized.")
    return service


@router.get("/{user_id}/portfolio")
async def get_portfolio(user_id: str, request: Request, currency: str = Query("usd", max_length=10)):
    service = _require_service(request, "portfolio_service")
    return service.summarize_portfolio(user_id, currency)


@router.post("/portfolio")
async def add_position(request: Request, payload: PortfolioUpsertRequest):
    service = _require_service(request, "portfolio_service")
    position = service.add_position(
        payload.user_id,
        payload.position.asset,
        payload.position.amount,
        payload.position.cost_basis,
    )
    return position


@router.delete("/portfolio")
async def delete_position(request: Request, payload: PortfolioDeleteRequest):
    service = _require_service(request, "portfolio_service")
    service.delete_position(payload.user_id, payload.position_id)
    return {"status": "deleted"}


@router.get("/{user_id}/watchlist")
async def get_watchlist(user_id: str, request: Request):
    service = _require_service(request, "portfolio_service")
    return {"user_id": user_id, "watchlist": service.get_watchlist(user_id)}


@router.post("/watchlist")
async def add_watch(request: Request, payload: WatchlistRequest):
    service = _require_service(request, "portfolio_service")
    watchlist = service.add_watch_asset(payload.user_id, payload.asset)
    return {"user_id": payload.user_id, "watchlist": watchlist}


@router.delete("/watchlist")
async def delete_watch(request: Request, payload: WatchlistRequest):
    service = _require_service(request, "portfolio_service")
    watchlist = service.remove_watch_asset(payload.user_id, payload.asset)
    return {"user_id": payload.user_id, "watchlist": watchlist}


@router.get("/{user_id}/alerts")
async def list_alerts(user_id: str, request: Request, currency: str = Query("usd", max_length=10)):
    alert_service = _require_service(request, "alert_service")
    alerts = alert_service.evaluate_alerts(user_id, currency)
    return {"user_id": user_id, "alerts": alerts}


@router.post("/alerts")
async def create_alert(request: Request, payload: AlertRequest):
    alert_service = _require_service(request, "alert_service")
    alert = alert_service.add_alert(
        payload.user_id, payload.description, payload.condition.model_dump()
    )
    return alert


@router.delete("/{user_id}/alerts/{alert_id}")
async def delete_alert(user_id: str, alert_id: str, request: Request):
    alert_service = _require_service(request, "alert_service")
    alert_service.delete_alert(user_id, alert_id)
    return {"status": "deleted"}
