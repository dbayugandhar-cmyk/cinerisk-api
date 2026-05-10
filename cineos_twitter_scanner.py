"""
CINEOS Twitter/X Fraud Scanner
Finds fake investment, betting, scam accounts on Twitter/X.
Targets: fake Zerodha, Groww, BCCI, IPL accounts.
"""
import asyncio, httpx, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

TWITTER_QUERIES = [
    # Fake broker accounts
    "site:x.com zerodha tips free telegram join",
    "site:x.com groww signals guaranteed returns india",
    "site:x.com angel one free tips telegram",
    # Betting
    "site:x.com ipl betting tips india satta",
    "site:x.com reddy anna book cricket",
    "site:x.com mahadev book betting",
    # Job scams
    "site:x.com work from home india earn daily telegram",
    # Crypto
    "site:x.com crypto pump india free signal telegram",
    # Fake celebrity accounts
    "site:x.com nithin kamath fake investment tips",
    "site:x.com radhakishan damani tips free",
]

async def scan_twitter():
    findings = []
    print("[Twitter/X] Starting scan...")

    async with httpx.AsyncClient(timeout=15) as client:
        for query in TWITTER_QUERIES:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "engine": "google",
                    "q": query,
                    "api_key": SERP_KEY,
                    "num": 10, "gl": "in",
                })
                for item in r.json().get("organic_results", []):
                    link = item.get("link","")
                    if "twitter.com" in link or "x.com" in link:
                        findings.append({
                            "platform": "twitter",
                            "title": item.get("title",""),
                            "snippet": item.get("snippet","")[:150],
                            "url": link,
                            "query": query,
                        })
                await asyncio.sleep(0.5)
            except:
                pass

    print(f"[Twitter/X] Found {len(findings)} suspicious accounts")
    for f in findings[:10]:
        print(f"  → {f['title'][:60]}")

    os.makedirs('reports', exist_ok=True)
    json.dump(findings, open('reports/twitter_fraud_accounts.json','w'), indent=2)
    return findings

asyncio.run(scan_twitter())
