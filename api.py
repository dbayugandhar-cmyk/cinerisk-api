"""
CineRisk API v1 — FastAPI bridge over engine.py
Run: python3 -m uvicorn api:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal, List, Optional
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import simulate, SimulationOutput

app = FastAPI(title="CineRisk API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimulateRequest(BaseModel):
    genre:    Literal["action","scifi","thriller","horror","drama","animation"]
    hype:     Literal["low","medium","high"]
    strategy: Literal["global_day1","staggered","streaming_delay"]
    budget_m: float = Field(100.0, ge=1.0, le=2000.0)
    film_title: Optional[str] = None

class StrategyResult(BaseModel):
    strategy:      str
    risk_score:    float
    risk_label:    str
    revenue_low:   float
    revenue_high:  float
    revenue_mid:   float
    confidence:    float
    leak_day_low:  int
    leak_day_high: int
    explanation:   List[str]
    is_recommended: bool
    is_current:     bool

class SimulateResponse(BaseModel):
    film_title:          Optional[str]
    genre:               str
    hype:                str
    budget_m:            float
    current_strategy:    str
    recommended:         str
    recommendation_text: str
    strategies:          List[StrategyResult]

def _fmt(out, title=None):
    return SimulateResponse(
        film_title=title,
        genre=out.film_genre,
        hype=out.film_hype,
        budget_m=out.budget_m,
        current_strategy=out.current_strategy,
        recommended=out.recommended,
        recommendation_text=out.recommendation_text,
        strategies=[
            StrategyResult(
                strategy=r.strategy,
                risk_score=r.risk_score,
                risk_label=r.risk_label,
                revenue_low=r.revenue_low,
                revenue_high=r.revenue_high,
                revenue_mid=r.revenue_mid,
                confidence=r.confidence,
                leak_day_low=r.leak_day_low,
                leak_day_high=r.leak_day_high,
                explanation=r.explanation,
                is_recommended=(r.strategy == out.recommended),
                is_current=(r.strategy == out.current_strategy),
            ) for r in out.results
        ]
    )

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}

@app.get("/genres")
def genres():
    return {"genres": [
        {"id":"action",    "label":"Action",    "sensitivity":0.72},
        {"id":"scifi",     "label":"Sci-Fi",    "sensitivity":0.68},
        {"id":"thriller",  "label":"Thriller",  "sensitivity":0.58},
        {"id":"horror",    "label":"Horror",    "sensitivity":0.52},
        {"id":"animation", "label":"Animation", "sensitivity":0.38},
        {"id":"drama",     "label":"Drama",     "sensitivity":0.24},
    ]}

@app.get("/strategies")
def strategies():
    return {"strategies": [
        {"id":"global_day1",     "label":"Global Day-One",      "delay_factor":0.0},
        {"id":"staggered",       "label":"Staggered by Region",  "delay_factor":0.52},
        {"id":"streaming_delay", "label":"Streaming Delay",      "delay_factor":0.28},
    ]}

@app.post("/simulate", response_model=SimulateResponse)
def simulate_film(req: SimulateRequest):
    try:
        out = simulate(req.genre, req.hype, req.strategy, req.budget_m)
        return _fmt(out, req.film_title)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/compare")
def compare(req: SimulateRequest):
    try:
        out = simulate(req.genre, req.hype, req.strategy, req.budget_m)
        return {
            "film_title":    req.film_title,
            "recommended":   out.recommended,
            "recommendation": out.recommendation_text,
            "comparison": [{
                "strategy":      r.strategy,
                "label":         r.strategy.replace("_"," ").title(),
                "risk":          r.risk_score,
                "risk_label":    r.risk_label,
                "revenue_range": f"${r.revenue_low}M-${r.revenue_high}M",
                "revenue_mid":   r.revenue_mid,
                "leak_window":   f"Day {r.leak_day_low}-{r.leak_day_high}",
                "confidence":    f"{r.confidence:.0%}",
                "recommended":   r.strategy == out.recommended,
                "current":       r.strategy == out.current_strategy,
            } for r in out.results]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))