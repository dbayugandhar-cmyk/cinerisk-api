#!/usr/bin/env python3
"""
CINEOS Live Shield v1.0
========================
Real-time Telegram cricket stream monitor.
Detects illegal IPL/cricket streams within 60 seconds.

The gap IBCAP misses:
- Telegram channels respawn within minutes of takedown
- Regional language streams (Tamil/Telugu/Kannada) unmonitored
- Illegal betting apps streaming inside gambling interfaces
- New channels created during match not detected fast enough

CINEOS Live Shield:
- Monitors 500+ Telegram channels in real time
- Detects new streams within 60 seconds of going live
- Identifies commentary language automatically
- Tracks subscriber count and growth velocity
- Alerts rights holders instantly via webhook
- Works during the match — not after

Target customers:
- JioStar/JioHotstar — IPL rights $6.4 billion
- BCCI — cricket rights protection
- Star Sports — Premier League India rights
- Sony LIV — cricket streaming rights
- ICC — global cricket rights

Price: $50,000/tournament or $5,000/month
Revenue: 3 customers = $150,000/tournament

US Provisional Patent 64/049,190
"""

import asyncio
import httpx
import re
import os
import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CINEOS-LIVE] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cineos.live")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ── Language detection ────────────────────────────────────────────
LANGUAGE_KEYWORDS = {
    "Tamil":    ["தமிழ்", "tamil", "tamilnadu", "chennai", "csk"],
    "Telugu":   ["తెలుగు", "telugu", "hyderabad", "srh", "rcb తెలుగు"],
    "Hindi":    ["हिंदी", "hindi", "हिन्दी", "mumbai", "mi ", "kkr"],
    "Kannada":  ["ಕನ್ನಡ", "kannada", "bangalore", "rcb kannada"],
    "Malayalam":["മലയാളം", "malayalam", "kerala", "kochi"],
    "Bengali":  ["বাংলা", "bengali", "kolkata", "kkr bengali"],
    "English":  ["english", "live stream", "watch live", "free stream"],
}

PIRACY_SIGNALS = [
    "live stream", "watch live", "free stream", "hd stream",
    "ipl live", "cricket live", "t20 live", "match live",
    "streaming now", "live now", "watch now", "stream link",
    "join now", "free watch", "live cricket", "ipl 2025",
    "ipl 2026", "cricket match", "t20 match",
    # Indian language signals
    "லைவ்", "நேரலை",  # Tamil
    "లైవ్", "ప్రత్యక్ష",  # Telugu
    "लाइव", "सीधा प्रसारण",  # Hindi
]

BETTING_SIGNALS = [
    "1xbet", "bet365", "betway", "reddy anna", "khelo",
    "cricket betting", "place bet", "win money", "odds",
    "satta", "matka", "betting app", "96win", "sat sport",
]

# Known Telegram channel patterns — India OTT + Sports piracy
# Expanded to cover all major Indian OTT platforms and sports

# ── Auto-save discovered channels ────────────────────
import json as _json
DISCOVERED_CHANNELS_FILE = "cineos_discovered_channels.json"

def load_discovered_channels():
    """Load previously auto-saved channels from disk."""
    try:
        with open(DISCOVERED_CHANNELS_FILE) as f:
            data = _json.load(f)
            return set(data.get("channels", []))
    except:
        return set()

def save_discovered_channels(channels: set):
    """Persist newly discovered channels to disk."""
    try:
        existing = load_discovered_channels()
        merged = existing | channels
        with open(DISCOVERED_CHANNELS_FILE, "w") as f:
            _json.dump({
                "channels": sorted(list(merged)),
                "total": len(merged),
                "last_updated": __import__("datetime").datetime.utcnow().isoformat()
            }, f, indent=2)
        return len(merged) - len(existing)  # new additions
    except Exception as e:
        log.warning(f"Could not save channels: {e}")
        return 0

CRICKET_CHANNEL_PATTERNS = [

    # ── IPL / Cricket live streams ────────────────────────
    "CricketStreamsLive", "IPLstreams", "SportsFreeStreams",
    "CricketLiveStream", "IPLLive2025", "IPLLive2026",
    "CricketFreeStream", "LiveCricket", "T20Live",
    "IPLMatchLive", "CricketMatch", "FreeCricketStream",
    "IPL_L", "RealCricPoint", "LiveCricketMatchLink",
    "CricketLive24", "IPLStreamFree", "CricHDLive",
    "CricketStreamHD", "IPLFreeStream", "T20WorldCup",

    # ── Regional language cricket ─────────────────────────
    "TamilCricketLive", "TeluguCricketLive", "HindiCricketLive",
    "CricketTamil", "CricketTelugu", "IPLTamil", "IPLTelugu",
    "KannadaCricket", "MalayalamCricket", "BengaliCricket",
    "MarathiCricket", "CricketGujarati", "PunjabiCricket",

    # ── Betting + streaming (highest priority) ────────────
    "CricketBetting", "IPLBetting", "CricketTips",
    "CricketPrediction", "IPLTips", "CricketFantasy",
    "Dream11Tips", "CricketOdds", "BettingTips",
    "CricketWinTips", "IPLWinPrediction",

    # ── JioHotstar piracy channels ────────────────────────
    "JioHotstarFree", "HotstarFree", "HotstarMovies",
    "JioCinemaFree", "HotstarSeriesFree", "DisneyHotstar",
    "HotstarOTT", "JioFreeMovies", "HotstarLeaks",
    "JioHotstarLeaks", "HotstarWebSeries",

    # ── Netflix India piracy ──────────────────────────────
    "NetflixIndia", "NetflixFree", "NetflixMoviesHindi",
    "NetflixSeriesFree", "NetflixLeaks", "NetflixHD",
    "NetflixTamil", "NetflixTelugu", "NetflixMalayalam",
    "NetflixWebSeries", "NetflixOriginals",

    # ── Amazon Prime Video piracy ─────────────────────────
    "AmazonPrimeFree", "PrimeVideoFree", "PrimeMoviesHindi",
    "AmazonPrimeLeaks", "PrimeVideoIndia", "AmazonHDMovies",
    "PrimeTamil", "PrimeTelugu", "PrimeWebSeries",

    # ── ZEE5 piracy ───────────────────────────────────────
    "ZEE5Free", "Zee5Movies", "Zee5Series",
    "ZEE5Leaks", "Zee5Telugu", "Zee5Tamil",
    "ZEE5Hindi", "ZeeMoviesFree",

    # ── AHA OTT piracy (Telugu) ───────────────────────────
    "AHAFree", "AHAMovies", "AHATelugu",
    "AHAOriginals", "AHALeaks", "AHAWebSeries",
    "AHAOTTFree", "TeluguOTTFree",

    # ── SonyLIV piracy ────────────────────────────────────
    "SonyLIVFree", "SonyLivMovies", "SonyLivSeries",
    "SonyLIVLeaks", "SonyLivTelugu", "SonyLivCricket",
    "SonyLivHD",

    # ── Hindi web series / Bollywood OTT ─────────────────
    "HindiWebSeries", "BollywoodMoviesFree",
    "HindiHDMovies", "BollywoodHD", "HindiOTTFree",
    "WebSeriesHindi", "HindiNetflix", "HindiAmazonPrime",
    "HindiMoviesHD4K", "BollywoodLeaks",

    # ── Telugu OTT piracy ─────────────────────────────────
    "TeluguMoviesFree", "TeluguHDMovies", "TeluguWebSeries",
    "TeluguOTT", "TeluguNewMovies", "TollywoodMovies",
    "TeluguMovies4K", "TeluguLatestMovies",

    # ── Tamil OTT piracy ──────────────────────────────────
    "TamilMoviesFree", "TamilHDMovies", "TamilRockersNew",
    "TamilMoviesOnline", "TamilWebSeries", "KollywoodMovies",
    "TamilNewMovies", "TamilOTTFree",

    # ── Other sports piracy ───────────────────────────────
    "FootballStreamFree", "PremierLeagueFree",
    "ISLFootballFree", "PKLKabaddi", "ProKabaddiFree",
    "FormulaOneFree", "F1StreamFree", "TennisFree",
    "BWFBadmintonFree", "ChessOlympiadFree",
]

# OTT-specific piracy signals
OTT_PIRACY_SIGNALS = [
    # Platform names
    "jiohotstar", "hotstar", "netflix", "amazon prime",
    "prime video", "zee5", "sonyliv", "aha ", "voot",
    "mxplayer", "jiocinema", "altbalaji", "ullu",
    # Action signals
    "free download", "watch free", "direct link",
    "download link", "hd link", "stream link",
    "720p", "1080p", "4k", "web-dl", "webrip",
    "season 1", "season 2", "episode", "ep ",
    "web series", "webseries", "all episodes",
    "google drive", "gdrive", "mega link", "telegram link",
    # Regional OTT signals
    "jio free", "ott free", "subscription free",
]

# Search queries for finding new channels
SEARCH_QUERIES = [
    "ipl live stream telegram",
    "cricket live free telegram",
    "ipl 2026 live telegram channel",
    "watch ipl free telegram",
    "t20 live stream telegram",
    "ipl tamil live telegram",
    "ipl telugu live telegram",
    "cricket live hindi telegram",
]


@dataclass
class TelegramStream:
    channel: str
    channel_url: str
    title: str
    description: str
    language: str
    is_betting: bool
    subscriber_count: int
    stream_signals: list
    detected_at: str
    confidence: float
    severity: str  # CRITICAL, HIGH, MEDIUM


def detect_language(text: str) -> str:
    """Detect commentary language from channel content."""
    text_lower = text.lower()
    scores = {}
    for lang, keywords in LANGUAGE_KEYWORDS.items():
        score = sum(1 for k in keywords if k.lower() in text_lower)
        if score > 0:
            scores[lang] = score
    if not scores:
        return "Unknown"
    return max(scores, key=scores.get)


def extract_subscriber_count(html: str) -> int:
    """Extract subscriber count from Telegram channel page."""
    patterns = [
        r'(\d+(?:\.\d+)?[KMB]?)\s*(?:subscribers|members|followers)',
        r'"members_count":(\d+)',
        r'(\d+)\s*subscribers',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            val = match.group(1)
            try:
                if 'K' in val:
                    return int(float(val.replace('K','')) * 1000)
                elif 'M' in val:
                    return int(float(val.replace('M','')) * 1000000)
                return int(val)
            except:
                pass
    return 0


def analyze_channel(html: str, channel: str) -> TelegramStream | None:
    """Analyze a Telegram channel page for piracy signals."""
    text = html.lower()

    # Count piracy signals — cricket + OTT combined
    signals_found = [s for s in PIRACY_SIGNALS if s.lower() in text]
    betting_found = [s for s in BETTING_SIGNALS if s.lower() in text]
    ott_found = [s for s in OTT_PIRACY_SIGNALS if s.lower() in text]

    if not signals_found and not betting_found and not ott_found:
        return None

    # Merge signals
    signals_found = list(set(signals_found + ott_found))

    # Extract title
    title_match = re.search(r'<title>([^<]+)</title>', html)
    title = title_match.group(1).strip() if title_match else channel

    # Extract description
    desc_match = re.search(
        r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html)
    description = desc_match.group(1) if desc_match else ""

    # Detect language
    language = detect_language(html)

    # Subscriber count
    subscribers = extract_subscriber_count(html)

    # Calculate confidence
    confidence = min(1.0, len(signals_found) * 0.15 +
                     len(betting_found) * 0.20)

    # Severity
    ott_platforms = ["netflix","hotstar","amazon prime","zee5",
                     "sonyliv","aha ","jiohotstar","jiocinema"]
    ott_platform_found = [p for p in ott_platforms if p in text]

    if betting_found or len(signals_found) >= 5:
        severity = "CRITICAL"
    elif ott_platform_found and len(signals_found) >= 2:
        severity = "CRITICAL"  # OTT platform piracy is critical
    elif len(signals_found) >= 3 or ott_platform_found:
        severity = "HIGH"
    else:
        severity = "MEDIUM"

    return TelegramStream(
        channel=channel,
        channel_url=f"https://t.me/{channel}",
        title=title,
        description=description[:100],
        language=language,
        is_betting=bool(betting_found),
        subscriber_count=subscribers,
        stream_signals=signals_found[:5],
        detected_at=now_utc(),
        confidence=confidence,
        severity=severity
    )


async def scan_channel(
    channel: str,
    client: httpx.AsyncClient
) -> TelegramStream | None:
    """Scan a single Telegram channel."""
    try:
        url = f"https://t.me/s/{channel}"
        r = await client.get(url, timeout=10, headers=HEADERS)
        if r.status_code == 200 and len(r.text) > 1000:
            return analyze_channel(r.text, channel)
    except Exception as e:
        log.debug(f"Channel {channel}: {e}")
    return None


async def search_new_channels(
    query: str,
    client: httpx.AsyncClient,
    serp_key: str
) -> list[str]:
    """
    Search for new Telegram channels using SerpApi.
    Finds channels created during a match that aren't in our list.
    """
    if not serp_key:
        return []
    try:
        r = await client.get(
            "https://serpapi.com/search",
            params={
                "q": f'site:t.me {query}',
                "api_key": serp_key,
                "num": 10,
                "engine": "google",
            },
            timeout=12
        )
        if r.status_code != 200:
            return []

        channels = []
        for item in r.json().get("organic_results", []):
            link = item.get("link", "")
            if "t.me/" in link:
                channel = link.split("t.me/")[-1].split("/")[0].strip()
                if channel and len(channel) > 2 and not channel.startswith('+'):
                    channels.append(channel)
        return list(set(channels))
    except Exception as e:
        log.debug(f"Search error: {e}")
        return []


async def run_live_scan(
    event_name: str = "IPL 2026",
    serp_key: str = "",
    webhook_url: str = ""
) -> dict:
    """
    Run a complete live shield scan.
    Monitors all known channels + searches for new ones.
    """
    log.info(f"Live Shield scan: {event_name}")
    start_time = datetime.now()

    # Load base + previously discovered channels
    _discovered = load_discovered_channels()
    all_channels = list(set(CRICKET_CHANNEL_PATTERNS) | _discovered)
    log.info(f"Channel list: {len(CRICKET_CHANNEL_PATTERNS)} base + {len(_discovered)} discovered = {len(all_channels)} total")
    streams_found = []

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=12
    ) as client:
        # Phase 1 — Scan known channels
        log.info(f"Phase 1: Scanning {len(all_channels)} known channels")
        tasks = [scan_channel(ch, client) for ch in all_channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, TelegramStream):
                streams_found.append(r)

        # Phase 2 — Search for new channels (uses SerpApi)
        if serp_key:
            log.info("Phase 2: Searching for new channels")
            new_channels = []
            for query in SEARCH_QUERIES[:3]:  # Limit to 3 searches
                found = await search_new_channels(query, client, serp_key)
                new_channels.extend(found)
                await asyncio.sleep(0.3)

            # Scan newly discovered channels
            new_unique = [c for c in set(new_channels)
                         if c not in all_channels]
            if new_unique:
                log.info(f"Found {len(new_unique)} new channels to scan")
                # Auto-save newly discovered channels permanently
                added = save_discovered_channels(set(new_unique))
                if added > 0:
                    log.info(f"Auto-saved {added} new channels to discovery list")
                new_tasks = [scan_channel(ch, client)
                            for ch in new_unique[:20]]
                new_results = await asyncio.gather(
                    *new_tasks, return_exceptions=True)
                for r in new_results:
                    if isinstance(r, TelegramStream):
                        streams_found.append(r)

    # Sort by severity
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    streams_found.sort(key=lambda x: severity_order.get(x.severity, 3))

    elapsed = (datetime.now() - start_time).total_seconds()

    # Send webhook if configured
    if webhook_url and streams_found:
        await send_webhook(webhook_url, event_name, streams_found)

    result = {
        "event": event_name,
        "streams_found": len(streams_found),
        "critical": sum(1 for s in streams_found if s.severity == "CRITICAL"),
        "high": sum(1 for s in streams_found if s.severity == "HIGH"),
        "channels_scanned": len(all_channels),
        "scan_time_seconds": round(elapsed, 1),
        "scanned_at": now_utc(),
        "streams": streams_found
    }

    log.info(f"Live Shield: {len(streams_found)} streams found "
             f"in {elapsed:.1f}s")
    return result


async def send_webhook(
    webhook_url: str,
    event: str,
    streams: list
) -> None:
    """Send alert to rights holder webhook."""
    payload = {
        "event": event,
        "streams_found": len(streams),
        "critical_count": sum(1 for s in streams
                              if s.severity == "CRITICAL"),
        "detected_at": now_utc(),
        "streams": [
            {
                "channel": s.channel,
                "url": s.channel_url,
                "language": s.language,
                "severity": s.severity,
                "subscribers": s.subscriber_count,
                "is_betting": s.is_betting,
            }
            for s in streams[:10]
        ]
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(webhook_url,
                                  json=payload, timeout=5)
            log.info(f"Webhook sent: HTTP {r.status_code}")
    except Exception as e:
        log.error(f"Webhook failed: {e}")


def print_report(result: dict):
    """Print live shield scan report."""
    print(f"\n{'='*65}")
    print(f"  CINEOS LIVE SHIELD — {result['event']}")
    print(f"  Real-time Telegram Stream Monitor")
    print(f"{'='*65}")
    print(f"  Streams found    : {result['streams_found']}")
    print(f"  Critical threats : {result['critical']}")
    print(f"  High threats     : {result['high']}")
    print(f"  Channels scanned : {result['channels_scanned']}")
    print(f"  Scan time        : {result['scan_time_seconds']}s")
    print(f"  Scanned at       : {result['scanned_at']}")

    if result['streams']:
        print(f"\n  DETECTED ILLEGAL STREAMS:")
        for s in result['streams']:
            print(f"\n  [{s.severity}] @{s.channel}")
            print(f"  Language   : {s.language}")
            print(f"  URL        : {s.channel_url}")
            print(f"  Subscribers: {s.subscriber_count:,}")
            print(f"  Betting    : {'YES ⚠' if s.is_betting else 'No'}")
            print(f"  Signals    : {', '.join(s.stream_signals[:3])}")
            print(f"  Confidence : {s.confidence*100:.0f}%")
    else:
        print("\n  No illegal streams detected")
    print(f"\n{'='*65}")




# ── LIVE CONTINUOUS MONITOR ──────────────────────────────────────────
async def continuous_monitor(
    event: str = "IPL 2026",
    interval_seconds: int = 60,
    webhook_url: str = "",
    alert_email: str = "",
    alert_threshold: int = 1
):
    """
    Run Live Shield continuously every N seconds.
    Detects NEW channels that appear between scans.
    Sends instant alerts when new illegal streams detected.
    """
    log.info(f"CINEOS LIVE MONITOR STARTED")
    log.info(f"Event: {event}")
    log.info(f"Scan interval: {interval_seconds}s")
    log.info(f"Alert threshold: {alert_threshold} new streams")
    log.info("Press Ctrl+C to stop")
    log.info("="*60)

    known_channels = set()  # Track already seen channels
    subscriber_history = {}  # channel_id -> list of (timestamp, count)
    velocity_alerts = []  # Channels growing suspiciously fast
    scan_count = 0
    total_detected = 0
    session_start = datetime.utcnow()

    while True:
        try:
            scan_count += 1
            scan_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            log.info(f"[Scan #{scan_count}] {scan_time}")

            # Run the scan
            serp_key = os.getenv("SERP_API_KEY", "")
            result = await run_live_scan(event, serp_key, webhook_url)

            if not result:
                await asyncio.sleep(interval_seconds)
                continue

            # Find NEW channels not seen before
            current_streams = result.get("streams", [])
            new_streams = []

            for stream in current_streams:
                # Handle both dict and dataclass
                if hasattr(stream, 'channel'):
                    ch = stream.channel or ""
                    url = stream.channel_url or ""
                    channel_id = ch + url
                else:
                    ch = stream.get("channel", "")
                    url = stream.get("url", "")
                    channel_id = ch + url
                if channel_id not in known_channels:
                    new_streams.append(stream)
                    known_channels.add(channel_id)

            total_detected += len(new_streams)

            # ── Subscriber Velocity Analysis ─────────────────────
            velocity_alerts = []
            now_ts = datetime.utcnow().isoformat()
            for stream in current_streams:
                ch_id = getattr(stream, 'channel', '') or ''
                subs = getattr(stream, 'subscriber_count', 0) or 0
                if ch_id:
                    if ch_id not in subscriber_history:
                        subscriber_history[ch_id] = []
                    subscriber_history[ch_id].append((now_ts, subs))
                    # Keep last 10 readings
                    subscriber_history[ch_id] = subscriber_history[ch_id][-10:]
                    # Calculate velocity if we have 2+ readings
                    history = subscriber_history[ch_id]
                    if len(history) >= 2:
                        oldest_subs = history[0][1]
                        newest_subs = history[-1][1]
                        growth = newest_subs - oldest_subs
                        growth_pct = (growth / max(oldest_subs, 1)) * 100
                        if growth > 500 or growth_pct > 20:
                            velocity_alerts.append({
                                "channel": ch_id,
                                "old_subs": oldest_subs,
                                "new_subs": newest_subs,
                                "growth": growth,
                                "growth_pct": round(growth_pct, 1),
                                "url": getattr(stream, 'channel_url', '')
                            })
                            log.info(f"  📈 VELOCITY ALERT: @{ch_id} grew {growth:+,} subs ({growth_pct:.1f}%)")

            if velocity_alerts:
                log.info(f"  📈 {len(velocity_alerts)} channels growing rapidly — PRIORITY TARGETS")

            if new_streams:
                log.info(f"  🚨 {len(new_streams)} NEW illegal streams detected!")
                for s in new_streams:
                    # Handle dataclass or dict
                    if hasattr(s, 'severity'):
                        severity = s.severity or "MEDIUM"
                        channel = s.channel or "Unknown"
                        subs = getattr(s, 'subscriber_count', 0) or 0
                        betting = "🎰 BETTING+" if getattr(s, 'is_betting', False) else ""
                        lang = getattr(s, 'language', 'Unknown') or "Unknown"
                        url = s.channel_url or ""
                    else:
                        severity = s.get("severity", "MEDIUM")
                        channel = s.get("channel", "Unknown")
                        subs = s.get("subscribers", 0)
                        betting = "🎰 BETTING+" if s.get("is_betting") else ""
                        lang = s.get("language", "Unknown")
                        url = s.get("url", "")
                    log.info(f"  [{severity}] {channel} — {subs:,} subs — {lang} {betting}")
                    log.info(f"    URL: {url}")

                # Generate alert
                alert = {
                    "timestamp": scan_time,
                    "event": event,
                    "new_streams": len(new_streams),
                    "total_session": total_detected,
                    "scan_number": scan_count,
                    "critical": [s for s in new_streams if (getattr(s,'severity',None) or s.get("severity","")) == "CRITICAL"],
                    "betting_combined": [s for s in new_streams if getattr(s,'is_betting',False) or (isinstance(s,dict) and s.get("is_betting"))],
                    "channels": new_streams
                }

                # Print formatted alert
                print("\n" + "="*60)
                print(f"  🚨 CINEOS LIVE ALERT — {scan_time}")
                print(f"  Event: {event}")
                print(f"  New streams: {len(new_streams)}")
                print(f"  Critical: {len(alert['critical'])}")
                print(f"  Betting+Stream: {len(alert['betting_combined'])}")
                if velocity_alerts:
                    print(f"  📈 RAPID GROWTH CHANNELS ({len(velocity_alerts)}):")
                    for v in velocity_alerts:
                        print(f"    @{v['channel']} +{v['growth']:,} subs ({v['growth_pct']}%) — PRIORITY")
                    print()
                print("="*60)

                for s in new_streams:
                    print(f"  [{s.get('severity','?')}] {s.get('channel','?')}")
                    print(f"    Subs: {s.get('subscriber_count',0):,}")
                    print(f"    Lang: {s.get('language','?')}")
                    print(f"    URL:  {s.get('channel_url','')}")
                    if getattr(s, 'is_betting', False) or (isinstance(s, dict) and s.get("is_betting")):
                        print(f"    ⚠️  BETTING SIGNALS DETECTED")
                    print()

                # Send webhook alert if configured
                if webhook_url and len(new_streams) >= alert_threshold:
                    try:
                        import httpx
                        async with httpx.AsyncClient() as client:
                            await client.post(webhook_url, json=alert, timeout=5)
                        log.info(f"  ✓ Webhook alert sent")
                    except Exception as e:
                        log.warning(f"  Webhook failed: {e}")

            else:
                log.info(f"  ✓ No new streams (total known: {len(known_channels)})")

            # Session summary every 10 scans
            if scan_count % 10 == 0:
                elapsed = (datetime.utcnow() - session_start).seconds // 60
                log.info(f"\n  SESSION SUMMARY — {elapsed} minutes")
                log.info(f"  Scans completed: {scan_count}")
                log.info(f"  Total new streams detected: {total_detected}")
                log.info(f"  Unique channels tracked: {len(known_channels)}")

            await asyncio.sleep(interval_seconds)

        except KeyboardInterrupt:
            log.info("\nLive monitor stopped by user")
            print(f"\nSESSION COMPLETE:")
            print(f"  Scans: {scan_count}")
            print(f"  New streams detected: {total_detected}")
            print(f"  Channels tracked: {len(known_channels)}")
            break
        except Exception as e:
            log.error(f"Monitor error: {e}")
            await asyncio.sleep(interval_seconds)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="CINEOS Live Shield — Telegram Stream Monitor")
    ap.add_argument("--event", default="IPL 2026",
                    help="Sports event name")
    ap.add_argument("--webhook", default="",
                    help="Webhook URL for alerts")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--ott", action="store_true",
                    help="Scan for OTT content piracy")
    ap.add_argument("--live", action="store_true",
                    help="Continuous live monitoring mode")
    ap.add_argument("--interval", type=int, default=60,
                    help="Scan interval in seconds (default: 60)")
    ap.add_argument("--threshold", type=int, default=1,
                    help="Alert threshold (min new streams)")
    args = ap.parse_args()

    if args.demo:
        print("\nCINEOS Live Shield v1.0")
        print("Real-time Telegram cricket stream monitor")
        print(f"Monitoring {len(CRICKET_CHANNEL_PATTERNS)} channels")
        print("No API key required for public channels")
        print("\nTarget customers:")
        print("  JioStar/JioHotstar — IPL $6.4B rights")
        print("  BCCI — cricket rights protection")
        print("  Star Sports — Premier League India")
        print("\nPrice: $50,000/tournament")
        print("\nRun: python3 cineos_live_shield.py --event 'IPL 2026'")
    else:
        serp_key = os.getenv("SERP_API_KEY", "")
        result = asyncio.run(run_live_scan(
            args.event, serp_key, args.webhook))
        print_report(result)
