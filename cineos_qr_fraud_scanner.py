"""
CINEOS QR Code Fraud Scanner
India-specific: UPI QR code fraud.
Fraudsters place fake QR stickers on top of real merchant QR.
Money goes to fraudster not merchant.
Also: QR codes on fake products.

CINEOS can:
1. Scan for QR fraud discussions on Telegram/social media
2. Detect fake merchant QR distribution channels
3. Alert brands whose QR codes are being faked
"""
import asyncio, httpx, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

QR_FRAUD_PATTERNS = [
    'qr code fraud', 'qr code scam',
    'fake qr code india', 'qr sticker scam',
    'upi qr fraud', 'scan qr fraud',
    'qr payment fraud', 'merchant qr fake',
    'qr code phishing', 'malicious qr',
    # Hindi
    'क्यूआर कोड धोखाधड़ी',
    'फर्जी क्यूआर',
    'यूपीआई क्यूआर स्कैम',
]

async def scan_qr_fraud():
    findings = []
    print("[QR Fraud] Scanning for QR code fraud in India...")

    async with httpx.AsyncClient(timeout=15) as client:
        queries = [
            "qr code fraud india telegram channel",
            "fake qr code upi merchant india",
            "qr sticker scam india 2026",
            "qr code phishing india",
            "क्यूआर कोड स्कैम भारत टेलीग्राम",
            "upi qr code manipulation india",
            "fake merchant qr sticker distributor",
            "qr code counterfeit products india",
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
                    check = (title+item.get("snippet","")).lower()

                    if any(p.lower() in check for p in QR_FRAUD_PATTERNS):
                        findings.append({
                            "type": "qr_fraud",
                            "title": title,
                            "url": link,
                            "snippet": item.get("snippet","")[:150],
                        })
                await asyncio.sleep(0.5)
            except:
                pass

    print(f"[QR Fraud] Found {len(findings)} QR fraud references")
    for f in findings[:5]:
        print(f"  → {f['title'][:65]}")

    os.makedirs('reports', exist_ok=True)
    json.dump(findings,
              open(f"reports/qr_fraud_{datetime.now().strftime('%Y%m%d_%H%M')}.json",'w'),
              indent=2)
    return findings

asyncio.run(scan_qr_fraud())
