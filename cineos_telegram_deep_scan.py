"""
CINEOS Telegram Deep Scan
Reads last 20 messages from all 1,245 channels.
Extracts: phones, UPIs, operator names, sample posts,
          join links, payment details, domain mentions.

Generates HIGH QUALITY alerts with:
  - Real channel name + subscriber count
  - Actual operator phone numbers
  - Actual UPI IDs
  - Sample fraudulent post (evidence)
  - SHA-256 hash of actual message content
  - Full legal basis + next steps

Run time: 3-4 hours (rate-limit aware)
Resume:   saves progress, can restart

Usage:
  python3 cineos_telegram_deep_scan.py
  python3 cineos_telegram_deep_scan.py --resume
  python3 cineos_telegram_deep_scan.py --limit 100
"""

import asyncio, json, re, hashlib, os, sys, time, argparse
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.errors import (FloodWaitError, ChannelPrivateError,
                              UsernameNotOccupiedError, ChatAdminRequiredError,
                              ChannelBannedError, UserBannedInChannelError)
from telethon.tl.types import Channel, Chat
from collections import defaultdict

# ── CONFIG ────────────────────────────────────────────────
API_ID    = 38636931
API_HASH  = '852280f65386a00114ff7453eac7849b'
SESSION   = 'cineos_session'
IST       = timezone(timedelta(hours=5, minutes=30))
MSG_LIMIT = 50          # messages per channel
DELAY     = 3.0         # seconds between channels
MAX_FLOOD = 600         # max flood wait before stopping

CHANNELS_FILE = 'reports/all_channels.json'
ALERTS_FILE   = 'reports/alerts/live_alerts.json'
GRAPH_FILE    = 'reports/fraud_intelligence_graph.json'
PROGRESS_FILE = 'reports/deep_scan_progress.json'
RESULTS_FILE  = 'reports/deep_scan_results.json'

os.makedirs('reports/alerts', exist_ok=True)
os.makedirs('reports/scan_logs', exist_ok=True)

# ── REGEX PATTERNS ────────────────────────────────────────
UPI_RE = re.compile(
    r'\b([a-zA-Z0-9.\-_]{2,40}@(?:paytm|gpay|okaxis|ybl|okhdfcbank|'
    r'okicici|oksbi|apl|upi|ibl|axl|hdfcbank|icici|sbi|kotak|'
    r'waaxis|waicici|wairtel|freecharge|jiomoney|airtel|oksbi|'
    r'axisbank|pnb|boi|cub|dbs|federal|kvb|rbl|sc|uco|union|'
    r'abfspay|fifederal|idbi|indus|mahb|postpaid|'
    r'[a-zA-Z]{2,20}))\b', re.IGNORECASE)

PHONE_RE = re.compile(r'(?:(?:\+91|91|0)[\s\-]?)?([6-9]\d{4}[\s\-]?\d{5})\b')

DOMAIN_RE = re.compile(
    r'\b(?:https?://)?(?:www\.)?([a-zA-Z0-9\-]{3,40}'
    r'\.(?:com|in|net|org|co\.in|app|io|xyz|site|online|live))\b',
    re.IGNORECASE)

WHATSAPP_RE = re.compile(r'(?:wa\.me|chat\.whatsapp\.com)/([A-Za-z0-9]+)')

FRAUD_KEYWORDS = {
    # VERTICAL 1: ILLEGAL BETTING — strongest vertical
    'illegal_betting': [
        # Platform names
        'satta','matka','betting','bookie','bet id','cricket id',
        'laser247','betbhai','cricbet','tiger365','diamond exch',
        'reddy anna','mahadev','book online','toss fix','match fix',
        'sure shot','world777','lotus365','fairplay','radhe exch',
        'sky exch','1xbet','betway','wolf777','parimatch',
        'all panel','cricbuzz id','my99exch','play99exch',
        # Hindi/regional
        'satta king','matka result','kalyan matka','milan matka',
        'rajdhani','gali disawar','faridabad','id lene ke liye',
        'new id','online id','betting id',
        # Action signals
        'whatsapp karo','contact karo','id banao','withdrawal guaranteed',
    ],

    # VERTICAL 2: COLOUR PREDICTION — growing fast
    'colour_prediction': [
        '91club','okwin','jalwa','bdg win','wingo','daman','tiranga',
        'aviator','crash game','colour trade','big small','colour prediction',
        'color prediction','jai club','daman game','bharat club',
        'tc lottery','lottery king','predict colour','win colour',
        'spin earn','rummy circle','teen patti gold',
    ],

    # VERTICAL 3: CRYPTO FRAUD — cross-vertical with betting
    'crypto_fraud': [
        'usdt','tether','btc','eth','binance','guaranteed return',
        'daily profit','trading signal','pump signal','mining plan',
        'withdrawal usdt','crypto investment','p2p trader','usdt sell',
        'usdt buy','coin signal','token launch','defi earn',
        'crypto wallet','bitcoin doubler','crypto ponzi',
        # India-specific
        'usdt inr','usdt to inr','coinswitch','wazirx','coindcx',
        'crypto earn daily','crypto referral',
    ],

    # VERTICAL 4: BANKING FRAUD — needs real Telegram channels
    'upi_mule': [
        # Mule recruitment — what real channels say
        'bank account kit','account kit sell','sell bank account',
        'current account sell','company account sell',
        'upi id sell','upi earn commission','upi agent',
        'atm card sell','sim card sell','kyc document sell',
        'fake kyc','rent account','account rent',
        # OTP/bypass
        'otp bypass','otp sell','sim swap','otp agent',
        'carding','cvv dump','bank login sell',
        # Hawala signals
        'hawala','hundi','cash transfer','money transfer agent',
        'international transfer','western union','moneygram',
        # Job scam overlap
        'earn per transaction','commission per transfer',
        'work from home upi','upi task earn',
    ],

    # VERTICAL 5: PHARMA — real seller patterns
    'counterfeit_pharma': [
        # Weight loss drugs (high demand, heavily faked)
        'ozempic','semaglutide','mounjaro','tirzepatide','wegovy',
        'saxenda','victoza','rybelsus',
        # ED drugs
        'sildenafil','tadalafil','viagra','cialis','kamagra',
        'cenforce','fildena','vidalista',
        # Controlled substances
        'tramadol','alprazolam','xanax','clonazepam','diazepam',
        'codeine','pregabalin','zolpidem','ambien','modafinil',
        # Steroids
        'testosterone','dianabol','anavar','trenbolone','hgh',
        'growth hormone','stanozolol','winstrol','clenbuterol',
        # Seller signals
        'cod available','cash on delivery medicine','home delivery tablet',
        'original medicine','genuine medicine','buy medicine online',
        'prescription not required','no prescription needed',
        'medicine supplier','pharma distributor','wholesale medicine',
        # India-specific
        'ayurvedic medicine sell','patanjali wholesale',
        'unani medicine','herbal supplier',
    ],

    # VERTICAL 6: INVESTMENT FRAUD
    'investment_fraud': [
        'guaranteed profit','stock tips','sebi unregistered',
        'option trading signal','nifty tips','sensex call',
        'insider tip','ipo allotment','mutual fund guaranteed',
        'portfolio management','wealth manager',
        'pig butchering','fake trading app','forex signal',
        'commodity tips','mcx tips','gold signal',
        '100 percent profit','double your money',
    ],

    # VERTICAL 7: PIRACY
    'piracy': [
        'free hotstar','free netflix','free amazon','cracked ott',
        'free web series','hd movies download','torrent link',
        'ipl live free','ipl stream','cricket live stream',
        'free subscription','ott account sell','shared account',
        'premium account free','disney plus free',
    ],

    # VERTICAL 8: TASK FRAUD
    'task_fraud': [
        'task earn','google review pay','youtube like pay',
        'instagram follow pay','part time work','daily task money',
        'earn 500 daily','earn 1000 daily','online part time',
        'simple task earn','work 2 hours earn','telegram task',
        'advance pay','withdrawal proof','task complete earn',
    ],

    # VERTICAL 9: LOAN FRAUD
    'loan_fraud': [
        'instant loan','no cibil check','personal loan fast',
        'loan app','easy loan no document','business loan quick',
        'loan without income proof','loan 5 minutes',
        'loan agent commission','processing fee loan',
        'loan recovery threat','loan harassment',
    ],

    # VERTICAL 10: AI / DIGITAL ARREST SCAM
    'ai_scam': [
        'digital arrest','ed officer','cbi notice','customs package',
        'your parcel seized','money laundering notice',
        'narcotics courier','police video call',
        'deepfake call','voice clone','ai video fraud',
        'sextortion','blackmail video','obscene video',
    ],

    # VERTICAL 11: DOMAIN SQUATTING / BRAND IMPERSONATION
    'domain_squat': [
        'jiohotstar','phonepe','paytm fake','gpay official',
        'amazon india fake','flipkart seller','hdfc official',
        'icici bank fake','sbi online fake','bcci official',
        'dream11 official','mpl game','rummy official',
        'fake payment gateway','payment failed refund',
    ],
}

LEGAL = {
    'illegal_betting':    'IT Act 2000 §65B + Public Gambling Act 1867 + OGA 2025 §8',
    'colour_prediction':  'IT Act 2000 §65B + Online Gaming Act 2025 §8 + FEMA 1999',
    'crypto_fraud':       'PMLA 2002 §3 + IT Act 2000 §65B + SEBI Act §12A',
    'investment_fraud':   'IT Act 2000 §66D + SEBI Act 1992 §12A + IPC §420',
    'upi_mule':           'IT Act 2000 §66 + PMLA §3 + IPC §420',
    'piracy':             'IT Act 2000 §65B + Copyright Act 1957 §51 + IT Rules 2021 §4(4)',
    'task_fraud':         'IT Act 2000 §66D + IPC §420',
    'loan_fraud':         'IT Act 2000 §66D + RBI Master Direction + IPC §420',
    'counterfeit_pharma': 'IT Act 2000 §65B + Drugs & Cosmetics Act 1940 §27',
    'ai_scam':            'IT Act 2000 §66D + §66C + IPC §419 §420',
    'domain_squat':       'IT Act 2000 §66D + Trade Marks Act 1999 §29 + UDRP',
}

NEXT_STEPS = {
    'illegal_betting':   ['Preserve evidence — SHA-256 hash archived','File NOGC complaint: nogc.gov.in','Report to state cybercrime cell with operator phone','Send Telegram takedown: abuse@telegram.org','Share with ED if crypto/Dubai link found'],
    'colour_prediction': ['Preserve evidence','File NOGC complaint — OGA 2025 §8 violation','Report app to Google Play / App Store','Send Telegram takedown','If Chinese-origin: report to MeitY'],
    'crypto_fraud':      ['Preserve evidence','File ED complaint: enforcement.gov.in','Report to FIU-IND: fiuindia.gov.in','File NCCRP: cybercrime.gov.in','Report to CERT-In if phishing site'],
    'investment_fraud':  ['Preserve evidence','Report to SEBI SCORES: scores.gov.in','Send Telegram takedown','Share operator details with cybercrime@sebi.gov.in','Alert CERT-In if phishing'],
    'upi_mule':          ['Preserve UPI + phone — hash done','Report mule UPIs to bank fraud desk immediately','File RBI Sachet: sachet.rbi.org.in','Report I4C: 1930 helpline','PMLA report to FIU-IND if >Rs 5L'],
    'piracy':            ['Preserve evidence','Send IT Rules 2021 §69A takedown: abuse@telegram.org','File with MIB: mib.gov.in','Report to BCCI / content owner','File NCCRP: cybercrime.gov.in'],
    'ai_scam':           ['Do NOT pay — it is a scam','Report immediately: cybercrime.gov.in / 1930','Preserve call recording + screenshot','File FIR at local PS','Report to TRAI: trai.gov.in'],
    'upi_mule':          ['Preserve UPI IDs + phone','Report to bank fraud desk immediately','File RBI Sachet: sachet.rbi.org.in','Report I4C: 1930','File PMLA if >Rs 5L'],
    'counterfeit_pharma':['Preserve evidence','File CDSCO complaint: cdsco.gov.in','Report to State Drug Controller','Notify brand owner legal team','Send Telegram takedown'],
    'domain_squat':      ['Preserve WHOIS evidence','File WIPO UDRP: wipo.int/amc','Report to registrar abuse team','Send C&D to registrant','Report CERT-In if phishing'],
}

REPORT_TO = {
    'illegal_betting':   ['NOGC — nogc.gov.in','State cybercrime cell','Telegram — abuse@telegram.org','ED — enforcement.gov.in'],
    'colour_prediction': ['NOGC — nogc.gov.in','MeitY — meity.gov.in','Telegram — abuse@telegram.org','I4C — cybercrime.gov.in'],
    'crypto_fraud':      ['ED — enforcement.gov.in','FIU-IND — fiuindia.gov.in','CERT-In — cert-in.org.in','I4C — 1930'],
    'investment_fraud':  ['SEBI SCORES — scores.gov.in','cybercrime@sebi.gov.in','I4C — cybercrime.gov.in'],
    'upi_mule':          ['Bank fraud desk','RBI Sachet — sachet.rbi.org.in','I4C — 1930','FIU-IND — fiuindia.gov.in'],
    'piracy':            ['MIB — mib.gov.in','BCCI — antipiracy@bcci.tv','JioHotstar — security@jiostar.com','Telegram — abuse@telegram.org'],
    'ai_scam':           ['I4C — 1930','MHA Cybercrime','TRAI — trai.gov.in','Local PS'],
    'counterfeit_pharma':['CDSCO — cdsco.gov.in','State Drug Controller','Brand owner legal','Telegram — abuse@telegram.org'],
    'domain_squat':      ['WIPO UDRP — wipo.int/amc','Domain registrar abuse','CERT-In','Brand owner legal'],
}

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

def clean_phone(p):
    digits = re.sub(r'[\s\-]', '', p)
    if len(digits) == 10 and digits[0] in '6789':
        return '+91' + digits
    if len(digits) == 12 and digits[:2] == '91':
        return '+' + digits
    return None

def classify(text):
    text_l = text.lower()
    scores = defaultdict(int)
    for cat, keywords in FRAUD_KEYWORDS.items():
        for kw in keywords:
            if kw in text_l:
                scores[cat] += 1
    if not scores:
        return 'unknown', 0
    best = max(scores, key=scores.get)
    return best, scores[best]

def severity(subs, phones, upis, cat, keyword_score):
    if subs > 500000 or (phones and cat in ['illegal_betting','upi_mule','crypto_fraud']):
        return 'critical'
    if subs > 100000 or phones or upis:
        return 'high'
    if keyword_score >= 3:
        return 'high'
    return 'medium'

# ── MAIN SCANNER ──────────────────────────────────────────

async def deep_scan(resume=False, limit=None):
    print('='*60)
    print(f'  CINEOS TELEGRAM DEEP SCAN')
    print(f'  {datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}')
    print(f'  Reading {MSG_LIMIT} messages per channel')
    print('='*60)

    # Load channels
    channels   = json.load(open(CHANNELS_FILE))
    if limit:
        channels = channels[:limit]

    # Load existing data
    try:
        existing_alerts = json.load(open(ALERTS_FILE))
    except:
        existing_alerts = []

    try:
        graph = json.load(open(GRAPH_FILE))
    except:
        graph = {'nodes': {}, 'edges': [], 'stats': {}}

    existing_ids = {a.get('id','') for a in existing_alerts}

    # Load progress if resuming
    scanned_usernames = set()
    if resume and os.path.exists(PROGRESS_FILE):
        prog = json.load(open(PROGRESS_FILE))
        scanned_usernames = set(prog.get('scanned', []))
        print(f'  Resuming: {len(scanned_usernames)} channels already scanned')

    # Sort: high subscribers first (most valuable data)
    channels.sort(key=lambda c: -c.get('subscribers', 0))

    # Connect
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    print(f'  Connected as: {(await client.get_me()).username}')
    print(f'  Channels to scan: {len(channels)}')
    print()

    # Stats
    stats = {
        'scanned': 0, 'skipped': 0, 'private': 0, 'errors': 0,
        'phones_found': 0, 'upis_found': 0, 'alerts_generated': 0,
        'start_time': datetime.now(IST).isoformat(),
    }
    new_alerts = []
    enriched_channels = []

    for i, ch in enumerate(channels):
        username = ch.get('username', '').strip('@').strip()
        if not username:
            stats['skipped'] += 1
            continue

        if username in scanned_usernames:
            continue

        try:
            # Fetch entity
            entity = await client.get_entity(f'@{username}')

            # Get messages
            messages = await client.get_messages(f'@{username}', limit=MSG_LIMIT)

            # Extract all text
            all_text = []
            for msg in messages:
                if msg.text:
                    all_text.append(msg.text)

            full_text = '\n'.join(all_text)

            # Extract identifiers
            raw_phones = PHONE_RE.findall(full_text)
            phones     = [p for p in [clean_phone(p) for p in raw_phones] if p]
            phones     = list(set(phones))
            # Filter fake numbers
            phones     = [p for p in phones if p not in ['+919999999999','+910000000000','+911234567890']]

            upis       = list(set(UPI_RE.findall(full_text)))
            domains    = list(set(DOMAIN_RE.findall(full_text)))
            wa_links   = list(set(WHATSAPP_RE.findall(full_text)))

            # Get real subscriber count
            subs = 0
            if hasattr(entity, 'participants_count') and entity.participants_count:
                subs = entity.participants_count
            else:
                subs = ch.get('subscribers', 0)

            # Classify
            bio_text   = getattr(entity, 'about', '') or ''
            title_text = getattr(entity, 'title', '') or ch.get('title', '')
            classify_text = title_text + ' ' + bio_text + ' ' + full_text
            cat, kw_score  = classify(classify_text)

            # Determine severity
            sev = severity(subs, phones, upis, cat, kw_score)

            # Update channel record
            ch['subscribers']   = subs
            ch['title']         = title_text
            ch['bio']           = bio_text[:200] if bio_text else ''
            ch['phones']        = phones
            ch['upi_ids']       = upis
            ch['domains']       = domains
            ch['wa_links']      = wa_links
            ch['category']      = cat if cat != 'unknown' else ch.get('category', 'unknown')
            ch['last_scanned']  = datetime.now(IST).isoformat()
            ch['message_count'] = len(messages)

            # Sample post (most recent non-empty message)
            sample_post = ''
            for msg in messages:
                if msg.text and len(msg.text) > 20:
                    sample_post = msg.text[:300]
                    break

            # Add to enriched list
            enriched_channels.append(ch)

            # Update stats
            stats['phones_found'] += len(phones)
            stats['upis_found']   += len(upis)

            # Generate alert if fraudulent
            if cat != 'unknown' and (subs > 1000 or phones or upis):
                alert_id = sha256(f'{username}{cat}{datetime.now(IST).strftime("%Y%m%d")}')[:16]

                if alert_id not in existing_ids:
                    alert = {
                        'id':           alert_id,
                        'title':        f'@{username} — {cat.replace("_"," ")} · {subs:,} subscribers',
                        'category':     cat,
                        'severity':     sev,
                        'platform':     'Telegram',
                        'detail':       f'{title_text[:80]} · {subs:,} subs · bio: {bio_text[:80]}' if bio_text else f'{title_text[:80]} · {subs:,} subscribers',
                        'detected_at':  datetime.now(IST).isoformat(),
                        'source':       'telegram_deep_scan',
                        'evidence_hash': sha256(f'{username}{subs}{full_text[:100]}'),
                        'legal_basis':  LEGAL.get(cat, 'IT Act 2000 §65B'),
                        'next_steps':   NEXT_STEPS.get(cat, ['Preserve evidence','File complaint at cybercrime.gov.in']),
                        'report_to':    REPORT_TO.get(cat, ['I4C — 1930','Telegram — abuse@telegram.org']),
                        'attribution': {
                            'name':    bio_text[:60] if bio_text else '',
                            'email':   '',
                            'phone':   phones[0] if phones else '',
                            'upi':     upis[0] if upis else '',
                            'address': '',
                            'source':  'telegram_message_scan',
                            'completeness': f'{sum(1 for x in [phones,upis,bio_text] if x)}/5 fields',
                        },
                        'chain': {
                            'channels_found':  [f'@{username}'],
                            'channel_title':   title_text,
                            'subscribers':     subs,
                            'keywords_matched': [kw for kw in FRAUD_KEYWORDS.get(cat,[])[:5] if kw in classify_text.lower()],
                            'reach':           subs,
                            'phones':          phones,
                            'upis':            upis,
                            'domains':         domains[:3],
                            'wa_links':        wa_links[:3],
                            'sample_post':     sample_post,
                            'bio':             bio_text[:200],
                            'evidence_hashes': [sha256(f'{username}{subs}{full_text[:100]}')[:16]],
                            'legal_basis':     LEGAL.get(cat, 'IT Act 2000 §65B'),
                            'recommended_action': NEXT_STEPS.get(cat,['Preserve evidence'])[0],
                            'report_to':       REPORT_TO.get(cat, ['I4C']),
                            'captured_at':     datetime.now(IST).isoformat(),
                            'operator_name':   None,
                            'operator_network': None,
                        },
                    }
                    new_alerts.append(alert)
                    existing_ids.add(alert_id)
                    stats['alerts_generated'] += 1

            # Update graph
            node_id = f'CHANNEL_{sha256(username)[:12]}'
            graph['nodes'][node_id] = {
                'id':          node_id,
                'type':        'CHANNEL',
                'username':    username,
                'title':       title_text,
                'category':    cat,
                'subscribers': subs,
                'bio':         bio_text[:200],
                'updated_at':  datetime.now(IST).isoformat(),
            }

            # Add phone nodes and edges
            for ph in phones:
                ph_id = f'PHONE_{sha256(ph)[:12]}'
                if ph_id not in graph['nodes']:
                    graph['nodes'][ph_id] = {
                        'id':         ph_id,
                        'type':       'PHONE',
                        'identifier': ph.replace('+91',''),
                        'properties': {
                            'number':    ph,
                            'source':    'telegram_deep_scan',
                            'whatsapp':  ph in full_text and 'whatsapp' in full_text.lower(),
                            'violations': list(FRAUD_KEYWORDS.get(cat,{})[:2]) if cat else [],
                            'confidence': 90,
                        },
                        'evidence_hash': sha256(ph),
                        'added_at':    datetime.now(IST).isoformat(),
                        'confidence':  90,
                    }
                # Add edge
                edge = {'from': node_id, 'to': ph_id, 'relation': 'has_phone', 'source': 'deep_scan'}
                if edge not in graph['edges']:
                    graph['edges'].append(edge)

            # Add UPI nodes and edges
            for upi in upis:
                upi_id = f'UPI_{sha256(upi)[:12]}'
                if upi_id not in graph['nodes']:
                    graph['nodes'][upi_id] = {
                        'id':        upi_id,
                        'type':      'UPI',
                        'label':     upi,
                        'upi_id':    upi,
                        'source':    'telegram_deep_scan',
                        'added_at':  datetime.now(IST).isoformat(),
                        'evidence_hash': sha256(upi),
                    }
                edge = {'from': node_id, 'to': upi_id, 'relation': 'has_upi', 'source': 'deep_scan'}
                if edge not in graph['edges']:
                    graph['edges'].append(edge)

            stats['scanned'] += 1
            scanned_usernames.add(username)

            # Print progress
            if phones or upis:
                print(f'  [{i+1:4}/{len(channels)}] @{username[:35]:35} {subs:>8,} subs  📞{len(phones)} 💳{len(upis)} [{cat[:15]}]')
            elif stats['scanned'] % 50 == 0:
                print(f'  [{i+1:4}/{len(channels)}] Scanned {stats["scanned"]} channels · '
                      f'{stats["phones_found"]} phones · {stats["upis_found"]} UPIs · '
                      f'{stats["alerts_generated"]} alerts')

            # Save progress every 100 channels
            if stats['scanned'] % 100 == 0:
                _save_all(channels, graph, new_alerts, existing_alerts, scanned_usernames, stats)
                print(f'\n  [CHECKPOINT] Saved at {stats["scanned"]} channels\n')

            await asyncio.sleep(DELAY)

        except FloodWaitError as e:
            wait = e.seconds
            print(f'\n  [FLOOD WAIT] {wait}s — {"saving and stopping" if wait > MAX_FLOOD else "waiting"}...')
            if wait > MAX_FLOOD:
                break
            await asyncio.sleep(wait + 5)

        except (ChannelPrivateError, ChannelBannedError,
                UsernameNotOccupiedError, UserBannedInChannelError):
            ch['status'] = 'private_or_banned'
            stats['private'] += 1

        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] <= 10:
                print(f'  Error @{username}: {type(e).__name__}: {str(e)[:60]}')

    await client.disconnect()

    # Final save
    _save_all(channels, graph, new_alerts, existing_alerts, scanned_usernames, stats)

    # Print summary
    print()
    print('='*60)
    print(f'  DEEP SCAN COMPLETE')
    print(f'  Scanned:          {stats["scanned"]} channels')
    print(f'  Private/banned:   {stats["private"]}')
    print(f'  Errors:           {stats["errors"]}')
    print(f'  Phones found:     {stats["phones_found"]} unique')
    print(f'  UPIs found:       {stats["upis_found"]} unique')
    print(f'  Alerts generated: {stats["alerts_generated"]} new')
    print()

    # Phone stats
    all_phones = []
    for ch in channels:
        all_phones.extend(ch.get('phones', []))
    phone_counts = defaultdict(int)
    for p in all_phones:
        phone_counts[p] += 1

    if phone_counts:
        print(f'  Top phones (seen in multiple channels):')
        for ph, cnt in sorted(phone_counts.items(), key=lambda x:-x[1])[:10]:
            print(f'    {ph}  ×{cnt} channels')

    # UPI stats
    all_upis = []
    for ch in channels:
        all_upis.extend(ch.get('upi_ids', []))
    if all_upis:
        from collections import Counter
        upi_counts = Counter(all_upis)
        print(f'\n  Top UPIs:')
        for upi, cnt in upi_counts.most_common(10):
            print(f'    {upi}  ×{cnt}')

    print()
    print(f'  Graph nodes: {len(graph["nodes"])}')
    print(f'  Graph edges: {len(graph["edges"])}')
    print('='*60)

    return stats


def _save_all(channels, graph, new_alerts, existing_alerts, scanned_usernames, stats):
    # Save channels
    json.dump(channels, open(CHANNELS_FILE, 'w'), indent=2, default=str)

    # Save graph
    graph['stats'] = {
        'total_nodes': len(graph['nodes']),
        'total_edges': len(graph['edges']),
        'updated_at': datetime.now(IST).isoformat(),
    }
    json.dump(graph, open(GRAPH_FILE, 'w'), indent=2, default=str)

    # Merge and save alerts
    all_alerts = new_alerts + existing_alerts
    # Dedup
    seen = set()
    deduped = []
    for a in all_alerts:
        if a.get('id') not in seen:
            seen.add(a.get('id'))
            deduped.append(a)

    # Sort by severity
    sev_order = {'critical':0,'high':1,'medium':2,'low':3}
    deduped.sort(key=lambda a: (sev_order.get(a.get('severity','low'),3),
                                 -(a.get('chain',{}).get('subscribers',0))))
    deduped = deduped[:2000]
    json.dump(deduped, open(ALERTS_FILE, 'w'), indent=2, default=str)

    # Save progress
    json.dump({
        'scanned': list(scanned_usernames),
        'stats': stats,
        'saved_at': datetime.now(IST).isoformat(),
    }, open(PROGRESS_FILE, 'w'), indent=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CINEOS Telegram Deep Scan')
    parser.add_argument('--resume', action='store_true', help='Resume from last checkpoint')
    parser.add_argument('--limit', type=int, help='Limit number of channels to scan')
    parser.add_argument('--top', type=int, default=0, help='Scan only top N by subscribers')
    args = parser.parse_args()

    limit = args.limit or (args.top if args.top else None)
    asyncio.run(deep_scan(resume=args.resume, limit=limit))
