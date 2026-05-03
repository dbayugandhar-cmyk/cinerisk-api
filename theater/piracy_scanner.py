import asyncio
import httpx
import os
from datetime import datetime, timezone

SERP_API_KEY = os.getenv("SERP_API_KEY", "")

PIRACY_DOMAINS = [
    "1337x.to", "rarbg.to", "yts.mx", "eztv.re",
    "thepiratebay.org", "kickasstorrents.cr", "torrentgalaxy.to",
    "limetorrents.info", "torlock.com", "zooqle.com",
    "rutracker.org", "nyaa.si", "animebytes.tv"
]

PIRACY_KEYWORDS = [
    "CAM", "HDCAM", "TS", "TELESYNC", "TELECINE",
    "CAMRIP", "CAMRip", "HC.CAM", "HCAM"
]

async def check_whereyouwatch(film: str, client: httpx.AsyncClient) -> dict:
    slug = film.lower().replace(" ", "-").replace(":", "").replace("'", "")
    url = f"https://whereyouwatch.com/movies/{slug}/"
    try:
        r = await client.get(url, timeout=12, follow_redirects=True)
        if r.status_code == 200:
            body = r.text.lower()
            found = [k for k in ["cam", "telesync", "torrent", "download"] if k in body]
            if len(found) >= 2:
                return {"source": "whereyouwatch.com", "hit": True, "url": url, "signals": found}
    except Exception as e:
        print(f"[SCANNER] whereyouwatch error: {e}")
    return {"source": "whereyouwatch.com", "hit": False, "url": url}

async def check_google_serp(film: str, client: httpx.AsyncClient) -> list:
    if not SERP_API_KEY:
        return []
    results = []
    queries = [
        f'"{film}" CAM torrent download 2026',
        f'"{film}" HDCAM free download',
        f'"{film}" CAMRip 1080p torrent',
    ]
    for query in queries:
        try:
            r = await client.get(
                "https://serpapi.com/search",
                params={"q": query, "api_key": SERP_API_KEY, "num": 10, "engine": "google"},
                timeout=15
            )
            data = r.json()
            organic = data.get("organic_results", [])
            for item in organic:
                link = item.get("link", "").lower()
                title = item.get("title", "").lower()
                snippet = item.get("snippet", "").lower()
                for domain in PIRACY_DOMAINS:
                    if domain in link:
                        results.append({
                            "source": domain,
                            "hit": True,
                            "url": item.get("link"),
                            "title": item.get("title"),
                            "query": query
                        })
                        break
                for kw in [k.lower() for k in PIRACY_KEYWORDS]:
                    if kw in title or kw in snippet:
                        if not any(r["url"] == item.get("link") for r in results):
                            results.append({
                                "source": "google_serp",
                                "hit": True,
                                "url": item.get("link"),
                                "title": item.get("title"),
                                "keyword": kw,
                                "query": query
                            })
                        break
        except Exception as e:
            print(f"[SCANNER] SERP error for '{query}': {e}")
    return results

async def check_telegram_signals(film: str, client: httpx.AsyncClient) -> dict:
    slug = film.lower().replace(" ", "+").replace(":", "").replace("'", "")
    search_url = f"https://t.me/s/camrips"
    try:
        r = await client.get(search_url, timeout=10)
        if r.status_code == 200:
            body = r.text.lower()
            film_lower = film.lower()
            if film_lower in body or slug.replace("+", " ") in body:
                return {"source": "telegram", "hit": True, "url": search_url, "signal": "film_mentioned"}
    except Exception as e:
        print(f"[SCANNER] Telegram error: {e}")
    return {"source": "telegram", "hit": False}

async def check_reddit_signals(film: str, client: httpx.AsyncClient) -> dict:
    query = f"{film} CAM torrent"
    url = f"https://www.reddit.com/search.json?q={query}&sort=new&limit=5"
    try:
        r = await client.get(url, timeout=10, headers={"User-Agent": "CINEOS-Scanner/1.0"})
        if r.status_code == 200:
            data = r.json()
            posts = data.get("data", {}).get("children", [])
            for post in posts:
                pd = post.get("data", {})
                title = pd.get("title", "").lower()
                for kw in [k.lower() for k in PIRACY_KEYWORDS]:
                    if kw in title and film.lower() in title:
                        return {
                            "source": "reddit",
                            "hit": True,
                            "url": f"https://reddit.com{pd.get('permalink', '')}",
                            "title": pd.get("title"),
                            "keyword": kw
                        }
    except Exception as e:
        print(f"[SCANNER] Reddit error: {e}")
    return {"source": "reddit", "hit": False}

async def check_yts_api(film: str, client: httpx.AsyncClient) -> dict:
    try:
        r = await client.get(
            "https://yts.mx/api/v2/list_movies.json",
            params={"query_term": film, "limit": 5},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            movies = data.get("data", {}).get("movies", [])
            for movie in movies:
                title = movie.get("title", "").lower()
                if film.lower() in title:
                    year = movie.get("year", 0)
                    if year >= 2026:
                        return {
                            "source": "yts.mx",
                            "hit": True,
                            "url": movie.get("url"),
                            "title": movie.get("title"),
                            "year": year,
                            "quality": [t.get("quality") for t in movie.get("torrents", [])]
                        }
    except Exception as e:
        print(f"[SCANNER] YTS error: {e}")
    return {"source": "yts.mx", "hit": False}

async def full_scan(film_title: str) -> dict:
    print(f"[SCANNER] Starting full scan for: {film_title}")
    start = datetime.now(timezone.utc)
    
    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; CINEOS-Scanner/1.0)"}
    ) as client:
        tasks = [
            check_whereyouwatch(film_title, client),
            check_telegram_signals(film_title, client),
            check_reddit_signals(film_title, client),
            check_yts_api(film_title, client),
        ]
        
        if SERP_API_KEY:
            serp_task = check_google_serp(film_title, client)
            results_list = await asyncio.gather(*tasks, serp_task, return_exceptions=True)
            basic_results = results_list[:4]
            serp_results = results_list[4] if not isinstance(results_list[4], Exception) else []
        else:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            basic_results = results_list
            serp_results = []

    hits = []
    all_results = []

    for r in basic_results:
        if isinstance(r, Exception):
            continue
        if isinstance(r, list):
            all_results.extend(r)
            hits.extend([x for x in r if x.get("hit")])
        elif isinstance(r, dict):
            all_results.append(r)
            if r.get("hit"):
                hits.append(r)

    if isinstance(serp_results, list):
        all_results.extend(serp_results)
        hits.extend([x for x in serp_results if x.get("hit")])

    duration = (datetime.now(timezone.utc) - start).total_seconds()
    
    summary = {
        "film": film_title,
        "scanned_at": start.isoformat(),
        "duration_seconds": round(duration, 2),
        "sources_checked": len(set(r.get("source") for r in all_results)),
        "total_hits": len(hits),
        "hits": hits,
        "platforms": list(set(h.get("source") for h in hits)),
        "first_url": hits[0].get("url") if hits else "",
        "query": f"{film_title} CAM torrent",
        "scan_method": "multi_source_v2"
    }

    print(f"[SCANNER] Complete — {len(hits)} hits across {summary['sources_checked']} sources in {duration:.1f}s")
    return summary

if __name__ == "__main__":
    import sys
    film = sys.argv[1] if len(sys.argv) > 1 else "Mandalorian Grogu"
    result = asyncio.run(full_scan(film))
    import json
    print(json.dumps(result, indent=2))
