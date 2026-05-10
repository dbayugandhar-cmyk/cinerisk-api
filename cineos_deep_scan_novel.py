"""
CINEOS Novel Intelligence Approach

WHAT NOBODY ELSE BUILDS:
The recruitment and supply chain layer — upstream of fraud.

LAYER 1: Mule account recruitment
  Where fraudsters recruit bank account holders
  These posts are PUBLIC — job boards, Telegram, Facebook
  Finding them = finding the fraud network BEFORE it operates

LAYER 2: Fake medicine distributor recruitment
  Where fake pharma networks recruit distributors
  Pharmacist WhatsApp groups, medicine distributor boards
  Finding them = finding counterfeit supply chain

LAYER 3: AI-generated QR code counterfeit detection
  Naza Medica used AI QR codes on fake medicine
  CINEOS can scan QR codes from IndiaMART sellers
  Detect AI-generated vs authentic QR codes

LAYER 4: XHelper-style app detection
  Apps that train mules and manage UPI fraud
  APK download sites, app stores, Telegram bots
  Finding these = finding the fraud infrastructure

LAYER 5: Cross-border money flow signals
  Dubai / China-linked UPI mule networks
  Hawala-adjacent Telegram channels
  International money movement via UPI
"""
import asyncio, httpx, json, os, re, hashlib
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

async def scan(client, query, gl='in', num=10):
    try:
        r = await client.get('https://serpapi.com/search',
            params={'engine':'google','q':query,
                    'api_key':SERP_KEY,'num':num,'gl':gl})
        return r.json().get('organic_results',[])
    except:
        return []

async def layer1_mule_recruitment(client):
    """
    Find where mule accounts are actively recruited.
    These are PUBLIC job posts — not private channels.
    This is the upstream layer nobody monitors.
    """
    print("\n[LAYER 1] Mule account recruitment scan...")

    queries = [
        # Direct recruitment
        'earn money share bank account india telegram 2026',
        '"share your account" earn commission india telegram',
        '"bank account rent" india earn money 2026',
        'part time earn money bank account india whatsapp',
        # Hindi recruitment
        'अपना बैंक अकाउंट शेयर करें कमाई करें',
        'bank account se paise kamao india telegram',
        # Specific platforms
        'site:facebook.com earn money bank account india',
        'site:instagram.com earn money bank account india',
        'naukri.com bank account agent earn commission india',
        # XHelper-style app recruitment
        'XHelper app india UPI money transfer agent',
        'money transfer agent earn commission india app',
        '"transfer agent" earn UPI india recruit',
        # Known mule recruitment terms
        '"mule account" recruit india telegram',
        'cyber fraud agent recruit india commission',
        'hawala agent recruit india telegram 2026',
    ]

    findings = []
    for query in queries:
        results = await scan(client, query)
        for item in results:
            url     = item.get('link','')
            title   = item.get('title','')
            snippet = item.get('snippet','').lower()

            # Skip news articles
            is_news = any(d in url for d in
                ['ndtv','timesofindia','thehindu','livemint',
                 'indianexpress','economictimes','the420.in'])

            signals = []
            if any(k in snippet for k in
                   ['share your account','bank account rent',
                    'account share','earn commission bank',
                    'transfer agent']):
                signals.append('DIRECT_MULE_RECRUITMENT')
            if any(k in snippet for k in
                   ['whatsapp','telegram','t.me']):
                signals.append('MESSAGING_RECRUITMENT')
            if any(k in snippet for k in
                   ['xhelper','payment gateway agent',
                    'upi agent earn']):
                signals.append('XHELPER_NETWORK')
            if any(k in snippet for k in
                   ['dubai','china','hong kong','foreign']):
                signals.append('CROSS_BORDER_LINK')

            if signals and not is_news:
                findings.append({
                    'layer':   'MULE_RECRUITMENT',
                    'query':   query,
                    'title':   title,
                    'url':     url[:120],
                    'snippet': snippet[:150],
                    'signals': signals,
                    'risk':    'CRITICAL' if 'DIRECT_MULE_RECRUITMENT'
                               in signals else 'HIGH',
                    'hash':    hashlib.sha256(
                               url.encode()).hexdigest(),
                })
        await asyncio.sleep(0.4)

    print(f"  Mule recruitment findings: {len(findings)}")
    critical = [f for f in findings
                if f['risk'] == 'CRITICAL']
    print(f"  Critical (direct):         {len(critical)}")
    for f in critical[:3]:
        print(f"  → {f['signals']}")
        print(f"    {f['url'][:70]}")
        print(f"    {f['snippet'][:80]}")
    return findings

async def layer2_pharma_distributor_recruitment(client):
    """
    Find where fake pharma distributor networks recruit.
    This is where the Unitel Pharma-type operations
    find their distribution agents.
    """
    print("\n[LAYER 2] Pharma distributor recruitment scan...")

    queries = [
        # Direct distributor recruitment
        'medicine distributor wanted india whatsapp telegram',
        'pharma agent wanted commission based india',
        'medicine wholesale agent recruit india telegram',
        'medical representative earn commission india',
        # Below-MRP supply chain
        'medicine below MRP wholesale agent india',
        'cheap medicine supplier india whatsapp group',
        'export surplus medicine agent india',
        'cancelled medicine stock india sell agent',
        # Specific drug types most counterfeited
        'cancer medicine wholesale agent india',
        'insulin cheap wholesale agent india',
        'hepatitis medicine distributor india',
        # Regional pharma recruitment (Hindi)
        'दवा एजेंट बनें कमाई करें',
        'medicine agent ban kamao india',
        # Platform-specific
        'site:facebook.com medicine agent india earn',
        'site:linkedin.com pharma agent commission india',
        'indiamart.com medicine distributor wanted',
    ]

    findings = []
    for query in queries:
        results = await scan(client, query)
        for item in results:
            url     = item.get('link','')
            title   = item.get('title','')
            snippet = item.get('snippet','').lower()

            is_news = any(d in url for d in
                ['ndtv','timesofindia','thehindu','livemint'])
            is_legit = any(d in url for d in
                ['cipla.com','sunpharma.com','mankind.in',
                 'naukri.com','linkedin.com/jobs'])

            signals = []
            if any(k in snippet for k in
                   ['below mrp','export surplus','cancelled',
                    'near expiry','without bill']):
                signals.append('GREY_MARKET_SUPPLY')
            if any(k in snippet for k in
                   ['whatsapp group','telegram channel',
                    't.me','wa.me']):
                signals.append('COVERT_RECRUITMENT')
            if any(k in snippet for k in
                   ['cancer','insulin','hepatitis','vaccine',
                    'rabies','albumin']):
                signals.append('HIGH_VALUE_DRUG')
            if any(k in snippet for k in
                   ['cash','no gst','without invoice',
                    'no bill required']):
                signals.append('OFF_BOOKS_OPERATION')

            if signals and not is_news and not is_legit:
                findings.append({
                    'layer':   'PHARMA_RECRUITMENT',
                    'query':   query,
                    'title':   title,
                    'url':     url[:120],
                    'snippet': snippet[:150],
                    'signals': signals,
                    'risk':    'CRITICAL' if len(signals) >= 2
                               else 'HIGH',
                    'hash':    hashlib.sha256(
                               url.encode()).hexdigest(),
                })
        await asyncio.sleep(0.4)

    print(f"  Pharma recruitment findings: {len(findings)}")
    return findings

async def layer3_ai_qr_counterfeit(client):
    """
    The Naza Medica case revealed AI-generated QR codes
    on counterfeit medicines. CINEOS can detect:
    1. Sites selling AI QR code generators for pharma
    2. Discussion of QR code bypass for medicine
    3. Tools to clone genuine medicine packaging
    """
    print("\n[LAYER 3] AI QR code counterfeit detection...")

    queries = [
        'AI QR code medicine fake india tool',
        'medicine QR code clone generator india',
        'fake QR code pharma india tool download',
        'CDSCO QR code bypass medicine india',
        'medicine packaging clone tool india',
        'counterfeit drug QR code india tool',
        '"naza medica" OR "QR code medicine fake" india',
        'AI generated drug label india sell',
        'medicine hologram clone india tool',
        'drug batch number fake generator india',
    ]

    findings = []
    for query in queries:
        results = await scan(client, query)
        for item in results:
            url     = item.get('link','')
            title   = item.get('title','')
            snippet = item.get('snippet','').lower()

            is_news = any(d in url for d in
                ['ndtv','the420.in','thehindu','livemint'])

            signals = []
            if any(k in snippet for k in
                   ['qr code clone','fake qr','clone qr',
                    'generate qr code medicine']):
                signals.append('QR_CLONE_TOOL')
            if any(k in snippet for k in
                   ['hologram clone','fake hologram',
                    'medicine hologram']):
                signals.append('HOLOGRAM_FRAUD')
            if any(k in snippet for k in
                   ['batch number fake','expiry date change',
                    'label clone']):
                signals.append('PACKAGING_FRAUD')
            if 'ai' in snippet and any(k in snippet for k in
                   ['medicine','drug','pharma','tablet']):
                signals.append('AI_ASSISTED_FRAUD')

            if signals and not is_news:
                findings.append({
                    'layer':   'AI_QR_COUNTERFEIT',
                    'query':   query,
                    'title':   title,
                    'url':     url[:120],
                    'snippet': snippet[:150],
                    'signals': signals,
                    'risk':    'CRITICAL',
                    'hash':    hashlib.sha256(
                               url.encode()).hexdigest(),
                })
        await asyncio.sleep(0.4)

    print(f"  AI QR counterfeit findings: {len(findings)}")
    return findings

async def layer4_xhelper_apps(client):
    """
    XHelper and similar apps manage UPI mule networks.
    Find: APK download sites, Telegram bots, app stores
    that distribute mule management infrastructure.
    """
    print("\n[LAYER 4] XHelper-style mule management apps...")

    queries = [
        'XHelper app UPI India download',
        'money mule app india UPI download',
        'UPI agent app india earn commission download',
        'bank account management app fraud india',
        'UPI transaction agent app india apk',
        'money transfer app india earn commission apk',
        '"payment agent" app india download telegram',
        'cyber fraud tool app india apk download',
        'UPI freeze bypass app india',
        'account freeze unblock tool india app',
    ]

    findings = []
    for query in queries:
        results = await scan(client, query)
        for item in results:
            url     = item.get('link','')
            title   = item.get('title','')
            snippet = item.get('snippet','').lower()

            is_news = any(d in url for d in
                ['ndtv','thehindu','livemint','hackernews'])
            is_security = any(d in url for d in
                ['cloudsek','cyble','group-ib','cert-in'])

            signals = []
            if any(k in snippet for k in
                   ['download','apk','install','get it']):
                signals.append('APK_DISTRIBUTION')
            if any(k in snippet for k in
                   ['freeze bypass','unblock account',
                    'kyc bypass']):
                signals.append('BYPASS_TOOL')
            if any(k in snippet for k in
                   ['earn commission','transfer agent',
                    'money mule']):
                signals.append('MULE_MANAGEMENT')
            if 't.me' in url or 'telegram' in snippet:
                signals.append('TELEGRAM_DISTRIBUTION')

            if signals and not is_news and not is_security:
                findings.append({
                    'layer':   'MULE_APP_INFRASTRUCTURE',
                    'query':   query,
                    'title':   title,
                    'url':     url[:120],
                    'snippet': snippet[:150],
                    'signals': signals,
                    'risk':    'CRITICAL' if 'BYPASS_TOOL'
                               in signals else 'HIGH',
                    'hash':    hashlib.sha256(
                               url.encode()).hexdigest(),
                })
        await asyncio.sleep(0.4)

    print(f"  Mule app findings: {len(findings)}")
    return findings

async def layer5_cross_border_flows(client):
    """
    Gujarat bust found Dubai links in mule network.
    China links in XHelper UPI fraud.
    Map cross-border money movement signals
    that are publicly visible.
    """
    print("\n[LAYER 5] Cross-border fraud flow detection...")

    queries = [
        'india UPI fraud china link telegram 2026',
        'india UPI money dubai hawala telegram 2026',
        'india cybercrime china payment gateway 2026',
        '"chinese payment gateway" UPI india fraud',
        'india hawala telegram channel 2026',
        'UAE india money transfer fraud telegram',
        'crypto UPI india fraud china network',
        'india scam call centre myanmar thailand 2026',
        'pig butchering india china link telegram',
        'india UPI fraud international link bank',
    ]

    findings = []
    for query in queries:
        results = await scan(client, query)
        for item in results:
            url     = item.get('link','')
            title   = item.get('title','')
            snippet = item.get('snippet','').lower()

            is_news = any(d in url for d in
                ['ndtv','thehindu','livemint',
                 'economictimes','hindustantimes'])

            signals = []
            if any(k in snippet for k in
                   ['china','chinese','beijing']):
                signals.append('CHINA_LINK')
            if any(k in snippet for k in
                   ['dubai','uae','abu dhabi']):
                signals.append('UAE_LINK')
            if any(k in snippet for k in
                   ['myanmar','cambodia','thailand',
                    'scam centre']):
                signals.append('SEA_SCAM_CENTRE')
            if any(k in snippet for k in
                   ['crypto','usdt','tether','bitcoin']):
                signals.append('CRYPTO_LAYERING')
            if 't.me' in url or 'telegram' in snippet:
                signals.append('TELEGRAM_COORDINATION')

            if len(signals) >= 2 and not is_news:
                findings.append({
                    'layer':   'CROSS_BORDER_FLOW',
                    'query':   query,
                    'title':   title,
                    'url':     url[:120],
                    'snippet': snippet[:150],
                    'signals': signals,
                    'risk':    'CRITICAL',
                    'hash':    hashlib.sha256(
                               url.encode()).hexdigest(),
                })
        await asyncio.sleep(0.4)

    print(f"  Cross-border findings: {len(findings)}")
    return findings

async def main():
    print("="*60)
    print("  CINEOS NOVEL INTELLIGENCE SCAN")
    print("  5 Layers — Upstream fraud detection")
    print("  Recruitment → Supply → Tools → Apps → Flows")
    print("="*60)

    async with httpx.AsyncClient(timeout=15) as client:
        l1 = await layer1_mule_recruitment(client)
        l2 = await layer2_pharma_distributor_recruitment(client)
        l3 = await layer3_ai_qr_counterfeit(client)
        l4 = await layer4_xhelper_apps(client)
        l5 = await layer5_cross_border_flows(client)

    all_findings = l1 + l2 + l3 + l4 + l5
    critical     = [f for f in all_findings
                    if f['risk'] == 'CRITICAL']

    # Deduplicate by URL
    seen = set()
    unique = []
    for f in all_findings:
        if f['url'] not in seen:
            seen.add(f['url'])
            unique.append(f)

    print(f"\n{'='*60}")
    print(f"  NOVEL SCAN RESULTS")
    print(f"{'='*60}")
    print(f"  Total findings:   {len(all_findings)}")
    print(f"  Unique:           {len(unique)}")
    print(f"  Critical:         {len(critical)}")

    by_layer = {}
    for f in unique:
        layer = f['layer']
        by_layer.setdefault(layer, []).append(f)

    for layer, findings in by_layer.items():
        crit = [f for f in findings if f['risk']=='CRITICAL']
        print(f"\n  {layer}:")
        print(f"    Total: {len(findings)} | Critical: {len(crit)}")
        for f in crit[:2]:
            print(f"    → {f['signals']}")
            print(f"      {f['url'][:65]}")

    # Save
    os.makedirs('reports', exist_ok=True)
    report = {
        'generated_at':  datetime.now().isoformat(),
        'classification':'INTERNAL — Novel upstream intelligence',
        'approach':      (
            'Scanning recruitment and supply chain layers '
            'upstream of fraud — where nobody else looks'
        ),
        'total':         len(unique),
        'critical':      len(critical),
        'layer1_mule_recruitment':         l1,
        'layer2_pharma_recruitment':       l2,
        'layer3_ai_qr_counterfeit':        l3,
        'layer4_xhelper_apps':             l4,
        'layer5_cross_border_flows':       l5,
        'novel_intelligence_value': {
            'for_npci':      'Mule recruitment upstream of UPI fraud',
            'for_banks':     'XHelper-style apps managing fraud ops',
            'for_sunpharma': 'Pharma distributor recruitment networks',
            'for_mha':       'Cross-border flow coordination channels',
            'for_cert_in':   'AI QR code counterfeit infrastructure',
        },
    }
    json.dump(report,
              open('reports/deep_scan_novel_approach.json','w'),
              indent=2, default=str)
    print(f"\n  Saved: reports/deep_scan_novel_approach.json")

    print(f"""
{"="*60}
  WHY THIS IS THE NOVEL APPROACH
{"="*60}

  WHAT OTHERS DO:          WHAT CINEOS ADDS:
  ──────────────────────   ──────────────────────────────
  Scan known fraud sites   Scan recruitment platforms
  Monitor dark web         Monitor job/agent boards
  Detect fraud in progress Detect fraud being SET UP
  React to incidents       Predict next incident

  The mule recruitment post appears BEFORE the UPI fraud.
  The pharma distributor recruitment appears BEFORE
  the counterfeit medicine reaches pharmacies.
  The XHelper app appears BEFORE the accounts are used.

  CINEOS monitoring the recruitment layer =
  Early warning system for both banks AND pharma companies.

  This is what nobody else has for India.
  This is what makes CINEOS worth Rs 2 Cr/year.
""")

asyncio.run(main())
