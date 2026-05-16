"""
CINEOS UPI Intelligence Engine
Maps UPI handles to banks, detects suspicious patterns,
builds UPI operator networks without needing banking API.

What we can do without banking partner:
1. UPI handle → bank inference (from handle suffix)
2. Cross-channel UPI matching (same UPI in multiple channels)
3. Foreign UPI detection (non-Indian payment rails)
4. Suspicious pattern scoring
5. UPI → operator correlation

Usage: python3 cineos_upi_intel.py
"""
import json, re, os
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5,minutes=30))

# UPI handle suffix → bank mapping (public knowledge)
UPI_BANK_MAP = {
    'okaxis':       {'bank':'Axis Bank',           'type':'PSP'},
    'okhdfcbank':   {'bank':'HDFC Bank',            'type':'PSP'},
    'okicici':      {'bank':'ICICI Bank',           'type':'PSP'},
    'oksbi':        {'bank':'State Bank of India',  'type':'PSP'},
    'ybl':          {'bank':'Yes Bank (PhonePe)',    'type':'PSP'},
    'ibl':          {'bank':'ICICI Bank (PhonePe)', 'type':'PSP'},
    'axl':          {'bank':'Axis Bank (PhonePe)',  'type':'PSP'},
    'paytm':        {'bank':'Paytm Payments Bank',  'type':'Wallet'},
    'apl':          {'bank':'Amazon Pay',           'type':'PSP'},
    'fbl':          {'bank':'Federal Bank',         'type':'PSP'},
    'rbl':          {'bank':'RBL Bank',             'type':'PSP'},
    'kotak':        {'bank':'Kotak Mahindra Bank',  'type':'PSP'},
    'federal':      {'bank':'Federal Bank',         'type':'PSP'},
    'airtel':       {'bank':'Airtel Payments Bank', 'type':'Wallet'},
    'jio':          {'bank':'Jio Payments Bank',    'type':'Wallet'},
    'upi':          {'bank':'NPCI Direct',          'type':'Direct'},
    'waicici':      {'bank':'ICICI Bank (WhatsApp)','type':'PSP'},
    'wahdfc':       {'bank':'HDFC Bank (WhatsApp)', 'type':'PSP'},
    'pingpay':      {'bank':'Standard Chartered',   'type':'PSP'},
    'naviaxis':     {'bank':'Navi/Axis Bank',       'type':'Fintech'},
    'jupiteraxis':  {'bank':'Jupiter/Axis Bank',    'type':'Fintech'},
    'indus':        {'bank':'IndusInd Bank',        'type':'PSP'},
    'hsbc':         {'bank':'HSBC Bank',            'type':'PSP'},
    'dbs':          {'bank':'DBS Bank India',       'type':'PSP'},
    # Suspicious / foreign
    'betviro':      {'bank':'FOREIGN — gambling platform',  'type':'SUSPICIOUS'},
    'pkheadwaysolutions': {'bank':'FOREIGN — shell company','type':'SUSPICIOUS'},
    'hobartpharma': {'bank':'FOREIGN — pharma entity',     'type':'SUSPICIOUS'},
    'pypi':         {'bank':'SUSPICIOUS — non-standard',   'type':'SUSPICIOUS'},
    'fast':         {'bank':'SUSPICIOUS — crypto gateway',  'type':'SUSPICIOUS'},
    'ir':           {'bank':'SUSPICIOUS — unregistered',   'type':'SUSPICIOUS'},
}

SUSPICIOUS_PATTERNS = [
    r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}',  # UUID format = crypto gateway
    r'@(fast|ir|pypi|betviro)',                 # Known suspicious suffixes
    r'^\d{10}@',                                # Raw phone as UPI = mule pattern
    r'@[a-z]{2,4}$',                           # Very short suffix = suspicious
]

def analyse_upi(upi):
    """Complete UPI intelligence analysis."""
    if not upi:
        return None

    upi = str(upi).lower().strip()
    parts = upi.split('@')
    if len(parts) != 2:
        return {'upi': upi, 'valid': False, 'risk': 'INVALID'}

    handle, suffix = parts

    # Bank lookup
    bank_info = UPI_BANK_MAP.get(suffix, {'bank': f'Unknown ({suffix})', 'type': 'Unknown'})

    # Suspicious pattern check
    suspicious = []
    for pat in SUSPICIOUS_PATTERNS:
        if re.search(pat, upi):
            suspicious.append(pat)

    # Risk scoring
    risk_score = 0
    if bank_info['type'] == 'SUSPICIOUS':     risk_score += 40
    if suspicious:                             risk_score += 30
    if re.match(r'^\d{10}@', upi):            risk_score += 20  # Phone as handle
    if len(suffix) <= 3:                       risk_score += 10  # Short suffix
    if any(c in handle for c in ['bet','game','win','earn','profit','invest']):
        risk_score += 20
    if any(c in handle for c in ['mule','hawk','transfer','convert']):
        risk_score += 30

    risk_level = 'CRITICAL' if risk_score >= 60 else 'HIGH' if risk_score >= 40 else 'MEDIUM' if risk_score >= 20 else 'LOW'

    return {
        'upi':        upi,
        'handle':     handle,
        'suffix':     suffix,
        'bank':       bank_info['bank'],
        'type':       bank_info['type'],
        'risk_score': risk_score,
        'risk_level': risk_level,
        'suspicious_patterns': suspicious,
        'is_foreign': bank_info['type'] == 'SUSPICIOUS',
        'flags':      [f for f in [
            'PHONE_AS_HANDLE' if re.match(r'^\d{10}@', upi) else None,
            'FOREIGN_GATEWAY' if bank_info['type'] == 'SUSPICIOUS' else None,
            'GAMBLING_KEYWORD' if any(k in handle for k in ['bet','game','win']) else None,
            'MULE_KEYWORD' if any(k in handle for k in ['mule','hawk']) else None,
            'UUID_FORMAT' if re.search(r'[a-f0-9]{8}-[a-f0-9]{4}', upi) else None,
        ] if f],
    }

def build_upi_network():
    """Build UPI operator network from all channels and alerts."""
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))

    upi_map    = defaultdict(list)  # UPI → channels
    phone_upis = defaultdict(set)   # Phone → UPI handles
    all_upis   = {}                 # UPI → analysis

    for ch in channels:
        for upi in ch.get('upis', []):
            if upi:
                upi_map[upi].append(ch.get('username',''))
                for ph in ch.get('phones',[]):
                    if ph: phone_upis[ph].add(upi)
                all_upis[upi] = analyse_upi(upi)

    for a in alerts:
        chain = a.get('chain',{})
        for upi in chain.get('upis',[]):
            if upi:
                upi_map[upi].append(a.get('title','')[:30])
                for ph in chain.get('phones',[]):
                    if ph: phone_upis[ph].add(upi)
                if upi not in all_upis:
                    all_upis[upi] = analyse_upi(upi)

    # Find cross-channel UPIs
    cross_ch = {u: chs for u, chs in upi_map.items() if len(chs) >= 2}

    # Find phone-UPI linkages
    ph_upi_links = {ph: list(upis) for ph, upis in phone_upis.items() if upis}

    report = {
        'generated_at':   datetime.now(IST).isoformat(),
        'total_upis':     len(all_upis),
        'cross_channel':  len(cross_ch),
        'phone_upi_links':len(ph_upi_links),
        'suspicious':     [u for u,a in all_upis.items() if a and a.get('risk_level') in ('CRITICAL','HIGH')],
        'foreign_upis':   [u for u,a in all_upis.items() if a and a.get('is_foreign')],
        'analysis':       {u: a for u,a in all_upis.items() if a},
        'cross_channel_upis': cross_ch,
        'phone_upi_map':  ph_upi_links,
    }

    os.makedirs('reports', exist_ok=True)
    json.dump(report, open('reports/upi_network.json','w'), indent=2)

    print(f'\nUPI Intelligence Report:')
    print(f'  Total UPIs tracked:     {len(all_upis)}')
    print(f'  Cross-channel UPIs:     {len(cross_ch)}')
    print(f'  Phone-UPI linkages:     {len(ph_upi_links)}')
    print(f'  Suspicious/Critical:    {len(report["suspicious"])}')
    print(f'  Foreign UPI handles:    {len(report["foreign_upis"])}')

    if report['foreign_upis']:
        print(f'\n  FOREIGN UPIs (high risk):')
        for upi in report['foreign_upis'][:5]:
            a = all_upis.get(upi,{})
            print(f'    {upi:40} → {a.get("bank","")}')

    if cross_ch:
        print(f'\n  CROSS-CHANNEL UPIs:')
        for upi, chs in list(cross_ch.items())[:5]:
            print(f'    {upi:35} in {len(chs)} channels')

    if ph_upi_links:
        print(f'\n  PHONE → UPI LINKAGES:')
        for ph, upis in list(ph_upi_links.items())[:5]:
            print(f'    {ph:20} → {upis[:2]}')

    return report

def enrich_operator_with_upi(phone):
    """Add UPI intelligence to a phone operator profile."""
    try:
        report = json.load(open('reports/upi_network.json'))
        upis = report.get('phone_upi_map',{}).get(phone,[])
        if not upis:
            return []
        return [{'upi': u, 'analysis': analyse_upi(u)} for u in upis]
    except:
        return []

if __name__ == '__main__':
    print('='*55)
    print(f'  CINEOS UPI INTELLIGENCE ENGINE')
    print(f'  {datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}')
    print('='*55)
    build_upi_network()

    print('\nTest UPI analysis:')
    test_upis = [
        'daria.d@betviro',
        'ravi.betting@ybl',
        '9876543210@paytm',
        'bcd02cc1-36d0-405d-9096-0e69219175c1@pypi',
        'sspglobaljob@gmail',
    ]
    for upi in test_upis:
        a = analyse_upi(upi)
        if a:
            print(f'  {upi:45} {a["risk_level"]:8} {a["bank"][:30]} {a["flags"]}')
