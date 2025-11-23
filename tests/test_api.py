import json


def test_health_endpoint(test_app):
    response = test_app.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_endpoint_returns_message(test_app):
    response = test_app.post("/api/chat", json={"message": "Give me a summary"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["content"].startswith("Mock")
    assert payload["thread_id"] == "test-thread"
    assert payload["structured"]
    assert payload["structured"]["responses"]


def test_stream_endpoint_streams_chunks(test_app):
    response = test_app.post("/api/chat/stream", json={"message": "Stream it"})
    assert response.status_code == 200
    chunk_text = []
    layout_seen = False
    current_event = "message"
    for line in response.iter_lines():
        if line.startswith("event:"):
            current_event = line.replace("event:", "").strip()
            continue
        if not line.startswith("data:"):
            continue
        data = json.loads(line.replace("data:", "").strip())
        if current_event == "layout":
            layout_seen = True
            continue
        if data.get("event") == "end":
            continue
        if "chunk" in data:
            chunk_text.append(data["chunk"])
    assert chunk_text or layout_seen


def test_market_overview_endpoint(test_app):
    response = test_app.get("/api/market/overview/btc")
    assert response.status_code == 200
    body = response.json()
    assert body["asset"] == "bitcoin"
    assert "series" in body


def test_market_trending_endpoint(test_app):
    response = test_app.get("/api/market/trending")
    assert response.status_code == 200
    body = response.json()
    assert len(body["trending"]) == 2


def test_market_compare_endpoint(test_app):
    response = test_app.get(
        "/api/market/compare",
        params=[("base", "btc"), ("targets", "eth"), ("targets", "sol")],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["base"] == "btc"
    assert len(payload["comparisons"]) == 2


def test_market_pulse_endpoint(test_app):
    response = test_app.get("/api/market/pulse")
    assert response.status_code == 200
    body = response.json()
    assert "global" in body


def test_market_news_endpoint(test_app):
    response = test_app.get("/api/market/news/btc")
    assert response.status_code == 200
    body = response.json()
    assert body["asset"] == "btc"
    assert body["sentiment"]


def test_onchain_endpoint(test_app):
    response = test_app.get("/api/market/onchain/btc")
    assert response.status_code == 200
    body = response.json()
    assert body["asset"] == "btc"


def test_advanced_compare_endpoint(test_app):
    response = test_app.get(
        "/api/market/compare/advanced",
        params=[("assets", "btc"), ("assets", "eth")],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["normalized_history"]


def test_portfolio_and_alert_flow(test_app):
    user_id = "tester"
    # add position
    add_resp = test_app.post(
        "/api/user/portfolio",
        json={
            "user_id": user_id,
            "position": {"asset": "btc", "amount": 1.0, "cost_basis": 65000},
        },
    )
    assert add_resp.status_code == 200

    portfolio = test_app.get(f"/api/user/{user_id}/portfolio")
    assert portfolio.status_code == 200
    assert portfolio.json()["positions"]

    watch = test_app.post(
        "/api/user/watchlist",
        json={"user_id": user_id, "asset": "eth"},
    )
    assert watch.status_code == 200

    alert = test_app.post(
        "/api/user/alerts",
        json={
            "user_id": user_id,
            "description": "RSI watcher",
            "condition": {
                "type": "indicator_threshold",
                "asset": "btc",
                "indicator": "rsi",
                "timeframe": "4h",
                "operator": "lt",
                "threshold": 30,
            },
        },
    )
    assert alert.status_code == 200

    alerts = test_app.get(f"/api/user/{user_id}/alerts")
    assert alerts.status_code == 200
    assert alerts.json()["alerts"]
