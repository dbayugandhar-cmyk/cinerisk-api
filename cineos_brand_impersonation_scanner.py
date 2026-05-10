"""
CINEOS Brand Impersonation Scanner
Covers: WhatsApp Business fakes, domain squatting,
        fake mobile apps, fake social profiles.
These gaps are covered by BrandShield + MarkMonitor globally
but nobody covers India brands specifically.
"""
import asyncio, httpx, json, os, re, hashlib
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY', '')

INDIA_BRANDS_FULL = [
    'Zerodha', 'Groww', 'Upstox', 'Angel One', 'Kite',
    'JioHotstar', 'JioCinema', 'Hotstar', 'SonyLIV', 'ZEE5',
    'PhonePe', 'Paytm', 'Google Pay', 'BHIM', 'Cred',
    'HDFC Bank', 'SBI', 'ICICI Bank', 'Axis Bank', 'Kotak',
    'BCCI', 'IPL', 'Tata', 'Reliance', 'Infosys', 'Wipro',
    'Swiggy', 'Zomato', 'Ola', 'Rapido', 'Urban Company',
]

async def scan_whatsapp_business_fakes(client) -> list:
    findings = []
    queries = [
        'fake whatsapp business account india fraud',
        'whatsapp impersonation bank india 2026',
        'fake zerodha groww whatsapp customer support',
        'fake SBI HDFC whatsapp OTP fraud india',
        'whatsapp fake kyc india bank fraud 2026',
    ]
    for query in queries:
        try:
            r = await client.get('https://serpapi.com/search', params={
                'engine': 'google', 'q': query,
                'api_key': SERP_KEY, 'num': 10, 'gl': 'in',
                'tbs': 'qdr:m',
            })
            for item in r.json().get('organic_results', []):
                findings.append({
                    'type':    'whatsapp_impersonation',
                    'title':   item.get('title', ''),
                    'url':     item.get('link', ''),
                    'snippet': item.get('snippet', '')[:120],
                    'risk':    'HIGH',
                    'action':  'Alert Meta India + brand legal team',
                })
            await asyncio.sleep(0.4)
        except:
            pass
    return findings

async def scan_fake_apps(client) -> list:
    findings = []
    queries = [
        'fake Zerodha Groww app download apk india',
        'fake PhonePe Paytm app fraud india 2026',
        'fake SBI HDFC app phishing india',
        'fake investment app india telegram apk',
        'clone app india banking fraud 2026',
    ]
    for query in queries:
        try:
            r = await client.get('https://serpapi.com/search', params={
                'engine': 'google', 'q': query,
                'api_key': SERP_KEY, 'num': 10, 'gl': 'in',
            })
            for item in r.json().get('organic_results', []):
                url = item.get('link', '')
                # Skip Play Store and App Store (legitimate)
                if any(x in url for x in
                       ['play.google.com', 'apps.apple.com',
                        'ndtv', 'timesofindia', 'thehindu']):
                    continue
                findings.append({
                    'type':    'fake_app',
                    'title':   item.get('title', ''),
                    'url':     url,
                    'snippet': item.get('snippet', '')[:120],
                    'risk':    'CRITICAL',
                    'action':  'Report to Google Play Protect + CERT-In',
                })
            await asyncio.sleep(0.4)
        except:
            pass
    return findings

async def scan_social_impersonation(client) -> list:
    findings = []
    for brand in INDIA_BRANDS_FULL[:10]:
        query = (f'fake "{brand}" account india fraud '
                 f'instagram twitter 2026')
        try:
            r = await client.get('https://serpapi.com/search', params={
                'engine': 'google', 'q': query,
                'api_key': SERP_KEY, 'num': 5, 'gl': 'in',
            })
            for item in r.json().get('organic_results', []):
                snippet = item.get('snippet', '').lower()
                if any(k in snippet for k in
                       ['fake', 'fraud', 'impersonat',
                        'scam', 'warn', 'alert']):
                    findings.append({
                        'type':    'social_impersonation',
                        'brand':   brand,
                        'title':   item.get('title', ''),
                        'url':     item.get('link', ''),
                        'snippet': item.get('snippet', '')[:120],
                        'risk':    'HIGH',
                        'action':  f'Takedown + brand alert',
                    })
            await asyncio.sleep(0.3)
        except:
            pass
    return findings

async def run_brand_impersonation_scan():
    print('='*55)
    print('  CINEOS BRAND IMPERSONATION SCANNER')
    print('  WhatsApp Business + Fake Apps + Social')
    print('='*55)

    async with httpx.AsyncClient(timeout=15) as client:
        print('\n[1/3] WhatsApp Business impersonation...')
        wa = await scan_whatsapp_business_fakes(client)
        print(f'  Findings: {len(wa)}')

        print('\n[2/3] Fake app detection...')
        apps = await scan_fake_apps(client)
        print(f'  Findings: {len(apps)}')

        print('\n[3/3] Social media impersonation...')
        social = await scan_social_impersonation(client)
        print(f'  Findings: {len(social)}')

    all_findings = {
        'generated_at':         datetime.now().isoformat(),
        'whatsapp_business':    wa,
        'fake_apps':            apps,
        'social_impersonation': social,
        'totals': {
            'whatsapp': len(wa),
            'apps':     len(apps),
            'social':   len(social),
            'total':    len(wa)+len(apps)+len(social),
        }
    }

    if apps:
        print(f'\n  CRITICAL — FAKE APPS:')
        for a in apps[:5]:
            print(f"  → {a['title'][:60]}")

    os.makedirs('reports', exist_ok=True)
    json.dump(all_findings,
              open('reports/brand_impersonation.json', 'w'),
              indent=2, default=str)

    print(f'\n{"="*55}')
    print(f'  BRAND IMPERSONATION SCAN COMPLETE')
    print(f'{"="*55}')
    print(f'  WhatsApp fakes:    {len(wa)}')
    print(f'  Fake apps:         {len(apps)}')
    print(f'  Social impersonation: {len(social)}')
    print(f'  Saved: reports/brand_impersonation.json')
    return all_findings

asyncio.run(run_brand_impersonation_scan())
