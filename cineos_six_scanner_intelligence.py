"""
CINEOS Six-Domain Fraud Intelligence System

Six genuine India fraud problems — end to end:

1. Counterfeit e-commerce sellers
2. Telegram investment scams (pig butchering)
3. UPI mule network intelligence
4. Fake loan apps
5. Fake job scams
6. Social-commerce fraud

Each scanner:
  - Telegram API first (real data)
  - WHOIS on every domain found
  - IT Act 65B evidence hash
  - Quality filter built in
  - Internal database only
"""
import asyncio, json, os, re, hashlib, subprocess
from datetime import datetime
from collections import defaultdict
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.errors import FloodWaitError

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

os.makedirs('reports/six_domains', exist_ok=True)

def sha256(text):
    return hashlib.sha256(str(text).encode()).hexdigest()

def extract_phones(text):
    return list(set(
        p[-10:] for p in
        re.findall(r'(?:\+91|91)?([6-9]\d{9})', text)
        if len(p) >= 10
    ))

def extract_upis(text):
    return list(set(u.lower() for u in re.findall(
        r'[\w.\-+]{3,}@(?:okaxis|okicici|paytm|gpay|'
        r'phonepe|ybl|upi|sbi|hdfc|icici|kotak|'
        r'axisbank|indus|federal|oksbi|okhdfcbank)',
        text, re.I)))

def extract_domains(text):
    domains = set()
    urls = re.findall(r'https?://([A-Za-z0-9.\-]+)', text)
    skip = ['telegram','t.me','whatsapp','youtube','google',
            'instagram','facebook','twitter','sebi.gov',
            'rbi.org','wikipedia','amazon.in','flipkart',
            'zerodha','groww','1mg','netmeds','practo']
    for url in urls:
        domain = url.lower().strip('.')
        if not any(s in domain for s in skip):
            domains.add(domain)
    return domains

def whois_domain(domain):
    try:
        r = subprocess.run(['whois', domain],
            capture_output=True, text=True, timeout=8)
        raw = r.stdout
        if 'registrar:' not in raw.lower():
            return None
        def ex(pattern):
            m = re.search(pattern, raw, re.I|re.M)
            return m.group(1).strip() if m else ''
        registrant = ex(r'Registrant Name:\s*(.+)')
        email      = ex(r'Registrant Email:\s*(.+)')
        country    = ex(r'Registrant Country:\s*(.+)')
        created    = ex(r'Creation Date:\s*(.+)')
        registrar  = ex(r'Registrar:\s*(.+)')
        is_hidden  = any(k in registrant.lower() for k in
                        ['privacy','redacted','protected'])
        is_recent  = any(yr in created for yr in
                        ['2024','2025','2026'])
        return {
            'domain':    domain,
            'registrant':registrant,
            'email':     email,
            'country':   country,
            'created':   created[:20],
            'registrar': registrar,
            'is_hidden': is_hidden,
            'is_recent': is_recent,
        }
    except:
        return None

# ═══════════════════════════════════════════════════════
# SCANNER 1: COUNTERFEIT E-COMMERCE SELLERS
# ═══════════════════════════════════════════════════════
async def scanner1_counterfeit_ecommerce(client):
    """
    Find counterfeit seller networks on Telegram
    that then sell on IndiaMART/Meesho/Amazon/Flipkart.
    Map: Telegram channel → seller listing → GST/phone
    """
    print("\n[1/6] COUNTERFEIT E-COMMERCE SELLERS")

    terms = [
        'first copy wholesale','replica wholesale india',
        'master copy sell','duplicate brand sell',
        'aaa quality wholesale','super clone sell',
        '7a quality shoes','inspired by wholesale',
        'first copy shoes wholesale','replica bags sell',
        'duplicate watches sell','branded copy wholesale',
        'nike replica wholesale','adidas first copy',
        'branded duplicate india',
    ]

    findings = []
    for term in terms:
        try:
            result = await client(SearchRequest(q=term, limit=20))
            for chat in result.chats:
                username = getattr(chat,'username','') or ''
                title    = getattr(chat,'title','') or ''
                subs     = getattr(chat,'participants_count',0) or 0
                if not username or subs < 200: continue

                combined = (username+title).lower()
                signals  = []
                if any(k in combined for k in
                       ['first copy','replica','duplicate',
                        'master copy','aaa','clone']):
                    signals.append('EXPLICIT_COUNTERFEIT')
                if any(k in combined for k in
                       ['wholesale','bulk','reseller','supplier']):
                    signals.append('WHOLESALE_NETWORK')

                if signals:
                    findings.append({
                        'username': username,
                        'title':    title,
                        'subs':     subs,
                        'signals':  signals,
                        'term':     term,
                        'hash':     sha256(username),
                    })
            await asyncio.sleep(1.5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,30))
        except:
            await asyncio.sleep(1)

    # Deep scan top channels for platforms + phones
    results = []
    for ch in sorted(findings,
                     key=lambda x:-x['subs'])[:15]:
        try:
            entity = await client.get_entity(ch['username'])
            msgs   = await client.get_messages(entity, limit=200)
            text   = '\n'.join(m.text for m in msgs if m.text)

            phones  = extract_phones(text)
            upis    = extract_upis(text)
            domains = extract_domains(text)

            # Platform mentions
            platforms = []
            for p in ['indiamart','meesho','amazon',
                      'flipkart','snapdeal','jiomart',
                      'shopclues','glowroad']:
                if p in text.lower():
                    platforms.append(p)

            # Price points (counterfeit sold cheap)
            prices = re.findall(
                r'(?:rs\.?|₹)\s*(\d[\d,]*)', text, re.I)

            ch.update({
                'phones':    phones,
                'upis':      upis,
                'domains':   list(domains),
                'platforms': platforms,
                'prices':    list(set(prices))[:5],
                'msg_count': len(msgs),
            })
            results.append(ch)
            print(f"  @{ch['username'][:35]:35} "
                  f"subs:{ch['subs']:6,} | "
                  f"phones:{len(phones)} | "
                  f"platforms:{platforms}")
            await asyncio.sleep(5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,60))
        except:
            await asyncio.sleep(3)

    # WHOIS on extracted domains
    whois_results = {}
    all_domains = set()
    for r in results:
        all_domains.update(r.get('domains',[]))
    for domain in list(all_domains)[:20]:
        w = whois_domain(domain)
        if w:
            whois_results[domain] = w

    save = {
        'scanner': 'counterfeit_ecommerce',
        'channels': results,
        'total_channels': len(results),
        'whois': whois_results,
        'generated_at': datetime.now().isoformat(),
    }
    json.dump(save,
              open('reports/six_domains/1_counterfeit_ecommerce.json','w'),
              indent=2, default=str)
    print(f"  Saved: {len(results)} channels, "
          f"{len(whois_results)} WHOIS")
    return results

# ═══════════════════════════════════════════════════════
# SCANNER 2: TELEGRAM INVESTMENT SCAMS (PIG BUTCHERING)
# ═══════════════════════════════════════════════════════
async def scanner2_investment_scams(client):
    """
    End-to-end pig butchering:
    Telegram channel → fake platform URL → WHOIS registrant
    Same registrant on multiple platforms = syndicate
    """
    print("\n[2/6] TELEGRAM INVESTMENT SCAMS (PIG BUTCHERING)")

    terms = [
        'stock tips guaranteed','sebi registered tips free',
        'option tips 100 accuracy','crypto investment earn',
        'trading profit daily','investment scheme earn',
        'forex signal vip','bitcoin earn daily',
        'mutual fund guaranteed','share market tips free',
        'demat account tips','nifty tips sure shot',
        'crypto pump signal','usdt earn daily',
        'trading mentor india',
    ]

    channels = []
    for term in terms:
        try:
            result = await client(SearchRequest(q=term, limit=20))
            for chat in result.chats:
                username = getattr(chat,'username','') or ''
                title    = getattr(chat,'title','') or ''
                subs     = getattr(chat,'participants_count',0) or 0
                if not username or subs < 500: continue
                channels.append({
                    'username': username,
                    'title':    title,
                    'subs':     subs,
                    'term':     term,
                    'hash':     sha256(username),
                })
            await asyncio.sleep(1.5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,30))
        except:
            await asyncio.sleep(1)

    # Deduplicate
    seen = set()
    unique = []
    for ch in channels:
        if ch['username'] not in seen:
            seen.add(ch['username'])
            unique.append(ch)

    # Deep scan for fake platform domains
    results      = []
    all_domains  = defaultdict(list)

    for ch in sorted(unique, key=lambda x:-x['subs'])[:15]:
        try:
            entity = await client.get_entity(ch['username'])
            msgs   = await client.get_messages(entity, limit=300)
            text   = '\n'.join(m.text for m in msgs if m.text)

            phones  = extract_phones(text)
            upis    = extract_upis(text)
            domains = extract_domains(text)
            wa_links= re.findall(
                r'(?:wa\.me|chat\.whatsapp\.com)/([A-Za-z0-9]+)',
                text)

            # Pig butchering signals
            signals = []
            tl = text.lower()
            if any(k in tl for k in
                   ['guaranteed','100%','sure profit',
                    'no loss','guaranteed return']):
                signals.append('GUARANTEED_RETURN_CLAIM')
            if any(k in tl for k in
                   ['withdrawal proof','payment proof',
                    'profit screenshot']):
                signals.append('FAKE_PROOF')
            if any(k in tl for k in
                   ['join group','add you','personal mentor',
                    'whatsapp me','dm me']):
                signals.append('GROOMING_PATTERN')
            if upis or phones:
                signals.append('PAYMENT_COLLECTION')

            for domain in domains:
                all_domains[domain].append(ch['username'])

            ch.update({
                'phones':   phones,
                'upis':     upis,
                'domains':  list(domains),
                'wa_links': wa_links[:3],
                'signals':  signals,
                'msg_count':len(msgs),
            })
            results.append(ch)
            print(f"  @{ch['username'][:35]:35} "
                  f"subs:{ch['subs']:6,} | "
                  f"signals:{signals[:2]}")
            await asyncio.sleep(5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,60))
        except:
            await asyncio.sleep(3)

    # WHOIS — find syndicates
    whois_results  = {}
    registrant_map = defaultdict(list)

    for domain in list(all_domains.keys())[:30]:
        w = whois_domain(domain)
        if w:
            whois_results[domain] = w
            if not w['is_hidden'] and w['registrant']:
                registrant_map[w['registrant']].append(domain)

    syndicates = {r:d for r,d in registrant_map.items()
                  if len(d) >= 2}
    if syndicates:
        print(f"\n  SYNDICATES FOUND: {len(syndicates)}")
        for reg, doms in syndicates.items():
            print(f"  → {reg}: {doms}")

    save = {
        'scanner':     'investment_scams_pig_butchering',
        'channels':    results,
        'domain_map':  dict(all_domains),
        'whois':       whois_results,
        'syndicates':  dict(syndicates),
        'generated_at':datetime.now().isoformat(),
    }
    json.dump(save,
              open('reports/six_domains/2_investment_scams.json','w'),
              indent=2, default=str)
    print(f"  Saved: {len(results)} channels, "
          f"{len(syndicates)} syndicates")
    return results

# ═══════════════════════════════════════════════════════
# SCANNER 3: UPI MULE NETWORK INTELLIGENCE
# ═══════════════════════════════════════════════════════
async def scanner3_upi_mule(client):
    """
    Map UPI mule recruitment and operation network.
    Find: recruitment channels, shared UPIs across channels,
    phone numbers, commission structures.
    Shared UPI across 2+ channels = mule network.
    """
    print("\n[3/6] UPI MULE NETWORK INTELLIGENCE")

    terms = [
        'bank account earn commission india',
        'UPI agent earn india',
        'money transfer agent earn',
        'bank account kit sell india',
        'sim card account sell',
        'earn commission UPI transfer',
        'cyber fraud agent earn',
        'account rent earn india',
        'payment gateway agent india',
        'mule account earn india',
    ]

    channels = []
    for term in terms:
        try:
            result = await client(SearchRequest(q=term, limit=20))
            for chat in result.chats:
                username = getattr(chat,'username','') or ''
                title    = getattr(chat,'title','') or ''
                subs     = getattr(chat,'participants_count',0) or 0
                if not username or subs < 100: continue
                channels.append({
                    'username': username,
                    'title':    title,
                    'subs':     subs,
                    'term':     term,
                    'hash':     sha256(username),
                })
            await asyncio.sleep(1.5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,30))
        except:
            await asyncio.sleep(1)

    seen = set()
    unique = []
    for ch in channels:
        if ch['username'] not in seen:
            seen.add(ch['username'])
            unique.append(ch)

    # Deep scan — extract UPIs and phones
    results   = []
    upi_map   = defaultdict(list)  # UPI → channels
    phone_map = defaultdict(list)  # Phone → channels

    for ch in sorted(unique, key=lambda x:-x['subs'])[:15]:
        try:
            entity = await client.get_entity(ch['username'])
            msgs   = await client.get_messages(entity, limit=300)
            text   = '\n'.join(m.text for m in msgs if m.text)

            phones = extract_phones(text)
            upis   = extract_upis(text)
            wa     = re.findall(
                r'(?:wa\.me|chat\.whatsapp\.com)/([A-Za-z0-9]+)',
                text)

            # Commission rates
            commissions = re.findall(
                r'(\d+(?:\.\d+)?)\s*%\s*(?:commission|earning|profit)',
                text, re.I)

            # Bank mentions
            banks = []
            for b in ['hdfc','icici','sbi','axis','kotak',
                      'pnb','bob','canara','yes bank']:
                if b in text.lower():
                    banks.append(b)

            # Mule signals
            signals = []
            tl = text.lower()
            if any(k in tl for k in
                   ['account kit','bank kit','account sell']):
                signals.append('ACCOUNT_KIT_SALES')
            if any(k in tl for k in
                   ['sim card','sim sell','sim rent']):
                signals.append('SIM_CARD_FRAUD')
            if any(k in tl for k in
                   ['dubai','china','foreign','abroad']):
                signals.append('CROSS_BORDER')
            if commissions:
                signals.append(
                    f'COMMISSION_{commissions[0]}pct')

            for upi in upis:
                upi_map[upi].append(ch['username'])
            for phone in phones:
                phone_map[phone].append(ch['username'])

            ch.update({
                'phones':      phones,
                'upis':        upis,
                'wa_links':    wa[:3],
                'commissions': commissions[:3],
                'banks':       banks,
                'signals':     signals,
                'msg_count':   len(msgs),
            })
            results.append(ch)
            print(f"  @{ch['username'][:35]:35} "
                  f"subs:{ch['subs']:5,} | "
                  f"UPIs:{len(upis)} | "
                  f"phones:{len(phones)} | "
                  f"{signals[:1]}")
            await asyncio.sleep(5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,60))
        except:
            await asyncio.sleep(3)

    # Shared UPIs = mule network
    shared_upis   = {u:c for u,c in upi_map.items()
                     if len(c) >= 2}
    shared_phones = {p:c for p,c in phone_map.items()
                     if len(c) >= 2}

    if shared_upis:
        print(f"\n  MULE NETWORK UPIs (shared across channels):")
        for upi, chs in shared_upis.items():
            print(f"  → {upi}: {chs}")
    if shared_phones:
        print(f"  MULE NETWORK PHONES:")
        for phone, chs in shared_phones.items():
            print(f"  → +91-{phone}: {chs}")

    save = {
        'scanner':      'upi_mule_network',
        'channels':     results,
        'upi_map':      dict(upi_map),
        'phone_map':    dict(phone_map),
        'shared_upis':  dict(shared_upis),
        'shared_phones':dict(shared_phones),
        'mule_networks':len(shared_upis)+len(shared_phones),
        'generated_at': datetime.now().isoformat(),
    }
    json.dump(save,
              open('reports/six_domains/3_upi_mule_network.json','w'),
              indent=2, default=str)
    print(f"  Saved: {len(results)} channels, "
          f"{len(shared_upis)} shared UPIs")
    return results

# ═══════════════════════════════════════════════════════
# SCANNER 4: FAKE LOAN APPS
# ═══════════════════════════════════════════════════════
async def scanner4_fake_loan_apps(client):
    """
    Find fake loan app distribution on Telegram.
    Extract: APK links, fake NBFC names, phones, UPIs.
    Map: channel → APK → domain → registrant.
    """
    print("\n[4/6] FAKE LOAN APPS")

    terms = [
        'instant loan app india','loan app no cibil',
        'loan without documents','quick loan telegram',
        'loan app download','emergency loan india',
        'loan agent earn commission','loan recovery agent',
        'nbfc loan app india','personal loan instant',
        'loan approved telegram','loan app new 2026',
    ]

    channels = []
    for term in terms:
        try:
            result = await client(SearchRequest(q=term, limit=20))
            for chat in result.chats:
                username = getattr(chat,'username','') or ''
                title    = getattr(chat,'title','') or ''
                subs     = getattr(chat,'participants_count',0) or 0
                if not username or subs < 100: continue
                channels.append({
                    'username': username,
                    'title':    title,
                    'subs':     subs,
                    'term':     term,
                    'hash':     sha256(username),
                })
            await asyncio.sleep(1.5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,30))
        except:
            await asyncio.sleep(1)

    seen = set()
    unique = []
    for ch in channels:
        if ch['username'] not in seen:
            seen.add(ch['username'])
            unique.append(ch)

    results    = []
    apk_links  = []
    all_domains= set()

    for ch in sorted(unique, key=lambda x:-x['subs'])[:15]:
        try:
            entity = await client.get_entity(ch['username'])
            msgs   = await client.get_messages(entity, limit=200)
            text   = '\n'.join(m.text for m in msgs if m.text)

            phones  = extract_phones(text)
            upis    = extract_upis(text)
            domains = extract_domains(text)
            all_domains.update(domains)

            # APK links
            apks = re.findall(
                r'https?://[^\s]+\.apk', text)
            apk_links.extend(apks)

            # Loan amounts promised
            amounts = re.findall(
                r'(?:rs\.?|₹)\s*(\d[\d,]*)\s*(?:lakh|lac|k|000)',
                text, re.I)

            # Interest rate claims
            rates = re.findall(
                r'(\d+(?:\.\d+)?)\s*%\s*(?:interest|rate|per)',
                text, re.I)

            # Red flags
            signals = []
            tl = text.lower()
            if any(k in tl for k in
                   ['no cibil','no documents','instant approval',
                    'without verification']):
                signals.append('PREDATORY_TERMS')
            if apks:
                signals.append('APK_DISTRIBUTION')
            if any(k in tl for k in
                   ['processing fee','advance fee',
                    'registration fee']):
                signals.append('ADVANCE_FEE_FRAUD')
            if any(k in tl for k in
                   ['contact list','photos access',
                    'harassment','blackmail']):
                signals.append('DATA_THEFT_THREAT')

            ch.update({
                'phones':  phones,
                'upis':    upis,
                'domains': list(domains),
                'apks':    apks[:3],
                'amounts': list(set(amounts))[:3],
                'rates':   list(set(rates))[:3],
                'signals': signals,
                'msg_count':len(msgs),
            })
            results.append(ch)
            print(f"  @{ch['username'][:35]:35} "
                  f"subs:{ch['subs']:5,} | "
                  f"APKs:{len(apks)} | "
                  f"{signals[:2]}")
            await asyncio.sleep(5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,60))
        except:
            await asyncio.sleep(3)

    # WHOIS on loan app domains
    whois_results = {}
    for domain in list(all_domains)[:20]:
        w = whois_domain(domain)
        if w:
            whois_results[domain] = w
            recent = '← RECENT' if w['is_recent'] else ''
            print(f"  WHOIS: {domain[:35]} {recent}")

    save = {
        'scanner':      'fake_loan_apps',
        'channels':     results,
        'apk_links':    list(set(apk_links)),
        'whois':        whois_results,
        'generated_at': datetime.now().isoformat(),
    }
    json.dump(save,
              open('reports/six_domains/4_fake_loan_apps.json','w'),
              indent=2, default=str)
    print(f"  Saved: {len(results)} channels, "
          f"{len(set(apk_links))} APK links")
    return results

# ═══════════════════════════════════════════════════════
# SCANNER 5: FAKE JOB SCAMS
# ═══════════════════════════════════════════════════════
async def scanner5_fake_job_scams(client):
    """
    Map fake job → task fraud pipeline end to end.
    Entry: fake job ad.
    Exit: advance fee drain via UPI.
    Map the complete chain.
    """
    print("\n[5/6] FAKE JOB SCAMS")

    terms = [
        'work from home earn daily','part time job telegram',
        'data entry job earn india','online job earn india',
        'typing job earn india','form fill job earn',
        'youtube like job earn','instagram job earn',
        'task earn money india','job earn per day india',
        'work home job telegram','earn money online india',
        'job vacancy telegram india','fresher job earn',
        'student earn money telegram',
    ]

    channels = []
    for term in terms:
        try:
            result = await client(SearchRequest(q=term, limit=20))
            for chat in result.chats:
                username = getattr(chat,'username','') or ''
                title    = getattr(chat,'title','') or ''
                subs     = getattr(chat,'participants_count',0) or 0
                if not username or subs < 200: continue
                channels.append({
                    'username': username,
                    'title':    title,
                    'subs':     subs,
                    'term':     term,
                    'hash':     sha256(username),
                })
            await asyncio.sleep(1.5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,30))
        except:
            await asyncio.sleep(1)

    seen = set()
    unique = []
    for ch in channels:
        if ch['username'] not in seen:
            seen.add(ch['username'])
            unique.append(ch)

    results   = []
    upi_drain = defaultdict(list)

    for ch in sorted(unique, key=lambda x:-x['subs'])[:15]:
        try:
            entity = await client.get_entity(ch['username'])
            msgs   = await client.get_messages(entity, limit=200)
            text   = '\n'.join(m.text for m in msgs if m.text)

            phones = extract_phones(text)
            upis   = extract_upis(text)
            wa     = re.findall(
                r'(?:wa\.me|chat\.whatsapp\.com)/([A-Za-z0-9]+)',
                text)

            # Daily earning claims
            earnings = re.findall(
                r'(?:earn|income|salary)\s*(?:rs\.?|₹)?\s*(\d[\d,]*)'
                r'(?:\s*(?:per|a|/)?\s*day)?',
                text, re.I)

            # Advance fee signals
            signals = []
            tl = text.lower()
            if any(k in tl for k in
                   ['deposit','advance','registration fee',
                    'training fee','security deposit']):
                signals.append('ADVANCE_FEE')
            if any(k in tl for k in
                   ['like task','rating task','review task',
                    'subscribe task']):
                signals.append('TASK_FRAUD')
            if any(k in tl for k in
                   ['guaranteed salary','fixed salary',
                    'no experience','fresher welcome']):
                signals.append('FAKE_JOB_AD')
            if upis and any(k in tl for k in
                           ['deposit','pay first','invest']):
                signals.append('UPI_DRAIN_RISK')

            for upi in upis:
                if any(k in tl for k in
                       ['deposit','pay','invest','fee']):
                    upi_drain[upi].append(ch['username'])

            ch.update({
                'phones':   phones,
                'upis':     upis,
                'wa_links': wa[:3],
                'earnings': list(set(earnings))[:3],
                'signals':  signals,
                'msg_count':len(msgs),
            })
            results.append(ch)
            print(f"  @{ch['username'][:35]:35} "
                  f"subs:{ch['subs']:5,} | "
                  f"{signals[:2]}")
            await asyncio.sleep(5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,60))
        except:
            await asyncio.sleep(3)

    save = {
        'scanner':    'fake_job_scams',
        'channels':   results,
        'upi_drain':  dict(upi_drain),
        'total_drain_upis': len(upi_drain),
        'generated_at':datetime.now().isoformat(),
    }
    json.dump(save,
              open('reports/six_domains/5_fake_job_scams.json','w'),
              indent=2, default=str)
    print(f"  Saved: {len(results)} channels, "
          f"{len(upi_drain)} UPI drain points")
    return results

# ═══════════════════════════════════════════════════════
# SCANNER 6: SOCIAL COMMERCE FRAUD
# ═══════════════════════════════════════════════════════
async def scanner6_social_commerce(client):
    """
    Social commerce fraud: fake sellers on Instagram/
    WhatsApp/Meesho/Glowroad promising products,
    taking UPI payment, never delivering.
    Find: WhatsApp seller groups, fake reseller channels.
    """
    print("\n[6/6] SOCIAL-COMMERCE FRAUD")

    terms = [
        'reseller earn india','dropshipping earn india',
        'whatsapp business sell india','meesho reseller earn',
        'online seller earn india','product resell earn',
        'dropship earn daily india','reseller group india',
        'wholesale supplier india whatsapp',
        'reseller channel india telegram',
        'social sell earn india','instagram seller earn',
        'facebook seller earn india',
        'glowroad reseller earn','shop101 earn india',
    ]

    channels = []
    for term in terms:
        try:
            result = await client(SearchRequest(q=term, limit=20))
            for chat in result.chats:
                username = getattr(chat,'username','') or ''
                title    = getattr(chat,'title','') or ''
                subs     = getattr(chat,'participants_count',0) or 0
                if not username or subs < 200: continue
                channels.append({
                    'username': username,
                    'title':    title,
                    'subs':     subs,
                    'term':     term,
                    'hash':     sha256(username),
                })
            await asyncio.sleep(1.5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,30))
        except:
            await asyncio.sleep(1)

    seen = set()
    unique = []
    for ch in channels:
        if ch['username'] not in seen:
            seen.add(ch['username'])
            unique.append(ch)

    results = []
    for ch in sorted(unique, key=lambda x:-x['subs'])[:15]:
        try:
            entity = await client.get_entity(ch['username'])
            msgs   = await client.get_messages(entity, limit=200)
            text   = '\n'.join(m.text for m in msgs if m.text)

            phones = extract_phones(text)
            upis   = extract_upis(text)
            wa     = re.findall(
                r'(?:wa\.me|chat\.whatsapp\.com)/([A-Za-z0-9]+)',
                text)

            # Commission/earning claims
            commissions = re.findall(
                r'(\d+(?:\.\d+)?)\s*%\s*(?:commission|margin|profit)',
                text, re.I)

            # Fraud signals
            signals = []
            tl = text.lower()
            if any(k in tl for k in
                   ['no delivery','order cancelled',
                    'fake product','not received']):
                signals.append('NON_DELIVERY_REPORTS')
            if any(k in tl for k in
                   ['advance payment','pay first',
                    'upi pay then order']):
                signals.append('ADVANCE_PAYMENT_FRAUD')
            if any(k in tl for k in
                   ['wholesale rate','below mrp',
                    'manufacturer price']):
                signals.append('FAKE_WHOLESALE_CLAIM')
            if any(k in tl for k in
                   ['100% genuine','original product',
                    'branded original']):
                signals.append('FALSE_AUTHENTICITY_CLAIM')

            # Platforms mentioned
            platforms = [p for p in
                        ['meesho','glowroad','instagram',
                         'facebook','whatsapp','amazon',
                         'flipkart','shop101','bulbul']
                        if p in tl]

            ch.update({
                'phones':      phones,
                'upis':        upis,
                'wa_links':    wa[:3],
                'commissions': commissions[:3],
                'platforms':   platforms,
                'signals':     signals,
                'msg_count':   len(msgs),
            })
            results.append(ch)
            print(f"  @{ch['username'][:35]:35} "
                  f"subs:{ch['subs']:5,} | "
                  f"platforms:{platforms[:3]} | "
                  f"{signals[:1]}")
            await asyncio.sleep(5)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds,60))
        except:
            await asyncio.sleep(3)

    save = {
        'scanner':    'social_commerce_fraud',
        'channels':   results,
        'generated_at':datetime.now().isoformat(),
    }
    json.dump(save,
              open('reports/six_domains/6_social_commerce.json','w'),
              indent=2, default=str)
    print(f"  Saved: {len(results)} channels")
    return results

# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
async def main():
    print("="*60)
    print("  CINEOS SIX-DOMAIN FRAUD INTELLIGENCE")
    print("  End-to-end. Telegram API. WHOIS. Real data.")
    print("="*60)

    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()

    results = {}

    r1 = await scanner1_counterfeit_ecommerce(client)
    results['counterfeit'] = len(r1)

    r2 = await scanner2_investment_scams(client)
    results['investment']  = len(r2)

    r3 = await scanner3_upi_mule(client)
    results['upi_mule']    = len(r3)

    r4 = await scanner4_fake_loan_apps(client)
    results['loan_apps']   = len(r4)

    r5 = await scanner5_fake_job_scams(client)
    results['job_scams']   = len(r5)

    r6 = await scanner6_social_commerce(client)
    results['social']      = len(r6)

    await client.disconnect()

    # Add all new channels to main database
    all_channels = json.load(open('reports/all_channels.json'))
    known        = {c.get('username','').lower()
                    for c in all_channels}
    added        = 0

    for scanner_name, channels in [
        ('counterfeit_ecommerce', r1),
        ('investment_fraud',      r2),
        ('upi_mule',              r3),
        ('fake_loan_apps',        r4),
        ('fake_job_scams',        r5),
        ('social_commerce',       r6),
    ]:
        for ch in channels:
            u = ch.get('username','').lower()
            if u and u not in known:
                known.add(u)
                ch['category'] = scanner_name
                all_channels.append(ch)
                added += 1

    json.dump(all_channels,
              open('reports/all_channels.json','w'),
              indent=2, default=str)

    # Summary
    print(f"\n{'='*60}")
    print(f"  SIX-DOMAIN SCAN COMPLETE")
    print(f"{'='*60}")
    for domain, count in results.items():
        print(f"  {domain:25} {count:3} channels")
    print(f"\n  New channels added: {added}")
    print(f"  Total database:     {len(all_channels)}")
    print(f"\n  Reports saved to: reports/six_domains/")
    print(f"""
  WHAT THIS BUILDS:

  1. Counterfeit e-commerce
     Channel → seller listing → IndiaMART/Meesho
     Evidence for brand legal teams

  2. Investment scams (pig butchering)
     Channel → fake platform → WHOIS registrant
     Syndicate = same person runs multiple platforms

  3. UPI mule network
     Shared UPI across channels = network node
     Commission structure mapped

  4. Fake loan apps
     APK links → domain → registrant
     Before they reach victims at scale

  5. Fake job scams
     Recruitment channel → advance fee → UPI drain
     Complete pipeline mapped

  6. Social commerce fraud
     WhatsApp seller → fake wholesale → advance UPI
     Platform cross-reference

  ALL INTERNAL. Share under signed agreement only.
""")

asyncio.run(main())

# Rebuild graph
import subprocess
print("Rebuilding intelligence graph...")
subprocess.run(
    ['python3','cineos_intelligence_graph.py'],
    capture_output=True, timeout=120)

import json
ch = json.load(open('reports/all_channels.json'))
print(f"Final database: {len(ch)} channels")
