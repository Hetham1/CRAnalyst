"""Configuration helpers for the Crypto Analyst chatbot application."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]

# Load environment variables from .env if present.
load_dotenv(ROOT_DIR / ".env")


class Settings(BaseModel):
    """Centralized application settings."""

    app_name: str = "Crypto Analyst Chatbot"
    google_api_key: str | None = Field(default=os.getenv("GOOGLE_API_KEY"))
    gemini_model: str = Field(default=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    coingecko_api_key: str | None = Field(default=os.getenv("COINGECKO_API_KEY"))
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    sqlite_db_path: str = Field(default=os.getenv("SQLITE_DB_PATH", "checkpoints/agent.db"))
    data_store_path: str = Field(
        default=os.getenv("DATA_STORE_PATH", "checkpoints/agent_state.json")
    )
    cryptocompare_api_key: str | None = Field(default=os.getenv("CRYPTOCOMPARE_API_KEY"))
    blockchair_api_key: str | None = Field(default=os.getenv("BLOCKCHAIR_API_KEY"))
    blockchair_base_url: str = "https://api.blockchair.com"
    default_currency: str = Field(default=os.getenv("DEFAULT_CURRENCY", "usd"))
    default_thread_id: str = Field(default=os.getenv("DEFAULT_THREAD_ID", "default-thread"))
    request_timeout: int = Field(default=int(os.getenv("REQUEST_TIMEOUT", "15")))
    testing: bool = Field(default=os.getenv("TESTING", "0") == "1")

    model_config = ConfigDict(frozen=True)

    @property
    def sqlite_path(self) -> Path:
        """Return the absolute path to the SQLite checkpoint file."""
        candidate = Path(self.sqlite_db_path)
        if not candidate.is_absolute():
            candidate = ROOT_DIR / candidate
        abs_path = candidate.resolve()
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        return abs_path

    @property
    def data_store_file(self) -> Path:
        """Return the file path used for agent portfolio/watchlist state."""
        candidate = Path(self.data_store_path)
        if not candidate.is_absolute():
            candidate = ROOT_DIR / candidate
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate.resolve()


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
