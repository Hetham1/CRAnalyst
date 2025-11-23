"""Public market endpoints for the frontend dashboard."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..market import MarketDataError

router = APIRouter(prefix="/api/market", tags=["market"])


def _get_market_service(request: Request):
    service = getattr(request.app.state, "market_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Market service unavailable.")
    return service


def _get_state_service(request: Request, name: str):
    service = getattr(request.app.state, name, None)
    if not service:
        raise HTTPException(status_code=503, detail=f"{name} unavailable.")
    return service


@router.get("/overview/{asset}")
async def fetch_asset_overview(
    asset: str,
    request: Request,
    currency: str = Query("usd", max_length=10),
    lookback_days: int = Query(7, ge=1, le=90),
):
    service = _get_market_service(request)
    try:
        return service.asset_overview(asset, currency, lookback_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/trending")
async def fetch_trending(request: Request):
    service = _get_market_service(request)
    try:
        return {"trending": service.get_trending()[:12]}
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/compare")
async def compare_assets(
    base: str = Query(..., min_length=1, max_length=32),
    request: Request = None,
    currency: str = Query("usd", max_length=10),
    targets: list[str] = Query(..., description="Repeated query param, up to 10 items"),
):
    service = _get_market_service(request)
    unique_targets = []
    for target in targets:
        symbol = target.strip()
        if symbol and symbol.lower() not in [t.lower() for t in unique_targets]:
            unique_targets.append(symbol)
        if len(unique_targets) >= 10:
            break
    if not unique_targets:
        raise HTTPException(status_code=400, detail="At least one target symbol is required.")
    try:
        comparisons = service.compare_assets(base, unique_targets, currency)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"base": base, "currency": currency, "comparisons": comparisons}


@router.get("/pulse")
async def market_pulse(request: Request, currency: str = Query("usd", max_length=10)):
    pulse_service = _get_state_service(request, "pulse_service")
    return pulse_service.build_pulse(currency)


@router.get("/news/{asset}")
async def asset_news(asset: str, request: Request, limit: int = Query(3, ge=1, le=6)):
    news_service = _get_state_service(request, "news_service")
    items = news_service.fetch_for_asset(asset, limit=limit)
    sentiment = news_service.summarize_sentiment(items)
    return {
        "asset": asset,
        "news": [
            {
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "published_at": item.published_at,
            }
            for item in items
        ],
        "sentiment": sentiment,
    }


@router.get("/onchain/{asset}")
async def onchain(asset: str, request: Request):
    onchain_service = _get_state_service(request, "onchain_service")
    try:
        return onchain_service.snapshot(asset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/compare/advanced")
async def advanced_compare(
    request: Request,
    assets: list[str] = Query(..., description="Repeated asset param, at least two."),
    currency: str = Query("usd", max_length=10),
):
    comparison_service = _get_state_service(request, "comparison_service")
    if len(assets) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two assets.")
    return comparison_service.compare(assets, currency)
