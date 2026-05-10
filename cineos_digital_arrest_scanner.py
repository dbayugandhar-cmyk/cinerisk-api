"""
CINEOS Digital Arrest Scanner
Brand new India-specific fraud — 2025/2026.
Fake CBI/ED/TRAI/Customs officer calls.
Victim told they are "digitally arrested" via video call.
Rs 2,000+ crore lost in 2024.
PM Modi himself warned about this in Mann Ki Baat.

Nobody is scanning for this pattern at scale.
CINEOS can be first.
"""
import asyncio, httpx, json, os
from datetime import datetime
from telethon import TelegramClient

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"
SERP_KEY = os.environ.get('SERP_API_KEY','')

# Digital arrest fraud patterns
DIGITAL_ARREST_PATTERNS = [
    # English
    'digital arrest', 'cyber arrest',
    'you are under arrest video call',
    'cbi officer call', 'ed officer call',
    'trai officer call', 'customs officer call',
    'money laundering case video',
    'clear your name pay fine',
    'aadhaar used crime',
    'your number crime',
    # Hindi
    'डिजिटल अरेस्ट', 'साइबर अरेस्ट',
    'सीबीआई अधिकारी', 'ईडी नोटिस',
    'आपका आधार अपराध',
    'गिरफ्तारी वारंट वीडियो',
]

IMPERSONATION_AGENCIES = [
    'CBI', 'ED', 'TRAI', 'Customs',
    'Income Tax', 'Narcotics', 'RBI',
    'Police Commissioner', 'DGP',
]

async def scan_digital_arrest():
    findings = []
    print("[Digital Arrest] Scanning India's newest fraud type...")

    async with httpx.AsyncClient(timeout=15) as client:
        # Search news/reports
        queries = [
            "digital arrest scam india 2026 cases",
            "fake cbi officer call fraud india telegram",
            "digital arrest whatsapp video call india",
            "डिजिटल अरेस्ट स्कैम भारत 2026",
            "fake ed officer telegram india",
            "cyber arrest money laundering fake india",
            "trai officer scam india 2026",
            "pm modi digital arrest warning",
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
                    title = item.get("title","")
                    link = item.get("link","")
                    snippet = item.get("snippet","")

                    check = (title+snippet).lower()
                    if any(p.lower() in check for p in
                           DIGITAL_ARREST_PATTERNS+IMPERSONATION_AGENCIES):
                        findings.append({
                            "type": "digital_arrest",
                            "title": title,
                            "url": link,
                            "snippet": snippet[:150],
                            "query": query,
                        })
                await asyncio.sleep(0.5)
            except:
                pass

    print(f"[Digital Arrest] Found {len(findings)} references")
    for f in findings[:8]:
        print(f"  → {f['title'][:65]}")

    os.makedirs('reports', exist_ok=True)
    path = f"reports/digital_arrest_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump({
        'scanned_at': datetime.now().isoformat(),
        'findings': findings,
        'description': 'Digital arrest — fake CBI/ED/TRAI officers via video call',
        'india_loss_2024': 'Rs 2,000+ Cr',
        'pm_modi_warned': True,
        'patterns': DIGITAL_ARREST_PATTERNS,
    }, open(path,'w'), indent=2)
    print(f"  Saved: {path}")
    return findings

asyncio.run(scan_digital_arrest())
