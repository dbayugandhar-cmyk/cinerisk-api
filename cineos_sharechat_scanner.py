"""
CINEOS ShareChat Scanner
ShareChat = India's largest vernacular platform.
200M users. Hindi, Tamil, Telugu, Kannada, Malayalam.
Fraud in regional languages nobody else monitors.
"""
import asyncio, httpx, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

SHARECHAT_QUERIES = [
    # Hindi fraud
    ("site:sharechat.com सट्टा मटका", "betting_hindi"),
    ("site:sharechat.com घर बैठे कमाई", "job_scam_hindi"),
    ("site:sharechat.com शेयर मार्केट टिप्स", "investment_fraud_hindi"),
    ("site:sharechat.com क्रिप्टो पैसे", "crypto_fraud_hindi"),
    # Telugu fraud
    ("site:sharechat.com telugu betting cricket", "betting_telugu"),
    ("site:sharechat.com telugu share market tips", "investment_fraud_telugu"),
    # Tamil fraud
    ("site:sharechat.com tamil betting tips", "betting_tamil"),
    # English fraud
    ("site:sharechat.com earn money daily india", "job_scam"),
    ("site:sharechat.com first copy shoes", "counterfeit"),
]

async def scan_sharechat():
    findings = []
    print("[ShareChat] Starting vernacular fraud scan...")

    async with httpx.AsyncClient(timeout=15) as client:
        for query, category in SHARECHAT_QUERIES:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "engine": "google",
                    "q": query,
                    "api_key": SERP_KEY,
                    "num": 10, "gl": "in", "hl": "hi",
                })
                for item in r.json().get("organic_results", []):
                    if "sharechat.com" in item.get("link",""):
                        findings.append({
                            "platform": "sharechat",
                            "title": item.get("title",""),
                            "url": item.get("link",""),
                            "category": category,
                            "language": category.split("_")[-1] if "_" in category else "english",
                        })
                await asyncio.sleep(0.5)
            except:
                pass

    print(f"[ShareChat] Found {len(findings)} fraud posts")
    for f in findings[:5]:
        print(f"  [{f['language'].upper():8}] {f['title'][:55]}")

    os.makedirs('reports', exist_ok=True)
    json.dump(findings, open('reports/sharechat_fraud.json','w'), indent=2)
    return findings

asyncio.run(scan_sharechat())
