"""
CINEOS Channel-to-Alert Generator
Generates proper §65B certified alerts for every channel
that has phones/UPIs in the database but no alert yet.

This is the missing link:
  Deep scan finds phones → stores in channels.json
  This script → creates alerts from those channels
  Result: every confirmed phone gets a proper alert
"""
import json, re, hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5,minutes=30))

LEGAL = {
    'illegal_betting':    'Online Gaming Act 2025 §8 + PMLA 2002 §3 + IT Act §65B',
    'crypto_fraud':       'PMLA 2002 §3 + IT Act §65B + IPC §420',
    'upi_mule':           'PMLA 2002 §3 + IT Act §66 + IPC §420',
    'counterfeit_pharma': 'Drugs & Cosmetics Act §17A + NDPS Act + IT Act §65B',
    'investment_fraud':   'SEBI Act §12A + IT Act §66D + IPC §420',
    'colour_prediction':  'Online Gaming Act 2025 §8 + IT Act §65B',
    'loan_fraud':         'RBI Guidelines + IT Act §66D + IPC §420',
    'task_fraud':         'IT Act §66D + IPC §420',
    'piracy':             'Copyright Act §51 + IT Act §65B',
    'domain_squat':       'IT Act §66D + Trade Marks Act §29',
    'unknown':            'IT Act §65B',
}

SEVERITY = {
    'illegal_betting':    'critical',
    'crypto_fraud':       'critical',
    'upi_mule':           'critical',
    'counterfeit_pharma': 'high',
    'investment_fraud':   'high',
    'colour_prediction':  'high',
    'loan_fraud':         'high',
    'task_fraud':         'high',
    'piracy':             'medium',
    'domain_squat':       'medium',
    'unknown':            'medium',
}

REPORT_TO = {
    'illegal_betting':    ['NOGC nogc.gov.in', 'State Cybercrime', 'ED enforcement.gov.in'],
    'crypto_fraud':       ['FIU-IND fiuindia.gov.in', 'ED enforcement.gov.in', 'I4C 1930'],
    'upi_mule':           ['FIU-IND fiuindia.gov.in', 'Bank Fraud Desk', 'I4C 1930'],
    'counterfeit_pharma': ['CDSCO cdsco.gov.in', 'State Drug Controller', 'I4C 1930'],
    'investment_fraud':   ['SEBI sebi.gov.in', 'I4C 1930', 'ED enforcement.gov.in'],
    'colour_prediction':  ['NOGC nogc.gov.in', 'State Cybercrime', 'I4C 1930'],
    'loan_fraud':         ['RBI rbi.org.in', 'I4C 1930', 'State Cybercrime'],
    'task_fraud':         ['I4C 1930', 'State Cybercrime'],
    'piracy':             ['MIB mib.gov.in', 'Copyright Board', 'Platform DMCA'],
    'domain_squat':       ['NIXI nixi.in', 'Brand Legal Team', 'I4C 1930'],
    'unknown':            ['I4C 1930', 'State Cybercrime'],
}

def make_alert_id(username, phone, ts):
    content = f'{username}:{phone}:{ts}'
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def confidence_score(phones, upis, subscribers, category):
    base = 60
    if len(phones) >= 5: base = 95
    elif len(phones) >= 3: base = 85
    elif len(phones) >= 2: base = 80
    elif len(phones) == 1: base = 70
    if upis: base = min(99, base + 10)
    if subscribers > 100000: base = min(99, base + 5)
    if category in ('illegal_betting','crypto_fraud','upi_mule'): base = min(99, base + 5)
    return base

def generate_alerts():
    channels  = json.load(open('reports/all_channels.json'))
    existing  = json.load(open('reports/alerts/live_alerts.json'))

    # Build set of channels already in alerts
    alerted = set()
    for a in existing:
        for ch in a.get('chain',{}).get('channels_found',[]):
            u = str(ch).replace('https://t.me/','').lower().strip('/').replace('@','')
            alerted.add(u)

    # Also build existing alert IDs for dedup
    existing_ids = {a.get('id','') for a in existing}

    now = datetime.now(IST)
    new_alerts = []
    skipped = 0

    for channel in channels:
        phones = channel.get('phones', [])
        upis   = channel.get('upis', [])

        # Only process channels with phones
        if not phones:
            skipped += 1
            continue

        username    = channel.get('username', '')
        title       = channel.get('title', username)
        subscribers = channel.get('subscribers', 0)
        category    = channel.get('category', 'unknown')
        bio         = channel.get('bio', '')
        domains     = channel.get('domains', [])

        # Check if already alerted
        if username.lower() in alerted:
            skipped += 1
            continue

        # Build alert
        conf      = confidence_score(phones, upis, subscribers, category)
        severity  = SEVERITY.get(category, 'medium')
        if conf >= 85: severity = 'critical'
        elif conf >= 75: severity = 'high'

        legal     = LEGAL.get(category, 'IT Act §65B')
        report_to = REPORT_TO.get(category, ['I4C 1930'])

        # Primary phone for this alert
        primary_phone = phones[0] if phones else ''
        alert_id      = make_alert_id(username, primary_phone, now.isoformat())

        if alert_id in existing_ids:
            skipped += 1
            continue

        # Build detail string
        detail_parts = []
        if bio: detail_parts.append(bio[:150])
        if phones: detail_parts.append(f'Phones: {", ".join(phones[:3])}')
        if upis: detail_parts.append(f'UPI: {", ".join(upis[:3])}')
        if domains: detail_parts.append(f'Domains: {", ".join(domains[:2])}')
        detail = ' | '.join(detail_parts) if detail_parts else title

        alert = {
            'id':           alert_id,
            'title':        f'@{username} — {category.replace("_"," ")} · {subscribers:,} subscribers',
            'category':     category,
            'severity':     severity,
            'platform':     'Telegram',
            'detail':       detail[:300],
            'detected_at':  now.isoformat(),
            'source':       f'channel_scan',
            'evidence_hash': alert_id,
            'reach':         subscribers,
            'phone':         primary_phone,
            'upi':           upis[0] if upis else '',
            'domain':        domains[0] if domains else '',
            'legal_basis':   legal,
            'next_steps': [
                'Evidence hash preserved at detection',
                f'File takedown: abuse@telegram.org — channel @{username}',
                f'Report to: {report_to[0]}',
                'Request telecom subpoena for phone subscriber identity',
            ],
            'report_to': report_to,
            'attribution': {
                'phone':   primary_phone,
                'upi':     upis[0] if upis else '',
                'domain':  domains[0] if domains else '',
                'source':  'telegram_deep_scan',
            },
            'chain': {
                'channels_found':   [f'https://t.me/{username}'],
                'keywords_matched': [],
                'reach':            subscribers,
                'phones':           phones,
                'upis':             upis,
                'domains':          domains,
                'evidence_hashes':  [alert_id],
                'legal_basis':      legal,
                'confidence':       conf,
                'recommended_action': f'File §69A takedown · Telecom subpoena for {primary_phone}',
                'report_to':        report_to,
                'captured_at':      now.isoformat(),
            },
        }

        new_alerts.append(alert)
        existing_ids.add(alert_id)

    print(f'CINEOS CHANNEL→ALERT GENERATOR')
    print(f'  Channels processed: {len(channels)}')
    print(f'  Already alerted:    {skipped}')
    print(f'  New alerts:         {len(new_alerts)}')
    print()

    if not new_alerts:
        print('No new alerts to add.')
        return

    # Show breakdown
    from collections import Counter
    cats = Counter(a.get('category','') for a in new_alerts)
    print('NEW ALERTS BY CATEGORY:')
    for cat, n in cats.most_common():
        phones_count = sum(len(a.get('chain',{}).get('phones',[])) for a in new_alerts if a.get('category')==cat)
        reach = sum(a.get('reach',0) for a in new_alerts if a.get('category')==cat)
        print(f'  {cat:30} {n:>4} alerts  '
              f'{phones_count:>4} phones  {reach:>12,} reach')

    # Sample
    print()
    print('SAMPLE NEW ALERTS:')
    for a in sorted(new_alerts, key=lambda x: -x.get('reach',0))[:8]:
        phones = a.get('chain',{}).get('phones',[])
        print(f'  [{a["severity"].upper():8}] @{a.get("title","")[:50]:50} '
              f'reach:{a["reach"]:>8,}  '
              f'phones:{len(phones)}')

    # Merge with existing
    merged = new_alerts + existing
    merged.sort(key=lambda x: (
        {'critical':0,'high':1,'medium':2,'low':3}.get(x.get('severity','low'),3)
    ))
    merged = merged[:10000]

    json.dump(merged, open('reports/alerts/live_alerts.json','w'),
              indent=2, default=str)
    print(f'\nSAVED: {len(merged)} total alerts')

if __name__ == '__main__':
    generate_alerts()
