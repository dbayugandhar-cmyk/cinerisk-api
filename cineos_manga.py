#!/usr/bin/env python3
"""
CINEOS Manga & Publishing Anti-Piracy v1.0
==========================================
The world's first affordable manga/publishing piracy monitor.

Market: 66.4 billion piracy visits to publishing sites in 2024.
       70% of publishing piracy is manga.
       Zero affordable tools exist for indie manga creators.

Covers:
- Manga scan/scanlation sites (20+ sites)
- Webtoon piracy platforms
- Ebook piracy sites
- Comic piracy sites
- Light novel piracy
- NYAA anime/manga torrents

Target customers:
- Manga creators on Webtoon, Tapas, Lezhin ($29/month)
- Independent comic artists ($29/month)
- Light novel authors ($29/month)
- Publishers: VIZ Media, Kodansha, Shueisha ($499/month)
- Webtoon studios ($199/month)

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
    format="%(asctime)s [CINEOS-MANGA] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.manga")

SERP_KEY = os.getenv("SERP_API_KEY", "")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "Accept-Language": "en-US,en;q=0.5",
}

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def title_slug(title: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

def title_query(title: str) -> str:
    return title.lower().replace(' ', '+')

def title_matches(title: str, text: str, min_words: int = 1) -> bool:
    words = [w for w in title.lower().split() if len(w) > 2]
    if not words:
        return False
    matches = sum(1 for w in words if w in text.lower())
    return matches >= min(min_words, len(words))


# ── Content type keywords ─────────────────────────────────────────
PIRACY_KEYWORDS = {
    "manga": [
        "read manga", "manga online", "manga free", "scanlation",
        "scan group", "chapter free", "read online free",
        "raw manga", "manga raw", "translated manga",
    ],
    "webtoon": [
        "webtoon free", "manhwa free", "manhua free",
        "read webtoon", "episode free", "season free",
    ],
    "ebook": [
        "epub free", "pdf free", "ebook free", "download epub",
        "download pdf", "free ebook", "light novel free",
        "novel download", "book download free",
    ],
    "comic": [
        "read comics free", "comic download", "cbr free",
        "cbz free", "comic online free",
    ],
}

ALL_PIRACY_KEYWORDS = [kw for kws in PIRACY_KEYWORDS.values() for kw in kws]

def contains_piracy(text: str, content_type: str = "all") -> bool:
    t = text.lower()
    if content_type == "all":
        return any(k in t for k in ALL_PIRACY_KEYWORDS)
    return any(k in t for k in PIRACY_KEYWORDS.get(content_type, []))


# ── Legitimate platforms (false positive prevention) ─────────────
LEGITIMATE_PLATFORMS = [
    "mangaplus.shueisha.com", "viz.com", "crunchyroll.com",
    "webtoons.com", "tapas.io", "lezhin.com", "manta.net",
    "bookwalker.jp", "amazon.com/kindle", "comixology.com",
    "yen press.com", "sevensseasentertainment.com",
    "kodanshacomics.com", "viz.com", "shonenjump.com",
    "mangaplanet.com", "azukiapp.com",
    "wikipedia.org", "reddit.com", "youtube.com",
    "twitter.com", "x.com", "instagram.com",
    "goodreads.com", "myanimelist.net",
]

def is_legitimate(url: str) -> bool:
    u = url.lower()
    return any(s in u for s in LEGITIMATE_PLATFORMS)


# ── 25 Manga/Publishing Piracy Sites ─────────────────────────────
MANGA_SITES = [
    # Major manga scan sites
    {"name": "MangaDex",        "domain": "mangadex.org",        "type": "manga",   "priority": 1},
    {"name": "MangaReader",     "domain": "mangareader.to",      "type": "manga",   "priority": 1},
    {"name": "MangaFire",       "domain": "mangafire.to",        "type": "manga",   "priority": 1},
    {"name": "MangaKakalot",    "domain": "mangakakalot.com",    "type": "manga",   "priority": 1},
    {"name": "Manganelo",       "domain": "manganelo.com",       "type": "manga",   "priority": 1},
    {"name": "MangaPark",       "domain": "mangapark.net",       "type": "manga",   "priority": 2},
    {"name": "MangaOwl",        "domain": "mangaowl.net",        "type": "manga",   "priority": 2},
    {"name": "MangaGo",         "domain": "mangago.me",          "type": "manga",   "priority": 2},
    {"name": "Readmng",         "domain": "readmng.com",         "type": "manga",   "priority": 2},
    {"name": "MangaFox",        "domain": "fanfox.net",          "type": "manga",   "priority": 2},
    # Webtoon/Manhwa piracy
    {"name": "ToonilY",         "domain": "toonily.com",         "type": "webtoon", "priority": 1},
    {"name": "ManhwaFreak",     "domain": "manhwafreak.com",     "type": "webtoon", "priority": 2},
    {"name": "IsekaiScan",      "domain": "isekaiscan.com",      "type": "webtoon", "priority": 2},
    {"name": "ReaperScans",     "domain": "reaperscans.com",     "type": "webtoon", "priority": 2},
    {"name": "AsuraScans",      "domain": "asurascans.com",      "type": "webtoon", "priority": 2},
    # Ebook/Light novel piracy
    {"name": "LibGen",          "domain": "libgen.is",           "type": "ebook",   "priority": 1},
    {"name": "ZLibrary",        "domain": "z-lib.org",           "type": "ebook",   "priority": 1},
    {"name": "PDFDrive",        "domain": "pdfdrive.com",        "type": "ebook",   "priority": 2},
    {"name": "OpenLibrary",     "domain": "openlibrary.org",     "type": "ebook",   "priority": 2},
    {"name": "FreeEbooks",      "domain": "free-ebooks.net",     "type": "ebook",   "priority": 3},
    # Comic piracy
    {"name": "GetComics",       "domain": "getcomics.org",       "type": "comic",   "priority": 1},
    {"name": "ReadComics",      "domain": "readcomiconline.li",  "type": "comic",   "priority": 1},
    {"name": "ComicExtra",      "domain": "comicextra.com",      "type": "comic",   "priority": 2},
    # Torrent sites for manga
    {"name": "NYAA",            "domain": "nyaa.si",             "type": "manga",   "priority": 1},
    {"name": "MangaRaw",        "domain": "manga1001.top",       "type": "manga",   "priority": 2},
]


@dataclass
class MangaResult:
    platform: str
    content_type: str      # manga, webtoon, ebook, comic
    status: str            # HIT, CLEAN, ERROR, BLOCKED
    url: str = ""
    detail: str = ""
    chapter: str = ""      # Chapter number if found
    language: str = "EN"
    confidence: float = 0.0
    severity: str = "HIGH"


async def scan_site_serp(
    site: dict,
    title: str,
    client: httpx.AsyncClient
) -> MangaResult:
    """Scan site via SerpApi — bypasses Cloudflare."""
    if not SERP_KEY:
        return MangaResult(site["name"], site["type"],
                          "SKIPPED", detail="No SerpApi key")
    try:
        query = f'site:{site["domain"]} "{title}"'
        r = await client.get(
            "https://serpapi.com/search",
            params={
                "q": query,
                "api_key": SERP_KEY,
                "num": 3,
                "engine": "google",
            },
            timeout=12
        )
        if r.status_code != 200:
            return MangaResult(site["name"], site["type"],
                              "ERROR", detail=f"HTTP {r.status_code}")

        items = r.json().get("organic_results", [])

        for item in items:
            link = item.get("link", "")
            item_title = item.get("title", "")
            snippet = item.get("snippet", "")
            full = f"{item_title} {snippet}".lower()

            if is_legitimate(link):
                continue
            if not title_matches(title, full):
                continue

            # Detect chapter info
            chapter = ""
            ch_match = re.search(r'chapter\s*(\d+)', full)
            if ch_match:
                chapter = f"Chapter {ch_match.group(1)}"

            # Detect language
            language = "EN"
            if any(l in full for l in ["spanish", "español"]):
                language = "ES"
            elif any(l in full for l in ["french", "français"]):
                language = "FR"
            elif any(l in full for l in ["portuguese", "português"]):
                language = "PT"
            elif "raw" in full or "japanese" in full:
                language = "JP-RAW"
            elif "indonesian" in full or "bahasa" in full:
                language = "ID"

            return MangaResult(
                platform=site["name"],
                content_type=site["type"],
                status="HIT",
                url=link,
                detail=f"{item_title[:80]}",
                chapter=chapter,
                language=language,
                confidence=0.85,
                severity="HIGH"
            )

        return MangaResult(site["name"], site["type"],
                          "CLEAN", confidence=1.0)

    except asyncio.TimeoutError:
        return MangaResult(site["name"], site["type"],
                          "TIMEOUT")
    except Exception as e:
        return MangaResult(site["name"], site["type"],
                          "ERROR", detail=str(e)[:50])


async def scan_nyaa_direct(
    title: str,
    client: httpx.AsyncClient
) -> MangaResult:
    """Direct NYAA scan — best torrent source for manga."""
    try:
        r = await client.get(
            f"https://nyaa.si/?f=0&c=3_0&q={quote(title)}&s=date&o=desc",
            timeout=10, headers=HEADERS
        )
        if r.status_code == 200:
            body = r.text.lower()
            if title_matches(title, body):
                # Extract result count
                count_match = re.search(r'(\d+)\s+results?', body)
                count = count_match.group(1) if count_match else "?"
                return MangaResult(
                    platform="NYAA (Manga)",
                    content_type="manga",
                    status="HIT",
                    url=f"https://nyaa.si/?c=3_0&q={quote(title)}",
                    detail=f"NYAA: {count} manga torrents found for {title}",
                    confidence=0.80
                )
        return MangaResult("NYAA (Manga)", "manga", "CLEAN")
    except Exception as e:
        return MangaResult("NYAA (Manga)", "manga", "ERROR",
                          detail=str(e)[:50])


async def scan_libgen_direct(
    title: str,
    client: httpx.AsyncClient
) -> MangaResult:
    """LibGen direct scan — largest ebook piracy library."""
    try:
        r = await client.get(
            f"https://libgen.is/search.php?req={quote(title)}&lg_topic=comics",
            timeout=10, headers=HEADERS
        )
        if r.status_code == 200:
            body = r.text.lower()
            if title_matches(title, body, min_words=2):
                count_match = re.search(r'(\d+)\s+files', body)
                count = count_match.group(1) if count_match else "?"
                return MangaResult(
                    platform="LibGen",
                    content_type="ebook",
                    status="HIT",
                    url=f"https://libgen.is/search.php?req={quote(title)}",
                    detail=f"LibGen: {count} files found for {title}",
                    confidence=0.90
                )
        return MangaResult("LibGen", "ebook", "CLEAN")
    except Exception as e:
        return MangaResult("LibGen", "ebook", "ERROR",
                          detail=str(e)[:50])


async def scan_ddg_manga(
    title: str,
    content_type: str,
    client: httpx.AsyncClient
) -> list[MangaResult]:
    """DuckDuckGo scan for manga piracy — free, no quota."""
    results = []
    queries = {
        "manga": [
            f"{title} read manga online free",
            f"{title} manga scan english free chapter",
        ],
        "webtoon": [
            f"{title} read webtoon free online",
            f"{title} manhwa free episode",
        ],
        "ebook": [
            f"{title} epub free download",
            f"{title} pdf ebook free download",
        ],
        "comic": [
            f"{title} read comic free online",
            f"{title} comic download cbr cbz",
        ],
        "all": [
            f"{title} read free online piracy",
            f"{title} download free epub pdf manga",
        ],
    }

    query_list = queries.get(content_type, queries["all"])
    piracy_domains = [s["domain"].split(".")[0] for s in MANGA_SITES]
    piracy_domains += ["libgen", "zlibrary", "z-lib", "getcomics",
                       "nyaa", "mangakakalot", "manganelo"]

    for query in query_list:
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

                is_piracy_site = any(d in url.lower()
                                     for d in piracy_domains)
                has_piracy_signal = contains_piracy(combined, content_type)

                # Reject generic articles
                is_generic = any(x in url.lower() for x in [
                    "bestmanga", "top10", "best-sites", "where-to-read",
                    "reddit.com", "quora.com", "yahoo.com"
                ])

                # Require title in URL for piracy sites
                title_in_url = title_matches(title, url, min_words=1)

                # Reject homepage/search URLs — must be title-specific page
                is_homepage = (
                    url.rstrip('/').count('/') <= 2 or
                    url.endswith('/search/') or
                    url.endswith('/search') or
                    '?s=' in url or
                    '?q=' in url or
                    '/search?' in url
                )

                if (is_piracy_site and has_piracy_signal and
                        not is_generic and title_in_url and
                        not is_homepage):
                    if not any(res.url == url for res in results):
                        results.append(MangaResult(
                            platform=f"DDG: {url.split('/')[2][:25]}",
                            content_type=content_type,
                            status="HIT",
                            url=url,
                            detail=t[:80],
                            confidence=0.70
                        ))

            await asyncio.sleep(1)
        except Exception as e:
            log.warning(f"DDG manga scan error: {e}")

    return results


async def scan_internet_archive_manga(
    title: str,
    client: httpx.AsyncClient
) -> MangaResult:
    """Internet Archive scan for manga uploads."""
    try:
        r = await client.get(
            "https://archive.org/advancedsearch.php",
            params={
                "q": f'title:"{title}" AND (mediatype:texts OR mediatype:image)',
                "fl": "identifier,title,description,subject",
                "rows": 5, "output": "json"
            },
            timeout=10
        )
        if r.status_code == 200:
            docs = r.json().get("response", {}).get("docs", [])
            for doc in docs:
                doc_title = doc.get("title", "").lower()
                desc = doc.get("description", "").lower()
                subject = str(doc.get("subject", "")).lower()
                combined = f"{doc_title} {desc} {subject}"

                if title_matches(title, combined, min_words=2):
                    is_manga = any(k in combined for k in
                                  ["manga", "comic", "manhwa",
                                   "webtoon", "chapter"])
                    if is_manga:
                        iid = doc.get("identifier", "")
                        return MangaResult(
                            platform="Internet Archive",
                            content_type="manga",
                            status="HIT",
                            url=f"https://archive.org/details/{iid}",
                            detail=f"Archive: {doc.get('title', '')}",
                            confidence=0.75
                        )
        return MangaResult("Internet Archive", "manga", "CLEAN")
    except Exception as e:
        return MangaResult("Internet Archive", "manga", "ERROR",
                          detail=str(e)[:50])


async def full_manga_scan(
    title: str,
    content_type: str = "manga"
) -> dict:
    """
    Complete manga/publishing piracy scan.
    25 platforms + DDG + NYAA + LibGen + Archive.
    """
    log.info(f"Starting manga scan: {title} ({content_type})")

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=15
    ) as client:
        # Priority 1 sites
        p1 = [s for s in MANGA_SITES if s["priority"] == 1]
        p2 = [s for s in MANGA_SITES if s["priority"] == 2]
        p3 = [s for s in MANGA_SITES if s["priority"] == 3]

        # Scan in priority order
        p1_tasks = [scan_site_serp(s, title, client) for s in p1]
        p1_results = await asyncio.gather(*p1_tasks, return_exceptions=True)
        await asyncio.sleep(0.5)

        p2_tasks = [scan_site_serp(s, title, client) for s in p2]
        p2_results = await asyncio.gather(*p2_tasks, return_exceptions=True)
        await asyncio.sleep(0.5)

        p3_tasks = [scan_site_serp(s, title, client) for s in p3]
        p3_results = await asyncio.gather(*p3_tasks, return_exceptions=True)

        # Free scans
        nyaa_result, libgen_result, archive_result = await asyncio.gather(
            scan_nyaa_direct(title, client),
            scan_libgen_direct(title, client),
            scan_internet_archive_manga(title, client),
            return_exceptions=True
        )

        # DDG free scan
        ddg_results = await scan_ddg_manga(title, content_type, client)

    # Compile all results
    all_results = []
    for r in [*p1_results, *p2_results, *p3_results]:
        if isinstance(r, MangaResult):
            all_results.append(r)

    for r in [nyaa_result, libgen_result, archive_result]:
        if isinstance(r, MangaResult):
            all_results.append(r)

    all_results.extend(ddg_results)

    hits = [r for r in all_results if r.status == "HIT"]

    # Group by content type
    by_type = {}
    for h in hits:
        by_type.setdefault(h.content_type, []).append(h)

    # Group by language
    by_lang = {}
    for h in hits:
        by_lang.setdefault(h.language, []).append(h)

    verdict = "CONFIRMED" if hits else "CLEAN"

    log.info(f"Manga scan complete: {len(hits)} hits on "
             f"{len(all_results)} platforms")

    return {
        "title": title,
        "content_type": content_type,
        "verdict": verdict,
        "hits_found": len(hits),
        "platforms_scanned": len(all_results),
        "hits": hits,
        "by_type": {k: len(v) for k, v in by_type.items()},
        "by_language": {k: len(v) for k, v in by_lang.items()},
        "scanned_at": now_utc(),
    }


def generate_manga_report(
    result: dict,
    creator: str = "",
    publisher: str = "",
    contact_email: str = ""
) -> str:
    """
    Generate takedown notice for manga/publishing piracy.
    Covers DMCA + international copyright law.
    """
    title = result["title"]
    hits = result["hits"]
    now = result["scanned_at"]
    by_type = result.get("by_type", {})
    by_lang = result.get("by_language", {})

    urls_section = ""
    if hits:
        for i, h in enumerate(hits, 1):
            urls_section += f"\n  {i}. Platform    : {h.platform}"
            urls_section += f"\n     Type        : {h.content_type.upper()}"
            urls_section += f"\n     URL         : {h.url}"
            if h.chapter:
                urls_section += f"\n     Chapter     : {h.chapter}"
            urls_section += f"\n     Language    : {h.language}"
            urls_section += f"\n     Confidence  : {h.confidence*100:.0f}%"
            if h.detail:
                urls_section += f"\n     Detail      : {h.detail[:70]}"
            urls_section += "\n"
    else:
        urls_section = "  No infringing content detected."

    type_summary = "\n".join(
        f"  {t.upper()}: {c} platform(s)"
        for t, c in by_type.items()
    ) if by_type else "  None"

    lang_summary = "\n".join(
        f"  {l}: {c} instance(s)"
        for l, c in by_lang.items()
    ) if by_lang else "  None"

    return f"""
{"="*72}
  CINEOS MANGA & PUBLISHING — ANTI-PIRACY EVIDENCE REPORT v1.0
  Digital Millennium Copyright Act 17 U.S.C. § 512(c)(3)
  Berne Convention for the Protection of Literary and Artistic Works
  US Provisional Patent 64/049,190
{"="*72}

REPORT DETAILS
{"─"*72}
  Title           : {title}
  Creator         : {creator or "Rights Holder"}
  Publisher       : {publisher or "N/A"}
  Contact         : {contact_email or "N/A"}
  Content Type    : {result['content_type'].upper()}
  Report Date     : {now}
  Prepared by     : CINEOS Manga & Publishing Anti-Piracy Platform

{"="*72}
  VERDICT         : {result['verdict']}
  Platforms scanned: {result['platforms_scanned']}
  Infringing copies: {result['hits_found']}
{"="*72}

CONTENT TYPE BREAKDOWN
{"─"*72}
{type_summary}

LANGUAGE VERSIONS FOUND
{"─"*72}
{lang_summary}

SECTION 1 — IDENTIFICATION OF COPYRIGHTED WORK
[17 U.S.C. § 512(c)(3)(A)(ii) + Berne Convention Article 2]
{"─"*72}
  Title           : {title}
  Type            : {result['content_type'].upper()} / Literary/Artistic Work
  Rights Holder   : {creator or publisher or "The Copyright Owner"}
  Protection      : Automatic under Berne Convention (168 member countries)
                    Digital rights under 17 U.S.C. § 106 (exclusive rights)

SECTION 2 — INFRINGING MATERIAL AND URLS
[17 U.S.C. § 512(c)(3)(A)(iii)]
{"─"*72}
{urls_section}

SECTION 3 — CONTACT INFORMATION
[17 U.S.C. § 512(c)(3)(A)(iv)]
{"─"*72}
  Name            : Yugandhar Mallavarapu, CINEOS
  Organization    : CINEOS Manga & Publishing Anti-Piracy
  Email           : yugandhar@cineos.in
  Patent          : US Provisional Patent 64/049,190

SECTION 4 — ACCURACY DECLARATION
[17 U.S.C. § 512(c)(3)(A)(v) + (vi)]
{"─"*72}
  The information in this notification is accurate to the best of
  my knowledge. This report is provided for informational purposes.
  Rights holders should verify all findings and consult qualified
  legal counsel before filing DMCA takedown notices.

  Electronic Signature : /s/ Yugandhar Mallavarapu, CINEOS
  Date                 : {now}
  Capacity             : Anti-Piracy Detection Service (Monitoring Only)

RECOMMENDED ACTIONS
{"─"*72}
{"  1. Submit DMCA notices to each platform listed above" if hits else "  No action required — title is clean."}
{"  2. Contact platform DMCA agents directly for faster removal" if hits else ""}
{"  3. File with Google DMCA removal for search deindexing" if hits else ""}
{"  4. Contact scan group directly via DMCA for scanlation sites" if hits else ""}
{"  5. Consider legal counsel for repeat infringers" if len(hits) > 3 else ""}

{"="*72}
  CINEOS Manga & Publishing Anti-Piracy Platform
  25 platforms | Real-time | $29/month for creators
  yugandhar@cineos.in | US Prov. Pat. 64/049,190
  Supporting: Manga · Webtoon · Ebook · Comics · Light Novel
{"="*72}
"""


async def main(
    title: str,
    content_type: str = "manga",
    creator: str = "",
    publisher: str = "",
    email: str = ""
):
    """Main entry point."""
    print(f"\nCINEOS Manga & Publishing — Scanning: {title}")
    print(f"Content type: {content_type}")
    print("="*50)

    result = await full_manga_scan(title, content_type)
    report = generate_manga_report(result, creator, publisher, email)
    print(report)

    if result["hits"]:
        print("CONFIRMED HITS:")
        for h in result["hits"]:
            print(f"  [{h.content_type}] {h.platform} "
                  f"({h.language}) — {h.url[:60]}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="CINEOS Manga & Publishing Anti-Piracy"
    )
    ap.add_argument("--title", required=True,
                    help="Manga/book title to scan")
    ap.add_argument("--type", default="manga",
                    choices=["manga", "webtoon", "ebook", "comic", "all"],
                    help="Content type")
    ap.add_argument("--creator", default="",
                    help="Creator/author name")
    ap.add_argument("--publisher", default="",
                    help="Publisher name")
    ap.add_argument("--email", default="",
                    help="Contact email")
    ap.add_argument("--list-platforms", action="store_true",
                    help="List all monitored platforms")
    args = ap.parse_args()

    if args.list_platforms:
        print("\nCINEOS Manga & Publishing — Monitored Platforms:")
        for t in ["manga", "webtoon", "ebook", "comic"]:
            sites = [s for s in MANGA_SITES if s["type"] == t]
            print(f"\n  {t.upper()} ({len(sites)} sites):")
            for s in sites:
                print(f"    {s['name']:20} — {s['domain']}")
    else:
        asyncio.run(main(
            args.title, args.type,
            args.creator, args.publisher, args.email
        ))
