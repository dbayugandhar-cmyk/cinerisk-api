"""
CINEOS Unified API
Combines Layer 1 (risk engine) + Theater API (Layers 2-5)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'theater'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import both apps as routers
try:
    from theater.theater_api import app as theater_app
except Exception as e:
    print(f"[WARN] Theater API import error: {e}")
    theater_app = None

try:
    from api import app as risk_app
except Exception as e:
    print(f"[WARN] Risk API import error: {e}")
    risk_app = None

app = FastAPI(
    title="CINEOS Platform API",
    version="2.0.0",
    description="Cinema Piracy Detection — Layer 1 through Layer 5"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount theater routes (Layers 2-5)
if theater_app:
    for route in theater_app.routes:
        app.routes.append(route)

# Mount risk engine routes (Layer 1)
if risk_app:
    for route in risk_app.routes:
        if not any(r.path == route.path for r in app.routes):
            app.routes.append(route)

@app.get("/")
async def root():
    return {
        "platform": "CINEOS",
        "version": "2.0.0",
        "patent": "US Prov. Pat. 64/049,190",
        "layers": {
            "layer1": "Risk prediction — /simulate",
            "layer2": "Theater detection — /theater/incident",
            "layer3": "Session tracking — /theater/sessions",
            "layer4": "Leak monitor — /theater/manual_scan",
            "layer5": "Intelligence — /theater/stats"
        },
        "status": "live"
    }
