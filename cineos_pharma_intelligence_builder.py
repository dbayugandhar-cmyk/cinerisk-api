"""
CINEOS Pharma + UPI Fraud Intelligence Builder

Builds comprehensive database of:
1. Telegram channels selling counterfeit/fake medicines
2. WhatsApp groups — pharma wholesale fraud
3. IndiaMART counterfeit medicine sellers (GST validated)
4. UPI IDs collected from pharma fraud channels
5. Phone numbers from pharma fraud channels
6. Network graph — how channels connect
7. Modus operandi patterns
8. Brand-specific counterfeit intelligence

All public data. IT Act 65B compliant.
This becomes the internal intelligence database
that makes CINEOS credible when speaking to pharma companies.
"""
import asyncio, httpx, json, os, re, hashlib
from datetime import datetime
from collections import defaultdict
from telethon import TelegramClient

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"
SERP_KEY = os.environ.get('SERP_API_KEY','')

# ── TARGET BRANDS — top pharma + FMCG ────────────────────
TARGET_BRANDS = [
    # Indian pharma — most counterfeited
    'Sun Pharma', 'Cipla', 'Dr Reddys', 'Mankind',
    'Abbott', 'Pfizer India', 'Novartis India',
    'Sanofi India', 'GSK India', 'Lupin',
    # Specific high-value drugs
    'Revlimid', 'Herceptin', 'Avastin', 'Gleevec',
    'Trastuzumab', 'Bevacizumab', 'Erlotinib',
    'Sorafenib', 'Imatinib', 'Lenalidomide',
    # OTC brands most counterfeited
    'Crocin', 'Dolo 650', 'Combiflam', 'Calpol',
    'Augmentin', 'Azithral', 'Pan 40', 'Pantop',
    'Thyronorm', 'Eltroxin', 'Insulin Glargine',
    # Vaccines
    'Covishield', 'Covaxin', 'Rabies vaccine',
    'Hepatitis B vaccine', 'Human Albumin',
]

# ── SEARCH KEYWORDS ───────────────────────────────────────
PHARMA_FRAUD_KEYWORDS = [
    # Direct fraud signals
    'fake medicine sell telegram', 'duplicate medicine india',
    'replica tablet india', 'counterfeit pharma wholesale',
    'medicine wholesale below MRP telegram',
    'original medicine cheap telegram india',
    # Hindi keywords
    'नकली दवाई बेचना', 'असली दवा सस्ती टेलीग्राम',
    'दवा थोक सस्ता', 'कैंसर दवा सस्ती',
    # Specific drug fraud
    'cancer medicine cheap buy india telegram',
    'insulin cheap buy india telegram',
    'hepatitis medicine wholesale india',
    'vaccine buy cheap india telegram',
    'steroid tablet buy india online',
    'controlled drug buy india telegram',
    # Seller patterns
    'medicine export surplus india sell',
    'near expiry medicine sell india',
    'medicine without prescription india telegram',
    'pharma wholesale below MRP india',
    # IndiaMART patterns
    'medicine first copy indiamart',
    'pharmaceutical wholesale indiamart below MRP',
    'cancer drug indiamart cheap',
]

# ── UPI FRAUD KEYWORDS ────────────────────────────────────
UPI_FRAUD_KEYWORDS = [
    'UPI fraud network india telegram 2026',
    'mule account UPI india telegram buy',
    'bank account rent UPI india',
    'UPI phishing tool india 2026',
    'fake payment UPI india telegram tool',
    'BHIM UPI fraud india channel',
    'merchant fraud UPI screenshot india',
    'UPI account sell india telegram',
]

async def build_pharma_database():
    """Build comprehensive pharma fraud intelligence database."""
    print("="*55)
    print("  CINEOS PHARMA FRAUD INTELLIGENCE BUILDER")
    print("="*55)

    database = {
        'generated_at':    datetime.now().isoformat(),
        'classification':  'INTERNAL INTELLIGENCE',
        'legal_basis':     'Public data only. IT Act 65B compliant.',
        'telegram_channels':   [],
        'web_findings':        [],
        'indiamart_sellers':   [],
        'upi_findings':        [],
        'phone_numbers':       [],
        'brand_intelligence':  {},
        'network_graph':       {'nodes':[], 'edges':[]},
        'modus_operandi':      [],
        'pattern_library':     {},
    }

    # ── PHASE 1: TELEGRAM CHANNEL DISCOVERY ──────────────
    print("\n[1/4] Telegram channel discovery...")

    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()

    from telethon.tl.functions.contacts import SearchRequest
    tg_channels = []
    seen_usernames = set()

    for keyword in PHARMA_FRAUD_KEYWORDS[:15]:
        try:
            result = await client(SearchRequest(q=keyword, limit=15))
            for chat in result.chats:
                username = getattr(chat, 'username', '') or ''
                title    = getattr(chat, 'title', '') or ''
                subs     = getattr(chat, 'participants_count', 0) or 0

                if not username or username.lower() in seen_usernames:
                    continue
                if subs < 100:
                    continue

                seen_usernames.add(username.lower())
                combined = (username + title).lower()

                # Fraud signals
                fraud_signals = []
                if any(k in combined for k in
                       ['pharma','medicine','drug','tablet',
                        'दवा','medical','health','meds']):
                    fraud_signals.append('pharma_keyword')
                if any(k in combined for k in
                       ['wholesale','export','cheap','rate',
                        'थोक','discount','bulk']):
                    fraud_signals.append('wholesale_signal')
                if any(k in combined for k in
                       ['fake','copy','replica','duplicate',
                        'नकल','spurious']):
                    fraud_signals.append('explicit_counterfeit')

                if fraud_signals:
                    channel = {
                        'username':      username,
                        'title':         title,
                        'subscribers':   subs,
                        'fraud_signals': fraud_signals,
                        'discovered_by': keyword,
                        'risk_tier':     (
                            'CRITICAL' if 'explicit_counterfeit'
                            in fraud_signals else 'HIGH'),
                        'phones':        [],
                        'upis':          [],
                        'brands_mentioned': [],
                        'found_at':      datetime.now().isoformat(),
                        'evidence_hash': hashlib.sha256(
                            username.encode()).hexdigest(),
                    }
                    tg_channels.append(channel)

        except Exception as e:
            pass
        await asyncio.sleep(0.5)

    # Deep scan top channels for phones, UPIs, brand mentions
    print(f"  Channels found: {len(tg_channels)}")
    print(f"  Deep scanning top channels...")

    all_phones = defaultdict(list)
    all_upis   = defaultdict(list)
    brand_map  = defaultdict(list)

    for ch in sorted(tg_channels,
                     key=lambda x: -x.get('subscribers',0))[:20]:
        try:
            entity   = await client.get_entity(ch['username'])
            messages = await client.get_messages(entity, limit=200)
            subs     = getattr(entity,'participants_count',0) or 0
            ch['subscribers'] = subs

            all_text = ' '.join(m.text for m in messages if m.text)

            # Extract phones
            phones = list(set(
                p[-10:] for p in
                re.findall(r'(?:\+91|91)?([6-9]\d{9})', all_text)
            ))
            ch['phones'] = phones

            # Extract UPIs
            upis = list(set(u.lower() for u in re.findall(
                r'[\w.\-+]{3,}@(?:okaxis|okicici|paytm|gpay|'
                r'phonepe|ybl|upi|sbi|hdfc|icici|kotak)',
                all_text, re.I)))
            ch['upis'] = upis

            # Extract brand mentions
            brands_in = [b for b in TARGET_BRANDS
                        if b.lower() in all_text.lower()]
            ch['brands_mentioned'] = brands_in

            # Extract prices
            prices = re.findall(
                r'(?:rs\.?|₹)\s*(\d+)', all_text, re.I)
            ch['price_points'] = list(set(prices))[:5]

            # Extract WhatsApp links
            wa_links = re.findall(
                r'(?:wa\.me|chat\.whatsapp\.com)/([A-Za-z0-9]+)',
                all_text)
            ch['whatsapp_links'] = wa_links[:3]

            # Map to graph
            for p in phones:
                all_phones[p].append(ch['username'])
            for u in upis:
                all_upis[u].append(ch['username'])
            for b in brands_in:
                brand_map[b].append({
                    'channel':     ch['username'],
                    'subscribers': subs,
                })

            subs_str = (f"{subs/1000:.0f}K" if subs >= 1000
                       else str(subs))
            print(f"  📱 @{ch['username'][:35]:35} "
                  f"{subs_str:5} | "
                  f"phones:{len(phones)} | "
                  f"upis:{len(upis)} | "
                  f"brands:{len(brands_in)}")
            if phones:
                print(f"      Phones: {phones[:3]}")
            if upis:
                print(f"      UPIs:   {upis[:2]}")
            if brands_in:
                print(f"      Brands: {brands_in[:4]}")

        except Exception as e:
            pass
        await asyncio.sleep(5)  # rate limit protection

    await client.disconnect()

    database['telegram_channels'] = tg_channels
    database['phone_map']          = dict(all_phones)
    database['upi_map']            = dict(all_upis)
    database['brand_intelligence'] = dict(brand_map)

    # ── PHASE 2: WEB INTELLIGENCE ─────────────────────────
    print(f"\n[2/4] Web intelligence scan...")

    web_findings = []
    async with httpx.AsyncClient(timeout=15) as http:
        for keyword in PHARMA_FRAUD_KEYWORDS[:10]:
            try:
                r = await http.get('https://serpapi.com/search',
                    params={'engine':'google','q':keyword,
                            'api_key':SERP_KEY,'num':10,'gl':'in'})
                for item in r.json().get('organic_results',[]):
                    url     = item.get('link','')
                    title   = item.get('title','')
                    snippet = item.get('snippet','')

                    # Skip news (not actionable)
                    is_news = any(d in url for d in
                        ['ndtv','timesofindia','thehindu',
                         'indianexpress','livemint','economictimes'])

                    # Find Telegram usernames
                    usernames = re.findall(
                        r't\.me/([A-Za-z0-9_]{5,})', url+snippet)

                    web_findings.append({
                        'keyword':   keyword,
                        'title':     title,
                        'url':       url[:100],
                        'snippet':   snippet[:120],
                        'is_news':   is_news,
                        'usernames': usernames,
                        'hash':      hashlib.sha256(
                            url.encode()).hexdigest(),
                    })
                await asyncio.sleep(0.4)
            except:
                pass

    database['web_findings'] = web_findings
    print(f"  Web findings: {len(web_findings)}")

    # ── PHASE 3: UPI FRAUD INTELLIGENCE ──────────────────
    print(f"\n[3/4] UPI fraud intelligence scan...")

    upi_findings = []
    async with httpx.AsyncClient(timeout=15) as http:
        for keyword in UPI_FRAUD_KEYWORDS:
            try:
                r = await http.get('https://serpapi.com/search',
                    params={'engine':'google','q':keyword,
                            'api_key':SERP_KEY,'num':10,'gl':'in'})
                for item in r.json().get('organic_results',[]):
                    url     = item.get('link','')
                    snippet = item.get('snippet','')

                    # Extract UPI patterns from snippets
                    upis = re.findall(
                        r'[\w.\-+]{3,}@(?:okaxis|paytm|gpay|'
                        r'phonepe|ybl|upi|sbi|hdfc)',
                        snippet, re.I)

                    phones = re.findall(
                        r'(?:\+91|91)?([6-9]\d{9})', snippet)

                    upi_findings.append({
                        'keyword':  keyword,
                        'url':      url[:100],
                        'snippet':  snippet[:120],
                        'upis':     upis,
                        'phones':   [p[-10:] for p in phones],
                        'risk':     'HIGH' if upis or phones
                                    else 'MEDIUM',
                    })
                await asyncio.sleep(0.4)
            except:
                pass

    database['upi_findings'] = upi_findings
    print(f"  UPI findings: {len(upi_findings)}")

    # ── PHASE 4: PATTERN LIBRARY ──────────────────────────
    print(f"\n[4/4] Building pattern library...")

    database['modus_operandi'] = [
        {
            'pattern':     'Cheap critical medicine',
            'description': 'Cancer, diabetes, cardiac medicines '
                          'offered at 50-90% below MRP',
            'red_flags':   ['price below MRP','export surplus',
                           'near expiry','bulk wholesale'],
            'platforms':   ['Telegram','WhatsApp','IndiaMART'],
            'example':     'Unitel Pharma bust May 2026 — '
                          'Rs 10 Cr fake cancer/liver drugs',
        },
        {
            'pattern':     'CGHS diversion',
            'description': 'Genuine medicines diverted from '
                          'government health schemes, '
                          'resold as counterfeit or overpriced',
            'red_flags':   ['CGHS medicine','govt supply',
                           'hospital surplus'],
            'platforms':   ['WhatsApp','phone'],
            'example':     'Unitel Pharma — Vikram Singh + '
                          'Watan Saini accused of CGHS diversion',
        },
        {
            'pattern':     'Advanced packaging mimicry',
            'description': 'High-quality printing equipment used '
                          'to replicate genuine pharmaceutical '
                          'packaging exactly',
            'red_flags':   ['packaging equipment seized',
                           'holograms replicated',
                           'batch numbers fake'],
            'platforms':   ['Physical supply chain'],
            'example':     '90,000 capsules + machinery seized '
                          'Mukherjee Nagar Delhi May 2026',
        },
        {
            'pattern':     'Multi-state distribution network',
            'description': 'Manufacturing in one state, '
                          'distribution across multiple states '
                          'via agents — Northeast India common hub',
            'red_flags':   ['interstate network','multiple states',
                           'regional distributors'],
            'platforms':   ['Physical + Telegram + WhatsApp'],
            'example':     'Unitel Pharma: Delhi mfg → '
                          'Northeast + East India distribution',
        },
        {
            'pattern':     'Telegram wholesale group',
            'description': 'Private Telegram channels/groups '
                          'operating as pharma wholesale markets. '
                          'Members post prices, WhatsApp for orders',
            'red_flags':   ['wholesale','bulk rate','below MRP',
                           'contact on WhatsApp'],
            'platforms':   ['Telegram'],
            'example':     f'{len(tg_channels)} channels found by '
                          'CINEOS — active pharmaceutical fraud',
        },
    ]

    # Brand-specific intelligence summary
    database['brand_summary'] = {}
    for brand, channels in brand_map.items():
        total_reach = sum(c.get('subscribers',0) for c in channels)
        database['brand_summary'][brand] = {
            'channels_mentioning': len(channels),
            'total_reach':         total_reach,
            'risk':                'CRITICAL' if len(channels) > 3
                                   else 'HIGH',
        }

    # Shared phone/UPI = mule network
    shared_phones = {p:chs for p,chs in all_phones.items()
                     if len(chs) >= 2}
    shared_upis   = {u:chs for u,chs in all_upis.items()
                     if len(chs) >= 2}

    database['mule_indicators'] = {
        'shared_phones': dict(shared_phones),
        'shared_upis':   dict(shared_upis),
        'note': 'Same phone/UPI across multiple channels = '
                'coordinated operation or mule network',
    }

    # Save
    os.makedirs('reports', exist_ok=True)
    json.dump(database,
              open('reports/pharma_upi_intelligence_db.json','w'),
              indent=2, default=str)

    # Summary
    total_phones = sum(len(ch.get('phones',[])) for ch in tg_channels)
    total_upis   = sum(len(ch.get('upis',[])) for ch in tg_channels)
    total_reach  = sum(ch.get('subscribers',0) for ch in tg_channels)
    brands_found = len(brand_map)

    print(f"\n{'='*55}")
    print(f"  PHARMA + UPI DATABASE BUILT")
    print(f"{'='*55}")
    print(f"  Telegram channels:    {len(tg_channels)}")
    print(f"  Total reach:          {total_reach/1000:.0f}K subscribers")
    print(f"  Phones extracted:     {total_phones}")
    print(f"  UPI IDs extracted:    {total_upis}")
    print(f"  Brands mentioned:     {brands_found}")
    print(f"  Shared phones (mule): {len(shared_phones)}")
    print(f"  Shared UPIs (mule):   {len(shared_upis)}")
    print(f"  Modus patterns:       {len(database['modus_operandi'])}")
    print(f"  Web findings:         {len(web_findings)}")
    print(f"  UPI fraud findings:   {len(upi_findings)}")
    print(f"\n  Saved: reports/pharma_upi_intelligence_db.json")
    print(f"\n  WHAT THIS DATABASE ENABLES:")
    print(f"  → For Sun Pharma: show which channels mention")
    print(f"    their brand name + exact subscriber reach")
    print(f"  → For HDFC/NPCI: show UPI mule network + phones")
    print(f"  → For CDSCO: show 5 modus operandi patterns")
    print(f"    with Unitel bust as corroborating evidence")
    print(f"\n  WHAT GOES IN EMAIL (credible + monetary):")
    print(f"  → Only channels where brand is mentioned")
    print(f"  → Only if subscriber reach is significant")
    print(f"  → Pattern match to recent bust = urgency")
    print(f"  → Never: raw names, raw phones, raw WHOIS")

asyncio.run(build_pharma_database())
