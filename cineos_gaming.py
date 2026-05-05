#!/usr/bin/env python3
"""
CINEOS Gaming — Indie Game Anti-Piracy Monitor
===============================================
Same infrastructure as film scanner.
Target: Indie game developers on Steam, Epic, itch.io
Price: $99/month per game

Nobody serves this market affordably.
FitGirl, DODI, CPY, EMPRESS crack sites monitored.
US Provisional Patent 64/049,190
"""

import asyncio
import httpx
import re
import os
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from urllib.parse import unquote

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CINEOS-GAMING] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.gaming")

SERP_KEY = os.getenv("SERP_API_KEY", "")
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# ── Known game crack sites and groups ────────────────────────────
CRACK_SITES = [
    "fitgirl-repacks.site",
    "fitgirl-repacks.net", 
    "dodi-repacks.site",
    "gog-games.to",
    "cs.rin.ru",
    "skidrowreloaded.com",
    "skidrowcodex.net",
    "oceanofgames.com",
    "igg-games.com",
    "crackwatch.com",
    "steamunlocked.net",
    "gamesrepacks.com",
    "repack-games.com",
    "pcgamestorrents.com",
    "gametrex.com",
    "1337x.to",
    "torrentgalaxy.to",
    "rarbg.to",
    "nyaa.si",
    "scene-rls.com",
]

# ── Crack keywords ────────────────────────────────────────────────
CRACK_KEYWORDS = [
    "crack", "cracked", "repack", "fitgirl", "dodi",
    "cpy", "empress", "codex", "skidrow", "reloaded",
    "free download", "full version", "torrent",
    "plaza", "hoodlum", "prophet", "razor1911",
    "steamunlocked", "igg", "ocean of games",
    "gog rip", "unlocked", "drm free pirate",
    "scene release", "nfo",
]

def contains_crack(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in CRACK_KEYWORDS)

def is_crack_site(url: str) -> bool:
    u = url.lower()
    return any(d in u for d in CRACK_SITES)

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@dataclass
class GameResult:
    platform: str
    status: str
    url: str = ""
    detail: str = ""
    crack_group: str = ""
    severity: str = "HIGH"


# ── Detect crack group from URL/title ─────────────────────────────
def detect_crack_group(text: str) -> str:
    groups = {
        "FitGirl": ["fitgirl"],
        "DODI": ["dodi"],
        "CPY": ["-cpy", "cpy crack"],
        "EMPRESS": ["empress"],
        "CODEX": ["-codex", "codex crack"],
        "SKIDROW": ["skidrow"],
        "RELOADED": ["-reloaded"],
        "PLAZA": ["-plaza"],
        "HOODLUM": ["-hoodlum"],
        "PROPHET": ["-prophet"],
        "RAZOR1911": ["razor1911"],
        "SteamUnlocked": ["steamunlocked"],
        "IGG": ["igg-games"],
        "GOG-Games": ["gog-games"],
    }
    t = text.lower()
    for group, keywords in groups.items():
        if any(k in t for k in keywords):
            return group
    return "Unknown"


# ── DuckDuckGo scan for game cracks ──────────────────────────────
async def scan_ddg_gaming(game: str,
                           client: httpx.AsyncClient) -> list[GameResult]:
    """Scan DuckDuckGo for cracked game releases. Free, no API key."""
    results = []
    queries = [
        f"{game} crack download free PC",
        f"{game} repack fitgirl DODI torrent",
        f"{game} steamunlocked free full version",
    ]

    for query in queries:
        try:
            r = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                timeout=12,
                headers=HEADERS
            )
            if r.status_code != 200:
                continue

            body = r.text
            urls = [unquote(u) for u in
                    re.findall(r'uddg=(https?[^&"]+)', body)]
            titles = re.findall(r'result__a"[^>]+>([^<]+)</a>', body)

            gw = [w for w in game.lower().split() if len(w) > 2]

            for i, url in enumerate(urls[:15]):
                title = titles[i % len(titles)] if titles else ""
                combined = (url + " " + title).lower()
                game_ok = sum(1 for w in gw if w in combined) >= min(1, len(gw))

                # Must be actual crack site — not news/youtube/reddit about cracks
                actual_crack = is_crack_site(url)
                legit_sites = ["youtube.com", "reddit.com", "express.co.uk",
                               "steam", "ccm.net", "pcgamer", "ign.com",
                               "kotaku", "polygon", "eurogamer", "gamespot",
                               "wikipedia", "twitter", "facebook", "instagram"]
                is_legit = any(s in url.lower() for s in legit_sites)
                
                if game_ok and actual_crack and not is_legit:
                    if not any(r.url == url for r in results):
                        group = detect_crack_group(combined)
                        results.append(GameResult(
                            platform="DuckDuckGo",
                            status="HIT",
                            url=url,
                            detail=title[:80],
                            crack_group=group
                        ))

            await asyncio.sleep(1)
        except Exception as e:
            log.warning(f"DDG gaming scan failed: {e}")

    return results


# ── SerpApi scan for specific crack sites ─────────────────────────
async def scan_serp_gaming(game: str,
                            client: httpx.AsyncClient) -> list[GameResult]:
    """SerpApi scan targeting known crack sites directly."""
    if not SERP_KEY:
        return []

    results = []
    top_sites = [
        "fitgirl-repacks.site",
        "dodi-repacks.site",
        "steamunlocked.net",
        "igg-games.com",
        "gog-games.to",
    ]

    for site in top_sites:
        try:
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": f'site:{site} "{game}"',
                    "api_key": SERP_KEY,
                    "num": 3,
                    "engine": "google"
                },
                timeout=12
            )
            if r.status_code == 200:
                items = r.json().get("organic_results", [])
                gw = [w for w in game.lower().split() if len(w) > 2]
                for item in items:
                    title = item.get("title", "")
                    link = item.get("link", "")
                    combined = (title + " " + link).lower()
                    game_ok = sum(1 for w in gw
                                  if w in combined) >= min(1, len(gw))
                    if game_ok:
                        group = detect_crack_group(combined)
                        results.append(GameResult(
                            platform=f"SerpApi ({site})",
                            status="HIT",
                            url=link,
                            detail=title[:80],
                            crack_group=group
                        ))
            await asyncio.sleep(0.3)
        except Exception as e:
            log.warning(f"SerpApi gaming scan error: {e}")

    return results


# ── SRRDB scene database scan ─────────────────────────────────────
async def scan_srrdb_gaming(game: str,
                             client: httpx.AsyncClient) -> list[GameResult]:
    """SRRDB scene release database — catches scene releases early."""
    try:
        slug = re.sub(r'[^a-z0-9]+', '.', game.lower()).strip('.')
        r = await client.get(
            f"https://www.srrdb.com/api/search/r:{slug}*",
            timeout=10,
            headers=HEADERS
        )
        if r.status_code == 200:
            items = r.json().get("results", [])
            gw = [w for w in game.lower().split() if len(w) > 2]
            for item in items:
                release = item.get("release", "")
                if sum(1 for w in gw
                       if w in release.lower()) >= min(1, len(gw)):
                    group = detect_crack_group(release)
                    return [GameResult(
                        platform="SRRDB Scene DB",
                        status="HIT",
                        url=f"https://www.srrdb.com/release/details/{release}",
                        detail=f"Scene release: {release}",
                        crack_group=group
                    )]
        return []
    except Exception as e:
        return []


# ── PreDB scan ────────────────────────────────────────────────────
async def scan_predb_gaming(game: str,
                             client: httpx.AsyncClient) -> list[GameResult]:
    """PreDB — scene release pre-database. Catches within minutes."""
    try:
        slug = game.replace(' ', '+')
        r = await client.get(
            f"https://predb.ovh/api/v1/?q={slug}&count=5",
            timeout=10,
            headers=HEADERS
        )
        if r.status_code == 200:
            rows = r.json().get("rows", [])
            gw = [w for w in game.lower().split() if len(w) > 2]
            for row in rows:
                name = row.get("name", "").lower()
                cat = row.get("cat", "").lower()
                if ("game" in cat or "iso" in cat) and \
                   sum(1 for w in gw if w in name) >= min(1, len(gw)):
                    group = detect_crack_group(name)
                    return [GameResult(
                        platform="PreDB",
                        status="HIT",
                        url=f"https://predb.ovh/?q={slug}",
                        detail=f"Scene pre-release: {row.get('name', '')}",
                        crack_group=group
                    )]
        return []
    except Exception as e:
        return []


# ── Full game scan ────────────────────────────────────────────────
async def full_game_scan(game: str) -> dict:
    """Complete game piracy scan across all sources."""
    log.info(f"Scanning for cracked copy of: {game}")

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=15
    ) as client:
        ddg_results, serp_results, srrdb_results, predb_results = \
            await asyncio.gather(
                scan_ddg_gaming(game, client),
                scan_serp_gaming(game, client),
                scan_srrdb_gaming(game, client),
                scan_predb_gaming(game, client),
                return_exceptions=True
            )

    all_hits = []
    for results in [ddg_results, serp_results, srrdb_results, predb_results]:
        if isinstance(results, list):
            all_hits.extend([r for r in results if r.status == "HIT"])

    # Deduplicate by URL
    seen = set()
    unique_hits = []
    for h in all_hits:
        if h.url not in seen:
            seen.add(h.url)
            unique_hits.append(h)

    verdict = "CONFIRMED" if unique_hits else "CLEAN"
    crack_groups = list(set(h.crack_group for h in unique_hits
                            if h.crack_group != "Unknown"))

    return {
        "game": game,
        "verdict": verdict,
        "hits_found": len(unique_hits),
        "crack_groups": crack_groups,
        "hits": unique_hits,
        "scanned_at": now_utc(),
    }


def generate_game_report(result: dict,
                          developer: str = "",
                          email: str = "") -> str:
    """Generate DMCA report for game piracy."""
    hits = result["hits"]
    game = result["game"]
    now = result["scanned_at"]
    groups = result["crack_groups"]

    urls_section = ""
    if hits:
        for i, h in enumerate(hits, 1):
            urls_section += f"\n  {i}. Platform    : {h.platform}\n"
            urls_section += f"     URL        : {h.url}\n"
            if h.crack_group != "Unknown":
                urls_section += f"     Crack group: {h.crack_group}\n"
            if h.detail:
                urls_section += f"     Detail     : {h.detail[:60]}\n"
    else:
        urls_section = "  No infringing content detected."

    report = f"""
{"="*70}
  CINEOS GAMING — ANTI-PIRACY EVIDENCE REPORT
  17 U.S.C. § 512(c)(3) | US Provisional Patent 64/049,190
{"="*70}

  Game Title    : {game}
  Developer     : {developer or "Game Developer / Rights Holder"}
  Report Date   : {now}
  Prepared by   : CINEOS Gaming Anti-Piracy Platform

{"="*70}
  VERDICT: {result['verdict']}
  Cracked copies found : {result['hits_found']}
  Crack groups detected: {', '.join(groups) if groups else 'None'}
{"="*70}

SECTION 1 — COPYRIGHTED WORK  [17 U.S.C. § 512(c)(3)(A)(ii)]
{"─"*70}
  Title         : {game}
  Type          : Commercial video game / software
  Rights holder : {developer or "The Copyright Owner"}
  Infringement  : Unauthorized cracking, repackaging, and distribution

SECTION 2 — INFRINGING MATERIAL  [17 U.S.C. § 512(c)(3)(A)(iii)]
{"─"*70}
{urls_section}

SECTION 3 — CONTACT INFORMATION  [17 U.S.C. § 512(c)(3)(A)(iv)]
{"─"*70}
  Name          : Yugandhar Mallavarapu, CINEOS
  Organization  : CINEOS Gaming Anti-Piracy Platform
  Email         : dba.yugandhar@gmail.com
  Patent        : US Provisional Patent 64/049,190

SECTION 4 — GOOD FAITH BELIEF  [17 U.S.C. § 512(c)(3)(A)(v)]
{"─"*70}
  I have a good faith belief that the use of the copyrighted material
  described above is not authorized by the copyright owner, its agent,
  or the law.

SECTION 5 — DECLARATION UNDER PENALTY OF PERJURY
{"─"*70}
  The information in this notification is accurate, and under penalty
  of perjury, I am authorized to act on behalf of the copyright owner.

  Electronic Signature : /s/ Yugandhar Mallavarapu, CINEOS
  Date                 : {now}
  Capacity             : Authorized Anti-Piracy Agent

RECOMMENDED ACTIONS
{"─"*70}
{"  1. File DMCA notices to all platforms listed above" if hits else "  No action required — game is clean."}
{"  2. Contact Steam/Epic anti-piracy team with this report" if hits else ""}
{"  3. Request takedown from crack group directly via DMCA" if hits else ""}
{"  4. Contact CINEOS for ongoing monitoring at $99/month" if hits else ""}

{"="*70}
  CINEOS Gaming — Protecting Indie Developers
  $99/month per game | Real-time monitoring | DMCA reports
  dba.yugandhar@gmail.com | US Prov. Pat. 64/049,190
{"="*70}
"""
    return report


async def main(game: str, developer: str = "", email: str = ""):
    print(f"\nCINEOS Gaming Anti-Piracy — Scanning: {game}")
    print("="*50)

    result = await full_game_scan(game)
    report = generate_game_report(result, developer, email)
    print(report)

    if result["hits"]:
        print(f"\nDETAILED HITS:")
        for h in result["hits"]:
            print(f"\n  {h.platform} | Group: {h.crack_group}")
            print(f"  {h.url[:75]}")
            print(f"  {h.detail[:65]}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="CINEOS Gaming — Game Anti-Piracy Monitor"
    )
    ap.add_argument("--game", required=True, help="Game title to scan")
    ap.add_argument("--developer", default="", help="Developer/studio name")
    ap.add_argument("--email", default="", help="Contact email")
    args = ap.parse_args()
    asyncio.run(main(args.game, args.developer, args.email))
