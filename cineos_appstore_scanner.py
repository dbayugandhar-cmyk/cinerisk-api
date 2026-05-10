"""
CINEOS App Store Fraud Scanner
Fake banking apps, fake broker apps, fake UPI apps.
Play Store + App Store listings.
"""
import asyncio, httpx, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

FAKE_APP_QUERIES = [
    # Fake banking/broker apps
    ("site:play.google.com fake zerodha app india", "fake_broker"),
    ("site:play.google.com fake groww app india", "fake_broker"),
    ("site:play.google.com fake sbi app india", "fake_bank"),
    ("site:play.google.com loan app instant india", "loan_fraud"),
    ("site:play.google.com earn money daily india", "job_scam"),
    ("site:play.google.com betting app cricket india", "betting"),
    # Check for known fraud app patterns
    ("play.google.com instant loan no cibil india", "loan_fraud"),
    ("play.google.com satta matka app india", "betting"),
]

async def scan_app_stores():
    findings = []
    print("[App Store] Starting fraud app scan...")

    async with httpx.AsyncClient(timeout=15) as client:
        for query, category in FAKE_APP_QUERIES:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "engine": "google",
                    "q": query,
                    "api_key": SERP_KEY,
                    "num": 10, "gl": "in",
                })
                for item in r.json().get("organic_results", []):
                    link = item.get("link","")
                    if "play.google.com" in link or "apps.apple.com" in link:
                        findings.append({
                            "platform": "app_store",
                            "store": "play_store" if "play.google" in link else "app_store",
                            "title": item.get("title",""),
                            "snippet": item.get("snippet","")[:100],
                            "url": link,
                            "category": category,
                        })
                await asyncio.sleep(0.5)
            except:
                pass

    print(f"[App Store] Found {len(findings)} suspicious apps")
    for f in findings[:5]:
        print(f"  [{f['store'].upper():12}] {f['title'][:50]}")

    os.makedirs('reports', exist_ok=True)
    json.dump(findings, open('reports/fraud_apps.json','w'), indent=2)
    return findings

asyncio.run(scan_app_stores())
