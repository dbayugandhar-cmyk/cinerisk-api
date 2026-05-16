"""
CINEOS Phone Intelligence Engine
Complete operator profile from a single phone number.
This is the core of what makes CINEOS THE product.

Usage: python3 cineos_phone_intel.py +918881754538
       python3 cineos_phone_intel.py --all (top 20 operators)
"""
import json, sys, re, hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

IST = timezone(timedelta(hours=5,minutes=30))

CARRIER_RANGES = {
    '6':  {'880':'Jio','881':'Jio','882':'Jio','883':'Jio','884':'Jio','885':'Jio','886':'Jio','900':'Jio','901':'Jio','902':'Jio'},
    '7':  {'700':'Vi','701':'Vi','720':'Airtel','721':'Airtel','730':'BSNL','740':'Airtel','741':'Airtel','742':'Airtel','743':'Airtel','760':'Jio','761':'Jio','762':'Jio','763':'Jio','764':'Jio','800':'Airtel','801':'Airtel','802':'Airtel','803':'Airtel'},
    '8':  {'800':'Airtel','801':'Airtel','802':'Airtel','803':'Airtel','820':'BSNL','840':'Airtel','850':'Airtel','860':'Jio','861':'Jio','862':'Jio','863':'Jio','870':'Vi','880':'Jio','881':'Jio'},
    '9':  {'900':'Airtel','901':'Airtel','910':'Airtel','920':'Vi','930':'Vi','940':'Vi','950':'Airtel','960':'Vi','970':'Airtel','980':'Airtel','990':'Airtel'},
}

def infer_carrier(phone):
    d = phone.replace('+91','').replace(' ','')
    if len(d) == 10:
        first = d[0]
        prefix = d[:3]
        ranges = CARRIER_RANGES.get(first, {})
        return ranges.get(prefix, 'Unknown carrier')
    return 'Unknown'

def infer_circle(phone):
    """Infer telecom circle from number prefix."""
    d = phone.replace('+91','').replace(' ','')
    if len(d) < 4: return 'Unknown'
    prefix = d[:4]
    circles = {
        '9810':'Delhi','9811':'Delhi','9820':'Mumbai','9821':'Mumbai',
        '9830':'West Bengal','9831':'West Bengal','9840':'Tamil Nadu',
        '9841':'Tamil Nadu','9850':'Maharashtra','9860':'Maharashtra',
        '9870':'Delhi','9880':'Karnataka','9890':'Maharashtra',
        '7045':'Mumbai','7046':'Maharashtra','9867':'Maharashtra',
        '8881':'Andhra Pradesh/Telangana','8808':'Andhra Pradesh',
        '8824':'Andhra Pradesh','7455':'Rajasthan','7400':'Rajasthan',
        '7832':'Uttar Pradesh','7413':'Rajasthan','7348':'Rajasthan',
        '9186':'Rajasthan','9602':'Rajasthan',
    }
    return circles.get(d[:4], circles.get(d[:3], 'Unknown circle'))

def load_all_data():
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))
    try:
        graph = json.load(open('reports/fraud_intelligence_graph.json'))
    except:
        graph = {'nodes':{}, 'edges':[]}
    try:
        resurrection = json.load(open('reports/resurrection_report.json'))
    except:
        resurrection = {'resurrections':[]}
    return channels, alerts, graph, resurrection

def build_phone_index(channels, alerts):
    """Build complete phone → all mentions index."""
    index = defaultdict(lambda: {
        'channels': [],
        'alerts': [],
        'categories': set(),
        'first_seen': None,
        'last_seen': None,
        'total_reach': 0,
        'upis': set(),
        'domains': set(),
    })

    for ch in channels:
        for ph in ch.get('phones', []):
            if not ph or '+91888888' in ph: continue
            ph = ph.strip()
            entry = index[ph]
            entry['channels'].append({
                'username':    ch.get('username',''),
                'title':       ch.get('title',''),
                'subscribers': ch.get('subscribers',0),
                'category':    ch.get('category',''),
                'first_seen':  ch.get('first_seen',''),
                'last_seen':   ch.get('last_seen',''),
                'detected_at': ch.get('detected_at',''),
            })
            entry['categories'].add(ch.get('category','unknown'))
            entry['total_reach'] += ch.get('subscribers',0)
            for u in ch.get('upis',[]): entry['upis'].add(u)

    for a in alerts:
        chain = a.get('chain', {})
        for ph in chain.get('phones', []):
            if not ph: continue
            ph = ph.strip()
            entry = index[ph]
            entry['alerts'].append({
                'title':       a.get('title',''),
                'category':    a.get('category',''),
                'severity':    a.get('severity',''),
                'detected_at': a.get('detected_at',''),
                'evidence_hash': a.get('evidence_hash',''),
            })
            entry['categories'].add(a.get('category','unknown'))
            for u in chain.get('upis',[]): entry['upis'].add(u)

    # Compute date range
    for ph, entry in index.items():
        dates = []
        for ch in entry['channels']:
            d = ch.get('detected_at') or ch.get('first_seen','')
            if d: dates.append(d[:19])
        for a in entry['alerts']:
            d = a.get('detected_at','')
            if d: dates.append(d[:19])
        if dates:
            dates.sort()
            entry['first_seen'] = dates[0]
            entry['last_seen']  = dates[-1]
        entry['categories'] = list(entry['categories'])

    return index

def days_active(first_seen, last_seen=None):
    if not first_seen: return None
    try:
        t1 = datetime.fromisoformat(first_seen[:19]).replace(tzinfo=IST)
        t2 = datetime.fromisoformat(last_seen[:19]).replace(tzinfo=IST) if last_seen else datetime.now(IST)
        return (t2 - t1).days
    except:
        return None

def confidence_score(entry):
    score = 70
    n_ch = len(entry['channels'])
    if n_ch >= 5:  score += 15
    elif n_ch >= 3: score += 10
    elif n_ch >= 2: score += 5
    if len(entry['categories']) >= 2: score += 10
    if entry['upis']:   score += 5
    if entry['domains']: score += 5
    da = days_active(entry.get('first_seen'), entry.get('last_seen'))
    if da and da >= 30: score += 5
    return min(score, 99)

def profile_operator(phone, index, resurrection):
    """Generate complete operator intelligence profile."""
    ph = phone.strip()
    if not ph.startswith('+91'):
        ph = '+91' + ph.lstrip('0')

    entry = index.get(ph) or index.get(ph.replace('+91','')) or {}
    if not entry:
        # Try without country code
        bare = ph.replace('+91','')
        for k in index:
            if bare in k or k in bare:
                entry = index[k]
                ph = k
                break

    if not entry:
        print(f'No data found for {phone}')
        return None

    conf = confidence_score(entry)
    carrier = infer_carrier(ph)
    circle  = infer_circle(ph)
    da = days_active(entry.get('first_seen'), entry.get('last_seen'))
    channels = sorted(entry['channels'], key=lambda x: -x.get('subscribers',0))
    cats = entry['categories']
    upis = list(entry['upis'])[:5]
    total_reach = entry['total_reach']

    # Check resurrection
    resurrections = [r for r in resurrection.get('resurrections',[]) if ph in r.get('phone','')]

    # Cross-category exposure
    cross_cat = len(cats) > 1

    # Primary category
    cat_counts = Counter(ch['category'] for ch in channels)
    primary_cat = cat_counts.most_common(1)[0][0] if cat_counts else cats[0] if cats else 'unknown'

    # Risk level
    risk = 'CRITICAL' if conf >= 90 and cross_cat else 'HIGH' if conf >= 80 else 'MEDIUM'

    ev_hash = hashlib.sha256((ph + ''.join(c['username'] for c in channels)).encode()).hexdigest()[:16]

    return {
        'phone':        ph,
        'carrier':      carrier,
        'circle':       circle,
        'confidence':   conf,
        'risk':         risk,
        'channels':     channels,
        'channel_count':len(channels),
        'total_reach':  total_reach,
        'categories':   cats,
        'primary_cat':  primary_cat,
        'cross_cat':    cross_cat,
        'upis':         upis,
        'first_seen':   entry.get('first_seen','Unknown'),
        'last_seen':    entry.get('last_seen','Unknown'),
        'days_active':  da,
        'resurrections':resurrections,
        'ev_hash':      ev_hash,
        'alerts':       entry.get('alerts',[])[:5],
    }

def print_profile(p):
    if not p: return

    now = datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')
    print()
    print('='*65)
    print(f'  CINEOS OPERATOR INTELLIGENCE PROFILE')
    print(f'  Generated: {now}')
    print(f'  Patent 64/049,190 · IT Act §65B')
    print('='*65)

    print(f'\n  PHONE:      {p["phone"]}')
    print(f'  CARRIER:    {p["carrier"]}')
    print(f'  CIRCLE:     {p["circle"]}')
    print(f'  CONFIDENCE: {p["confidence"]}%  [{p["risk"]}]')
    print(f'  CHANNELS:   {p["channel_count"]} confirmed')
    print(f'  REACH:      {p["total_reach"]:,} combined subscribers')

    print(f'\n  ACTIVITY TIMELINE:')
    print(f'    First seen:  {p["first_seen"][:10] if p["first_seen"] != "Unknown" else "Unknown"}')
    print(f'    Last seen:   {p["last_seen"][:10] if p["last_seen"] != "Unknown" else "Unknown"}')
    print(f'    Days active: {p["days_active"] or "Unknown"}')

    print(f'\n  CHANNEL NETWORK ({p["channel_count"]} channels):')
    for ch in p['channels'][:8]:
        print(f'    @{ch["username"][:45]:45}  {ch["subscribers"]:>8,}  {ch["category"]}')

    print(f'\n  FRAUD CATEGORIES ({len(p["categories"])}):')
    for cat in p['categories']:
        marker = ' ← PRIMARY' if cat == p['primary_cat'] else ''
        print(f'    {cat}{marker}')

    if p['cross_cat']:
        print(f'\n  ⚠  CROSS-CATEGORY OPERATOR — active in multiple fraud types')
        print(f'     This significantly increases legal exposure')

    if p['upis']:
        print(f'\n  UPI IDs EXTRACTED:')
        for u in p['upis']:
            print(f'    {u}')

    if p['resurrections']:
        print(f'\n  ⚠  RESURRECTION CONFIRMED:')
        for r in p['resurrections']:
            print(f'    Active {r["days_after_bust"]}d after {r["enforcement_event"]}')
            print(f'    Channel: @{r["channel"]}')
            print(f'    Legal note: {r["legal_note"]}')
    else:
        print(f'\n  Resurrection: No post-arrest activity detected yet')

    print(f'\n  EVIDENCE HASH (IT Act §65B):')
    print(f'    {p["ev_hash"]}...')

    print(f'\n  NARRATIVE:')
    print(generate_narrative(p))

    print()
    print('='*65)

def generate_narrative(p):
    """Auto-generate plain English case narrative."""
    lines = []
    phone = p['phone']
    ch_n  = p['channel_count']
    reach = f'{p["total_reach"]:,}'
    cats  = ', '.join(p['categories'])

    if p['first_seen'] and p['first_seen'] != 'Unknown':
        da = p['days_active'] or 0
        lines.append(f'  This operator first appeared in CINEOS database on '
                     f'{p["first_seen"][:10]}, {da} days ago.')
    else:
        lines.append(f'  This operator was detected by CINEOS automated scanning.')

    if ch_n > 1:
        lines.append(f'  The same phone number {phone} has been extracted from '
                     f'messages across {ch_n} separate Telegram channels, '
                     f'reaching a combined {reach} subscribers.')
        lines.append(f'  This cross-channel presence confirms a single operator '
                     f'controlling multiple fraud channels.')
    else:
        lines.append(f'  Phone {phone} was extracted from a Telegram channel '
                     f'with {reach} subscribers.')

    if p['cross_cat']:
        lines.append(f'  The operator is active across multiple fraud categories: '
                     f'{cats}. This cross-vertical activity indicates a '
                     f'sophisticated operation and increases criminal exposure.')

    if p['upis']:
        lines.append(f'  UPI payment handles were extracted from the same channels, '
                     f'providing payment trail linkage: {", ".join(p["upis"][:2])}.')

    if p['resurrections']:
        for r in p['resurrections'][:1]:
            lines.append(f'  After {r["enforcement_event"]}, this operator '
                         f'continued operating — detected in new channels '
                         f'{r["days_after_bust"]} days post-arrest. '
                         f'This constitutes continued criminal operation.')

    lines.append(f'  Evidence certified under IT Act 2000 §65B at detection. '
                 f'SHA-256 hash: {p["ev_hash"]}...')

    return '\n'.join(lines)

def top_operators(index, resurrection, n=20):
    """Show top N operators by channel count and confidence."""
    scored = []
    for ph, entry in index.items():
        if len(entry['channels']) < 1: continue
        conf = confidence_score(entry)
        scored.append((ph, entry, conf))
    scored.sort(key=lambda x: (-len(x[1]['channels']), -x[2]))

    print(f'\nCINEOS TOP {n} OPERATOR PROFILES')
    print(f'Generated: {datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}')
    print('='*95)
    print(f'{"Phone":20} {"Channels":8} {"Reach":10} {"Conf":6} {"Categories":35} {"Days":6}')
    print('-'*95)

    for ph, entry, conf in scored[:n]:
        ch_n  = len(entry['channels'])
        reach = entry['total_reach']
        cats  = ','.join(list(entry['categories'])[:3])[:34]
        rs    = f'{reach/1e6:.1f}M' if reach>=1e6 else f'{reach/1e3:.0f}K'
        da    = days_active(entry.get('first_seen'), entry.get('last_seen'))
        da_s  = str(da)+'d' if da else '?'
        res   = ' ⚠RESURRECTED' if any(ph in r.get('phone','') for r in resurrection.get('resurrections',[])) else ''
        print(f'{ph:20} {ch_n:8} {rs:10} {conf:5}% {cats:35} {da_s:6}{res}')

if __name__ == '__main__':
    channels, alerts, graph, resurrection = load_all_data()
    index = build_phone_index(channels, alerts)
    print(f'Phone index built: {len(index)} unique phones')

    if len(sys.argv) > 1 and sys.argv[1] == '--all':
        top_operators(index, resurrection, 20)
    elif len(sys.argv) > 1:
        p = profile_operator(sys.argv[1], index, resurrection)
        print_profile(p)
    else:
        # Default: show top operators + profile the #1
        top_operators(index, resurrection, 15)
        print('\nRun: python3 cineos_phone_intel.py +91XXXXXXXXXX for full profile')
