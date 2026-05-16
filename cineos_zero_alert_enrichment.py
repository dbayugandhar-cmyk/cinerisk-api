"""
CINEOS Zero-Alert Phone Enrichment
When a phone is not in our database, we still return
useful intelligence using pattern scoring.

This is what separates a watchlist from intelligence.
"""
import re, json
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5,minutes=30))

# High-risk number prefixes from our database
# Built from phones we KNOW are fraud operators
HIGH_RISK_PREFIXES = {
    # Rajasthan Jio — highest concentration of betting operators
    '7455': {'risk': 35, 'reason': 'High concentration of betting operators in CINEOS database'},
    '7400': {'risk': 35, 'reason': 'High concentration of betting operators in CINEOS database'},
    '7413': {'risk': 30, 'reason': 'Known toss-fix operator prefix'},
    '7832': {'risk': 30, 'reason': 'Cross-vertical fraud operator prefix'},
    # AP/Telangana Jio — Reddy Anna network
    '8881': {'risk': 40, 'reason': 'Reddy Anna / World777 network prefix — multiple confirmed operators'},
    '8808': {'risk': 25, 'reason': 'Known fraud operator prefix AP/Telangana'},
    '8824': {'risk': 20, 'reason': 'Known fraud operator prefix'},
    # Rajasthan Airtel — satta/matka operators
    '9186': {'risk': 30, 'reason': 'Faridabad satta operator prefix'},
    '9602': {'risk': 25, 'reason': 'Satta operator prefix Rajasthan'},
    '9521': {'risk': 25, 'reason': 'Known betting operator prefix'},
}

# Virtual/VoIP number ranges (higher fraud risk)
VOIP_PATTERNS = [
    r'^(\+91)?[6][0-3]',  # Some 6xxx ranges are VoIP
]

def score_unknown_phone(phone):
    """
    Score a phone not in our database.
    Returns intelligence even when we have no alerts.
    """
    d = re.sub(r'[^\d]', '', phone)
    if len(d) == 12 and d[:2] == '91':
        d = d[2:]
    if len(d) != 10:
        return {'error': 'Invalid phone format'}

    score = 0
    signals = []
    flags   = []

    # TRAI lookup
    try:
        series = json.load(open('configs/trai_series.json'))
        trai = series.get(d[:4]) or series.get(d[:3]) or {}
    except:
        trai = {}

    carrier = trai.get('operator', 'Unknown')
    circle  = trai.get('circle',   'Unknown')

    # High-risk prefix check
    prefix_risk = HIGH_RISK_PREFIXES.get(d[:4])
    if prefix_risk:
        score += prefix_risk['risk']
        signals.append(prefix_risk['reason'])
        flags.append('HIGH_RISK_PREFIX')

    # Rajasthan + Jio = highest betting operator concentration
    if 'Rajasthan' in circle and carrier == 'Jio':
        score += 15
        signals.append('Rajasthan Jio — highest concentration of betting operators in CINEOS database')

    # AP/Telangana + Jio = Reddy Anna network area
    if 'Andhra' in circle or 'Telangana' in circle:
        if carrier == 'Jio':
            score += 20
            signals.append('AP/Telangana Jio — Reddy Anna network registration area')

    # Number format patterns
    if d[:4] == d[4:8]:  # Repeating pattern
        score += 5
        signals.append('Repeating number pattern')

    # Sequential digits (often fake/VoIP)
    if d in ['1234567890','9876543210','0000000000']:
        score += 30
        flags.append('SEQUENTIAL_DIGITS')

    # All same digit
    if len(set(d)) == 1:
        score += 30
        flags.append('REPEATED_DIGITS')

    risk_level = 'HIGH' if score >= 40 else 'MEDIUM' if score >= 20 else 'LOW'

    return {
        'phone':         '+91' + d,
        'found_in_db':   False,
        'risk_score':    min(score, 99),
        'risk_level':    risk_level,
        'carrier':       carrier,
        'circle':        circle,
        'signals':       signals,
        'flags':         flags,
        'note':          'Phone not in CINEOS alert database. Risk scored from prefix patterns, TRAI data, and geographic concentration of known operators.',
        'recommendation':'Monitor — add to watchlist if other risk signals present',
    }

if __name__ == '__main__':
    # Test with phones we know
    tests = [
        '+917455000000',  # Rajasthan Jio prefix — should score HIGH
        '+918881000000',  # AP/TG Jio prefix — should score HIGH
        '+919876543210',  # Maharashtra Airtel — should score LOW
        '+919999999999',  # Delhi — LOW
        '+917400111111',  # Rajasthan Jio — HIGH
    ]
    print('Zero-Alert Phone Enrichment Test:')
    print(f'{"Phone":20} {"Risk":8} {"Score":6} {"Circle":25} {"Signals"}')
    print('-'*90)
    for ph in tests:
        r = score_unknown_phone(ph)
        sigs = ' | '.join(r['signals'][:1]) if r['signals'] else ''
        print(f'{ph:20} {r["risk_level"]:8} {r["risk_score"]:5}% {r["circle"]:25} {sigs}')
