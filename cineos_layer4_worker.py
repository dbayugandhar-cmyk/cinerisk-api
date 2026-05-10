#!/usr/bin/env python3
"""
cineos_layer4_worker.py — CINEOS Layer 4 Background Scanner
============================================================
Three scan modes running continuously as a single process:

  MODE 1 — Immediate (triggered by L2 alert)
    Fires within seconds of L2 detection.
    Scans all sources right now while suspect may still be in theater.
    Called via API endpoint POST /scan/trigger

  MODE 2 — Opening weekend (timer-based, no L2 needed)
    Runs every 10 minutes from release day through Sunday night.
    Catches uploads that happen between showings or overnight.
    Driven by CTI threat index — only CRITICAL/HIGH films.

  MODE 3 — Ongoing global monitor (forever)
    Runs every 6 hours for any film that ever had an L2 incident.
    Catches delayed uploads, international sites, Telegram reposts.
    Runs until film leaves theaters (90 days).

Deploy as a separate Railway service alongside your API.

Usage:
  python3 cineos_layer4_worker.py              # run all 3 modes
  python3 cineos_layer4_worker.py --test       # test all sources once
  python3 cineos_layer4_worker.py --film "Mortal Kombat II"  # manual scan now

Environment variables:
  DATABASE_URL        Railway PostgreSQL
  SERP_API_KEY        SerpApi key (serpapi.com — $50/mo, 100 searches/day free tier)
  SENDGRID_API_KEY    SendGrid key (free 100 emails/day)
  TELEGRAM_BOT_TOKEN  Telegram bot token (free)
  TELEGRAM_CHAT_ID    Your Telegram chat ID for alerts
  ALERT_EMAIL_TO      yugandhar@cineos.in
  CINEOS_API          https://cinerisk-api-production.up.railway.app
"""

import asyncio
import os
import json
import time
import httpx
import asyncpg
import logging
import argparse
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional
from cineos_email_alerts import send_piracy_alert, send_daily_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [L4] %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.l4")

# ── CONFIG ─────────────────────────────────────────────────────────
DATABASE_URL      = os.getenv("DATABASE_URL", "")
SERP_API_KEY      = os.getenv("SERP_API_KEY", "")
SENDGRID_API_KEY  = os.getenv("SENDGRID_API_KEY", "")
TELEGRAM_BOT_TOKEN= os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID", "")
ALERT_EMAIL_TO    = os.getenv("ALERT_EMAIL_TO", "yugandhar@cineos.in")
ALERT_EMAIL_FROM  = os.getenv("ALERT_EMAIL_FROM", "alerts@cineos.io")
CINEOS_API        = os.getenv("CINEOS_API", "https://cinerisk-api-production.up.railway.app")
TMDB_KEY          = os.getenv("TMDB_API_KEY", "28ff1ef4ae81f137ddd9cbeec2634033")

MODE2_INTERVAL_MIN  = int(os.getenv("MODE2_INTERVAL_MIN", "10"))   # every 10 min opening weekend
MODE3_INTERVAL_HRS  = int(os.getenv("MODE3_INTERVAL_HRS", "6"))    # every 6 hrs ongoing
OPENING_WEEKEND_DAYS= int(os.getenv("OPENING_WEEKEND_DAYS", "4"))  # Fri-Mon = 4 days
ONGOING_DAYS        = int(os.getenv("ONGOING_DAYS", "90"))          # monitor for 90 days

# Known torrent/piracy domain fragments
PIRACY_DOMAINS = [
    "1337x", "yts.", "rarbg", "torrentz", "piratebay", "thepiratebay",
    "kickass", "limetorrents", "zooqle", "torlock", "torrentgalaxy",
    "eztv", "nyaa", "rutracker", "kinozal", "nnmclub",
]
CAM_KEYWORDS = ["cam", "camrip", "hdcam", "telesync", "hdts", "ts rip",
                "camcorder", "cinema recording", "theater recording"]


# ── DATA STRUCTURES ────────────────────────────────────────────────

@dataclass
class ScanResult:
    film_title: str
    scan_time: str
    mode: str                      # immediate / opening_weekend / ongoing
    sources_checked: int = 0
    hits_found: int = 0
    platforms: list = field(default_factory=list)
    first_url: str = ""
    query: str = ""
    gap_minutes: int = 0
    incident_id: str = ""
    telegram_hits: int = 0
    reddit_hits: int = 0


@dataclass
class WatchlistFilm:
    film_title: str
    release_date: str
    cti_score: int
    is_opening_weekend: bool
    last_scanned: Optional[datetime] = None
    scan_count: int = 0
    leak_found: bool = False


# ── DB ─────────────────────────────────────────────────────────────

async def get_conn():
    if not DATABASE_URL:
        log.warning("No DATABASE_URL — DB writes disabled")
        return None
    try:
        return await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        log.error(f"DB connect failed: {e}")
        return None


async def ensure_tables():
    conn = await get_conn()
    if not conn: return
    try:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS l4_scan_results (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            film_title      TEXT NOT NULL,
            scan_time       TIMESTAMPTZ DEFAULT NOW(),
            scan_mode       TEXT,           -- immediate / opening_weekend / ongoing
            incident_id     UUID,
            sources_checked INTEGER DEFAULT 0,
            hits_found      INTEGER DEFAULT 0,
            platforms       TEXT[],
            first_hit_url   TEXT,
            gap_minutes     INTEGER,
            query           TEXT,
            telegram_hits   INTEGER DEFAULT 0,
            reddit_hits     INTEGER DEFAULT 0,
            alert_sent      BOOLEAN DEFAULT FALSE,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS l4_watchlist (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            film_title      TEXT UNIQUE NOT NULL,
            release_date    DATE,
            cti_score       INTEGER DEFAULT 0,
            added_at        TIMESTAMPTZ DEFAULT NOW(),
            last_scanned    TIMESTAMPTZ,
            scan_count      INTEGER DEFAULT 0,
            leak_found      BOOLEAN DEFAULT FALSE,
            leak_url        TEXT,
            active          BOOLEAN DEFAULT TRUE
        );

        CREATE INDEX IF NOT EXISTS idx_l4_film ON l4_scan_results (film_title, scan_time);
        CREATE INDEX IF NOT EXISTS idx_l4_hits ON l4_scan_results (hits_found) WHERE hits_found > 0;
        """)
        log.info("Tables ready")
    except Exception as e:
        log.error(f"Table creation: {e}")
    finally:
        await conn.close()


async def write_scan_result(result: ScanResult, alert_sent: bool = False):
    conn = await get_conn()
    if not conn: return
    try:
        await conn.execute("""
            INSERT INTO l4_scan_results
            (film_title, scan_mode, incident_id, sources_checked, hits_found,
             platforms, first_hit_url, gap_minutes, query, telegram_hits,
             reddit_hits, alert_sent)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        """,
            result.film_title, result.mode,
            result.incident_id or None,
            result.sources_checked, result.hits_found,
            result.platforms or [],
            result.first_hit_url or "",
            result.gap_minutes,
            result.query or "",
            result.telegram_hits,
            result.reddit_hits,
            alert_sent
        )
    except Exception as e:
        log.error(f"write_scan_result: {e}")
    finally:
        await conn.close()


async def update_watchlist(film: str, leak_found: bool = False, leak_url: str = ""):
    conn = await get_conn()
    if not conn: return
    try:
        await conn.execute("""
            UPDATE l4_watchlist
            SET last_scanned=NOW(), scan_count=scan_count+1,
                leak_found=CASE WHEN $2 THEN TRUE ELSE leak_found END,
                leak_url=CASE WHEN $2 THEN $3 ELSE leak_url END
            WHERE film_title=$1
        """, film, leak_found, leak_url)
    except Exception as e:
        log.error(f"update_watchlist: {e}")
    finally:
        await conn.close()


async def get_active_watchlist() -> list[WatchlistFilm]:
    conn = await get_conn()
    if not conn:
        return []
    try:
        rows = await conn.fetch("""
            SELECT film_title, release_date, cti_score,
                   last_scanned, scan_count, leak_found,
                   release_date >= NOW()::date - INTERVAL '4 days' AS is_opening_weekend
            FROM l4_watchlist
            WHERE active = TRUE AND NOT leak_found
        """)
        return [WatchlistFilm(
            film_title=r["film_title"],
            release_date=str(r["release_date"]),
            cti_score=r["cti_score"],
            is_opening_weekend=r["is_opening_weekend"],
            last_scanned=r["last_scanned"],
            scan_count=r["scan_count"],
            leak_found=r["leak_found"],
        ) for r in rows]
    except Exception as e:
        log.error(f"get_watchlist: {e}")
        return []
    finally:
        await conn.close()


async def add_to_watchlist(film_title: str, release_date: str, cti_score: int):
    conn = await get_conn()
    if not conn: return
    try:
        await conn.execute("""
            INSERT INTO l4_watchlist (film_title, release_date, cti_score)
            VALUES ($1, $2, $3)
            ON CONFLICT (film_title) DO UPDATE
            SET cti_score=$3, active=TRUE
        """, film_title, __import__("datetime").date.fromisoformat(release_date) if isinstance(release_date, str) else release_date, cti_score)
        log.info(f"Watchlist: added '{film_title}' CTI={cti_score}")
    except Exception as e:
        log.error(f"add_to_watchlist: {e}")
    finally:
        await conn.close()


# ── SCAN SOURCES ───────────────────────────────────────────────────

async def scan_serp(film_title: str, client: httpx.AsyncClient) -> dict:
    """Google search via SerpApi for CAM copies."""
    if not SERP_API_KEY:
        return {"hits": 0, "urls": [], "source": "serp_disabled"}
    query = f'"{film_title}" CAM torrent 1080p download'
    try:
        r = await client.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": SERP_API_KEY,
                    "num": 10, "engine": "google"},
            timeout=15
        )
        if r.status_code != 200:
            return {"hits": 0, "urls": [], "source": "serp_error"}
        results = r.json().get("organic_results", [])
        hits, urls = [], []
        for item in results:
            link = item.get("link", "").lower()
            title = item.get("title", "").lower()
            snippet = item.get("snippet", "").lower()
            is_piracy = any(d in link for d in PIRACY_DOMAINS)
            is_cam = any(k in title or k in snippet for k in CAM_KEYWORDS)
            if is_piracy or (is_cam and film_title.lower() in title):
                hits.append(item.get("link", ""))
                urls.append(item.get("link", ""))
        return {"hits": len(hits), "urls": urls, "source": "serpapi", "query": query}
    except Exception as e:
        log.warning(f"SerpApi error: {e}")
        return {"hits": 0, "urls": [], "source": "serp_error"}


async def scan_whereyouwatch(film_title: str, client: httpx.AsyncClient) -> dict:
    """Check whereyouwatch.com for CAM/piracy listings."""
    slug = (film_title.lower()
            .replace(" ", "-").replace(":", "")
            .replace("'", "").replace(".", ""))
    url = f"https://whereyouwatch.com/movies/{slug}/"
    try:
        r = await client.get(url, timeout=12, follow_redirects=True)
        if r.status_code == 200:
            body = r.text.lower()
            found = [k for k in CAM_KEYWORDS if k in body]
            if len(found) >= 2:
                return {"hits": 1, "urls": [url], "source": "whereyouwatch", "keywords": found}
        return {"hits": 0, "urls": [], "source": "whereyouwatch"}
    except Exception as e:
        return {"hits": 0, "urls": [], "source": "whereyouwatch_error"}


async def scan_reddit(film_title: str, client: httpx.AsyncClient) -> dict:
    """Search Reddit for CAM copy posts — reuse layer1 logic."""
    words = [w for w in film_title.split() if len(w) > 2]
    if len(words) < 2:
        return {"hits": 0, "urls": [], "source": "reddit_skip"}
    try:
        r = await client.get(
            "https://www.reddit.com/search.json",
            params={"q": film_title + " CAM", "sort": "new",
                    "limit": 25, "t": "week"},
            headers={"User-Agent": "CINEOS-L4/2.0"},
            timeout=12
        )
        if r.status_code != 200:
            return {"hits": 0, "urls": [], "source": "reddit_error"}
        posts = r.json().get("data", {}).get("children", [])
        hits, urls = 0, []
        for post in posts:
            pd = post.get("data", {})
            title = pd.get("title", "").lower()
            subreddit = pd.get("subreddit", "").lower()
            body = pd.get("selftext", "").lower()
            exact = film_title.lower() in title or film_title.lower() in body
            is_cam = any(k in title or k in body for k in CAM_KEYWORDS)
            is_piracy_sub = any(s in subreddit for s in ["piracy","moviepiracy","pirate"])
            if exact and (is_cam or is_piracy_sub):
                hits += 1
                urls.append(f"https://reddit.com{pd.get('permalink','')}")
        return {"hits": hits, "urls": urls, "source": "reddit"}
    except Exception as e:
        return {"hits": 0, "urls": [], "source": "reddit_error"}


async def scan_telegram_public(film_title: str, client: httpx.AsyncClient) -> dict:
    """
    Search public Telegram via t.me/s/ (no API key needed).
    Public channels only — private channels need Bot API.
    """
    query = film_title.replace(" ", "+") + "+CAM"
    url = f"https://t.me/s/moviespiracy?q={query}"
    hits, urls = 0, []
    channels_to_check = [
        f"https://t.me/s/camrips?q={film_title.replace(' ','+')}",
        f"https://t.me/s/movie_cam_prints?q={film_title.replace(' ','+')}",
    ]
    for ch_url in channels_to_check:
        try:
            r = await client.get(ch_url, timeout=10, follow_redirects=True)
            if r.status_code == 200:
                body = r.text.lower()
                if film_title.lower() in body and any(k in body for k in CAM_KEYWORDS):
                    hits += 1
                    urls.append(ch_url)
        except:
            pass

    if TELEGRAM_BOT_TOKEN:
        try:
            r = await client.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                timeout=10
            )
        except:
            pass

    return {"hits": hits, "urls": urls, "source": "telegram_public"}


async def scan_1337x_direct(film_title: str, client: httpx.AsyncClient) -> dict:
    """Direct scrape of 1337x search results."""
    query = film_title.replace(" ", "+") + "+CAM"
    url = f"https://1337x.to/search/{query}/1/"
    try:
        r = await client.get(url, timeout=12,
                             headers={"User-Agent": "Mozilla/5.0"},
                             follow_redirects=True)
        if r.status_code == 200:
            body = r.text.lower()
            film_lower = film_title.lower()
            if film_lower in body and any(k in body for k in ["cam", "camrip", "hdcam"]):
                return {"hits": 1, "urls": [url], "source": "1337x"}
        return {"hits": 0, "urls": [], "source": "1337x"}
    except Exception as e:
        return {"hits": 0, "urls": [], "source": "1337x_error"}


async def scan_yts(film_title: str, client: httpx.AsyncClient) -> dict:
    """Check YTS API for CAM uploads."""
    try:
        r = await client.get(
            "https://yts.mx/api/v2/list_movies.json",
            params={"query_term": film_title, "quality": "CAM"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            movies = data.get("movies", [])
            if movies:
                return {"hits": len(movies), "urls": [m.get("url","") for m in movies], "source": "yts"}
        return {"hits": 0, "urls": [], "source": "yts"}
    except:
        return {"hits": 0, "urls": [], "source": "yts_error"}


# ── FULL SCAN ──────────────────────────────────────────────────────

async def run_full_scan(
    film_title: str,
    mode: str,
    incident_id: str = "",
    detected_at: str = "",
) -> ScanResult:
    """Run all scan sources and return aggregated result."""
    result = ScanResult(
        film_title=film_title,
        scan_time=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        incident_id=incident_id,
    )

    # Gap since detection
    if detected_at:
        try:
            dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
            result.gap_minutes = int(
                (datetime.now(timezone.utc) - dt).total_seconds() / 60
            )
        except:
            pass

    log.info(f"[{mode}] Scanning '{film_title}' — gap={result.gap_minutes}min")

    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; CINEOS/2.0)"}
    ) as client:
        tasks = [
            scan_whereyouwatch(film_title, client),
            scan_reddit(film_title, client),
            scan_telegram_public(film_title, client),
            scan_1337x_direct(film_title, client),
            scan_yts(film_title, client),
        ]
        if SERP_API_KEY:
            tasks.append(scan_serp(film_title, client))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    result.sources_checked = len(tasks)
    for res in results:
        if isinstance(res, dict) and res.get("hits", 0) > 0:
            result.hits_found += res["hits"]
            result.platforms.append(res.get("source", "unknown"))
            if not result.first_url and res.get("urls"):
                result.first_url = res["urls"][0]
            if res.get("source") == "telegram_public":
                result.telegram_hits += res["hits"]
            if res.get("source") == "reddit":
                result.reddit_hits += res["hits"]

    log.info(
        f"[{mode}] '{film_title}' — "
        f"{result.sources_checked} sources · "
        f"{result.hits_found} hits · "
        f"platforms: {result.platforms or 'none'}"
    )
    return result


# ── ALERTS ────────────────────────────────────────────────────────

async def send_telegram_alert(result: ScanResult):
    """Send alert to your Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    msg = (
        f"🚨 CINEOS L4 — CAM LEAK FOUND\n\n"
        f"Film: {result.film_title}\n"
        f"Mode: {result.mode}\n"
        f"Platforms: {', '.join(result.platforms)}\n"
        f"Gap: {result.gap_minutes} minutes\n"
        f"First URL: {result.first_url or 'N/A'}\n"
        f"Reddit hits: {result.reddit_hits}\n"
        f"Telegram hits: {result.telegram_hits}\n"
        f"Time: {result.scan_time[:19]}\n"
        f"US Prov. Pat. 64/049,190"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
            )
        log.info(f"Telegram alert sent for '{result.film_title}'")
    except Exception as e:
        log.error(f"Telegram alert failed: {e}")


async def send_email_alert(result: ScanResult):
    """Send email alert via SendGrid — uses cineos_email_alerts module."""
    platform = result.platforms[0] if result.platforms else "Unknown"
    send_piracy_alert(
        film     = result.film_title,
        platform = platform,
        url      = result.first_url or "",
        verdict  = "CONFIRMED" if result.hits_found > 0 else "HIGH",
        quality  = "CAM",
    )


async def handle_leak_found(result: ScanResult):
    """Central handler when a leak is detected."""
    log.warning(
        f"LEAK FOUND — '{result.film_title}' on {result.platforms} "
        f"gap={result.gap_minutes}min mode={result.mode}"
    )
    # Write to DB
    await write_scan_result(result, alert_sent=True)
    # Update watchlist
    await update_watchlist(result.film_title, leak_found=True,
                           leak_url=result.first_url)
    # Alert both channels
    await asyncio.gather(
        send_telegram_alert(result),
        send_email_alert(result),
    )


# ── WATCHLIST SYNC FROM L1 ─────────────────────────────────────────

async def sync_watchlist_from_cti():
    """
    Pull latest CTI threat index and add CRITICAL/HIGH films to watchlist.
    Runs once at startup and every 6 hours.
    """
    cti_path = os.path.expanduser("~/Desktop/cinerisk/cineos_threat_index.json")
    if os.path.exists(cti_path):
        try:
            data = json.load(open(cti_path))
            for film in data.get("films", []):
                if film.get("cti_level") in ("CRITICAL", "HIGH"):
                    await add_to_watchlist(
                        film["title"],
                        film["release_date"],
                        film["cti_score"]
                    )
            log.info(f"Watchlist synced from CTI — "
                     f"{len([f for f in data['films'] if f.get('cti_level') in ('CRITICAL','HIGH')])} films")
            return
        except Exception as e:
            log.warning(f"CTI file read error: {e}")

    # Fallback: seed from known films currently tracked
    seeds = [
        ("Mortal Kombat II", "2026-05-08", 82),
        ("Star Wars: The Mandalorian and Grogu", "2026-05-22", 70),
        ("Obsession", "2026-05-15", 62),
    ]
    for title, date, score in seeds:
        await add_to_watchlist(title, date, score)
    log.info("Watchlist seeded with fallback films")


# ── MODE 1: IMMEDIATE ─────────────────────────────────────────────

async def mode1_immediate(
    film_title: str,
    incident_id: str,
    detected_at: str,
    zone: str,
    confidence: float
):
    """
    Called directly when L2 fires.
    Scans immediately — suspect may still be in theater.
    """
    log.info(f"MODE 1 IMMEDIATE — '{film_title}' zone={zone} conf={confidence:.2f}")
    result = await run_full_scan(
        film_title, mode="immediate",
        incident_id=incident_id, detected_at=detected_at
    )
    if result.hits_found > 0:
        await handle_leak_found(result)
    else:
        await write_scan_result(result, alert_sent=False)
        log.info(f"MODE 1 — No leak found yet for '{film_title}'")


# ── MODE 2: OPENING WEEKEND ───────────────────────────────────────

async def mode2_opening_weekend():
    """
    Runs every MODE2_INTERVAL_MIN minutes.
    Scans all CRITICAL/HIGH films that are in their opening window.
    """
    while True:
        try:
            films = await get_active_watchlist()
            opening = [f for f in films if f.is_opening_weekend]
            log.info(f"MODE 2 — {len(opening)} films in opening window")

            for film in opening:
                # Skip if scanned recently (within interval)
                if film.last_scanned:
                    age = (datetime.now(timezone.utc) - film.last_scanned).total_seconds() / 60
                    if age < MODE2_INTERVAL_MIN * 0.9:
                        continue

                result = await run_full_scan(film.film_title, mode="opening_weekend")
                if result.hits_found > 0:
                    await handle_leak_found(result)
                else:
                    await write_scan_result(result)
                    await update_watchlist(film.film_title)

                # Small gap between films
                await asyncio.sleep(3)

        except Exception as e:
            log.error(f"MODE 2 error: {e}")

        await asyncio.sleep(MODE2_INTERVAL_MIN * 60)


# ── MODE 3: ONGOING GLOBAL ────────────────────────────────────────

async def mode3_ongoing():
    """
    Runs every MODE3_INTERVAL_HRS hours.
    Scans all active films — opening weekend and beyond.
    This catches delayed uploads, international sites, Telegram reposts.
    """
    # Stagger start by 2 hours so mode2 and mode3 don't collide
    await asyncio.sleep(7200)

    while True:
        try:
            films = await get_active_watchlist()
            log.info(f"MODE 3 — {len(films)} films in watchlist")

            for film in films:
                # Skip films scanned very recently (mode2 will handle those)
                if film.is_opening_weekend:
                    continue  # mode2 handles opening weekend

                result = await run_full_scan(film.film_title, mode="ongoing")
                if result.hits_found > 0:
                    await handle_leak_found(result)
                else:
                    await write_scan_result(result)
                    await update_watchlist(film.film_title)

                await asyncio.sleep(5)

        except Exception as e:
            log.error(f"MODE 3 error: {e}")

        await asyncio.sleep(MODE3_INTERVAL_HRS * 3600)


# ── WATCHLIST SYNC LOOP ───────────────────────────────────────────

async def watchlist_sync_loop():
    """Sync watchlist from CTI every 6 hours."""
    while True:
        await sync_watchlist_from_cti()
        await asyncio.sleep(6 * 3600)


# ── API ENDPOINT (for L2 to trigger Mode 1) ───────────────────────

async def start_api_server():
    """
    Minimal HTTP server so detector_rtsp.py can POST to trigger Mode 1.
    POST /scan/trigger  {film_title, incident_id, detected_at, zone, confidence}
    GET  /scan/status   returns watchlist and recent scans
    """
    try:
        from aiohttp import web

        async def trigger(request):
            data = await request.json()
            asyncio.create_task(mode1_immediate(
                film_title  = data.get("film_title", ""),
                incident_id = data.get("incident_id", ""),
                detected_at = data.get("detected_at", ""),
                zone        = data.get("zone", ""),
                confidence  = float(data.get("confidence", 0)),
            ))
            return web.json_response({"status": "scan_started", "film": data.get("film_title")})

        async def status(request):
            films = await get_active_watchlist()
            return web.json_response({
                "watchlist": len(films),
                "opening_weekend": len([f for f in films if f.is_opening_weekend]),
                "films": [f.film_title for f in films]
            })

        app = web.Application()
        app.router.add_post("/scan/trigger", trigger)
        app.router.add_get("/scan/status", status)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8001)
        await site.start()
        log.info("API server running on :8001")
    except ImportError:
        log.warning("aiohttp not installed — API endpoint disabled. "
                    "pip install aiohttp to enable L2→L4 trigger.")


# ── TEST MODE ─────────────────────────────────────────────────────

async def run_test(film_title: str = "Mortal Kombat II"):
    """Test all scan sources once and print results."""
    print(f"\n{'='*60}")
    print(f"  CINEOS L4 — Source test for '{film_title}'")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(
        timeout=15, follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"}
    ) as client:
        tests = [
            ("whereyouwatch", scan_whereyouwatch(film_title, client)),
            ("reddit",        scan_reddit(film_title, client)),
            ("telegram",      scan_telegram_public(film_title, client)),
            ("1337x",         scan_1337x_direct(film_title, client)),
            ("yts",           scan_yts(film_title, client)),
        ]
        if SERP_API_KEY:
            tests.append(("whereyouwatch", scan_whereyouwatch(film_title, client)))

        results = await asyncio.gather(*[t[1] for t in tests], return_exceptions=True)

    for (name, _), res in zip(tests, results):
        if isinstance(res, Exception):
            print(f"  {name:20s} ERROR: {res}")
        else:
            status = "FOUND" if res.get("hits",0) > 0 else "clean"
            urls = res.get("urls", [])
            print(f"  {name:20s} {status:8s} hits={res.get('hits',0)} "
                  f"{'→ ' + urls[0][:60] if urls else ''}")

    print(f"\n  Config:")
    print(f"  SERP_API_KEY     : {'SET' if SERP_API_KEY else 'NOT SET (add for Google search)'}")
    print(f"  SENDGRID_API_KEY : {'SET' if SENDGRID_API_KEY else 'NOT SET (add for email alerts)'}")
    print(f"  TELEGRAM_BOT_TOKEN: {'SET' if TELEGRAM_BOT_TOKEN else 'NOT SET (add for Telegram alerts)'}")
    print(f"  DATABASE_URL     : {'SET' if DATABASE_URL else 'NOT SET (no DB writes)'}")
    print()


# ── MAIN ──────────────────────────────────────────────────────────

async def main():
    ap = argparse.ArgumentParser(description="CINEOS Layer 4 Background Worker")
    ap.add_argument("--test",   action="store_true", help="Test all sources once")
    ap.add_argument("--film",   type=str, default=None, help="Manual scan for a film")
    ap.add_argument("--mode",   type=int, default=0, help="Run specific mode only (1/2/3)")
    ap.add_argument("--no-api", action="store_true", help="Skip API server")
    args = ap.parse_args()

    if args.test:
        await run_test(args.film or "Mortal Kombat II")
        return

    if args.film:
        result = await run_full_scan(args.film, mode="manual")
        print(f"\nResult: {result.hits_found} hits on {result.platforms or 'no platforms'}")
        if result.first_url:
            print(f"First URL: {result.first_url}")
        return

    # Full production mode
    print(f"\n{'='*60}")
    print(f"  CINEOS Layer 4 — Background Worker v2")
    print(f"  Mode 2: every {MODE2_INTERVAL_MIN}min (opening weekend)")
    print(f"  Mode 3: every {MODE3_INTERVAL_HRS}hrs (ongoing global)")
    print(f"  Sources: whereyouwatch, 1337x, YTS, Reddit, Telegram")
    if SERP_API_KEY: print(f"  + SerpApi (Google search)")
    if TELEGRAM_BOT_TOKEN: print(f"  + Telegram Bot alerts")
    print(f"{'='*60}\n")

    await ensure_tables()
    await sync_watchlist_from_cti()

    tasks = [
        watchlist_sync_loop(),
        mode2_opening_weekend(),
        mode3_ongoing(),
    ]
    if not args.no_api:
        tasks.append(start_api_server())

    if args.mode == 2:
        await mode2_opening_weekend()
    elif args.mode == 3:
        await mode3_ongoing()
    else:
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
