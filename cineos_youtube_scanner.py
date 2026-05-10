"""
CINEOS YouTube Fraud Channel Scanner
Finds fake investment, betting, job scam channels on YouTube.
India-specific: searches in English + Hindi + Telugu + Tamil.
"""
import asyncio, httpx, json, os, re
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

YOUTUBE_QUERIES = [
    # English
    ("IPL betting tips free telegram", "betting"),
    ("guaranteed stock tips sebi registered", "investment_fraud"),
    ("zerodha free tips channel", "investment_fraud"),
    ("groww free signals telegram", "investment_fraud"),
    ("work from home earn daily india", "job_scam"),
    ("crypto pump signal free india", "crypto_fraud"),
    ("mahadev book cricket betting", "betting"),
    ("reddy anna book ipl", "betting"),
    # Hindi
    ("रोज कमाओ घर बैठे", "job_scam"),
    ("क्रिप्टो पंप सिग्नल", "crypto_fraud"),
    ("शेयर मार्केट टिप्स फ्री", "investment_fraud"),
    ("सट्टा मटका टिप्स", "betting"),
    # Telugu
    ("telugu stock tips free", "investment_fraud"),
    ("telugu betting tips ipl", "betting"),
    # Tamil
    ("tamil betting tips cricket", "betting"),
    ("tamil stock market tips free", "investment_fraud"),
]

async def scan_youtube():
    findings = []
    print("[YouTube] Starting scan...")

    async with httpx.AsyncClient(timeout=15) as client:
        for query, category in YOUTUBE_QUERIES:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "engine": "youtube",
                    "search_query": query,
                    "api_key": SERP_KEY,
                })
                videos = r.json().get("video_results", [])
                for v in videos[:5]:
                    title = v.get("title","")
                    channel = v.get("channel",{})
                    subs = channel.get("subscribers","")
                    
                    # Risk signals
                    risk = 0
                    signals = []
                    title_lower = title.lower()
                    
                    fraud_terms = ['free','guaranteed','daily','profit','tips',
                                   'signal','sure','100%','bet','betting','satta',
                                   'earn','घर बैठे','रोज','टिप्स','फ्री']
                    found = [t for t in fraud_terms if t in title_lower]
                    if found:
                        risk += len(found) * 10
                        signals.append(f"Fraud terms: {found[:3]}")
                    
                    if risk >= 20:
                        findings.append({
                            "platform": "youtube",
                            "title": title,
                            "channel": channel.get("name",""),
                            "subscribers": subs,
                            "views": v.get("views",""),
                            "url": v.get("link",""),
                            "category": category,
                            "risk_score": min(100, risk),
                            "signals": signals,
                            "query": query,
                        })

                await asyncio.sleep(0.5)

            except Exception as e:
                pass

    # Sort by risk
    findings.sort(key=lambda x: -x['risk_score'])
    
    print(f"[YouTube] Found {len(findings)} suspicious channels")
    for f in findings[:10]:
        print(f"  [{f['risk_score']:3}/100] {f['channel'][:30]:30} "
              f"| {f['title'][:40]}")

    os.makedirs('reports', exist_ok=True)
    json.dump(findings, open('reports/youtube_fraud_channels.json','w'), indent=2)
    print(f"  Saved: reports/youtube_fraud_channels.json")
    return findings

asyncio.run(scan_youtube())
