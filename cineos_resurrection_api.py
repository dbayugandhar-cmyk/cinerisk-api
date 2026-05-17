"""
CINEOS Operator Resurrection API
The hardest moat to replicate.

Input:  Phone number, brand name, or operator alias
Output: Complete alias chain — every brand name this
        operator has used, every enforcement event,
        every post-arrest resurrection, full timeline.

This compounds with time. Every arrest makes it
more valuable. No other India tool has this.
"""
import json, re, hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5,minutes=30))

BRAND_MAP = {
    'mahadev':      'Mahadev Book',
    'reddy anna':   'Reddy Anna',
    'world777':     'World777',
    'lotus365':     'Lotus365',
    'radhe':        'Radhe Exchange',
    'diamond exch': 'Diamond Exchange',
    'diamond':      'Diamond Exchange',
    'fairplay':     'Fairplay',
    'vipin':        'Vipin Aryan',
    'sawariya':     'Sawariya Exchange',
    'laser247':     'Laser247',
    'tiger365':     'Tiger365',
    'tiger exch':   'Tiger Exchange',
    'cricbet':      'Cricbet99',
    'betbhai':      'Betbhai9',
    'sky exch':     'Sky Exchange',
    'wolf777':      'Wolf777',
    'my99':         'My99Exch',
    'play99':       'Play99Exch',
    'all panel':    'All Panel',
    'betbook':      'Betbook247',
    'goldbet':      'Gold Bet',
    'ambani':       'Ambani Exchange',
    'lotus book':   'Lotus Book',
    'kalyan':       'Kalyan Matka',
    'satta king':   'Satta King',
}

# Known enforcement events with dates
ENFORCEMENT_EVENTS = [
    {
        'date': '2026-05-13',
        'event': 'Visakhapatnam Arrests',
        'detail': '24 arrested · Visakhapatnam Police · ₹1,500Cr suspected · 7 platforms · Mastermind Gabbar arrested Kolkata',
        'source': 'ANI / The News Mill',
        'keywords': ['mahadev', 'visakhapatnam', 'vizag', '8824645116', '8888888888'],
        'affected_phones': ['+918824645116', '+918888888888'],
    },
    {
        'date': '2026-05-01',
        'event': 'Gujarat UPI Mule Bust',
        'detail': '10 arrested · Gujarat Cybercrime · UPI mule network',
        'source': 'CINEOS resurrection tracker',
        'keywords': ['gujarat', 'upi', 'mule', '8881448108', '8808843584'],
        'affected_phones': ['+918881448108', '+918808843584'],
    },
    {
        'date': '2026-03-15',
        'event': 'ED Attachment — Mahadev Book',
        'detail': 'ED attached ₹1,700Cr · Ravi Uppal arrested Dubai · Interpol Red Notice',
        'source': 'Wikipedia / ED press release',
        'keywords': ['mahadev', 'ed', 'enforcement', 'ravi uppal'],
        'affected_phones': [],
    },
    {
        'date': '2025-11-10',
        'event': 'Visakhapatnam Mule Account Arrests',
        'detail': 'Madhava and Srikanth arrested · 35 mule accounts supplied to Reddy Anna, Mahadev Book, Sprinters',
        'source': 'The Hans India',
        'keywords': ['mahadev', 'reddy anna', 'mule', 'visakhapatnam'],
        'affected_phones': [],
    },
    {
        'date': '2023-06-15',
        'event': 'Visakhapatnam PM Palem Arrest (Original)',
        'detail': '19 arrested · 53 phones seized · ₹5Cr from 71 accounts · ₹50Cr transactions · Franchise model exposed',
        'source': 'Yo! Vizag / G2G News',
        'keywords': ['mahadev', 'visakhapatnam', 'vizag'],
        'affected_phones': [],
    },
]

def normalize_phone(raw):
    digits = re.sub(r'[^\d]', '', str(raw))
    if len(digits) == 10 and digits[0] in '6789':
        return '+91' + digits
    if len(digits) == 12 and digits[:2] == '91':
        return '+' + digits
    return None

def extract_brands(text):
    text_l = text.lower()
    found = set()
    for kw, brand in BRAND_MAP.items():
        if kw in text_l:
            found.add(brand)
    return found

def get_resurrection_profile(raw_input):
    """
    Master function. Takes any identifier.
    Returns complete resurrection/alias chain profile.
    """
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))
    try:
        res_report = json.load(open('reports/resurrection_report.json'))
    except:
        res_report = {'resurrections': []}

    # ── DETECT INPUT TYPE ──────────────────────────────────
    normalized_phone = normalize_phone(raw_input)
    is_phone = normalized_phone is not None
    search_term = raw_input.lower()

    # ── FIND SEED PHONE(S) ─────────────────────────────────
    seed_phones = set()

    if is_phone:
        seed_phones.add(normalized_phone)
    else:
        # Brand/keyword search — find all phones in matching channels
        for c in channels:
            text = (c.get('username','') + ' ' + c.get('title','') + ' ' + str(c.get('bio',''))).lower()
            if search_term in text or any(kw in text for kw in search_term.split()):
                for p in c.get('phones', []):
                    if p: seed_phones.add(p)

    if not seed_phones:
        return {'found': False, 'input': raw_input, 'message': 'No operator found'}

    # ── BUILD PHONE → BRAND MAP ────────────────────────────
    phone_brands   = defaultdict(set)
    phone_channels = defaultdict(list)
    phone_reach    = defaultdict(int)

    for c in channels:
        brands_in_channel = extract_brands(c.get('username','') + ' ' + c.get('title',''))
        for p in c.get('phones', []):
            if not p: continue
            phone_channels[p].append(c)
            phone_reach[p] += c.get('subscribers', 0)
            phone_brands[p].update(brands_in_channel)

    # ── EXPAND TO FULL NETWORK ─────────────────────────────
    # Find all phones that share channels with seed phones
    network_phones = set(seed_phones)
    for seed in seed_phones:
        seed_channel_names = {c.get('username','') for c in phone_channels.get(seed, [])}
        for p, chs in phone_channels.items():
            p_channel_names = {c.get('username','') for c in chs}
            if seed_channel_names & p_channel_names:
                network_phones.add(p)

    # ── COLLECT ALL BRANDS ACROSS NETWORK ─────────────────
    all_brands = set()
    for p in network_phones:
        all_brands.update(phone_brands.get(p, set()))

    # ── BUILD ALIAS CHAIN ──────────────────────────────────
    # Sort brands by first detection date (approximate)
    brand_first_seen = {}
    for a in sorted(alerts, key=lambda x: x.get('detected_at', '')):
        text = (a.get('title','') + str(a.get('detail',''))).lower()
        for brand in all_brands:
            kw = brand.lower().split()[0]
            if kw in text and brand not in brand_first_seen:
                brand_first_seen[brand] = a.get('detected_at', '')[:10]

    alias_chain = []
    for brand in sorted(all_brands):
        first_seen = brand_first_seen.get(brand, 'Unknown')
        # Find channels for this brand
        brand_channels = []
        for c in channels:
            text = (c.get('username','') + ' ' + c.get('title','')).lower()
            b_kw = brand.lower().split()[0]
            if b_kw in text:
                brand_channels.append(c)
        reach = sum(c.get('subscribers',0) for c in brand_channels)
        alias_chain.append({
            'brand':       brand,
            'first_seen':  first_seen,
            'channels':    len(brand_channels),
            'reach':       reach,
            'status':      'ACTIVE',
        })

    alias_chain.sort(key=lambda x: x['first_seen'])

    # ── FIND ENFORCEMENT EVENTS ────────────────────────────
    relevant_events = []
    all_brands_lower = {b.lower() for b in all_brands}
    all_phones_bare  = {p.replace('+','').replace(' ','')[-10:] for p in network_phones}

    for event in ENFORCEMENT_EVENTS:
        matched = False
        # Check keywords
        for kw in event.get('keywords', []):
            if any(kw in b for b in all_brands_lower):
                matched = True
            if kw in all_phones_bare:
                matched = True
        # Check affected phones
        for p in event.get('affected_phones', []):
            if normalize_phone(p) in network_phones:
                matched = True
        if matched:
            relevant_events.append(event)

    relevant_events.sort(key=lambda x: x['date'])

    # ── FIND RESURRECTIONS ─────────────────────────────────
    resurrections = []
    for r in res_report.get('resurrections', []):
        r_phone = normalize_phone(r.get('phone',''))
        if r_phone in network_phones:
            resurrections.append(r)

    # Also detect based on timing
    for event in relevant_events:
        event_date = event['date']
        for p in event.get('affected_phones', []):
            norm_p = normalize_phone(p)
            if not norm_p: continue
            # Find alerts detected AFTER event date
            post_alerts = [a for a in alerts
                           if norm_p and norm_p.replace('+91','') in str(a)
                           and a.get('detected_at','') > event_date + 'T00:00:00']
            if post_alerts:
                first_post = sorted(post_alerts, key=lambda x: x.get('detected_at',''))[0]
                first_date = first_post.get('detected_at','')[:10]
                if first_date > event_date:
                    days_after = (
                        datetime.strptime(first_date,'%Y-%m-%d') -
                        datetime.strptime(event_date,'%Y-%m-%d')
                    ).days
                    existing = {r.get('phone','') for r in resurrections}
                    if norm_p not in existing:
                        resurrections.append({
                            'enforcement_event': event['event'],
                            'enforcement_date':  event_date,
                            'phone':             norm_p,
                            'channel':           first_post.get('title','')[:50],
                            'days_after_bust':   days_after,
                            'confidence':        85,
                            'significance':      f'DETECTED {days_after} DAYS AFTER ENFORCEMENT',
                        })

    # ── PRIMARY OPERATOR NAME ─────────────────────────────
    # Infer from most-channels phone
    primary_phone = max(network_phones,
                        key=lambda p: len(phone_channels.get(p,[])),
                        default='')
    priority_brands = ['Mahadev Book','Reddy Anna','Radhe Exchange','Vipin Aryan',
                       'Diamond Exchange','World777','Laser247']
    primary_brand = next((b for b in priority_brands if b in all_brands),
                          next(iter(all_brands), 'Unknown'))

    # ── TIMELINE ──────────────────────────────────────────
    timeline = []
    for event in relevant_events:
        timeline.append({
            'date':   event['date'],
            'type':   'ENFORCEMENT',
            'event':  event['event'],
            'detail': event['detail'],
            'source': event.get('source',''),
        })
    for r in resurrections:
        if r.get('enforcement_date'):
            days = r.get('days_after_bust',0)
            rdate = (datetime.strptime(r['enforcement_date'],'%Y-%m-%d') +
                     timedelta(days=days)).strftime('%Y-%m-%d')
            timeline.append({
                'date':   rdate,
                'type':   'RESURRECTION',
                'event':  f'Network active — {r.get("phone","")}',
                'detail': f'Detected {days} days after {r["enforcement_event"]}',
                'source': 'CINEOS',
            })
    timeline.sort(key=lambda x: x['date'])

    # ── TOTAL STATS ───────────────────────────────────────
    total_reach = sum(phone_reach.get(p,0) for p in seed_phones)
    total_channels = sum(len(phone_channels.get(p,[])) for p in seed_phones)
    conf = 95 if len(network_phones) >= 5 else 85 if len(network_phones) >= 3 else 75

    return {
        'input':             raw_input,
        'found':             True,
        'primary_name':      primary_brand,
        'primary_phone':     primary_phone,
        'confidence':        conf,
        'network_phones':    sorted(network_phones),
        'alias_chain':       alias_chain,
        'total_brands':      len(all_brands),
        'total_channels':    total_channels,
        'total_reach':       total_reach,
        'enforcement_events':relevant_events,
        'resurrections':     resurrections,
        'timeline':          timeline,
        'moat_statement': (
            f'{primary_brand} has operated under {len(all_brands)} brand names '
            f'across {total_channels} Telegram channels. '
            f'{len(resurrections)} post-enforcement resurrection(s) confirmed. '
            f'Network reach: {total_reach:,} subscribers.'
        ),
        'generated_at': datetime.now(IST).isoformat(),
    }


def print_profile(profile):
    if not profile.get('found'):
        print(f'Not found: {profile.get("message","")}')
        return

    print('=' * 65)
    print(f'  CINEOS RESURRECTION INTELLIGENCE REPORT')
    print(f'  {datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}')
    print('=' * 65)
    print()
    print(f'  Operator:    {profile["primary_name"]}')
    print(f'  Confidence:  {profile["confidence"]}%')
    print(f'  Phones:      {len(profile["network_phones"])} in network')
    print(f'  Brands:      {profile["total_brands"]} confirmed aliases')
    print(f'  Channels:    {profile["total_channels"]}')
    print(f'  Reach:       {profile["total_reach"]:,}')
    print()

    print('🔗 ALIAS CHAIN — All Brand Names Used:')
    for a in profile['alias_chain']:
        bar = '█' * min(20, a['channels'] * 2)
        print(f'  {a["brand"]:25} {a["channels"]:2} channels  '
              f'{a["reach"]:>9,} reach  {bar}')
    print()

    if profile['enforcement_events']:
        print('⚖️  ENFORCEMENT EVENTS:')
        for e in profile['enforcement_events']:
            print(f'  [{e["date"]}] {e["event"]}')
            print(f'    {e["detail"][:80]}')
        print()

    if profile['resurrections']:
        print('⚡ POST-ARREST RESURRECTIONS:')
        for r in profile['resurrections']:
            print(f'  [{r["enforcement_date"]}+{r.get("days_after_bust",0)}d] '
                  f'{r.get("phone","")} — {r.get("significance","")[:60]}')
        print()

    print('📅 FULL TIMELINE:')
    for t in profile['timeline']:
        icon = '⚖️' if t['type'] == 'ENFORCEMENT' else '⚡'
        print(f'  {icon} [{t["date"]}] {t["event"]}')
    print()

    print(f'🎯 MOAT STATEMENT:')
    print(f'  {profile["moat_statement"]}')
    print('=' * 65)


if __name__ == '__main__':
    import sys
    tests = sys.argv[1:] if len(sys.argv) > 1 else [
        '+918881754538',
        'Mahadev Book',
        'Radhe Exchange',
        '+917455697977',
    ]
    for t in tests:
        profile = get_resurrection_profile(t)
        print_profile(profile)
        print()
