"""
CINEOS Layer 4 — Piracy Scanner v4
Plugin-based architecture — add new sources by adding a function to SCANNERS list
US Prov. Pat. 64/049,190
"""
import asyncio
import httpx
import os
import json
from datetime import datetime, timezone
from typing import Optional

SERP_API_KEY = os.getenv("SERP_API_KEY", "")
SCANNER_TIMEOUT = 8

# ─── KEYWORD ENGINE ───────────────────────────────────────────────────────────

CAM_KEYWORDS = [
    "cam", "hdcam", "camrip", "cam-rip",
    "ts", "telesync", "tele-sync",
    "telecine", "tc",
    "hc.cam", "hcam", "hc-cam",
    "webrip", "web-rip",         # sometimes pre-release
    "screener", "scr",           # screener leaks
    "r5", "r6",                  # region releases
    "pdvd",                      # pirated dvd
]

STREAMING_SIGNALS = [
    "watch online", "free download", "direct download",
    "google drive", "mega.nz", "1fichier",
    "480p", "720p", "1080p",
]

def find_keyword(text: str) -> str:
    t = text.lower()
    for kw in CAM_KEYWORDS:
        if kw in t:
            return kw
    return ""

def film_match(text: str, film: str) -> bool:
    t = text.lower()
    words = [w for w in film.lower().split() if len(w) > 2]
    return sum(1 for w in words if w in t) >= max(1, len(words) // 2)

# ─── SCANNER PLUGINS ─────────────────────────────────────────────────────────
# Each plugin is an async function(film, client) -> dict or list
# Return: {"source": str, "hit": bool, "url": str, ...}

async def scan_whereyouwatch(film: str, c: httpx.AsyncClient) -> dict:
    slug = film.lower().replace(" ", "-").replace(":", "").replace("'", "")
    url = f"https://whereyouwatch.com/movies/{slug}/"
    try:
        r = await c.get(url)
        if r.status_code == 200:
            body = r.text.lower()
            found = [k for k in ["cam", "telesync", "torrent", "download"] if k in body]
            if len(found) >= 2:
                return {"source": "whereyouwatch.com", "hit": True, "url": url, "signals": found}
    except: pass
    return {"source": "whereyouwatch.com", "hit": False}

async def scan_piratebay(film: str, c: httpx.AsyncClient) -> dict:
    try:
        r = await c.get("https://apibay.org/q.php", params={"q": f"{film} CAM", "cat": "0"})
        if r.status_code == 200:
            for item in r.json():
                name = item.get("name", "")
                kw = find_keyword(name)
                if kw and film_match(name, film):
                    return {"source": "thepiratebay.org", "hit": True,
                            "url": f"https://thepiratebay.org/description.php?id={item.get('id')}",
                            "title": name, "seeders": item.get("seeders"), "keyword": kw}
    except: pass
    return {"source": "thepiratebay.org", "hit": False}

async def scan_solidtorrents(film: str, c: httpx.AsyncClient) -> dict:
    try:
        r = await c.get("https://solidtorrents.to/api/v1/search",
                        params={"q": f"{film} CAM", "category": "video"})
        if r.status_code == 200:
            for item in r.json().get("results", []):
                title = item.get("title", "")
                kw = find_keyword(title)
                if kw and film_match(title, film):
                    return {"source": "solidtorrents.to", "hit": True,
                            "url": f"https://solidtorrents.to/view/{item.get('_id')}",
                            "title": title, "keyword": kw}
    except: pass
    return {"source": "solidtorrents.to", "hit": False}

async def scan_eztv(film: str, c: httpx.AsyncClient) -> dict:
    try:
        r = await c.get("https://eztv.re/api/get-torrents",
                        params={"limit": 20, "keywords": film})
        if r.status_code == 200:
            for item in r.json().get("torrents", []):
                title = item.get("title", "")
                kw = find_keyword(title)
                if kw and film_match(title, film):
                    return {"source": "eztv.re", "hit": True,
                            "url": item.get("torrent_url", ""),
                            "title": title, "keyword": kw}
    except: pass
    return {"source": "eztv.re", "hit": False}

async def scan_bitsearch(film: str, c: httpx.AsyncClient) -> dict:
    try:
        r = await c.get("https://bitsearch.to/search",
                        params={"q": f"{film} CAM", "category": "1"})
        if r.status_code == 200:
            body = r.text.lower()
            kw = find_keyword(body)
            if kw and film_match(body, film):
                return {"source": "bitsearch.to", "hit": True,
                        "url": f"https://bitsearch.to/search?q={film}+CAM", "keyword": kw}
    except: pass
    return {"source": "bitsearch.to", "hit": False}

async def scan_rarbg(film: str, c: httpx.AsyncClient) -> dict:
    try:
        r = await c.get("https://rarbggo.to/torrents.php",
                        params={"search": f"{film} CAM"})
        if r.status_code == 200:
            body = r.text.lower()
            kw = find_keyword(body)
            if kw and film_match(body, film):
                return {"source": "rarbg.mirror", "hit": True,
                        "url": f"https://rarbggo.to/torrents.php?search={film}+CAM", "keyword": kw}
    except: pass
    return {"source": "rarbg.mirror", "hit": False}

async def scan_glodls(film: str, c: httpx.AsyncClient) -> dict:
    try:
        r = await c.get("https://glodls.to/search_results.php",
                        params={"search": f"{film} CAM"})
        if r.status_code == 200:
            body = r.text.lower()
            kw = find_keyword(body)
            if kw and film_match(body, film):
                return {"source": "glodls.to", "hit": True,
                        "url": f"https://glodls.to/search_results.php?search={film}+CAM", "keyword": kw}
    except: pass
    return {"source": "glodls.to", "hit": False}

async def scan_limetorrents(film: str, c: httpx.AsyncClient) -> dict:
    try:
        slug = film.lower().replace(" ", "-")
        url = f"https://www.limetorrents.lol/search/all/{slug}-CAM/"
        r = await c.get(url)
        if r.status_code == 200:
            body = r.text.lower()
            kw = find_keyword(body)
            if kw and film_match(body, film):
                return {"source": "limetorrents.lol", "hit": True, "url": url, "keyword": kw}
    except: pass
    return {"source": "limetorrents.lol", "hit": False}

async def scan_torlock(film: str, c: httpx.AsyncClient) -> dict:
    try:
        slug = film.lower().replace(" ", "-")
        url = f"https://www.torlock.com/all/torrents/{slug}-cam.html"
        r = await c.get(url)
        if r.status_code == 200:
            body = r.text.lower()
            kw = find_keyword(body)
            if kw and film_match(body, film):
                return {"source": "torlock.com", "hit": True, "url": url, "keyword": kw}
    except: pass
    return {"source": "torlock.com", "hit": False}

async def scan_kickass(film: str, c: httpx.AsyncClient) -> dict:
    try:
        r = await c.get(f"https://kickasstorrents.to/usearch/{film.replace(' ', '%20')}%20CAM/")
        if r.status_code == 200:
            body = r.text.lower()
            kw = find_keyword(body)
            if kw and film_match(body, film):
                return {"source": "kickasstorrents.to", "hit": True,
                        "url": f"https://kickasstorrents.to/usearch/{film}+CAM/", "keyword": kw}
    except: pass
    return {"source": "kickasstorrents.to", "hit": False}

async def scan_reddit(film: str, c: httpx.AsyncClient) -> dict:
    try:
        r = await c.get("https://www.reddit.com/search.json",
                        params={"q": f"{film} CAM torrent", "sort": "new", "limit": 5},
                        headers={"User-Agent": "CINEOS-Scanner/1.0"})
        if r.status_code == 200:
            for post in r.json().get("data", {}).get("children", []):
                pd = post.get("data", {})
                title = pd.get("title", "")
                kw = find_keyword(title)
                if kw and film_match(title, film):
                    return {"source": "reddit.com", "hit": True,
                            "url": f"https://reddit.com{pd.get('permalink', '')}",
                            "title": title, "keyword": kw}
    except: pass
    return {"source": "reddit.com", "hit": False}

async def scan_telegram(film: str, c: httpx.AsyncClient) -> list:
    channels = [
        "CamRips", "moviehdfree", "hdmovies4u",
        "MoviesFlixPro", "piratebayofficial", "freemovies4utg"
    ]
    hits = []
    for ch in channels:
        try:
            r = await c.get(f"https://t.me/s/{ch}")
            if r.status_code == 200:
                body = r.text.lower()
                if film_match(body, film):
                    kw = find_keyword(body)
                    hits.append({
                        "source": f"telegram:t.me/{ch}",
                        "hit": True,
                        "url": f"https://t.me/s/{ch}",
                        "signal": "film_mentioned",
                        "keyword": kw or "mentioned"
                    })
        except: pass
    return hits

async def scan_streaming_sites(film: str, c: httpx.AsyncClient) -> list:
    sites = [
        ("720pstream.me", f"https://720pstream.me/?s={film.replace(' ', '+')}"),
        ("yesmovies.mn", f"https://yesmovies.mn/search/?q={film.replace(' ', '+')}"),
        ("lookmovie2.to", f"https://lookmovie2.to/movies/search/?q={film.replace(' ', '+')}"),
    ]
    hits = []
    for name, url in sites:
        try:
            r = await c.get(url)
            if r.status_code == 200:
                body = r.text.lower()
                if film_match(body, film):
                    hits.append({
                        "source": name,
                        "hit": True,
                        "url": url,
                        "signal": "film_available_on_streaming_site"
                    })
        except: pass
    return hits

async def scan_google_serp(film: str, c: httpx.AsyncClient) -> list:
    if not SERP_API_KEY:
        return []
    hits = []
    queries = [
        f'"{film}" CAM torrent download 2026',
        f'"{film}" HDCAM free download',
    ]
    PIRACY_DOMAINS = [
        "1337x", "rarbg", "yts", "eztv", "thepiratebay",
        "kickass", "torrentgalaxy", "nyaa", "rutracker"
    ]
    for query in queries:
        try:
            r = await c.get("https://serpapi.com/search",
                            params={"q": query, "api_key": SERP_API_KEY, "num": 10})
            for item in r.json().get("organic_results", []):
                link = item.get("link", "").lower()
                for domain in PIRACY_DOMAINS:
                    if domain in link:
                        hits.append({
                            "source": f"serp:{domain}",
                            "hit": True,
                            "url": item.get("link"),
                            "title": item.get("title"),
                            "query": query
                        })
                        break
        except: pass
    return hits

# ─── PLUGIN REGISTRY ─────────────────────────────────────────────────────────
# To add a new source: write scan_SOURCENAME(film, client) -> dict|list
# Then add it here. That's it.

SCANNERS = [
    # Torrent indexes
    scan_whereyouwatch,
    scan_piratebay,
    scan_solidtorrents,
    scan_eztv,
    scan_bitsearch,
    scan_rarbg,
    scan_glodls,
    scan_limetorrents,
    scan_torlock,
    scan_kickass,
    # Social / community
    scan_reddit,
    scan_telegram,
    # Streaming piracy sites
    scan_streaming_sites,
    # Paid API (optional)
    scan_google_serp,
]

# ─── MAIN SCAN ───────────────────────────────────────────────────────────────

async def full_scan(film_title: str) -> dict:
    print(f"[SCANNER] Starting full scan — {film_title} — {len(SCANNERS)} sources")
    start = datetime.now(timezone.utc)

    async with httpx.AsyncClient(
        timeout=SCANNER_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    ) as client:
        results_list = await asyncio.gather(
            *[s(film_title, client) for s in SCANNERS],
            return_exceptions=True
        )

    hits = []
    all_results = []

    for r in results_list:
        if isinstance(r, Exception):
            continue
        if isinstance(r, list):
            all_results.extend(r)
            hits.extend([x for x in r if x.get("hit")])
        elif isinstance(r, dict):
            all_results.append(r)
            if r.get("hit"):
                hits.append(r)

    duration = (datetime.now(timezone.utc) - start).total_seconds()

    summary = {
        "film": film_title,
        "scanned_at": start.isoformat(),
        "duration_seconds": round(duration, 2),
        "sources_checked": len(SCANNERS),
        "total_hits": len(hits),
        "hits": hits,
        "platforms": list(set(h.get("source") for h in hits)),
        "first_url": hits[0].get("url") if hits else "",
        "query": f"{film_title} CAM",
        "scan_method": "multi_source_v4_plugin"
    }

    print(f"[SCANNER] Done — {len(hits)} hits / {len(SCANNERS)} sources / {duration:.1f}s")
    return summary

if __name__ == "__main__":
    import sys
    film = sys.argv[1] if len(sys.argv) > 1 else "Sinners"
    result = asyncio.run(full_scan(film))
    print(json.dumps(result, indent=2))
