"""
CINEOS Meesho Counterfeit Scanner
Meesho = 150M users, major counterfeit hub.
Finds fake Nike, Samsung, boAt, Dove, Dettol on Meesho.
"""
import asyncio, httpx, json, os, re
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

BRANDS_TO_SCAN = [
    ("Nike", 3000, 8000),
    ("Adidas", 2500, 7000),
    ("boAt", 500, 3000),
    ("Samsung Galaxy", 8000, 20000),
    ("Ray-Ban", 5000, 12000),
    ("Dove", 100, 250),
    ("Dettol", 80, 200),
    ("Apple", 30000, 80000),
    ("Puma", 2000, 6000),
    ("Titan", 2000, 8000),
]

def parse_price(text):
    nums = re.findall(r'[\d,]+', text.replace(',',''))
    return int(nums[0]) if nums else 0

async def scan_meesho():
    findings = []
    print("[Meesho] Starting counterfeit scan...")

    async with httpx.AsyncClient(timeout=15) as client:
        for brand, min_price, retail in BRANDS_TO_SCAN:
            queries = [
                f"site:meesho.com {brand} copy",
                f"site:meesho.com {brand} replica",
                f"site:meesho.com {brand} first copy",
                f"site:meesho.com {brand} master copy",
            ]
            for query in queries:
                try:
                    r = await client.get("https://serpapi.com/search", params={
                        "engine": "google",
                        "q": query,
                        "api_key": SERP_KEY,
                        "num": 10, "gl": "in",
                    })
                    for item in r.json().get("organic_results", []):
                        link = item.get("link","")
                        title = item.get("title","")
                        snippet = item.get("snippet","")

                        if "meesho.com" not in link:
                            continue

                        # Check for counterfeit signals
                        check = (title + " " + snippet).lower()
                        signals = []
                        score = 0

                        # Explicit copy signals
                        for term in ['copy','replica','first copy','master copy','duplicate']:
                            if term in check:
                                score += 35
                                signals.append(f"EXPLICIT: '{term}'")
                                break

                        # Price check from snippet
                        prices = re.findall(r'₹\s*(\d+)', snippet)
                        for p in prices:
                            price = int(p)
                            if price < min_price * 0.3:
                                gap = int((1-price/retail)*100)
                                score += 30
                                signals.append(f"PRICE: Rs {price} = {gap}% below retail")
                                break

                        if score >= 35:
                            findings.append({
                                "platform": "meesho",
                                "brand": brand,
                                "title": title,
                                "snippet": snippet[:100],
                                "url": link,
                                "risk_score": min(100, score),
                                "signals": signals,
                            })

                    await asyncio.sleep(0.5)
                except:
                    pass

    findings.sort(key=lambda x: -x['risk_score'])
    print(f"[Meesho] Found {len(findings)} counterfeit listings")
    for f in findings[:10]:
        print(f"  [{f['risk_score']:3}/100] {f['brand']:15} {f['title'][:40]}")
        for s in f['signals']:
            print(f"    → {s}")

    os.makedirs('reports', exist_ok=True)
    json.dump(findings, open('reports/meesho_counterfeits.json','w'), indent=2)
    print(f"  Saved: reports/meesho_counterfeits.json")
    return findings

asyncio.run(scan_meesho())
