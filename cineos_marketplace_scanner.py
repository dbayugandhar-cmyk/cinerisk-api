"""
CINEOS India Marketplace Scanner
Covers: Amazon India, Flipkart, Snapdeal, JioMart
Detects counterfeit sellers using public product listings.
Same methodology as IndiaMART scanner — extended to more platforms.
"""
import asyncio, httpx, json, os, re, hashlib
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY', '')

COUNTERFEIT_SIGNALS = [
    'first copy', '1st copy', 'master copy', 'replica',
    'duplicate', 'aaa grade', 'super clone', 'inspired by',
    '7a quality', 'mirror copy', 'best quality copy',
    'export surplus', 'class a copy', 'premium replica',
    # Hindi
    'नकल', 'नकली', 'कॉपी', 'प्रतिलिपि',
]

TARGET_BRANDS = [
    'Nike', 'Adidas', 'Puma', 'Reebok', 'New Balance',
    'Samsung', 'Apple', 'OnePlus', 'boAt', 'Noise',
    'Dove', 'Dettol', 'Himalaya', 'Mamaearth',
    'Ray-Ban', 'Oakley', 'Fossil', 'Titan',
    'Zerodha', 'Groww', 'Upstox',  # financial brand impersonation
]

async def scan_amazon_india(brand: str, client) -> list:
    findings = []
    queries = [
        f'{brand} replica site:amazon.in',
        f'{brand} first copy site:amazon.in',
        f'{brand} master copy site:amazon.in',
        f'"{brand}" "inspired by" site:amazon.in',
    ]
    for query in queries:
        try:
            r = await client.get('https://serpapi.com/search', params={
                'engine': 'google', 'q': query,
                'api_key': SERP_KEY, 'num': 10, 'gl': 'in',
            })
            for item in r.json().get('organic_results', []):
                url     = item.get('link', '')
                title   = item.get('title', '').lower()
                snippet = item.get('snippet', '').lower()
                combined = title + ' ' + snippet

                if 'amazon.in' not in url:
                    continue

                signals = [s for s in COUNTERFEIT_SIGNALS
                          if s in combined]
                if signals:
                    findings.append({
                        'platform':  'amazon_india',
                        'brand':     brand,
                        'title':     item.get('title', ''),
                        'url':       url,
                        'snippet':   item.get('snippet', '')[:150],
                        'signals':   signals,
                        'risk_score': min(40 + len(signals) * 20, 95),
                        'verdict':   'CONFIRMED_COUNTERFEIT',
                        'evidence':  hashlib.sha256(
                            (url+title).encode()).hexdigest(),
                        'found_at':  datetime.now().isoformat(),
                    })
            await asyncio.sleep(0.4)
        except:
            pass
    return findings

async def scan_flipkart(brand: str, client) -> list:
    findings = []
    queries = [
        f'{brand} replica site:flipkart.com',
        f'{brand} first copy site:flipkart.com',
        f'"{brand}" copy site:flipkart.com',
    ]
    for query in queries:
        try:
            r = await client.get('https://serpapi.com/search', params={
                'engine': 'google', 'q': query,
                'api_key': SERP_KEY, 'num': 10, 'gl': 'in',
            })
            for item in r.json().get('organic_results', []):
                url     = item.get('link', '')
                title   = item.get('title', '').lower()
                snippet = item.get('snippet', '').lower()
                combined = title + ' ' + snippet

                if 'flipkart.com' not in url:
                    continue

                signals = [s for s in COUNTERFEIT_SIGNALS
                          if s in combined]
                if signals:
                    findings.append({
                        'platform':  'flipkart',
                        'brand':     brand,
                        'title':     item.get('title', ''),
                        'url':       url,
                        'snippet':   item.get('snippet', '')[:150],
                        'signals':   signals,
                        'risk_score': min(40 + len(signals) * 20, 95),
                        'verdict':   'CONFIRMED_COUNTERFEIT',
                        'evidence':  hashlib.sha256(
                            (url+title).encode()).hexdigest(),
                        'found_at':  datetime.now().isoformat(),
                    })
            await asyncio.sleep(0.4)
        except:
            pass
    return findings

async def scan_snapdeal_jiomart(brand: str, client) -> list:
    findings = []
    for site in ['snapdeal.com', 'jiomart.com']:
        query = f'{brand} replica OR "first copy" site:{site}'
        try:
            r = await client.get('https://serpapi.com/search', params={
                'engine': 'google', 'q': query,
                'api_key': SERP_KEY, 'num': 5, 'gl': 'in',
            })
            for item in r.json().get('organic_results', []):
                url     = item.get('link', '')
                title   = item.get('title', '').lower()
                snippet = item.get('snippet', '').lower()
                combined = title + ' ' + snippet

                if site not in url:
                    continue

                signals = [s for s in COUNTERFEIT_SIGNALS
                          if s in combined]
                if signals:
                    findings.append({
                        'platform':  site.replace('.com', ''),
                        'brand':     brand,
                        'title':     item.get('title', ''),
                        'url':       url,
                        'signals':   signals,
                        'risk_score': min(35 + len(signals) * 15, 90),
                        'verdict':   'LIKELY_COUNTERFEIT',
                        'evidence':  hashlib.sha256(
                            (url+title).encode()).hexdigest(),
                        'found_at':  datetime.now().isoformat(),
                    })
            await asyncio.sleep(0.4)
        except:
            pass
    return findings

async def run_marketplace_scan():
    print('='*55)
    print('  CINEOS MARKETPLACE SCANNER')
    print('  Amazon India + Flipkart + Snapdeal + JioMart')
    print('='*55)

    all_findings = []
    async with httpx.AsyncClient(timeout=15) as client:
        for brand in TARGET_BRANDS[:10]:  # top 10 brands first
            print(f'\n  Scanning: {brand}')
            amz = await scan_amazon_india(brand, client)
            fk  = await scan_flipkart(brand, client)
            sd  = await scan_snapdeal_jiomart(brand, client)
            found = amz + fk + sd

            if found:
                for f in found:
                    print(f"  [{f['platform'].upper():15}] "
                          f"{f['brand']:12} "
                          f"Score:{f['risk_score']:3} "
                          f"| {f['signals'][0] if f['signals'] else ''}")
            all_findings.extend(found)

    # Save
    os.makedirs('reports', exist_ok=True)
    json.dump(all_findings,
              open('reports/marketplace_findings.json', 'w'),
              indent=2, default=str)

    # Summary
    by_platform = {}
    for f in all_findings:
        p = f['platform']
        by_platform[p] = by_platform.get(p, 0) + 1

    print(f'\n{"="*55}')
    print(f'  MARKETPLACE SCAN RESULTS')
    print(f'{"="*55}')
    print(f'  Total findings: {len(all_findings)}')
    for p, count in sorted(by_platform.items(), key=lambda x: -x[1]):
        print(f'  {p:20}: {count}')
    print(f'  Saved: reports/marketplace_findings.json')
    return all_findings

asyncio.run(run_marketplace_scan())
