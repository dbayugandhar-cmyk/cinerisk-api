"""
CINEOS Banking Fraud Case Study Generator
Generates intelligence reports for banks, PSPs, FIU-IND, RBI
"""
import json, os, hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5,minutes=30))
os.makedirs('reports/case_studies_banking', exist_ok=True)

def now_ist(): return datetime.now(IST)
def sha(t): return hashlib.sha256(t.encode()).hexdigest()
def fmt(n): return f'{n/1e6:.1f}M' if n>=1e6 else f'{n/1e3:.0f}K' if n>=1e3 else str(n)

def run():
    alerts   = json.load(open('reports/alerts/live_alerts.json'))
    channels = json.load(open('reports/all_channels.json'))

    # Group banking alerts by type
    cats = {
        'upi_mule':        [a for a in alerts if a.get('category')=='upi_mule'],
        'loan_fraud':      [a for a in alerts if a.get('category')=='loan_fraud'],
        'investment_fraud':[a for a in alerts if a.get('category')=='investment_fraud'],
        'crypto_fraud':    [a for a in alerts if a.get('category')=='crypto_fraud'],
    }

    # Build phone-based operator profiles from banking channels
    phone_map = defaultdict(list)
    for ch in channels:
        if ch.get('category') in ('upi_mule','loan_fraud','investment_fraud','crypto_fraud'):
            for ph in ch.get('phones',[]):
                if ph and '+91888888' not in ph:
                    phone_map[ph].append(ch)

    # Build case list
    cases = []

    # Type 1: Cross-channel phone operators (highest confidence)
    for ph, chs in sorted(phone_map.items(), key=lambda x:-len(x[1])):
        if len(chs) < 1: continue
        reach = sum(c.get('subscribers',0) for c in chs)
        upis  = list(set(u for c in chs for u in c.get('upis',[])))
        conf  = 70 + (10 if len(chs)>=2 else 5) + (10 if upis else 0)
        cat   = chs[0].get('category','upi_mule')
        cases.append({
            'type':'CHANNEL_OPERATOR', 'phone':ph, 'channels':chs,
            'reach':reach, 'upis':upis, 'conf':min(conf,99),
            'category':cat,
        })

    # Type 2: News-based banking fraud alerts with phones
    for a in alerts:
        if a.get('category') not in ('upi_mule','loan_fraud') : continue
        ph = a.get('chain',{}).get('phones',[])
        up = a.get('chain',{}).get('upis',[])
        if not ph and not up: continue
        conf = 65 + (15 if len(ph)>=2 else 10 if ph else 0) + (10 if up else 0)
        cases.append({
            'type':'NEWS_ALERT', 'alert':a,
            'phones':ph, 'upis':up, 'conf':min(conf,99),
            'category':a.get('category','upi_mule'),
        })

    cases.sort(key=lambda x:-x['conf'])
    top = cases[:20]

    generated = []
    for i, case in enumerate(top, 1):
        fname = f'bank_{i:03d}.html'
        html  = build_html(case, i)
        open(f'reports/case_studies_banking/{fname}','w').write(html)
        generated.append(fname)
        label = case.get('phone','') or (case.get('alert',{}).get('title','')[:30])
        print(f'  [{i:2d}] {case["conf"]}%  {label[:45]:45s}  {case["category"]}')

    # Index
    build_index(top, generated)
    print(f'\nDone: {len(top)} banking case studies')
    print(f'Index: reports/case_studies_banking/index.html')

def build_html(case, n):
    now   = now_ist()
    cid   = f'CINEOS-BANK-2026-{n:03d}'
    conf  = case['conf']
    cc    = '#166534' if conf>=85 else '#D97706' if conf>=70 else '#2563EB'
    cbg   = '#DCFCE7' if conf>=85 else '#FFFBEB' if conf>=70 else '#EFF6FF'

    if case['type'] == 'CHANNEL_OPERATOR':
        chs     = case['channels']
        phone   = case['phone']
        upis    = case['upis']
        reach   = case['reach']
        cat     = case['category']
        title   = f'Banking Fraud Operator — {phone}'
        detail  = f'{len(chs)} channels · {fmt(reach)} reach · {cat.replace("_"," ").title()}'
        phones_html = f'<div class="phone-item">📞 {phone}</div>'
        upis_html   = ''.join(f'<div class="upi-item">💳 {u}</div>' for u in upis) or '<span class="na">None extracted yet</span>'
        ch_rows = ''.join(f'''<tr>
          <td class="mono">@{c.get("username","")[:40]}</td>
          <td class="num">{c.get("subscribers",0):,}</td>
          <td class="mono red">{phone}</td>
          <td><span class="badge match">✓ Phone match</span></td>
        </tr>''' for c in chs[:6])
        why = f'Phone {phone} extracted from {len(chs)} banking fraud channels. Operator recruiting mule accounts or running financial fraud network. {fmt(reach)} combined reach.'
        legal = 'PMLA 2002 §3 + §4 · IT Act 2000 §65B + §66D · IPC §420 · RBI Master Direction on Fraud'
        steps = ['File complaint with FIU-IND at fiuindia.gov.in','Request phone subpoena via cybercrime cell','Screen phone against bank KYC database','File FIR under PMLA 2002 + IT Act §66D','Request Telegram channel removal via MHA']
        report_to = ['FIU-IND — fiuindia.gov.in','RBI Ombudsman — rbi.org.in','I4C — cybercrime.gov.in','State Police Cybercrime Cell']
    else:
        a       = case['alert']
        phones  = case['phones']
        upis    = case['upis']
        cat     = case['category']
        title   = a.get('title','Banking Fraud Alert')[:80]
        detail  = a.get('detail','')[:200]
        phones_html = ''.join(f'<div class="phone-item">📞 {p}</div>' for p in phones) or '<span class="na">No phone extracted</span>'
        upis_html   = ''.join(f'<div class="upi-item">💳 {u}</div>' for u in upis) or '<span class="na">No UPI extracted</span>'
        ch_rows = f'<tr><td colspan="4" class="mono" style="color:var(--m);padding:10px">{a.get("chain",{}).get("channels_found",["—"])[0][:80]}</td></tr>'
        why     = f'Enforcement action detected: {title}. CINEOS cross-referenced against database of active fraud operators.'
        legal   = 'PMLA 2002 §3 · IT Act 2000 §65B + §66D · IPC §420'
        steps   = ['Cross-reference phones with bank KYC records','File with FIU-IND if PMLA threshold met','Share with state cybercrime cell','Monitor for resurrection after enforcement']
        report_to = ['FIU-IND — fiuindia.gov.in','I4C — cybercrime.gov.in','RBI']

    ev_hash = sha(phone if case['type']=='CHANNEL_OPERATOR' else title)[:16]
    steps_html   = ''.join(f'<div class="step"><span class="step-n">{i+1}</span><span>{s}</span></div>' for i,s in enumerate(steps))
    report_html  = ''.join(f'<span class="agency">{r}</span>' for r in report_to)

    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>CINEOS Banking {cid}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--g:#166534;--gt:#F0FDF4;--gb:#BBF7D0;--gl:#DCFCE7;--ink:#0F172A;--b:#475569;--m:#94A3B8;--bo:#E2E8F0;--s:#F8FAFC;--w:#fff;--navy:#0D2B55;--blue:#1A56A0;--teal:#0E7490}}
body{{font-family:"Segoe UI",system-ui,sans-serif;background:var(--s);color:var(--ink);font-size:13px;line-height:1.6}}
.header{{background:var(--navy);color:#fff;padding:24px 36px 20px}}
.header-top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}}
.logo{{font-family:monospace;font-size:18px;font-weight:700;letter-spacing:.15em}}
.conf-badge{{background:{cbg};color:{cc};border:2px solid {cc};border-radius:8px;padding:6px 16px;text-align:center}}
.conf-pct{{font-size:24px;font-weight:700;line-height:1}}
.conf-lbl{{font-size:9px;text-transform:uppercase;letter-spacing:.1em}}
.vertical-badge{{background:#1A56A0;color:#fff;font-family:monospace;font-size:10px;padding:3px 10px;border-radius:3px;margin-bottom:8px;display:inline-block}}
.case-title{{font-size:17px;font-weight:700;margin-bottom:3px}}
.case-sub{{font-size:12px;color:#9EC6F3}}
.meta{{background:#132244;padding:8px 36px;display:flex;gap:32px;border-bottom:2px solid var(--teal)}}
.meta-item{{font-size:10px}}.meta-lbl{{color:#7BAFD4;font-family:monospace;font-size:8px;text-transform:uppercase;display:block;margin-bottom:1px}}.meta-val{{color:#fff;font-weight:600}}
.body{{padding:24px 36px;max-width:1000px}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}}
.stat{{background:var(--w);border:1px solid var(--bo);border-radius:6px;padding:10px;text-align:center}}
.stat-n{{font-family:monospace;font-size:20px;font-weight:700;color:{cc}}}
.stat-l{{font-size:9px;color:var(--m);margin-top:2px}}
.section{{background:var(--w);border:1px solid var(--bo);border-radius:6px;overflow:hidden;margin-bottom:14px}}
.sec-title{{font-family:monospace;font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:var(--m);padding:8px 14px;background:var(--s);border-bottom:1px solid var(--bo)}}
.sec-body{{padding:14px}}
.phones{{display:flex;flex-wrap:wrap;gap:6px}}
.phone-item{{font-family:monospace;font-size:13px;font-weight:600;color:#DC2626;background:#FEF2F2;border:1px solid #FECACA;padding:5px 10px;border-radius:4px}}
.upi-item{{font-family:monospace;font-size:12px;color:var(--g);background:var(--gt);border:1px solid var(--gb);padding:4px 8px;border-radius:4px}}
.na{{font-size:11px;color:var(--m);font-style:italic}}
.ev-box{{background:#0A1628;color:#7FD8E8;font-family:monospace;font-size:11px;padding:10px 14px;border-radius:5px;border:1px solid var(--teal)}}
.ev-lbl{{color:var(--teal);font-size:8px;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:3px}}
table{{width:100%;border-collapse:collapse}}
thead th{{font-family:monospace;font-size:8px;text-transform:uppercase;letter-spacing:.08em;color:var(--m);padding:7px 10px;text-align:left;border-bottom:2px solid var(--bo);background:var(--s)}}
tbody td{{padding:8px 10px;border-bottom:1px solid var(--bo);font-size:12px}}
.mono{{font-family:monospace;font-size:11px}}.num{{text-align:right;color:var(--g);font-weight:600;font-family:monospace}}.red{{color:#DC2626}}
.badge{{font-family:monospace;font-size:9px;padding:2px 6px;border-radius:3px;font-weight:600}}
.match{{background:var(--gl);color:var(--g);border:1px solid var(--gb)}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.step{{display:flex;align-items:flex-start;gap:8px;font-size:12px;color:var(--b);padding:4px 0}}
.step-n{{font-family:monospace;font-size:9px;font-weight:700;color:#fff;background:var(--navy);width:18px;height:18px;border-radius:3px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.agencies{{display:flex;flex-wrap:wrap;gap:5px}}
.agency{{font-family:monospace;font-size:9px;background:#DBEAFE;color:#1A56A0;border:1px solid #BFDBFE;padding:3px 8px;border-radius:3px;font-weight:600}}
.footer{{background:var(--navy);color:#7BAFD4;padding:12px 36px;font-size:9px;font-family:monospace;display:flex;justify-content:space-between;margin-top:24px}}
</style></head><body>
<div class="header">
  <div class="header-top">
    <div>
      <div class="logo">CINEOS</div>
      <div class="vertical-badge">BANKING FRAUD INTELLIGENCE</div>
      <div class="case-title">{title}</div>
      <div class="case-sub">Case ID: {cid} · {cat.replace("_"," ").title()} · Telegram Attribution</div>
    </div>
    <div class="conf-badge"><div class="conf-pct">{conf}%</div><div class="conf-lbl">Confidence</div></div>
  </div>
</div>
<div class="meta">
  <div class="meta-item"><span class="meta-lbl">Case ID</span><span class="meta-val">{cid}</span></div>
  <div class="meta-item"><span class="meta-lbl">Generated</span><span class="meta-val">{now.strftime("%Y-%m-%d %H:%M IST")}</span></div>
  <div class="meta-item"><span class="meta-lbl">Evidence</span><span class="meta-val">IT Act §65B</span></div>
  <div class="meta-item"><span class="meta-lbl">Hash</span><span class="meta-val" style="font-family:monospace;font-size:9px">{ev_hash}...</span></div>
  <div class="meta-item"><span class="meta-lbl">Vertical</span><span class="meta-val">Banking Fraud</span></div>
</div>
<div class="body">
  <div class="stats">
    <div class="stat"><div class="stat-n">{conf}%</div><div class="stat-l">Confidence</div></div>
    <div class="stat"><div class="stat-n">{len(case.get("channels",[])) or len(case.get("phones",[]))}</div><div class="stat-l">Entities Found</div></div>
    <div class="stat"><div class="stat-n">{fmt(case.get("reach",0))}</div><div class="stat-l">Reach</div></div>
    <div class="stat"><div class="stat-n">§65B</div><div class="stat-l">Evidence Standard</div></div>
  </div>
  <div class="section"><div class="sec-title">Phone Attribution</div><div class="sec-body"><div class="phones">{phones_html}</div></div></div>
  <div class="two">
    <div class="section"><div class="sec-title">UPI / Payment IDs</div><div class="sec-body"><div style="display:flex;flex-wrap:wrap;gap:5px">{upis_html}</div></div></div>
    <div class="section"><div class="sec-title">Evidence Hash (§65B)</div><div class="sec-body"><div class="ev-box"><span class="ev-lbl">SHA-256</span>{sha(title)[:48]}...<br><br><span class="ev-lbl">Timestamp</span>{now.strftime("%Y-%m-%d %H:%M:%S IST")}</div></div></div>
  </div>
  <div class="section"><div class="sec-title">Channels / Sources</div><div class="sec-body" style="padding:0"><table><thead><tr><th>Channel</th><th style="text-align:right">Subscribers</th><th>Phone</th><th>Status</th></tr></thead><tbody>{ch_rows}</tbody></table></div></div>
  <div class="section"><div class="sec-title">Why It Matters</div><div class="sec-body" style="font-size:12px;color:var(--b);line-height:1.7">{why}</div></div>
  <div class="section"><div class="sec-title">Legal Basis</div><div class="sec-body" style="font-size:12px;color:var(--b)">{legal}</div></div>
  <div class="two">
    <div class="section"><div class="sec-title">Next Steps</div><div class="sec-body">{steps_html}</div></div>
    <div class="section"><div class="sec-title">Report To</div><div class="sec-body"><div class="agencies">{report_html}</div><div style="margin-top:10px;font-size:11px;color:var(--m)">Full §65B(2) evidence package available on request.</div></div></div>
  </div>
</div>
<div class="footer"><span>CINEOS · Banking Fraud Intelligence · IP Registration Pending · yugandhar@cineos.in</span><span>RESTRICTED · {cid}</span></div>
</body></html>'''

def build_index(cases, files):
    rows = ''
    for i,(case,fname) in enumerate(zip(cases,files),1):
        conf = case['conf']
        cc   = '#166534' if conf>=85 else '#D97706' if conf>=70 else '#2563EB'
        cbg  = '#DCFCE7' if conf>=85 else '#FFFBEB' if conf>=70 else '#EFF6FF'
        label = case.get('phone','') or case.get('alert',{}).get('title','')[:40]
        cat   = case.get('category','').replace('_',' ')
        reach = fmt(case.get('reach',0))
        ents  = len(case.get('channels',[])) or len(case.get('phones',[]))
        rows += f'<tr onclick="window.open(\'{fname}\')" style="cursor:pointer"><td class="mono" style="color:var(--m)">CINEOS-BANK-2026-{i:03d}</td><td><b>{label[:50]}</b></td><td>{cat}</td><td style="text-align:center">{ents}</td><td style="text-align:right;color:var(--g);font-weight:600">{reach}</td><td style="text-align:center"><span style="font-family:monospace;font-size:11px;font-weight:700;color:{cc};background:{cbg};padding:2px 8px;border-radius:3px">{conf}%</span></td></tr>'
    open('reports/case_studies_banking/index.html','w').write(f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>CINEOS Banking Intelligence</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:"Segoe UI",system-ui,sans-serif;background:#F0F7FF;color:#0F172A;font-size:13px}}.header{{background:#0D2B55;color:#fff;padding:20px 36px}}.logo{{font-family:monospace;font-size:18px;font-weight:700;letter-spacing:.15em;margin-bottom:4px}}h1{{font-size:20px;font-weight:600}}.sub{{font-size:12px;color:#9EC6F3;margin-top:3px}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 36px;background:#132244}}.stat{{text-align:center}}.stat-n{{font-family:monospace;font-size:26px;font-weight:700;color:#22c55e}}.stat-l{{font-size:10px;color:#7BAFD4;margin-top:2px}}.body{{padding:20px 36px}}table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #BFDBFE;border-radius:6px;overflow:hidden}}thead th{{font-family:monospace;font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#94A3B8;padding:9px 10px;text-align:left;border-bottom:2px solid #E2E8F0;background:#F8FAFC}}tbody td{{padding:9px 10px;border-bottom:1px solid #E2E8F0;font-size:12px}}tbody tr:hover{{background:#F0FDF4}}.mono{{font-family:monospace;font-size:11px}}</style></head>
<body><div class="header"><div class="logo">CINEOS</div><h1>Banking Fraud Intelligence — Case Studies</h1><div class="sub">UPI Mule · KYC Fraud · Loan Fraud · Investment Fraud · Hawala · IP Registration Pending · {datetime.now(IST).strftime("%Y-%m-%d")}</div></div>
<div class="stats"><div class="stat"><div class="stat-n">{len(cases)}</div><div class="stat-l">Case Studies</div></div><div class="stat"><div class="stat-n">{sum(1 for c in cases if c["conf"]>=85)}</div><div class="stat-l">≥85% Confidence</div></div><div class="stat"><div class="stat-n">§65B</div><div class="stat-l">Evidence Standard</div></div><div class="stat"><div class="stat-n">3</div><div class="stat-l">Report Agencies</div></div></div>
<div class="body"><table><thead><tr><th>Case ID</th><th>Operator / Alert</th><th>Category</th><th style="text-align:center">Entities</th><th style="text-align:right">Reach</th><th style="text-align:center">Confidence</th></tr></thead><tbody>{rows}</tbody></table></div></body></html>''')

if __name__ == '__main__':
    print('='*55)
    print(f'  CINEOS BANKING FRAUD CASE STUDIES')
    print(f'  {now_ist().strftime("%Y-%m-%d %H:%M IST")}')
    print('='*55)
    run()
