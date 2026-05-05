#!/usr/bin/env python3
"""
CINEOS DuckDuckGo Search — Zero cost, no API key, no quota
"""
import asyncio, httpx, re, logging
from urllib.parse import unquote

log = logging.getLogger("cineos.ddg")
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

CAM_KEYWORDS = [
    "camrip","cam-rip","hdcam","hdts","telesync","source: camera",
    "line audio","hdrip","dvdrip","dvdscr","webrip","theater print",
]
PIRACY_DOMAINS = [
    "movierulz","tamilmv","filmyzilla","9xmovies","tamilblasters",
    "ibomma","isaimini","hdhub4u","vegamovies","bolly4u","1337x",
    "torrentgalaxy","yts.mx","nyaa","torrentleech","xrel.to",
    "torrentclaw","hdcam","scene","predb","srrdb",
]

def contains_cam(text: str) -> bool:
    return any(k in text.lower() for k in CAM_KEYWORDS)

def is_piracy(url: str, title: str = "") -> bool:
    combined = (url + " " + title).lower()
    return (any(d in combined for d in PIRACY_DOMAINS) or
            contains_cam(combined))


async def ddg_search(query: str, client: httpx.AsyncClient) -> list[dict]:
    try:
        r = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query}, timeout=12, headers=HEADERS
        )
        if r.status_code != 200:
            return []
        body = r.text
        urls = [unquote(u) for u in re.findall(r'uddg=(https?[^&"]+)', body)]
        titles = re.findall(r'result__a"[^>]+>([^<]+)</a>', body)
        results = []
        for i, url in enumerate(urls[:15]):
            title = titles[i % len(titles)] if titles else ""
            results.append({"url": url, "title": title.strip()})
        return results
    except Exception as e:
        log.error(f"DDG failed: {e}")
        return []


async def scan_ddg(film: str, client: httpx.AsyncClient) -> list[dict]:
    hits = []
    fw = [w for w in film.lower().split() if len(w) > 2]

    queries = [
        f'{film} 2026 telesync torrent download',
        f'{film} 2026 camrip hdcam movierulz filmyzilla',
    ]

    for query in queries:
        results = await ddg_search(query, client)
        for r in results:
            url = r["url"]
            title = r["title"]
            film_ok = sum(1 for w in fw if w in (url+title).lower()) >= min(1, len(fw))
            if film_ok and is_piracy(url, title):
                if not any(h["url"] == url for h in hits):
                    hits.append({
                        "platform": "DuckDuckGo",
                        "url": url,
                        "title": title[:80],
                        "quality": "CAM/TELESYNC"
                    })
        await asyncio.sleep(1)

    return hits


async def main(film: str):
    print(f"\nCINEOS DDG Scanner — {film}")
    print("="*50)
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        hits = await scan_ddg(film, client)
    if hits:
        print(f"HITS: {len(hits)}")
        for h in hits:
            print(f"\n  {h['platform']} | {h['quality']}")
            print(f"  {h['url'][:75]}")
            print(f"  {h['title'][:65]}")
    else:
        print("CLEAN — No piracy hits")
    print(f"\nSerpApi searches used: 0")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", required=True)
    args = ap.parse_args()
    asyncio.run(main(args.film))
