"""
CINEOS Predatory Loan App Scanner
Illegal loan apps targeting India — RBI banned 600+ apps.
New ones appear daily. Nobody is tracking them all.

Pattern:
  - Promise instant loan without CIBIL
  - Access phone contacts
  - Harass contacts if payment delayed
  - Charge 200-1000% APR

Sell to: RBI, banks, NBFC, Google Play, NPCI
"""
import asyncio, httpx, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

LOAN_APP_PATTERNS = [
    'instant loan without cibil', 'loan aadhar card',
    'loan 5 minutes', 'loan without documents',
    'payday loan india', 'salary advance app india',
    'personal loan instant approval',
    'loan app no credit check india',
    # RBI banned app patterns
    'loanfront', 'kissht fraud', 'kreditbee issues',
    'loan app harassment', 'loan app contacts access',
    'loan shark app india',
    # Hindi
    'तुरंत लोन', 'बिना सिबिल लोन', 'आधार से लोन',
    'लोन ऐप परेशानी',
    # Telugu
    'వెంటనే రుణం', 'తక్షణ లోన్',
]

ILLEGAL_LOAN_CHANNELS = [
    'instant_loan_india_group',
    'loan_without_cibil_india',
    'personal_loan_telegram_india',
    'easy_loan_india',
    'fast_loan_approval',
]

async def scan_loan_apps():
    findings = {'telegram': [], 'play_store': [], 'social': []}
    print("[Loan App] Scanning for predatory loan apps...")

    async with httpx.AsyncClient(timeout=15) as client:
        # Play Store illegal loan apps
        queries = [
            "site:play.google.com instant loan india no cibil",
            "site:play.google.com personal loan 5 minutes india",
            "illegal loan app india rbi banned 2026",
            "predatory loan app india telegram",
            "loan app harassment india contacts",
            "instant loan app india without documents",
        ]
        for q in queries:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "engine": "google", "q": q,
                    "api_key": SERP_KEY, "num": 10, "gl": "in"
                })
                for item in r.json().get("organic_results", []):
                    findings['play_store'].append({
                        'title': item.get("title",""),
                        'url': item.get("link",""),
                        'snippet': item.get("snippet","")[:120],
                    })
                await asyncio.sleep(0.5)
            except: pass

    total = sum(len(v) for v in findings.values())
    print(f"[Loan App] Total findings: {total}")

    os.makedirs('reports', exist_ok=True)
    json.dump(findings,
        open(f"reports/loan_apps_{datetime.now().strftime('%Y%m%d_%H%M')}.json",'w'),
        indent=2)
    return findings

asyncio.run(scan_loan_apps())
