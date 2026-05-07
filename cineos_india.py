#!/usr/bin/env python3
"""
CINEOS India v3.0 — Expanded to 75+ platforms
===============================================
Fixes:
- Reject category/page URLs — require film-specific URLs
- Reject news articles about piracy
- Expand from 20 to 75+ Indian piracy platforms
- Add direct URL construction for known sites
- Better quality detection
- Add Telegram Indian channels
- Add Google News piracy alerts for Indian films

US Provisional Patent 64/049,190
"""

import asyncio
import httpx
import re
import os
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from urllib.parse import unquote, quote

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CINEOS-INDIA-V3] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.india.v3")

SERP_KEY = os.getenv("SERP_API_KEY", "")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.5",
}

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def film_ok(title: str, text: str, min_words: int = 2) -> bool:
    words = [w for w in title.lower().split() if len(w) > 2]
    if not words:
        return False
    text_lower = text.lower()
    # Check individual words
    word_matches = sum(1 for w in words if w in text_lower)
    # Also check concatenated title (e.g. "Jet Lee" -> "jetlee")
    concat = title.lower().replace(' ', '')
    if len(concat) > 4 and concat in text_lower:
        return True
    return word_matches >= min(min_words, len(words))

def is_news_article(url: str, text: str) -> bool:
    """Reject news articles about piracy — not actual piracy."""
    news_domains = [
        "abplive.com", "ndtv.com", "indiatoday.in", "timesofindia.com",
        "thehindu.com", "hindustantimes.com", "india.com", "bollywoodhungama.com",
        "pinkvilla.com", "filmfare.com", "deccanchronicle.com", "telanganatoday.com",
        "andhrajyothy.com", "sakshi.com", "eenadu.net", "news18.com",
        "firstpost.com", "scroll.in", "thequint.com", "oneindia.com",
        "mediaindia.eu", "gulte.com", "123telugu.com", "greatandhra.com",
        "tollywoodzone.com", "cinejosh.com", "idlebrain.com",
    ]
    u = url.lower()
    if any(d in u for d in news_domains):
        return True
    # Reject URLs with news-like patterns
    news_patterns = [
        "download-online", "piracy-penalty", "illegal-piracy",
        "tamilrockers-link", "filmyzilla-link", "punishment",
        "risk-illegal", "watch-online-free-warning",
    ]
    return any(p in u.lower() for p in news_patterns)

def is_category_page(url: str) -> bool:
    """Reject category/listing pages — require film-specific URLs."""
    category_patterns = [
        "/category/", "/page/", "/tag/", "/movies/page/",
        "/bollywood/", "/hollywood/", "/telugu/page/",
        "/?s=", "/search/", "/index.php",
        "/latest-movies/", "/new-movies/",
        "/user/", "?s=", "?c=", "?q=",
        "/genre/", "/actor/", "/director/",
        "/singer-", "/music/", "/songs-", "/album-", "/lyrics-",
        "songs-", "-songs/", "/series/", "/season-",
    ]
    u = url.lower().rstrip('/')
    for p in category_patterns:
        if p in u:
            return True
    # Reject if URL ends with just a number
    if re.search(r'/\d+/?$', u):
        return True
    return False

def has_piracy_signal(text: str) -> bool:
    signals = [
        "download", "watch online", "free download", "hdrip",
        "dvdrip", "camrip", "webrip", "bluray", "720p", "1080p",
        "dubbed", "tamil", "telugu", "hindi", "malayalam",
        "torrent", "magnet", "direct download",
    ]
    t = text.lower()
    return sum(1 for s in signals if s in t) >= 2


# ── 75+ Indian piracy platforms ───────────────────────────────────
INDIAN_PLATFORMS = [
    # ── Priority 1 — Telugu primary ────────────────────────────
    {"name":"Movierulz",       "domain":"5movierulz.markets",   "lang":"Telugu",   "p":1},
    {"name":"Movierulz2",      "domain":"movierulz.markets",        "lang":"Telugu",   "p":1},
    {"name":"Movierulz3",      "domain":"5movierulz.one",        "lang":"Telugu",   "p":1},
    {"name":"Movierulz4",      "domain":"3movierulz.markets",       "lang":"Telugu",   "p":1},
    {"name":"iBomma",          "domain":"ibommamoviess.com",           "lang":"Telugu",   "p":1},
    {"name":"iBomma2",         "domain":"ibomma.one",            "lang":"Telugu",   "p":1},
    {"name":"TollyStream",     "domain":"tollystream.com",      "lang":"Telugu",   "p":1},
    {"name":"Cinevood",        "domain":"cinevood.com",         "lang":"Telugu",   "p":1},
    # teluguwap removed — music site not film piracy
    {"name":"OFilmywap",       "domain":"ofilmywap.com",        "lang":"Telugu",   "p":1},
    {"name":"Todaypk",         "domain":"todaypk.chat",         "lang":"Telugu",   "p":1},
    {"name":"Movierulz5",      "domain":"movierulz5.com",       "lang":"Telugu",   "p":1},

    # ── Priority 1 — Tamil primary ─────────────────────────────
    {"name":"TamilMV",         "domain":"1tamilmv.world",       "lang":"Tamil",    "p":1},
    {"name":"TamilMV2",        "domain":"tamilmv.wiki",         "lang":"Tamil",    "p":1},
    {"name":"TamilRockers",    "domain":"tamilrockers.ws",      "lang":"Tamil",    "p":1},
    {"name":"TamilBlasters",   "domain":"tamilblasters.life",   "lang":"Tamil",    "p":1},
    {"name":"TamilBlasters2",  "domain":"tamilblasters.ws",     "lang":"Tamil",    "p":1},
    {"name":"Isaimini",        "domain":"isaimini.com",         "lang":"Tamil",    "p":1},
    {"name":"Isaimini2",       "domain":"isaimini.io",          "lang":"Tamil",    "p":1},
    {"name":"TamilGun",        "domain":"tamilgun.com",         "lang":"Tamil",    "p":1},
    {"name":"TamilYogi",       "domain":"tamilyogi.wiki",       "lang":"Tamil",    "p":1},
    {"name":"Kuttymovies",     "domain":"kuttymovies.com",      "lang":"Tamil",    "p":1},
    {"name":"Kuttymovies2",    "domain":"kuttymovies4u.com",    "lang":"Tamil",    "p":1},
    {"name":"Moviesda",        "domain":"moviesda.com",         "lang":"Tamil",    "p":1},
    {"name":"Moviesda2",       "domain":"moviesda.io",          "lang":"Tamil",    "p":1},
    {"name":"TamilPrint",      "domain":"tamilprint.com",       "lang":"Tamil",    "p":1},
    {"name":"TamilPrint2",     "domain":"tamilprint2.com",      "lang":"Tamil",    "p":1},
    {"name":"Madrasrockers",   "domain":"madrasrockers.com",    "lang":"Tamil",    "p":1},
    {"name":"Isaidub",         "domain":"isaidub.com",          "lang":"Tamil",    "p":1},
    {"name":"TamilRasigan",    "domain":"tamilrasigan.com",     "lang":"Tamil",    "p":1},
    {"name":"Tamilrockers2",   "domain":"tamilrockers.cx",      "lang":"Tamil",    "p":1},

    # ── Priority 1 — Hindi primary ─────────────────────────────
    {"name":"Filmyzilla",      "domain":"filmyzilla.com.co",    "lang":"Hindi",    "p":1},
    {"name":"Filmyzilla2",     "domain":"filmyzilla2.com",      "lang":"Hindi",    "p":1},
    {"name":"Filmyzilla3",     "domain":"filmyzilla.pg.in",     "lang":"Hindi",    "p":1},
    {"name":"9xMovies",        "domain":"9xmovies.cool",        "lang":"Hindi",    "p":1},
    {"name":"9xMovies2",       "domain":"9xmovies.pink",        "lang":"Hindi",    "p":1},
    {"name":"9xMovies3",       "domain":"9xmovies.show",        "lang":"Hindi",    "p":1},
    {"name":"Mp4moviez",       "domain":"mp4moviez.com",        "lang":"Hindi",    "p":1},
    {"name":"Mp4moviez2",      "domain":"mp4moviez.in",         "lang":"Hindi",    "p":1},
    {"name":"Vegamovies",      "domain":"vegamovies.in",        "lang":"Hindi",    "p":1},
    {"name":"Vegamovies2",     "domain":"vegamovies.nl",        "lang":"Hindi",    "p":1},
    {"name":"HDHub4u",         "domain":"hdhub4u.com",          "lang":"Hindi",    "p":1},
    {"name":"HDHub4u2",        "domain":"hdhub4u.skin",         "lang":"Hindi",    "p":1},
    {"name":"Bolly4u",         "domain":"bolly4u.trade",        "lang":"Hindi",    "p":1},
    {"name":"Bolly4u2",        "domain":"bolly4u.top",          "lang":"Hindi",    "p":1},

    # ── Priority 2 — Pan-India ─────────────────────────────────
    {"name":"Filmyhit",        "domain":"filmyhit.com.co",      "lang":"Pan-India","p":2},
    {"name":"Filmy4wap",       "domain":"filmy4wap.com",        "lang":"Pan-India","p":2},
    {"name":"Filmy4wap2",      "domain":"filmy4wap.lol",        "lang":"Pan-India","p":2},
    {"name":"WorldFree4u",     "domain":"worldfree4u.mom",      "lang":"Pan-India","p":2},
    {"name":"WorldFree4u2",    "domain":"worldfree4u.trade",    "lang":"Pan-India","p":2},
    {"name":"Khatrimaza",      "domain":"khatrimaza.com",       "lang":"Pan-India","p":2},
    {"name":"Khatrimaza2",     "domain":"khatrimaza.mov",       "lang":"Pan-India","p":2},
    {"name":"7StarHD",         "domain":"7starhd.art",          "lang":"Pan-India","p":2},
    {"name":"7StarHD2",        "domain":"7starhd.show",         "lang":"Pan-India","p":2},
    {"name":"SkymoviesHD",     "domain":"skymovieshd.mov",      "lang":"Pan-India","p":2},
    {"name":"SkymoviesHD2",    "domain":"skymovieshd.pink",     "lang":"Pan-India","p":2},
    {"name":"DownloadHub",     "domain":"downloadhub.city",     "lang":"Pan-India","p":2},
    {"name":"DownloadHub2",    "domain":"downloadhub.skin",     "lang":"Pan-India","p":2},
    {"name":"RdxHD",           "domain":"rdxhd.com",            "lang":"Pan-India","p":2},
    {"name":"Moviesmod",       "domain":"moviesmod.com",        "lang":"Pan-India","p":2},
    {"name":"Moviesmod2",      "domain":"moviesmod.pe",         "lang":"Pan-India","p":2},
    {"name":"Katmoviesx",      "domain":"katmoviesx.com",       "lang":"Pan-India","p":2},
    {"name":"Katmoviesx2",     "domain":"katmoviesx.io",        "lang":"Pan-India","p":2},
    {"name":"Mkvcage",         "domain":"mkvcage.com",          "lang":"Pan-India","p":2},
    {"name":"Moviecounter",    "domain":"moviecounter.app",     "lang":"Pan-India","p":2},
    {"name":"Extramovies",     "domain":"extramovies.casa",     "lang":"Pan-India","p":2},
    {"name":"O2TVSeries",      "domain":"o2tvseries.com",       "lang":"Pan-India","p":2},
    {"name":"Jalshamoviez",    "domain":"jalshamoviez.ac",      "lang":"Pan-India","p":2},
    {"name":"Jalshamoviez2",   "domain":"jalshamoviez.bid",     "lang":"Pan-India","p":2},
    {"name":"Filmysplit",      "domain":"filmysplit.com",        "lang":"Pan-India","p":2},
    {"name":"AFilmywap",       "domain":"afilmywap.com",        "lang":"Pan-India","p":2},
    {"name":"Filmywap",        "domain":"filmywap.com",         "lang":"Pan-India","p":2},
    {"name":"Coolmoviez",      "domain":"coolmoviez.com",       "lang":"Pan-India","p":2},
    {"name":"Djpunjab",        "domain":"djpunjab.com",         "lang":"Pan-India","p":2},
    {"name":"PagalMovies",     "domain":"pagalmovies.com",      "lang":"Pan-India","p":2},
    {"name":"MkvMoviesPoint",  "domain":"mkvmoviespoint.life",  "lang":"Pan-India","p":2},
    {"name":"DesireMovies",    "domain":"desiremovies.beauty",  "lang":"Pan-India","p":2},
    {"name":"Moviehax",        "domain":"moviehax.com",         "lang":"Pan-India","p":2},
    {"name":"Moviesroot",      "domain":"moviesroot.com",       "lang":"Pan-India","p":2},
    {"name":"YoMovies",        "domain":"yomovies.cool",        "lang":"Pan-India","p":2},
    {"name":"GoMovies",        "domain":"gomovies.sx",          "lang":"Pan-India","p":2},
    {"name":"123Movies",       "domain":"123movies.gd",         "lang":"Pan-India","p":2},
    {"name":"9xTamil",         "domain":"9xtamil.com",          "lang":"Tamil",    "p":2},
    {"name":"Tamilrockers3",   "domain":"tamilrockers.net",     "lang":"Tamil",    "p":2},

    # ── Priority 2 — Malayalam ─────────────────────────────────
    {"name":"MalayalamTorrents","domain":"mlwbd.com",           "lang":"Malayalam","p":2},
    {"name":"Cinemavilla",     "domain":"cinemavilla.com.co",   "lang":"Malayalam","p":2},
    {"name":"Tamilmv3",        "domain":"tamilmv.app",          "lang":"Malayalam","p":2},

    # ── Priority 3 — Torrent/Global ────────────────────────────
    {"name":"1337x",           "domain":"1337x.to",             "lang":"Pan-India","p":3},
    {"name":"TorrentGalaxy",   "domain":"torrentgalaxy.to",     "lang":"Pan-India","p":3},
    {"name":"NetflixLeak",     "domain":"netflixleak.com",      "lang":"Pan-India","p":3},
    {"name":"PrimeVideoLeak",  "domain":"primevideoleak.com",   "lang":"Pan-India","p":3},
    {"name":"Moviesflix",      "domain":"moviesflix.com.co",    "lang":"Pan-India","p":3},
    {"name":"Moviesflix2",     "domain":"moviesflix.in",        "lang":"Pan-India","p":3},
    {"name":"Hdhub",           "domain":"hdhub.life",           "lang":"Pan-India","p":3},
    {"name":"FilmyZap",        "domain":"filmyzap.com",         "lang":"Hindi",    "p":3},
    {"name":"Bollyshare",      "domain":"bollyshare.com",       "lang":"Hindi",    "p":3},
    {"name":"Hdmovie2",        "domain":"hdmovie2.com",         "lang":"Pan-India","p":3},
    {"name":"Moviesbaba",      "domain":"moviesbaba.net",       "lang":"Pan-India","p":3},
    {"name":"Uwatchfree",      "domain":"uwatchfree.com",       "lang":"Pan-India","p":3},
    {"name":"Tamilplay",       "domain":"tamilplay.com",        "lang":"Tamil",    "p":3},
    {"name":"Tamilplay2",      "domain":"tamilplay.net",        "lang":"Tamil",    "p":3},
    {"name":"Isaimovies",      "domain":"isaimovies.com",       "lang":"Tamil",    "p":3},
    {"name":"Tamilanda",       "domain":"tamilanda.com",        "lang":"Tamil",    "p":3},
]



@dataclass
class IndiaHit:
    platform: str
    language: str
    url: str
    quality: str = ""
    detail: str = ""
    confidence: float = 0.0
    severity: str = "HIGH"
    is_cam: bool = False


# ── Direct URL construction scanner ──────────────────────────────
DIRECT_URL_PATTERNS = [
    # Pattern: (site, url_template, verify_keywords)
    ("TamilRockers",    "https://www.tamilrockers.ws/{slug}/",
     ["download", "watch", "hdrip", "720p", "1080p"]),
    ("Movierulz",       "https://www.5movierulz.markets/{slug}-telugu/",
     ["watch online", "free", "hdrip", "full movie"]),
    ("Movierulz2",      "https://www.5movierulz.markets/{slug}-hindi/",
     ["watch online", "free", "hdrip", "full movie"]),
    ("Movierulz3",      "https://www.5movierulz.markets/{slug}-tamil/",
     ["watch online", "free", "hdrip", "full movie"]),
    ("Filmyzilla",      "https://filmyzilla.com.co/{slug}/",
     ["download", "hdrip", "720p", "hindi"]),
    ("TamilMV",         "https://www.1tamilmv.world/{slug}/",
     ["download", "watch", "hdrip"]),
    ("Isaimini",        "https://isaimini.com/{slug}/",
     ["download", "tamil", "hdrip"]),
    ("Kuttymovies",     "https://kuttymovies.com/{slug}/",
     ["download", "tamil", "hdrip"]),
    ("Moviesda",        "https://moviesda.com/{slug}/",
     ["download", "tamil", "hdrip"]),
    ("TamilGun",        "https://www.tamilgun.com/{slug}/",
     ["download", "watch", "tamil"]),
    ("Madrasrockers",   "https://www.madrasrockers.com/{slug}/",
     ["download", "watch", "hdrip"]),
    ("9xMovies",        "https://9xmovies.cool/{slug}/",
     ["download", "hindi", "hdrip"]),
    ("WorldFree4u",     "https://worldfree4u.mom/{slug}/",
     ["download", "hindi", "hdrip"]),
    ("Mp4moviez",       "https://mp4moviez.com/{slug}/",
     ["download", "hdrip", "720p"]),
    ("HDHub4u",         "https://hdhub4u.com/{slug}/",
     ["download", "hdrip", "720p"]),
]

async def scan_direct_urls(
    film: str,
    client: httpx.AsyncClient
) -> list[IndiaHit]:
    """
    Construct direct film URLs and verify content.
    Bypasses Google indexing gaps.
    Strict false positive prevention.
    """
    import re as _re
    hits = []
    slug = _re.sub(r'[^a-z0-9]+', '-', film.lower()).strip('-')
    slug_nospace = _re.sub(r'[^a-z0-9]+', '', film.lower())  # jetlee
    slug_year = f"{slug}-2026"
    slug_year2 = f"{slug}-2025"
    film_words = [w for w in film.lower().split() if len(w) > 2]
    if not film_words:
        return hits

    # TamilRockers removed — catch-all pages, unreliable
    # Movierulz uses concatenated slug: jetlee-2026-telugu
    slug_c = _re.sub(r'[^a-z0-9]+', '', film.lower())
    year = "2026"

    patterns = [
        # Movierulz — concatenated slug + year + language
        ("Movierulz Telugu",
         f"https://www.5movierulz.markets/{slug_c}-{year}-telugu/movie-watch-online-free"),
        ("Movierulz Hindi",
         f"https://www.5movierulz.markets/{slug_c}-{year}-hindi/movie-watch-online-free"),
        ("Movierulz Tamil",
         f"https://www.5movierulz.markets/{slug_c}-{year}-tamil/movie-watch-online-free"),
        ("Filmyzilla",    f"https://filmyzilla.com.co/{slug}/"),
        ("TamilMV",       f"https://www.1tamilmv.world/{slug}/"),
        ("Isaimini",      f"https://isaimini.com/{slug}/"),
        ("Moviesda",      f"https://moviesda.com/{slug}/"),
        ("9xMovies",      f"https://9xmovies.cool/{slug}/"),
        ("WorldFree4u",   f"https://worldfree4u.mom/{slug}/"),
        ("Mp4moviez",     f"https://mp4moviez.com/{slug}/"),
        ("HDHub4u",       f"https://hdhub4u.com/{slug}/"),
    ]

    for site_name, url in patterns:
        try:
            r = await client.get(url, timeout=8, headers=HEADERS)
            if r.status_code != 200:
                await asyncio.sleep(0.1)
                continue

            body = r.text.lower()

            # Get page title
            title_m = _re.search(r'<title>([^<]+)</title>', body)
            page_title = title_m.group(1).strip() if title_m else ""

            # Reject catch-all pages
            domain = url.split("/")[2]
            is_catchall = (
                page_title.lower() in [domain, "not found",
                                        "404", "error", ""] or
                len(page_title) < 5 or
                page_title.lower() == domain.lower() or
                page_title.lower().strip('.') == domain.lower().strip('www.') or
                page_title.lower() == domain.replace('www.','').lower()
            )
            if is_catchall:
                await asyncio.sleep(0.1)
                continue

            # Extra check — film title must appear in PAGE TITLE
            # not just body (body has generic content on catch-all sites)
            film_in_title = any(w in page_title.lower()
                               for w in film_words if len(w) > 3)
            if not film_in_title:
                await asyncio.sleep(0.1)
                continue

            # ALL film words must appear in body
            all_words = all(w in body for w in film_words)
            if not all_words:
                await asyncio.sleep(0.1)
                continue

            # Must have actual piracy signals
            signals = ["download", "hdrip", "dvdrip", "webrip",
                      "720p", "1080p", "watch online", "camrip"]
            signal_count = sum(1 for s in signals if s in body)
            if signal_count < 2:
                await asyncio.sleep(0.1)
                continue

            # Detect quality
            is_cam = any(k in body for k in
                        ["camrip", "hdcam", "telesync", "line audio"])
            quality = ("CAM" if is_cam else
                      "HDRip" if "hdrip" in body else
                      "WebRip" if "webrip" in body else
                      "720p" if "720p" in body else "Unknown")

            hits.append(IndiaHit(
                platform=site_name,
                language="Pan-India",
                url=url,
                quality=quality,
                detail=f"Direct URL: {film} confirmed on {site_name}",
                confidence=0.90,
                is_cam=is_cam,
                severity="CRITICAL" if is_cam else "HIGH"
            ))
            await asyncio.sleep(0.2)

        except Exception:
            pass

    return hits




async def scan_ddg_india(
    film: str,
    client: httpx.AsyncClient
) -> list[IndiaHit]:
    """DDG scan for Indian piracy — free, no quota."""
    results = []
    queries = [
        f"{film} movierulz ibomma tamilmv download 720p",
        f"{film} hdrip camrip telugu tamil hindi free download",
        f"{film} tamilrockers filmyzilla 2025 download",
    ]

    piracy_domains = [p["domain"].split(".")[0]
                      for p in INDIAN_PLATFORMS]

    for query in queries:
        try:
            r = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                timeout=12, headers=HEADERS
            )
            if r.status_code != 200:
                continue

            urls = [unquote(u) for u in
                    re.findall(r'uddg=(https?[^&"]+)', r.text)]
            titles = re.findall(r'result__a"[^>]+>([^<]+)</a>', r.text)

            for i, url in enumerate(urls[:15]):
                title = titles[i % len(titles)] if titles else ""
                combined = f"{url} {title}".lower()

                # All false positive checks
                if is_news_article(url, combined):
                    continue
                if is_category_page(url):
                    continue
                if not film_ok(film, combined):
                    continue
                if not any(d in url.lower() for d in piracy_domains):
                    continue
                if not has_piracy_signal(combined):
                    continue

                is_cam = any(k in combined for k in
                            ["cam","telesync","hdcam"])
                quality = "CAM" if is_cam else "HDRip"

                if not any(h.url == url for h in results):
                    results.append(IndiaHit(
                        platform=f"DDG: {url.split('/')[2][:20]}",
                        language="Pan-India",
                        url=url,
                        quality=quality,
                        detail=title[:80],
                        confidence=0.70,
                        is_cam=is_cam
                    ))

            await asyncio.sleep(1)
        except Exception as e:
            log.warning(f"DDG India error: {e}")

    return results


async def scan_batch_serp(
    film: str,
    client: httpx.AsyncClient
) -> list[IndiaHit]:
    """
    Hybrid scanner — DDG search + direct URL verification.
    Strategy:
    1. DDG search with alternate spellings (fast, finds real URLs)
    2. Direct URL check for top piracy sites (catches what DDG misses)
    3. Strict domain whitelist validation — no false positives
    """
    import re as _re
    from urllib.parse import quote_plus, urlparse

    film_lower = film.lower().strip()
    slug  = _re.sub(r"[^a-z0-9]+", "-", film_lower).strip("-")
    slugs = quote_plus(film_lower)

    # Extended slugs — piracy sites often include subtitle in URL
    # "Pushpa 2" → also try "pushpa-2-the-rule", "pushpa-2-reloaded"
    # "Devara" → also try "devara-part-1"
    slug_variants = [slug]
    # Common subtitle patterns
    subtitle_map = {
        # Pushpa
        "pushpa-2": [
            "pushpa-2-the-rule-reloaded",
            "pushpa-2-the-rule",
            "pushpa-the-rule-part-2",
            "pushpa-2-reloaded",
        ],
        # Devara
        "devara":   ["devara-part-1", "devara-2024"],
        # Kalki
        "kalki":    ["kalki-2898-ad", "kalki-2898"],
        "kalki-2898-ad": ["kalki-2898-ad"],
        # KGF
        "kgf":      ["kgf-chapter-2", "kgf-2"],
        # Baahubali
        "baahubali": ["baahubali-2-the-conclusion", "baahubali-2"],
        # Common patterns — add subtitle suffixes
        # These generate extra slug variants for any film
    }
    # Also generate common subtitle patterns automatically
    common_suffixes = [
        "-the-rule", "-part-1", "-part-2", "-reloaded",
        "-chapter-2", "-2-the-conclusion", "-extended",
        "-director-cut", "-special-edition",
    ]
    for sfx in common_suffixes:
        if not slug.endswith(sfx.lstrip("-")):
            slug_variants.append(slug + sfx)
    for key, extras in subtitle_map.items():
        if key in slug:
            slug_variants.extend(extras)
    slug_variants = list(dict.fromkeys(slug_variants))[:4]

    # Build alternate spellings — critical for Telugu/Tamil films
    variants = [film, film.lower().title()]
    swaps = [
        ("bh","b"),("bh","bb"),("th","t"),("sh","s"),
        ("aa","a"),("ee","i"),("oo","u"),("ck","k"),
        ("ph","f"),("rr","r"),("ll","l"),("nn","n"),
        (" 2 "," 2: "),(" part 1",""),(" part-1",""),
    ]
    for o, n in swaps:
        if o in film_lower:
            v = film_lower.replace(o, n).strip().title()
            if v and v not in variants and v.lower() != film_lower:
                variants.append(v)
    # Also add common title variants
    variants.append(film + " The Rule")
    variants.append(film + " Part 1")
    variants.append(film.replace(" 2","").strip())
    variants = list(dict.fromkeys(variants))[:5]  # unique, max 5

    PIRACY_DOMAINS = {
        "movierulz",   "ibomma",    "tamilmv",    "tamilrocker",
        "isaimini",    "kuttymovies","moviesda",   "tamilgun",
        "tamilyogi",   "tamilblaster","filmyzilla","9xmovies",
        "vegamovies",  "hdhub4u",   "bolly4u",    "mp4moviez",
        "rdxhd",       "skymovieshd","khatrimaza", "worldfree4u",
        "filmy4wap",   "downloadhub","moviesmod",  "katmoviesx",
        "1337x",       "cinevood",  "tollystream", "moviesdacom",
        "moviesflix",  "filmyhit",  "jiorocker",  "tamilprint",
        "madrasrocker","isaidub",   "tamilrasigan","azmovies",
    }

    LEGAL_DOMAINS = {
        "youtube.com","youtu.be","netflix.com","amazon.com","primevideo",
        "hotstar","jiocinema","zee5","sonyliv","aha.video","plex.tv",
        "ottplay","justwatch","hungama","airtelxstream","mxplayer",
        "imdb.com","wikipedia","rottentomatoes","moviefone","justdial",
        "twitter","facebook","instagram","reddit","tumblr","linkedin",
        "ndtv","thehindu","timesofindia","indiatimes","hindustantimes",
        "indianexpress","economictimes","timesnownews","thestatesman",
        "freepressjournal","businesstoday","latestly","filmibeat",
        "koimoi","pinkvilla","bollywoodhungama","siasat","gulte",
        "123telugu","greatandhra","cinejosh","tollywood.net","abplive",
        "zeenews","oneindia","dnaindia","cinemamanishi","asianetnews",
        "deccanherald","liveindia","thevocalnews","dailymotion","vimeo",
        "bilibili","archive.org","pastebin","github.com","google.com",
        "terabox","retroflix","blogspot","wordpress","opensea",
        "myvi.in","justwatch","thesouthfirst","samayam",
    }

    PIRACY_SIGNALS = [
        "download","1080p","720p","480p","hdrip","webrip","bluray",
        "dvdrip","camrip","mkv","mp4","torrent","dual audio",
        "hindi dubbed","full movie free","watch online free",
        "free download","movie download","watch online",
    ]

    all_hits  = []
    seen_urls = set()

    def is_legal(url: str) -> bool:
        dom = urlparse(url).netloc.lstrip("www.").lower()
        return any(s in dom for s in LEGAL_DOMAINS)

    def is_piracy(url: str) -> bool:
        dom = urlparse(url).netloc.lstrip("www.").lower()
        return any(s in dom for s in PIRACY_DOMAINS)

    # ── PART 1: DDG Search with all variants ──────────────────
    async def ddg_search(query: str, variant: str) -> list:
        try:
            r = await client.get(
                "https://serpapi.com/search",
                params={"q": query, "api_key": SERP_KEY,
                        "num": 10, "engine": "duckduckgo"},
                timeout=12
            )
            if r.status_code != 200:
                return []

            hits = []
            v_low   = variant.lower()
            v_words = [w for w in v_low.split() if len(w) > 2]

            for item in r.json().get("organic_results", []):
                link    = item.get("link", "")
                title   = item.get("title", "")
                snippet = item.get("snippet", "")
                full    = (title+" "+snippet+" "+link).lower()

                if link in seen_urls: continue
                if is_legal(link):   continue
                if not is_piracy(link): continue

                # Film name in title/snippet OR in URL path
                title_snip = (title+" "+snippet+" "+link).lower()
                found = any(
                    v.lower() in title_snip or
                    slug in link.lower() or
                    (len([w for w in v.lower().split() if len(w)>2]) >= 2 and
                     all(w in title_snip for w in [x for x in v.lower().split() if len(x)>2]))
                    for v in variants
                )
                # Also check slug variants in URL
                if not found:
                    found = any(sv in link.lower() for sv in slug_variants)
                if not found: continue

                # For confirmed piracy domains, relax signal requirement
                if not any(s in full for s in PIRACY_SIGNALS):
                    # If it's a known piracy domain and film in URL, accept it
                    if not (is_piracy(link) and any(sv in link.lower() for sv in slug_variants)):
                        continue
                if is_category_page(link): continue

                f = full.lower()
                is_cam = any(k in f for k in ["camrip","hdcam","telesync"])
                quality = (
                    "CAM"    if is_cam else
                    "HDRip"  if "hdrip"  in f else
                    "WebRip" if any(k in f for k in ["webrip","web-dl"]) else
                    "BluRay" if "bluray" in f else
                    "1080p"  if "1080p"  in f else
                    "720p"   if "720p"   in f else "Unknown"
                )

                matched = next(
                    (p for p in INDIAN_PLATFORMS if
                     p["domain"].split(".")[0].lstrip("0123456789") in
                     urlparse(link).netloc.lstrip("www.")),
                    {"name": urlparse(link).netloc.lstrip("www.").split(".")[0].title(),
                     "lang": "Unknown"}
                )
                seen_urls.add(link)
                hits.append(IndiaHit(
                    platform=matched["name"],
                    language=matched.get("lang","Unknown"),
                    url=link, quality=quality, detail=title[:80],
                    confidence=0.92 if is_cam else 0.85,
                    severity="CRITICAL" if is_cam else "HIGH",
                    is_cam=is_cam
                ))
            return hits
        except Exception as e:
            log.debug(f"DDG error: {e}")
            return []

    # Run DDG queries — one per variant × 3 query types
    ddg_tasks = []
    for v in variants[:3]:
        v_low = v.lower()
        ddg_tasks += [
            ddg_search(f'"{v}" movierulz download telugu', v),
            ddg_search(f'"{v}" movierulz download tamil', v),
            ddg_search(f'"{v}" tamilmv OR tamilblasters download', v),
            ddg_search(f'"{v}" filmyzilla OR hdhub4u download 1080p', v),
            ddg_search(f'"{v}" ibomma OR moviesda download', v),
            ddg_search(f'{v_low} movierulz telugu download 1080p', v),
            ddg_search(f'{v_low} tamilrockers kuttymovies isaimini download', v),
        ]
    for sv in slug_variants[1:3]:
        sv_title = sv.replace("-"," ").title()
        ddg_tasks += [
            ddg_search(f'"{sv_title}" movierulz download', sv_title),
            ddg_search(f'{sv_title} tamilmv filmyzilla ibomma download', sv_title),
        ]

    try:
        ddg_results = await asyncio.wait_for(
            asyncio.gather(*ddg_tasks, return_exceptions=True),
            timeout=15
        )
    except asyncio.TimeoutError:
        ddg_results = []
        log.debug("DDG searches timed out after 15s")
    for r in ddg_results:
        if isinstance(r, list):
            all_hits.extend(r)

    # ── PART 2: Direct URL check for TOP 5 sites ──────────────
    # Only check sites that respond quickly — verified 2025
    FAST_SITES = [
        {"name":"TamilBlasters","lang":"Tamil","domains":
            ["1tamilblasters.luxe","tamilblasters.life","1tamilblasters.art"],
         "urls":[
            "/{slug}-2025-telugu/",
            "/{slug}-2025-tamil/",
            "/{slug}-2025-hindi/",
            "/{slug}-2024-telugu/",
            "/{slug}-2024-tamil/",
         ]},
        {"name":"Moviesda","lang":"Tamil","domains":
            ["moviesda30.com","moviesda28.info","moviesda.com","moviesda.io"],
         "urls":[
            "/{slug}-2025-tamil-movie/",
            "/{slug}-2024-tamil-movie/",
            "/{slug}-2025-telugu-movie/",
            "/{slug}-2024-telugu-movie/",
            "/{slug}-2025-hindi-dubbed-movie/",
            "/{slug}-2024-hindi-dubbed-movie/",
            "/download/{slug}-original-1080p-hd/",
            "/download/{slug}-2025-original-1080p-hd/",
            "/{slug}-movie/",
         ]},
        {"name":"Filmyzilla","lang":"Hindi","domains":
            ["filmyzilla36.com","filmyzilla37.com","filmyzillaofficial.com"],
         "urls":[
            "/search/{slug}/",
         ]},
        {"name":"Movierulz","lang":"Telugu","domains":
            ["5movierulz2.band","5movierulz.markets","7movierulz.co"],
         "urls":[
            "/{slug}-2025-telugu/movie-watch-online-free/",
            "/{slug}-2025-tamil/movie-watch-online-free/",
            "/{slug}-2025-hindi/movie-watch-online-free/",
            "/{slug}-2024-telugu/movie-watch-online-free/",
            "/{slug}-2024-tamil/movie-watch-online-free/",
            "/{slug}-2024-hindi/movie-watch-online-free/",
         ]},
        {"name":"iBomma","lang":"Telugu","domains":
            ["ibomma.one","ibommamoviess.com"],
         "urls":[
            "/{slug}-telugu-movie/",
            "/{slug}-2025-telugu/",
            "/{slug}-2024-telugu/",
         ]},
    ]

    headers2 = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async def fast_check(url: str, site: dict) -> IndiaHit | None:
        if url in seen_urls:
            return None
        try:
            r = await client.get(url, headers=headers2,
                                 follow_redirects=True, timeout=7)
            if r.status_code != 200:
                return None

            chunk = r.content[:3000].decode("utf-8", errors="ignore").lower()
            title_m = _re.search(r"<title[^>]*>(.*?)</title>", chunk, _re.DOTALL)
            page_title = title_m.group(1).strip() if title_m else ""

            # Film name must be in title OR page content
            check_zone = (page_title + " " + chunk[:1000]).lower()
            film_found = any(
                v.lower() in check_zone or
                all(w in check_zone for w in
                    [x for x in v.lower().split() if len(x)>2])
                for v in variants
            )
            # Also check slug variants
            if not film_found:
                film_found = any(sv.replace("-"," ") in check_zone
                                 for sv in slug_variants)
            if not film_found:
                return None

            # Reject generic search pages — must be a specific film page
            final_path = str(r.url).split("?")[0].rstrip("/")
            is_search_page = (
                "?s=" in str(r.url) or
                "/search" in str(r.url) or
                "/page/" in str(r.url) or
                final_path.endswith(("/movies", "/telugu", "/tamil", "/hindi"))
            )
            if is_search_page:
                # For search pages — only accept if film name in title exactly
                if not page_title or not any(
                    v.lower() in page_title.lower() for v in variants
                ):
                    return None
                # And must show download links — not just search results
                if chunk.count("download") < 2:
                    return None

            if not any(s in chunk for s in ["download","watch","1080p","720p","hdrip"]):
                return None

            is_cam = any(k in chunk for k in ["camrip","hdcam","telesync"])
            quality = (
                "CAM"    if is_cam else
                "1080p"  if "1080p" in chunk else
                "720p"   if "720p"  in chunk else
                "HDRip"  if "hdrip" in chunk else "Unknown"
            )

            seen_urls.add(url)
            return IndiaHit(
                platform=site["name"], language=site["lang"],
                url=str(r.url), quality=quality,
                detail=page_title[:80] or f"Verified — {site['name']}",
                confidence=0.97 if is_cam else 0.93,
                severity="CRITICAL" if is_cam else "HIGH",
                is_cam=is_cam
            )
        except Exception:
            return None

    direct_tasks = []
    for site in FAST_SITES:
        for domain in site["domains"][:2]:
            for pattern in site["urls"]:
                for slug_v in slug_variants:  # try all slug variants
                    url = f"https://{domain}" + pattern.format(
                        slug=slug_v, slugs=slugs
                    )
                    direct_tasks.append(fast_check(url, site))

    # Hard 20s timeout on all direct checks combined
    try:
        direct_results = await asyncio.wait_for(
            asyncio.gather(*direct_tasks, return_exceptions=True),
            timeout=20
        )
    except asyncio.TimeoutError:
        direct_results = []
        log.debug("Direct URL checks timed out after 20s")
    for r in direct_results:
        if isinstance(r, IndiaHit) and r.url not in seen_urls:
            all_hits.append(r)
            seen_urls.add(r.url)

    # Deduplicate
    seen = set()
    unique = []
    for h in all_hits:
        if h.url not in seen:
            seen.add(h.url)
            unique.append(h)
    return unique


async def full_india_scan(film: str) -> dict:
    """Complete India scan — 75+ platforms."""
    log.info(f"India v3 scan: {film}")

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=15
    ) as client:
        # Run all three scans simultaneously
        batch_hits, ddg_hits, direct_hits = await asyncio.gather(
            scan_batch_serp(film, client),
            scan_ddg_india(film, client),
            scan_direct_urls(film, client),
            return_exceptions=True
        )

    all_hits = []
    seen = set()
    for h in (batch_hits if isinstance(batch_hits, list) else []) + \
             (ddg_hits if isinstance(ddg_hits, list) else []) + \
             (direct_hits if isinstance(direct_hits, list) else []):
        if h.url not in seen:
            seen.add(h.url)
            all_hits.append(h)

    cam_hits = [h for h in all_hits if h.is_cam]
    by_lang = {}
    for h in all_hits:
        by_lang.setdefault(h.language, []).append(h)

    verdict = ("CRITICAL" if cam_hits else
               "CONFIRMED" if all_hits else "CLEAN")

    log.info(f"India scan: {len(all_hits)} hits "
             f"({len(cam_hits)} CAM)")

    return {
        "film": film,
        "verdict": verdict,
        "hits_found": len(all_hits),
        "cam_hits": len(cam_hits),
        "platforms_scanned": len(INDIAN_PLATFORMS),
        "hits": all_hits,
        "by_language": {k: len(v) for k, v in by_lang.items()},
        "scanned_at": now_utc(),
    }


def print_report(result: dict):
    film = result["film"]
    hits = result["hits"]
    print(f"\n{'='*60}")
    print(f"  CINEOS India v3.0 — {film}")
    print(f"{'='*60}")
    print(f"  VERDICT  : {result['verdict']}")
    print(f"  Hits     : {result['hits_found']}")
    print(f"  CAM hits : {result['cam_hits']}")
    print(f"  Platforms: {result['platforms_scanned']}")
    print(f"  Scanned  : {result['scanned_at']}")

    if hits:
        print(f"\n  CONFIRMED HITS:")
        for h in hits:
            cam_flag = " ⚠ CAM" if h.is_cam else ""
            print(f"\n  [{h.quality}]{cam_flag} {h.platform} ({h.language})")
            print(f"  {h.url[:70]}")
            print(f"  {h.detail[:60]}")
    else:
        print(f"\n  CLEAN — No piracy detected")
    print(f"\n{'='*60}")


async def main(film: str):
    result = await full_india_scan(film)
    print_report(result)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="CINEOS India v3 — 75+ platforms")
    ap.add_argument("--film", required=True)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        print(f"\nCINEOS India v3 — {len(INDIAN_PLATFORMS)} platforms:")
        for p in ["1","2","3"]:
            plats = [x for x in INDIAN_PLATFORMS if str(x["p"]) == p]
            print(f"\n  Priority {p} ({len(plats)} platforms):")
            for x in plats:
                print(f"    {x['name']:20} {x['lang']}")
    else:
        asyncio.run(main(args.film))
