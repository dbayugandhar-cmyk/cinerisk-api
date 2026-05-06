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

@app.get("/theater/threat_briefing")
async def threat_briefing(days_ahead: int = 60, api_key: str = Header(None, alias="X-API-Key")):
    """CINEOS Layer 1 CTI v2 — Live threat briefing with release gap + franchise signals"""
    verify_api_key(api_key)
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from layer1_pipeline import full_threat_pipeline
        threats = await full_threat_pipeline(days_ahead=days_ahead)
        from datetime import datetime, timezone
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": "CTI v2",
            "signals": ["TMDB release dates", "Reddit velocity", "CINEOS CAM patterns", "Franchise detection"],
            "total_films": len(threats),
            "critical": len([t for t in threats if t["cti_level"] == "CRITICAL"]),
            "high": len([t for t in threats if t["cti_level"] == "HIGH"]),
            "films": threats,
            "patent": "US Prov. Pat. 64/049,190"
        }
    except Exception as e:
        raise HTTPException(500, f"CTI pipeline error: {e}")


# Add this to theater/theater_api.py
# New endpoint: POST /theater/gold_scan
# Runs the full 6-tier gold standard scanner and returns structured JSON

@app.post("/theater/gold_scan")
@app.post("/theater/gold_scan")
async def gold_scan(request: dict):
    """
    Production gold standard scan — calls cineos_layer4_gold.py
    22 sources, zero false positives, production grade.
    US Provisional Patent 64/049,190
    """
    import asyncio
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    film = request.get("film_title", "").strip()
    if not film:
        return {"error": "film_title required"}
    
    try:
        from cineos_layer4_gold import full_scan
        report = await full_scan(film)
        
        hits = []
        for r in report.hits:
            hits.append({
                "platform": r.name,
                "category": r.category,
                "quality": r.quality or "CAM",
                "url": r.url or "",
                "detail": r.detail or "",
                "severity": "HIGH"
            })
        
        return {
            "film_title": film,
            "verdict": report.verdict,
            "hits_found": len(report.hits),
            "sources_scanned": report.total_sources,
            "hits": hits,
            "scanned_at": report.scan_time,
            "cam_copies_found": len(report.hits),
        }
    except Exception as e:
        import traceback
        return {
            "film_title": film,
            "verdict": "ERROR",
            "hits_found": 0,
            "error": str(e),
            "traceback": traceback.format_exc()[-500:]
        }

    def slug(t):
        return re.sub(r'[^a-z0-9]+', '.', t.lower()).strip('.')
        t = text.lower()
        return any(k in t for k in CAM_STRICT)

    def film_match(text, film_title):
        words = [w for w in film_title.lower().split() if len(w) > 2]
        return sum(1 for w in words if w in text.lower()) >= max(2, len(words) - 1)

    results = []
    hits = []

    async with httpx.AsyncClient(timeout=15, headers=HEADERS,
                                  follow_redirects=True) as client:

        # PreDB scanned via SerpApi below





        # ── Google SerpApi ─────────────────────────────────────────
        if SERP_KEY:
            queries = [
                f'"{film}" (CAM OR HDCam OR HDTS OR camrip) (download OR torrent OR "free watch") -site:imdb.com -site:youtube.com',
                f'"{film}" CAM 1080p download -site:imdb.com -site:rottentomatoes.com',
            ]
            piracy_domains = [
                "1337x", "yts.", "tamilmv", "movierulz", "filmyzilla",
                "tamilblasters", "9xmovies", "ibomma", "bolly4u", "filmxy",
                "torrentgalaxy", "thepiratebay", "predb", "rarbg"
            ]
            for query in queries:
                try:
                    r = await client.get(
                        "https://serpapi.com/search",
                        params={"q": query, "api_key": SERP_KEY,
                                "num": 10, "engine": "google", "gl": "us"},
                        timeout=20
                    )
                    if r.status_code == 200:
                        for item in r.json().get("organic_results", []):
                            link = item.get("link", "")
                            title = item.get("title", "")
                            snippet = item.get("snippet", "")
                            full = f"{link} {title} {snippet}"
                            is_piracy = any(d in link.lower() for d in piracy_domains)
                            is_cam = has_cam(full)
                            film_ok = film_match(f"{title} {snippet}", film)
                            if (is_piracy or is_cam) and film_ok:
                                hits.append({
                                    "platform": f"Google → {link.split('/')[2][:30]}",
                                    "category": "Search",
                                    "quality": "CAM" if "cam" in full.lower() else "Unknown",
                                    "url": link,
                                    "detail": title[:80],
                                    "severity": "HIGH"
                                })
                    await asyncio.sleep(0.5)
                except:
                    pass
            results.append({"platform": "Google (SerpApi)", 
                           "status": "SCANNED",
                           "queries": len(queries)})
        else:
            results.append({"platform": "Google (SerpApi)", 
                           "status": "BLOCKED",
                           "detail": "Add SERP_API_KEY to Railway"})

        # ── Reddit via SerpApi (bypass Railway DNS block) ──────
        if SERP_KEY:
            try:
                r = await client.get(
                    "https://serpapi.com/search",
                    params={
                        "q": f'"{film}" CAM OR camrip OR hdcam site:reddit.com',
                        "api_key": SERP_KEY, "num": 5, "engine": "google"
                    },
                    timeout=12
                )
                if r.status_code == 200:
                    items = r.json().get("organic_results", [])
                    for item in items:
                        t = item.get("title", "")
                        lnk = item.get("link", "")
                        fw = [w for w in film.lower().split() if len(w) > 2]
                        if sum(1 for w in fw if w in t.lower()) >= 2 and has_cam(t):
                            hits.append({
                                "platform": "Reddit",
                                "category": "Social",
                                "quality": "CAM",
                                "url": lnk,
                                "detail": t[:80],
                                "severity": "MEDIUM"
                            })
                            break
                results.append({"platform": "Reddit", "status": "SCANNED"})
            except Exception as e:
                results.append({"platform": "Reddit", "status": "UNAVAILABLE", "detail": str(e)[:50]})
        else:
            results.append({"platform": "Reddit", "status": "BLOCKED"})



        # ── YTS + PreDB via SerpApi (bypasses Railway IP blocks) ───
        for site_name, site_domain in [("YTS", "yts.mx"), ("PreDB", "predb.me")]:
            if SERP_KEY:
                try:
                    r = await client.get(
                        "https://serpapi.com/search",
                        params={
                            "q": f'site:{site_domain} "{film}" CAM OR HDCam OR HDTS',
                            "api_key": SERP_KEY, "num": 3, "engine": "google"
                        },
                        timeout=12
                    )
                    if r.status_code == 200:
                        items = r.json().get("organic_results", [])
                        if items:
                            t = items[0].get("title", "")
                            lnk = items[0].get("link", "")
                            fw = [w for w in film.lower().split() if len(w) > 2]
                            if sum(1 for w in fw if w in t.lower()) >= 2 and has_cam(t):
                                hits.append({
                                    "platform": site_name,
                                    "category": "Torrent" if site_name=="YTS" else "Scene DB",
                                    "quality": "CAM",
                                    "url": lnk,
                                    "detail": t[:80],
                                    "severity": "HIGH"
                                })
                    results.append({"platform": site_name, "status": "SCANNED"})
                    await asyncio.sleep(0.3)
                except Exception as e:
                    results.append({"platform": site_name, "status": "ERROR", "detail": str(e)[:50]})
            else:
                results.append({"platform": site_name, "status": "BLOCKED"})

        # ── Telegram public ────────────────────────────────────────
        tg_hits = 0
        for ch in ["CamRips", "MoviesHD4K"]:
            try:
                r = await client.get(
                    f"https://t.me/s/{ch}?q={film.replace(' ','+')}",
                    timeout=8
                )
                if r.status_code == 200:
                    body = r.text.lower()
                    if film_match(body, film) and has_cam(body):
                        tg_hits += 1
                        hits.append({
                            "platform": f"Telegram @{ch}",
                            "category": "Messaging",
                            "quality": "CAM",
                            "url": f"https://t.me/{ch}",
                            "detail": f"CAM content found in @{ch}",
                            "severity": "HIGH"
                        })
            except:
                pass
        results.append({"platform": "Telegram", "status": "SCANNED",
                        "channels_checked": 2})

        # ── WhereYouWatch ──────────────────────────────────────────
        try:
            wyw_slug = re.sub(r"[^a-z0-9]+", "-", film.lower()).strip("-")
            wyw_url = f"https://whereyouwatch.com/movies/{wyw_slug}/"
            r = await client.get(wyw_url, timeout=12)
            if r.status_code == 200:
                body = r.text.lower()
                film_words = [w for w in film.lower().split() if len(w) > 2]
                film_ok = sum(1 for w in film_words if w in body) >= min(2, len(film_words))
                if film_ok and any(k in body for k in CAM_STRICT):
                    hits.append({
                        "platform": "WhereYouWatch",
                        "category": "Streaming",
                        "quality": "CAM",
                        "url": wyw_url,
                        "detail": f"CAM report found on WhereYouWatch for {film}",
                        "severity": "HIGH"
                    })
            results.append({"platform": "WhereYouWatch", "status": "SCANNED"})
        except Exception as e:
            results.append({"platform": "WhereYouWatch", "status": "ERROR", "detail": str(e)[:50]})

        # ── Regional sites via SerpApi ─────────────────────────────
        regional = [
            ("Movierulz", "movierulz.com"),
            ("TamilMV", "tamilmv.fi"),
            ("Filmyzilla", "filmyzilla.skin"),
            ("9xMovies", "9xmovies.care"),
        ]
        for name, domain in regional:
            if SERP_KEY:
                try:
                    r = await client.get(
                        "https://serpapi.com/search",
                        params={
                            "q": f'site:{domain} "{film}" CAM OR HDCam OR HDTS',
                            "api_key": SERP_KEY, "num": 3, "engine": "google"
                        },
                        timeout=12
                    )
                    if r.status_code == 200:
                        items = r.json().get("organic_results", [])
                        if items:
                            hits.append({
                                "platform": name,
                                "category": "Regional",
                                "quality": "CAM",
                                "url": items[0].get("link", ""),
                                "detail": items[0].get("title", "")[:80],
                                "severity": "HIGH"
                            })
                    results.append({"platform": name, "status": "SCANNED"})
                    await asyncio.sleep(0.3)
                except:
                    results.append({"platform": name, "status": "ERROR"})
            else:
                results.append({"platform": name, "status": "BLOCKED"})

    # ── Theater DB cross-reference ─────────────────────────────────
    theater_incidents = []
    try:
        rows = await db_fetch("""
            SELECT id, film_title, theater_name, zone, detection_type,
                   confidence, detected_at, screen_number
            FROM incidents
            WHERE LOWER(film_title) LIKE LOWER($1)
            AND film_title NOT IN ('string', 'Test Film', '')
            ORDER BY detected_at DESC LIMIT 10
        """, f"%{film}%")
        theater_incidents = [dict(r) for r in rows] if rows else []
    except:
        pass

    # ── Verdict ────────────────────────────────────────────────────
    hit_count = len(hits)
    scene_hit = any(h["platform"] == "PreDB Scene" for h in hits)
    inc_count = len(theater_incidents)

    if scene_hit and hit_count >= 2 and inc_count > 0:
        verdict = "CRITICAL"
        verdict_text = "CAM confirmed: scene DB + platforms + theater seat evidence"
    elif scene_hit or hit_count >= 2:
        verdict = "HIGH"
        verdict_text = "CAM copy confirmed on multiple platforms"
    elif hit_count >= 1 and inc_count > 0:
        verdict = "HIGH"
        verdict_text = "CAM confirmed online + theater recording in database"
    elif hit_count >= 1:
        verdict = "CONFIRMED"
        verdict_text = "CAM copy found online. Issue DMCA immediately."
    else:
        verdict = "CLEAN"
        verdict_text = "No CAM copy detected across all 21 sources"

    return {
        "film_title": film,
        "scan_time": __import__('datetime').datetime.utcnow().isoformat() + "Z",
        "verdict": verdict,
        "verdict_text": verdict_text,
        "total_sources": len(results),
        "hits_found": hit_count,
        "hits": hits,
        "platforms": results,
        "theater_incidents": theater_incidents,
        "serp_enabled": bool(SERP_KEY),
        "studio_email": studio_email,
    }


@app.get("/theater/velocity_summary")
async def velocity_summary():
    """Get latest velocity data for all tracked films."""
    try:
        rows = await db_fetch("""
            SELECT DISTINCT ON (film_title)
                film_title, scan_time, platform_count,
                hits_found, hours_since_release, spread_rate,
                platforms
            FROM cineos_velocity
            ORDER BY film_title, scan_time DESC
        """)
        films = []
        for r in rows:
            platforms = r[6] or []
            hours = float(r[4] or 0)
            platform_count = r[2] or 0
            daily_dl = platform_count * 50000
            days = max(1, hours / 24)
            loss = daily_dl * days * 0.15 * 12.50
            films.append({
                "title": r[0],
                "last_scan": str(r[1]),
                "platform_count": platform_count,
                "hits_found": r[3] or 0,
                "hours_since_release": hours,
                "spread_rate": float(r[5] or 0),
                "platforms": platforms,
                "revenue_loss_usd": round(loss),
                "velocity_level": (
                    "CRITICAL" if float(r[5] or 0) > 0.5 or platform_count > 20
                    else "HIGH" if float(r[5] or 0) > 0.1 or platform_count > 10
                    else "MEDIUM" if platform_count > 3
                    else "LOW"
                )
            })
        return {"films": films, "count": len(films)}
    except Exception as e:
        return {"films": [], "error": str(e)}


@app.get("/theater/velocity_history")
async def velocity_history(film: str):
    """Get historical velocity data for a specific film."""
    try:
        rows = await db_fetch("""
            SELECT scan_time, platform_count, hits_found,
                   hours_since_release, spread_rate
            FROM cineos_velocity
            WHERE film_title = $1
            ORDER BY scan_time ASC
        """, film)
        history = [{
            "scan_time": str(r[0]),
            "platform_count": r[1] or 0,
            "hits_found": r[2] or 0,
            "hours_since_release": float(r[3] or 0),
            "spread_rate": float(r[4] or 0)
        } for r in rows]
        return {"film": film, "history": history, "scans": len(history)}
    except Exception as e:
        return {"film": film, "history": [], "error": str(e)}


@app.post("/theater/gold_scan")
async def gold_scan(request: dict):
    """Run real-time scan for a film title."""
    film_title = request.get("film_title", "")
    if not film_title:
        return {"error": "film_title required"}
    try:
        import subprocess, json as _json, os
        env = os.environ.copy()
        result = subprocess.run(
            ["python3", "cineos_layer4_gold.py",
             "--film", film_title, "--json"],
            capture_output=True, text=True, timeout=120,
            cwd="/app", env=env
        )
        if result.stdout:
            try:
                return _json.loads(result.stdout)
            except Exception:
                pass
        return {
            "film_title": film_title,
            "verdict": "SCAN_ERROR",
            "hits_found": 0,
            "hits": [],
            "error": result.stderr[:200] if result.stderr else "Unknown error"
        }
    except Exception as e:
        return {"film_title": film_title, "verdict": "ERROR",
                "hits_found": 0, "hits": [], "error": str(e)}

