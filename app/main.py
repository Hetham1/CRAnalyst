"""FastAPI entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import logging

import aiosqlite
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .agent import build_agent
from .config import Settings, get_settings
from .logging_config import setup_logging
from .market import CoinGeckoClient, MarketDataService
from .routes.chat import router as chat_router
from .routes.market import router as market_router
from .routes.user import router as user_router
from .services import (
    AgentDataStore,
    AlertService,
    AdvancedComparisonService,
    CryptoNewsService,
    MarketPulseService,
    OnChainService,
    PortfolioService,
    TechnicalAnalysisService,
)
from .tools import build_market_tools

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
LEGACY_STATIC = BASE_DIR / "static"


def _resolve_static_dir() -> Path:
    if FRONTEND_DIST.exists():
        return FRONTEND_DIST
    LEGACY_STATIC.mkdir(parents=True, exist_ok=True)
    return LEGACY_STATIC


STATIC_DIR = _resolve_static_dir()

setup_logging()
logger = logging.getLogger(__name__)

def create_app(
    settings_override: Settings | None = None,
    llm_override=None,
    market_service_override: MarketDataService | None = None,
) -> FastAPI:
    """Instantiate the FastAPI application."""

    settings = settings_override or get_settings()
    logger.info("Booting FastAPI app with SQLite DB at %s", settings.sqlite_path)
    coingecko_client = CoinGeckoClient(
        base_url=settings.coingecko_base_url,
        api_key=settings.coingecko_api_key,
        timeout=settings.request_timeout,
    )
    market_service = market_service_override or MarketDataService(coingecko_client)
    news_service = CryptoNewsService(
        api_key=settings.cryptocompare_api_key,
    )
    onchain_service = OnChainService(
        api_key=settings.blockchair_api_key,
        base_url=settings.blockchair_base_url,
    )
    technical_service = TechnicalAnalysisService(market_service)
    data_store = AgentDataStore(settings.data_store_file)
    portfolio_service = PortfolioService(data_store, market_service)
    alert_service = AlertService(data_store, market_service, technical_service, portfolio_service)
    pulse_service = MarketPulseService(market_service, news_service)
    comparison_service = AdvancedComparisonService(market_service)

    tools = build_market_tools(
        market_service,
        news_service=news_service,
        onchain_service=onchain_service,
        technical_service=technical_service,
        portfolio_service=portfolio_service,
        alert_service=alert_service,
        pulse_service=pulse_service,
        comparison_service=comparison_service,
    )

    graph_tools = tools

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting lifespan context, opening checkpoint DB.")
        conn = await aiosqlite.connect(str(settings.sqlite_path))
        checkpointer = AsyncSqliteSaver(conn)
        app.state.graph = build_agent(
            settings,
            graph_tools,
            llm=llm_override,
            checkpointer=checkpointer,
        )
        logger.info("LangGraph agent compiled and ready.")
        try:
            yield
        finally:
            await conn.close()
            app.state.graph = None
            logger.info("Checkpoint DB closed, graph torn down.")

    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.graph = None
    app.state.market_service = market_service
    app.state.portfolio_service = portfolio_service
    app.state.alert_service = alert_service
    app.state.news_service = news_service
    app.state.onchain_service = onchain_service
    app.state.technical_service = technical_service
    app.state.pulse_service = pulse_service
    app.state.comparison_service = comparison_service

    app.include_router(chat_router)
    app.include_router(market_router)
    app.include_router(user_router)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    if STATIC_DIR == FRONTEND_DIST:
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    else:
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/")
    async def root():
        return FileResponse(STATIC_DIR / "index.html")

    if (STATIC_DIR / "vite.svg").exists():

        @app.get("/vite.svg")
        async def vite_svg():
            return FileResponse(STATIC_DIR / "vite.svg")

    return app
app = create_app()
