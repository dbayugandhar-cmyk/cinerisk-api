#!/usr/bin/env python3
"""
CINEOS Velocity Tracker v1.0
==============================
Tracks piracy spread velocity over time.
Runs every hour, stores timestamped platform counts.
Powers the velocity dashboard with REAL data.

This is what makes CINEOS industry gold standard:
- Every scan timestamped to the minute
- Platform count tracked over time
- Spread rate calculated per film
- Revenue impact estimated from spread rate
- Cascade order documented (which platform → which platform)

US Provisional Patent 64/049,190
"""

import asyncio
import httpx
import psycopg2
import os
import re
import logging
from datetime import datetime, timezone
from dataclasses import dataclass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CINEOS-VELOCITY] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.velocity")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:REDACTED@tramway.proxy.rlwy.net:27075/railway"
)
SERP_KEY = os.getenv("SERP_API_KEY", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}

# Known release dates for films we monitor
RELEASE_DATES = {
    "Michael": "2026-04-10",
    "Retro": "2025-12-20",
    "Jet Lee": "2026-04-17",
    "Mortal Kombat II": "2026-05-08",
    "Pushpa 2": "2024-12-05",
    "The Sheep Detectives": "2026-04-01",
    "The Devil Wears Prada 2": "2025-06-01",
    "Star Wars: The Mandalorian and Grogu": "2026-05-22",
}

# Revenue per theater visit estimates (USD)
REVENUE_PER_TICKET = {
    "film": 12.50,
    "india": 3.50,
}

# Conversion rate: piracy downloads → lost tickets
PIRACY_CONVERSION = 0.15  # 15% of pirates would have paid

# Average downloads per platform per day
AVG_DOWNLOADS_PER_PLATFORM = 50000

PIRACY_SITES = [
    # Major torrent sites
    "thepiratebay.org", "1337x.to", "yts.mx", "rarbg.to",
    "torrentgalaxy.to", "nyaa.si", "limetorrents.lol",
    "torrentleech.org", "magnetdl.com", "bitsearch.to",
    # Indian piracy
    "5movierulz.camera", "movierulz.com", "tamilmv.fi",
    "filmyzilla.com", "ibomma.com", "tamilrockers.ws",
    "isaimini.com", "hdhub4u.com", "9xmovies.cool",
    "worldfree4u.mom", "mp4moviez.com", "kuttymovies.com",
    # Streaming piracy
    "whereyouwatch.com", "watchsomuch.to", "fmovies.to",
    "soap2day.to", "123movies.ai", "hdtoday.cc",
    # Index sites
    "opensubtitles.org", "subscene.com",
    # Gaming
    "fitgirl-repacks.site", "igg-games.com",
]

NEWS_DOMAINS = [
    "ndtv", "abplive", "indiatoday", "timesofindia",
    "hindustantimes", "thehindu", "news18", "firstpost",
    "123telugu", "gulte", "cinejosh", "idlebrain",
]

CATEGORY_PATTERNS = [
    "/page/", "/category/", "/tag/", "/language/",
    "/genre/", "/quality/", "?sort=", "/?s=",
]


def hours_since_release(title: str) -> float:
    """Calculate hours since film release."""
    release_str = RELEASE_DATES.get(title)
    if not release_str:
        return 0
    release = datetime.strptime(release_str, "%Y-%m-%d")
    return (datetime.now() - release).total_seconds() / 3600


def estimate_revenue_loss(
    platform_count: int,
    hours: float,
    category: str = "film"
) -> float:
    """
    Estimate revenue loss based on platform count and time.
    Formula: platforms × avg_downloads × conversion × ticket_price
    """
    daily_downloads = platform_count * AVG_DOWNLOADS_PER_PLATFORM
    days_active = max(1, hours / 24)
    lost_tickets = daily_downloads * days_active * PIRACY_CONVERSION
    price = REVENUE_PER_TICKET.get(category, 12.50)
    return round(lost_tickets * price)


def is_valid_hit(link: str, title: str, text: str) -> bool:
    """Strict validation — reject false positives."""
    # Reject news articles
    if any(d in link.lower() for d in NEWS_DOMAINS):
        return False
    # Reject category pages
    if any(p in link.lower() for p in CATEGORY_PATTERNS):
        return False
    # Title must appear in text
    words = [w for w in title.lower().split() if len(w) > 2]
    text_lower = text.lower()
    # Check concatenated (jetlee) AND spaced (jet lee)
    concat = title.lower().replace(" ", "")
    if len(concat) > 4 and concat in text_lower:
        return True
    matched = sum(1 for w in words if w in text_lower)
    return matched >= min(2, len(words))


async def scan_film_velocity(
    title: str,
    client: httpx.AsyncClient
) -> dict:
    """Scan film across all piracy sites and return velocity data."""
    hits = []
    platforms_found = set()
    quality_found = set()

    batches = [PIRACY_SITES[i:i+8]
               for i in range(0, len(PIRACY_SITES), 8)]

    for batch in batches:
        site_q = " OR ".join(f"site:{s}" for s in batch)
        query = f'"{title}" ({site_q})'

        try:
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": SERP_KEY,
                    "num": 10,
                    "engine": "google"
                },
                timeout=15
            )
            if r.status_code != 200:
                continue

            for item in r.json().get("organic_results", []):
                link = item.get("link", "")
                t = item.get("title", "")
                snippet = item.get("snippet", "")
                full = f"{t} {snippet}"

                if not is_valid_hit(link, title, full):
                    continue

                domain = link.split("/")[2] if "/" in link else link
                platforms_found.add(domain[:40])

                # Quality detection
                f = full.lower()
                if any(k in f for k in ["hdts","ts ","telesync","camrip","cam rip"]):
                    quality_found.add("CAM/HDTS")
                elif "hdrip" in f:
                    quality_found.add("HDRip")
                elif "webrip" in f or "web-dl" in f:
                    quality_found.add("WebRip")
                elif "bluray" in f:
                    quality_found.add("BluRay")
                elif "1080p" in f:
                    quality_found.add("1080p")
                elif "720p" in f:
                    quality_found.add("720p")

                hits.append({
                    "url": link,
                    "platform": domain[:40],
                    "title": t[:80],
                    "quality": list(quality_found)[-1] if quality_found else "Unknown"
                })

            await asyncio.sleep(0.3)
        except Exception as e:
            log.debug(f"Scan error: {e}")

    hours = hours_since_release(title)
    platform_count = len(platforms_found)
    revenue_loss = estimate_revenue_loss(platform_count, hours)

    # Calculate spread rate (platforms per hour)
    spread_rate = round(platform_count / max(1, hours), 4) if hours > 0 else 0

    return {
        "title": title,
        "hits": len(hits),
        "platforms": list(platforms_found),
        "platform_count": platform_count,
        "hours_since_release": round(hours, 1),
        "spread_rate": spread_rate,
        "quality": ", ".join(quality_found) if quality_found else "Unknown",
        "revenue_loss": revenue_loss,
        "hit_details": hits[:10],
    }


async def store_velocity(result: dict, conn) -> None:
    """Store velocity scan result in database."""
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO cineos_velocity
            (film_title, hits_found, platforms, platform_count,
             hours_since_release, spread_rate, category, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            result["title"],
            result["hits"],
            result["platforms"],
            result["platform_count"],
            result["hours_since_release"],
            result["spread_rate"],
            "film",
            "serp_real"
        ))
        conn.commit()
    except Exception as e:
        log.error(f"DB store error: {e}")
        conn.rollback()
    finally:
        cur.close()


def get_velocity_history(title: str, conn) -> list:
    """Get historical velocity data for a film."""
    cur = conn.cursor()
    cur.execute("""
        SELECT scan_time, platform_count, hits_found,
               hours_since_release, spread_rate
        FROM cineos_velocity
        WHERE film_title = %s
        ORDER BY scan_time ASC
    """, (title,))
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "scan_time": str(r[0]),
            "platform_count": r[1],
            "hits_found": r[2],
            "hours_since_release": float(r[3] or 0),
            "spread_rate": float(r[4] or 0)
        }
        for r in rows
    ]


def get_velocity_summary(conn) -> list:
    """Get latest velocity data for all tracked films."""
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (film_title)
            film_title, scan_time, platform_count,
            hits_found, hours_since_release, spread_rate
        FROM cineos_velocity
        ORDER BY film_title, scan_time DESC
    """)
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "title": r[0],
            "last_scan": str(r[1]),
            "platform_count": r[2],
            "hits_found": r[3],
            "hours_since_release": float(r[4] or 0),
            "spread_rate": float(r[5] or 0),
            "revenue_loss": estimate_revenue_loss(r[2] or 0, float(r[4] or 0))
        }
        for r in rows
    ]


async def run_velocity_scan(watchlist: list) -> None:
    """Run velocity scan for all films in watchlist."""
    log.info(f"Velocity scan: {len(watchlist)} films")

    try:
        conn = psycopg2.connect(DATABASE_URL)
    except Exception as e:
        log.error(f"DB connection error: {e}")
        return

    async with httpx.AsyncClient(
        headers=HEADERS, follow_redirects=True, timeout=15
    ) as client:
        for title in watchlist:
            log.info(f"Scanning: {title}")
            result = await scan_film_velocity(title, client)
            await store_velocity(result, conn)

            velocity_level = (
                "CRITICAL" if result["spread_rate"] > 0.5 else
                "HIGH" if result["spread_rate"] > 0.1 else
                "MEDIUM" if result["platform_count"] > 3 else
                "LOW"
            )

            log.info(
                f"{title}: {result['platform_count']} platforms, "
                f"{result['hits']} hits, "
                f"rate={result['spread_rate']}/hr, "
                f"velocity={velocity_level}"
            )
            await asyncio.sleep(1)

    # Print summary
    summary = get_velocity_summary(conn)
    print("\n" + "="*60)
    print("  CINEOS VELOCITY SUMMARY")
    print("="*60)
    for s in summary:
        hours = s["hours_since_release"]
        days = hours / 24
        print(f"\n  {s['title']}")
        print(f"  Platforms     : {s['platform_count']}")
        print(f"  Total hits    : {s['hits_found']}")
        print(f"  Time since release: {days:.0f} days ({hours:.0f}h)")
        print(f"  Spread rate   : {s['spread_rate']:.4f} platforms/hr")
        print(f"  Revenue loss  : ${s['revenue_loss']:,.0f}")

    conn.close()
    log.info("Velocity scan complete")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="CINEOS Velocity Tracker")
    ap.add_argument("--scan", action="store_true",
                    help="Run velocity scan")
    ap.add_argument("--summary", action="store_true",
                    help="Show velocity summary")
    ap.add_argument("--history", type=str,
                    help="Show history for a film")
    ap.add_argument("--films", nargs="+",
                    default=list(RELEASE_DATES.keys()),
                    help="Films to scan")
    args = ap.parse_args()

    if args.summary or args.history:
        conn = psycopg2.connect(DATABASE_URL)
        if args.history:
            history = get_velocity_history(args.history, conn)
            print(f"\nVelocity history: {args.history}")
            for h in history:
                print(f"  {h['scan_time'][:16]} — "
                      f"{h['platform_count']} platforms, "
                      f"{h['hits_found']} hits")
        else:
            summary = get_velocity_summary(conn)
            for s in summary:
                print(f"{s['title']}: {s['platform_count']} platforms, "
                      f"${s['revenue_loss']:,.0f} loss")
        conn.close()
    else:
        asyncio.run(run_velocity_scan(args.films))
