#!/usr/bin/env python3
"""
CINEOS Content Brand Shield v1.0
==================================
Content-focused brand protection for creators,
studios, labels, game developers, and sports leagues.

The gap: BrandShield serves physical product brands.
Nobody affordably serves content creators whose
brand/name/logo appears on piracy sites.

What we detect:
1. Brand name on piracy streaming sites
2. Artist/studio name on torrent sites  
3. Fake social media impersonation accounts
4. Domain squatting using brand names
5. Logo/name on crack sites (gaming)
6. Unauthorized merchandise using artist name
7. Fake apps using brand name on app stores
8. Brand name in phishing/scam ads

Target customers:
- Film studios ($499/month)
- Music labels ($299/month)
- Game developers ($199/month)
- Sports leagues ($999/month)
- Individual artists/creators ($49/month)
- Publishers ($299/month)

US Provisional Patent 64/049,190
"""

import asyncio
import httpx
import re
import os
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from urllib.parse import quote, unquote

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CINEOS-BRAND] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.content_brand")

SERP_KEY = os.getenv("SERP_API_KEY", "")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
}

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def name_matches(name: str, text: str) -> bool:
    words = [w for w in name.lower().split() if len(w) > 1]
    return sum(1 for w in words if w in text.lower()) >= min(2, len(words))


# ── Brand abuse signals ───────────────────────────────────────────
IMPERSONATION_SIGNALS = [
    "official", "real", "verified", "authentic",
    "original", "genuine", "legit", "legitimate",
    "fan page", "fanpage", "fan account",
    "not official", "unofficial fan",
]

PHISHING_SIGNALS = [
    "login", "sign in", "password", "account",
    "verify", "confirm", "update payment",
    "exclusive content", "free access",
    "limited offer", "click here",
]

PIRACY_BRAND_SIGNALS = [
    "free download", "watch free", "stream free",
    "full album free", "crack", "keygen",
    "serial key", "license key free",
    "torrent", "magnet link",
]

def is_impersonation(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in IMPERSONATION_SIGNALS)

def is_phishing(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in PHISHING_SIGNALS)

def is_piracy_brand_abuse(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in PIRACY_BRAND_SIGNALS)


# ── Platforms to monitor ──────────────────────────────────────────
PIRACY_PLATFORMS = [
    # Film piracy
    "fmovies.to", "gomovies.sx", "123movies.ai",
    "putlocker.vip", "soap2day.to", "watchsomuch.to",
    "flixhq.to", "myflixer.to", "hdtoday.cc",
    # Torrent sites
    "1337x.to", "torrentgalaxy.to", "yts.mx",
    "thepiratebay.org", "rarbg.to", "nyaa.si",
    # Music piracy
    "rutracker.org", "mp3juices.cc", "zaycev.net",
    # Gaming crack sites
    "fitgirl-repacks.site", "dodi-repacks.site",
    "igg-games.com", "steamunlocked.net",
    # Indian piracy
    "movierulz.com", "tamilmv.fi", "filmyzilla.com",
    # Sports streaming
    "crackstreams.com", "vipbox.lc", "hesgoal.com",
]

SOCIAL_PLATFORMS = [
    ("Instagram",  "instagram.com"),
    ("TikTok",     "tiktok.com"),
    ("Facebook",   "facebook.com"),
    ("Twitter/X",  "twitter.com"),
    ("YouTube",    "youtube.com"),
    ("Telegram",   "t.me"),
]

APP_STORES = [
    ("Google Play", "play.google.com"),
    ("APKPure",     "apkpure.com"),
    ("APKMirror",   "apkmirror.com"),
    ("HappyMod",    "happymod.com"),
]


@dataclass
class BrandAbuse:
    abuse_type: str     # PIRACY_USE, IMPERSONATION, PHISHING, DOMAIN_SQUAT, FAKE_APP
    platform: str
    url: str
    title: str = ""
    detail: str = ""
    confidence: float = 0.0
    severity: str = "HIGH"


async def scan_piracy_sites_for_brand(
    brand_name: str,
    client: httpx.AsyncClient
) -> list[BrandAbuse]:
    """
    Scan piracy sites for unauthorized use of brand name.
    Detects studios/labels/developers whose brand appears on piracy sites.
    """
    if not SERP_KEY:
        return []
    threats = []

    # Batch query — 10 piracy sites per SerpApi search
    batches = [PIRACY_PLATFORMS[i:i+10]
               for i in range(0, len(PIRACY_PLATFORMS), 10)]

    for batch in batches:
        site_query = " OR ".join(f"site:{s}" for s in batch)
        query = f'"{brand_name}" ({site_query})'

        try:
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": SERP_KEY,
                    "num": 10,
                    "engine": "google",
                },
                timeout=12
            )
            if r.status_code == 200:
                items = r.json().get("organic_results", [])
                for item in items:
                    link = item.get("link", "")
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    full = f"{title} {snippet}".lower()

                    if not name_matches(brand_name, full):
                        continue

                    # Determine severity
                    is_piracy = is_piracy_brand_abuse(full)
                    platform = link.split('/')[2] if '/' in link else link

                    threats.append(BrandAbuse(
                        abuse_type="PIRACY_USE",
                        platform=platform[:30],
                        url=link,
                        title=title[:80],
                        detail=snippet[:100],
                        confidence=0.80 if is_piracy else 0.60,
                        severity="HIGH"
                    ))

            await asyncio.sleep(0.3)
        except Exception as e:
            log.debug(f"Piracy brand scan error: {e}")

    return threats


async def scan_social_impersonation(
    brand_name: str,
    client: httpx.AsyncClient
) -> list[BrandAbuse]:
    """
    Detect fake social media accounts impersonating a brand.
    Finds fake Instagram/TikTok/Facebook pages using brand name.
    """
    if not SERP_KEY:
        return []
    threats = []

    for platform_name, domain in SOCIAL_PLATFORMS:
        try:
            query = (f'site:{domain} "{brand_name}" '
                     f'(official OR real OR verified OR fake)')
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": SERP_KEY,
                    "num": 5,
                    "engine": "google",
                },
                timeout=12
            )
            if r.status_code == 200:
                items = r.json().get("organic_results", [])
                for item in items:
                    link = item.get("link", "")
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    full = f"{title} {snippet}".lower()

                    if not name_matches(brand_name, full):
                        continue

                    # Check for impersonation signals
                    if is_impersonation(full) or is_phishing(full):
                        threats.append(BrandAbuse(
                            abuse_type="IMPERSONATION",
                            platform=platform_name,
                            url=link,
                            title=title[:80],
                            detail=snippet[:100],
                            confidence=0.75,
                            severity="CRITICAL"
                        ))

            await asyncio.sleep(0.3)
        except Exception as e:
            log.debug(f"Social impersonation scan error: {e}")

    return threats


async def scan_fake_apps(
    brand_name: str,
    client: httpx.AsyncClient
) -> list[BrandAbuse]:
    """
    Detect fake apps using brand name on app stores.
    Finds unauthorized APKs and cloned apps.
    """
    if not SERP_KEY:
        return []
    threats = []

    for store_name, domain in APP_STORES:
        try:
            query = f'site:{domain} "{brand_name}"'
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
            if r.status_code == 200:
                items = r.json().get("organic_results", [])
                for item in items:
                    link = item.get("link", "")
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    full = f"{title} {snippet}".lower()

                    if not name_matches(brand_name, full):
                        continue

                    # APKPure and HappyMod are always unauthorized
                    is_unauthorized = domain in [
                        "apkpure.com", "apkmirror.com",
                        "happymod.com"
                    ]

                    if is_unauthorized:
                        threats.append(BrandAbuse(
                            abuse_type="FAKE_APP",
                            platform=store_name,
                            url=link,
                            title=title[:80],
                            detail=f"Unauthorized app on {store_name}",
                            confidence=0.85,
                            severity="HIGH"
                        ))

            await asyncio.sleep(0.3)
        except Exception as e:
            log.debug(f"Fake app scan error: {e}")

    return threats


async def scan_domain_squatting(
    brand_name: str,
    client: httpx.AsyncClient
) -> list[BrandAbuse]:
    """
    Detect domain squatting using brand name.
    Finds fake websites using brand name in domain.
    """
    if not SERP_KEY:
        return []
    threats = []

    brand_slug = brand_name.lower().replace(' ', '')
    queries = [
        f'"{brand_name}" (site OR shop OR store OR free OR official) -{brand_slug}.com',
        f'inurl:{brand_slug} (fake OR free OR download OR unofficial)',
    ]

    for query in queries:
        try:
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": SERP_KEY,
                    "num": 5,
                    "engine": "google",
                },
                timeout=12
            )
            if r.status_code == 200:
                items = r.json().get("organic_results", [])
                for item in items:
                    link = item.get("link", "")
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    full = f"{title} {snippet} {link}".lower()

                    # Brand name must appear in domain
                    domain = link.split('/')[2] if '/' in link else ""
                    brand_in_domain = brand_slug in domain.lower()

                    if (brand_in_domain and
                            name_matches(brand_name, full) and
                            (is_phishing(full) or
                             is_piracy_brand_abuse(full))):
                        threats.append(BrandAbuse(
                            abuse_type="DOMAIN_SQUAT",
                            platform=domain[:30],
                            url=link,
                            title=title[:80],
                            detail=f"Brand name in domain: {domain}",
                            confidence=0.85,
                            severity="CRITICAL"
                        ))

            await asyncio.sleep(0.3)
        except Exception as e:
            log.debug(f"Domain squat scan error: {e}")

    return threats


async def scan_phishing_ads(
    brand_name: str,
    client: httpx.AsyncClient
) -> list[BrandAbuse]:
    """
    Detect phishing ads using brand name.
    Fake ads impersonating brand in Google/social media.
    """
    if not SERP_KEY:
        return []
    threats = []

    try:
        # Check Google Ads for brand impersonation
        r = await client.get(
            "https://serpapi.com/search",
            params={
                "q": brand_name,
                "api_key": SERP_KEY,
                "num": 10,
                "engine": "google",
            },
            timeout=12
        )
        if r.status_code == 200:
            # Check ads section
            ads = r.json().get("ads", [])
            organic = r.json().get("organic_results", [])

            for ad in ads:
                link = ad.get("link", "")
                title = ad.get("title", "")
                snippet = ad.get("description", "")
                full = f"{title} {snippet}".lower()

                brand_slug = brand_name.lower().replace(' ', '')
                domain = link.split('/')[2] if '/' in link else ""

                # Ad using brand name but different domain
                if (name_matches(brand_name, full) and
                        brand_slug not in domain.lower() and
                        is_phishing(full)):
                    threats.append(BrandAbuse(
                        abuse_type="PHISHING",
                        platform="Google Ads",
                        url=link,
                        title=title[:80],
                        detail=f"Phishing ad using brand name",
                        confidence=0.80,
                        severity="CRITICAL"
                    ))

    except Exception as e:
        log.debug(f"Phishing ads scan error: {e}")

    return threats


async def full_content_brand_scan(
    brand_name: str,
    brand_type: str = "general"
) -> dict:
    """
    Complete content brand protection scan.
    Covers piracy sites, social impersonation,
    fake apps, domain squatting, phishing ads.
    """
    log.info(f"Content brand scan: {brand_name} [{brand_type}]")

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=15
    ) as client:
        piracy, social, apps, domains, phishing = \
            await asyncio.gather(
                scan_piracy_sites_for_brand(brand_name, client),
                scan_social_impersonation(brand_name, client),
                scan_fake_apps(brand_name, client),
                scan_domain_squatting(brand_name, client),
                scan_phishing_ads(brand_name, client),
                return_exceptions=True
            )

    all_threats = []
    for r in [piracy, social, apps, domains, phishing]:
        if isinstance(r, list):
            all_threats.extend(r)

    # Group by type
    by_type = {}
    for t in all_threats:
        by_type.setdefault(t.abuse_type, []).append(t)

    critical = [t for t in all_threats if t.severity == "CRITICAL"]
    verdict = ("CRITICAL" if critical else
               "CONFIRMED" if all_threats else "CLEAN")

    log.info(f"Content brand scan: {len(all_threats)} threats")

    return {
        "brand": brand_name,
        "brand_type": brand_type,
        "verdict": verdict,
        "threats_found": len(all_threats),
        "critical_threats": len(critical),
        "threats": all_threats,
        "by_type": {k: len(v) for k, v in by_type.items()},
        "scanned_at": now_utc(),
    }


def generate_content_brand_report(
    result: dict,
    brand_owner: str = "",
    contact_email: str = ""
) -> str:
    """Generate content brand protection report."""
    brand = result["brand"]
    threats = result["threats"]
    now = result["scanned_at"]

    threats_section = ""
    if threats:
        for i, t in enumerate(threats, 1):
            threats_section += f"\n  {i}. Type       : {t.abuse_type}"
            threats_section += f"\n     Platform   : {t.platform}"
            threats_section += f"\n     Severity   : {t.severity}"
            threats_section += f"\n     URL        : {t.url}"
            threats_section += f"\n     Title      : {t.title[:60]}"
            threats_section += f"\n     Confidence : {t.confidence*100:.0f}%"
            threats_section += f"\n     Detail     : {t.detail[:60]}"
            threats_section += "\n"
    else:
        threats_section = "  No brand threats detected."

    by_type = result.get("by_type", {})
    type_summary = "\n".join(
        f"  {t}: {c}" for t, c in by_type.items()
    ) if by_type else "  None"

    return f"""
{"="*72}
  CINEOS CONTENT BRAND SHIELD — BRAND ABUSE REPORT v1.0
  Content Brand Protection for Creators & Studios
  US Provisional Patent 64/049,190
{"="*72}

  Brand           : {brand}
  Brand Type      : {result.get('brand_type', 'N/A')}
  Brand Owner     : {brand_owner or "Rights Holder"}
  Report Date     : {now}

{"="*72}
  VERDICT         : {result['verdict']}
  Threats found   : {result['threats_found']}
  Critical threats: {result['critical_threats']}
{"="*72}

THREAT BREAKDOWN
{"─"*72}
{type_summary}

DETAILED THREATS
{"─"*72}
{threats_section}

RECOMMENDED ACTIONS
{"─"*72}
{"  1. Report piracy use to each platform's IP team" if "PIRACY_USE" in by_type else ""}
{"  2. Report fake social accounts to platform trust & safety" if "IMPERSONATION" in by_type else ""}
{"  3. File DMCA with app stores for unauthorized apps" if "FAKE_APP" in by_type else ""}
{"  4. File UDRP complaint for domain squatting" if "DOMAIN_SQUAT" in by_type else ""}
{"  5. Report phishing ads to Google Ads policy team" if "PHISHING" in by_type else ""}
{"  No action required — brand is clean." if not threats else ""}

ACCURACY DECLARATION
{"─"*72}
  This report is for informational purposes only.
  Rights holders should verify findings and consult legal counsel.

  /s/ Yugandhar Mallavarapu, CINEOS
  Date: {now}
  Capacity: Brand Protection Detection Service (Monitoring Only)

{"="*72}
  CINEOS Content Brand Shield
  $49/month creators | $299/month labels | $999/month leagues
  dba.yugandhar@gmail.com | US Prov. Pat. 64/049,190
{"="*72}
"""


async def main(brand: str, brand_type: str = "general",
               owner: str = "", email: str = ""):
    print(f"\nCINEOS Content Brand Shield — {brand}")
    print("="*50)
    result = await full_content_brand_scan(brand, brand_type)
    report = generate_content_brand_report(result, owner, email)
    print(report)
    if result["threats"]:
        print("THREATS:")
        for t in result["threats"]:
            print(f"  [{t.severity}] {t.abuse_type} — {t.platform}")
            print(f"  {t.url[:65]}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="CINEOS Content Brand Shield")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--type", default="general",
                    choices=["film", "music", "gaming",
                             "sports", "creator", "general"])
    ap.add_argument("--owner", default="")
    ap.add_argument("--email", default="")
    args = ap.parse_args()
    asyncio.run(main(args.brand, args.type,
                     args.owner, args.email))
