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

LEGAL DISCLAIMER
{"─"*72}
  This report is provided for informational and monitoring purposes only.
  CINEOS is an anti-piracy detection service, not a legal representative.
  Rights holders should verify all findings and consult qualified legal
  counsel before filing DMCA takedown notices or taking legal action.
  Filing false DMCA notices may result in legal liability under 17 U.S.C.
  § 512(f). Always verify infringing URLs before filing.
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
  penalty of perjury, the information in this notification is accurate
  to the best of my knowledge. This report is provided for informational
  purposes. Rights holders should consult legal counsel before filing
  DMCA takedown notices.

SECTION 6 — ELECTRONIC SIGNATURE
[17 U.S.C. § 512(c)(3)(A)(i)]
  /s/ Yugandhar Mallavarapu, CINEOS
  Date: {now_utc()}
  Capacity             : Anti-Piracy Detection Service (Monitoring Only)

{"="*72}
  CINEOS — Content Intelligence and Protection Platform
  {patent_ref}
  yugandhar@cineos.in
{"="*72}
"""

print("CINEOS config loaded — production ready")
print(f"SerpApi: {'configured' if SERP_API_KEY else 'MISSING'}")
print(f"API endpoint: {CINEOS_API}")

# ══════════════════════════════════════════════════════════════════
# EXPANDED SITE LISTS — 100+ per category
# For use with SerpApi site: operator batch scanning
# ══════════════════════════════════════════════════════════════════

FILM_PIRACY_SITES_100 = [
    # Major torrent sites
    "1337x.to", "yts.mx", "yts.am", "rarbg.to", "rarbg.is",
    "thepiratebay.org", "tpb.party", "torrentgalaxy.to",
    "torrentleech.org", "iptorrents.com", "limetorrents.lol",
    "torrentz2.eu", "torlock.com", "magnetdl.com",
    "zooqle.to", "bitsearch.to", "torrentfunk.com",
    "kickasstorrents.to", "katcr.co", "bt4g.com",
    # Scene/NFO databases
    "predb.me", "predb.ovh", "xrel.to", "srrdb.com",
    "nzbindex.com", "nzbplanet.net", "nzbfinder.ws",
    # Streaming piracy
    "fmovies.to", "gomovies.sx", "123movies.ai",
    "putlocker.vip", "solarmovie.pe", "yesmovies.ag",
    "cmovies.tv", "vumoo.to", "popcorntime.app",
    "streamlord.com", "soap2day.to", "lookmovie.ag",
    "flixhq.to", "myflixer.to", "cineb.net",
    "hdtoday.cc", "flixtorr.to", "moviesjoy.plus",
    "bflix.gg", "nunflix.org", "pressplay.top",
    # Direct download
    "archive.org", "rapidgator.net", "nitroflare.com",
    "uptobox.com", "1fichier.com", "katfile.com",
    "filefox.cc", "ddownload.com", "drop.download",
    # Indian piracy
    "movierulz.com", "5movierulz.camera", "tamilmv.fi",
    "filmyzilla.com", "9xmovies.cool", "tamilblasters.life",
    "ibomma.com", "isaimini.com", "kuttymovies.com",
    "tamilyogi.wiki", "moviesda.com", "cinevood.com",
    "hdhub4u.com", "vegamovies.in", "bolly4u.trade",
    "filmyhit.com", "skymovies.mov", "filmysplit.com",
    "moviecounter.app", "filmy4wap.com", "mlwbd.com",
    "movierulz.plz", "tamilrockers.ws", "isaidub.com",
    "khatrimaza.com", "mp4moviez.com", "worldfree4u.com",
    "7starhd.com", "downloadhub.city", "rdxhd.com",
    # OpenSubtitles/tracking
    "opensubtitles.org", "subscene.com", "yifysubtitles.org",
    # Telegram/Social
    "t.me", "telegram.me",
    # WhereYouWatch/tracking
    "whereyouwatch.com", "watchsomuch.to",
    # P2P/Magnet
    "btdig.com", "snowfl.com", "btmet.com",
    "torrentdownload.ch", "torrentproject.se",
    # Additional streaming
    "m4ufree.tv", "azmovies.net", "gostream.site",
    "iosmovies.org", "watch32.app", "c1ne.co",
    "moviesmod.com", "extramovies.casa", "o2tvseries.com",
    "tvseries.to", "hdeuropix.com", "streamm4u.club",
]

GAMING_PIRACY_SITES_100 = [
    # Repack sites
    "fitgirl-repacks.site", "fitgirl-repacks.net",
    "dodi-repacks.site", "dodi-repacks.com",
    "gog-games.to", "gog-games.com",
    "cs.rin.ru", "skidrowreloaded.com",
    "skidrowcodex.net", "oceanofgames.com",
    "igg-games.com", "steamunlocked.net",
    "gamesrepacks.com", "repack-games.com",
    "pcgamestorrents.com", "gametrex.com",
    "freegogpcgames.com", "ovagames.com",
    "repacklab.com", "crackwatch.com",
    "codex-games.com", "empress-games.com",
    "rg-mechanics.org", "masquerade-repacks.com",
    "kaoskrew.org", "darksiderg.com",
    "xatab-repacks.com", "seyter-repacks.com",
    "corepack.io", "onlinefix.me",
    # Torrent sites gaming category
    "1337x.to", "torrentgalaxy.to", "rarbg.to",
    "limetorrents.lol", "nyaa.si", "rutracker.org",
    "kat.cr", "zooqle.to", "bitsearch.to",
    "torrentfunk.com", "bt4g.com", "magnetdl.com",
    # Scene databases
    "predb.me", "xrel.to", "srrdb.com", "predb.ovh",
    # Direct download gaming
    "archive.org", "rapidgator.net", "nitroflare.com",
    "uptobox.com", "1fichier.com",
    # Gaming specific
    "myabandonware.com", "old-games.com",
    "abandonia.com", "classicdosgames.com",
    # APK/Mobile piracy
    "apkpure.com", "apkmirror.com", "happymod.com",
    "an1.com", "apkdone.com", "revdl.com",
    "rexdl.com", "androeed.ru", "apknite.com",
    # DRM bypass sites
    "crack-status.com", "crackwatch.com",
    "gamestatus.info", "iscracked.net",
    # Additional repack sites
    "karanpc.com", "apunkagames.com", "ocean-of-games.com",
    "fullgamepc.com", "pcgames-download.com",
    "torrentpc.org", "gamepciso.com",
    "skidrow-games.com", "repack.info",
    "gamesdbase.com", "gload.cc",
]

MANGA_PIRACY_SITES_100 = [
    # Scan sites
    "mangadex.org", "mangareader.to", "mangafire.to",
    "mangakakalot.com", "manganelo.com", "mangapark.net",
    "mangaowl.net", "mangago.me", "readmng.com",
    "fanfox.net", "mangahere.cc", "mangapanda.com",
    "kissmanga.org", "mangafreak.net", "mangahub.io",
    "mangafast.net", "mangaclash.com", "mangastream.net",
    "readmanganato.com", "toonily.com", "manhwafreak.com",
    "isekaiscan.com", "reaperscans.com", "asurascans.com",
    "flamescans.org", "nitroscans.com", "aquamanga.com",
    "kunmanga.com", "bato.to", "webtoon.xyz",
    "manhuascan.com", "manhuafast.com", "manhuaplus.com",
    "manhwatop.com", "manhwakool.com", "1stkissmanga.com",
    # Ebook piracy
    "libgen.is", "libgen.rs", "libgen.st",
    "z-lib.org", "zlibrary.to", "b-ok.cc",
    "pdfdrive.com", "free-ebooks.net", "manybooks.net",
    "epublibre.org", "epubbooks.net", "getfreeebooks.com",
    "booksc.org", "sci-hub.se", "sci-hub.st",
    # Comic piracy
    "getcomics.org", "readcomiconline.li",
    "comicextra.com", "viewcomic.com", "readallcomics.com",
    "comicbookplus.com", "digitalcomicmuseum.com",
    "readcomicsonline.ru", "comix-load.com",
    # Torrent manga
    "nyaa.si", "bakabt.me", "animebytes.tv",
    "anidex.info", "tokyotosho.info",
    "mangaeden.com", "mangacow.com",
    # Light novel
    "novelupdates.com", "royalroad.com", "wuxiaworld.com",
    "lightnovelworld.com", "novelfull.com", "readlightnovel.me",
    "mtlnation.com", "webnovel.com", "scribblehub.com",
    # Raw manga
    "manga1001.top", "rawkuma.com", "mangabuddy.com",
    "klmanga.com", "manga-zip.net", "dl-raw.net",
]

MUSIC_PIRACY_SITES_100 = [
    # MP3 download sites
    "mp3juices.cc", "mp3skull.com", "mp3clan.com",
    "freemp3cloud.com", "beemp3.com", "mp3download.to",
    "freemp3.fm", "mp3raid.com", "mp3skull.cc",
    "waptrick.com", "mdundo.com", "mp3paw.com",
    "mp3fusion.net", "fakaza.com", "zamusic.org",
    "hitxgh.com", "ghanamotion.com", "tooxclusive.com",
    "naijaloaded.com.ng", "naijapals.com",
    # Indian music piracy
    "pagalworld.com", "djpunjab.com", "mrjatt.in",
    "songspk.name", "downloadming.uno", "djjohal.com",
    "djmaza.info", "bestwap.in", "raagsong.com",
    "gaana.link", "hungama.link", "saavnpro.com",
    "wynk.link", "jiosaavn.link", "bollywood.link",
    # Russian music sites
    "rutracker.org", "zaycev.net", "prostopleer.com",
    "pleer.net", "mp3base.ru", "muzmo.ru",
    "realmusic.ru", "zvuki.ru", "muspy.com",
    # YouTube rip sites
    "y2mate.com", "ytmp3.cc", "convertmp3.io",
    "yt1s.com", "flvto.biz", "2conv.com",
    "onlinevideoconverter.com", "mp3ify.com",
    "notube.net", "savefrom.net", "clipconverter.cc",
    # Torrent music
    "1337x.to", "rutracker.org", "nyaa.si",
    "torrentgalaxy.to", "limetorrents.lol",
    "bakabt.me", "what.cd", "redacted.ch",
    "orpheus.network", "dicmusic.club",
    # Archive/sharing
    "archive.org", "soundcloud.com",
    # Album download
    "free-mp3-download.net", "allmp3.com",
    "downloadalbums.club", "musicpleer.audio",
    "mp3va.com", "musicmp3.com", "audiomack.link",
    # Telegram music channels
    "t.me",
    # VK
    "vk.com",
]

SPORTS_PIRACY_SITES_100 = [
    # Illegal streaming sites
    "crackstreams.com", "crackstreams.live",
    "buffstream.io", "buffstreams.app",
    "sportsurge.net", "sportsurge.app",
    "hesgoal.com", "hesgoal.live",
    "vipbox.lc", "vipbox.tv", "viprow.me",
    "sportlemon.tv", "firstrowsports.eu",
    "livetv.sx", "livetv.ru",
    "ronaldo7.net", "wiziwig.tv",
    "laola1.tv", "laola1.at",
    "strikeout.nu", "streameast.live",
    "sportsbay.org", "sportp2p.com",
    "streamhunter.eu", "atdhe.net",
    "fromhot.com", "batman-stream.com",
    "myp2p.eu", "vipleague.lc",
    "rojadirecta.me", "rojadirecta.es",
    "tarjetarojaonline.sx", "peliculasyonkis.com",
    # Cricket streaming
    "cricfree.sc", "crictime.com", "smartcric.com",
    "webcric.com", "crichd.com", "cricwick.net",
    "willow.tv.link", "hotstar.link",
    "star.link", "sonyliv.link",
    # Football streaming
    "footybite.cc", "footybite.to",
    "soccerstreams.net", "nflbite.com",
    "nbabite.com", "mlbbite.com",
    "nhllive.net", "boxingstreams.cc",
    "mmastreams.me", "ufcstreams.me",
    # IPTV
    "iptvcat.com", "freefreeiptv.com",
    "freeiptvlist.tk", "iptvsource.com",
    "iptv-org.github.io", "iptvleak.com",
    # Torrent sports
    "1337x.to", "torrentgalaxy.to",
    "limetorrents.lol", "nyaa.si",
    # Reddit
    "reddit.com",
    # Telegram sports
    "t.me",
    # P2P sports
    "acestream.net", "sopcast.com",
    "channelsurfer.live", "streamtp.com",
    "sportstream.live", "streamwoop.com",
    "sportsstream24.com", "livesport.ws",
    "streamonsport.com", "sport365.live",
    "livescore.cric", "sportsmax.tv.link",
]

print("Expanded site lists loaded:")
print(f"  Film:   {len(FILM_PIRACY_SITES_100)} sites")
print(f"  Gaming: {len(GAMING_PIRACY_SITES_100)} sites")
print(f"  Manga:  {len(MANGA_PIRACY_SITES_100)} sites")
print(f"  Music:  {len(MUSIC_PIRACY_SITES_100)} sites")
print(f"  Sports: {len(SPORTS_PIRACY_SITES_100)} sites")

# ══════════════════════════════════════════════════════════════════
# EXPANDED SITE LISTS — 100+ per category
# For use with SerpApi site: operator batch scanning
# ══════════════════════════════════════════════════════════════════

FILM_PIRACY_SITES_100 = [
    # Major torrent sites
    "1337x.to", "yts.mx", "yts.am", "rarbg.to", "rarbg.is",
    "thepiratebay.org", "tpb.party", "torrentgalaxy.to",
    "torrentleech.org", "iptorrents.com", "limetorrents.lol",
    "torrentz2.eu", "torlock.com", "magnetdl.com",
    "zooqle.to", "bitsearch.to", "torrentfunk.com",
    "kickasstorrents.to", "katcr.co", "bt4g.com",
    # Scene/NFO databases
    "predb.me", "predb.ovh", "xrel.to", "srrdb.com",
    "nzbindex.com", "nzbplanet.net", "nzbfinder.ws",
    # Streaming piracy
    "fmovies.to", "gomovies.sx", "123movies.ai",
    "putlocker.vip", "solarmovie.pe", "yesmovies.ag",
    "cmovies.tv", "vumoo.to", "popcorntime.app",
    "streamlord.com", "soap2day.to", "lookmovie.ag",
    "flixhq.to", "myflixer.to", "cineb.net",
    "hdtoday.cc", "flixtorr.to", "moviesjoy.plus",
    "bflix.gg", "nunflix.org", "pressplay.top",
    # Direct download
    "archive.org", "rapidgator.net", "nitroflare.com",
    "uptobox.com", "1fichier.com", "katfile.com",
    "filefox.cc", "ddownload.com", "drop.download",
    # Indian piracy
    "movierulz.com", "5movierulz.camera", "tamilmv.fi",
    "filmyzilla.com", "9xmovies.cool", "tamilblasters.life",
    "ibomma.com", "isaimini.com", "kuttymovies.com",
    "tamilyogi.wiki", "moviesda.com", "cinevood.com",
    "hdhub4u.com", "vegamovies.in", "bolly4u.trade",
    "filmyhit.com", "skymovies.mov", "filmysplit.com",
    "moviecounter.app", "filmy4wap.com", "mlwbd.com",
    "movierulz.plz", "tamilrockers.ws", "isaidub.com",
    "khatrimaza.com", "mp4moviez.com", "worldfree4u.com",
    "7starhd.com", "downloadhub.city", "rdxhd.com",
    # OpenSubtitles/tracking
    "opensubtitles.org", "subscene.com", "yifysubtitles.org",
    # Telegram/Social
    "t.me", "telegram.me",
    # WhereYouWatch/tracking
    "whereyouwatch.com", "watchsomuch.to",
    # P2P/Magnet
    "btdig.com", "snowfl.com", "btmet.com",
    "torrentdownload.ch", "torrentproject.se",
    # Additional streaming
    "m4ufree.tv", "azmovies.net", "gostream.site",
    "iosmovies.org", "watch32.app", "c1ne.co",
    "moviesmod.com", "extramovies.casa", "o2tvseries.com",
    "tvseries.to", "hdeuropix.com", "streamm4u.club",
]

GAMING_PIRACY_SITES_100 = [
    # Repack sites
    "fitgirl-repacks.site", "fitgirl-repacks.net",
    "dodi-repacks.site", "dodi-repacks.com",
    "gog-games.to", "gog-games.com",
    "cs.rin.ru", "skidrowreloaded.com",
    "skidrowcodex.net", "oceanofgames.com",
    "igg-games.com", "steamunlocked.net",
    "gamesrepacks.com", "repack-games.com",
    "pcgamestorrents.com", "gametrex.com",
    "freegogpcgames.com", "ovagames.com",
    "repacklab.com", "crackwatch.com",
    "codex-games.com", "empress-games.com",
    "rg-mechanics.org", "masquerade-repacks.com",
    "kaoskrew.org", "darksiderg.com",
    "xatab-repacks.com", "seyter-repacks.com",
    "corepack.io", "onlinefix.me",
    # Torrent sites gaming category
    "1337x.to", "torrentgalaxy.to", "rarbg.to",
    "limetorrents.lol", "nyaa.si", "rutracker.org",
    "kat.cr", "zooqle.to", "bitsearch.to",
    "torrentfunk.com", "bt4g.com", "magnetdl.com",
    # Scene databases
    "predb.me", "xrel.to", "srrdb.com", "predb.ovh",
    # Direct download gaming
    "archive.org", "rapidgator.net", "nitroflare.com",
    "uptobox.com", "1fichier.com",
    # Gaming specific
    "myabandonware.com", "old-games.com",
    "abandonia.com", "classicdosgames.com",
    # APK/Mobile piracy
    "apkpure.com", "apkmirror.com", "happymod.com",
    "an1.com", "apkdone.com", "revdl.com",
    "rexdl.com", "androeed.ru", "apknite.com",
    # DRM bypass sites
    "crack-status.com", "crackwatch.com",
    "gamestatus.info", "iscracked.net",
    # Additional repack sites
    "karanpc.com", "apunkagames.com", "ocean-of-games.com",
    "fullgamepc.com", "pcgames-download.com",
    "torrentpc.org", "gamepciso.com",
    "skidrow-games.com", "repack.info",
    "gamesdbase.com", "gload.cc",
]

MANGA_PIRACY_SITES_100 = [
    # Scan sites
    "mangadex.org", "mangareader.to", "mangafire.to",
    "mangakakalot.com", "manganelo.com", "mangapark.net",
    "mangaowl.net", "mangago.me", "readmng.com",
    "fanfox.net", "mangahere.cc", "mangapanda.com",
    "kissmanga.org", "mangafreak.net", "mangahub.io",
    "mangafast.net", "mangaclash.com", "mangastream.net",
    "readmanganato.com", "toonily.com", "manhwafreak.com",
    "isekaiscan.com", "reaperscans.com", "asurascans.com",
    "flamescans.org", "nitroscans.com", "aquamanga.com",
    "kunmanga.com", "bato.to", "webtoon.xyz",
    "manhuascan.com", "manhuafast.com", "manhuaplus.com",
    "manhwatop.com", "manhwakool.com", "1stkissmanga.com",
    # Ebook piracy
    "libgen.is", "libgen.rs", "libgen.st",
    "z-lib.org", "zlibrary.to", "b-ok.cc",
    "pdfdrive.com", "free-ebooks.net", "manybooks.net",
    "epublibre.org", "epubbooks.net", "getfreeebooks.com",
    "booksc.org", "sci-hub.se", "sci-hub.st",
    # Comic piracy
    "getcomics.org", "readcomiconline.li",
    "comicextra.com", "viewcomic.com", "readallcomics.com",
    "comicbookplus.com", "digitalcomicmuseum.com",
    "readcomicsonline.ru", "comix-load.com",
    # Torrent manga
    "nyaa.si", "bakabt.me", "animebytes.tv",
    "anidex.info", "tokyotosho.info",
    "mangaeden.com", "mangacow.com",
    # Light novel
    "novelupdates.com", "royalroad.com", "wuxiaworld.com",
    "lightnovelworld.com", "novelfull.com", "readlightnovel.me",
    "mtlnation.com", "webnovel.com", "scribblehub.com",
    # Raw manga
    "manga1001.top", "rawkuma.com", "mangabuddy.com",
    "klmanga.com", "manga-zip.net", "dl-raw.net",
]

MUSIC_PIRACY_SITES_100 = [
    # MP3 download sites
    "mp3juices.cc", "mp3skull.com", "mp3clan.com",
    "freemp3cloud.com", "beemp3.com", "mp3download.to",
    "freemp3.fm", "mp3raid.com", "mp3skull.cc",
    "waptrick.com", "mdundo.com", "mp3paw.com",
    "mp3fusion.net", "fakaza.com", "zamusic.org",
    "hitxgh.com", "ghanamotion.com", "tooxclusive.com",
    "naijaloaded.com.ng", "naijapals.com",
    # Indian music piracy
    "pagalworld.com", "djpunjab.com", "mrjatt.in",
    "songspk.name", "downloadming.uno", "djjohal.com",
    "djmaza.info", "bestwap.in", "raagsong.com",
    "gaana.link", "hungama.link", "saavnpro.com",
    "wynk.link", "jiosaavn.link", "bollywood.link",
    # Russian music sites
    "rutracker.org", "zaycev.net", "prostopleer.com",
    "pleer.net", "mp3base.ru", "muzmo.ru",
    "realmusic.ru", "zvuki.ru", "muspy.com",
    # YouTube rip sites
    "y2mate.com", "ytmp3.cc", "convertmp3.io",
    "yt1s.com", "flvto.biz", "2conv.com",
    "onlinevideoconverter.com", "mp3ify.com",
    "notube.net", "savefrom.net", "clipconverter.cc",
    # Torrent music
    "1337x.to", "rutracker.org", "nyaa.si",
    "torrentgalaxy.to", "limetorrents.lol",
    "bakabt.me", "what.cd", "redacted.ch",
    "orpheus.network", "dicmusic.club",
    # Archive/sharing
    "archive.org", "soundcloud.com",
    # Album download
    "free-mp3-download.net", "allmp3.com",
    "downloadalbums.club", "musicpleer.audio",
    "mp3va.com", "musicmp3.com", "audiomack.link",
    # Telegram music channels
    "t.me",
    # VK
    "vk.com",
]

SPORTS_PIRACY_SITES_100 = [
    # Illegal streaming sites
    "crackstreams.com", "crackstreams.live",
    "buffstream.io", "buffstreams.app",
    "sportsurge.net", "sportsurge.app",
    "hesgoal.com", "hesgoal.live",
    "vipbox.lc", "vipbox.tv", "viprow.me",
    "sportlemon.tv", "firstrowsports.eu",
    "livetv.sx", "livetv.ru",
    "ronaldo7.net", "wiziwig.tv",
    "laola1.tv", "laola1.at",
    "strikeout.nu", "streameast.live",
    "sportsbay.org", "sportp2p.com",
    "streamhunter.eu", "atdhe.net",
    "fromhot.com", "batman-stream.com",
    "myp2p.eu", "vipleague.lc",
    "rojadirecta.me", "rojadirecta.es",
    "tarjetarojaonline.sx", "peliculasyonkis.com",
    # Cricket streaming
    "cricfree.sc", "crictime.com", "smartcric.com",
    "webcric.com", "crichd.com", "cricwick.net",
    "willow.tv.link", "hotstar.link",
    "star.link", "sonyliv.link",
    # Football streaming
    "footybite.cc", "footybite.to",
    "soccerstreams.net", "nflbite.com",
    "nbabite.com", "mlbbite.com",
    "nhllive.net", "boxingstreams.cc",
    "mmastreams.me", "ufcstreams.me",
    # IPTV
    "iptvcat.com", "freefreeiptv.com",
    "freeiptvlist.tk", "iptvsource.com",
    "iptv-org.github.io", "iptvleak.com",
    # Torrent sports
    "1337x.to", "torrentgalaxy.to",
    "limetorrents.lol", "nyaa.si",
    # Reddit
    "reddit.com",
    # Telegram sports
    "t.me",
    # P2P sports
    "acestream.net", "sopcast.com",
    "channelsurfer.live", "streamtp.com",
    "sportstream.live", "streamwoop.com",
    "sportsstream24.com", "livesport.ws",
    "streamonsport.com", "sport365.live",
    "livescore.cric", "sportsmax.tv.link",
]

print("Expanded site lists loaded:")
print(f"  Film:   {len(FILM_PIRACY_SITES_100)} sites")
print(f"  Gaming: {len(GAMING_PIRACY_SITES_100)} sites")
print(f"  Manga:  {len(MANGA_PIRACY_SITES_100)} sites")
print(f"  Music:  {len(MUSIC_PIRACY_SITES_100)} sites")
print(f"  Sports: {len(SPORTS_PIRACY_SITES_100)} sites")


async def batch_serp_scan(
    title: str,
    sites: list[str],
    client,
    batch_size: int = 10
) -> list[dict]:
    """
    Scan 100+ sites via SerpApi using OR operator.
    Batches sites into groups of 10 for efficient querying.
    1 SerpApi search = 10 sites checked simultaneously.
    100 sites = only 10 SerpApi searches instead of 100.
    """
    if not SERP_API_KEY:
        return []

    all_hits = []
    # Group sites into batches
    batches = [sites[i:i+batch_size]
               for i in range(0, len(sites), batch_size)]

    for batch in batches:
        # Build site: OR query
        site_query = " OR ".join(f"site:{s}" for s in batch)
        query = f'"{title}" ({site_query})'

        try:
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": SERP_API_KEY,
                    "num": 10,
                    "engine": "google",
                },
                timeout=15
            )
            if r.status_code == 200:
                items = r.json().get("organic_results", [])
                for item in items:
                    link = item.get("link", "")
                    t = item.get("title", "")
                    snippet = item.get("snippet", "")
                    # Verify title match
                    if film_matches(title, f"{t} {snippet}"):
                        all_hits.append({
                            "platform": link.split('/')[2][:30],
                            "url": link,
                            "title": t[:80],
                            "snippet": snippet[:100],
                        })
            await asyncio.sleep(0.3)
        except Exception as e:
            logging.warning(f"Batch serp error: {e}")

    return all_hits
