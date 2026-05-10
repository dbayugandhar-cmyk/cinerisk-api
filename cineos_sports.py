#!/usr/bin/env python3
"""
CINEOS Sports Anti-Piracy v1.0
================================
Real-time illegal sports stream detection.

Market: $4.5 billion lost to sports piracy in 2024
       Streameast (1.6B visits/year) just shut down Sept 2025
       Vacuum in the market — hundreds of replacements emerging
       IPL media rights: $1.2B/season
       NFL total revenue: $23B/year

Covers:
- Live stream piracy sites (Reddit streams, Streameast mirrors)
- Telegram sports channels (primary piracy vector)
- IPTV piracy detection
- Social media illegal streams (YouTube, Facebook Live)
- Dedicated illegal sports streaming sites
- Torrent sites for sports events

Target customers:
- Regional sports leagues ($299/month)
- Sports broadcasters DAZN, Sky, ESPN ($999/month)
- IPL team anti-piracy ($499/month)
- Premier League clubs ($499/month)
- Fight promoters: UFC, boxing PPV ($299/event)

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
    format="%(asctime)s [CINEOS-SPORTS] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.sports")

SERP_KEY = os.getenv("SERP_API_KEY", "")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "Accept-Language": "en-US,en;q=0.5",
}

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def matches(query: str, text: str, min_words: int = 1) -> bool:
    words = [w for w in query.lower().split() if len(w) > 2]
    if not words:
        return False
    return sum(1 for w in words if w in text.lower()) >= min(min_words, len(words))

# ── Sports piracy keywords ────────────────────────────────────────
PIRACY_KEYWORDS = [
    "live stream free", "watch live free", "free stream",
    "illegal stream", "stream online free", "watch online free",
    "reddit stream", "crackstream", "buffstream",
    "free sports stream", "live sports free",
    "sopcast", "acestream", "p2p stream",
    "iptv free", "free iptv", "m3u playlist",
    "livetv", "live tv free", "sports stream",
    "hesgoal", "streameast", "sportsurge",
    "firstrowsports", "ronaldo7", "vipbox",
    "wiziwig", "laola1", "sportlemon",
]

def contains_piracy(text: str) -> bool:
    return any(k in text.lower() for k in PIRACY_KEYWORDS)

# ── Legitimate sports sites ───────────────────────────────────────
LEGITIMATE_SITES = [
    "espn.com", "nfl.com", "nba.com", "mlb.com", "nhl.com",
    "premierleague.com", "uefa.com", "fifa.com",
    "sky.com", "bbc.com/sport", "skysports.com",
    "dazn.com", "peacocktv.com", "paramountplus.com",
    "primevideo.com", "disneyplus.com", "hulu.com",
    "hotstar.com", "jiocinema.com", "sonyliv.com",
    "wikipedia.org", "reddit.com/r/nfl", "reddit.com/r/soccer",
    "twitter.com", "youtube.com/@official",
    "cricbuzz.com", "espncricinfo.com",
]

def is_legitimate(url: str) -> bool:
    return any(s in url.lower() for s in LEGITIMATE_SITES)

# ── Sports piracy sites ───────────────────────────────────────────
SPORTS_PIRACY_SITES = [
    # Major illegal streaming sites (Streameast replacements)
    {"name": "Crackstreams",   "domain": "crackstreams.com",    "priority": 1},
    {"name": "BuffStream",     "domain": "buffstream.io",       "priority": 1},
    {"name": "Sportsurge",     "domain": "sportsurge.net",      "priority": 1},
    {"name": "HesGoal",        "domain": "hesgoal.com",         "priority": 1},
    {"name": "VIPBox",         "domain": "vipbox.lc",           "priority": 1},
    {"name": "SportLemon",     "domain": "sportlemon.tv",       "priority": 1},
    {"name": "FirstRowSports", "domain": "firstrowsports.eu",   "priority": 1},
    {"name": "LiveTV",         "domain": "livetv.sx",           "priority": 1},
    {"name": "Ronaldo7",       "domain": "ronaldo7.net",        "priority": 2},
    {"name": "WiziWig",        "domain": "wiziwig.tv",          "priority": 2},
    {"name": "Laola1",         "domain": "laola1.tv",           "priority": 2},
    {"name": "StrikeOut",      "domain": "strikeout.nu",        "priority": 2},
    {"name": "CricFree",       "domain": "cricfree.sc",         "priority": 1},
    {"name": "StreamEast Mirror","domain": "streameast.live",   "priority": 1},
    {"name": "SportP2P",       "domain": "sportp2p.com",        "priority": 2},
    # Reddit streams
    {"name": "Reddit Streams", "domain": "reddit.com",          "priority": 1},
    # Telegram sports channels
    {"name": "Telegram Sports","domain": "t.me",                "priority": 1},
    # IPTV sites
    {"name": "IPTV Cat",       "domain": "iptvcat.com",         "priority": 2},
    {"name": "Free IPTV",      "domain": "freefreeiptv.com",    "priority": 2},
    # Indian sports piracy
    {"name": "CricTime",       "domain": "crictime.com",        "priority": 1},
    {"name": "SmartCric",      "domain": "smartcric.com",       "priority": 1},
    {"name": "WebCric",        "domain": "webcric.com",         "priority": 2},
    {"name": "CricHD",         "domain": "crichd.com",          "priority": 1},
    # Torrent sites for sports
    {"name": "1337x Sports",   "domain": "1337x.to",            "priority": 2},
    {"name": "TorrentGalaxy",  "domain": "torrentgalaxy.to",    "priority": 2},
]


@dataclass
class SportsResult:
    platform: str
    status: str
    url: str = ""
    detail: str = ""
    stream_type: str = ""   # LIVE, REPLAY, IPTV, TORRENT
    confidence: float = 0.0


async def scan_site_serp(
    site: dict,
    event: str,
    client: httpx.AsyncClient
) -> SportsResult:
    """Scan sports piracy site via SerpApi."""
    if not SERP_KEY:
        return SportsResult(site["name"], "SKIPPED")
    try:
        query = f'site:{site["domain"]} "{event}" stream'
        r = await client.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": SERP_KEY,
                    "num": 3, "engine": "google"},
            timeout=12
        )
        if r.status_code != 200:
            return SportsResult(site["name"], "ERROR")

        items = r.json().get("organic_results", [])
        for item in items:
            link = item.get("link", "")
            t = item.get("title", "")
            snippet = item.get("snippet", "")
            full = f"{t} {snippet}".lower()

            if is_legitimate(link):
                continue
            if not matches(event, full):
                continue

            # Detect stream type
            stream_type = "LIVE"
            if "torrent" in full: stream_type = "TORRENT"
            elif "iptv" in full or "m3u" in full: stream_type = "IPTV"
            elif "replay" in full or "highlights" in full:
                stream_type = "REPLAY"

            return SportsResult(
                platform=site["name"],
                status="HIT",
                url=link,
                detail=t[:80],
                stream_type=stream_type,
                confidence=0.85
            )

        return SportsResult(site["name"], "CLEAN", confidence=1.0)

    except Exception as e:
        return SportsResult(site["name"], "ERROR",
                           detail=str(e)[:50])


async def scan_reddit_streams(
    event: str,
    client: httpx.AsyncClient
) -> SportsResult:
    """Scan Reddit for illegal stream links."""
    if not SERP_KEY:
        return SportsResult("Reddit Streams", "SKIPPED")
    try:
        r = await client.get(
            "https://serpapi.com/search",
            params={
                "q": f'site:reddit.com "{event}" stream free watch',
                "api_key": SERP_KEY,
                "num": 5,
                "engine": "google"
            },
            timeout=12
        )
        if r.status_code == 200:
            items = r.json().get("organic_results", [])
            for item in items:
                t = item.get("title", "")
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                full = f"{t} {snippet}".lower()
                if matches(event, full) and contains_piracy(full):
                    return SportsResult(
                        platform="Reddit Streams",
                        status="HIT",
                        url=link,
                        detail=t[:80],
                        stream_type="LIVE",
                        confidence=0.75
                    )
        return SportsResult("Reddit Streams", "CLEAN")
    except Exception as e:
        return SportsResult("Reddit Streams", "ERROR",
                           detail=str(e)[:50])


async def scan_telegram_sports(
    event: str,
    client: httpx.AsyncClient
) -> list[SportsResult]:
    """Scan Telegram sports channels."""
    results = []
    channels = [
        "SportsFreeStreams", "LiveSportsTV",
        "CricketLiveStream", "FootballLiveStream",
        "IPLLiveStream", "NFLLiveStream",
        "UFCLiveStream", "NBALiveStream",
    ]
    ew = [w for w in event.lower().split() if len(w) > 2]

    for ch in channels:
        try:
            r = await client.get(
                f"https://t.me/s/{ch}",
                timeout=8, headers=HEADERS
            )
            if r.status_code == 200:
                body = r.text.lower()
                # Require ALL significant event words to appear
                # AND a streaming signal — not just channel exists
                event_words_found = sum(1 for w in ew if w in body)
                has_stream_signal = any(k in body for k in [
                    "live stream", "watch live", "stream link",
                    "free stream", "hd stream", "live now"
                ])
                min_required = max(2, len(ew))
                if (event_words_found >= min(min_required, len(ew))
                        and has_stream_signal and len(ew) >= 2):
                    results.append(SportsResult(
                        platform=f"Telegram @{ch}",
                        status="HIT",
                        url=f"https://t.me/{ch}",
                        detail=f"Stream confirmed in Telegram @{ch}",
                        stream_type="LIVE",
                        confidence=0.70
                    ))
            await asyncio.sleep(0.2)
        except Exception:
            pass

    return results


async def scan_ddg_sports(
    event: str,
    client: httpx.AsyncClient
) -> list[SportsResult]:
    """DuckDuckGo free scan for sports piracy."""
    results = []
    queries = [
        f"{event} free live stream watch online",
        f"{event} illegal stream crackstream buffstream",
        f"{event} iptv free stream link",
    ]

    piracy_domains = [s["domain"].split(".")[0]
                      for s in SPORTS_PIRACY_SITES]

    for query in queries:
        try:
            r = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                timeout=12, headers=HEADERS
            )
            if r.status_code != 200:
                continue

            body = r.text
            urls = [unquote(u) for u in
                    re.findall(r'uddg=(https?[^&"]+)', body)]
            titles_raw = re.findall(
                r'result__a"[^>]+>([^<]+)</a>', body)

            for i, url in enumerate(urls[:15]):
                t = titles_raw[i % len(titles_raw)] \
                    if titles_raw else ""
                combined = (url + " " + t).lower()

                if is_legitimate(url):
                    continue
                if not matches(event, combined):
                    continue

                is_piracy = any(d in url.lower()
                               for d in piracy_domains)
                has_signal = contains_piracy(combined)
                is_homepage = url.rstrip('/').count('/') <= 2
                is_generic = any(x in url.lower() for x in [
                    "best-sites", "top-10", "how-to",
                    "reddit.com/r/", "quora.com",
                    "youtube.com/watch"
                ])
                event_in_url = matches(event, url, min_words=1)

                if ((is_piracy or has_signal) and
                        not is_homepage and not is_generic and
                        event_in_url):
                    if not any(res.url == url for res in results):
                        results.append(SportsResult(
                            platform=f"DDG: {url.split('/')[2][:25]}",
                            status="HIT",
                            url=url,
                            detail=t[:80],
                            stream_type="LIVE",
                            confidence=0.70
                        ))

            await asyncio.sleep(1)
        except Exception as e:
            log.warning(f"DDG sports error: {e}")

    return results


async def full_sports_scan(event: str, sport: str = "") -> dict:
    """Complete sports piracy scan."""
    log.info(f"Scanning: {event} ({sport})")

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=15
    ) as client:
        # Run ALL sites in parallel — no sequential batches
        all_tasks = [scan_site_serp(s, event, client)
                     for s in SPORTS_PIRACY_SITES]
        all_results = await asyncio.gather(*all_tasks,
                                           return_exceptions=True)
        p1_results = all_results
        p2_results = []

        reddit_result, tg_results, ddg_results = \
            await asyncio.gather(
                scan_reddit_streams(event, client),
                scan_telegram_sports(event, client),
                scan_ddg_sports(event, client),
                return_exceptions=True
            )

    all_results = []
    for r in [*p1_results, *p2_results]:
        if isinstance(r, SportsResult):
            all_results.append(r)
    if isinstance(reddit_result, SportsResult):
        all_results.append(reddit_result)
    if isinstance(tg_results, list):
        all_results.extend(tg_results)
    if isinstance(ddg_results, list):
        all_results.extend(ddg_results)

    hits = [r for r in all_results if r.status == "HIT"]
    stream_types = list(set(h.stream_type for h in hits
                            if h.stream_type))

    verdict = "CONFIRMED" if hits else "CLEAN"
    log.info(f"Sports scan: {len(hits)} hits")

    return {
        "event": event,
        "sport": sport,
        "verdict": verdict,
        "hits_found": len(hits),
        "platforms_scanned": len(all_results),
        "hits": hits,
        "stream_types": stream_types,
        "scanned_at": now_utc(),
    }


def generate_sports_report(
    result: dict,
    broadcaster: str = "",
    contact_email: str = ""
) -> str:
    """Generate sports piracy evidence report."""
    event = result["event"]
    hits = result["hits"]
    now = result["scanned_at"]
    types = result.get("stream_types", [])

    urls_section = ""
    if hits:
        for i, h in enumerate(hits, 1):
            urls_section += f"\n  {i}. Platform   : {h.platform}"
            urls_section += f"\n     URL        : {h.url}"
            urls_section += f"\n     Type       : {h.stream_type}"
            urls_section += f"\n     Confidence : {h.confidence*100:.0f}%"
            if h.detail:
                urls_section += f"\n     Detail     : {h.detail[:70]}"
            urls_section += "\n"
    else:
        urls_section = "  No infringing streams detected."

    return f"""
{"="*72}
  CINEOS SPORTS — ANTI-PIRACY EVIDENCE REPORT v1.0
  17 U.S.C. § 605 (Unauthorized Reception of Communications)
  17 U.S.C. § 512(c)(3) (DMCA Safe Harbor)
  US Provisional Patent 64/049,190
{"="*72}

  Event           : {event}
  Sport           : {result.get('sport', 'N/A')}
  Broadcaster     : {broadcaster or "Rights Holder"}
  Report Date     : {now}
  Prepared by     : CINEOS Sports Anti-Piracy Platform

{"="*72}
  VERDICT         : {result['verdict']}
  Platforms scanned: {result['platforms_scanned']}
  Illegal streams  : {result['hits_found']}
  Stream types     : {', '.join(types) if types else 'None'}
{"="*72}

ILLEGAL STREAMS DETECTED
{"─"*72}
{urls_section}

ACCURACY DECLARATION
{"─"*72}
  The information in this report is accurate to the best of my
  knowledge. This report is provided for informational purposes.
  Rights holders should verify findings and consult legal counsel
  before filing notices under 17 U.S.C. § 605 or § 512.

  /s/ Yugandhar Mallavarapu, CINEOS
  Date: {now}
  Capacity: Anti-Piracy Detection Service (Monitoring Only)

{"="*72}
  CINEOS Sports Anti-Piracy
  $299/month per league | $99/event for PPV
  yugandhar@cineos.in | US Prov. Pat. 64/049,190
{"="*72}
"""


async def main(event: str, sport: str = "",
               broadcaster: str = "", email: str = ""):
    print(f"\nCINEOS Sports — Scanning: {event}")
    print("="*50)
    result = await full_sports_scan(event, sport)
    report = generate_sports_report(result, broadcaster, email)
    print(report)
    if result["hits"]:
        print("ILLEGAL STREAMS:")
        for h in result["hits"]:
            print(f"  [{h.stream_type}] {h.platform} "
                  f"— {h.url[:60]}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="CINEOS Sports Anti-Piracy")
    ap.add_argument("--event", required=True,
                    help="Event name e.g. 'IPL 2025 Final'")
    ap.add_argument("--sport", default="",
                    help="Sport type e.g. cricket, football")
    ap.add_argument("--broadcaster", default="")
    ap.add_argument("--email", default="")
    args = ap.parse_args()
    asyncio.run(main(args.event, args.sport,
                     args.broadcaster, args.email))
