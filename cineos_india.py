#!/usr/bin/env python3
"""
CINEOS India — Regional Cinema Anti-Piracy
==========================================
Specialized monitoring for Indian film industry.

India loses $1.2 billion annually to piracy.
Tamil, Telugu, Malayalam, Hindi films pirated
within hours of release on Indian-specific platforms
that Western anti-piracy companies don't cover well.

20 Indian piracy platforms monitored.
Notices generated under Indian Copyright Act Section 51.
Pricing: Rs 5,000-15,000/month per title.

US Provisional Patent 64/049,190
"""

import asyncio
import httpx
import re
import json
import os
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CINEOS-INDIA] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.india")

SERP_KEY = os.getenv("SERP_API_KEY", "")
CINEOS_API = os.getenv("CINEOS_API", "https://cinerisk-api-production.up.railway.app")

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# ── Indian CAM keywords (multilingual) ────────────────────────────
CAM_KEYWORDS = [
    # English
    "camrip", "cam-rip", "hdcam", "hdts", "telesync",
    "source: camera", "line audio", "cam rip",
    # Transliterated Hindi/Tamil/Telugu
    "full movie", "watch online", "download free",
    "tamil dubbed", "telugu dubbed", "hindi dubbed",
    "malayalam", "kannada", "bengali",
    # Quality tags used in Indian releases
    "predvd", "pre-dvd", "dvdscr", "hq cam",
    "theater print", "theatre print",
    "theater print", "theatre print",
    # Digital rips — common in Indian piracy
    "hdrip", "hd rip", "dvdrip", "dvdscr", "webrip",
    "web-dl", "bluray", "480p", "720p", "1080p",
    "watch online free", "download free", "full movie",
]

def film_slug(title: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

@dataclass
class IndiaResult:
    platform: str
    language: str          # Hindi, Tamil, Telugu, Malayalam etc
    status: str            # HIT, CLEAN, ERROR, BLOCKED
    url: str = ""
    detail: str = ""
    quality: str = ""
    severity: str = "HIGH"


# ══════════════════════════════════════════════════════════════════
# 20 INDIAN PIRACY PLATFORMS
# ══════════════════════════════════════════════════════════════════

INDIAN_PLATFORMS = [
    # Pan-India platforms
    {"name": "Movierulz",      "domain": "5movierulz.camera",  "lang": "Pan-India"},
    {"name": "Filmyzilla",     "domain": "filmyzilla.com.co",  "lang": "Hindi/Bollywood"},
    {"name": "9xMovies",       "domain": "9xmovies.cool",      "lang": "Hindi/Bollywood"},
    {"name": "Bolly4u",        "domain": "bolly4u.trade",      "lang": "Hindi/Bollywood"},
    {"name": "MovieCounter",   "domain": "moviecounter.app",   "lang": "Hindi/Bollywood"},
    # South Indian platforms
    {"name": "TamilMV",        "domain": "tamilmv.fi",         "lang": "Tamil"},
    {"name": "TamilBlasters",  "domain": "tamilblasters.life", "lang": "Tamil"},
    {"name": "Ibomma",         "domain": "ibomma.com",         "lang": "Telugu"},
    {"name": "Isaimini",       "domain": "isaimini.com",       "lang": "Tamil"},
    {"name": "Kuttymovies",    "domain": "kuttymovies.com",    "lang": "Tamil"},
    {"name": "Tamilyogi",      "domain": "tamilyogi.wiki",     "lang": "Tamil"},
    {"name": "Moviesda",       "domain": "moviesda.com",       "lang": "Tamil"},
    {"name": "Cinevood",       "domain": "cinevood.com",       "lang": "Malayalam"},
    {"name": "Malayalamtorrents","domain": "mlwbd.com",        "lang": "Malayalam"},
    {"name": "Filmyhit",       "domain": "filmyhit.com.co",    "lang": "Punjabi/Hindi"},
    # Streaming piracy sites
    {"name": "HDHub4u",        "domain": "hdhub4u.com",        "lang": "Pan-India"},
    {"name": "Vegamovies",     "domain": "vegamovies.in",      "lang": "Pan-India"},
    {"name": "Filmy4wap",      "domain": "filmy4wap.com",      "lang": "Hindi/Bollywood"},
    {"name": "SkymoviesHD",    "domain": "skymovieshd.mov",    "lang": "Pan-India"},
    {"name": "Filmysplit",     "domain": "filmysplit.com",     "lang": "Pan-India"},
]


async def scan_indian_platform_via_serp(
    platform: dict, film: str, 
    client: httpx.AsyncClient
) -> IndiaResult:
    """Scan Indian platform via SerpApi — bypasses Cloudflare."""
    if not SERP_KEY:
        return IndiaResult(platform["name"], platform["lang"], "BLOCKED",
                          detail="No SerpApi key")
    try:
        query = f'site:{platform["domain"]} "{film}"'
        r = await client.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": SERP_KEY,
                    "num": 3, "engine": "google"},
            timeout=12
        )
        if r.status_code == 200:
            items = r.json().get("organic_results", [])
            fw = [w for w in film.lower().split() if len(w) > 2]
            for item in items:
                title = item.get("title", "")
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                full = f"{title} {snippet}".lower()
                film_ok = sum(1 for w in fw if w in full) >= min(2, len(fw))
                if film_ok and contains_cam(full):
                    return IndiaResult(
                        platform=platform["name"],
                        language=platform["lang"],
                        status="HIT",
                        url=link,
                        detail=f"{title[:80]}",
                        quality="CAM"
                    )
        return IndiaResult(platform["name"], platform["lang"], "CLEAN")
    except Exception as e:
        return IndiaResult(platform["name"], platform["lang"], "ERROR",
                          detail=str(e)[:50])


async def scan_all_indian_platforms(film: str) -> list[IndiaResult]:
    """Scan all 20 Indian platforms for a film."""
    log.info(f"Scanning 20 Indian platforms for: {film}")
    results = []
    
    async with httpx.AsyncClient(timeout=15, headers=HEADERS,
                                  follow_redirects=True) as client:
        # Batch in groups of 5 to avoid rate limits
        for i in range(0, len(INDIAN_PLATFORMS), 5):
            batch = INDIAN_PLATFORMS[i:i+5]
            tasks = [scan_indian_platform_via_serp(p, film, client) 
                    for p in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in batch_results:
                if isinstance(r, IndiaResult):
                    results.append(r)
            await asyncio.sleep(0.5)
    
    hits = [r for r in results if r.status == "HIT"]
    log.info(f"India scan complete: {len(hits)} hits across {len(results)} platforms")
    return results


def generate_india_report(film: str, results: list[IndiaResult],
                           producer: str = "", 
                           contact_email: str = "") -> str:
    """
    Generate DMCA notice under Indian Copyright Act Section 51.
    Also includes standard US DMCA elements for international filing.
    """
    now = now_utc()
    hits = [r for r in results if r.status == "HIT"]
    clean = [r for r in results if r.status == "CLEAN"]
    
    # Group hits by language
    by_lang = {}
    for h in hits:
        lang = h.language
        if lang not in by_lang:
            by_lang[lang] = []
        by_lang[lang].append(h)
    
    urls_section = ""
    if hits:
        for i, h in enumerate(hits, 1):
            urls_section += f"\n  {i}. Platform : {h.platform} ({h.language})\n"
            urls_section += f"     URL      : {h.url}\n"
            if h.detail:
                urls_section += f"     Detail   : {h.detail}\n"
            urls_section += f"     Quality  : {h.quality}\n"
    else:
        urls_section = "  No infringing content detected on Indian platforms."
    
    # Language breakdown
    lang_summary = ""
    for lang, lang_hits in by_lang.items():
        lang_summary += f"\n  {lang}: {len(lang_hits)} platform(s)"
    
    verdict = "CONFIRMED" if hits else "CLEAN"
    
    report = f"""
{"="*72}
  CINEOS INDIA — ANTI-PIRACY EVIDENCE REPORT
  Indian Copyright Act 1957, Section 51 + 17 U.S.C. § 512(c)(3)
  US Provisional Patent 64/049,190
{"="*72}

REPORT DETAILS
  Film Title    : {film}
  Report Date   : {now}
  Producer      : {producer or "Film Producer / Rights Holder"}
  Contact       : {contact_email or "N/A"}
  Prepared by   : CINEOS India Anti-Piracy Platform
  Coverage      : 20 Indian piracy platforms monitored

{"="*72}
  VERDICT: {verdict}
  Platforms scanned : {len(results)}
  Infringing copies : {len(hits)}
{"="*72}

SECTION 1 — COPYRIGHTED WORK
  [Indian Copyright Act 1957, Section 51 + 17 U.S.C. § 512(c)(3)(A)(ii)]
{"─"*72}
  Title         : {film}
  Type          : Theatrical motion picture
  Rights holder : {producer or "The Copyright Owner"}
  Infringement  : Unauthorized theatrical recording (CAM) and
                  distribution on Indian piracy platforms

SECTION 2 — INFRINGING MATERIAL AND URLS
  [Indian Copyright Act 1957, Section 51 + 17 U.S.C. § 512(c)(3)(A)(iii)]
{"─"*72}
  Total platforms scanned : {len(results)}
  CAM copies found        : {len(hits)}
  Language markets affected:{lang_summary if lang_summary else " None"}

{urls_section}

SECTION 3 — PLATFORMS CLEAN
{"─"*72}
  {", ".join([r.platform for r in clean[:10]])}{"..." if len(clean) > 10 else ""}

SECTION 4 — CONTACT INFORMATION
  [17 U.S.C. § 512(c)(3)(A)(iv)]
{"─"*72}
  Name          : Yugandhar Mallavarapu, CINEOS
  Organization  : CINEOS Anti-Piracy Platform
  Email         : dba.yugandhar@gmail.com
  Patent        : US Provisional Patent 64/049,190

SECTION 5 — GOOD FAITH BELIEF STATEMENT
  [17 U.S.C. § 512(c)(3)(A)(v)]
{"─"*72}
  I have a good faith belief that the use of the copyrighted material
  described above is not authorized by the copyright owner, its agent,
  or the law. The material constitutes an unauthorized theatrical
  recording made and distributed without license or authorization
  in violation of the Indian Copyright Act 1957, Section 51 and
  the Digital Millennium Copyright Act 17 U.S.C. § 512.

SECTION 6 — DECLARATION UNDER PENALTY OF PERJURY
  [17 U.S.C. § 512(c)(3)(A)(vi)]
{"─"*72}
  The information in this notification is accurate, and under penalty
  of perjury, I am authorized to act on behalf of the copyright owner.

  Electronic Signature : /s/ Yugandhar Mallavarapu, CINEOS
  Date                 : {now}
  Capacity             : Authorized Anti-Piracy Agent

RECOMMENDED ACTIONS
{"─"*72}
{"  STEP 1: File takedown notices to all platforms listed above" if hits else "  No action required — film is clean on Indian platforms."}
{"  STEP 2: File complaint with Cyber Crime Cell — cybercrime.gov.in" if hits else "  CINEOS will continue monitoring every 10 minutes."}
{"  STEP 3: Contact Internet Service Provider for site blocking" if hits else ""}
{"  STEP 4: File complaint with MIB — Ministry of Information & Broadcasting" if hits else ""}
{"  STEP 5: Contact CINEOS for theater-level attribution evidence" if hits else ""}

{"="*72}
  CINEOS India — Protecting Indian Cinema
  20 platforms | Real-time monitoring | Rs 5,000-15,000/month
  dba.yugandhar@gmail.com | US Prov. Pat. 64/049,190
{"="*72}
"""
    return report


async def india_scan_cli(film: str, producer: str = "", email: str = ""):
    """Full India scan with report."""
    print(f"\nCINEOS India — Scanning 20 platforms for: {film}")
    print("="*50)
    
    results = await scan_all_indian_platforms(film)
    report = generate_india_report(film, results, producer, email)
    print(report)
    
    hits = [r for r in results if r.status == "HIT"]
    if hits:
        print(f"\nHITS FOUND:")
        for h in hits:
            print(f"  {h.platform} ({h.language}): {h.url[:60]}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="CINEOS India — Indian Cinema Anti-Piracy")
    ap.add_argument("--film", required=True, help="Film title to scan")
    ap.add_argument("--producer", default="", help="Producer/studio name")
    ap.add_argument("--email", default="", help="Contact email for report")
    ap.add_argument("--list-platforms", action="store_true",
                    help="List all 20 monitored Indian platforms")
    args = ap.parse_args()
    
    if args.list_platforms:
        print("\nCINEOS India — 20 monitored platforms:")
        for p in INDIAN_PLATFORMS:
            print(f"  {p['name']:20} ({p['lang']}) — {p['domain']}")
    else:
        asyncio.run(india_scan_cli(args.film, args.producer, args.email))
