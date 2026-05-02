# Run: python3 create_railway_setup.py
# Creates all files needed to deploy CineRisk API to Railway
import os

base = os.path.expanduser("~/Desktop/cinerisk")

# ── requirements.txt ──────────────────────────────────────────────────
req = """fastapi==0.136.1
uvicorn==0.46.0
pydantic>=2.0.0
"""

# ── Procfile (tells Railway how to start the app) ─────────────────────
procfile = "web: uvicorn api:app --host 0.0.0.0 --port $PORT\n"

# ── railway.json (optional but speeds up deploy) ─────────────────────
railway_json = """{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn api:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE"
  }
}
"""

# ── .gitignore ────────────────────────────────────────────────────────
gitignore = """__pycache__/
*.pyc
*.pyo
.env
.env.local
*.pdf
node_modules/
.DS_Store
"""

# ── README for the repo ───────────────────────────────────────────────
readme = """# CineRisk API

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
curl -X POST https://YOUR-RAILWAY-URL/simulate \\
  -H "Content-Type: application/json" \\
  -d '{"genre":"action","hype":"high","strategy":"staggered","budget_m":180}'
```
"""

files = {
    "requirements.txt": req,
    "Procfile":         procfile,
    "railway.json":     railway_json,
    ".gitignore":       gitignore,
    "README.md":        readme,
}

for name, content in files.items():
    path = os.path.join(base, name)
    with open(path, "w") as f:
        f.write(content)
    print(f"  Created: {path}")

print("""
All Railway deployment files created.

DEPLOY IN 4 STEPS:
──────────────────
Step 1 — Push to GitHub (run in ~/Desktop/cinerisk):
  git init
  git add engine.py api.py requirements.txt Procfile railway.json .gitignore README.md
  git commit -m "CineRisk API v1"
  gh repo create cinerisk-api --public --push
  (or: go to github.com → New repo → upload files manually)

Step 2 — Deploy to Railway:
  Go to railway.app
  Click "New Project" → "Deploy from GitHub repo"
  Select cinerisk-api
  Railway detects Python automatically → click Deploy

Step 3 — Get your URL:
  Railway gives you a URL like: https://cinerisk-api-production.up.railway.app
  Open that URL + /docs to see the live API playground

Step 4 — Update dashboard:
  In dashboard_v2.html, change line:
    const API = 'http://localhost:8000';
  To:
    const API = 'https://YOUR-RAILWAY-URL';
  Then open dashboard — it calls the live API instead of local
""")
