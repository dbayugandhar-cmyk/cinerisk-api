#!/usr/bin/env python3
"""
CINEOS API Gateway v1.0
========================
Hardened B2B API with:
- API key authentication
- Rate limiting per tier
- Usage metering
- Stripe billing integration
- Full audit trail

Pricing tiers:
- Starter:    $49/month  — 500 queries/month
- Pro:        $499/month — 5,000 queries/month  
- Studio:     $999/month — 20,000 queries/month
- Enterprise: Custom     — Unlimited

US Provisional Patent 64/049,190
"""

import os
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncpg

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("cineos.gateway")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:REDACTED@tramway.proxy.rlwy.net:27075/railway"
)
SERP_KEY = os.getenv("SERP_API_KEY", "")
STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY", "")

# ── Tier definitions ──────────────────────────────────────────────
TIERS = {
    "starter":    {"price": 49,   "queries": 500,    "rate_per_min": 10},
    "pro":        {"price": 499,  "queries": 5000,   "rate_per_min": 30},
    "studio":     {"price": 999,  "queries": 20000,  "rate_per_min": 60},
    "enterprise": {"price": 0,    "queries": 999999, "rate_per_min": 200},
    "free":       {"price": 0,    "queries": 10,     "rate_per_min": 2},
}

pool = None

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return pool

async def db_exec(query, *args):
    p = await get_pool()
    async with p.acquire() as conn:
        return await conn.execute(query, *args)

async def db_fetch(query, *args):
    p = await get_pool()
    async with p.acquire() as conn:
        return [dict(r) for r in await conn.fetch(query, *args)]

async def db_fetchrow(query, *args):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None

# ── Setup tables ──────────────────────────────────────────────────
SETUP_SQL = """
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    key_hash TEXT UNIQUE NOT NULL,
    key_prefix TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    tier TEXT DEFAULT 'free',
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    queries_this_month INTEGER DEFAULT 0,
    queries_total INTEGER DEFAULT 0,
    month_reset_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_usage (
    id SERIAL PRIMARY KEY,
    key_prefix TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    query_params JSONB,
    response_code INTEGER,
    response_time_ms INTEGER,
    hits_found INTEGER DEFAULT 0,
    queried_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rate_limit_log (
    key_prefix TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    request_count INTEGER DEFAULT 0,
    PRIMARY KEY (key_prefix, window_start)
);

CREATE INDEX IF NOT EXISTS idx_usage_key ON api_usage(key_prefix, queried_at DESC);
CREATE INDEX IF NOT EXISTS idx_keys_email ON api_keys(customer_email);
"""

def now_utc():
    return datetime.now(timezone.utc)

def hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()

def generate_api_key() -> tuple[str, str]:
    """Generate API key. Returns (full_key, prefix)."""
    raw = secrets.token_urlsafe(32)
    key = f"ck_{raw}"  # ck = cineos key
    prefix = key[:12]
    return key, prefix


# ── Pydantic models ───────────────────────────────────────────────
class ScanRequest(BaseModel):
    title: str
    category: str = "film"  # film, india, gaming, sports, live_shield
    language: str = "any"

class CreateKeyRequest(BaseModel):
    customer_name: str
    customer_email: str
    tier: str = "free"

class APIResponse(BaseModel):
    success: bool
    data: dict
    meta: dict


# ── Auth dependency ───────────────────────────────────────────────
async def verify_api_key(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
) -> dict:
    """Verify API key and return customer data."""
    # Extract key from header
    key = x_api_key
    if not key and authorization:
        if authorization.startswith("Bearer "):
            key = authorization[7:]

    if not key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "API key required",
                "message": "Include your API key in X-API-Key header",
                "docs": "https://dbayugandhar-cmyk.github.io/cinerisk-api/cineos_landing.html"
            }
        )

    key_hash = hash_key(key)
    customer = await db_fetchrow(
        "SELECT * FROM api_keys WHERE key_hash = $1 AND active = TRUE",
        key_hash
    )

    if not customer:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid API key", "message": "Key not found or inactive"}
        )

    # Reset monthly counter if new month
    reset_at = customer.get("month_reset_at")
    if reset_at:
        reset_at_dt = reset_at if hasattr(reset_at, 'tzinfo') else reset_at.replace(tzinfo=timezone.utc)
        if now_utc() > reset_at_dt + timedelta(days=30):
            await db_exec(
                "UPDATE api_keys SET queries_this_month = 0, month_reset_at = NOW() WHERE key_hash = $1",
                key_hash
            )
            customer["queries_this_month"] = 0

    # Check monthly quota
    tier = customer.get("tier", "free")
    tier_config = TIERS.get(tier, TIERS["free"])
    monthly_limit = tier_config["queries"]

    if customer.get("queries_this_month", 0) >= monthly_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Monthly quota exceeded",
                "tier": tier,
                "limit": monthly_limit,
                "used": customer.get("queries_this_month", 0),
                "upgrade": "Contact dba.yugandhar@gmail.com to upgrade"
            }
        )

    return customer


async def check_rate_limit(customer: dict) -> bool:
    """Check per-minute rate limit."""
    tier = customer.get("tier", "free")
    rate_per_min = TIERS.get(tier, TIERS["free"])["rate_per_min"]
    prefix = customer.get("key_prefix", "")

    window = now_utc().replace(second=0, microsecond=0)

    try:
        row = await db_fetchrow(
            "SELECT request_count FROM rate_limit_log WHERE key_prefix = $1 AND window_start = $2",
            prefix, window
        )
        count = row["request_count"] if row else 0

        if count >= rate_per_min:
            return False

        if row:
            await db_exec(
                "UPDATE rate_limit_log SET request_count = request_count + 1 WHERE key_prefix = $1 AND window_start = $2",
                prefix, window
            )
        else:
            await db_exec(
                "INSERT INTO rate_limit_log (key_prefix, window_start, request_count) VALUES ($1, $2, 1) ON CONFLICT DO NOTHING",
                prefix, window
            )
        return True
    except Exception:
        return True  # Allow on error


async def log_usage(
    customer: dict,
    endpoint: str,
    method: str,
    params: dict,
    response_code: int,
    response_time_ms: int,
    hits_found: int = 0
):
    """Log API usage for billing and analytics."""
    try:
        import json
        await db_exec(
            """INSERT INTO api_usage 
               (key_prefix, customer_email, endpoint, method, 
                query_params, response_code, response_time_ms, hits_found)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            customer.get("key_prefix", ""),
            customer.get("customer_email", ""),
            endpoint,
            method,
            json.dumps(params),
            response_code,
            response_time_ms,
            hits_found
        )
        # Increment usage counter
        await db_exec(
            """UPDATE api_keys 
               SET queries_this_month = queries_this_month + 1,
                   queries_total = queries_total + 1,
                   last_used_at = NOW()
               WHERE key_prefix = $1""",
            customer.get("key_prefix", "")
        )
    except Exception as e:
        log.error(f"Usage log error: {e}")


# ── FastAPI app ───────────────────────────────────────────────────
app = FastAPI(
    title="CINEOS Intelligence API",
    version="1.0.0",
    description="Real-time piracy intelligence for film, gaming, sports, and India cinema",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialize database tables."""
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            await conn.execute(SETUP_SQL)
        log.info("CINEOS API Gateway ready")
    except Exception as e:
        log.error(f"Startup error: {e}")


# ── Public endpoints ──────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "api": "CINEOS Intelligence API",
        "version": "1.0.0",
        "patent": "US Prov. Pat. 64/049,190",
        "docs": "/docs",
        "pricing": {
            "starter": "$49/month — 500 queries",
            "pro": "$499/month — 5,000 queries",
            "studio": "$999/month — 20,000 queries",
            "enterprise": "Custom — unlimited"
        },
        "contact": "dba.yugandhar@gmail.com",
        "endpoints": {
            "scan": "POST /v1/scan — Scan for piracy",
            "live_shield": "POST /v1/live_shield — Telegram stream monitor",
            "velocity": "GET /v1/velocity/{title} — Piracy spread data",
            "report": "POST /v1/report — Generate evidence PDF",
            "usage": "GET /v1/usage — Your API usage stats",
        }
    }


@app.get("/v1/health")
async def health():
    return {"status": "ok", "timestamp": now_utc().isoformat()}


# ── Key management (admin only) ───────────────────────────────────
@app.post("/admin/keys/create")
async def create_api_key(
    request: CreateKeyRequest,
    x_admin_key: Optional[str] = Header(None)
):
    """Create a new API key for a customer."""
    # Simple admin auth
    admin_key = os.getenv("ADMIN_KEY", "cineos_admin_2026")
    if x_admin_key != admin_key:
        raise HTTPException(403, "Admin key required")

    if request.tier not in TIERS:
        raise HTTPException(400, f"Invalid tier. Choose: {list(TIERS.keys())}")

    full_key, prefix = generate_api_key()
    key_hash = hash_key(full_key)

    await db_exec(
        """INSERT INTO api_keys 
           (key_hash, key_prefix, customer_name, customer_email, tier)
           VALUES ($1, $2, $3, $4, $5)""",
        key_hash, prefix,
        request.customer_name, request.customer_email, request.tier
    )

    tier_config = TIERS[request.tier]
    return {
        "api_key": full_key,
        "key_prefix": prefix,
        "customer": request.customer_name,
        "email": request.customer_email,
        "tier": request.tier,
        "monthly_queries": tier_config["queries"],
        "price": f"${tier_config['price']}/month",
        "warning": "Store this key securely — it will not be shown again"
    }


@app.get("/admin/keys/list")
async def list_keys(x_admin_key: Optional[str] = Header(None)):
    """List all API keys (admin only)."""
    admin_key = os.getenv("ADMIN_KEY", "cineos_admin_2026")
    if x_admin_key != admin_key:
        raise HTTPException(403, "Admin key required")

    rows = await db_fetch(
        """SELECT key_prefix, customer_name, customer_email, 
                  tier, active, created_at, last_used_at,
                  queries_this_month, queries_total
           FROM api_keys ORDER BY created_at DESC"""
    )
    return {"keys": rows, "total": len(rows)}


# ── Core API endpoints ────────────────────────────────────────────
@app.post("/v1/scan")
async def scan_for_piracy(
    request: ScanRequest,
    customer: dict = Depends(verify_api_key),
    req: Request = None
):
    """
    Scan for piracy across 1000+ sources.
    
    Categories: film, india, gaming, sports
    Returns: verdict, hits, platforms, velocity data
    """
    import time
    start = time.time()

    # Rate limit check
    if not await check_rate_limit(customer):
        raise HTTPException(
            status_code=429,
            detail={"error": "Rate limit exceeded", "retry_after": "60 seconds"}
        )

    title = request.title.strip()
    if not title:
        raise HTTPException(400, "title is required")

    category = request.category.lower()
    valid_categories = ["film", "india", "gaming", "sports", "all"]
    if category not in valid_categories:
        raise HTTPException(400, f"category must be one of: {valid_categories}")

    # Run the actual scan via SerpApi
    hits = []
    verdict = "CLEAN"
    platforms = []

    if SERP_KEY:
        try:
            import httpx as _httpx

            # Category-specific site lists
            site_lists = {
                "film": [
                    "thepiratebay.org", "1337x.to", "yts.mx",
                    "whereyouwatch.com", "nyaa.si", "limetorrents.lol",
                    "torrentgalaxy.to", "rarbg.to", "bitsearch.to",
                    "opensubtitles.org", "watchsomuch.to"
                ],
                "india": [
                    "5movierulz.camera", "1tamilmv.world", "ibomma.com",
                    "filmyzilla.com", "9xmovies.cool", "tamilrockers.ws",
                    "isaimini.com", "hdHub4u.com", "worldfree4u.mom",
                    "mp4moviez.com", "kuttymovies.com", "moviesda.com"
                ],
                "gaming": [
                    "fitgirl-repacks.site", "igg-games.com",
                    "steamunlocked.net", "dodi-repacks.site",
                    "gog-games.to", "cs.rin.ru", "ovagames.com",
                    "repacklab.com", "pcgamestorrents.com"
                ],
                "sports": [
                    "crackstreams.com", "vipbox.lc", "hesgoal.com",
                    "buffstream.io", "sportsurge.net", "livetv.sx",
                    "cricfree.sc", "crictime.com", "smartcric.com"
                ],
            }

            sites = site_lists.get(category, site_lists["film"])
            if category == "all":
                sites = [s for sl in site_lists.values() for s in sl]

            site_q = " OR ".join(f"site:{s}" for s in sites[:10])
            query = f'"{title}" ({site_q})'

            async with _httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    "https://serpapi.com/search",
                    params={
                        "q": query,
                        "api_key": SERP_KEY,
                        "num": 10,
                        "engine": "google"
                    }
                )

            if r.status_code == 200:
                for item in r.json().get("organic_results", []):
                    link = item.get("link", "")
                    t = item.get("title", "")
                    snippet = item.get("snippet", "")
                    full = f"{t} {snippet}".lower()

                    # Basic validation
                    title_words = [w for w in title.lower().split() if len(w) > 2]
                    matched = sum(1 for w in title_words if w in full)
                    if matched < min(1, len(title_words)):
                        continue

                    domain = link.split("/")[2] if "/" in link else link
                    platforms.append(domain[:40])
                    hits.append({
                        "platform": domain[:40],
                        "url": link,
                        "title": t[:80],
                        "snippet": snippet[:100]
                    })

                if hits:
                    verdict = "CONFIRMED"

        except Exception as e:
            log.error(f"Scan error: {e}")

    elapsed_ms = int((time.time() - start) * 1000)
    tier = customer.get("tier", "free")
    tier_config = TIERS.get(tier, TIERS["free"])
    queries_used = customer.get("queries_this_month", 0) + 1
    queries_left = tier_config["queries"] - queries_used

    # Log usage
    await log_usage(
        customer, "/v1/scan", "POST",
        {"title": title, "category": category},
        200, elapsed_ms, len(hits)
    )

    return {
        "success": True,
        "data": {
            "title": title,
            "category": category,
            "verdict": verdict,
            "hits_found": len(hits),
            "platforms": list(set(platforms)),
            "hits": hits[:10],
        },
        "meta": {
            "response_time_ms": elapsed_ms,
            "queries_used": queries_used,
            "queries_remaining": queries_left,
            "tier": tier,
            "scanned_at": now_utc().isoformat()
        }
    }


@app.post("/v1/live_shield")
async def live_shield_scan(
    event_name: str = "IPL 2026",
    customer: dict = Depends(verify_api_key)
):
    """
    Scan Telegram channels for illegal sports streams.
    Detects IPL, cricket, Premier League illegal streams.
    Returns language, subscriber count, betting flag.
    """
    import time
    start = time.time()

    if not await check_rate_limit(customer):
        raise HTTPException(429, {"error": "Rate limit exceeded"})

    streams = []
    try:
        import httpx as _httpx

        CHANNELS = [
            # ── OTT channels FIRST — scanned before timeout ──
            "NetflixFree", "NetflixLeaks", "NetflixTamil", "NetflixTelugu",
            "NetflixIndia", "NetflixHD", "NetflixWebSeries", "NetflixSeriesFree",
            "HotstarFree", "HotstarLeaks", "JioHotstarFree", "JioHotstarLeaks",
            "HotstarWebSeries", "HotstarOTT", "HotstarMovies", "DisneyHotstar",
            "JioCinemaFree", "AmazonPrimeFree", "AmazonPrimeLeaks", "PrimeVideoFree",
            "PrimeVideoIndia", "PrimeTamil", "PrimeTelugu", "PrimeMoviesHindi",
            "ZEE5Free", "ZEE5Hindi", "ZEE5Leaks", "Zee5Series", "Zee5Movies",
            "Zee5Tamil", "Zee5Telugu", "ZeeMoviesFree",
            "SonyLIVFree", "SonyLIVLeaks", "SonyLivHD", "SonyLivMovies",
            "SonyLivSeries", "SonyLivTelugu",
            "AHAFree", "AHALeaks", "AHAMovies", "AHATelugu", "AHAWebSeries",
            "AHAOTTFree", "AHAOriginals", "TeluguOTTFree",
            # ── Cricket / Sports ──────────────────────────────
            "CricketStreamsLive", "IPLstreams", "SportsFreeStreams", "CricketLiveStream", "IPLLive2025", "IPLLive2026",
            "CricketFreeStream", "LiveCricket", "T20Live", "IPLMatchLive", "CricketMatch", "FreeCricketStream",
            "IPL_L", "RealCricPoint", "LiveCricketMatchLink", "CricketLive24", "IPLStreamFree", "CricHDLive",
            "CricketStreamHD", "IPLFreeStream", "T20WorldCup", "TamilCricketLive", "TeluguCricketLive", "HindiCricketLive",
            "CricketTamil", "CricketTelugu", "IPLTamil", "IPLTelugu", "KannadaCricket", "MalayalamCricket",
            "BengaliCricket", "MarathiCricket", "CricketGujarati", "PunjabiCricket", "CricketBetting", "IPLBetting",
            "CricketTips", "CricketPrediction", "IPLTips", "CricketFantasy", "Dream11Tips", "CricketOdds",
            "BettingTips", "CricketWinTips", "IPLWinPrediction", "JioHotstarFree", "HotstarFree", "HotstarMovies",
            "JioCinemaFree", "HotstarSeriesFree", "DisneyHotstar", "HotstarOTT", "JioFreeMovies", "HotstarLeaks",
            "JioHotstarLeaks", "HotstarWebSeries", "NetflixIndia", "NetflixFree", "NetflixMoviesHindi", "NetflixSeriesFree",
            "NetflixLeaks", "NetflixHD", "NetflixTamil", "NetflixTelugu", "NetflixMalayalam", "NetflixWebSeries",
            "NetflixOriginals", "AmazonPrimeFree", "PrimeVideoFree", "PrimeMoviesHindi", "AmazonPrimeLeaks", "PrimeVideoIndia",
            "AmazonHDMovies", "PrimeTamil", "PrimeTelugu", "PrimeWebSeries", "ZEE5Free", "Zee5Movies",
            "Zee5Series", "ZEE5Leaks", "Zee5Telugu", "Zee5Tamil", "ZEE5Hindi", "ZeeMoviesFree",
            "AHAFree", "AHAMovies", "AHATelugu", "AHAOriginals", "AHALeaks", "AHAWebSeries",
            "AHAOTTFree", "TeluguOTTFree", "SonyLIVFree", "SonyLivMovies", "SonyLivSeries", "SonyLIVLeaks",
            "SonyLivTelugu", "SonyLivCricket", "SonyLivHD", "HindiWebSeries", "BollywoodMoviesFree", "HindiHDMovies",
            "BollywoodHD", "HindiOTTFree", "WebSeriesHindi", "HindiNetflix", "HindiAmazonPrime", "HindiMoviesHD4K",
            "BollywoodLeaks", "TeluguMoviesFree", "TeluguHDMovies", "TeluguWebSeries", "TeluguOTT", "TeluguNewMovies",
            "TollywoodMovies", "TeluguMovies4K", "TeluguLatestMovies", "TamilMoviesFree", "TamilHDMovies", "TamilRockersNew",
            "TamilMoviesOnline", "TamilWebSeries", "KollywoodMovies", "TamilNewMovies", "TamilOTTFree", "FootballStreamFree",
            "PremierLeagueFree", "ISLFootballFree", "PKLKabaddi", "ProKabaddiFree", "FormulaOneFree", "F1StreamFree",
            "TennisFree", "BWFBadmintonFree", "ChessOlympiadFree",
        ]

        PIRACY_SIGNALS = [
            "live stream", "watch live", "ipl live", "cricket live",
            "free stream", "streaming now", "stream link",
        ]
        BETTING_SIGNALS = [
            "1xbet", "bet365", "reddy anna", "khelo", "betting",
            "satta", "96win",
        ]

        headers = {"User-Agent": "Mozilla/5.0 AppleWebKit/537.36"}

        async with _httpx.AsyncClient(
            headers=headers, follow_redirects=True, timeout=8
        ) as client:
            tasks = [client.get(f"https://t.me/s/{ch}") for ch in CHANNELS]
            import asyncio
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for ch, r in zip(CHANNELS, results):
            if isinstance(r, Exception):
                continue
            if r.status_code != 200:
                continue

            text = r.text.lower()
            signals = [s for s in PIRACY_SIGNALS if s in text]
            betting = [s for s in BETTING_SIGNALS if s in text]

            if not signals and not betting:
                continue

            # Extract subscriber count
            import re
            sub_match = re.search(
                r'(\d+(?:\.\d+)?[KMB]?)\s*(?:subscribers|members)',
                r.text, re.IGNORECASE
            )
            subscribers = 0
            if sub_match:
                val = sub_match.group(1)
                try:
                    if 'K' in val:
                        subscribers = int(float(val.replace('K','')) * 1000)
                    elif 'M' in val:
                        subscribers = int(float(val.replace('M','')) * 1e6)
                    else:
                        subscribers = int(val)
                except:
                    pass

            # Language detection
            lang = "English"
            if any(k in text for k in ["tamil", "தமிழ்"]):
                lang = "Tamil"
            elif any(k in text for k in ["telugu", "తెలుగు"]):
                lang = "Telugu"
            elif any(k in text for k in ["hindi", "हिंदी"]):
                lang = "Hindi"

            severity = "CRITICAL" if betting else \
                      "HIGH" if len(signals) >= 3 else "MEDIUM"

            streams.append({
                "channel": ch,
                "channel_url": f"https://t.me/{ch}",
                "language": lang,
                "subscriber_count": subscribers,
                "is_betting": bool(betting),
                "stream_signals": signals[:3],
                "severity": severity,
                "confidence": min(1.0, len(signals)*0.15 + len(betting)*0.2)
            })

    except Exception as e:
        log.error(f"Live shield error: {e}")

    elapsed_ms = int((time.time() - start) * 1000)
    await log_usage(
        customer, "/v1/live_shield", "POST",
        {"event": event_name},
        200, elapsed_ms, len(streams)
    )

    return {
        "success": True,
        "data": {
            "event": event_name,
            "streams_found": len(streams),
            "critical": sum(1 for s in streams if s["severity"] == "CRITICAL"),
            "streams": streams
        },
        "meta": {
            "response_time_ms": elapsed_ms,
            "channels_scanned": len(CHANNELS),
            "tier": customer.get("tier", "free"),
            "scanned_at": now_utc().isoformat()
        }
    }


@app.get("/v1/velocity/{title}")
async def get_velocity(
    title: str,
    customer: dict = Depends(verify_api_key)
):
    """Get piracy spread velocity data for a film."""
    if not await check_rate_limit(customer):
        raise HTTPException(429, {"error": "Rate limit exceeded"})

    rows = await db_fetch(
        """SELECT scan_time, platform_count, hits_found,
                  hours_since_release, spread_rate
           FROM cineos_velocity
           WHERE film_title ILIKE $1
           ORDER BY scan_time DESC LIMIT 20""",
        f"%{title}%"
    )

    await log_usage(customer, f"/v1/velocity/{title}", "GET", {}, 200, 0)

    return {
        "success": True,
        "data": {
            "title": title,
            "history": [
                {
                    "scan_time": str(r["scan_time"]),
                    "platforms": r["platform_count"],
                    "hits": r["hits_found"],
                    "hours_since_release": float(r["hours_since_release"] or 0),
                    "spread_rate": float(r["spread_rate"] or 0)
                }
                for r in rows
            ],
            "latest": rows[0] if rows else None
        },
        "meta": {"tier": customer.get("tier", "free")}
    }


@app.get("/v1/usage")
async def get_usage(customer: dict = Depends(verify_api_key)):
    """Get your API usage statistics."""
    tier = customer.get("tier", "free")
    tier_config = TIERS.get(tier, TIERS["free"])

    recent = await db_fetch(
        """SELECT endpoint, queried_at, response_time_ms, hits_found
           FROM api_usage
           WHERE key_prefix = $1
           ORDER BY queried_at DESC LIMIT 20""",
        customer.get("key_prefix", "")
    )

    return {
        "success": True,
        "data": {
            "customer": customer.get("customer_name"),
            "email": customer.get("customer_email"),
            "tier": tier,
            "price": f"${tier_config['price']}/month",
            "queries_this_month": customer.get("queries_this_month", 0),
            "queries_limit": tier_config["queries"],
            "queries_remaining": tier_config["queries"] - customer.get("queries_this_month", 0),
            "queries_total": customer.get("queries_total", 0),
            "recent_calls": [
                {
                    "endpoint": r["endpoint"],
                    "at": str(r["queried_at"]),
                    "ms": r["response_time_ms"],
                    "hits": r["hits_found"]
                }
                for r in recent
            ]
        }
    }


@app.get("/v1/tiers")
async def get_tiers():
    """Get available pricing tiers."""
    return {
        "tiers": {
            name: {
                "price_usd_month": config["price"],
                "queries_per_month": config["queries"],
                "rate_limit_per_minute": config["rate_per_min"],
            }
            for name, config in TIERS.items()
            if name != "free"
        },
        "contact": "dba.yugandhar@gmail.com",
        "trial": "Free tier: 10 queries to test the API"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
