"""
CINEOS Alias Chain Tracker
Documents operator brand evolution:
Original brand → post-arrest resurrection → current brand

This is what no other tool has.
An operator arrested as "Mahadev Book" comes back as
"MHB Exchange" — same phone, new brand.
We track the chain.
"""
import json, re, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5,minutes=30))

# Known alias chains from our database + news cross-reference
ALIAS_CHAINS = {
    'Radhe Exchange / Mahadev Book Network': {
        'phones': ['+917455697977','+917400749393','+917832350002'],
        'chain': [
            {'brand':'Mahadev Book',    'status':'BUSTED',  'date':'2022-10',
             'note':'Original brand · ED case filed · Rs 5,000Cr estimate'},
            {'brand':'Mahadev Book 2.0','status':'BUSTED',  'date':'2023-06',
             'note':'Resurrection 1 · Same operators · New domains'},
            {'brand':'Radhe Exchange',  'status':'ACTIVE',  'date':'2024-01',
             'note':'Current brand · Same phone network · Rajasthan circle'},
            {'brand':'Diamond Exchange','status':'ACTIVE',  'date':'2024-06',
             'note':'Parallel brand · Same phones confirmed'},
            {'brand':'World777',        'status':'ACTIVE',  'date':'2025-03',
             'note':'Sub-brand · Shared operator network'},
        ],
        'confirmed_by': 'Phone +917455697977 in all channel sets',
        'confidence': 95,
    },
    'Reddy Anna Network': {
        'phones': ['+918881754538','+918881349483','+918881987328'],
        'chain': [
            {'brand':'Reddy Anna',      'status':'ACTIVE',  'date':'2023-01',
             'note':'Primary brand · AP/Telangana Jio circle'},
            {'brand':'World777',        'status':'ACTIVE',  'date':'2023-06',
             'note':'Co-brand · Same operator phones'},
            {'brand':'Lotus365',        'status':'ACTIVE',  'date':'2024-01',
             'note':'Parallel brand · Same phone network'},
            {'brand':'Fairplay',        'status':'ACTIVE',  'date':'2024-06',
             'note':'Sub-brand · Shared channels'},
        ],
        'confirmed_by': 'Phone +918881754538 across all brand channels',
        'confidence': 85,
    },
    'Vipin Aryan / Sawariya Exchange': {
        'phones': ['+918881886916'],
        'chain': [
            {'brand':'Sawariya Exchange','status':'ACTIVE', 'date':'2024-06',
             'note':'Primary brand'},
            {'brand':'Vipin Aryan',      'status':'ACTIVE', 'date':'2025-01',
             'note':'Personal brand · Same phone'},
        ],
        'confirmed_by': 'Phone +918881886916 in both channel sets',
        'confidence': 80,
    },
}

def detect_alias_from_channels(channels, phone):
    """
    Detect alias chain from channel names for a given phone.
    Look for brand name patterns across all channels with this phone.
    """
    matching = [c for c in channels if phone in c.get('phones', [])]
    if not matching:
        return []

    brands = set()
    BRAND_PATTERNS = {
        'Mahadev Book':     r'mahadev|mhb',
        'Reddy Anna':       r'reddy.?anna|reddyanna',
        'World777':         r'world.?777',
        'Lotus365':         r'lotus.?365|lotus_365',
        'Radhe Exchange':   r'radhe.?exch|radheexch',
        'Diamond Exchange': r'diamond.?exch|diamondexch',
        'Fairplay':         r'fairplay|fair.?play',
        'Laser247':         r'laser.?247',
        'Cricbet99':        r'cricbet.?99',
        'Betbhai9':         r'betbhai.?9',
        'Sky Exchange':     r'sky.?exch|skyexch',
        'Tiger Exchange':   r'tiger.?exch',
        'Sawariya':         r'sawariya',
        'Vipin Aryan':      r'vipin.?aryan',
        '91CLUB':           r'91.?club',
        'Daman Games':      r'daman.?game',
        'Tiranga':          r'tiranga',
    }

    for ch in matching:
        text = (ch.get('username', '') + ' ' + ch.get('title', '')).lower()
        for brand, pattern in BRAND_PATTERNS.items():
            if re.search(pattern, text):
                brands.add(brand)

    return list(brands)

def detect_agent_hierarchy(channels, alerts):
    """
    Detect sub-agent recruitment signals.
    These appear in channel messages as:
    - Commission rate mentions
    - Referral code patterns
    - WhatsApp group invite links
    - "Become an agent" / "panel" language
    """
    hierarchy_signals = []

    AGENT_PATTERNS = [
        r'(?:become|join)\s+(?:an?\s+)?(?:agent|partner|affiliate)',
        r'(?:commission|profit)\s*(?:share|splitting?)',
        r'(?:\d+)\s*%\s*(?:commission|profit|share)',
        r'(?:referral|refer|ref)\s+(?:code|id|link)',
        r'(?:master|super)\s+(?:agent|panel)',
        r'(?:whatsapp|wa\.me)\s+(?:group|join)',
        r'panel\s+(?:available|open|free)',
        r'(?:sub.?agent|sub.?panel)',
        r'(?:unlimited|daily)\s+(?:earn|income|profit)',
    ]

    for a in alerts:
        if a.get('category') != 'illegal_betting':
            continue
        text = (a.get('title', '') + ' ' + a.get('detail', '')).lower()
        for pat in AGENT_PATTERNS:
            if re.search(pat, text):
                phones = a.get('chain', {}).get('phones', [])
                wa_match = re.search(r'wa\.me/(?:91)?([6-9]\d{9})', text)
                commission = re.search(r'(\d+)\s*%', text)

                hierarchy_signals.append({
                    'channel':    a.get('chain', {}).get('channels_found', [''])[0],
                    'signal':     pat,
                    'phones':     phones[:2],
                    'wa_contact': '+91' + wa_match.group(1) if wa_match else None,
                    'commission': commission.group(1) + '%' if commission else None,
                    'title':      a.get('title', '')[:60],
                    'type':       'AGENT_RECRUITMENT',
                })
                break

    return hierarchy_signals

def run():
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))

    print('ALIAS CHAIN ANALYSIS:')
    print()
    for network, data in ALIAS_CHAINS.items():
        print(f'NETWORK: {network}')
        print(f'Confidence: {data["confidence"]}%')
        print(f'Phones: {data["phones"]}')
        print('Brand Evolution:')
        for i, brand in enumerate(data['chain'], 1):
            status_icon = '✓ BUSTED' if brand['status'] == 'BUSTED' else '⚡ ACTIVE'
            print(f'  {i}. [{brand["date"]}] {brand["brand"]:25} {status_icon}')
            print(f'     {brand["note"]}')
        print()

        # Auto-detect from our database
        for ph in data['phones']:
            detected = detect_alias_from_channels(channels, ph)
            if detected:
                print(f'  Auto-detected brands for {ph}: {detected}')
        print()

    print('AGENT HIERARCHY SIGNALS:')
    signals = detect_agent_hierarchy(channels, alerts)
    print(f'Total: {len(signals)} recruitment signals detected')
    for s in signals[:5]:
        print(f'  Channel: {str(s["channel"])[:50]}')
        print(f'  Commission: {s["commission"]} | WA: {s["wa_contact"]}')
        print()

    # Save
    report = {
        'generated_at':   datetime.now(IST).isoformat(),
        'alias_chains':   ALIAS_CHAINS,
        'agent_signals':  signals,
        'total_networks': len(ALIAS_CHAINS),
        'total_agents':   len(signals),
    }
    json.dump(report, open('reports/alias_chains.json', 'w'), indent=2)
    print('Saved: reports/alias_chains.json')

if __name__ == '__main__':
    print('=' * 55)
    print(f'  CINEOS ALIAS CHAIN TRACKER')
    print(f'  {datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}')
    print('=' * 55)
    run()
