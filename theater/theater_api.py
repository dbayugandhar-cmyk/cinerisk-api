import os
from datetime import datetime
from typing import Optional, Literal
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx

DATABASE_URL = os.getenv("DATABASE_URL", "")
CINEOS_API = os.getenv("CINEOS_API", "https://web-production-f7244.up.railway.app")

try:
    import asyncpg
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False

pool = None

async def get_pool():
    global pool
    if pool is None and PG_AVAILABLE and DATABASE_URL:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return pool

async def db_fetch(query, *args):
    p = await get_pool()
    if not p: raise HTTPException(503, "Database not available")
    async with p.acquire() as conn:
        return [dict(r) for r in await conn.fetch(query, *args)]

async def db_fetchrow(query, *args):
    p = await get_pool()
    if not p: raise HTTPException(503, "Database not available")
    async with p.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else {}

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS incidents (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    theater_name text, screen_number text, seat_location text,
    zone text, detection_type text DEFAULT 'PHONE', confidence float,
    film_title text, alerted boolean DEFAULT false, device_id text,
    detected_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS screenings (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    theater_name text, screen_number text, film_title text,
    genre text, release_strategy text,
    started_at timestamptz DEFAULT now(), ended_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_inc_at ON incidents(detected_at DESC);
"""

def s(r):
    if isinstance(r, dict):
        return {k: v.isoformat() if hasattr(v,'isoformat') else v for k,v in r.items()}
    return r

CINEOS_API_KEY = os.getenv("CINEOS_API_KEY", "")

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if CINEOS_API_KEY and x_api_key != CINEOS_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

@asynccontextmanager
async def lifespan(app):
    if PG_AVAILABLE and DATABASE_URL:
        try:
            p = await get_pool()
            async with p.acquire() as conn:
                await conn.execute(CREATE_TABLES)
            print("DB ready")
        except Exception as e:
            print(f"DB: {e}")
    yield
    if pool: await pool.close()

app = FastAPI(title="CINEOS Theater API", description="US Prov. Pat. 64/049,190", version="2.0.0", docs_url="/theater/docs", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class IncidentCreate(BaseModel):
    theater_name: str; screen_number: str; seat_location: Optional[str]=None
    zone: Literal["LEFT","CENTER","RIGHT"]; detection_type: str="PHONE"
    confidence: float=Field(...,ge=0,le=1); film_title: Optional[str]=None
    alerted: bool=False; device_id: Optional[str]=None

class ScreeningCreate(BaseModel):
    theater_name: str; screen_number: str; film_title: str
    genre: Optional[str]=None; release_strategy: Optional[str]=None

@app.get("/theater/health")
async def health():
    db_status = "not configured"
    if PG_AVAILABLE and DATABASE_URL:
        try:
            await db_fetch("SELECT 1"); db_status="connected"
        except Exception as e:
            db_status=f"error: {str(e)[:60]}"
    return {"status":"ok","version":"2.0.0","patent":"US Prov. Pat. 64/049,190","database":db_status,"timestamp":datetime.utcnow().isoformat()}

@app.post("/theater/incident")
async def log_incident(inc: IncidentCreate, api_key: str = Depends(verify_api_key)):
    row = await db_fetchrow("INSERT INTO incidents (theater_name,screen_number,seat_location,zone,detection_type,confidence,film_title,alerted,device_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *",
        inc.theater_name,inc.screen_number,inc.seat_location,inc.zone,inc.detection_type,round(inc.confidence,4),inc.film_title,inc.alerted,inc.device_id)
    return {"status":"logged","incident":s(row)}

@app.get("/theater/incidents")
async def get_incidents(theater:Optional[str]=None,film:Optional[str]=None,hours:Optional[int]=None,limit:int=Query(200,ge=1,le=1000)):
    conds,args,i=["1=1"],[],1
    if theater: conds.append(f"theater_name ILIKE ${i}"); args.append(f"%{theater}%"); i+=1
    if film: conds.append(f"film_title ILIKE ${i}"); args.append(f"%{film}%"); i+=1
    if hours: conds.append(f"detected_at >= NOW() - INTERVAL '{hours} hours'")
    args.append(limit)
    rows=await db_fetch(f"SELECT * FROM incidents WHERE {' AND '.join(conds)} ORDER BY detected_at DESC LIMIT ${i}",*args)
    return {"count":len(rows),"incidents":[s(r) for r in rows]}

@app.post("/theater/screening")
async def create_screening(sc: ScreeningCreate):
    row=await db_fetchrow("INSERT INTO screenings (theater_name,screen_number,film_title,genre,release_strategy) VALUES ($1,$2,$3,$4,$5) RETURNING *",sc.theater_name,sc.screen_number,sc.film_title,sc.genre,sc.release_strategy)
    return {"status":"created","screening":s(row)}

@app.get("/theater/screenings")
async def get_screenings():
    rows=await db_fetch("SELECT * FROM screenings ORDER BY started_at DESC LIMIT 50")
    return [s(r) for r in rows]

@app.get("/theater/stats")
async def get_stats():
    total=await db_fetchrow("SELECT COUNT(*) as n FROM incidents")
    today=await db_fetchrow("SELECT COUNT(*) as n FROM incidents WHERE detected_at::date=CURRENT_DATE")
    theaters=await db_fetchrow("SELECT COUNT(DISTINCT theater_name) as n FROM incidents")
    avg_conf=await db_fetchrow("SELECT ROUND(AVG(confidence)::numeric,3) as n FROM incidents")
    zones=await db_fetch("SELECT zone,COUNT(*) as c FROM incidents GROUP BY zone ORDER BY c DESC LIMIT 3")
    total_n=int(total.get("n",0) or 0)
    return {"total_incidents":total_n,"incidents_today":int(today.get("n",0) or 0),"theaters_active":int(theaters.get("n",0) or 0),"avg_confidence":float(avg_conf.get("n") or 0),"high_risk_zones":[z["zone"] for z in zones if int(z.get("c",0))>2],"compliance_score":max(0,round(100-min(total_n/100,1)*30))}

@app.get("/theater/risk/{film_title}")
async def get_film_risk(film_title:str,genre:str=Query("action"),hype:str=Query("medium"),strategy:str=Query("staggered"),budget_m:float=Query(100.0)):
    engine_data=None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r=await client.post(f"{CINEOS_API}/simulate",json={"genre":genre,"hype":hype,"strategy":strategy,"budget_m":budget_m,"film_title":film_title})
        if r.status_code==200: engine_data=r.json()
    except: pass
    observed=await db_fetch("SELECT * FROM incidents WHERE film_title ILIKE $1 LIMIT 500",f"%{film_title}%")
    predicted_leak=None
    if engine_data:
        cur=next((s for s in engine_data.get("strategies",[]) if s["strategy"]==strategy),None)
        if cur: predicted_leak=cur.get("leak_day_low")
    return {"film_title":film_title,"layer1_prediction":engine_data,"layer2_observed_incidents":len(observed),"layer3_comparison":{"predicted_leak_day":predicted_leak,"calibration_note":"Need 10+ screenings." if len(observed)<10 else "Run feedback/bridge.py."}}

@app.get("/theater/repeat-offenders")
async def repeat_offenders(min_incidents:int=Query(2)):
    rows=await db_fetch("SELECT device_id,COUNT(*) as incident_count,ARRAY_AGG(DISTINCT theater_name) as theaters,MAX(detected_at) as last_seen FROM incidents WHERE device_id IS NOT NULL GROUP BY device_id HAVING COUNT(*)>=$1 ORDER BY incident_count DESC",min_incidents)
    return {"repeat_offenders":[s(r) for r in rows],"total":len(rows)}

if __name__=="__main__":
    import uvicorn
    uvicorn.run("theater_api:app",host="0.0.0.0",port=8001,reload=True)


@app.get("/theater/alerts")
async def get_alerts():
    try:
        rows = await db_fetch("""
            SELECT i.id, i.theater_name, i.film_title, i.zone,
                   i.confidence, i.detected_at,
                   s.scan_time, s.hits_found, s.platforms,
                   s.first_hit_url, s.gap_minutes
            FROM incidents i
            JOIN scan_results s ON s.incident_id = i.id
            WHERE i.alerted = true
            ORDER BY i.detected_at DESC LIMIT 50
        """)
        return {"count": len(rows), "alerts": [dict(r) for r in rows]}
    except Exception as e:
        return {"count": 0, "alerts": [], "error": str(e)}

@app.get("/theater/scan_status/{film_title}")
async def scan_status(film_title: str):
    try:
        row = await db_fetchrow("""
            SELECT film_title, hits_found, platforms, first_hit_url,
                   gap_minutes, scan_time
            FROM scan_results
            WHERE LOWER(film_title) = LOWER($1)
            ORDER BY scan_time DESC LIMIT 1
        """, film_title)
        if not row:
            return {"film_title": film_title, "status": "not_scanned", "hits": 0}
        return {
            "film_title": film_title,
            "status": "cam_confirmed" if row["hits_found"] > 0 else "clean",
            "hits": row["hits_found"],
            "platforms": row["platforms"],
            "first_url": row["first_hit_url"],
            "gap_minutes": row["gap_minutes"],
            "scan_time": str(row["scan_time"]),
        }
    except Exception as e:
        return {"film_title": film_title, "status": "error", "error": str(e)}

@app.post("/theater/manual_scan")
async def manual_scan(film_title: str):
    from layer4_trigger import search_piracy
    scan = await search_piracy(film_title)
    return {"film_title": film_title, "hits": scan["hits"],
            "platforms": scan["platforms"], "first_url": scan["first_url"]}
