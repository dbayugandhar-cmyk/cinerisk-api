"""
CINEOS Misinformation Scanner v2
Upgraded with:
- Election misinformation (state elections 2026)
- Health misinformation (fake medicine cures)
- Financial misinformation (fake RBI/SEBI announcements)
- Communal misinformation (fake viral videos)

Sell to: MeitY, Election Commission, PIB, AYUSH Ministry
"""
import asyncio, httpx, json, os
from datetime import datetime
from telethon import TelegramClient

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"
SERP_KEY = os.environ.get('SERP_API_KEY','')

MISINFO_PATTERNS = {
    'election_misinfo': [
        'voting machine hacked', 'evm rigged',
        'election results fake', 'vote manipulation',
        'election commission corrupt',
    ],
    'health_misinfo': [
        'cancer cure home remedy', 'covid fake vaccine',
        'diabetes cure guaranteed', 'blood pressure cure',
        'ayurvedic cancer cure', 'fake medicine cure',
        'नीम से कैंसर ठीक', 'हल्दी से इलाज',
    ],
    'financial_misinfo': [
        'rbi new scheme free money', 'government scheme 10000',
        'pm kisan new scheme fake', 'lic fraud scheme',
        'bank account double scheme',
        'सरकारी योजना पैसे', 'आरबीआई नई योजना',
    ],
    'product_misinfo': [
        'covid spray kills virus', 'fake sanitizer',
        'n95 mask fake selling', 'counterfeit medicine',
    ],
}

async def scan_misinfo():
    findings = {cat: [] for cat in MISINFO_PATTERNS}
    print("[Misinfo v2] Scanning misinformation...")

    async with httpx.AsyncClient(timeout=15) as client:
        for category, patterns in MISINFO_PATTERNS.items():
            for pattern in patterns[:3]:
                try:
                    r = await client.get("https://serpapi.com/search", params={
                        "engine": "google",
                        "q": f"viral india telegram whatsapp {pattern} fake",
                        "api_key": SERP_KEY,
                        "num": 10, "gl": "in"
                    })
                    for item in r.json().get("organic_results", []):
                        findings[category].append({
                            'pattern': pattern,
                            'title': item.get("title",""),
                            'url': item.get("link",""),
                            'snippet': item.get("snippet","")[:100],
                        })
                    await asyncio.sleep(0.5)
                except: pass

    total = sum(len(v) for v in findings.values())
    print(f"[Misinfo v2] Total: {total} findings")
    for cat, items in findings.items():
        if items:
            print(f"  {cat}: {len(items)}")

    os.makedirs('reports', exist_ok=True)
    json.dump(findings,
        open(f"reports/misinfo_v2_{datetime.now().strftime('%Y%m%d_%H%M')}.json",'w'),
        indent=2)
    return findings

asyncio.run(scan_misinfo())
