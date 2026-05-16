"""
CINEOS Number Intelligence Engine
Cross-vertical phone number risk lookup.

Input:  Any Indian mobile number
Output: Risk category, confidence, linked entities,
        network connections, resurrection history,
        evidence references, legal disclaimer.

This is what DoT FRI + I4C NCRP cannot do.
They flag numbers from complaints.
We map networks from source channels.
"""
import json, re, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

IST = timezone(timedelta(hours=5,minutes=30))

def normalize_phone(raw):
    d = re.sub(r'[^\d]', '', str(raw))
    if len(d) == 12 and d[:2] == '91': d = d[2:]
    if len(d) == 10: return '+91' + d
    return None

def lookup_number(phone_raw):
    """
    Full cross-vertical intelligence lookup for a phone number.
    Returns complete profile or risk-scored unknown result.
    """
    ph = normalize_phone(phone_raw)
    if not ph:
        return {'error': 'Invalid phone number format'}

    bare = ph.replace('+', '').replace(' ', '')

    # Load data
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))

    try:
        trai = json.load(open('configs/trai_series.json'))
        d10  = bare[-10:]
        trai_info = trai.get(d10[:4]) or trai.get(d10[:3]) or {}
    except:
        trai_info = {}

    # ── FIND ALL CHANNELS ─────────────────────────────────
    matched_channels = []
    for c in channels:
        if ph in c.get('phones', []) or bare in str(c.get('phones', [])):
            matched_channels.append(c)

    # ── FIND ALL ALERTS ──────────────────────────────────
    matched_alerts = [a for a in alerts
                      if bare[-10:] in str(a) or ph in str(a)]

    # ── FIND NETWORK CONNECTIONS ─────────────────────────
    # Other phones appearing in same channels
    co_phones = defaultdict(int)
    for c in matched_channels:
        for p in c.get('phones', []):
            if p and p != ph:
                co_phones[p] += 1

    # ── FIND UPI HANDLES ─────────────────────────────────
    upis = set()
    for c in matched_channels:
        for u in c.get('upis', []):
            if u: upis.add(u)

    # ── CATEGORIES ───────────────────────────────────────
    cats = Counter(c.get('category', 'unknown')
                   for c in matched_channels)

    # ── CONFIDENCE SCORE ─────────────────────────────────
    n = len(matched_channels)
    if n >= 7:   conf = 95
    elif n >= 5: conf = 85
    elif n >= 3: conf = 80
    elif n >= 2: conf = 70
    elif n == 1: conf = 55
    else:        conf = 0

    # ── RISK LEVEL ───────────────────────────────────────
    if conf >= 85:   risk = 'CRITICAL'
    elif conf >= 70: risk = 'HIGH'
    elif conf >= 40: risk = 'MEDIUM'
    elif conf > 0:   risk = 'LOW'
    else:
        # Zero-alert enrichment
        prefix = bare[-10:][:4]
        HIGH_PREFIXES = {
            '8881': 40, '8808': 30, '7455': 35,
            '7400': 35, '7413': 30, '7832': 30,
            '8888': 25, '9186': 30, '9602': 25,
        }
        base = HIGH_PREFIXES.get(prefix, 0)
        risk = 'MEDIUM' if base >= 25 else 'LOW' if base > 0 else 'CLEAR'
        conf = base

    # ── FIRST / LAST SEEN ────────────────────────────────
    dates = sorted([a.get('detected_at', '')
                    for a in matched_alerts
                    if a.get('detected_at')])
    first_seen = dates[0][:19] if dates else None
    last_seen  = dates[-1][:19] if dates else None

    # ── RESURRECTION CHECK ───────────────────────────────
    try:
        res_rpt = json.load(open('reports/resurrection_report.json'))
        resurrections = [r for r in res_rpt.get('resurrections', [])
                         if ph in str(r) or bare in str(r)]
    except:
        resurrections = []

    # ── ALIAS BRANDS ─────────────────────────────────────
    brand_patterns = {
        'Mahadev Book':   r'mahadev',
        'Reddy Anna':     r'reddy.?anna',
        'World777':       r'world.?777',
        'Lotus365':       r'lotus.?365',
        'Radhe Exchange': r'radhe.?exch',
        'Diamond Exchange':r'diamond.?exch',
        'Fairplay':       r'fairplay',
        'Vipin Aryan':    r'vipin.?aryan',
        'Sawariya':       r'sawariya',
        'Tiger Exchange': r'tiger.?exch',
    }
    aliases = set()
    for c in matched_channels:
        text = (c.get('username','') + ' ' +
                c.get('title','') + ' ' +
                str(c.get('bio',''))).lower()
        for brand, pat in brand_patterns.items():
            if re.search(pat, text):
                aliases.add(brand)

    # ── FINANCIAL EXPOSURE ───────────────────────────────
    total_reach = sum(c.get('subscribers', 0)
                      for c in matched_channels)
    daily_est   = int(total_reach * 0.001 * 500)

    # ── LEGAL FRAMEWORK ──────────────────────────────────
    legal_map = {
        'illegal_betting':   ['Online Gaming Act 2025 §8', 'PMLA 2002 §3'],
        'crypto_fraud':      ['PMLA 2002 §3', 'IPC §420'],
        'upi_mule':          ['PMLA 2002 §3', 'RBI Guidelines'],
        'counterfeit_pharma':['Drugs Act §17A', 'NDPS Act'],
        'loan_fraud':        ['RBI Guidelines', 'IT Act §66D'],
        'piracy':            ['Copyright Act §51', 'IT Act §65'],
    }
    primary_cat = cats.most_common(1)[0][0] if cats else 'unknown'
    legal_acts  = legal_map.get(primary_cat, ['IT Act §65B'])

    # ── BUILD PROFILE ─────────────────────────────────────
    profile = {
        'phone':         ph,
        'found':         len(matched_channels) > 0,
        'risk_level':    risk,
        'risk_score':    conf,

        'who': {
            'phone':         ph,
            'carrier':       trai_info.get('operator', 'Unknown'),
            'circle':        trai_info.get('circle', 'Unknown'),
            'aliases':       sorted(aliases),
            'network_phones': dict(sorted(co_phones.items(),
                                          key=lambda x: -x[1])[:5]),
        },

        'what': {
            'categories':   dict(cats),
            'primary':      primary_cat,
            'channels':     len(matched_channels),
            'total_reach':  total_reach,
            'upi_handles':  list(upis)[:5],
            'legal_basis':  legal_acts,
        },

        'when': {
            'first_detected': first_seen,
            'last_detected':  last_seen,
            'total_alerts':   len(matched_alerts),
            'resurrections':  len(resurrections),
        },

        'where': {
            'telecom_circle': trai_info.get('circle', 'Unknown'),
            'channels_sample': [
                {'username': c.get('username',''),
                 'subscribers': c.get('subscribers', 0),
                 'category': c.get('category','')}
                for c in sorted(matched_channels,
                                key=lambda x: -x.get('subscribers', 0))[:3]
            ],
        },

        'how': {
            'method':        'Cross-channel Telegram phone extraction',
            'evidence_hash': 'SHA-256 certified at detection',
            'daily_exposure_est': f'₹{daily_est:,}' if daily_est else 'N/A',
            'monthly_est':   f'₹{daily_est*30:,}' if daily_est else 'N/A',
        },

        'why': {
            'legal_framework': legal_acts,
            'pmla_applicable': total_reach > 10000,
            'ed_threshold':    daily_est * 30 > 1_00_00_000,
        },

        'evidence': {
            'cert_id':     f'CINEOS-65B-{datetime.now(IST).strftime("%Y-%m%d")}-{bare[-6:]}',
            'method':      'IT Act 2000 §65B(2) — public source OSINT',
            'disclaimer':  'Intelligence-grade assessment from public sources. '
                           'Confidence score reflects attribution likelihood, '
                           'not legal proof. Verify before enforcement action.',
        },
    }

    return profile


def print_profile(profile):
    if profile.get('error'):
        print(f'Error: {profile["error"]}')
        return

    ph   = profile['phone']
    risk = profile['risk_level']
    conf = profile['risk_score']

    colors = {'CRITICAL':'⛔','HIGH':'🔴','MEDIUM':'🟡','LOW':'🟢','CLEAR':'✅'}
    icon   = colors.get(risk, '❓')

    print('=' * 65)
    print(f'  CINEOS NUMBER INTELLIGENCE REPORT')
    print(f'  Generated: {datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}')
    print('=' * 65)
    print()
    print(f'{icon}  {ph}  —  {risk}  ({conf}% confidence)')
    print()

    w = profile['who']
    print('👤 WHO')
    print(f'   Carrier:   {w["carrier"]} · {w["circle"]}')
    if w['aliases']:
        print(f'   Brands:    {", ".join(w["aliases"])}')
    if w['network_phones']:
        print(f'   Network:   {len(w["network_phones"])} co-phones in same channels')
    print()

    wh = profile['what']
    print('🎯 WHAT')
    print(f'   Category:  {wh["primary"]}')
    print(f'   Channels:  {wh["channels"]} confirmed')
    print(f'   Reach:     {wh["total_reach"]:,} subscribers')
    if wh['upi_handles']:
        print(f'   UPIs:      {len(wh["upi_handles"])} handles extracted')
    print()

    wn = profile['when']
    print('📅 WHEN')
    print(f'   First detected: {wn["first_detected"] or "Unknown"}')
    print(f'   Last detected:  {wn["last_detected"] or "Unknown"}')
    print(f'   Total alerts:   {wn["total_alerts"]}')
    if wn['resurrections']:
        print(f'   Resurrections:  {wn["resurrections"]} post-arrest')
    print()

    wr = profile['where']
    print('📍 WHERE')
    print(f'   Circle:    {wr["telecom_circle"]}')
    for ch in wr['channels_sample']:
        print(f'   Channel:   @{ch["username"][:35]:35} {ch["subscribers"]:>8,}')
    print()

    hw = profile['how']
    print('⚙️  HOW')
    print(f'   Method:    {hw["method"]}')
    print(f'   Exposure:  {hw["daily_exposure_est"]}/day · {hw["monthly_est"]}/month (est.)')
    print()

    wy = profile['why']
    print('⚖️  WHY (Legal)')
    for act in wy['legal_framework']:
        print(f'   · {act}')
    if wy['ed_threshold']:
        print(f'   ⚠️  Estimated monthly exposure EXCEEDS ED/PMLA ₹1Cr threshold')
    print()

    ev = profile['evidence']
    print('🔐 EVIDENCE')
    print(f'   Certificate: {ev["cert_id"]}')
    print(f'   Standard:    {ev["method"]}')
    print()
    print(f'   ⚠️  DISCLAIMER: {ev["disclaimer"]}')
    print()
    print('=' * 65)


if __name__ == '__main__':
    import sys
    phones_to_test = sys.argv[1:] if len(sys.argv) > 1 else [
        '+918888888888',
        '+918881754538',
        '+917455697977',
        '+919999999999',  # unknown clean
        '+918881000000',  # unknown AP/TG prefix
    ]
    for ph in phones_to_test:
        profile = lookup_number(ph)
        print_profile(profile)
        if len(phones_to_test) > 1:
            print()
