# MNQ Momentum Monitor

Analysis-only TradingView alert receiver on Railway with PostgreSQL.

## Endpoints
- `GET /health` checks database connectivity.
- `POST /webhook/tradingview` authenticates and stores MNQ/NQ alerts; it **never places orders**.

## Railway
Connect this repository to the existing `mnq-python-monitor` service. Set:
- `DATABASE_URL=${{Postgres.DATABASE_URL}}` (Railway reference)
- `EXECUTION_ENABLED=false`
- `WEBHOOK_SECRET` to a long random secret **in Railway variables only**
- `TZ=America/Chicago`

Generate a public HTTPS domain in Railway for the Python service. Do not put credentials in GitHub.

## TradingView JSON alert example
```json
{"token":"YOUR_WEBHOOK_SECRET","event_id":"{{ticker}}-{{time}}-signal-name","symbol":"{{ticker}}","timeframe":"5","signal":"inverted_fvg"}
```

This is an ingestion starter, not an ICT signal engine, order router, or scheduled market-data report. `RISK_LIMIT_USD` is a configuration placeholder, not implemented position-risk enforcement. Use paper testing before any execution integration.
