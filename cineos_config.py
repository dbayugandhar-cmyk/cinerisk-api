#!/usr/bin/env python3
"""
CINEOS Platform Configuration
==============================
Single source of truth for all API keys, constants, and shared utilities.
Production-grade — no hardcoded secrets anywhere.
US Provisional Patent 64/049,190
"""

import os
import re
import logging
import asyncio
import httpx
from datetime import datetime, timezone

# ── API Keys — all from environment variables ─────────────────────
SERP_API_KEY    = os.getenv("SERP_API_KEY", "")
CINEOS_API      = os.getenv("CINEOS_API", "https://cinerisk-api-production.up.railway.app")
DATABASE_URL    = os.getenv("DATABASE_URL", "")

# ── HTTP Configuration ────────────────────────────────────────────
DEFAULT_TIMEOUT  = 15
DEFAULT_HEADERS  = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# ── CAM/Piracy Keywords ───────────────────────────────────────────
CAM_KEYWORDS = [
    # CAM recording types
    "camrip", "cam-rip", "hdcam", "hdts", "telesync", "ts-rip",
    "source: camera", "line audio", "cam rip", "cam copy",
    "camera recording", "theater recording", "theatre recording",
    "cinema recording", "recorded in cinema", "recorded in theater",
    # Audio indicators
    "with line audio", "cam with line", "line-audio",
    "internal mic", "external mic", "audience audio",
    # Quality indicators used for CAM releases
    "hdrip", "hd rip", "dvdrip", "dvd rip", "dvdscr", "dvd-scr",
    "webrip", "web rip", "web-dl", "webdl", "bluray rip",
    # Pre-release indicators
    "predvd", "pre-dvd", "pre dvd", "prescreener",
    # Indian market specific
    "theater print", "theatre print", "hq cam", "hq-cam",
    "480p", "720p", "1080p", "4k",
    "tamil dubbed", "telugu dubbed", "hindi dubbed",
    "malayalam", "kannada",
    "watch online free", "download free", "full movie free",
]

# ── Piracy Domains ────────────────────────────────────────────────
PIRACY_DOMAINS = [
    # Western torrent sites
    "1337x", "torrentgalaxy", "yts.mx", "yts.am",
    "rarbg", "nyaa.si", "nyaa.net",
    "tpb", "thepiratebay", "piratebay",
    "torrentleech", "iptorrents",
    "limetorrents", "torlock",
    "torrentz2", "magnetdl",
    "scene-rls", "predb", "srrdb",
    "xrel.to", "nzbindex",
    # Indian piracy sites
    "movierulz", "tamilmv", "filmyzilla", "9xmovies",
    "tamilblasters", "ibomma", "isaimini", "kuttymovies",
    "tamilyogi", "moviesda", "cinevood", "hdhub4u",
    "vegamovies", "bolly4u", "filmyhit", "skymovies",
    "filmy4wap", "filmysplit", "moviescounter",
    # Streaming piracy
    "whereyouwatch", "fmovies", "gomovies", "123movies",
    "putlocker", "solarmovie", "watchseries",
    "streamlord", "vumoo", "popcorntime",
    # Archive sites used for piracy
    "archive.org/download",
    # Scene/NFO databases
    "torrentclaw", "sanet.st",
]

# ── Legitimate Sites (false positive prevention) ──────────────────
LEGITIMATE_SITES = [
    # News/media
    "youtube.com", "reddit.com", "twitter.com", "x.com",
    "facebook.com", "instagram.com", "tiktok.com",
    "wikipedia.org", "imdb.com", "rottentomatoes.com",
    "variety.com", "hollywoodreporter.com", "deadline.com",
    "theguardian.com", "bbc.com", "cnn.com", "nytimes.com",
    # Gaming legitimate sites
    "steampowered.com", "epicgames.com", "gog.com",
    "itch.io", "humble.com", "greenmangaming.com",
    "pcgamer.com", "ign.com", "kotaku.com", "polygon.com",
    "eurogamer.net", "gamespot.com", "rockpapershotgun.com",
    # Film legitimate sites
    "netflix.com", "primevideo.com", "disneyplus.com",
    "hulu.com", "hbomax.com", "appletv.com",
    "letterboxd.com", "justwatch.com",
    # Legal/official
    "lionsgate.com", "warnerbros.com", "sony.com",
    "universalpictures.com", "paramount.com", "disney.com",
    # Tech/dev
    "github.com", "stackoverflow.com", "dev.to",
]

# ── Game Crack Sites ──────────────────────────────────────────────
CRACK_SITES = [
    "fitgirl-repacks.site", "fitgirl-repacks.net",
    "dodi-repacks.site", "dodi-repacks.com",
    "gog-games.to", "gog-games.com",
    "cs.rin.ru", "skidrowreloaded.com",
    "skidrowcodex.net", "oceanofgames.com",
    "igg-games.com", "crackwatch.com",
    "steamunlocked.net", "gamesrepacks.com",
    "repack-games.com", "pcgamestorrents.com",
    "gametrex.com", "freegogpcgames.com",
    "ovagames.com", "repacklab.com",
]

# ── Crack Groups ──────────────────────────────────────────────────
CRACK_GROUPS = {
    "FitGirl": ["fitgirl"],
    "DODI": ["dodi"],
    "CPY": ["-cpy", ".cpy."],
    "EMPRESS": ["empress"],
    "CODEX": ["-codex", ".codex."],
    "SKIDROW": ["skidrow"],
    "RELOADED": ["-reloaded"],
    "PLAZA": ["-plaza"],
    "HOODLUM": ["-hoodlum"],
    "PROPHET": ["-prophet"],
    "RAZOR1911": ["razor1911"],
    "SteamUnlocked": ["steamunlocked"],
    "IGG": ["igg-games"],
    "GOG-Games": ["gog-games"],
    "RUNE": ["-rune"],
    "CONSPIRACY": ["-conspiracy"],
}

# ── Scene Release Groups (CAM) ────────────────────────────────────
CAM_GROUPS = [
    "CinemaCity", "EVO", "HDCAM", "CAMRip",
    "UNiON", "SyncUP", "TELESYNC", "BBB",
    "FGT", "YIFY", "YTS", "Decepticon",
]

# ── Utility Functions ─────────────────────────────────────────────
def contains_cam(text: str) -> bool:
    """Check if text contains CAM/piracy keywords."""
    t = text.lower()
    return any(k in t for k in CAM_KEYWORDS)

def is_piracy_domain(url: str) -> bool:
    """Check if URL is a known piracy domain."""
    u = url.lower()
    return any(d in u for d in PIRACY_DOMAINS)

def is_legitimate_site(url: str) -> bool:
    """Check if URL is a legitimate site (false positive prevention)."""
    u = url.lower()
    return any(s in u for s in LEGITIMATE_SITES)

def is_crack_site(url: str) -> bool:
    """Check if URL is a known game crack site."""
    u = url.lower()
    return any(d in u for d in CRACK_SITES)

def detect_crack_group(text: str) -> str:
    """Detect known crack group from text."""
    t = text.lower()
    for group, keywords in CRACK_GROUPS.items():
        if any(k in t for k in keywords):
            return group
    return "Unknown"

def detect_cam_group(text: str) -> str:
    """Detect known CAM release group from text."""
    t = text.lower()
    for group in CAM_GROUPS:
        if group.lower() in t:
            return group
    return "Unknown"

def film_slug(title: str) -> str:
    """Convert film title to URL slug."""
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

def now_utc() -> str:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def clean_text(text: str) -> str:
    """Clean HTML entities from text."""
    import html
    return html.unescape(text).strip()

# ── Rate Limiting ─────────────────────────────────────────────────
class RateLimiter:
    """Simple rate limiter for API calls."""
    def __init__(self, calls_per_second: float = 2.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0
    
    async def wait(self):
        import time
        now = time.time()
        wait_time = self.min_interval - (now - self.last_call)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self.last_call = time.time()

# ── Retry Logic ───────────────────────────────────────────────────
async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict = None,
    max_retries: int = 3,
    backoff: float = 1.0
) -> httpx.Response | None:
    """Fetch URL with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            r = await client.get(
                url, params=params,
                timeout=DEFAULT_TIMEOUT,
                headers=DEFAULT_HEADERS
            )
            if r.status_code == 200:
                return r
            elif r.status_code == 429:
                # Rate limited — wait longer
                wait = backoff * (2 ** attempt) * 2
                logging.warning(f"Rate limited on {url[:50]}, waiting {wait:.1f}s")
                await asyncio.sleep(wait)
            elif r.status_code in (403, 404):
                # Permanent failure — don't retry
                return None
            else:
                await asyncio.sleep(backoff * (2 ** attempt))
        except asyncio.TimeoutError:
            logging.warning(f"Timeout on {url[:50]}, attempt {attempt+1}")
            await asyncio.sleep(backoff * (2 ** attempt))
        except Exception as e:
            logging.warning(f"Error on {url[:50]}: {e}")
            if attempt == max_retries - 1:
                return None
            await asyncio.sleep(backoff * (2 ** attempt))
    return None

# ── SerpApi Search ────────────────────────────────────────────────
async def serp_search(
    query: str,
    client: httpx.AsyncClient,
    num: int = 5
) -> list[dict]:
    """
    Search via SerpApi — premium plan, 5000 searches/month.
    Returns list of {title, link, snippet} dicts.
    """
    if not SERP_API_KEY:
        return []
    try:
        r = await client.get(
            "https://serpapi.com/search",
            params={
                "q": query,
                "api_key": SERP_API_KEY,
                "num": num,
                "engine": "google",
                "safe": "off",
            },
            timeout=DEFAULT_TIMEOUT
        )
        if r.status_code == 200:
            return r.json().get("organic_results", [])
        return []
    except Exception as e:
        logging.warning(f"SerpApi error: {e}")
        return []

# ── DDG Search ────────────────────────────────────────────────────
async def ddg_search(
    query: str,
    client: httpx.AsyncClient
) -> list[dict]:
    """
    DuckDuckGo search — free, no API key, no quota.
    Returns list of {title, url} dicts.
    """
    from urllib.parse import unquote
    try:
        r = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            timeout=DEFAULT_TIMEOUT,
            headers=DEFAULT_HEADERS
        )
        if r.status_code != 200:
            return []
        body = r.text
        urls = [unquote(u) for u in re.findall(r'uddg=(https?[^&"]+)', body)]
        titles = re.findall(r'result__a"[^>]+>([^<]+)</a>', body)
        results = []
        for i, url in enumerate(urls[:15]):
            title = titles[i % len(titles)] if titles else ""
            results.append({
                "url": url,
                "title": clean_text(title),
                "link": url,
                "snippet": ""
            })
        return results
    except Exception as e:
        logging.warning(f"DDG search error: {e}")
        return []

# ── Film Match Check ──────────────────────────────────────────────
def film_matches(title: str, text: str, min_words: int = 2) -> bool:
    """
    Check if film title words appear in text.
    Requires minimum word matches to reduce false positives.
    """
    words = [w for w in title.lower().split() if len(w) > 2]
    if not words:
        return False
    matches = sum(1 for w in words if w in text.lower())
    return matches >= min(min_words, len(words))

# ── DMCA Report Generator ─────────────────────────────────────────
def generate_dmca_report(
    title: str,
    content_type: str,
    rights_holder: str,
    infringing_urls: list[str],
    contact_email: str,
    patent_ref: str = "US Provisional Patent 64/049,190"
) -> str:
    """
    Generate legally compliant DMCA takedown notice.
    All 6 elements per 17 U.S.C. § 512(c)(3).
    """
    urls_text = "\n".join(f"  {i+1}. {url}" 
                          for i, url in enumerate(infringing_urls)) \
                if infringing_urls else "  No infringing URLs detected."
    
    return f"""
{"="*72}
  DMCA TAKEDOWN NOTICE — 17 U.S.C. § 512(c)(3)
  Generated by CINEOS Anti-Piracy Platform
  {patent_ref}
{"="*72}

SECTION 1 — IDENTIFICATION OF COPYRIGHTED WORK
[17 U.S.C. § 512(c)(3)(A)(ii)]
  Title        : {title}
  Type         : {content_type}
  Rights Holder: {rights_holder}

SECTION 2 — IDENTIFICATION OF INFRINGING MATERIAL
[17 U.S.C. § 512(c)(3)(A)(iii)]
{urls_text}

SECTION 3 — CONTACT INFORMATION
[17 U.S.C. § 512(c)(3)(A)(iv)]
  Name         : Yugandhar Mallavarapu, CINEOS
  Organization : CINEOS Anti-Piracy Platform
  Email        : {contact_email}
  Patent       : {patent_ref}

SECTION 4 — GOOD FAITH BELIEF STATEMENT
[17 U.S.C. § 512(c)(3)(A)(v)]
  I have a good faith belief that use of the copyrighted material
  described above is not authorized by the copyright owner, its
  agent, or the law.

SECTION 5 — ACCURACY AND AUTHORITY STATEMENT
[17 U.S.C. § 512(c)(3)(A)(vi)]
  The information in this notification is accurate, and under
  penalty of perjury, I am authorized to act on behalf of the
  copyright owner of an exclusive right that is allegedly infringed.

SECTION 6 — ELECTRONIC SIGNATURE
[17 U.S.C. § 512(c)(3)(A)(i)]
  /s/ Yugandhar Mallavarapu, CINEOS
  Date: {now_utc()}
  Capacity: Authorized Anti-Piracy Agent

{"="*72}
  CINEOS — Content Intelligence and Protection Platform
  {patent_ref}
  dba.yugandhar@gmail.com
{"="*72}
"""

print("CINEOS config loaded — production ready")
print(f"SerpApi: {'configured' if SERP_API_KEY else 'MISSING'}")
print(f"API endpoint: {CINEOS_API}")
