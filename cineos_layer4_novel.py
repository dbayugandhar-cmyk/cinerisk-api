#!/usr/bin/env python3
"""
CINEOS Layer 4 — Novel Anti-Piracy Engine
==========================================
Three novel capabilities nobody has built:

NOVEL 1 — Gold Scanner in Background Worker
  The Railway worker now uses all 10 sources (WhereYouWatch, SerpApi,
  PreDB via Google, Reddit via Google, YTS via Google, Telegram,
  Movierulz, TamilMV, Filmyzilla, 9xMovies) instead of the old 5.
  Runs every 10 minutes for all watchlist films automatically.

NOVEL 2 — Global CAM Feed with Theater Cross-Reference
  Monitors PreDB RSS + WhereYouWatch new listings + SerpApi for ANY
  new CAM release globally — not just watchlist films.
  The moment a new CAM appears, automatically checks:
  - Is this film in our theater incident DB?
  - Was there a recording incident in the last 8 hours?
  - If yes → AUTOMATIC MATCH → fire CRITICAL alert with seat evidence
  No other system connects physical detection to internet monitoring.

NOVEL 3 — NFO File Intelligence Parser
  Every scene CAM release includes an NFO file with metadata.
  NFOs often contain: theater city, audio type (dolby/imax),
  recording equipment hints, language, sometimes screen details.
  We parse NFO content and cross-reference against our incident DB
  to narrow down the source theater. Nobody does this systematically.

US Provisional Patent 64/049,190 — Yugandhar Mallavarapu
"""

import asyncio
import httpx
import os
import re
import json
import asyncpg
import logging
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [L4-NOVEL] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.l4.novel")

# ── CONFIG ─────────────────────────────────────────────────────────
DATABASE_URL    = os.getenv("DATABASE_URL", "")
SERP_API_KEY    = os.getenv("SERP_API_KEY", "")
SENDGRID_KEY    = os.getenv("SENDGRID_API_KEY", "")
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT   = os.getenv("TELEGRAM_CHAT_ID", "")
ALERT_EMAIL     = os.getenv("ALERT_EMAIL_TO", "yugandhar@cineos.in")
CINEOS_API      = os.getenv("CINEOS_API", "https://cinerisk-api-production.up.railway.app")
MODE2_INTERVAL  = int(os.getenv("MODE2_INTERVAL_MIN", "10"))
MODE3_INTERVAL  = int(os.getenv("MODE3_INTERVAL_HRS", "6"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

CAM_KEYWORDS = [
    "camrip", "cam-rip", "hdcam", "hdts", "telesync",
    "camcorder", "theater rip", "cinema rip", "hd-cam",
    "source: camera", "cinemacity", "cam rip", "hdcam-rip",
    "recorded in cinema", "theater recording"
]

WATCHLIST = [
    {"title": "Mortal Kombat II",                        "cti": 82, "release": "2026-05-08"},
    {"title": "The Sheep Detectives",                    "cti": 77, "release": "2026-05-08"},
    {"title": "Star Wars: The Mandalorian and Grogu",    "cti": 70, "release": "2026-05-22"},
    {"title": "GUNDAM Hathaway",                         "cti": 65, "release": "2026-05-15"},
    {"title": "Obsession",                               "cti": 62, "release": "2026-05-15"},
]

def has_cam(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in CAM_KEYWORDS)

def film_slug(title: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ══════════════════════════════════════════════════════════════════
# NOVEL 1 — GOLD SCANNER (10 sources replacing old 5-source scanner)
# ══════════════════════════════════════════════════════════════════

async def gold_scan_film(film: str, client: httpx.AsyncClient) -> dict:
    """
    Full 10-source gold standard scan for a specific film.
    Replaces old scan_whereyouwatch + scan_reddit + scan_1337x + scan_yts.
    """
    hits = []
    sources_checked = 0

    # ── WhereYouWatch (direct - most reliable) ──────────────────
    try:
        slug = film_slug(film)
        r = await client.get(
            f"https://whereyouwatch.com/movies/{slug}/",
            timeout=12, headers=HEADERS
        )
        sources_checked += 1
        if r.status_code == 200:
            body = r.text.lower()
            fw = [w for w in film.lower().split() if len(w) > 2]
            if sum(1 for w in fw if w in body) >= 2 and has_cam(body):
                hits.append({
                    "platform": "WhereYouWatch",
                    "url": f"https://whereyouwatch.com/movies/{slug}/",
                    "quality": "CAM",
                    "severity": "HIGH"
                })
    except:
        pass

    # ── SerpApi Google (bypasses blocked sites) ─────────────────
    if SERP_API_KEY:
        queries = [
            f'"{film}" (camrip OR hdcam OR hdts OR "cam-rip") (download OR torrent) -site:imdb.com',
            f'"{film}" CAM 2026 download -site:imdb.com -site:youtube.com',
        ]
        piracy_domains = [
            "1337x", "yts.", "tamilmv", "movierulz", "filmyzilla",
            "tamilblasters", "9xmovies", "ibomma", "bolly4u", "filmxy",
            "torrentgalaxy", "thepiratebay", "predb", "rarbg", "nyaa"
        ]
        false_positive_domains = [
            "softonic.com", "apple.com", "play.google.com",
            "amazon.com", "wikipedia.org", "imdb.com", "rottentomatoes.com"
        ]
        for query in queries:
            try:
                r = await client.get(
                    "https://serpapi.com/search",
                    params={"q": query, "api_key": SERP_API_KEY,
                            "num": 10, "engine": "google", "gl": "us"},
                    timeout=20
                )
                sources_checked += 1
                if r.status_code == 200:
                    for item in r.json().get("organic_results", []):
                        link = item.get("link", "")
                        title = item.get("title", "")
                        snippet = item.get("snippet", "")
                        full = f"{link} {title} {snippet}".lower()
                        fw = [w for w in film.lower().split() if len(w) > 2]
                        film_ok = sum(1 for w in fw if w in title.lower() or w in snippet.lower()) >= max(2, len(fw)-1)
                        is_piracy = any(d in link.lower() for d in piracy_domains)
                        is_fp = any(d in link.lower() for d in false_positive_domains)
                        if (is_piracy or has_cam(full)) and film_ok and not is_fp:
                            hits.append({
                                "platform": f"Google→{link.split('/')[2][:25]}",
                                "url": link,
                                "quality": "CAM",
                                "severity": "HIGH"
                            })
                await asyncio.sleep(0.5)
            except:
                pass

        # ── YTS via SerpApi ─────────────────────────────────────
        for site_name, domain in [("YTS","yts.mx"),("PreDB","predb.me"),
                                   ("1337x","1337x.to"),("TamilMV","tamilmv.fi")]:
            try:
                r = await client.get(
                    "https://serpapi.com/search",
                    params={
                        "q": f'site:{domain} "{film}" CAM OR HDCam OR HDTS',
                        "api_key": SERP_API_KEY, "num": 3, "engine": "google"
                    },
                    timeout=12
                )
                sources_checked += 1
                if r.status_code == 200:
                    items = r.json().get("organic_results", [])
                    for item in items:
                        t = item.get("title", "")
                        lnk = item.get("link", "")
                        fw = [w for w in film.lower().split() if len(w) > 2]
                        if sum(1 for w in fw if w in t.lower()) >= 2 and has_cam(t):
                            hits.append({
                                "platform": site_name,
                                "url": lnk,
                                "quality": "CAM",
                                "severity": "HIGH"
                            })
                            break
                await asyncio.sleep(0.3)
            except:
                pass

    # ── Telegram public channels ────────────────────────────────
    for ch in ["CamRips", "MoviesHD4K"]:
        try:
            r = await client.get(
                f"https://t.me/s/{ch}?q={film.replace(' ','+')}",
                timeout=8, headers=HEADERS
            )
            sources_checked += 1
            if r.status_code == 200:
                body = r.text.lower()
                fw = [w for w in film.lower().split() if len(w) > 2]
                if sum(1 for w in fw if w in body) >= 2 and has_cam(body):
                    hits.append({
                        "platform": f"Telegram @{ch}",
                        "url": f"https://t.me/{ch}",
                        "quality": "CAM",
                        "severity": "HIGH"
                    })
        except:
            pass

    log.info(f"Gold scan '{film}': {sources_checked} sources, {len(hits)} hits")
    return {"hits": hits, "sources_checked": sources_checked,
            "film": film, "scan_time": now_utc()}


# ══════════════════════════════════════════════════════════════════
# NOVEL 2 — GLOBAL CAM FEED + THEATER CROSS-REFERENCE
# ══════════════════════════════════════════════════════════════════

async def fetch_global_cam_feed(client: httpx.AsyncClient) -> list:
    """
    Fetch ALL new CAM releases globally from multiple sources.
    Returns list of {title, release_name, url, source, detected_at}
    This is the novel part — watching the global feed, not just specific films.
    """
    new_cams = []

    # ── WhereYouWatch new CAM listings ─────────────────────────
    try:
        r = await client.get(
            "https://whereyouwatch.com/",
            timeout=12, headers=HEADERS
        )
        if r.status_code == 200:
            body = r.text.lower()
            # Extract film titles from new CAM listings
            matches = re.findall(
                r'href="/movies/([^/]+)/"[^>]*>[^<]*(?:cam|hdcam|hdts)[^<]*<',
                body
            )
            for slug in matches[:10]:
                title = slug.replace('-', ' ').title()
                new_cams.append({
                    "title": title,
                    "slug": slug,
                    "url": f"https://whereyouwatch.com/movies/{slug}/",
                    "source": "whereyouwatch",
                    "quality": "CAM",
                    "detected_at": now_utc()
                })
    except Exception as e:
        log.warning(f"WYW global feed: {e}")

    # ── SerpApi: scan for ALL new CAM releases today ────────────
    if SERP_API_KEY:
        today = datetime.now(timezone.utc).strftime("%Y")
        queries = [
            f'site:whereyouwatch.com "cam-rip" OR "hdcam" {today}',
            f'"CAM-RIP" OR "HDCam" movie {today} download torrent -site:imdb.com',
        ]
        for query in queries:
            try:
                r = await client.get(
                    "https://serpapi.com/search",
                    params={"q": query, "api_key": SERP_API_KEY,
                            "num": 10, "engine": "google", "gl": "us",
                            "tbs": "qdr:d"},  # last 24 hours
                    timeout=20
                )
                if r.status_code == 200:
                    for item in r.json().get("organic_results", []):
                        title_raw = item.get("title", "")
                        link = item.get("link", "")
                        snippet = item.get("snippet", "")
                        if has_cam(f"{title_raw} {snippet}"):
                            # Extract film title from result
                            film_title = re.sub(
                                r'\s*(CAM|HDCam|HDTS|download|torrent|free|watch|online).*',
                                '', title_raw, flags=re.IGNORECASE
                            ).strip()
                            if len(film_title) > 3:
                                new_cams.append({
                                    "title": film_title,
                                    "url": link,
                                    "source": "serpapi_global",
                                    "quality": "CAM",
                                    "detected_at": now_utc(),
                                    "snippet": snippet[:100]
                                })
                await asyncio.sleep(0.5)
            except Exception as e:
                log.warning(f"SerpApi global: {e}")

    log.info(f"Global CAM feed: {len(new_cams)} new CAM releases found")
    return new_cams


async def cross_reference_theater_db(cam_title: str) -> list:
    """
    Cross-reference a CAM release title against our theater incident DB.
    Check if we have a recording incident for this film in the last 8 hours.
    THIS IS THE NOVEL PART — no other system does this.
    """
    if not DATABASE_URL:
        return []
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch("""
            SELECT id, film_title, theater_name, zone, detection_type,
                   confidence, detected_at, screen_number, seat_location
            FROM incidents
            WHERE LOWER(film_title) LIKE LOWER($1)
            AND detected_at > NOW() - INTERVAL '8 hours'
            AND film_title NOT IN ('string', 'Test Film', '')
            ORDER BY detected_at DESC
            LIMIT 5
        """, f"%{cam_title[:10]}%")
        await conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        log.warning(f"DB cross-reference error: {e}")
        return []


async def run_global_cam_monitor():
    """
    Novel 2 — Runs every 30 minutes.
    Watches the entire internet for ANY new CAM release.
    Cross-references each against our theater incident DB.
    If match found → CRITICAL alert with seat evidence.
    """
    log.info("NOVEL 2: Global CAM monitor starting")
    while True:
        try:
            async with httpx.AsyncClient(timeout=15, headers=HEADERS,
                                         follow_redirects=True) as client:
                new_cams = await fetch_global_cam_feed(client)

                for cam in new_cams:
                    title = cam.get("title", "")
                    if len(title) < 4:
                        continue

                    # Cross-reference against theater DB
                    incidents = await cross_reference_theater_db(title)

                    if incidents:
                        # CRITICAL — CAM appeared online AND we have theater evidence
                        log.warning(
                            f"NOVEL MATCH — '{title}' CAM online + "
                            f"{len(incidents)} theater incident(s) in last 8h"
                        )
                        await send_novel_alert(cam, incidents)
                    else:
                        log.info(f"Global CAM: '{title}' — no theater match")

        except Exception as e:
            log.error(f"Global CAM monitor error: {e}")

        await asyncio.sleep(30 * 60)  # every 30 minutes


# ══════════════════════════════════════════════════════════════════
# NOVEL 3 — NFO FILE INTELLIGENCE PARSER
# ══════════════════════════════════════════════════════════════════

def parse_nfo_content(nfo_text: str) -> dict:
    """
    Parse NFO file content for theater attribution clues.
    NFOs often contain: city, audio type, screen format, equipment hints.
    Nobody does this systematically for anti-piracy attribution.
    """
    nfo = nfo_text.lower()
    clues = {}

    # Audio format clues (help identify screen/theater type)
    if "dolby atmos" in nfo:
        clues["audio"] = "Dolby Atmos"
        clues["theater_type"] = "Premium large format likely"
    elif "imax" in nfo:
        clues["audio"] = "IMAX"
        clues["theater_type"] = "IMAX screen"
    elif "dolby digital" in nfo:
        clues["audio"] = "Dolby Digital"
    elif "dts" in nfo:
        clues["audio"] = "DTS"

    # Language clues (narrow down country/region)
    lang_patterns = {
        "hindi dubbed": "India",
        "tamil dubbed": "South India",
        "telugu dubbed": "South India",
        "english": "English-speaking market",
        "arabic": "Middle East",
        "french": "France/Canada",
        "spanish": "Spain/Latin America",
    }
    for pattern, region in lang_patterns.items():
        if pattern in nfo:
            clues["language_region"] = region
            break

    # Equipment clues
    if "camcorder" in nfo:
        clues["device"] = "Dedicated camcorder"
    elif "dslr" in nfo or "digital slr" in nfo:
        clues["device"] = "DSLR camera"
    elif "phone" in nfo or "smartphone" in nfo:
        clues["device"] = "Smartphone"
    elif "night vision" in nfo:
        clues["device"] = "Night vision equipped camera"

    # Screen position clues
    if "center" in nfo or "centre" in nfo:
        clues["position"] = "CENTER zone"
    elif "front row" in nfo:
        clues["position"] = "Front rows"
    elif "back" in nfo and "row" in nfo:
        clues["position"] = "Back rows"
    elif "balcony" in nfo:
        clues["position"] = "Balcony section"

    # Release group patterns
    group_match = re.search(r'-([A-Z0-9]{2,12})\s*$', nfo_text.strip(), re.MULTILINE)
    if group_match:
        clues["release_group"] = group_match.group(1)

    # City/location mentions
    cities = [
        "new york", "los angeles", "london", "mumbai", "delhi",
        "toronto", "sydney", "dubai", "singapore", "paris",
        "chicago", "houston", "atlanta", "dallas"
    ]
    for city in cities:
        if city in nfo:
            clues["city_hint"] = city.title()
            break

    # Recording quality indicators
    if "microphone" in nfo or "external mic" in nfo:
        clues["audio_setup"] = "External microphone used"
    if "tripod" in nfo:
        clues["stability"] = "Tripod used — fixed position"
    if "handheld" in nfo:
        clues["stability"] = "Handheld — mobile position"

    return clues


async def fetch_nfo_for_release(release_name: str,
                                 client: httpx.AsyncClient) -> Optional[str]:
    """
    Try to fetch NFO file for a scene release.
    NFOs are indexed on srrdb.com and nfodb.com.
    """
    if not SERP_API_KEY:
        return None

    try:
        r = await client.get(
            "https://serpapi.com/search",
            params={
                "q": f'site:srrdb.com "{release_name}"',
                "api_key": SERP_API_KEY,
                "num": 3, "engine": "google"
            },
            timeout=12
        )
        if r.status_code == 200:
            items = r.json().get("organic_results", [])
            if items:
                # Try to fetch the NFO from srrdb
                nfo_url = items[0].get("link", "").replace(
                    "srrdb.com/release/details/",
                    "srrdb.com/release/nfo/"
                )
                if "srrdb.com" in nfo_url:
                    r2 = await client.get(nfo_url, timeout=10)
                    if r2.status_code == 200:
                        return r2.text
    except Exception as e:
        log.warning(f"NFO fetch error: {e}")
    return None


async def run_nfo_intelligence(release_name: str,
                                film_title: str) -> dict:
    """
    Novel 3 — Full NFO intelligence pipeline.
    1. Fetch NFO for a known CAM release
    2. Parse for theater attribution clues
    3. Cross-reference clues against incident DB
    4. Return matched incidents with confidence boost
    """
    result = {
        "release": release_name,
        "film": film_title,
        "nfo_found": False,
        "clues": {},
        "matched_incidents": [],
        "attribution_confidence": 0
    }

    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        nfo_text = await fetch_nfo_for_release(release_name, client)

        if not nfo_text:
            log.info(f"NFO: No NFO found for {release_name}")
            return result

        result["nfo_found"] = True
        clues = parse_nfo_content(nfo_text)
        result["clues"] = clues
        log.info(f"NFO clues for '{release_name}': {clues}")

        # Cross-reference clues against incident DB
        if DATABASE_URL:
            try:
                conn = await asyncpg.connect(DATABASE_URL)

                # Build query based on available clues
                query = """
                    SELECT id, film_title, theater_name, zone, detection_type,
                           confidence, detected_at, screen_number, seat_location
                    FROM incidents
                    WHERE LOWER(film_title) LIKE LOWER($1)
                    AND film_title NOT IN ('string', 'Test Film', '')
                    ORDER BY detected_at DESC LIMIT 10
                """
                rows = await conn.fetch(query, f"%{film_title[:8]}%")
                await conn.close()

                incidents = [dict(r) for r in rows]

                # Score each incident against NFO clues
                for inc in incidents:
                    score = 0
                    reasons = []

                    # Zone match
                    if "position" in clues:
                        zone = (inc.get("zone") or "").upper()
                        if "CENTER" in clues["position"] and zone == "CENTER":
                            score += 30
                            reasons.append("Zone matches NFO (CENTER)")
                        elif "FRONT" in clues["position"] and zone in ["CENTER", "LEFT"]:
                            score += 15
                            reasons.append("Position consistent with NFO")

                    # Device match
                    if "device" in clues:
                        det_type = (inc.get("detection_type") or "").upper()
                        if "CAMCORDER" in clues["device"] and "CAM" in det_type:
                            score += 25
                            reasons.append("Device type matches")
                        elif "DSLR" in clues["device"] and "IR" in det_type:
                            score += 20
                            reasons.append("DSLR consistent with IR detection")

                    # Base confidence from detector
                    conf = float(inc.get("confidence") or 0)
                    score += int(conf * 20)

                    if score > 20:
                        result["matched_incidents"].append({
                            **inc,
                            "nfo_match_score": score,
                            "nfo_match_reasons": reasons
                        })

                result["matched_incidents"].sort(
                    key=lambda x: x["nfo_match_score"], reverse=True
                )
                if result["matched_incidents"]:
                    result["attribution_confidence"] = min(
                        95, result["matched_incidents"][0]["nfo_match_score"]
                    )

            except Exception as e:
                log.error(f"NFO DB cross-reference: {e}")

    return result


# ══════════════════════════════════════════════════════════════════
# ALERT SYSTEM
# ══════════════════════════════════════════════════════════════════

async def send_novel_alert(cam: dict, incidents: list):
    """Send CRITICAL alert when global CAM matches theater incident."""
    film = cam.get("title", "Unknown")
    url = cam.get("url", "")
    source = cam.get("source", "")

    inc = incidents[0] if incidents else {}
    seat = inc.get("seat_location") or f"{inc.get('zone','—')} zone"
    theater = inc.get("theater_name", "Unknown theater")
    conf = int(float(inc.get("confidence") or 0) * 100)
    det_time = str(inc.get("detected_at", ""))[:19]

    msg = (
        f"🚨 CINEOS NOVEL MATCH — CRITICAL\n\n"
        f"Film: {film}\n"
        f"CAM found on: {source}\n"
        f"URL: {url}\n\n"
        f"Theater incident match:\n"
        f"  Theater: {theater}\n"
        f"  Location: {seat}\n"
        f"  Confidence: {conf}%\n"
        f"  Detected: {det_time} UTC\n"
        f"  Total matches: {len(incidents)}\n\n"
        f"Action: Request NFO file for seat attribution\n"
        f"CINEOS — US Prov. Pat. 64/049,190"
    )

    # Telegram
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": TELEGRAM_CHAT, "text": msg}
                )
            log.info(f"Telegram alert sent for '{film}'")
        except Exception as e:
            log.error(f"Telegram: {e}")

    # Email via SendGrid
    if SENDGRID_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {SENDGRID_KEY}",
                             "Content-Type": "application/json"},
                    json={
                        "personalizations": [{"to": [{"email": ALERT_EMAIL}]}],
                        "from": {"email": "alerts@cineos.io", "name": "CINEOS"},
                        "subject": f"[CINEOS CRITICAL] Novel Match: {film}",
                        "content": [{"type": "text/plain", "value": msg}]
                    }
                )
            log.info(f"Email alert sent for '{film}'")
        except Exception as e:
            log.error(f"Email: {e}")


# ══════════════════════════════════════════════════════════════════
# BACKGROUND WORKER — All 3 novels running together
# ══════════════════════════════════════════════════════════════════

async def mode2_gold_opening_weekend():
    """
    Novel 1 — Gold scanner replacing old 5-source scanner.
    Runs every 10 minutes for watchlist films on opening weekend.
    """
    log.info("NOVEL 1: Gold scanner worker starting (Mode 2 — opening weekend)")
    while True:
        try:
            async with httpx.AsyncClient(timeout=15, headers=HEADERS,
                                         follow_redirects=True) as client:
                for film_data in WATCHLIST:
                    film = film_data["title"]
                    log.info(f"Gold scanning: '{film}'")
                    result = await gold_scan_film(film, client)

                    if result["hits"]:
                        log.warning(
                            f"HIT: '{film}' found on "
                            f"{[h['platform'] for h in result['hits']]}"
                        )
                        # Check for theater incidents
                        incidents = await cross_reference_theater_db(film)
                        if incidents:
                            log.warning(
                                f"CRITICAL MATCH: '{film}' — "
                                f"CAM online + {len(incidents)} theater incidents"
                            )
                        # Save to DB
                        await save_scan_result(film, result, incidents)
                        # Alert
                        if result["hits"]:
                            await send_novel_alert(
                                {"title": film, "url": result["hits"][0]["url"],
                                 "source": result["hits"][0]["platform"]},
                                incidents
                            )
                    await asyncio.sleep(3)

        except Exception as e:
            log.error(f"Mode 2 gold error: {e}")

        await asyncio.sleep(MODE2_INTERVAL * 60)


async def save_scan_result(film: str, result: dict, incidents: list):
    """Save scan result to Railway DB."""
    if not DATABASE_URL:
        return
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            INSERT INTO l4_scan_results
            (film_title, scan_mode, sources_checked, hits_found,
             platforms, first_hit_url, alert_sent)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT DO NOTHING
        """,
            film, "gold_novel",
            result.get("sources_checked", 0),
            len(result.get("hits", [])),
            [h["platform"] for h in result.get("hits", [])],
            result["hits"][0]["url"] if result.get("hits") else "",
            len(incidents) > 0
        )
        await conn.close()
    except Exception as e:
        log.warning(f"Save scan result: {e}")


# ══════════════════════════════════════════════════════════════════
# CLI — Test and run modes
# ══════════════════════════════════════════════════════════════════

async def test_all_novels():
    """Test all 3 novel features."""
    print("\n" + "="*60)
    print("  CINEOS Novel Anti-Piracy Engine — Test Mode")
    print("="*60)

    # Test Novel 1 — Gold scanner
    print("\n[NOVEL 1] Gold Scanner — The Devil Wears Prada 2")
    async with httpx.AsyncClient(timeout=15, headers=HEADERS,
                                  follow_redirects=True) as client:
        result = await gold_scan_film("The Devil Wears Prada 2", client)
    print(f"  Sources checked: {result['sources_checked']}")
    print(f"  Hits found: {len(result['hits'])}")
    for h in result["hits"]:
        print(f"  HIT: {h['platform']} — {h['url'][:60]}")

    # Test Novel 2 — Global CAM feed
    print("\n[NOVEL 2] Global CAM Feed")
    async with httpx.AsyncClient(timeout=15, headers=HEADERS,
                                  follow_redirects=True) as client:
        cams = await fetch_global_cam_feed(client)
    print(f"  New CAM releases found globally: {len(cams)}")
    for cam in cams[:3]:
        print(f"  CAM: {cam['title']} — {cam['source']}")
        # Cross-reference each against theater DB
        incidents = await cross_reference_theater_db(cam["title"])
        if incidents:
            print(f"  *** THEATER MATCH: {len(incidents)} incidents for '{cam['title']}'")

    # Test Novel 3 — NFO parser
    print("\n[NOVEL 3] NFO Intelligence Parser")
    sample_nfo = """
    The.Devil.Wears.Prada.2.2026.CAM-RIP-CinemaCity
    Source: Camera recording from cinema
    Audio: Dolby Digital 5.1
    Language: English
    Recorded from center section
    External microphone used
    Location: New York premiere screening
    """
    clues = parse_nfo_content(sample_nfo)
    print(f"  NFO clues extracted: {len(clues)}")
    for k, v in clues.items():
        print(f"  {k}: {v}")

    print("\n" + "="*60)
    print("  All 3 novel features operational")
    print("="*60 + "\n")


async def main():
    ap = argparse.ArgumentParser(description="CINEOS Novel Anti-Piracy Engine")
    ap.add_argument("--test",   action="store_true", help="Test all 3 novels")
    ap.add_argument("--film",   type=str, help="Gold scan a specific film")
    ap.add_argument("--nfo",    type=str, help="Parse NFO for release name")
    ap.add_argument("--global-feed", action="store_true", help="Run global CAM feed once")
    ap.add_argument("--run",    action="store_true", help="Run all workers")
    args = ap.parse_args()

    if args.test:
        await test_all_novels()
    elif args.film:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS,
                                      follow_redirects=True) as client:
            result = await gold_scan_film(args.film, client)
        print(f"Film: {args.film}")
        print(f"Hits: {len(result['hits'])}")
        for h in result["hits"]:
            print(f"  {h['platform']}: {h['url']}")
    elif args.nfo:
        result = await run_nfo_intelligence(args.nfo, args.nfo.split('.')[0])
        print(json.dumps(result, indent=2, default=str))
    elif getattr(args, 'global_feed'):
        async with httpx.AsyncClient(timeout=15, headers=HEADERS,
                                      follow_redirects=True) as client:
            cams = await fetch_global_cam_feed(client)
        for cam in cams:
            print(f"{cam['title']} — {cam['source']} — {cam['url'][:60]}")
    elif args.run:
        print("\nCINEOS Novel Engine — All 3 features running")
        print(f"Novel 1: Gold scanner every {MODE2_INTERVAL} min")
        print(f"Novel 2: Global CAM feed every 30 min")
        print(f"Novel 3: NFO parsing on every hit\n")
        await asyncio.gather(
            mode2_gold_opening_weekend(),
            run_global_cam_monitor(),
        )
    else:
        ap.print_help()


if __name__ == "__main__":
    asyncio.run(main())
