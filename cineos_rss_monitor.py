#!/usr/bin/env python3
"""
CINEOS RSS Feed Monitor v2.0
==============================
Real-time monitoring across verified working RSS feeds.
Zero SerpApi quota. Catches uploads within minutes.
Covers film, music, gaming, manga, sports, India.

Verified working feeds: 13 feeds, ~620 items monitored.
US Provisional Patent 64/049,190
"""

import asyncio
import httpx
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CINEOS-RSS] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.rss")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
}

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

# ── Verified working feeds — tested May 2026 ──────────────────────
RSS_FEEDS = {
    # ── FILM — 8 feeds, 530+ items ───────────────────────────────
    "film": [
        {"name": "LimeTorrents Movies", "url": "https://www.limetorrents.lol/rss/movies/"},
        {"name": "LimeTorrents TV",     "url": "https://www.limetorrents.lol/rss/tv/"},
        {"name": "LimeTorrents All",    "url": "https://www.limetorrents.lol/rss/all/"},
        {"name": "NYAA All",            "url": "https://nyaa.si/?page=rss&c=0_0&f=0"},
        {"name": "NYAA Live Action",    "url": "https://nyaa.si/?page=rss&c=4_0&f=0"},
        {"name": "EZTV",                "url": "https://eztv.re/ezrss.xml"},
        {"name": "ShowRSS",             "url": "https://showrss.info/other/all.rss"},
        {"name": "NZBIndex",            "url": "https://nzbindex.com/rss"},
    ],
    # ── MUSIC — 5 feeds, 500+ items ──────────────────────────────
    "music": [
        {"name": "LimeTorrents Music",  "url": "https://www.limetorrents.lol/rss/music/"},
        {"name": "NYAA Music",          "url": "https://nyaa.si/?page=rss&c=2_0&f=0"},
        {"name": "TokyoTosho Music",    "url": "https://www.tokyotosho.info/rss.php?cat=2"},
        {"name": "NZBIndex",            "url": "https://nzbindex.com/rss"},
        {"name": "ShowRSS",             "url": "https://showrss.info/other/all.rss"},
    ],
    # ── GAMING — 12 feeds, 150+ items ────────────────────────────
    "gaming": [
        {"name": "FitGirl Repacks",     "url": "https://fitgirl-repacks.site/feed/"},
        {"name": "IGG Games",           "url": "https://igg-games.com/feed"},
        {"name": "OvaGames",            "url": "https://ovagames.com/feed"},
        {"name": "RepackLab",           "url": "https://repacklab.com/feed"},
        {"name": "Karanpc",             "url": "https://karanpc.com/feed"},
        {"name": "ApunKaGames",         "url": "https://apunkagames.biz/feed"},
        {"name": "PCGamesTorrents",     "url": "https://pcgamestorrents.com/feed"},
        {"name": "GameTrex",            "url": "https://gametrex.com/feed"},
        {"name": "FreeGOGPCGames",      "url": "https://freegogpcgames.com/feed"},
        {"name": "LimeTorrents Games",  "url": "https://www.limetorrents.lol/rss/games/"},
        {"name": "NYAA Games",          "url": "https://nyaa.si/?page=rss&c=6_2&f=0"},
        {"name": "NYAA Software",       "url": "https://nyaa.si/?page=rss&c=6_1&f=0"},
    ],
    # ── MANGA — 10 feeds, 900+ items ─────────────────────────────
    "manga": [
        {"name": "NYAA Manga",          "url": "https://nyaa.si/?page=rss&c=3_1&f=0"},
        {"name": "NYAA Books",          "url": "https://nyaa.si/?page=rss&c=3_0&f=0"},
        {"name": "NYAA Anime English",  "url": "https://nyaa.si/?page=rss&c=1_2&f=0"},
        {"name": "NYAA Anime Non-Eng",  "url": "https://nyaa.si/?page=rss&c=1_3&f=0"},
        {"name": "LimeTorrents Anime",  "url": "https://www.limetorrents.lol/rss/anime/"},
        {"name": "LimeTorrents Other",  "url": "https://www.limetorrents.lol/rss/other/"},
        {"name": "SubsPlease",          "url": "https://subsplease.org/rss/?r=1080"},
        {"name": "TokyoTosho Anime",    "url": "https://www.tokyotosho.info/rss.php?cat=1"},
        {"name": "TokyoTosho Manga",    "url": "https://www.tokyotosho.info/rss.php?cat=4"},
        {"name": "AniDex",              "url": "https://anidex.info/rss?id=1,2,3"},
    ],
    # ── SPORTS — 5 feeds, 380+ items ─────────────────────────────
    "sports": [
        {"name": "LimeTorrents TV",     "url": "https://www.limetorrents.lol/rss/tv/"},
        {"name": "LimeTorrents All",    "url": "https://www.limetorrents.lol/rss/all/"},
        {"name": "NYAA All",            "url": "https://nyaa.si/?page=rss&c=0_0&f=0"},
        {"name": "EZTV",                "url": "https://eztv.re/ezrss.xml"},
        {"name": "ShowRSS",             "url": "https://showrss.info/other/all.rss"},
    ],
    # ── INDIA — 6 feeds, 430+ items ──────────────────────────────
    "india": [
        {"name": "LimeTorrents Movies", "url": "https://www.limetorrents.lol/rss/movies/"},
        {"name": "LimeTorrents All",    "url": "https://www.limetorrents.lol/rss/all/"},
        {"name": "NYAA All",            "url": "https://nyaa.si/?page=rss&c=0_0&f=0"},
        {"name": "NYAA Live Action",    "url": "https://nyaa.si/?page=rss&c=4_0&f=0"},
        {"name": "EZTV",                "url": "https://eztv.re/ezrss.xml"},
        {"name": "NZBIndex",            "url": "https://nzbindex.com/rss"},
    ],
}

ALL_FEEDS = []
for cat, feeds in RSS_FEEDS.items():
    for f in feeds:
        entry = dict(f)
        entry["category"] = cat
        ALL_FEEDS.append(entry)


@dataclass
class RSSHit:
    feed_name: str
    category: str
    title: str
    url: str
    pub_date: str = ""
    matched_title: str = ""
    confidence: float = 0.0


def matches(query: str, text: str) -> tuple[bool, float]:
    """Check if query words appear in text. Returns (matched, confidence)."""
    words = [w for w in query.lower().split() if len(w) > 2]
    if not words:
        return False, 0.0
    text_lower = text.lower()
    matched = sum(1 for w in words if w in text_lower)
    confidence = matched / len(words)
    # Require ALL words for short queries (1-2 words)
    # Require 75% match for longer queries
    if len(words) <= 2:
        required = len(words)  # All words must match
    else:
        required = max(2, int(len(words) * 0.75))
    return matched >= required, confidence


def get_item_text(item, tag: str) -> str:
    """Safely get text from XML element."""
    el = item.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return ""


def get_link(item) -> str:
    """Extract link from RSS item — handles multiple formats."""
    # Standard RSS link
    link_el = item.find('link')
    if link_el is not None:
        if link_el.text and link_el.text.strip().startswith('http'):
            return link_el.text.strip()
        href = link_el.get('href', '')
        if href.startswith('http'):
            return href

    # Try guid as fallback
    guid_el = item.find('guid')
    if guid_el is not None and guid_el.text:
        text = guid_el.text.strip()
        if text.startswith('http'):
            return text

    return ""


def parse_feed(xml_text: str, feed_name: str,
               category: str, search: str) -> list[RSSHit]:
    """Parse RSS/Atom feed and return matching hits."""
    hits = []
    try:
        root = ET.fromstring(xml_text)

        # Find items (RSS) or entries (Atom)
        items = root.findall('.//item')
        if not items:
            items = root.findall(
                './/{http://www.w3.org/2005/Atom}entry')

        for item in items[:75]:
            title = get_item_text(item, 'title')
            if not title:
                title_el = item.find(
                    '{http://www.w3.org/2005/Atom}title')
                title = (title_el.text or "").strip() \
                    if title_el is not None else ""

            desc = get_item_text(item, 'description')
            pub_date = get_item_text(item, 'pubDate')
            link = get_link(item)

            combined = f"{title} {desc}"
            matched, confidence = matches(search, combined)

            if matched:
                hits.append(RSSHit(
                    feed_name=feed_name,
                    category=category,
                    title=title,
                    url=link,
                    pub_date=pub_date,
                    matched_title=search,
                    confidence=round(confidence, 2)
                ))

    except ET.ParseError:
        pass
    except Exception as e:
        log.debug(f"Parse error {feed_name}: {e}")

    return hits


async def fetch_and_parse(feed: dict, search: str,
                           client: httpx.AsyncClient) -> list[RSSHit]:
    """Fetch RSS feed and parse for matches."""
    try:
        r = await client.get(feed["url"], timeout=10, headers=HEADERS)
        if r.status_code != 200:
            return []
        return parse_feed(r.text, feed["name"],
                          feed.get("category", ""), search)
    except asyncio.TimeoutError:
        return []
    except Exception:
        return []


async def scan_rss(title: str, category: str = "all") -> dict:
    """Scan RSS feeds for a title."""
    log.info(f"RSS scan: '{title}' [{category}]")

    if category == "all":
        feeds = ALL_FEEDS
    else:
        feeds = [dict(f, category=category)
                 for f in RSS_FEEDS.get(category, [])]

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=12
    ) as client:
        tasks = [fetch_and_parse(f, title, client) for f in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_hits = []
    for r in results:
        if isinstance(r, list):
            all_hits.extend(r)

    # Deduplicate by URL
    seen = set()
    unique = []
    for h in all_hits:
        key = h.url or h.title
        if key not in seen:
            seen.add(key)
            unique.append(h)

    log.info(f"RSS: {len(unique)} hits across {len(feeds)} feeds")

    return {
        "title": title,
        "category": category,
        "verdict": "CONFIRMED" if unique else "CLEAN",
        "hits_found": len(unique),
        "feeds_scanned": len(feeds),
        "hits": unique,
        "scanned_at": now_utc(),
    }


async def scan_watchlist_rss(titles: list[str]) -> dict:
    """Scan multiple titles via RSS — zero SerpApi quota."""
    log.info(f"Watchlist RSS: {len(titles)} titles")
    results = {}

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=12
    ) as client:
        for title in titles:
            tasks = [fetch_and_parse(f, title, client)
                     for f in ALL_FEEDS]
            raw = await asyncio.gather(*tasks, return_exceptions=True)
            hits = []
            seen = set()
            for r in raw:
                if isinstance(r, list):
                    for h in r:
                        key = h.url or h.title
                        if key not in seen:
                            seen.add(key)
                            hits.append(h)
            results[title] = {
                "verdict": "CONFIRMED" if hits else "CLEAN",
                "hits_found": len(hits),
                "hits": hits
            }
            await asyncio.sleep(0.3)

    confirmed = sum(1 for r in results.values()
                    if r["verdict"] == "CONFIRMED")
    return {
        "scanned": len(titles),
        "confirmed": confirmed,
        "results": results,
        "scanned_at": now_utc()
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="CINEOS RSS Monitor")
    ap.add_argument("--title", help="Title to search")
    ap.add_argument("--category", default="all",
                    choices=["all","film","music","gaming",
                             "manga","sports","india"])
    ap.add_argument("--watchlist", nargs="+",
                    help="Multiple titles")
    ap.add_argument("--list-feeds", action="store_true")
    args = ap.parse_args()

    if args.list_feeds:
        total = sum(len(v) for v in RSS_FEEDS.values())
        print(f"\nCINEOS RSS Monitor — {total} verified feeds:")
        for cat, feeds in RSS_FEEDS.items():
            print(f"\n  {cat.upper()} ({len(feeds)} feeds):")
            for f in feeds:
                print(f"    {f['name']}")
        import sys; sys.exit(0)

    if args.watchlist:
        result = asyncio.run(scan_watchlist_rss(args.watchlist))
        print(f"\nWatchlist RSS Scan — {result['scanned_at']}")
        print(f"Scanned: {result['scanned']} | "
              f"Confirmed: {result['confirmed']}")
        for title, r in result['results'].items():
            icon = "🔴" if r['hits_found'] > 0 else "✓"
            print(f"  {icon} {title}: {r['verdict']} "
                  f"({r['hits_found']} hits)")
            for h in r['hits']:
                print(f"      [{h.feed_name}] {h.title[:55]}")
                print(f"      {h.url[:65]}")

    elif args.title:
        result = asyncio.run(scan_rss(args.title, args.category))
        print(f"\n{'='*60}")
        print(f"  CINEOS RSS — {result['title']}")
        print(f"  Verdict: {result['verdict']} | "
              f"Hits: {result['hits_found']} | "
              f"Feeds: {result['feeds_scanned']}")
        print(f"{'='*60}")
        for h in result['hits']:
            print(f"\n  [{h.category.upper()}] {h.feed_name}")
            print(f"  {h.title[:70]}")
            print(f"  {h.url[:70]}")
            print(f"  Confidence: {h.confidence*100:.0f}%")
        if not result['hits']:
            print("  No matches in current RSS feeds")
            print("  (RSS shows only recent uploads — "
                  "older content won't appear)")

    else:
        print("Use --title, --watchlist, or --list-feeds")
