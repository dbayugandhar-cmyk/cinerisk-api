#!/usr/bin/env python3
"""
CINEOS Music Anti-Piracy v1.0
==============================
The world's first affordable music piracy monitor for indie artists.

Market: 13.9 billion piracy visits in 2024
       $12.5 billion lost annually to music piracy
       Zero affordable tools for indie musicians

Covers:
- MP3 download sites (20+ sites)
- YouTube rip sites
- SoundCloud piracy
- Torrent sites for music
- Telegram music channels
- Russian music sites (VK, Zaycev)
- Free music download aggregators

Target customers:
- Indie musicians on Spotify/SoundCloud ($19/month)
- Record labels ($199/month)
- Music publishers ($99/month)
- Podcast creators ($19/month)

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
    format="%(asctime)s [CINEOS-MUSIC] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.music")

SERP_KEY = os.getenv("SERP_API_KEY", "")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "Accept-Language": "en-US,en;q=0.5",
}

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def title_matches(title: str, text: str, min_words: int = 1) -> bool:
    words = [w for w in title.lower().split() if len(w) > 2]
    if not words:
        return False
    return sum(1 for w in words if w in text.lower()) >= min(min_words, len(words))

# ── Music piracy keywords ─────────────────────────────────────────
PIRACY_KEYWORDS = [
    "mp3 free download", "free mp3", "download mp3",
    "free music download", "music download free",
    "flac free", "download flac", "free flac",
    "320kbps free", "download 320kbps",
    "zip download", "album download free",
    "discography download", "full album free",
    "mp3 skull", "mp3juice", "yt mp3",
    "youtube to mp3", "convert youtube",
    "leaked album", "album leak",
]

def contains_piracy(text: str) -> bool:
    return any(k in text.lower() for k in PIRACY_KEYWORDS)

# ── Legitimate music sites ────────────────────────────────────────
LEGITIMATE_SITES = [
    "spotify.com", "apple.com/music", "tidal.com",
    "soundcloud.com", "bandcamp.com", "deezer.com",
    "youtube.com", "music.youtube.com", "amazon.com/music",
    "pandora.com", "iheart.com", "last.fm",
    "genius.com", "allmusic.com", "discogs.com",
    "pitchfork.com", "rollingstone.com",
    "wikipedia.org", "reddit.com", "twitter.com",
]

def is_legitimate(url: str) -> bool:
    return any(s in url.lower() for s in LEGITIMATE_SITES)

# ── 25 Music Piracy Sites ─────────────────────────────────────────
MUSIC_SITES = [
    # MP3 download sites
    {"name": "MP3Juices",     "domain": "mp3juices.cc",      "priority": 1},
    {"name": "MP3Skull",      "domain": "mp3skull.com",      "priority": 1},
    {"name": "FreeMP3Cloud",  "domain": "freemp3cloud.com",  "priority": 1},
    {"name": "MP3Clan",       "domain": "mp3clan.com",       "priority": 1},
    {"name": "Zaycev",        "domain": "zaycev.net",        "priority": 1},
    {"name": "Prostopleer",   "domain": "prostopleer.com",   "priority": 2},
    {"name": "MP3Download",   "domain": "mp3download.to",    "priority": 2},
    {"name": "FreeMP3",       "domain": "freemp3.fm",        "priority": 2},
    {"name": "BeeMP3",        "domain": "beemp3.com",        "priority": 2},
    {"name": "SongsPK",       "domain": "songspk.name",      "priority": 2},
    # Torrent sites for music
    {"name": "RuTracker",     "domain": "rutracker.org",     "priority": 1},
    {"name": "NYAA Music",    "domain": "nyaa.si",           "priority": 1},
    {"name": "1337x Music",   "domain": "1337x.to",          "priority": 1},
    {"name": "TorrentGalaxy", "domain": "torrentgalaxy.to",  "priority": 2},
    # Russian/Eastern European music sites
    {"name": "VK Music",      "domain": "vk.com",            "priority": 1},
    {"name": "Zaycev.net",    "domain": "zaycev.net",        "priority": 1},
    # YouTube rip sites
    {"name": "Y2Mate",        "domain": "y2mate.com",        "priority": 1},
    {"name": "YTMP3",         "domain": "ytmp3.cc",          "priority": 2},
    {"name": "ConvertMP3",    "domain": "convertmp3.io",     "priority": 2},
    # Album download sites
    {"name": "Free-mp3-download", "domain": "free-mp3-download.net", "priority": 2},
    {"name": "AllMP3",        "domain": "allmp3.com",        "priority": 2},
    {"name": "MP3Raid",       "domain": "mp3raid.com",       "priority": 3},
    # Archive/sharing
    {"name": "Internet Archive Music", "domain": "archive.org", "priority": 2},
    # Telegram
    {"name": "Telegram Music", "domain": "t.me",             "priority": 2},
    # Indian music piracy
    {"name": "DJPunjab",      "domain": "djpunjab.com",      "priority": 2},
    {"name": "PagalWorld",    "domain": "pagalworld.com",    "priority": 2},
    {"name": "MrJatt",        "domain": "mrjatt.in",         "priority": 2},
]


@dataclass
class MusicResult:
    platform: str
    status: str
    url: str = ""
    detail: str = ""
    format: str = ""       # MP3, FLAC, ZIP, etc
    quality: str = ""      # 128kbps, 320kbps, lossless
    confidence: float = 0.0


async def scan_site_serp(
    site: dict,
    title: str,
    artist: str,
    client: httpx.AsyncClient
) -> MusicResult:
    """Scan music site via SerpApi."""
    if not SERP_KEY:
        return MusicResult(site["name"], "SKIPPED")
    try:
        query = f'site:{site["domain"]} "{title}" {artist} download'
        r = await client.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": SERP_KEY,
                    "num": 3, "engine": "google"},
            timeout=12
        )
        if r.status_code != 200:
            return MusicResult(site["name"], "ERROR",
                              detail=f"HTTP {r.status_code}")

        items = r.json().get("organic_results", [])
        for item in items:
            link = item.get("link", "")
            t = item.get("title", "")
            snippet = item.get("snippet", "")
            full = f"{t} {snippet}".lower()

            if is_legitimate(link):
                continue
            if not title_matches(title, full):
                continue

            # Detect format and quality
            fmt = "MP3"
            if "flac" in full: fmt = "FLAC"
            elif "zip" in full: fmt = "ZIP/Album"
            elif "320" in full: fmt = "MP3-320"

            quality = ""
            q_match = re.search(r'(\d+)\s*kbps', full)
            if q_match:
                quality = f"{q_match.group(1)}kbps"

            return MusicResult(
                platform=site["name"],
                status="HIT",
                url=link,
                detail=f"{t[:80]}",
                format=fmt,
                quality=quality,
                confidence=0.85
            )

        return MusicResult(site["name"], "CLEAN", confidence=1.0)

    except Exception as e:
        return MusicResult(site["name"], "ERROR", detail=str(e)[:50])


async def scan_ddg_music(
    title: str,
    artist: str,
    client: httpx.AsyncClient
) -> list[MusicResult]:
    """DuckDuckGo free scan for music piracy."""
    results = []
    queries = [
        f"{artist} {title} mp3 free download",
        f"{artist} {title} full album download free",
        f"{title} {artist} flac 320kbps download",
    ]

    piracy_domains = [s["domain"].split(".")[0] for s in MUSIC_SITES]
    piracy_domains += ["mp3", "flac", "music-download",
                       "freemusicdownload", "songdownload"]

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
            titles_raw = re.findall(r'result__a"[^>]+>([^<]+)</a>', body)

            for i, url in enumerate(urls[:15]):
                t = titles_raw[i % len(titles_raw)] if titles_raw else ""
                combined = (url + " " + t).lower()

                if is_legitimate(url):
                    continue
                if not title_matches(title, combined):
                    continue

                is_piracy = any(d in url.lower() for d in piracy_domains)
                has_signal = contains_piracy(combined)
                is_homepage = url.rstrip('/').count('/') <= 2
                is_generic = any(x in url.lower() for x in [
                    "best-sites", "top-10", "how-to",
                    "reddit.com", "quora.com"
                ])
                title_in_url = title_matches(title, url, min_words=1)

                if (is_piracy or has_signal) and not is_homepage \
                        and not is_generic and title_in_url:
                    if not any(res.url == url for res in results):
                        fmt = "FLAC" if "flac" in combined else "MP3"
                        results.append(MusicResult(
                            platform=f"DDG: {url.split('/')[2][:25]}",
                            status="HIT",
                            url=url,
                            detail=t[:80],
                            format=fmt,
                            confidence=0.70
                        ))

            await asyncio.sleep(1)
        except Exception as e:
            log.warning(f"DDG music error: {e}")

    return results


async def scan_rutracker(
    title: str,
    artist: str,
    client: httpx.AsyncClient
) -> MusicResult:
    """RuTracker — largest music torrent site."""
    if not SERP_KEY:
        return MusicResult("RuTracker", "SKIPPED")
    try:
        r = await client.get(
            "https://serpapi.com/search",
            params={
                "q": f'site:rutracker.org "{artist}" "{title}"',
                "api_key": SERP_KEY,
                "num": 3,
                "engine": "google"
            },
            timeout=12
        )
        if r.status_code == 200:
            items = r.json().get("organic_results", [])
            for item in items:
                t = item.get("title", "")
                link = item.get("link", "")
                if title_matches(title, t) and artist.lower() in t.lower():
                    return MusicResult(
                        platform="RuTracker",
                        status="HIT",
                        url=link,
                        detail=t[:80],
                        format="FLAC/MP3",
                        confidence=0.90
                    )
        return MusicResult("RuTracker", "CLEAN")
    except Exception as e:
        return MusicResult("RuTracker", "ERROR", detail=str(e)[:50])


async def scan_vk_music(
    title: str,
    artist: str,
    client: httpx.AsyncClient
) -> MusicResult:
    """VK.com — scan via SerpApi only, not direct (always returns 200)."""
    if not SERP_KEY:
        return MusicResult("VK Music", "SKIPPED")
    try:
        r = await client.get(
            "https://serpapi.com/search",
            params={
                "q": f'site:vk.com "{artist}" "{title}" mp3',
                "api_key": SERP_KEY,
                "num": 3,
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
                if (title_matches(title, full) and
                        title_matches(artist, full) and
                        "audio" in link.lower()):
                    return MusicResult(
                        platform="VK Music",
                        status="HIT",
                        url=link,
                        detail=t[:80],
                        format="MP3",
                        confidence=0.85
                    )
        return MusicResult("VK Music", "CLEAN")
    except Exception as e:
        return MusicResult("VK Music", "ERROR", detail=str(e)[:50])


async def full_music_scan(
    title: str,
    artist: str = ""
) -> dict:
    """Complete music piracy scan."""
    log.info(f"Scanning: {artist} - {title}")

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=15
    ) as client:
        # Priority 1 sites
        p1 = [s for s in MUSIC_SITES if s["priority"] == 1]
        p2 = [s for s in MUSIC_SITES if s["priority"] == 2]

        p1_tasks = [scan_site_serp(s, title, artist, client)
                    for s in p1]
        p1_results = await asyncio.gather(*p1_tasks,
                                          return_exceptions=True)
        await asyncio.sleep(0.5)

        p2_tasks = [scan_site_serp(s, title, artist, client)
                    for s in p2]
        p2_results = await asyncio.gather(*p2_tasks,
                                          return_exceptions=True)

        # Free scans
        vk_result, ddg_results = await asyncio.gather(
            scan_vk_music(title, artist, client),
            scan_ddg_music(title, artist, client),
            return_exceptions=True
        )

    all_results = []
    for r in [*p1_results, *p2_results]:
        if isinstance(r, MusicResult):
            all_results.append(r)
    if isinstance(vk_result, MusicResult):
        all_results.append(vk_result)
    if isinstance(ddg_results, list):
        all_results.extend(ddg_results)

    hits = [r for r in all_results if r.status == "HIT"]
    formats = list(set(h.format for h in hits if h.format))

    verdict = "CONFIRMED" if hits else "CLEAN"
    log.info(f"Music scan complete: {len(hits)} hits")

    return {
        "title": title,
        "artist": artist,
        "verdict": verdict,
        "hits_found": len(hits),
        "platforms_scanned": len(all_results),
        "hits": hits,
        "formats_found": formats,
        "scanned_at": now_utc(),
    }


def generate_music_report(
    result: dict,
    label: str = "",
    contact_email: str = ""
) -> str:
    """Generate music piracy evidence report."""
    title = result["title"]
    artist = result["artist"]
    hits = result["hits"]
    now = result["scanned_at"]
    formats = result.get("formats_found", [])

    urls_section = ""
    if hits:
        for i, h in enumerate(hits, 1):
            urls_section += f"\n  {i}. Platform  : {h.platform}"
            urls_section += f"\n     URL       : {h.url}"
            urls_section += f"\n     Format    : {h.format or 'Unknown'}"
            if h.quality:
                urls_section += f"\n     Quality   : {h.quality}"
            urls_section += f"\n     Confidence: {h.confidence*100:.0f}%"
            if h.detail:
                urls_section += f"\n     Detail    : {h.detail[:70]}"
            urls_section += "\n"
    else:
        urls_section = "  No infringing content detected."

    return f"""
{"="*72}
  CINEOS MUSIC — ANTI-PIRACY EVIDENCE REPORT v1.0
  17 U.S.C. § 512(c)(3) | DMCA Safe Harbor
  US Provisional Patent 64/049,190
{"="*72}

  Artist          : {artist or "Rights Holder"}
  Title           : {title}
  Label           : {label or "Independent"}
  Report Date     : {now}
  Prepared by     : CINEOS Music Anti-Piracy Platform

{"="*72}
  VERDICT         : {result['verdict']}
  Platforms scanned: {result['platforms_scanned']}
  Infringing copies: {result['hits_found']}
  Formats found   : {', '.join(formats) if formats else 'None'}
{"="*72}

INFRINGING MATERIAL
{"─"*72}
{urls_section}

ACCURACY DECLARATION
{"─"*72}
  The information in this report is accurate to the best of my
  knowledge. This report is provided for informational purposes.
  Rights holders should verify findings and consult legal counsel
  before filing DMCA notices.

  /s/ Yugandhar Mallavarapu, CINEOS
  Date: {now}
  Capacity: Anti-Piracy Detection Service (Monitoring Only)

{"="*72}
  CINEOS Music Anti-Piracy | $19/month per artist
  yugandhar@cineos.in | US Prov. Pat. 64/049,190
{"="*72}
"""


async def main(title: str, artist: str = "",
               label: str = "", email: str = ""):
    print(f"\nCINEOS Music — Scanning: {artist} - {title}")
    print("="*50)
    result = await full_music_scan(title, artist)
    report = generate_music_report(result, label, email)
    print(report)
    if result["hits"]:
        print("HITS:")
        for h in result["hits"]:
            print(f"  [{h.format}] {h.platform} — {h.url[:60]}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="CINEOS Music Anti-Piracy")
    ap.add_argument("--title", required=True)
    ap.add_argument("--artist", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--email", default="")
    args = ap.parse_args()
    asyncio.run(main(args.title, args.artist,
                     args.label, args.email))
