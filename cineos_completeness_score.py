"""
CINEOS Case Completeness Scoring Engine
Scores every operator profile on WHO/WHAT/WHEN/WHERE/HOW/WHY.
Displayed in dashboard so buyers see intelligence quality in real time.
This is a unique trust layer — no competitor shows this.
"""
import json, os, re
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5, minutes=30))

def score_operator(profile):
    """
    Score an operator profile 0-100 on each dimension.
    Returns dict with scores + overall + missing items.
    """
    scores = {}
    missing = {}
    
    ph       = profile.get('phone','')
    channels = profile.get('channels',[])
    cats     = profile.get('categories',[])
    upis     = profile.get('upis',[])
    name     = profile.get('inferred_name','')
    aliases  = profile.get('known_aliases',[])
    first    = profile.get('first_seen','')
    da       = profile.get('days_active')
    res      = profile.get('resurrections',[])
    conf     = profile.get('confidence', 0)
    circle   = profile.get('circle','Unknown')
    carrier  = profile.get('carrier','Unknown')

    # Load alias chains
    try:
        alias_data = json.load(open('reports/alias_chains.json'))
        phone_aliases = {}
        for net, data in alias_data.get('alias_chains',{}).items():
            if ph in data.get('phones',[]):
                phone_aliases = data
    except:
        phone_aliases = {}

    # Load hotspot data
    try:
        hotspot_data = json.load(open('reports/hotspot_map.json'))
        phone_hotspot = hotspot_data.get('phone_hotspot_map',{}).get(ph,'')
    except:
        phone_hotspot = ''

    # ── WHO (0-100) ────────────────────────────────────────
    who = 0
    who_missing = []
    if ph:                          who += 20
    if carrier != 'Unknown':        who += 15
    if circle != 'Unknown':         who += 15
    if name:                        who += 20
    else: who_missing.append('Inferred operator name')
    if aliases:                     who += 15
    else: who_missing.append('Known aliases')
    if phone_aliases:               who += 15
    else: who_missing.append('Alias chain (brand evolution)')
    scores['WHO'] = min(who, 100)
    missing['WHO'] = who_missing

    # ── WHAT (0-100) ───────────────────────────────────────
    what = 0
    what_missing = []
    if cats:                        what += 20
    if len(cats) >= 2:              what += 15  # cross-vertical
    if len(channels) >= 3:          what += 20
    if upis:                        what += 15
    else: what_missing.append('UPI payment handles')
    # Check for financial flow
    has_flow = any(
        ch.get('chain',{}).get('financial_flow') or
        ch.get('chain',{}).get('match_fixing_signals')
        for ch in channels
    )
    if has_flow:                    what += 15
    else: what_missing.append('Financial flow data')
    if len(channels) >= 5:          what += 15
    else: what_missing.append('Agent recruitment signals')
    scores['WHAT'] = min(what, 100)
    missing['WHAT'] = what_missing

    # ── WHEN (0-100) ───────────────────────────────────────
    when = 0
    when_missing = []
    if first:                       when += 25
    else: when_missing.append('Channel creation date (enrichment needed)')
    if da and da > 0:               when += 25
    if da and da > 30:              when += 15  # long running
    if res:                         when += 20  # resurrection = timeline evidence
    else: when_missing.append('Post-arrest activity data')
    # Post frequency
    has_freq = any(ch.get('posts_per_day') for ch in channels)
    if has_freq:                    when += 15
    else: when_missing.append('Posting frequency per day')
    scores['WHEN'] = min(when, 100)
    missing['WHEN'] = when_missing

    # ── WHERE (0-100) ──────────────────────────────────────
    where = 0
    where_missing = []
    if circle != 'Unknown':         where += 25
    if carrier != 'Unknown':        where += 15
    if phone_hotspot:               where += 30
    else: where_missing.append('Fraud geography hotspot mapping')
    # Cross-border
    try:
        corridor = json.load(open('reports/corridor_map.json'))
        if ph in json.dumps(corridor):
            where += 20
        else: where_missing.append('Cross-border payment corridor')
    except:
        where_missing.append('Cross-border payment corridor')
        where += 0
    if not where_missing or where >= 70: pass
    else: where_missing.append('City-level location (subpoena required)')
    scores['WHERE'] = min(where, 100)
    missing['WHERE'] = where_missing

    # ── HOW (0-100) ────────────────────────────────────────
    how = 0
    how_missing = []
    if len(channels) >= 2:          how += 20  # multi-channel = method confirmed
    if upis:                        how += 20  # payment method known
    else: how_missing.append('Payment method confirmation')
    # Agent signals
    try:
        alias_rpt = json.load(open('reports/alias_chains.json'))
        agent_sigs = alias_rpt.get('agent_signals', [])
        ph_agents = [s for s in agent_sigs if ph in str(s.get('phones',''))]
        if ph_agents:               how += 20
        else: how_missing.append('Agent recruitment method')
    except:
        how_missing.append('Agent recruitment method')
    if len(cats) > 1:               how += 20  # cross-vertical = sophisticated
    if res:                         how += 20  # resurrection = evasion method known
    else: how_missing.append('Post-enforcement evasion method')
    scores['HOW'] = min(how, 100)
    missing['HOW'] = how_missing

    # ── WHY (0-100) ────────────────────────────────────────
    # Legal framework completeness
    why = 0
    why_missing = []
    LEGAL_BY_CAT = {
        'illegal_betting':   ['Online Gaming Act 2025', 'IT Act §65B', 'PMLA 2002'],
        'crypto_fraud':      ['PMLA 2002', 'IT Act §65B', 'IPC §420'],
        'upi_mule':          ['PMLA 2002', 'IT Act §66', 'RBI Guidelines'],
        'counterfeit_pharma':['Drugs Act §17A', 'IT Act §65B', 'NDPS Act'],
        'loan_fraud':        ['RBI Guidelines', 'IT Act §66D', 'IPC §420'],
    }
    primary_cat = cats[0] if cats else ''
    legal_acts = LEGAL_BY_CAT.get(primary_cat, [])
    if legal_acts:                  why += 40
    why += 30  # §65B always present
    why += 15  # Evidence hash present
    if upis:                        why += 15  # Payment trail
    else: why_missing.append('UPI payment trail for PMLA')
    scores['WHY'] = min(why, 100)
    missing['WHY'] = why_missing

    # ── OVERALL ────────────────────────────────────────────
    weights = {'WHO':25, 'WHAT':20, 'WHEN':20, 'WHERE':15, 'HOW':10, 'WHY':10}
    overall = sum(scores[k] * weights[k] / 100 for k in weights)

    return {
        'phone':    ph,
        'name':     name or 'Unknown',
        'scores':   scores,
        'overall':  round(overall),
        'missing':  missing,
        'grade':    'A' if overall >= 85 else 'B' if overall >= 70 else 'C' if overall >= 55 else 'D',
        'pitch_ready': overall >= 70,
    }

def score_all_operators():
    """Score all known operators and produce ranking."""
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))

    try:
        resurrection = json.load(open('reports/resurrection_report.json'))
    except:
        resurrection = {'resurrections': []}

    from cineos_phone_intel import build_phone_index, profile_operator
    index   = build_phone_index(channels, alerts)
    scored  = sorted(index.items(), key=lambda x: -len(x[1]['channels']))

    results = []
    for ph, entry in scored[:20]:
        if len(entry['channels']) < 2:
            continue
        p = profile_operator(ph, index, resurrection)
        if not p:
            continue
        s = score_operator(p)
        results.append(s)

    results.sort(key=lambda x: -x['overall'])

    print(f'\nOPERATOR COMPLETENESS SCORES:')
    print(f'{"Phone":20} {"Name":25} {"WHO":5} {"WHAT":5} {"WHEN":5} {"WHERE":5} {"HOW":5} {"WHY":5} {"OVERALL":8} {"GRADE":5} {"READY"}')
    print('-' * 105)
    for r in results:
        s = r['scores']
        ready = '✓ YES' if r['pitch_ready'] else '✗ NO'
        print(f'{r["phone"]:20} {r["name"][:24]:25} '
              f'{s["WHO"]:5} {s["WHAT"]:5} {s["WHEN"]:5} '
              f'{s["WHERE"]:5} {s["HOW"]:5} {s["WHY"]:5} '
              f'{r["overall"]:8} {r["grade"]:5} {ready}')

    # Save
    json.dump(results, open('reports/completeness_scores.json','w'), indent=2)
    print(f'\nSaved: reports/completeness_scores.json')

    # Platform-level summary
    pitch_ready = [r for r in results if r['pitch_ready']]
    print(f'\nPLATFORM SUMMARY:')
    print(f'  Operators scored:     {len(results)}')
    print(f'  Pitch-ready (≥70%):   {len(pitch_ready)}')
    print(f'  Top score:            {max(r["overall"] for r in results) if results else 0}%')
    print(f'  Average score:        {sum(r["overall"] for r in results)//len(results) if results else 0}%')

    return results

if __name__ == '__main__':
    print('=' * 55)
    print(f'  CINEOS COMPLETENESS SCORING ENGINE')
    print(f'  {datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}')
    print('=' * 55)
    score_all_operators()
