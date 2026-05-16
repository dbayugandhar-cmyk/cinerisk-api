"""
CINEOS Identity Intelligence Engine
Enriches operator profiles with identity signals:
1. Truecaller-style name inference from known patterns
2. Cross-database alias matching
3. Social handle inference
4. WhatsApp network inference from wa.me links

NOTE: No Truecaller API used — we build from our own data
and public patterns. More defensible legally.

Usage: python3 cineos_identity_intel.py +917455697977
"""
import json, re, os
from collections import defaultdict
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5,minutes=30))

# Known operator name patterns from our database
OPERATOR_ALIASES = {
    '+918881754538': ['Reddy Anna', 'World777 operator', 'Lotus365 admin'],
    '+918881349483': ['Reddy Anna network', 'World777'],
    '+918881987328': ['Reddy Anna network', 'World777'],
    '+917455697977': ['Radhe Exchange operator', 'Diamond Exchange'],
    '+917400749393': ['Radhe Exchange network'],
    '+917832350002': ['Radhe Exchange network'],
    '+918881886916': ['Vipin Aryan', 'Sawariya Exchange'],
}

def infer_name_from_channels(channels):
    """Infer operator name from channel names and titles."""
    all_text = ' '.join(
        (c.get('username','') + ' ' + c.get('title','')).lower()
        for c in channels
    )
    name_patterns = {
        'Reddy Anna':      ['reddy', 'annaw', 'annae'],
        'Mahadev Book':    ['mahadev', 'mhb'],
        'World777':        ['world777', 'world_777'],
        'Fairplay':        ['fairplay', 'fair_play'],
        'Laser247':        ['laser247', 'laser_247'],
        'Vipin Aryan':     ['vipin', 'aryan', 'sawariya'],
        'Lotus365':        ['lotus', 'lotus365'],
        'Diamond Exchange':['diamond', 'diamondexch'],
        'Radhe Exchange':  ['radhe', 'radheexch'],
        '91CLUB':          ['91club', 'jalwa', 'okwin'],
        'Daman Games':     ['daman', 'tiranga'],
        'Faridabad Satta': ['faridabad', 'satta_king'],
    }
    for name, keywords in name_patterns.items():
        if any(kw in all_text for kw in keywords):
            return name
    return None

def build_wa_network():
    """
    Build WhatsApp operator network from wa.me links.
    We can't access WA groups but we CAN map which
    Telegram channels share the same WA numbers —
    that IS the network inference.
    """
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))

    wa_map = defaultdict(list)  # WA phone → channels

    # Extract from channels
    for ch in channels:
        for ph in ch.get('phones',[]):
            if ph and 'wa_' in ch.get('phone_method','').lower():
                wa_map[ph].append({
                    'source':     'telegram_channel',
                    'channel':    ch.get('username',''),
                    'category':   ch.get('category',''),
                    'subscribers':ch.get('subscribers',0),
                })

        # Also check bio for wa.me
        bio = ch.get('bio','')
        if bio:
            wa_phones = re.findall(r'wa\.me/(?:91)?([6-9]\d{9})', bio)
            for p in wa_phones:
                norm = '+91' + p
                wa_map[norm].append({
                    'source':   'channel_bio',
                    'channel':  ch.get('username',''),
                    'category': ch.get('category',''),
                })

    # Extract from alerts
    for a in alerts:
        detail = a.get('detail','')
        wa_phones = re.findall(r'wa\.me/(?:91)?([6-9]\d{9})', detail)
        for p in wa_phones:
            norm = '+91' + p
            wa_map[norm].append({
                'source':   'alert',
                'category': a.get('category',''),
                'title':    a.get('title','')[:50],
            })

    report = {
        'generated_at': datetime.now(IST).isoformat(),
        'wa_numbers_found': len(wa_map),
        'cross_channel_wa': {ph: refs for ph, refs in wa_map.items() if len(refs) >= 2},
        'all_wa_numbers': dict(wa_map),
        'insight': f'{len(wa_map)} WhatsApp numbers inferred from Telegram content. Same WA number in multiple channels = same operator using WA for order management.',
    }

    os.makedirs('reports', exist_ok=True)
    json.dump(report, open('reports/wa_network.json','w'), indent=2)

    cross = report['cross_channel_wa']
    print(f'\nWhatsApp Network Inference:')
    print(f'  WA numbers found:    {len(wa_map)}')
    print(f'  Cross-channel WA:    {len(cross)}')
    if cross:
        for ph, refs in list(cross.items())[:5]:
            print(f'    {ph} in {len(refs)} sources')
    return report

def get_identity_profile(phone):
    """
    Get complete identity intelligence for a phone number.
    Combines: known aliases + channel name inference +
              WA network + UPI linkage + TRAI data
    """
    try:
        channels = json.load(open('reports/all_channels.json'))
    except:
        return {}

    from collections import defaultdict
    phone_map = defaultdict(list)
    for ch in channels:
        for ph in ch.get('phones',[]):
            if ph == phone:
                phone_map[phone].append(ch)

    matching_channels = phone_map.get(phone, [])

    # Known aliases
    known_aliases = OPERATOR_ALIASES.get(phone, [])

    # Infer from channel names
    inferred_name = infer_name_from_channels(matching_channels)

    # UPI linkage
    upi_intel = []
    try:
        upi_report = json.load(open('reports/upi_network.json'))
        upis = upi_report.get('phone_upi_map',{}).get(phone,[])
        for upi in upis:
            from cineos_upi_intel import analyse_upi
            upi_intel.append(analyse_upi(upi))
    except:
        pass

    # WA network
    wa_mentions = []
    try:
        wa_report = json.load(open('reports/wa_network.json'))
        wa_all = wa_report.get('all_wa_numbers',{})
        if phone in wa_all:
            wa_mentions = wa_all[phone]
    except:
        pass

    return {
        'phone':          phone,
        'known_aliases':  known_aliases,
        'inferred_name':  inferred_name,
        'upi_accounts':   upi_intel,
        'wa_mentions':    wa_mentions,
        'channel_count':  len(matching_channels),
        'identity_confidence': 'HIGH' if known_aliases or inferred_name else 'MEDIUM',
        'note': 'Name inference from channel content and cross-database matching. Not from Truecaller API.',
    }

if __name__ == '__main__':
    import sys
    print('='*55)
    print(f'  CINEOS IDENTITY INTELLIGENCE ENGINE')
    print(f'  {datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}')
    print('='*55)

    print('\nBuilding UPI network...')
    from cineos_upi_intel import build_upi_network
    build_upi_network()

    print('\nBuilding WA network inference...')
    build_wa_network()

    if len(sys.argv) > 1 and sys.argv[1].startswith('+'):
        phone = sys.argv[1]
        profile = get_identity_profile(phone)
        print(f'\nIdentity Profile: {phone}')
        print(f'  Known aliases:  {profile["known_aliases"]}')
        print(f'  Inferred name:  {profile["inferred_name"]}')
        print(f'  UPI accounts:   {len(profile["upi_accounts"])}')
        print(f'  WA mentions:    {len(profile["wa_mentions"])}')
        print(f'  Confidence:     {profile["identity_confidence"]}')
    else:
        print('\nTest identity lookups:')
        for ph in ['+918881754538', '+917455697977', '+918383061215']:
            p = get_identity_profile(ph)
            print(f'  {ph}: name={p["inferred_name"]} aliases={p["known_aliases"][:1]}')
