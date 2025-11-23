"""News + sentiment helpers built on top of the CryptoCompare feed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Sequence
import logging

import requests
from requests import Response

logger = logging.getLogger(__name__)


POSITIVE_KEYWORDS = {
    "surge",
    "upgrades",
    "upgrade",
    "bull",
    "bullish",
    "record",
    "partnership",
    "approve",
    "adopt",
    "rally",
    "growth",
    "funding",
    "investment",
    "accumulate",
}
NEGATIVE_KEYWORDS = {
    "hack",
    "ban",
    "lawsuit",
    "sell-off",
    "bear",
    "bearish",
    "outage",
    "exploit",
    "downgrade",
    "fear",
    "crash",
    "plunge",
    "liquidation",
    "investigation",
}


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    source: str
    published_at: str
    categories: List[str]
    body: str


class CryptoNewsService:
    """Thin client wrapping CryptoCompare's public news endpoint."""

    def __init__(
        self,
        base_url: str = "https://min-api.cryptocompare.com/data/v2/news/",
        api_key: str | None = None,
        timeout: int = 10,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._cache: dict[tuple, tuple[float, list[NewsItem]]] = {}
        self.cache_ttl = 120.0

    def _request(self, params: Dict) -> Dict:
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Apikey {self.api_key}"
        try:
            response: Response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            logger.error("News API failed status=%s", exc.response.status_code if exc.response else "?")
            raise
        return response.json()

    def fetch_news(
        self,
        *,
        limit: int = 5,
        categories: Sequence[str] | None = None,
        assets: Sequence[str] | None = None,
    ) -> List[NewsItem]:
        """Return curated news; results cached briefly to avoid rate limits."""

        normalized_assets = tuple(sorted({asset.lower() for asset in assets or []}))
        normalized_categories = tuple(sorted({cat.lower() for cat in categories or []}))
        cache_key = (limit, normalized_categories, normalized_assets)
        now = datetime.now(timezone.utc).timestamp()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < self.cache_ttl:
            return cached[1]

        params = {"lang": "EN", "sortOrder": "popular", "limit": limit}
        if normalized_categories:
            params["categories"] = ",".join(normalized_categories)
        payload = self._request(params)
        entries = payload.get("Data", [])
        items: list[NewsItem] = []
        for entry in entries:
            title = entry.get("title", "").strip()
            if not title:
                continue
            tags = (entry.get("tags") or "").lower().split("|")
            categories = (entry.get("categories") or "").lower().split("|")
            if normalized_assets and not any(asset in tags for asset in normalized_assets):
                continue
            published_ts = entry.get("published_on")
            try:
                published_at = datetime.fromtimestamp(published_ts, tz=timezone.utc).isoformat()
            except (TypeError, ValueError):
                published_at = datetime.now(timezone.utc).isoformat()
            items.append(
                NewsItem(
                    title=title,
                    url=entry.get("url", ""),
                    source=entry.get("source") or entry.get("source_info", {}).get("name", "Unknown"),
                    published_at=published_at,
                    categories=[cat for cat in categories if cat],
                    body=(entry.get("body") or "").strip(),
                )
            )
            if len(items) >= limit:
                break
        self._cache[cache_key] = (now, items)
        return items

    def fetch_for_asset(self, asset: str, *, limit: int = 3) -> List[NewsItem]:
        return self.fetch_news(limit=limit, assets=[asset])

    def summarize_sentiment(self, items: Iterable[NewsItem]) -> Dict[str, object]:
        """Crude sentiment gauge using keyword heuristics."""

        items = list(items)
        if not items:
            return {"score": 0.0, "label": "neutral", "keywords": []}
        score = 0
        keyword_hits: dict[str, int] = {}
        for item in items:
            text = f"{item.title} {item.body}".lower()
            for token in POSITIVE_KEYWORDS:
                if token in text:
                    score += 1
                    keyword_hits[token] = keyword_hits.get(token, 0) + 1
            for token in NEGATIVE_KEYWORDS:
                if token in text:
                    score -= 1
                    keyword_hits[token] = keyword_hits.get(token, 0) + 1
        normalized = score / max(len(items), 1)
        if normalized > 0.75:
            label = "strongly positive"
        elif normalized > 0.25:
            label = "positive"
        elif normalized < -0.75:
            label = "strongly negative"
        elif normalized < -0.25:
            label = "negative"
        else:
            label = "neutral"
        top_keywords = sorted(keyword_hits.items(), key=lambda kv: kv[1], reverse=True)[:3]
        return {
            "score": round(normalized, 2),
            "label": label,
            "keywords": [word for word, _ in top_keywords],
            "sample_size": len(items),
        }
