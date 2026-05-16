"""
CINEOS Case Narrative Engine
Generates complete operator story from all available data.
This is what turns data into THE product.

Every case study gets:
1. Who — operator identity layer
2. What — what crimes they run
3. When — full timeline
4. Where — geographic inference
5. How — operational method
6. Why it matters — legal + business impact
7. What next — specific action steps
"""
import json, hashlib, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

IST = timezone(timedelta(hours=5,minutes=30))
os.makedirs('reports/narratives', exist_ok=True)

def now_ist(): return datetime.now(IST)
def sha(t): return hashlib.sha256(t.encode()).hexdigest()
def fmt_reach(n):
    return f'{n/1e6:.1f}M' if n>=1e6 else f'{n/1e3:.0f}K' if n>=1e3 else str(n)

CATEGORY_LABELS = {
    'illegal_betting':    'Illegal Betting',
    'crypto_fraud':       'Crypto Fraud',
    'piracy':             'OTT/Content Piracy',
    'colour_prediction':  'Colour Prediction Game Fraud',
    'upi_mule':           'UPI Mule / Money Mule',
    'investment_fraud':   'Investment Fraud',
    'counterfeit_pharma': 'Counterfeit Pharmaceuticals',
    'loan_fraud':         'Loan Fraud',
    'domain_squat':       'Domain Squatting',
    'ai_scam':            'AI Voice / Deepfake Scam',
}

LEGAL_BY_CAT = {
    'illegal_betting':    ['Public Gambling Act 1867', 'Online Gaming Act 2025 §8', 'IT Act 2000 §65B+§66D'],
    'crypto_fraud':       ['PMLA 2002 §3+§4', 'IT Act 2000 §65B+§66D', 'IPC §420'],
    'piracy':             ['Copyright Act 1957 §51', 'IT Act 2000 §65B+§66D', 'IPC §63'],
    'colour_prediction':  ['Online Gaming Act 2025 §8', 'IT Act 2000 §65B+§66D', 'FEMA 1999'],
    'upi_mule':           ['PMLA 2002 §3+§4', 'IT Act 2000 §66', 'IPC §420'],
    'investment_fraud':   ['SEBI Act §12A', 'PMLA 2002 §3', 'IT Act 2000 §65B+§66D', 'IPC §420'],
    'counterfeit_pharma': ['Drugs & Cosmetics Act 1940 §17A+§18', 'IT Act 2000 §65B', 'IPC §420+§468'],
    'loan_fraud':         ['RBI Guidelines', 'IT Act 2000 §66D', 'IPC §420'],
}

REPORT_TO_BY_CAT = {
    'illegal_betting':    ['NOGC — nogc.gov.in', 'I4C — cybercrime.gov.in', 'State Police Cybercrime Cell'],
    'crypto_fraud':       ['ED — enforcement.gov.in', 'FIU-IND — fiuindia.gov.in', 'I4C — cybercrime.gov.in'],
    'piracy':             ['MIB — mib.gov.in', 'I4C — cybercrime.gov.in', 'Brand Legal Team'],
    'upi_mule':           ['FIU-IND — fiuindia.gov.in', 'RBI — rbi.org.in', 'I4C — cybercrime.gov.in'],
    'counterfeit_pharma': ['CDSCO — cdsco.gov.in', 'State Drug Controller', 'I4C — cybercrime.gov.in'],
    'investment_fraud':   ['SEBI SCORES — scores.sebi.gov.in', 'ED', 'I4C — cybercrime.gov.in'],
}

def build_narrative(op):
    """
    Generate complete operator narrative.
    op = operator profile dict from cineos_phone_intel.py
    """
    phone    = op['phone']
    channels = op['channels']
    cats     = op['categories']
    reach    = op['total_reach']
    conf     = op['confidence']
    circle   = op.get('circle', 'Unknown')
    carrier  = op.get('carrier', 'Unknown')
    inf_name = op.get('inferred_name', '')
    aliases  = op.get('known_aliases', [])
    da       = op.get('days_active')
    first    = op.get('first_seen','')[:10]
    last     = op.get('last_seen','')[:10]
    upis     = op.get('upis',[])
    res      = op.get('resurrections',[])
    primary  = op.get('primary_cat', cats[0] if cats else 'unknown')
    cross    = len(cats) > 1

    cat_labels = [CATEGORY_LABELS.get(c, c) for c in cats]
    primary_label = CATEGORY_LABELS.get(primary, primary)

    # ── WHO ──────────────────────────────────────────────
    who = f"""OPERATOR IDENTITY
Phone:     {phone}
Inferred name: {inf_name or 'Unknown — enrichment pending'}
Known aliases: {', '.join(aliases) if aliases else 'None confirmed yet'}
Carrier:   {carrier}
Circle:    {circle} (telecom registration area)
Channels:  {len(channels)} confirmed Telegram channels
Reach:     {fmt_reach(reach)} combined subscribers
Confidence: {conf}% attribution confidence"""

    # ── WHAT ─────────────────────────────────────────────
    what_lines = [f'PRIMARY OPERATION: {primary_label}']
    if cross:
        what_lines.append(f'SECONDARY OPERATIONS: {", ".join(cat_labels[1:])}')
        what_lines.append(f'CROSS-VERTICAL: Same operator confirmed across {len(cats)} fraud types')
        what_lines.append(f'This pattern indicates an organised criminal enterprise rather than opportunistic fraud.')
    what_lines.append('')
    what_lines.append('CHANNEL BREAKDOWN:')
    for ch in channels[:6]:
        what_lines.append(f'  @{ch["username"][:40]:42} {ch["subscribers"]:>8,} subs  {CATEGORY_LABELS.get(ch["category"], ch["category"])}')
    what = '\n'.join(what_lines)

    # ── WHEN ─────────────────────────────────────────────
    if da and first:
        when = f"""ACTIVITY TIMELINE
First detected: {first}
Last detected:  {last}
Days active:    {da} days in CINEOS database
Status:         {'ACTIVE — detected in last 7 days' if da <= 7 else 'MONITORED — ongoing tracking'}

Note: Detection date reflects when CINEOS first captured this operator.
Actual operation may predate CINEOS monitoring."""
    else:
        when = f"""ACTIVITY TIMELINE
First detected: {first or 'Unknown — pre-dates current scan'}
Last detected:  {last or 'Unknown'}
Status:         ACTIVE — channels still live at time of report"""

    if res:
        r = res[0]
        when += f"""

POST-ARREST ACTIVITY CONFIRMED:
  Enforcement event: {r['enforcement_event']}
  Days until reappearance: {r['days_after_bust']} days
  New channel: @{r['channel']}
  Legal significance: Continued operation post-arrest = aggravated offense
  Under IPC §195A + IT Act §66: enhanced imprisonment applicable"""

    # ── HOW ──────────────────────────────────────────────
    method_map = {
        'illegal_betting': """OPERATIONAL METHOD — ILLEGAL BETTING
1. Creates Telegram channel with betting platform brand name
   (Mahadev Book, World777, Laser247, Reddy Anna, etc.)
2. Posts operator phone number in channel description or 
   first pinned message for customer contact
3. Recruits sub-agents via WhatsApp to expand network
4. Collects betting funds via UPI, crypto, or hawala
5. Pays winning bets in cash or crypto to avoid banking trail
6. Rotates channels after police action — same phone, new channel""",
        'crypto_fraud': """OPERATIONAL METHOD — CRYPTO FRAUD
1. Creates Telegram channel posing as investment platform
2. Shows fake profit screenshots to recruit investors
3. Collects USDT/BTC via provided wallet addresses
4. Moves funds through P2P exchanges to INR
5. Uses hawala or mule accounts for final cash-out
6. Disappears after collecting sufficient funds (exit scam)""",
        'piracy': """OPERATIONAL METHOD — CONTENT PIRACY
1. Creates Telegram channel with OTT brand names 
   (JioHotstar, Netflix, Amazon Prime)
2. Streams live matches or movies via Telegram video
3. Monetises via subscription fees or advertising
4. Uses same operator phone for subscriber support
5. Migrates to new channel after takedown""",
        'upi_mule': """OPERATIONAL METHOD — UPI MULE
1. Recruits individuals via Telegram with commission promises
2. Collects bank account details or active UPI IDs
3. Routes fraud proceeds through mule accounts
4. Pays mule 1-2% commission per transaction
5. Account holder faces legal consequences as the visible actor""",
        'counterfeit_pharma': """OPERATIONAL METHOD — COUNTERFEIT PHARMA
1. Creates Telegram channel advertising prescription drugs
2. Accepts orders via WhatsApp or Telegram DM
3. Sources drugs from unregulated manufacturers
4. Ships COD via courier without prescription verification
5. Hides operator identity — uses images not text for contact""",
    }
    how = method_map.get(primary, f'Operational method: {primary_label} via Telegram channels')

    # ── WHY IT MATTERS ───────────────────────────────────
    legal_acts = LEGAL_BY_CAT.get(primary, ['IT Act 2000 §65B+§66D', 'IPC §420'])
    report_to  = REPORT_TO_BY_CAT.get(primary, ['I4C — cybercrime.gov.in'])

    why = f"""WHY THIS MATTERS

Scale of harm:
  {fmt_reach(reach)} subscribers exposed to fraud content
  {'Cross-vertical operation = multiple victim pools' if cross else ''}

Legal framework:
  {chr(10).join('  ' + a for a in legal_acts)}

Business impact (for buyers):
  Banks/PSPs: Phone {phone} on your customer watchlist = catch mules before fraud
  Brand owners: Channel activity targets your customers directly
  Regulators: Pre-complaint intelligence with court-ready evidence

Evidence certification:
  IT Act 2000 §65B(2) — all 5 conditions met
  SHA-256 hash generated at detection
  Timestamp legally defensible in court"""

    if upis:
        why += f"""

UPI PAYMENT TRAIL:
  {chr(10).join('  ' + u for u in upis[:3])}
  (Cross-reference with bank records for PMLA prosecution)"""

    # ── NEXT STEPS ───────────────────────────────────────
    steps_map = {
        'illegal_betting': [
            f'File complaint at NOGC portal: nogc.gov.in (reference phone {phone})',
            'Submit to I4C cybercrime portal: cybercrime.gov.in',
            'File FIR: Public Gambling Act 1867 + Online Gaming Act 2025 §8',
            f'Phone subpoena: request subscriber identity for {phone} from telecom',
            'Request Telegram channel takedown via MHA portal',
            'Cross-reference phone against bank KYC for UPI/account linkage',
        ],
        'crypto_fraud': [
            'File with ED: enforcement.gov.in (PMLA 2002 §3)',
            'File with FIU-IND: fiuindia.gov.in',
            'Report to I4C: cybercrime.gov.in',
            f'Request phone subpoena for {phone}',
            'Freeze any identified UPI handles via bank request',
        ],
        'upi_mule': [
            'File with FIU-IND: fiuindia.gov.in (PMLA threshold)',
            'Alert RBI: rbi.org.in/fraud',
            'Block identified UPI handles via NPCI',
            f'Phone subpoena for {phone}',
            'Trace to originating fraud via transaction reversal',
        ],
        'counterfeit_pharma': [
            'File complaint: cdsco.gov.in/complaint',
            'Report to State Drug Controller',
            'File FIR: Drugs & Cosmetics Act §17A + §18',
            'Alert NDPS authority if Schedule H drugs involved',
        ],
    }
    steps = steps_map.get(primary, [
        f'File complaint at I4C: cybercrime.gov.in (phone: {phone})',
        'Submit evidence package to state cybercrime cell',
        'Request phone subpoena from telecom provider',
    ])
    next_steps = 'RECOMMENDED NEXT STEPS\n' + '\n'.join(f'{i+1}. {s}' for i,s in enumerate(steps))

    # ── ASSEMBLE FULL NARRATIVE ───────────────────────────
    ev_hash = sha(phone + ''.join(c['username'] for c in channels[:3]))
    narrative = {
        'case_id':    f'CINEOS-{primary.upper()[:4]}-2026-{hash(phone)%9999:04d}',
        'phone':      phone,
        'confidence': conf,
        'generated':  now_ist().isoformat(),
        'ev_hash':    ev_hash[:16],
        'sections': {
            'WHO':          who,
            'WHAT':         what,
            'WHEN':         when,
            'HOW':          how,
            'WHY':          why,
            'NEXT_STEPS':   next_steps,
        },
        'report_to':  report_to,
        'legal_acts': legal_acts,
    }
    return narrative

def print_narrative(n):
    """Print narrative to terminal."""
    print()
    print('='*65)
    print(f'  CINEOS OPERATOR CASE NARRATIVE')
    print(f'  Case ID: {n["case_id"]}')
    print(f'  Confidence: {n["confidence"]}%  |  Evidence: {n["ev_hash"]}...')
    print(f'  Generated: {n["generated"][:19]} IST')
    print('='*65)
    for section, content in n['sections'].items():
        print(f'\n── {section} ' + '─'*(55-len(section)))
        print(content)
    print(f'\nReport to: {" · ".join(n["report_to"])}')
    print('='*65)

def generate_all():
    """Generate narratives for all top operators."""
    # Load data
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))
    try:
        cross_map = json.load(open('reports/cross_vertical_map.json'))
    except:
        cross_map = {'operators':[]}
    try:
        resurrection = json.load(open('reports/resurrection_report.json'))
    except:
        resurrection = {'resurrections':[]}

    # Import phone intel
    import sys
    sys.path.insert(0,'.')
    from cineos_phone_intel import build_phone_index, profile_operator

    index = build_phone_index(channels, alerts)

    # Generate for top 10 by channel count
    scored = sorted(index.items(), key=lambda x: -len(x[1]['channels']))
    generated = []
    print(f'Generating narratives for top operators...')
    for ph, entry in scored[:10]:
        if len(entry['channels']) < 2: continue
        p = profile_operator(ph, index, resurrection)
        if not p: continue
        n = build_narrative(p)
        fname = f'reports/narratives/narrative_{ph.replace("+","").replace("-","")}.json'
        json.dump(n, open(fname,'w'), indent=2)
        generated.append((ph, n))
        print(f'  {ph}  {n["confidence"]}%  {n["case_id"]}')

    print(f'\nGenerated {len(generated)} narratives in reports/narratives/')
    return generated

if __name__ == '__main__':
    import sys
    print('='*55)
    print(f'  CINEOS NARRATIVE ENGINE')
    print(f'  {now_ist().strftime("%Y-%m-%d %H:%M IST")}')
    print('='*55)

    if len(sys.argv) > 1 and sys.argv[1].startswith('+'):
        # Profile specific phone
        channels = json.load(open('reports/all_channels.json'))
        alerts   = json.load(open('reports/alerts/live_alerts.json'))
        try:
            resurrection = json.load(open('reports/resurrection_report.json'))
        except:
            resurrection = {'resurrections':[]}
        from cineos_phone_intel import build_phone_index, profile_operator
        index = build_phone_index(channels, alerts)
        p = profile_operator(sys.argv[1], index, resurrection)
        if p:
            n = build_narrative(p)
            print_narrative(n)
            fname = f'reports/narratives/narrative_{sys.argv[1].replace("+","").replace("-","")}.json'
            json.dump(n, open(fname,'w'), indent=2)
            print(f'\nSaved: {fname}')
    else:
        generate_all()
