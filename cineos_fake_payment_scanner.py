"""
CINEOS Fake Payment Screenshot Scanner
India-specific: Fake UPI/PhonePe/Paytm screenshots
used to defraud merchants.
Also detects: demo payment apps, screenshot editor channels.
Sell to: PhonePe, Paytm, Google Pay, all merchants.
"""
import asyncio, httpx, json, os
from datetime import datetime
from telethon import TelegramClient

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"
SERP_KEY = os.environ.get('SERP_API_KEY','')

FAKE_PAYMENT_PATTERNS = [
    # Screenshot fraud
    'fake payment screenshot', 'fake upi screenshot',
    'payment screenshot edit', 'fake gpay screenshot',
    'fake phonepe screenshot', 'fake paytm screenshot',
    'payment proof edit', 'upi proof fake',
    'demo payment app', 'prank payment app',
    'payment successful fake', 'screenshot generator payment',
    # Telegram channels distributing fake screenshot tools
    'screenshot editor upi', 'payment edit app',
    'fake receipt generator', 'upi screenshot tool',
    # Hindi
    'नकली पेमेंट', 'फर्जी रसीद', 'पेमेंट एडिट',
    # Telugu
    'నకిలీ పేమెంట్', 'చెల్లింపు స్క్రీన్‌షాట్',
]

async def scan_fake_payments():
    findings = []
    print("[Fake Payment] Scanning for payment screenshot fraud...")

    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()

    # Telegram channels that distribute fake payment tools
    channels_to_check = [
        'screenshot_editor_upi', 'fake_payment_tools',
        'payment_proof_generator', 'upi_screenshot_maker',
        'demo_payment_app_india', 'payment_edit_group',
    ]

    for channel in channels_to_check:
        try:
            entity = await client.get_entity(channel)
            messages = await client.get_messages(entity, limit=200)
            subs = getattr(entity, 'participants_count', 0) or 0

            hits = []
            for msg in messages:
                if not msg.text: continue
                text = msg.text.lower()
                found = [p for p in FAKE_PAYMENT_PATTERNS if p.lower() in text]
                if found:
                    hits.extend(found)

            if hits:
                findings.append({
                    'channel': channel,
                    'subscribers': subs,
                    'patterns_found': list(set(hits[:5])),
                    'risk': 'CRITICAL',
                    'platform': 'telegram',
                })
                print(f"  FOUND: @{channel} {subs:,} subs — {hits[:2]}")
        except:
            pass

    await client.disconnect()

    # Also search web
    async with httpx.AsyncClient(timeout=15) as client:
        queries = [
            "fake upi screenshot tool telegram india",
            "payment screenshot editor app india download",
            "fake phonepe payment proof india",
            "site:t.me fake payment screenshot india",
        ]
        for q in queries:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "engine": "google", "q": q,
                    "api_key": SERP_KEY, "num": 10, "gl": "in"
                })
                for item in r.json().get("organic_results", []):
                    findings.append({
                        'type': 'web_search',
                        'title': item.get("title",""),
                        'url': item.get("link",""),
                        'snippet': item.get("snippet","")[:100],
                        'query': q,
                    })
                await asyncio.sleep(0.5)
            except: pass

    print(f"[Fake Payment] Total findings: {len(findings)}")
    os.makedirs('reports', exist_ok=True)
    json.dump(findings,
        open(f"reports/fake_payment_{datetime.now().strftime('%Y%m%d_%H%M')}.json",'w'),
        indent=2, default=str)
    return findings

asyncio.run(scan_fake_payments())
