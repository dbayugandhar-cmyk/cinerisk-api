# CineRisk API

Film release risk and revenue intelligence engine.

## Endpoints

- `GET  /health`     — health check
- `GET  /genres`     — genre sensitivity index
- `GET  /strategies` — release strategy reference
- `POST /simulate`   — full risk simulation
- `POST /compare`    — strategy comparison

## Run locally

```bash
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

Open http://localhost:8000/docs for interactive docs.

## Deploy to Railway

1. Push this repo to GitHub
2. Go to railway.app → New Project → Deploy from GitHub
3. Select this repo → Railway auto-detects Python + Procfile
4. Done — live URL in ~2 minutes

## Example request

```bash
curl -X POST https://YOUR-RAILWAY-URL/simulate \
  -H "Content-Type: application/json" \
  -d '{"genre":"action","hype":"high","strategy":"staggered","budget_m":180}'
```
