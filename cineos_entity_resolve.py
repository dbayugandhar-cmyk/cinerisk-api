"""
CINEOS Entity Resolution Engine
Core of the Number Intelligence product.

Input:  ANY identifier — phone, UPI, @handle, domain, keyword
Output: Full linked entity graph with all connected identifiers,
        confidence score, vertical classification, evidence trail.

This is the engine. The API and UI sit on top of this.
"""
import json, re, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

IST = timezone(timedelta(hours=5,minutes=30))

def load_data():
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))
    try:
        trai = json.load(open('configs/trai_series.json'))
    except:
        trai = {}
    return channels, alerts, trai

def detect_input_type(raw):
    """Detect what kind of identifier was entered."""
    raw = raw.strip()
    
    # Phone number
    digits = re.sub(r'[^\d]', '', raw)
    if len(digits) in (10, 11, 12) and digits[-10:][0] in '6789':
        return 'phone', '+91' + digits[-10:]
    
    # UPI handle
    if '@' in raw and '.' in raw.split('@')[-1]:
        return 'upi', raw.lower()
    
    # Telegram handle
    if raw.startswith('@') or raw.startswith('t.me/'):
        handle = raw.replace('t.me/','').replace('@','').lower()
        return 'telegram', handle
    
    # Domain
    if '.' in raw and ' ' not in raw and len(raw) > 4:
        return 'domain', raw.lower()
    
    # Keyword / brand name
    return 'keyword', raw.lower()


def resolve_entity(raw_input):
    """
    Master resolution function.
    Takes any input, finds everything connected to it.
    """
    channels, alerts, trai = load_data()
    
    input_type, normalized = detect_input_type(raw_input)
    
    # ── BUILD LOOKUP INDEXES ─────────────────────────────
    # Phone → channels
    phone_to_channels = defaultdict(list)
    for c in channels:
        for p in c.get('phones', []):
            if p: phone_to_channels[p].append(c)
    
    # UPI → channels
    upi_to_channels = defaultdict(list)
    for c in channels:
        for u in c.get('upis', []):
            if u: upi_to_channels[u.lower()].append(c)
    
    # Handle → channel
    handle_to_channel = {}
    for c in channels:
        h = c.get('username', '').lower()
        if h: handle_to_channel[h] = c
    
    # ── FIND SEED CHANNELS ───────────────────────────────
    seed_channels = []
    
    if input_type == 'phone':
        bare = normalized.replace('+','').replace(' ','')
        bare10 = bare[-10:]
        for p, chs in phone_to_channels.items():
            p_bare = p.replace('+','').replace(' ','')[-10:]
            if bare10 == p_bare:  # exact 10-digit match only
                seed_channels.extend(chs)
    
    elif input_type == 'upi':
        for u, chs in upi_to_channels.items():
            if normalized in u or u in normalized:
                seed_channels.extend(chs)
    
    elif input_type == 'telegram':
        if normalized in handle_to_channel:
            seed_channels.append(handle_to_channel[normalized])
    
    elif input_type == 'domain':
        for c in channels:
            if normalized in str(c.get('domains', [])) or \
               normalized in str(c.get('detail', '')).lower():
                seed_channels.append(c)
    
    elif input_type == 'keyword':
        brand_patterns = {
            'mahadev': 'Mahadev Book',
            'reddy anna': 'Reddy Anna',
            'radhe': 'Radhe Exchange',
            'world777': 'World777',
            'lotus365': 'Lotus365',
            'fairplay': 'Fairplay',
            'diamond': 'Diamond Exchange',
            'vipin': 'Vipin Aryan',
            'sawariya': 'Sawariya Exchange',
            'laser247': 'Laser247',
            'sky exch': 'Sky Exchange',
            'tiger': 'Tiger Exchange',
        }
        for c in channels:
            text = (c.get('username','') + ' ' + 
                   c.get('title','') + ' ' + 
                   str(c.get('bio',''))).lower()
            if normalized in text:
                seed_channels.append(c)
    
    # Deduplicate seed channels
    seen_ids = set()
    unique_seeds = []
    for c in seed_channels:
        cid = c.get('username', str(id(c)))
        if cid not in seen_ids:
            seen_ids.add(cid)
            unique_seeds.append(c)
    seed_channels = unique_seeds
    
    if not seed_channels:
        return build_empty_result(raw_input, input_type, normalized, trai)
    
    # ── EXPAND ENTITY GRAPH ──────────────────────────────
    # From seed channels, collect ALL linked identifiers
    all_phones  = set()
    all_upis    = set()
    all_handles = set()
    all_domains = set()
    all_cats    = Counter()
    
    for c in seed_channels:
        for p in c.get('phones', []):
            if p: all_phones.add(p)
        for u in c.get('upis', []):
            if u: all_upis.add(u.lower())
        h = c.get('username', '')
        if h: all_handles.add(h)
        for d in c.get('domains', []):
            if d: all_domains.add(d.lower())
        cat = c.get('category', '')
        if cat: all_cats[cat] += 1
    
    # Expand: find ALL channels connected to ANY of these phones
    expanded_channels = set()
    for p in all_phones:
        for c in phone_to_channels.get(p, []):
            expanded_channels.add(c.get('username', ''))
    
    all_connected = []
    for c in channels:
        if c.get('username', '') in expanded_channels:
            all_connected.append(c)
            for p in c.get('phones', []):
                if p: all_phones.add(p)
            for u in c.get('upis', []):
                if u: all_upis.add(u.lower())
    
    # ── ALIAS BRAND DETECTION ────────────────────────────
    BRAND_PATTERNS = {
        'Mahadev Book':     r'mahadev',
        'Reddy Anna':       r'reddy.?anna',
        'World777':         r'world.?777',
        'Lotus365':         r'lotus.?365',
        'Radhe Exchange':   r'radhe.?exch',
        'Diamond Exchange': r'diamond.?exch',
        'Fairplay':         r'fairplay',
        'Vipin Aryan':      r'vipin.?aryan',
        'Sawariya':         r'sawariya',
        'Tiger Exchange':   r'tiger.?exch',
        'Laser247':         r'laser.?247',
        'Sky Exchange':     r'sky.?exch',
        'Cricbet99':        r'cricbet.?99',
        'Betbhai9':         r'betbhai.?9',
        '1xBet':            r'1xbet',
        'Parimatch':        r'parimatch',
    }
    
    aliases = set()
    for c in seed_channels + all_connected:
        text = (c.get('username','') + ' ' + 
               c.get('title','') + ' ' + 
               str(c.get('bio',''))).lower()
        for brand, pat in BRAND_PATTERNS.items():
            if re.search(pat, text):
                aliases.add(brand)
    
    # ── CONFIDENCE SCORE ─────────────────────────────────
    n_channels = len(seed_channels)
    n_phones   = len(all_phones)
    
    if n_channels >= 7 or n_phones >= 5: conf = 95
    elif n_channels >= 5 or n_phones >= 3: conf = 85
    elif n_channels >= 3: conf = 80
    elif n_channels >= 2: conf = 75
    elif n_channels == 1: conf = 60
    else: conf = 0
    
    risk = ('CRITICAL' if conf >= 85 else
            'HIGH'     if conf >= 75 else
            'MEDIUM'   if conf >= 50 else 'LOW')
    
    # ── TIMELINE ─────────────────────────────────────────
    ph_bare = [p.replace('+','').replace(' ','')[-10:] 
               for p in all_phones]
    ph_alerts = [a for a in alerts 
                 if any(p in str(a) for p in ph_bare)]
    
    dates = sorted([a.get('detected_at','') 
                    for a in ph_alerts if a.get('detected_at','')])
    
    # ── FINANCIAL EXPOSURE ───────────────────────────────
    total_reach = sum(c.get('subscribers', 0) 
                      for c in seed_channels)
    daily_est   = int(total_reach * 0.001 * 500)
    
    # ── CO-NETWORK PHONES ────────────────────────────────
    # Other phones appearing in same channels
    co_phones = defaultdict(int)
    primary_phone = next(iter(sorted(all_phones, 
                    key=lambda p: len(phone_to_channels.get(p,[])), 
                    reverse=True)), None)
    
    for c in seed_channels:
        for p in c.get('phones', []):
            if p and p not in all_phones:
                co_phones[p] += 1
    
    # ── TRAI LOOKUP ──────────────────────────────────────
    carrier, circle = 'Unknown', 'Unknown'
    if primary_phone:
        d10 = primary_phone.replace('+91','')[-10:]
        info = trai.get(d10[:4]) or trai.get(d10[:3]) or {}
        carrier = info.get('operator', 'Unknown')
        circle  = info.get('circle', 'Unknown')
    
    # ── LEGAL FRAMEWORK ──────────────────────────────────
    primary_cat = all_cats.most_common(1)[0][0] if all_cats else 'unknown'
    LEGAL = {
        'illegal_betting':   ['Online Gaming Act 2025 §8', 'PMLA 2002 §3', 'IT Act §65B'],
        'crypto_fraud':      ['PMLA 2002 §3', 'IPC §420', 'IT Act §65B'],
        'upi_mule':          ['PMLA 2002 §3', 'RBI Digital Lending Guidelines'],
        'counterfeit_pharma':['Drugs & Cosmetics Act §17A', 'NDPS Act §8'],
        'loan_fraud':        ['RBI Guidelines', 'IT Act §66D', 'IPC §420'],
        'piracy':            ['Copyright Act §51', 'IT Act §65'],
        'investment_fraud':  ['SEBI Act §12A', 'IT Act §66D', 'IPC §420'],
    }
    legal_acts = LEGAL.get(primary_cat, ['IT Act §65B'])
    
    return {
        'input':        raw_input,
        'input_type':   input_type,
        'normalized':   normalized,
        'found':        True,
        'risk_level':   risk,
        'confidence':   conf,
        
        'entity_graph': {
            'phones':       sorted(all_phones),
            'upi_handles':  sorted(all_upis)[:10],
            'channels':     [c.get('username','') for c in seed_channels],
            'domains':      sorted(all_domains)[:5],
            'aliases':      sorted(aliases),
            'co_network':   dict(sorted(co_phones.items(), 
                                        key=lambda x:-x[1])[:5]),
        },
        
        'who': {
            'primary_phone': primary_phone,
            'carrier':       carrier,
            'circle':        circle,
            'aliases':       sorted(aliases),
            'operator_name': _infer_operator_name(aliases),
        },
        
        'what': {
            'categories':    dict(all_cats),
            'primary':       primary_cat,
            'channel_count': len(seed_channels),
            'total_reach':   total_reach,
            'cross_vertical': len(all_cats) > 1,
        },
        
        'when': {
            'first_detected': dates[0][:19] if dates else None,
            'last_detected':  dates[-1][:19] if dates else None,
            'alert_count':    len(ph_alerts),
        },
        
        'where': {
            'telecom_circle': circle,
            'carrier':        carrier,
            'top_channels':   [
                {'username': c.get('username',''),
                 'subscribers': c.get('subscribers',0),
                 'category': c.get('category','')}
                for c in sorted(seed_channels, 
                                key=lambda x:-x.get('subscribers',0))[:5]
            ],
        },
        
        'how': {
            'method':          'Cross-channel Telegram entity resolution',
            'daily_exposure':  f'₹{daily_est:,}' if daily_est else 'N/A',
            'monthly_exposure':f'₹{daily_est*30:,}' if daily_est else 'N/A',
            'pmla_threshold':  daily_est * 30 > 10_000_000,
        },
        
        'why': {
            'legal_framework': legal_acts,
            'primary_law':     legal_acts[0] if legal_acts else 'IT Act §65B',
        },
        
        'evidence': {
            'cert_id':    f'CINEOS-65B-{datetime.now(IST).strftime("%Y%m%d")}-{str(abs(hash(normalized)))[:6]}',
            'standard':   'IT Act 2000 §65B(2) — public source OSINT',
            'disclaimer': 'Intelligence-grade assessment. Confidence reflects attribution likelihood, not legal proof. Verify before enforcement action.',
        },
    }


def _infer_operator_name(aliases):
    """Infer primary operator name from alias set."""
    priority = ['Reddy Anna','Radhe Exchange','Vipin Aryan','Mahadev Book',
                'Vipin Aryan','Diamond Exchange','World777',
                'Lotus365','Fairplay','Laser247','Sky Exchange']
    for name in priority:
        if name in aliases:
            return name
    return aliases[0] if aliases else 'Unknown operator'


def build_empty_result(raw, input_type, normalized, trai):
    """Result for identifiers not in database."""
    # Zero-alert enrichment for phones
    carrier, circle, base_score, signals = 'Unknown', 'Unknown', 0, []
    
    if input_type == 'phone':
        d10 = normalized.replace('+91','')[-10:]
        info = trai.get(d10[:4]) or trai.get(d10[:3]) or {}
        carrier = info.get('operator', 'Unknown')
        circle  = info.get('circle', 'Unknown')
        
        HIGH_PREFIXES = {
            '8881':40,'8808':30,'7455':35,'7400':35,
            '7413':30,'7832':30,'8888':25,'9186':30,'9602':25,
        }
        base_score = HIGH_PREFIXES.get(d10[:4], 0)
        if base_score: 
            signals.append(f'Prefix {d10[:4]} matches known fraud operator geography')
        if 'Rajasthan' in circle and carrier == 'Jio':
            base_score += 15
            signals.append('Rajasthan Jio — highest fraud operator density in CINEOS database')
        if 'Andhra' in circle or 'Telangana' in circle:
            if carrier == 'Jio':
                base_score += 20
                signals.append('AP/Telangana Jio — known fraud operator network area')
    
    risk = ('MEDIUM' if base_score >= 25 else 
            'LOW'    if base_score > 0 else 'CLEAR')
    
    return {
        'input':      raw,
        'input_type': input_type,
        'normalized': normalized,
        'found':      False,
        'risk_level': risk,
        'confidence': base_score,
        'signals':    signals,
        'who':   {'carrier': carrier, 'circle': circle},
        'what':  {'categories': {}, 'channel_count': 0},
        'when':  {'first_detected': None, 'last_detected': None},
        'where': {'telecom_circle': circle, 'carrier': carrier},
        'how':   {'daily_exposure': 'N/A'},
        'why':   {'legal_framework': ['IT Act §65B']},
        'evidence': {
            'cert_id': f'CINEOS-65B-{datetime.now(IST).strftime("%Y%m%d")}-{str(abs(hash(normalized)))[:6]}',
            'standard': 'IT Act 2000 §65B(2)',
            'disclaimer': 'Phone not in CINEOS database. Pattern-based risk score only.',
        },
        'entity_graph': {
            'phones':[], 'upi_handles':[], 
            'channels':[], 'domains':[], 
            'aliases':[], 'co_network':{}
        },
    }


if __name__ == '__main__':
    import sys
    
    tests = sys.argv[1:] if len(sys.argv) > 1 else [
        '+918881754538',    # Phone — Reddy Anna
        'World777',         # Brand keyword
        '@Reddy_Annaw',     # Telegram handle
        '+919999999999',    # Unknown clean phone
        '+918881000000',    # Unknown AP/TG prefix
    ]
    
    print('=' * 65)
    print('  CINEOS ENTITY RESOLUTION ENGINE — TEST')
    print('=' * 65)
    
    for t in tests:
        result = resolve_entity(t)
        itype = result['input_type'].upper()
        risk  = result['risk_level']
        conf  = result['confidence']
        found = result['found']
        cats  = result.get('what',{}).get('categories',{})
        chs   = result.get('what',{}).get('channel_count',0)
        aliases = result.get('who',{}).get('aliases',[])
        name    = result.get('who',{}).get('operator_name','—')
        
        print(f'\n[{itype}] {t}')
        print(f'  Risk: {risk} ({conf}%) | Found: {found}')
        if found:
            print(f'  Operator: {name}')
            print(f'  Aliases:  {", ".join(aliases[:4])}')
            print(f'  Channels: {chs} | Categories: {list(cats.keys())}')
            g = result.get('entity_graph',{})
            print(f'  Phones:   {len(g.get("phones",[]))} | UPIs: {len(g.get("upi_handles",[]))}')
        else:
            sigs = result.get('signals',[])
            if sigs: print(f'  Signals: {sigs[0]}')
            print(f'  Circle: {result["where"]["telecom_circle"]}')
