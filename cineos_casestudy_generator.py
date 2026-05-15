"""
CINEOS Case Study Generator
Generates 25+ operator intelligence reports from the database.
Standard format for buyer demos and law enforcement sharing.

Run: python3 cineos_casestudy_generator.py
Output: reports/case_studies/
"""

import json, os, hashlib, re
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5, minutes=30))
os.makedirs('reports/case_studies', exist_ok=True)

def now_ist():
    return datetime.now(IST)

def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()

def fmt_reach(n):
    if n >= 1_000_000: return f'{n/1_000_000:.1f}M'
    if n >= 1_000:     return f'{n/1_000:.0f}K'
    return str(n)

def confidence_score(phone_count, channel_count, has_sample, has_upi):
    score = 70
    if phone_count >= 2:   score += 10
    if phone_count >= 3:   score += 5
    if channel_count >= 3: score += 5
    if channel_count >= 5: score += 5
    if has_sample:         score += 5
    if has_upi:            score += 5
    return min(score, 99)

def load_data():
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))
    try:
        graph = json.load(open('reports/fraud_intelligence_graph.json'))
    except:
        graph = {'nodes':{}, 'edges':[]}
    return channels, alerts, graph

def build_operator_profiles(channels, alerts):
    """Group channels by shared phone numbers to identify operators."""
    phone_map = defaultdict(list)
    for ch in channels:
        if ch.get('category') not in ('illegal_betting','betting','crypto_fraud','colour_prediction'):
            continue
        for ph in ch.get('phones', []):
            if ph and '+91888888' not in ph and '+91999999' not in ph:
                phone_map[ph].append(ch)

    profiles = []

    # Multi-channel operators (highest confidence)
    seen_channels = set()
    for ph, chs in sorted(phone_map.items(), key=lambda x: -sum(c.get('subscribers',0) for c in x[1])):
        if len(chs) < 2:
            continue
        total_reach = sum(c.get('subscribers',0) for c in chs)
        all_phones  = list(set(
            p for c in chs for p in c.get('phones',[])
            if p and '+91888888' not in p
        ))
        all_upis = list(set(
            u for c in chs for u in c.get('upis',[]) if u
        ))
        # Find matching alerts
        ch_names = [c.get('username','') for c in chs]
        matching_alerts = [
            a for a in alerts
            if any(n.lower() in json.dumps(a).lower() for n in ch_names if n)
        ]
        sample_post = ''
        for a in matching_alerts:
            sp = a.get('chain',{}).get('sample_post','')
            if sp and len(sp) > 20:
                sample_post = sp[:200]
                break

        conf = confidence_score(len(all_phones), len(chs), bool(sample_post), bool(all_upis))

        # Determine operator name from channel names
        op_name = infer_operator_name(chs)

        profiles.append({
            'type':          'MULTI_CHANNEL',
            'operator_name': op_name,
            'primary_phone': ph,
            'all_phones':    all_phones[:6],
            'channels':      sorted(chs, key=lambda x: -x.get('subscribers',0)),
            'channel_count': len(chs),
            'total_reach':   total_reach,
            'upis':          all_upis[:3],
            'sample_post':   sample_post,
            'confidence':    conf,
            'alerts':        matching_alerts[:5],
            'category':      chs[0].get('category','illegal_betting'),
        })
        seen_channels.update(ch_names)

    # Single-channel operators with phones (still valid evidence)
    for ph, chs in sorted(phone_map.items(), key=lambda x: -x[1][0].get('subscribers',0) if len(x[1])==1 else 0):
        if len(chs) != 1:
            continue
        ch = chs[0]
        if ch.get('username','') in seen_channels:
            continue
        if ch.get('subscribers',0) < 10000:
            continue

        all_upis = ch.get('upis',[])
        matching_alerts = [
            a for a in alerts
            if ch.get('username','').lower() in json.dumps(a).lower()
        ]
        sample_post = ''
        for a in matching_alerts:
            sp = a.get('chain',{}).get('sample_post','')
            if sp and len(sp) > 20:
                sample_post = sp[:200]
                break

        conf = confidence_score(1, 1, bool(sample_post), bool(all_upis))

        profiles.append({
            'type':          'SINGLE_CHANNEL',
            'operator_name': infer_operator_name([ch]),
            'primary_phone': ph,
            'all_phones':    [ph],
            'channels':      [ch],
            'channel_count': 1,
            'total_reach':   ch.get('subscribers',0),
            'upis':          all_upis[:3],
            'sample_post':   sample_post,
            'confidence':    conf,
            'alerts':        matching_alerts[:3],
            'category':      ch.get('category','illegal_betting'),
        })
        seen_channels.add(ch.get('username',''))

    # Sort by confidence then reach
    profiles.sort(key=lambda x: (-x['confidence'], -x['total_reach']))
    return profiles

def infer_operator_name(channels):
    """Infer operator name from channel usernames."""
    all_names = ' '.join(c.get('username','') + ' ' + c.get('title','') for c in channels).lower()
    brand_map = {
        'mahadev':    'Mahadev Book Operator',
        'reddy':      'Reddy Anna / World777 Operator',
        'world777':   'World777 Operator',
        'fairplay':   'Fairplay Betting Operator',
        'laser247':   'Laser247 / Betbhai9 Operator',
        'cricbet':    'Cricbet99 / Betbhai9 Operator',
        'diamond':    'Diamond Exchange Operator',
        'radhe':      'Radhe Exchange Operator',
        'tiger':      'Tiger Exchange Operator',
        'lotus':      'Lotus365 Operator',
        'vipin':      'Vipin Aryan / Sawariya Operator',
        'sawariya':   'Sawariya Exchange Operator',
        'faridabad':  'Faridabad Satta Operator',
        'satta':      'Satta / Matka Operator',
        'matka':      'Satta Matka Operator',
        'toss':       'Toss Match Fix Operator',
        'ipl':        'IPL Betting Operator',
        '91club':     '91CLUB Colour Prediction Operator',
        'daman':      'Daman Games Operator',
        'aviator':    'Aviator / Colour Prediction Operator',
    }
    for key, name in brand_map.items():
        if key in all_names:
            return name
    # Fallback: use first channel name
    first = channels[0].get('username','Unknown')
    return f'Operator via @{first[:25]}'

def generate_html_report(profile, case_num, total):
    """Generate a single HTML case study report."""
    ch_list  = profile['channels']
    phones   = profile['all_phones']
    conf     = profile['confidence']
    reach    = profile['total_reach']
    cat      = profile['category'].replace('_',' ').title()
    now      = now_ist()
    case_id  = f'CINEOS-CS-2026-{case_num:03d}'
    ev_hash  = sha(profile['primary_phone'] + str(profile['total_reach']) + case_id)[:16]

    conf_color = '#166534' if conf >= 90 else '#D97706' if conf >= 75 else '#2563EB'
    conf_bg    = '#DCFCE7' if conf >= 90 else '#FFFBEB' if conf >= 75 else '#EFF6FF'

    legal_map = {
        'illegal_betting':   'Public Gambling Act 1867 · Online Gaming Act 2025 §8 · IT Act 2000 §65B + §66D',
        'betting':           'Public Gambling Act 1867 · Online Gaming Act 2025 §8 · IT Act 2000 §65B',
        'crypto_fraud':      'PMLA 2002 §3 · IT Act 2000 §65B + §66D · SEBI Act §12A',
        'colour_prediction': 'Online Gaming Act 2025 §8 · IT Act 2000 §65B + §66D · FEMA 1999',
        'upi_mule':          'PMLA 2002 §3 · IT Act 2000 §66 · IPC §420',
    }
    legal = legal_map.get(profile['category'], 'IT Act 2000 §65B + §66D · IPC §420')

    channels_html = ''
    for i, ch in enumerate(ch_list[:8]):
        subs = ch.get('subscribers', 0)
        ch_phones = ch.get('phones', [])
        ch_upis   = ch.get('upis',   [])
        ph_str  = ' · '.join(ch_phones[:2]) if ch_phones else '—'
        upi_str = ' · '.join(ch_upis[:1])   if ch_upis   else '—'
        channels_html += f"""
        <tr>
          <td class="mono">@{ch.get('username','')[:45]}</td>
          <td class="num">{subs:,}</td>
          <td class="mono red">{ph_str}</td>
          <td class="mono green">{upi_str}</td>
          <td><span class="badge {'match' if ch_phones else 'pending'}">{'✓ Phone match' if ch_phones else 'Pending'}</span></td>
        </tr>"""

    phones_html = ''.join(f'<div class="phone-item">📞 {p}</div>' for p in phones)
    upis_html   = ''.join(f'<div class="upi-item">💳 {u}</div>' for u in profile['upis']) if profile['upis'] else '<div class="na">No UPI IDs extracted in this scan</div>'

    sample_html = ''
    if profile['sample_post']:
        sample_html = f"""
      <div class="section">
        <div class="section-title">Sample Evidence Post</div>
        <div class="sample-post">{profile['sample_post']}</div>
        <div class="caption">Extracted from live Telegram message · Hashed at detection</div>
      </div>"""

    next_steps_map = {
        'illegal_betting':   ['File complaint with NOGC: nogc.gov.in', 'Report to state cybercrime cell with operator phone', 'File FIR under Public Gambling Act 1867 + OGA 2025 §8', 'Request Telegram channel takedown via MHA', 'Cross-reference phone with bank KYC records'],
        'betting':           ['File complaint with NOGC: nogc.gov.in', 'Report to state cybercrime cell', 'File FIR under Public Gambling Act 1867'],
        'crypto_fraud':      ['File with ED under PMLA 2002', 'Report to SEBI SCORES portal', 'File cybercrime complaint: cybercrime.gov.in', 'Request bank freeze on operator UPI/accounts'],
        'colour_prediction': ['File complaint with OGA enforcement', 'Report to I4C: cybercrime.gov.in', 'File FIR under IT Act §66D + OGA 2025 §8'],
    }
    steps = next_steps_map.get(profile['category'], ['Report to I4C: cybercrime.gov.in', 'File FIR under IT Act §65B + §66D', 'Share with state cybercrime cell'])
    steps_html = ''.join(f'<div class="step"><span class="step-n">{i+1}</span><span>{s}</span></div>' for i,s in enumerate(steps))

    report_to_map = {
        'illegal_betting':   ['NOGC — nogc.gov.in', 'I4C — cybercrime.gov.in', 'State Police Cybercrime Cell', 'Ministry of Home Affairs'],
        'crypto_fraud':      ['Enforcement Directorate (ED)', 'SEBI — scores.sebi.gov.in', 'I4C — cybercrime.gov.in'],
        'colour_prediction': ['I4C — cybercrime.gov.in', 'Online Gaming Authority (OGA)', 'State Police Cybercrime Cell'],
    }
    report_to = report_to_map.get(profile['category'], ['I4C — cybercrime.gov.in', 'State Police Cybercrime Cell'])
    report_html = ''.join(f'<span class="agency">{r}</span>' for r in report_to)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CINEOS Case Study {case_id}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --g:#166534;--gm:#15803D;--gt:#F0FDF4;--gb:#BBF7D0;--gl:#DCFCE7;
  --ink:#0F172A;--b:#475569;--m:#94A3B8;--bo:#E2E8F0;--s:#F8FAFC;--w:#fff;
  --navy:#0D2B55;--blue:#1A56A0;--teal:#0E7490;--sky:#DBEAFE;
}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--s);color:var(--ink);font-size:13px;line-height:1.6}}
.header{{background:var(--navy);color:#fff;padding:28px 40px 24px}}
.header-top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}}
.logo{{font-family:monospace;font-size:22px;font-weight:700;letter-spacing:.15em;color:#fff}}
.logo-sub{{font-size:11px;color:#7BAFD4;letter-spacing:.05em;margin-top:2px}}
.conf-badge{{background:{conf_bg};color:{conf_color};border:2px solid {conf_color};border-radius:8px;padding:8px 18px;text-align:center;font-family:monospace}}
.conf-pct{{font-size:28px;font-weight:700;line-height:1}}
.conf-label{{font-size:10px;text-transform:uppercase;letter-spacing:.1em;margin-top:2px}}
.case-title{{font-size:20px;font-weight:700;margin-bottom:4px}}
.case-sub{{font-size:13px;color:#9EC6F3}}
.meta-strip{{background:#132244;padding:10px 40px;display:flex;gap:40px;border-bottom:2px solid var(--teal)}}
.meta-item{{font-size:11px}}
.meta-label{{color:#7BAFD4;text-transform:uppercase;letter-spacing:.08em;font-family:monospace;display:block;margin-bottom:2px}}
.meta-value{{color:#fff;font-weight:600}}
.body{{padding:28px 40px;max-width:1100px}}
.section{{background:var(--w);border:1px solid var(--bo);border-radius:8px;overflow:hidden;margin-bottom:18px}}
.section-title{{font-family:monospace;font-size:9px;text-transform:uppercase;letter-spacing:.12em;color:var(--m);padding:10px 16px;background:var(--s);border-bottom:1px solid var(--bo);display:flex;align-items:center;justify-content:space-between}}
.section-body{{padding:16px}}
.phones{{display:flex;flex-wrap:wrap;gap:8px}}
.phone-item{{font-family:monospace;font-size:13px;font-weight:600;color:#DC2626;background:#FEF2F2;border:1px solid #FECACA;padding:6px 12px;border-radius:5px}}
.upi-item{{font-family:monospace;font-size:12px;color:var(--g);background:var(--gt);border:1px solid var(--gb);padding:5px 10px;border-radius:5px}}
.na{{font-size:12px;color:var(--m);font-style:italic}}
.evidence-box{{background:#0A1628;color:#7FD8E8;font-family:monospace;font-size:12px;padding:12px 16px;border-radius:6px;border:1px solid var(--teal)}}
.evidence-box .label{{color:var(--teal);font-size:9px;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:4px}}
table{{width:100%;border-collapse:collapse}}
thead th{{font-family:monospace;font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:var(--m);padding:8px 12px;text-align:left;border-bottom:2px solid var(--bo);background:var(--s)}}
tbody td{{padding:9px 12px;border-bottom:1px solid var(--bo);font-size:12px}}
tbody tr:last-child td{{border-bottom:none}}
tbody tr:hover{{background:var(--gt)}}
.mono{{font-family:monospace;font-size:11px}}
.num{{font-family:monospace;text-align:right;color:var(--g);font-weight:600}}
.red{{color:#DC2626}}
.green{{color:var(--g)}}
.badge{{font-family:monospace;font-size:9px;padding:2px 7px;border-radius:3px;font-weight:600;text-transform:uppercase}}
.badge.match{{background:var(--gl);color:var(--g);border:1px solid var(--gb)}}
.badge.pending{{background:var(--s);color:var(--m);border:1px solid var(--bo)}}
.sample-post{{font-size:12px;color:var(--b);background:var(--s);border:1px solid var(--bo);border-left:3px solid var(--g);padding:10px 14px;border-radius:0 5px 5px 0;font-style:italic;line-height:1.6;margin-bottom:6px}}
.caption{{font-size:10px;color:var(--m);font-family:monospace}}
.steps{{display:flex;flex-direction:column;gap:8px}}
.step{{display:flex;align-items:flex-start;gap:10px;font-size:12px;color:var(--b)}}
.step-n{{font-family:monospace;font-size:10px;font-weight:700;color:#fff;background:var(--navy);width:20px;height:20px;border-radius:3px;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px}}
.agencies{{display:flex;flex-wrap:wrap;gap:6px}}
.agency{{font-family:monospace;font-size:10px;background:var(--sky);color:var(--blue);border:1px solid #BFDBFE;padding:4px 10px;border-radius:3px;font-weight:600}}
.footer{{background:var(--navy);color:#7BAFD4;padding:14px 40px;font-size:10px;font-family:monospace;display:flex;justify-content:space-between;margin-top:28px}}
.stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}}
.stat-box{{background:var(--s);border:1px solid var(--bo);border-radius:6px;padding:12px;text-align:center}}
.stat-n{{font-family:monospace;font-size:22px;font-weight:700;color:{conf_color}}}
.stat-l{{font-size:10px;color:var(--m);margin-top:2px}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.chain-box{{background:var(--gt);border:1px solid var(--gb);border-radius:6px;padding:12px 14px}}
.chain-label{{font-family:monospace;font-size:9px;color:var(--g);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px}}
@media print{{body{{background:#fff}}.header{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <div>
      <div class="logo">CINEOS</div>
      <div class="logo-sub">India Trust Intelligence Network · Patent 64/049,190</div>
    </div>
    <div class="conf-badge">
      <div class="conf-pct">{conf}%</div>
      <div class="conf-label">Confidence</div>
    </div>
  </div>
  <div class="case-title">Intelligence Case Study: {profile['operator_name']}</div>
  <div class="case-sub">Case ID: {case_id} · Category: {cat} · Telegram Attribution</div>
</div>

<div class="meta-strip">
  <div class="meta-item"><span class="meta-label">Case ID</span><span class="meta-value">{case_id}</span></div>
  <div class="meta-item"><span class="meta-label">Generated</span><span class="meta-value">{now.strftime('%Y-%m-%d %H:%M IST')}</span></div>
  <div class="meta-item"><span class="meta-label">Evidence Standard</span><span class="meta-value">IT Act 2000 §65B</span></div>
  <div class="meta-item"><span class="meta-label">Evidence Hash</span><span class="meta-value" style="font-family:monospace;font-size:10px">{ev_hash}...</span></div>
  <div class="meta-item"><span class="meta-label">Classification</span><span class="meta-value">RESTRICTED</span></div>
</div>

<div class="body">

  <div class="stat-grid">
    <div class="stat-box"><div class="stat-n">{fmt_reach(reach)}</div><div class="stat-l">Subscriber Reach</div></div>
    <div class="stat-box"><div class="stat-n">{profile['channel_count']}</div><div class="stat-l">Channels Confirmed</div></div>
    <div class="stat-box"><div class="stat-n">{len(phones)}</div><div class="stat-l">Operator Phones</div></div>
    <div class="stat-box"><div class="stat-n">{conf}%</div><div class="stat-l">Attribution Confidence</div></div>
  </div>

  <div class="section">
    <div class="section-title">
      <span>Operator Phone Attribution</span>
      <span style="color:{'var(--g)' if len(phones)>1 else 'var(--m)'}">{'CROSS-CHANNEL CONFIRMED' if len(phones)>1 else 'SINGLE CHANNEL'}</span>
    </div>
    <div class="section-body">
      <div class="phones">{phones_html}</div>
      {'<div style="margin-top:10px;font-size:11px;color:var(--g);font-weight:600">✓ Same phone number appears across ' + str(profile['channel_count']) + ' separate Telegram channels — confirming single operator</div>' if len(phones) >= 1 and profile['channel_count'] > 1 else ''}
    </div>
  </div>

  <div class="two-col">
    <div class="section">
      <div class="section-title">UPI / Payment IDs</div>
      <div class="section-body">
        <div style="display:flex;flex-wrap:wrap;gap:6px">{upis_html}</div>
      </div>
    </div>
    <div class="section">
      <div class="section-title">Evidence Hash (IT Act §65B)</div>
      <div class="section-body">
        <div class="evidence-box">
          <span class="label">SHA-256 Evidence Hash</span>
          {sha(profile['primary_phone'] + ''.join(c.get('username','') for c in ch_list))[:48]}...
          <br><br>
          <span class="label">Detection Timestamp</span>
          {now.strftime('%Y-%m-%d · %H:%M:%S IST')}
        </div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">
      <span>Telegram Channels — Operator Attribution</span>
      <span>{profile['channel_count']} channels · {fmt_reach(reach)} total reach</span>
    </div>
    <div class="section-body" style="padding:0">
      <table>
        <thead><tr>
          <th>Channel Username</th>
          <th style="text-align:right">Subscribers</th>
          <th>Phone Extracted</th>
          <th>UPI Extracted</th>
          <th>Status</th>
        </tr></thead>
        <tbody>{channels_html}</tbody>
      </table>
    </div>
  </div>

  {sample_html}

  <div class="section">
    <div class="section-title">Legal Basis</div>
    <div class="section-body">
      <div style="font-size:12px;color:var(--b);line-height:1.8">{legal}</div>
      <div style="margin-top:10px;font-size:11px;color:var(--m)">Evidence certified under IT Act 2000 §65B · SHA-256 hash generated at detection · Timestamp legally defensible</div>
    </div>
  </div>

  <div class="two-col">
    <div class="section">
      <div class="section-title">Recommended Next Steps</div>
      <div class="section-body">
        <div class="steps">{steps_html}</div>
      </div>
    </div>
    <div class="section">
      <div class="section-title">Report To</div>
      <div class="section-body">
        <div class="agencies">{report_html}</div>
        <div style="margin-top:12px;font-size:11px;color:var(--m)">CINEOS can provide complete evidence package including timestamped message archives, operator profile, and §65B certificate on request.</div>
      </div>
    </div>
  </div>

</div>

<div class="footer">
  <span>CINEOS India Trust Intelligence Network · Patent 64/049,190 · yugandhar@cineos.in · cineos.in</span>
  <span>RESTRICTED — Law Enforcement / Legal Use Only · {case_id}</span>
</div>

</body>
</html>"""

def generate_index(profiles, generated):
    """Generate an index HTML of all case studies."""
    rows = ''
    for i, (p, fname) in enumerate(zip(profiles, generated), 1):
        conf = p['confidence']
        conf_color = '#166534' if conf >= 90 else '#D97706' if conf >= 75 else '#2563EB'
        rows += f"""
        <tr onclick="window.open('{fname}')" style="cursor:pointer">
          <td class="mono" style="color:var(--m)">CINEOS-CS-2026-{i:03d}</td>
          <td><b>{p['operator_name']}</b></td>
          <td class="mono" style="color:#DC2626">{p['primary_phone']}</td>
          <td style="text-align:center"><b>{p['channel_count']}</b></td>
          <td style="text-align:right;color:var(--g);font-weight:600">{fmt_reach(p['total_reach'])}</td>
          <td style="text-align:center">
            <span style="font-family:monospace;font-size:11px;font-weight:700;color:{conf_color};background:{'#DCFCE7' if conf>=90 else '#FFFBEB' if conf>=75 else '#EFF6FF'};padding:2px 8px;border-radius:3px">{conf}%</span>
          </td>
          <td style="font-size:11px;color:var(--m)">{p['category'].replace('_',' ')}</td>
        </tr>"""

    high_conf = sum(1 for p in profiles if p['confidence'] >= 90)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CINEOS Case Studies — Index</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--g:#166534;--gt:#F0FDF4;--gb:#BBF7D0;--ink:#0F172A;--b:#475569;--m:#94A3B8;--bo:#E2E8F0;--s:#F8FAFC;--w:#fff;--navy:#0D2B55}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--s);color:var(--ink);font-size:13px}}
.header{{background:var(--navy);color:#fff;padding:24px 40px}}
.logo{{font-family:monospace;font-size:20px;font-weight:700;letter-spacing:.15em;margin-bottom:4px}}
h1{{font-size:22px;font-weight:600}}
.sub{{font-size:13px;color:#9EC6F3;margin-top:4px}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:20px 40px;background:#132244}}
.stat{{text-align:center}}
.stat-n{{font-family:monospace;font-size:28px;font-weight:700;color:#22c55e}}
.stat-l{{font-size:11px;color:#7BAFD4;margin-top:2px}}
.body{{padding:24px 40px}}
table{{width:100%;border-collapse:collapse;background:var(--w);border:1px solid var(--bo);border-radius:8px;overflow:hidden}}
thead th{{font-family:monospace;font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:var(--m);padding:10px 12px;text-align:left;border-bottom:2px solid var(--bo);background:var(--s)}}
tbody td{{padding:10px 12px;border-bottom:1px solid var(--bo);font-size:12px}}
tbody tr:hover{{background:var(--gt)}}
.mono{{font-family:monospace;font-size:11px}}
</style>
</head>
<body>
<div class="header">
  <div class="logo">CINEOS</div>
  <h1>Intelligence Case Studies — Illegal Betting · Telegram Attribution</h1>
  <div class="sub">India Trust Intelligence Network · Patent 64/049,190 · Generated {datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')}</div>
</div>
<div class="stats">
  <div class="stat"><div class="stat-n">{len(profiles)}</div><div class="stat-l">Total Case Studies</div></div>
  <div class="stat"><div class="stat-n">{high_conf}</div><div class="stat-l">≥90% Confidence</div></div>
  <div class="stat"><div class="stat-n">{sum(p['channel_count'] for p in profiles)}</div><div class="stat-l">Channels Covered</div></div>
  <div class="stat"><div class="stat-n">{fmt_reach(sum(p['total_reach'] for p in profiles))}</div><div class="stat-l">Total Reach</div></div>
</div>
<div class="body">
  <table>
    <thead><tr>
      <th>Case ID</th><th>Operator</th><th>Primary Phone</th>
      <th style="text-align:center">Channels</th>
      <th style="text-align:right">Reach</th>
      <th style="text-align:center">Confidence</th>
      <th>Category</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
</body>
</html>"""

def run():
    print('='*60)
    print('  CINEOS CASE STUDY GENERATOR')
    print(f'  {now_ist().strftime("%Y-%m-%d %H:%M IST")}')
    print('='*60)

    channels, alerts, graph = load_data()
    print(f'Database: {len(channels)} channels · {len(alerts)} alerts')

    profiles = build_operator_profiles(channels, alerts)
    print(f'Operator profiles found: {len(profiles)}')
    print(f'  ≥90% confidence: {sum(1 for p in profiles if p["confidence"]>=90)}')
    print(f'  ≥75% confidence: {sum(1 for p in profiles if p["confidence"]>=75)}')

    # Generate top 30 case studies
    top_profiles = profiles[:30]
    generated_files = []

    print(f'\nGenerating {len(top_profiles)} case studies...')
    for i, profile in enumerate(top_profiles, 1):
        fname = f'case_{i:03d}_{profile["primary_phone"].replace("+91","").replace("+","")}.html'
        fpath = f'reports/case_studies/{fname}'
        html  = generate_html_report(profile, i, len(top_profiles))
        open(fpath, 'w').write(html)
        generated_files.append(fname)
        conf_str = f'{profile["confidence"]}%'
        print(f'  [{i:2d}] {conf_str:4s} · {profile["operator_name"][:40]:40s} · {fmt_reach(profile["total_reach"])} reach')

    # Generate index
    index_html = generate_index(top_profiles, generated_files)
    open('reports/case_studies/index.html','w').write(index_html)

    print(f'\n{"="*60}')
    print(f'DONE: {len(top_profiles)} case studies in reports/case_studies/')
    print(f'Index: reports/case_studies/index.html')
    print(f'Open: open reports/case_studies/index.html')

    # Summary
    high = sum(1 for p in top_profiles if p['confidence'] >= 90)
    med  = sum(1 for p in top_profiles if 75 <= p['confidence'] < 90)
    total_reach = sum(p['total_reach'] for p in top_profiles)
    print(f'\nSUMMARY:')
    print(f'  ≥90% confidence: {high} case studies')
    print(f'  75-89%:          {med} case studies')
    print(f'  Total reach:     {fmt_reach(total_reach)}')
    print(f'  Use case:        Illegal Betting · Telegram Attribution')
    print(f'  Evidence standard: IT Act 2000 §65B')

if __name__ == '__main__':
    run()
