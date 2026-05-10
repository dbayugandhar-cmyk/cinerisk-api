"""
CINEOS Dark Web + Criminal Forum Intelligence Scanner

IMPORTANT: This scanner uses ONLY publicly accessible data:
- Google indexing of public paste sites
- Public SerpApi search for exposed credentials
- Public news reports about dark web India fraud
- Public cybersecurity research about India-specific threats

This does NOT access Tor or private criminal forums directly.
It monitors what is publicly indexed and reported about
India fraud activity on the dark web.

For actual dark web access, law enforcement (I4C, CBI) use
authorised tools with legal authority. CINEOS provides the
surface-web intelligence layer that points law enforcement
to specific threats.
"""
import asyncio, httpx, json, os, re, hashlib
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY', '')

async def scan_paste_sites_india(client) -> list:
    """
    Scan paste sites for India fraud content.
    Pastebin, Ghostbin, Rentry — publicly indexed.
    """
    findings = []
    queries = [
        'site:pastebin.com india UPI fraud bank account',
        'site:pastebin.com india fake PhonePe Paytm',
        'site:pastebin.com india aadhaar pan leak',
        'site:ghostbin.com india fraud UPI',
        'pastebin india bank credential leak 2026',
        'india UPI account dump paste 2026',
        'india bank login credential exposed paste',
        'phonepe paytm fraud tool paste india',
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

                # Check for India fraud signals
                india_signals = ['india', 'upi', 'paytm', 'phonepe',
                                'aadhaar', 'pan card', 'ifsc', 'hdfc',
                                'sbi', 'icici', 'axis bank', 'neft']
                fraud_signals = ['leak', 'dump', 'fraud', 'fake',
                                'credential', 'breach', 'exposed',
                                'hacked', 'stealer', 'tool']

                has_india = any(s in combined for s in india_signals)
                has_fraud = any(s in combined for s in fraud_signals)

                if has_india and has_fraud:
                    findings.append({
                        'source':    'paste_site',
                        'url':       url,
                        'title':     item.get('title', ''),
                        'snippet':   item.get('snippet', '')[:150],
                        'query':     query,
                        'risk':      'HIGH',
                        'action':    'Flag to CERT-In + I4C',
                        'evidence':  hashlib.sha256(
                            url.encode()).hexdigest(),
                        'found_at':  datetime.now().isoformat(),
                    })
            await asyncio.sleep(0.5)
        except:
            pass

    return findings

async def scan_india_fraud_tools(client) -> list:
    """
    Scan for India-specific fraud tools being sold/discussed.
    Fake UPI screenshot generators, KYC bypass tools etc.
    All via public web search — not direct forum access.
    """
    findings = []
    queries = [
        'fake UPI screenshot generator tool india telegram',
        'fake PhonePe screenshot tool download 2026',
        'fake Paytm payment proof generator india',
        'india KYC bypass aadhaar verification tool',
        'india bank OTP bypass tool telegram',
        'fake bank statement generator india tool',
        'india credit card generator tool dark web',
        'india SIM swap fraud tool telegram 2026',
        '"fake UPI" tool buy india telegram channel',
        'india aadhaar hack tool sell telegram',
    ]

    for query in queries:
        try:
            r = await client.get('https://serpapi.com/search', params={
                'engine': 'google', 'q': query,
                'api_key': SERP_KEY, 'num': 10, 'gl': 'in',
            })
            for item in r.json().get('organic_results', []):
                url     = item.get('link', '')
                title   = item.get('title', '')
                snippet = item.get('snippet', '').lower()

                # Skip news articles about fraud (not the tools themselves)
                is_news = any(d in url for d in [
                    'ndtv','timesofindia','hindustantimes',
                    'thehindu','livemint','economictimes',
                    'indianexpress','businessstandard',
                    'thequint','scroll.in','thewire',
                ])
                if is_news:
                    continue

                # Flag if it looks like an actual tool/channel
                tool_signals = ['download', 'buy', 'sell', 'channel',
                               't.me', 'telegram', 'tool', 'software',
                               'apk', 'generator', 'free download']
                if any(s in snippet for s in tool_signals):
                    findings.append({
                        'source':   'fraud_tool',
                        'url':      url,
                        'title':    title,
                        'snippet':  snippet[:150],
                        'query':    query,
                        'risk':     'CRITICAL',
                        'action':   'Report to MHA + NPCI',
                        'evidence': hashlib.sha256(
                            url.encode()).hexdigest(),
                        'found_at': datetime.now().isoformat(),
                    })
            await asyncio.sleep(0.5)
        except:
            pass

    return findings

async def scan_credential_leak_reports(client) -> list:
    """
    Scan for reports of India credential leaks.
    Banks, UPI providers, financial institutions.
    """
    findings = []
    queries = [
        'india bank data breach 2025 2026 credential leak',
        'UPI account data leak india 2026',
        'PhonePe Paytm BHIM data breach 2026',
        'india financial data dark web sold 2026',
        'HDFC SBI ICICI data breach india 2026',
        'india aadhaar data leak dark web 2026',
        'india credit card data breach 2026 dump',
        'RBI bank data breach india 2026',
    ]

    for query in queries:
        try:
            r = await client.get('https://serpapi.com/search', params={
                'engine': 'google', 'q': query,
                'api_key': SERP_KEY, 'num': 10, 'gl': 'in',
                'tbs': 'qdr:m',  # last month
            })
            for item in r.json().get('organic_results', []):
                url     = item.get('link', '')
                title   = item.get('title', '')
                snippet = item.get('snippet', '')

                findings.append({
                    'source':   'credential_leak_report',
                    'url':      url,
                    'title':    title,
                    'snippet':  snippet[:150],
                    'query':    query,
                    'risk':     'HIGH',
                    'action':   'Alert CERT-In + affected institution',
                    'evidence': hashlib.sha256(
                        url.encode()).hexdigest(),
                    'found_at': datetime.now().isoformat(),
                })
            await asyncio.sleep(0.5)
        except:
            pass

    return findings

async def scan_domain_squatting(client) -> list:
    """
    Scan for typosquatting and domain fraud targeting India brands.
    BrandShield and MarkMonitor cover this globally — CINEOS adds India.
    """
    findings = []
    INDIA_BRANDS = [
        ('zerodha', ['zerodha.co', 'zerodha.net', 'zeroodha.com',
                     'zerodha-login.com', 'zerodha-support.com']),
        ('jiohotstar', ['jiohotstar.co', 'jio-hotstar.com',
                       'jiohoststar.com', 'jiohotstar.net']),
        ('paytm', ['paytm-bank.com', 'paytmlogin.com',
                   'paytm-kyc.com', 'paytmsupport.in']),
        ('groww', ['groww-invest.com', 'growwapp.in',
                   'groww-login.com', 'growwsupport.com']),
        ('bcci', ['bccitickets.net', 'bcci-match.com',
                  'bccilive.in', 'bcci-official.com']),
        ('npci', ['npci-upi.com', 'npci-bhim.com', 'npciin.com']),
    ]

    for brand, suspect_domains in INDIA_BRANDS:
        for domain in suspect_domains:
            query = f'site:{domain} OR "{domain}"'
            try:
                r = await client.get('https://serpapi.com/search', params={
                    'engine': 'google', 'q': query,
                    'api_key': SERP_KEY, 'num': 5,
                })
                results = r.json().get('organic_results', [])
                if results:
                    for item in results[:2]:
                        findings.append({
                            'source':      'domain_squatting',
                            'brand':       brand,
                            'domain':      domain,
                            'url':         item.get('link', ''),
                            'title':       item.get('title', ''),
                            'risk':        'HIGH',
                            'action':      f'Takedown notice to registrar',
                            'legal':       'Trade Marks Act 1999 Sec 29',
                            'evidence':    hashlib.sha256(
                                domain.encode()).hexdigest(),
                            'found_at':    datetime.now().isoformat(),
                        })
                await asyncio.sleep(0.3)
            except:
                pass

    return findings

async def run_darkweb_scan():
    print('='*55)
    print('  CINEOS DARK WEB INTELLIGENCE SCANNER')
    print('  Public data: paste sites, fraud tools,')
    print('  credential leaks, domain squatting')
    print('='*55)

    async with httpx.AsyncClient(timeout=15) as client:
        print('\n[1/4] Scanning paste sites...')
        paste  = await scan_paste_sites_india(client)
        print(f'  Paste site findings: {len(paste)}')

        print('\n[2/4] Scanning India fraud tools...')
        tools  = await scan_india_fraud_tools(client)
        print(f'  Fraud tool findings: {len(tools)}')

        print('\n[3/4] Scanning credential leak reports...')
        creds  = await scan_credential_leak_reports(client)
        print(f'  Credential leak reports: {len(creds)}')

        print('\n[4/4] Scanning domain squatting...')
        domains = await scan_domain_squatting(client)
        print(f'  Suspect domains: {len(domains)}')

    all_findings = {
        'generated_at':   datetime.now().isoformat(),
        'paste_sites':    paste,
        'fraud_tools':    tools,
        'credential_leaks': creds,
        'domain_squatting': domains,
        'totals': {
            'paste':   len(paste),
            'tools':   len(tools),
            'creds':   len(creds),
            'domains': len(domains),
            'total':   len(paste)+len(tools)+len(creds)+len(domains),
        }
    }

    # Print critical findings
    if tools:
        print(f'\n  CRITICAL — FRAUD TOOLS FOUND:')
        for t in tools[:5]:
            print(f"  → {t['title'][:60]}")
            print(f"    {t['url'][:70]}")

    if domains:
        print(f'\n  HIGH — DOMAIN SQUATTING:')
        for d in domains[:8]:
            print(f"  → {d['domain']:30} brand: {d['brand']}")

    os.makedirs('reports', exist_ok=True)
    json.dump(all_findings,
              open('reports/darkweb_intelligence.json', 'w'),
              indent=2, default=str)

    print(f'\n{"="*55}')
    print(f'  DARK WEB INTELLIGENCE COMPLETE')
    print(f'{"="*55}')
    print(f'  Paste sites:       {len(paste)}')
    print(f'  Fraud tools:       {len(tools)}')
    print(f'  Credential leaks:  {len(creds)}')
    print(f'  Domain squatting:  {len(domains)}')
    print(f'  Total:             {all_findings["totals"]["total"]}')
    print(f'  Saved: reports/darkweb_intelligence.json')
    print(f'\n  REFERRALS:')
    print(f'  Fraud tools → MHA + NPCI + CERT-In')
    print(f'  Credential leaks → CERT-In + affected banks')
    print(f'  Domain squatting → brand legal teams')
    return all_findings

asyncio.run(run_darkweb_scan())
