"""
CINEOS India Scanner v4 — Enterprise Grade
Multi-engine, multi-strategy, maximum detection
"""
import asyncio, httpx, re, os, itertools
from datetime import datetime
from urllib.parse import quote, urlparse

SERP_KEY = os.environ.get("SERP_API_KEY","")
API = "https://cinerisk-api-production.up.railway.app"

# ── INDIA PIRACY PLATFORMS ────────────────────────────────
INDIA_SITES = [
    # Tamil
    "tamilblasters","tamilmv","tamilrockers","isaimini",
    "kuttymovies","moviesda","tamilyogi","tamilgun",
    "madrasrockers","cinemavilla","tamilplay","1tamilmv",
    # Telugu  
    "ibomma","movierulz","iBomma","teluguwap","telugumovies",
    "afilmywap","tollywood","telugupalaka","moviezwap",
    # Hindi
    "filmyzilla","filmywap","9xmovies","bolly4u","filmix",
    "hdmovies","moviesflix","vegamovies","skymovieshd",
    "hdhub4u","rdxhd","khatrimaza","123mkv","mp4moviez",
    # Multi
    "moviesda","movierulz","5movierulz","7movierulz",
    "jalshamoviez","worldfree4u","downloadhub",
    "mkvcage","1337x","torrentking","tamilrockers",
]

# ── QUALITY SIGNALS ───────────────────────────────────────
CAM_SIGNALS = ["cam","camrip","hdcam","tc","telecine",
               "line audio","theater","audience"]
HD_SIGNALS = ["hdrip","webrip","web-dl","bluray","1080p",
              "720p","4k","hevc","x264","x265"]
LEAK_SIGNALS = ["leaked","full movie","watch online","free download",
                "download","direct link"]

class IndiaHit:
    def __init__(self, url, platform, quality, language, source):
        self.url = url
        self.platform = platform
        self.quality = quality
        self.language = language
        self.source = source
    def __repr__(self):
        return f"Hit({self.platform} | {self.quality} | {self.language})"

def detect_quality(text):
    text = text.lower()
    for s in CAM_SIGNALS:
        if s in text: return "CAM"
    for s in HD_SIGNALS:
        if s in text: return "HDRip"
    if any(s in text for s in LEAK_SIGNALS):
        return "Leak"
    return "Unknown"

def detect_language(text, url=""):
    combined = (text + url).lower()
    if any(w in combined for w in ["telugu","teluguwap","ibomma","tollywood","అ","తె"]):
        return "Telugu"
    if any(w in combined for w in ["tamil","tamilmv","isaimini","kuttymovies","த","மு"]):
        return "Tamil"
    if any(w in combined for w in ["hindi","bollywood","filmyzilla","filmywap","हि"]):
        return "Hindi"
    if any(w in combined for w in ["malayalam","cinemavilla","kerala","മ"]):
        return "Malayalam"
    if any(w in combined for w in ["kannada","kgf","sandalwood","ಕ"]):
        return "Kannada"
    return "Multi"

def is_piracy_url(url, title):
    url_lower = url.lower()
    title_words = [w.lower() for w in title.split() if len(w) > 2]
    # Must match title
    title_match = any(w in url_lower for w in title_words)
    # Must be on piracy site
    site_match = any(s in url_lower for s in INDIA_SITES)
    return title_match and site_match

async def search_serpapi(client, query, engine="google"):
    """Search via SerpApi."""
    try:
        r = await client.get("https://serpapi.com/search", params={
            "q": query,
            "api_key": SERP_KEY,
            "num": 10,
            "engine": engine,
            "gl": "in",  # India results
            "hl": "en",
        }, timeout=10)
        return r.json().get("organic_results", [])
    except:
        return []

async def search_ddg(client, query):
    """Search DuckDuckGo via SerpApi."""
    try:
        r = await client.get("https://serpapi.com/search", params={
            "q": query,
            "api_key": SERP_KEY,
            "num": 10,
            "engine": "duckduckgo",
        }, timeout=10)
        return r.json().get("organic_results", [])
    except:
        return []

async def check_direct_url(client, url, title):
    """Check if a direct URL is live and contains the film."""
    try:
        r = await client.get(url, timeout=6,
            headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            follow_redirects=True)
        if r.status_code == 200:
            text = r.text[:3000].lower()
            title_words = [w.lower() for w in title.split() if len(w) > 2]
            if any(w in text for w in title_words):
                return str(r.url)
    except:
        pass
    return None

def build_direct_urls(title, site_base, year=None):
    """Build direct URL patterns for a title on a site."""
    slug = title.lower().strip()
    slug = re.sub(r'[^a-z0-9\s]', '', slug)
    slug = re.sub(r'\s+', '-', slug).strip('-')
    
    years = [str(year)] if year else ["2025","2026","2024"]
    languages = ["telugu","tamil","hindi","malayalam","kannada",""]
    
    urls = []
    for y in years:
        for lang in languages:
            parts = [slug]
            if y: parts.append(y)
            if lang: parts.append(lang)
            path = "-".join(p for p in parts if p)
            urls.append(f"https://{site_base}/{path}/")
            urls.append(f"https://{site_base}/{path}-movie/")
            urls.append(f"https://www.{site_base}/{path}/")
    return urls[:8]  # limit per site

async def full_india_scan_v4(title: str) -> dict:
    """
    Enterprise-grade India piracy scan.
    Multi-engine, multi-strategy, maximum coverage.
    """
    print(f"[CINEOS-v4] Scanning: {title}")
    start = datetime.now()
    
    hits = []
    seen_urls = set()
    
    async with httpx.AsyncClient(
        timeout=12,
        headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        follow_redirects=True
    ) as client:
        
        # ── STRATEGY 1: Google search with site operators ──
        # Most powerful — Google indexes piracy sites
        google_queries = [
            f'"{title}" site:tamilblasters.life OR site:tamilmv.world OR site:1tamilmv.world download',
            f'"{title}" site:movierulz.com OR site:5movierulz.com OR site:movierulzon.com',
            f'"{title}" site:filmyzilla.com OR site:filmywap.com OR site:9xmovies.ltd download',
            f'"{title}" site:ibomma.com OR site:ibomma.one OR site:ibommamoviess.com telugu',
            f'"{title}" site:isaimini.com OR site:moviesda.com OR site:kuttymovies.com tamil',
            f'"{title}" filetype:mkv OR filetype:mp4 download 1080p india free',
            f'"{title}" 2025 download telugu tamil hindi hdrip webrip',
            f'"{title}" tamilblasters movierulz ibomma filmyzilla download free',
            f'"{title}" full movie download free 1080p 720p',
            f'"{title}" leaked online watch free hdrip webrip',
        ]
        
        # ── STRATEGY 2: DDG searches ──
        ddg_queries = [
            f'"{title}" tamilmv tamilblasters download telugu tamil',
            f'"{title}" movierulz ibomma filmyzilla download free',
            f'"{title}" 1080p 720p download mkv mp4 free',
            f'"{title}" CAM copy leaked online watch',
        ]
        
        # ── STRATEGY 3: Direct URL construction ──
        # Check known URL patterns on top piracy sites
        direct_sites = [
            "1tamilblasters.luxe",
            "tamilblasters.life", 
            "www.1tamilmv.world",
            "moviesda.com",
            "ibomma.one",
            "5movierulz.markets",
            "filmyzilla.com.co",
        ]
        
        # Run all searches concurrently
        tasks = []
        
        # Google searches (use 5 to preserve quota)
        for q in google_queries[:5]:
            tasks.append(search_serpapi(client, q, "google"))
        
        # Bing searches — finds different results than Google
        bing_queries = [
            f'"{title}" tamilblasters movierulz download telugu tamil hindi',
            f'"{title}" filmyzilla ibomma 1080p 720p free download',
        ]
        for q in bing_queries:
            tasks.append(search_serpapi(client, q, "bing"))
        
        # DDG searches
        for q in ddg_queries:
            tasks.append(search_ddg(client, q))
        
        # Direct URL checks
        direct_urls = []
        for site in direct_sites:
            direct_urls.extend(build_direct_urls(title, site))
        
        for url in direct_urls[:30]:
            tasks.append(check_direct_url(client, url, title))
        
        print(f"[CINEOS-v4] Running {len(tasks)} parallel checks...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process search results
        for result in results:
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, dict):
                        url = item.get("link","")
                        snippet = item.get("snippet","")
                        item_title = item.get("title","")
                        combined = f"{url} {snippet} {item_title}"
                        
                        if not url or url in seen_urls:
                            continue
                        
                        domain = urlparse(url).netloc.lower()
                        
                        # Check if it's a piracy site
                        is_piracy = any(s in domain for s in INDIA_SITES)
                        
                        # Check if title matches — require at least 2 words or 1 unique word
                        title_words = [w.lower() for w in title.split() if len(w) > 2]
                        matched = sum(1 for w in title_words if w in combined.lower())
                        title_match = matched >= min(2, len(title_words))
                        
                        path = urlparse(url).path.strip("/")
                        # Exclude homepages and category pages
                        is_specific = len(path) > 5 and any(
                            w.lower() in path.lower() 
                            for w in title.split() if len(w) > 2
                        )
                        if is_piracy and title_match and is_specific:
                            seen_urls.add(url)
                            quality = detect_quality(combined)
                            language = detect_language(combined, url)
                            platform = domain.replace("www.","").split(".")[0].title()
                            hits.append(IndiaHit(url, platform, quality, language, "search"))
            
            elif isinstance(result, str) and result:
                # Direct URL hit — must contain title in URL path
                if result not in seen_urls:
                    path = urlparse(result).path.lower()
                    title_words = [w.lower() for w in title.split() if len(w) > 2]
                    if any(w in path for w in title_words):
                        seen_urls.add(result)
                        domain = urlparse(result).netloc.lower()
                        platform = domain.replace("www.","").split(".")[0].title()
                        quality = detect_quality(path)
                        language = detect_language("", result)
                        hits.append(IndiaHit(result, platform, quality, language, "direct"))
        
        # ── STRATEGY 4: Verify top hits are live ──
        # Re-check top 10 hits to confirm they're accessible
        if hits:
            verify_tasks = []
            for hit in hits[:10]:
                verify_tasks.append(check_direct_url(client, hit.url, title))
            verified = await asyncio.gather(*verify_tasks, return_exceptions=True)
            
            confirmed = []
            for i, v in enumerate(verified):
                if i < len(hits):
                    if v or hits[i].source == "search":
                        confirmed.append(hits[i])
            hits = confirmed if confirmed else hits
    
    elapsed = (datetime.now() - start).total_seconds()
    
    # Determine verdict
    cam_hits = [h for h in hits if h.quality == "CAM"]
    if cam_hits:
        verdict = f"CRITICAL — CAM copy confirmed on {len(cam_hits)} platform(s)"
    elif len(hits) >= 5:
        verdict = f"HIGH — Confirmed on {len(hits)} piracy platforms"
    elif len(hits) > 0:
        verdict = f"CONFIRMED — Found on {len(hits)} platform(s)"
    else:
        verdict = "CLEAN — No piracy detected"
    
    print(f"[CINEOS-v4] Done: {len(hits)} hits in {elapsed:.1f}s")
    
    return {
        "title": title,
        "verdict": verdict,
        "hits_found": len(hits),
        "cam_hits": len(cam_hits),
        "hits": hits,
        "scan_time": round(elapsed, 2),
        "strategies_used": ["google_search","ddg_search","direct_url"],
        "queries_run": len(tasks),
    }

async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", required=True)
    args = ap.parse_args()
    
    result = await full_india_scan_v4(args.film)
    
    print(f"\n{'='*65}")
    print(f"  CINEOS v4 — {result['title']}")
    print(f"{'='*65}")
    print(f"  Verdict    : {result['verdict']}")
    print(f"  Hits       : {result['hits_found']}")
    print(f"  CAM copies : {result['cam_hits']}")
    print(f"  Scan time  : {result['scan_time']}s")
    print(f"  Queries run: {result['queries_run']}")
    print(f"\n  CONFIRMED PIRACY URLS:")
    for h in result['hits']:
        print(f"  [{h.quality:8}] [{h.language:8}] {h.url[:70]}")
    print(f"{'='*65}")

if __name__ == "__main__":
    asyncio.run(main())
