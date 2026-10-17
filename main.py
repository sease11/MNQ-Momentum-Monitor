import os
import json
import hmac
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import create_engine, text

app = FastAPI(title="MNQ Momentum Monitor", version="0.1.0")
engine = None

def database():
    global engine
    if engine is None:
        url = os.environ["DATABASE_URL"]
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        engine = create_engine(url, pool_pre_ping=True)
    return engine

@app.on_event("startup")
def startup():
    with database().begin() as conn:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS tv_alerts (
            id BIGSERIAL PRIMARY KEY,
            received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            event_id TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT,
            signal TEXT,
            payload JSONB NOT NULL
        )"""))

@app.get("/health")
def health():
    with database().connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected", "execution_enabled": False}

@app.post("/webhook/tradingview")
async def tradingview(request: Request):
    secret = os.getenv("WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(503, "Webhook secret not configured")
    supplied = request.headers.get("x-webhook-secret", "")
    raw = await request.body()
    if len(raw) > 32768:
        raise HTTPException(413, "Payload too large")
    try:
        payload: dict[str, Any] = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid JSON object")
    token = supplied or str(payload.pop("token", ""))
    if not hmac.compare_digest(token, secret):
        raise HTTPException(401, "Unauthorized")
    symbol = str(payload.get("symbol", ""))
    normalized_symbol = symbol.upper().split(":")[-1]
    is_mnq = normalized_symbol.startswith(("MNQ", "NQ"))
    is_btc_test = normalized_symbol.startswith("BTCUSD")
    if not symbol or len(symbol) > 64 or not (is_mnq or is_btc_test):
        raise HTTPException(422, "MNQ/NQ or BTCUSD test symbol required")
    if is_btc_test and str(payload.get("signal", "")) != "connection_test":
        raise HTTPException(422, "BTCUSD only allowed for connection_test")
    event_id = str(payload.get("event_id") or "")
    if not event_id or len(event_id) > 160:
        raise HTTPException(422, "Unique event_id required")
    with database().begin() as conn:
        result = conn.execute(text("""INSERT INTO tv_alerts (event_id,symbol,timeframe,signal,payload)
            VALUES (:event_id,:symbol,:timeframe,:signal,CAST(:payload AS JSONB))
            ON CONFLICT (event_id) DO NOTHING RETURNING id"""), {
            "event_id": event_id, "symbol": symbol,
            "timeframe": str(payload.get("timeframe", ""))[:32],
            "signal": str(payload.get("signal", ""))[:80],
            "payload": json.dumps(payload),
        }).scalar_one_or_none()
    return {"accepted": True, "duplicate": result is None, "test_only": is_btc_test, "execution_enabled": False}
