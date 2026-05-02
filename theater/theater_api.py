"""
CINEOS Theater API v1
=====================
FastAPI bridge between the YOLO detection pipeline and the studio/theater dashboards.
Sits on top of Supabase — adds proper endpoints, CORS, validation, and Layer 3 bridge.

Endpoints:
  POST /theater/incident         — log a detection event from detector.py
  GET  /theater/incidents        — retrieve incidents (filtered)
  GET  /theater/screenings       — list screenings
  POST /theater/screening        — register a new screening
  GET  /theater/risk/{title}     — get CineRisk Layer 1 score for a film
  GET  /theater/stats            — aggregate stats for studio dashboard
  GET  /theater/health           — health check

Supabase schema (incidents table):
  id             uuid PK
  theater_name   text
  screen_number  text
  seat_location  text
  zone           text (LEFT/CENTER/RIGHT)
  detection_type text (PHONE/DEVICE)
  confidence     float
  detected_at    timestamp
  film_title     text
  alerted        boolean

Run locally:
  SUPABASE_URL=https://fuaybehxfusfywghuxwp.supabase.co \
  SUPABASE_KEY=your_service_key \
  uvicorn theater_api:app --reload --port 8001

Deploy: add to Railway alongside api.py (different port via env var)
"""

import os, sys, json
from datetime import datetime, timedelta
from typing import Optional, List, Literal
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx

# ── Config ────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://fuaybehxfusfywghuxwp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")  # Use service key for writes, anon for reads
CINERISK_API = os.getenv("CINERISK_API", "http://localhost:8000")

# ── App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="CINEOS Theater API",
    description="Real-time theater detection bridge. US Prov. Pat. 64/049,190",
    version="1.0.0",
    docs_url="/theater/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Supabase client helpers ───────────────────────────────────────────

def _sb_headers():
    """Supabase REST headers."""
    key = SUPABASE_KEY or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1YXliZWh4ZnVzZnl3Z2h1eHdwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcxNTIzNDgsImV4cCI6MjA5MjcyODM0OH0.mbYxdL8NilgZOT4_vyWGK73h64UVxqCpT5SEzO3Kcks"
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

async def _sb_get(table: str, params: dict = None) -> list:
    """GET from Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.get(url, headers=_sb_headers(), params=params or {})
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Supabase error: {r.text}")
        return r.json()

async def _sb_post(table: str, data: dict) -> dict:
    """POST (insert) to Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(url, headers=_sb_headers(), json=data)
        if r.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"Supabase insert error: {r.text}")
        result = r.json()
        return result[0] if isinstance(result, list) and result else result

# ── Request / Response models ─────────────────────────────────────────

class IncidentCreate(BaseModel):
    theater_name:   str   = Field(..., example="AMC Times Square")
    screen_number:  str   = Field(..., example="Screen 7")
    seat_location:  Optional[str] = Field(None, example="Row G Seat 14")
    zone:           Literal["LEFT","CENTER","RIGHT"] = Field(..., example="CENTER")
    detection_type: str   = Field("PHONE", example="PHONE")
    confidence:     float = Field(..., ge=0.0, le=1.0, example=0.87)
    film_title:     Optional[str] = Field(None, example="Nova Station")
    alerted:        bool  = Field(False)
    device_id:      Optional[str] = Field(None, description="For repeat offender tracking")

class ScreeningCreate(BaseModel):
    theater_name:   str
    screen_number:  str
    film_title:     str
    genre:          Optional[str] = None
    release_strategy: Optional[str] = None
    started_at:     Optional[str] = None

class IncidentResponse(BaseModel):
    id:             Optional[str]
    theater_name:   str
    screen_number:  str
    seat_location:  Optional[str]
    zone:           str
    detection_type: str
    confidence:     float
    film_title:     Optional[str]
    alerted:        bool
    detected_at:    str

class StatsResponse(BaseModel):
    total_incidents:    int
    incidents_today:    int
    theaters_active:    int
    avg_confidence:     float
    high_risk_zones:    List[str]
    compliance_score:   int

# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/theater/health", tags=["System"])
async def health():
    """Health check — confirms API and Supabase connectivity."""
    try:
        await _sb_get("incidents", {"limit": "1"})
        sb_status = "connected"
    except Exception as e:
        sb_status = f"error: {str(e)[:60]}"
    return {
        "status": "ok",
        "version": "1.0.0",
        "patent": "US Prov. Pat. 64/049,190",
        "supabase": sb_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/theater/incident", response_model=IncidentResponse, tags=["Detection"])
async def log_incident(inc: IncidentCreate):
    """
    Log a detection event from detector.py.
    Called automatically when YOLO detects a phone above confidence threshold.
    """
    payload = {
        "theater_name":   inc.theater_name,
        "screen_number":  inc.screen_number,
        "seat_location":  inc.seat_location,
        "zone":           inc.zone,
        "detection_type": inc.detection_type,
        "confidence":     round(inc.confidence, 4),
        "film_title":     inc.film_title,
        "alerted":        inc.alerted,
        "detected_at":    datetime.utcnow().isoformat(),
    }
    if inc.device_id:
        payload["device_id"] = inc.device_id

    result = await _sb_post("incidents", payload)
    return {**payload, "id": result.get("id") if isinstance(result, dict) else None}


@app.get("/theater/incidents", tags=["Detection"])
async def get_incidents(
    theater:  Optional[str] = Query(None, description="Filter by theater name"),
    limit:    int           = Query(200, ge=1, le=1000),
    hours:    Optional[int] = Query(None, description="Last N hours only"),
    film:     Optional[str] = Query(None, description="Filter by film title"),
):
    """
    Retrieve incidents. Powers both the studio dashboard and theater map.
    Called every 5 seconds by the dashboards (matches existing polling interval).
    """
    params = {
        "select":   "*",
        "order":    "detected_at.desc",
        "limit":    str(limit),
    }
    if theater:
        params["theater_name"] = f"ilike.*{theater}*"
    if film:
        params["film_title"] = f"ilike.*{film}*"
    if hours:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        params["detected_at"] = f"gte.{cutoff}"

    incidents = await _sb_get("incidents", params)
    return {
        "count":     len(incidents),
        "incidents": incidents,
    }


@app.post("/theater/screening", tags=["Screenings"])
async def create_screening(s: ScreeningCreate):
    """Register a new screening session. Called when a film starts."""
    payload = {
        "theater_name":     s.theater_name,
        "screen_number":    s.screen_number,
        "film_title":       s.film_title,
        "genre":            s.genre,
        "release_strategy": s.release_strategy,
        "started_at":       s.started_at or datetime.utcnow().isoformat(),
    }
    result = await _sb_post("screenings", payload)
    return {"status": "created", "screening": result}


@app.get("/theater/screenings", tags=["Screenings"])
async def get_screenings(active_only: bool = Query(True)):
    """List screenings. Used to map incidents to films for Layer 3."""
    params = {"select": "*", "order": "started_at.desc", "limit": "50"}
    if active_only:
        params["ended_at"] = "is.null"
    return await _sb_get("screenings", params)


@app.get("/theater/stats", response_model=StatsResponse, tags=["Analytics"])
async def get_stats():
    """
    Aggregate statistics for the studio compliance dashboard.
    Mirrors the stats the dashboard currently computes client-side,
    but calculated server-side for accuracy and caching.
    """
    incidents = await _sb_get("incidents", {
        "select": "*", "order": "detected_at.desc", "limit": "1000"
    })

    today = datetime.utcnow().date().isoformat()
    today_incidents = [i for i in incidents if i.get("detected_at","").startswith(today)]
    theaters = set(i.get("theater_name","") for i in incidents if i.get("theater_name"))
    confidences = [i.get("confidence",0) for i in incidents if i.get("confidence")]
    avg_conf = round(sum(confidences)/len(confidences), 3) if confidences else 0.0

    # Zone risk: which zones have most incidents
    zone_counts = {}
    for i in incidents:
        z = i.get("zone","UNKNOWN")
        zone_counts[z] = zone_counts.get(z, 0) + 1
    high_risk = [z for z,c in sorted(zone_counts.items(), key=lambda x:-x[1]) if c > 2]

    # Compliance score: 100 - (incident rate penalty)
    total = len(incidents)
    incident_rate = min(total / 100, 1.0) if total > 0 else 0.0
    compliance_score = max(0, round(100 - incident_rate * 30))

    return StatsResponse(
        total_incidents=total,
        incidents_today=len(today_incidents),
        theaters_active=len(theaters),
        avg_confidence=avg_conf,
        high_risk_zones=high_risk[:3],
        compliance_score=compliance_score,
    )


@app.get("/theater/risk/{film_title}", tags=["Layer 1 Bridge"])
async def get_film_risk(
    film_title: str,
    genre:      str = Query("action"),
    hype:       str = Query("medium"),
    strategy:   str = Query("staggered"),
    budget_m:   float = Query(100.0),
):
    """
    Layer 1 + Layer 2 bridge.
    Fetches CineRisk engine prediction AND real incident count for a film.
    This is the Layer 3 connection point — predicted vs observed.
    """
    # Get Layer 1 prediction from CineRisk engine
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(f"{CINERISK_API}/simulate", json={
                "genre": genre,
                "hype": hype,
                "strategy": strategy,
                "budget_m": budget_m,
                "film_title": film_title,
            })
        engine_data = r.json() if r.status_code == 200 else None
    except Exception:
        engine_data = None

    # Get Layer 2 observed incidents for this film
    try:
        observed = await _sb_get("incidents", {
            "film_title": f"ilike.*{film_title}*",
            "select": "*",
            "limit": "500",
        })
    except Exception:
        observed = []

    # Layer 3: compare predicted leak day vs observed first incident
    predicted_leak = None
    observed_first_incident = None
    delta_days = None

    if engine_data and engine_data.get("strategies"):
        cur = next((s for s in engine_data["strategies"]
                    if s["strategy"] == strategy), None)
        if cur:
            predicted_leak = cur.get("leak_day_low")

    if observed:
        first = min(observed, key=lambda x: x.get("detected_at",""))
        observed_first_incident = first.get("detected_at")

    return {
        "film_title":               film_title,
        "layer1_prediction":        engine_data,
        "layer2_observed_incidents": len(observed),
        "layer3_comparison": {
            "predicted_leak_day":        predicted_leak,
            "observed_first_incident":   observed_first_incident,
            "delta_days":                delta_days,
            "calibration_note": (
                "Insufficient observed data for calibration — need 10+ screenings."
                if len(observed) < 10 else
                "Sufficient data for Layer 3 calibration. Run feedback/bridge.py."
            ),
        },
    }


@app.get("/theater/repeat-offenders", tags=["Analytics"])
async def get_repeat_offenders(min_incidents: int = Query(2)):
    """
    Identify device IDs with multiple incidents across sessions.
    Supports legal/enforcement use case from the patent.
    """
    incidents = await _sb_get("incidents", {
        "select": "device_id,theater_name,detected_at",
        "device_id": "not.is.null",
        "limit": "1000",
    })
    device_counts: dict = {}
    for i in incidents:
        did = i.get("device_id")
        if did:
            if did not in device_counts:
                device_counts[did] = {"count": 0, "theaters": set(), "last_seen": ""}
            device_counts[did]["count"] += 1
            device_counts[did]["theaters"].add(i.get("theater_name",""))
            if i.get("detected_at","") > device_counts[did]["last_seen"]:
                device_counts[did]["last_seen"] = i.get("detected_at","")

    repeat = [
        {
            "device_id":   did,
            "incident_count": data["count"],
            "theaters_seen":  list(data["theaters"]),
            "last_seen":      data["last_seen"],
        }
        for did, data in device_counts.items()
        if data["count"] >= min_incidents
    ]
    repeat.sort(key=lambda x: -x["incident_count"])
    return {"repeat_offenders": repeat, "total": len(repeat)}


# ── Dev server ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("\nCINEOS Theater API starting...")
    print("  Docs:      http://localhost:8001/theater/docs")
    print("  Health:    http://localhost:8001/theater/health")
    print("  Incidents: GET http://localhost:8001/theater/incidents")
    print("  Stats:     GET http://localhost:8001/theater/stats\n")
    uvicorn.run("theater_api:app", host="0.0.0.0", port=8001, reload=True)
