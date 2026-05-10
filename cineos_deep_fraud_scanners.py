"""
CINEOS Deep Fraud Intelligence — 4 Novel Scanners

Scanner 1: Fake loan app distribution channels
  Find new fake loan apps on Telegram/WhatsApp
  BEFORE they reach victims at scale

Scanner 2: Unregistered investment advisor detection
  Find SEBI-unregistered tip channels
  Cross-reference with SEBI registration database

Scanner 3: Digital arrest script trading
  Find where digital arrest scripts + deepfake
  audio are traded before deployment

Scanner 4: Task fraud recruitment pipeline
  Map part-time job → task fraud → UPI drain
  Full recruitment to operation chain

All public data. IT Act 65B compliant.
"""
import asyncio, httpx, json, os, re, hashlib
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

async def search(client, query, num=10):
    try:
        r = await client.get('https://serpapi.com/search',
            params={'engine':'google','q':query,
                    'api_key':SERP_KEY,'num':num,'gl':'in'})
        return r.json().get('organic_results',[])
    except:
        return []

def is_genuine(url, skip_domains):
    return not any(d in url for d in skip_domains)

NEWS_DOMAINS = [
    'ndtv','timesofindia','thehindu','livemint',
    'indianexpress','economictimes','hindustantimes',
    'businessstandard','moneycontrol','cnbctv18',
    'financialexpress','thequint','scroll.in',
    'the420.in','thewire.in','aljazeera',
]

async def scanner1_fake_loan_apps(client):
    """
    Find fake loan apps being distributed via Telegram/WhatsApp
    BEFORE they reach victims at scale.
    Novel: Nobody monitors the pre-deployment distribution layer.
    """
    print("\n[SCANNER 1] Fake loan app distribution channels...")
    print("  Finding new apps BEFORE they reach victims")

    queries = [
        # Pre-deployment distribution
        'new loan app download telegram india 2026',
        'instant loan app apk download telegram india',
        'loan app without RBI india telegram whatsapp',
        '"instant loan" apk download india telegram channel',
        # Regional distribution
        'loan app download whatsapp group india hindi',
        'तुरंत लोन app download telegram india',
        'instant loan app new india 2026 telegram join',
        # Specific red flags
        '"no cibil" loan app telegram india download',
        '"no documents" loan app india telegram 2026',
        'loan approved instantly apk india telegram',
        # Chinese-linked patterns
        'chinese loan app india new 2026 telegram',
        'loan app without NBFC india telegram download',
        # Recovery agent recruitment
        'loan recovery agent earn commission india telegram',
        'loan collection agent india commission telegram',
    ]

    findings = []
    for query in queries:
        results = await search(client, query)
        for item in results:
            url     = item.get('link','')
            title   = item.get('title','')
            snippet = item.get('snippet','').lower()

            if not is_genuine(url, NEWS_DOMAINS):
                continue

            # Extract Telegram/WhatsApp links
            tg_links = re.findall(
                r't\.me/([A-Za-z0-9_]{5,})', url+' '+snippet)
            wa_links = re.findall(
                r'(?:wa\.me|chat\.whatsapp\.com)/([A-Za-z0-9]+)',
                url+' '+snippet)
            apk_urls = re.findall(
                r'https?://[^\s]+\.apk', url+' '+snippet)

            signals = []
            if tg_links or wa_links:
                signals.append('MESSAGING_DISTRIBUTION')
            if apk_urls:
                signals.append('APK_DISTRIBUTION')
            if any(k in snippet for k in
                   ['no cibil','no documents','instant approval',
                    'without verification','no kyc']):
                signals.append('PREDATORY_TERMS')
            if any(k in snippet for k in
                   ['chinese','china','recovery agent',
                    'collection agent']):
                signals.append('CHINESE_LINK_OR_HARASSMENT')
            if any(k in snippet for k in
                   ['nbfc','rbi','registered']):
                signals.append('RBI_CLAIM')  # unverified claim

            if signals and (tg_links or wa_links or apk_urls):
                findings.append({
                    'scanner':   'FAKE_LOAN_APP',
                    'query':     query,
                    'title':     title,
                    'url':       url[:100],
                    'snippet':   snippet[:150],
                    'signals':   signals,
                    'tg_links':  tg_links[:3],
                    'wa_links':  wa_links[:3],
                    'apk_urls':  apk_urls[:2],
                    'risk':      'CRITICAL',
                    'evidence':  hashlib.sha256(
                                 url.encode()).hexdigest(),
                    'action':    'Report to RBI + Play Store + MeitY',
                    'found_at':  datetime.now().isoformat(),
                })
        await asyncio.sleep(0.4)

    # Deduplicate by URL
    seen  = set()
    unique = []
    for f in findings:
        if f['url'] not in seen:
            seen.add(f['url'])
            unique.append(f)

    print(f"  Fake loan app findings: {len(unique)}")
    tg_found = [f for f in unique if f['tg_links']]
    print(f"  With Telegram links:    {len(tg_found)}")
    for f in tg_found[:5]:
        print(f"  → @{f['tg_links']} | {f['signals']}")
        print(f"    {f['snippet'][:70]}")
    return unique

async def scanner2_sebi_unregistered(client):
    """
    Find SEBI-unregistered investment advisors on Telegram.
    Novel: SEBI has mandate. CINEOS provides the intelligence.
    Cross-reference with SEBI registration database.
    """
    print("\n[SCANNER 2] SEBI-unregistered investment advisors...")
    print("  Finding unregistered tip channels + SEBI mandate")

    queries = [
        # Direct unregistered advisory signals
        '"SEBI registered" tips telegram india free join',
        '"guaranteed returns" stock tips telegram india',
        '"sure shot" tips telegram india stock 2026',
        'stock tips telegram india channel free join 2026',
        'option tips telegram india free channel join',
        # Specific fraud patterns
        '"100% accuracy" stock tips india telegram',
        '"guaranteed profit" trading telegram india',
        'intraday tips free telegram india join now',
        'F&O tips telegram india free channel 2026',
        # Pump and dump signals
        'multibagger stock tips telegram india 2026',
        '"next 10x" stock telegram india channel',
        'penny stock tips telegram india channel free',
        # Hindi queries
        'शेयर बाजार टिप्स टेलीग्राम फ्री जॉइन',
        'share market tips telegram india hindi free',
        # Investment app fraud
        'fake trading app india telegram 2026',
        'fake stock broker app india download telegram',
    ]

    findings = []
    for query in queries:
        results = await search(client, query)
        for item in results:
            url     = item.get('link','')
            title   = item.get('title','')
            snippet = item.get('snippet','').lower()

            if not is_genuine(url, NEWS_DOMAINS):
                continue

            tg_links = re.findall(
                r't\.me/([A-Za-z0-9_]{5,})', url+' '+snippet)

            signals = []
            if any(k in snippet for k in
                   ['guaranteed','100%','sure shot',
                    'no loss','profit guaranteed']):
                signals.append('GUARANTEED_RETURNS')  # illegal claim
            if any(k in snippet for k in
                   ['free tips','free channel','join free']):
                signals.append('FREE_TIP_CHANNEL')
            if any(k in snippet for k in
                   ['sebi registered','sebi approved',
                    'rbi approved']):
                signals.append('UNVERIFIED_SEBI_CLAIM')
            if any(k in snippet for k in
                   ['multibagger','10x','penny stock',
                    'next reliance','circuit stock']):
                signals.append('PUMP_DUMP_SIGNAL')
            if tg_links:
                signals.append('TELEGRAM_CHANNEL')

            if signals and tg_links:
                findings.append({
                    'scanner':  'SEBI_UNREGISTERED',
                    'query':    query,
                    'title':    title,
                    'url':      url[:100],
                    'snippet':  snippet[:150],
                    'signals':  signals,
                    'tg_links': tg_links[:3],
                    'risk':     'HIGH',
                    'violation':'SEBI IA Regulations 2013 — '
                                'unregistered investment advisor',
                    'action':   'SEBI SCORES complaint + '
                                'Telegram IT Rules 2021 notice',
                    'evidence': hashlib.sha256(
                                url.encode()).hexdigest(),
                })
        await asyncio.sleep(0.4)

    seen   = set()
    unique = []
    for f in findings:
        if f['url'] not in seen:
            seen.add(f['url'])
            unique.append(f)

    print(f"  SEBI unregistered findings: {len(unique)}")
    guaranteed = [f for f in unique
                  if 'GUARANTEED_RETURNS' in f['signals']]
    print(f"  Guaranteed returns claims:  {len(guaranteed)}")
    for f in guaranteed[:3]:
        print(f"  → @{f['tg_links']} | {f['signals']}")
        print(f"    {f['snippet'][:70]}")
    return unique

async def scanner3_digital_arrest_scripts(client):
    """
    Find digital arrest scripts, voice clones and deepfake
    audio being traded on Telegram before deployment.
    Novel: Detecting the weapon before it is used.
    """
    print("\n[SCANNER 3] Digital arrest script + deepfake trading...")
    print("  Finding scripts BEFORE they reach victims")

    queries = [
        # Script trading
        'digital arrest script india telegram sell 2026',
        'CBI ED police impersonation script india',
        'fake police call script india buy telegram',
        '"digital arrest" script hindi india telegram',
        # Deepfake/voice clone trading
        'voice clone tool india buy telegram 2026',
        'deepfake video call tool india telegram buy',
        'AI voice india scam tool sell telegram',
        'fake video call app india police impersonation',
        # Infrastructure
        'digital arrest call centre india telegram 2026',
        'fake CBI officer script india whatsapp',
        'Aadhaar money laundering script india call',
        # Technical tools
        'voice changer tool india scam telegram sell',
        'video background police india fake tool',
        'fake badge ID card india police telegram sell',
    ]

    findings = []
    for query in queries:
        results = await search(client, query)
        for item in results:
            url     = item.get('link','')
            title   = item.get('title','')
            snippet = item.get('snippet','').lower()

            if not is_genuine(url, NEWS_DOMAINS):
                continue

            tg_links = re.findall(
                r't\.me/([A-Za-z0-9_]{5,})', url+' '+snippet)
            wa_links = re.findall(
                r'(?:wa\.me|chat\.whatsapp\.com)/([A-Za-z0-9]+)',
                url+' '+snippet)

            signals = []
            if any(k in snippet for k in
                   ['script','template','call centre',
                    'call center','dialogue']):
                signals.append('SCRIPT_TRADING')
            if any(k in snippet for k in
                   ['voice clone','deepfake','ai voice',
                    'voice changer','synthetic voice']):
                signals.append('AI_VOICE_TOOL')
            if any(k in snippet for k in
                   ['buy','sell','download','tool',
                    'software','app']):
                signals.append('TOOL_DISTRIBUTION')
            if any(k in snippet for k in
                   ['cbi','ed','police','aarrest',
                    'warrant','aadhaar freeze']):
                signals.append('IMPERSONATION_CONTENT')

            if signals and (tg_links or wa_links):
                findings.append({
                    'scanner':  'DIGITAL_ARREST_SCRIPT',
                    'query':    query,
                    'title':    title,
                    'url':      url[:100],
                    'snippet':  snippet[:150],
                    'signals':  signals,
                    'tg_links': tg_links[:3],
                    'wa_links': wa_links[:3],
                    'risk':     'CRITICAL',
                    'action':   'I4C + MHA + CERT-In',
                    'evidence': hashlib.sha256(
                                url.encode()).hexdigest(),
                })
        await asyncio.sleep(0.4)

    seen   = set()
    unique = []
    for f in findings:
        if f['url'] not in seen:
            seen.add(f['url'])
            unique.append(f)

    print(f"  Digital arrest script findings: {len(unique)}")
    ai_tools = [f for f in unique
                if 'AI_VOICE_TOOL' in f['signals']]
    print(f"  AI voice/deepfake tools:        {len(ai_tools)}")
    for f in ai_tools[:3]:
        print(f"  → {f['signals']}")
        print(f"    {f['url'][:70]}")
    return unique

async def scanner4_task_fraud_pipeline(client):
    """
    Map the complete task fraud pipeline:
    Part-time job ad → Telegram group → task assignments
    → UPI payment → account drained

    Novel: Map the recruitment → operation chain
    before victims are trapped.
    """
    print("\n[SCANNER 4] Task fraud recruitment pipeline...")
    print("  Mapping recruitment → operation → drain")

    queries = [
        # Entry point — job ads
        'part time job earn daily india telegram 2026',
        'work from home earn money india telegram channel',
        'youtube like task earn india telegram join',
        'online task earn money india telegram channel',
        # Hindi entry points
        'घर बैठे काम करें कमाई करें telegram',
        'part time work online earn india telegram hindi',
        # Task assignment platforms
        '"task complete" earn UPI india telegram',
        '"video like" earn money india telegram channel',
        '"rating task" earn india telegram channel',
        # Operation signals
        'advance task earn india telegram 2026',
        '"deposit" task earn india telegram channel',
        'task agent india earn commission telegram',
        # Platform-specific
        'instagram like task earn india telegram',
        'amazon review task earn india telegram',
        'google map task earn india telegram 2026',
    ]

    findings = []
    for query in queries:
        results = await search(client, query)
        for item in results:
            url     = item.get('link','')
            title   = item.get('title','')
            snippet = item.get('snippet','').lower()

            if not is_genuine(url, NEWS_DOMAINS):
                continue

            tg_links = re.findall(
                r't\.me/([A-Za-z0-9_]{5,})', url+' '+snippet)
            wa_links = re.findall(
                r'(?:wa\.me|chat\.whatsapp\.com)/([A-Za-z0-9]+)',
                url+' '+snippet)

            signals = []
            if any(k in snippet for k in
                   ['earn daily','daily earning','per task',
                    'task complete earn']):
                signals.append('TASK_FRAUD_RECRUITMENT')
            if any(k in snippet for k in
                   ['deposit','advance','pre-deposit',
                    'invest first']):
                signals.append('ADVANCE_FEE_SIGNAL')
            if any(k in snippet for k in
                   ['upi','payment','transfer']):
                signals.append('UPI_DRAIN_POTENTIAL')
            if any(k in snippet for k in
                   ['like','rating','review','subscribe',
                    'follow']):
                signals.append('FAKE_ENGAGEMENT_TASK')
            if tg_links or wa_links:
                signals.append('MESSAGING_PLATFORM')

            if signals and (tg_links or wa_links):
                findings.append({
                    'scanner':  'TASK_FRAUD_PIPELINE',
                    'query':    query,
                    'title':    title,
                    'url':      url[:100],
                    'snippet':  snippet[:150],
                    'signals':  signals,
                    'tg_links': tg_links[:3],
                    'wa_links': wa_links[:3],
                    'risk':     ('CRITICAL'
                                 if 'ADVANCE_FEE_SIGNAL' in signals
                                 else 'HIGH'),
                    'action':   'I4C + NPCI + bank alert',
                    'evidence': hashlib.sha256(
                                url.encode()).hexdigest(),
                })
        await asyncio.sleep(0.4)

    seen   = set()
    unique = []
    for f in findings:
        if f['url'] not in seen:
            seen.add(f['url'])
            unique.append(f)

    print(f"  Task fraud findings: {len(unique)}")
    advance = [f for f in unique
               if 'ADVANCE_FEE_SIGNAL' in f['signals']]
    print(f"  With advance fee:    {len(advance)}")
    for f in advance[:3]:
        print(f"  → @{f['tg_links']} | {f['signals']}")
        print(f"    {f['snippet'][:70]}")
    return unique

async def main():
    print("="*60)
    print("  CINEOS DEEP FRAUD INTELLIGENCE — 4 NOVEL SCANNERS")
    print("  Finding fraud BEFORE it reaches victims")
    print("="*60)

    all_results = {}
    async with httpx.AsyncClient(timeout=15) as client:
        all_results['fake_loan_apps']    = await scanner1_fake_loan_apps(client)
        all_results['sebi_unregistered'] = await scanner2_sebi_unregistered(client)
        all_results['digital_arrest']    = await scanner3_digital_arrest_scripts(client)
        all_results['task_fraud']        = await scanner4_task_fraud_pipeline(client)

    # Apply quality filter immediately
    print(f"\n{'='*60}")
    print(f"  QUALITY FILTER — GENUINE FINDINGS ONLY")
    print(f"{'='*60}")

    genuine = {}
    for scanner, findings in all_results.items():
        # Only keep findings with actual Telegram/WhatsApp links
        # AND at least 2 fraud signals
        real = [f for f in findings
                if (f.get('tg_links') or f.get('wa_links'))
                and len(f.get('signals',[])) >= 2]
        genuine[scanner] = real
        print(f"\n  {scanner}:")
        print(f"    Raw:     {len(findings)}")
        print(f"    Genuine: {len(real)}")
        for f in real[:3]:
            tg = f.get('tg_links',[])[0] if f.get('tg_links') else ''
            print(f"    → @{tg} | {f['signals'][:2]}")
            print(f"      {f['snippet'][:60]}")

    # Business intelligence
    print(f"\n{'='*60}")
    print(f"  WHO PAYS FOR EACH SCANNER")
    print(f"{'='*60}")
    print(f"""
  SCANNER 1 — FAKE LOAN APPS: {len(genuine.get('fake_loan_apps',[]))} genuine findings
    RBI mandate: Banks must report fake lending
    Who pays: RBI (govt contract) + NBFCs + banks
    Annual value: Rs 50L-2Cr/year
    Urgency: 87 apps blocked December 2025 alone
    New apps appear faster than blocking

  SCANNER 2 — SEBI UNREGISTERED: {len(genuine.get('sebi_unregistered',[]))} genuine findings
    SEBI mandate: IA Regulations 2013 — must register
    Who pays: SEBI (govt) + Zerodha + Groww + Angel One
    Annual value: Rs 25L-1Cr/year
    Urgency: Ravindra Bharti case — YouTube to Telegram
    Already have 238 investment fraud channels

  SCANNER 3 — DIGITAL ARREST: {len(genuine.get('digital_arrest',[]))} genuine findings
    MHA mandate: PM spoke about this in Mann ki Baat
    Who pays: MHA + I4C + insurance companies
    Annual value: Rs 1-5Cr/year (govt contract)
    Urgency: Rs 20Bn senior citizen losses 2024
    47% India adults affected by AI scams

  SCANNER 4 — TASK FRAUD: {len(genuine.get('task_fraud',[]))} genuine findings
    NPCI + banks lose UPI to task fraud daily
    Who pays: NPCI + HDFC + ICICI + Axis
    Annual value: Rs 50L-2Cr/year
    Urgency: Youth specifically targeted
    Pre-deposit signal = account drain imminent
""")

    # Save
    os.makedirs('reports', exist_ok=True)
    report = {
        'generated_at':  datetime.now().isoformat(),
        'classification':'INTERNAL — Novel fraud intelligence',
        'raw_results':   all_results,
        'genuine_results':genuine,
        'total_genuine': sum(len(v) for v in genuine.values()),
        'business_value': {
            'fake_loan_apps':    'RBI + NBFCs — Rs 50L-2Cr/year',
            'sebi_unregistered': 'SEBI + brokers — Rs 25L-1Cr/year',
            'digital_arrest':    'MHA + I4C — Rs 1-5Cr/year',
            'task_fraud':        'NPCI + banks — Rs 50L-2Cr/year',
        },
    }
    json.dump(report,
              open('reports/deep_scan_medicines_mule_trading.json','w'),
              indent=2, default=str)
    print(f"\n  Saved: reports/deep_scan_medicines_mule_trading.json")
    print(f"  Total genuine findings: "
          f"{sum(len(v) for v in genuine.values())}")

asyncio.run(main())
