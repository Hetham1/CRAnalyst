# Crypto Analyst Chatbot (WORK IN PROGRESS)

An AI-powered conversational analyst for cryptocurrency market insights powered by LangGraph + FastAPI. The agent maintains threaded conversations with persistent memory, calls CoinGecko-powered tools, and streams answers to a lightweight web UI.

## Features
- LangGraph 1.0 agent that persists state in SQLite checkpoints via `langgraph-checkpoint-sqlite`.
- Google Gemini (via `langchain-google-genai`) for reasoning + tool orchestration.
- FastAPI backend with SSE chat, REST helpers (`/api/market/overview`, `/api/market/trending`), and realtime CoinGecko tooling.
- Modern React + Vite + shadcn/ui frontend with glassmorphic chat surface, SSE streaming bubbles, and live charts (price + volume sparklines powered by Recharts).
- Comprehensive testing (unit, integration, API) with pytest + httpx TestClient.

## Tech Stack
- Python 3.11+, FastAPI, LangChain / LangGraph, SQLite checkpoints.
- React 19 + Vite + TypeScript, TailwindCSS + shadcn/ui, Recharts, lucide-react.
- CoinGecko API (tool + REST endpoints); SSE chat transport.

## Quick Start
1. **Backend**
   - Create & activate a Python 3.11+ virtualenv.
   - Install deps: `pip install -r requirements.txt`.
   - Copy `.env.example` to `.env`, fill in `GOOGLE_API_KEY`, optional `COINGECKO_API_KEY`, and tweak `LOG_LEVEL`, etc.
   - Run FastAPI: `uvicorn app.main:app --reload`.
2. **Frontend**
   - `cd frontend`
   - `npm install`
   - For local dev run `npm run dev` (Vite) – this proxies API calls to the backend at `http://localhost:8000`.
   - For production build run `npm run build`. The compiled files land in `frontend/dist`; FastAPI automatically serves from that directory if it exists.
3. Browse to `http://localhost:8000` (served build) or the Vite dev URL (default `http://127.0.0.1:5173`) for the rich UI.

## Conversational UX Upgrades

- **Smart components JSON** – every LLM answer now returns `{ "summary": "...", "responses": [...] }` so the React client can mix text, tables, charts, alerts, and follow-up prompts in a single reply.
- **Market pulse + news** – new `/api/market/pulse`, `/api/market/news/{asset}`, and `/api/market/onchain/{asset}` endpoints fuel the “What’s happening now?” panel and LangGraph tools.
- **Personal analyst tooling** – advanced comparisons, technical analysis (RSI with candlestick + indicator charts), and on-chain whale heat signals are available as LangChain tools (`market_pulse`, `asset_intel`, `advanced_compare`, `technical_analysis`, `onchain_activity`).
- **Automated assistant** – portfolio, watchlist, and alert APIs (`/api/user/...`) persist threaded user state to `checkpoints/agent_state.json` so the agent can answer “Show my portfolio” or “Arm an RSI alert” without external services.
- **React overhaul** – the chat UI now renders streamed structured components via `SmartComponentRenderer`, keeps proactive follow-ups, and stores responses in localStorage per-thread.

## API Quick Reference

| Endpoint | Purpose |
| --- | --- |
| `GET /api/market/pulse?currency=usd` | Global market summary with movers, categories, sentiment |
| `GET /api/market/news/{asset}` | Coin-specific headlines + sentiment snapshot |
| `GET /api/market/onchain/{asset}` | Whale + network growth heuristics (BTC/ETH/LTC/DOGE/BCH) |
| `GET /api/market/compare/advanced?assets=btc&assets=eth` | Multi-metric comparison w/ normalized 90d performance |
| `GET /api/user/{user_id}/portfolio` | Portfolio valuation + allocation donut |
| `POST /api/user/portfolio` | Upsert holdings (`asset`, `amount`, `cost_basis`) |
| `POST /api/user/watchlist` | Maintain a watchlist per thread/user |
| `POST /api/user/alerts` | Create indicator/price-move alerts stored locally |

FastAPI’s `/docs` exposes the full schema for the new routes.

## Running Locally

```
python -m pip install -r requirements.txt
python -m pytest
uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

Environment additions in `.env`:

```
CRYPTOCOMPARE_API_KEY=           # optional – public feed works without but has stricter limits
BLOCKCHAIR_API_KEY=             # optional – required for higher on-chain throughput
DATA_STORE_PATH=checkpoints/agent_state.json
```

The React dev server streams directly to the FastAPI backend (`http://localhost:8000`). Build with `npm run build` to serve the bundled UI from FastAPI’s static mount.

See `DEPLOYMENT.md` for Docker & cloud deployment notes.
