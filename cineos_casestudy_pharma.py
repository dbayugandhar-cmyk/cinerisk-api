"""
CINEOS Counterfeit Pharma Case Study Generator
For: CDSCO, pharma brands, state drug controllers, DEA-India
Run: python3 cineos_casestudy_pharma.py
"""
import json, os, hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5,minutes=30))
os.makedirs('reports/case_studies_pharma', exist_ok=True)

def now_ist(): return datetime.now(IST)
def sha(t): return hashlib.sha256(t.encode()).hexdigest()

DRUG_BRANDS = {
    'ozempic':    'Ozempic (Semaglutide) — GLP-1 weight loss',
    'semaglutide':'Semaglutide — GLP-1 weight loss injection',
    'mounjaro':   'Mounjaro (Tirzepatide) — weight loss injection',
    'tirzepatide':'Tirzepatide — weight loss injection',
    'viagra':     'Viagra (Sildenafil) — sexual enhancement',
    'sildenafil': 'Sildenafil — sexual enhancement',
    'cialis':     'Cialis (Tadalafil) — sexual enhancement',
    'tadalafil':  'Tadalafil — sexual enhancement',
    'kamagra':    'Kamagra — unregistered sildenafil analog',
    'tramadol':   'Tramadol — opioid painkiller',
    'codeine':    'Codeine — controlled opioid',
    'alprazolam': 'Alprazolam (Xanax) — Schedule H1 benzodiazepine',
    'xanax':      'Xanax (Alprazolam) — Schedule H1 controlled',
    'steroid':    'Anabolic steroids — Schedule H',
    'hgh':        'HGH — Human Growth Hormone',
    'insulin':    'Insulin — unregulated supply chain risk',
    'cancer':     'Unproven cancer treatment claim',
    'tumor':      'Unproven cancer/tumor treatment',
    'diabetes':   'Unproven diabetes cure claim',
}

SEVERITY_MAP = {
    'tramadol':'critical', 'codeine':'critical',
    'alprazolam':'critical', 'xanax':'critical',
    'ozempic':'high', 'mounjaro':'high',
    'semaglutide':'high', 'tirzepatide':'high',
    'steroid':'high', 'hgh':'high',
    'viagra':'high', 'sildenafil':'high',
    'cialis':'high', 'tadalafil':'high', 'kamagra':'high',
    'cancer':'high', 'tumor':'high',
}

DRUG_RISK = {
    'tramadol':   'SCHEDULE H — Opioid · High addiction risk · Fatal overdose possible',
    'codeine':    'SCHEDULE H — Controlled opioid · Banned OTC in India · NDPS Act',
    'alprazolam': 'SCHEDULE H1 — Psychotropic · Prescription mandatory · Dependency risk',
    'xanax':      'SCHEDULE H1 — Psychotropic · Prescription mandatory · Dependency risk',
    'ozempic':    'Prescription-only GLP-1 · Counterfeit risk: wrong dosage + contamination',
    'mounjaro':   'Prescription-only · Not yet approved in India · High counterfeit risk',
    'sildenafil': 'SCHEDULE H — Prescription required · Cardiac risk without supervision',
    'tadalafil':  'SCHEDULE H — Prescription required · Drug interaction risk',
    'kamagra':    'NOT registered in India · Unverified sildenafil dosage · Public health risk',
    'steroid':    'Anabolic steroids — Schedule H · Prescription mandatory · Liver/cardiac risk',
    'hgh':        'Prescription-only growth hormone · Counterfeit endocrine risk',
    'cancer':     'Unproven treatment claim — Drugs and Magic Remedies Act 1954 violation',
    'tumor':      'Unproven treatment claim — Drugs and Magic Remedies Act 1954 violation',
    'insulin':    'Critical medication — counterfeit supply chain risk · Patient safety threat',
}

def detect_drug(text):
    tl = text.lower()
    for k, v in DRUG_BRANDS.items():
        if k in tl:
            return k, v
    return None, 'Unspecified pharmaceutical product'

def run():
    alerts = json.load(open('reports/alerts/live_alerts.json'))
    pharma = [a for a in alerts if a.get('category') == 'counterfeit_pharma']
    print(f'Pharma alerts in database: {len(pharma)}')

    cases = []
    for a in pharma:
        text     = (a.get('title','') + ' ' + a.get('detail','')).lower()
        drug_k, drug_v = detect_drug(text)
        phones   = a.get('chain',{}).get('phones',[])
        websites = a.get('chain',{}).get('websites',[])
        upis     = a.get('chain',{}).get('upis',[])

        conf = 60
        if drug_k:                                  conf += 10
        if phones:                                  conf += 15
        if websites:                                conf += 8
        if upis:                                    conf += 8
        if 'arrested' in text or 'seized' in text:  conf += 10
        if 'cdsco' in text or 'dcgi' in text:       conf += 8
        if 'prescription' in text:                  conf += 5
        if 'telegram' in text:                      conf += 5
        if 'fake' in text or 'counterfeit' in text: conf += 5

        sev = SEVERITY_MAP.get(drug_k, 'high')
        cases.append({
            'alert':a, 'drug_key':drug_k, 'drug_name':drug_v,
            'phones':phones, 'websites':websites, 'upis':upis,
            'conf':min(conf,99), 'severity':sev,
            'title':a.get('title','')[:80],
        })

    cases.sort(key=lambda x: (-x['conf'], x['severity']!='critical'))
    top = cases[:25]

    generated = []
    for i, case in enumerate(top, 1):
        fname = f'pharma_{i:03d}.html'
        html  = build_html(case, i)
        open(f'reports/case_studies_pharma/{fname}','w').write(html)
        generated.append(fname)
        sev_label = f'[{case["severity"].upper()}]'
        print(f'  [{i:2d}] {case["conf"]}%  {sev_label:10s}  {case["drug_name"][:35]:35s}  {case["title"][:30]}')

    build_index(top, generated)
    crit = sum(1 for c in top if c['severity']=='critical')
    drugs = len(set(c['drug_key'] for c in top if c['drug_key']))
    print(f'\nSUMMARY:')
    print(f'  Case studies:    {len(top)}')
    print(f'  Critical (NDPS): {crit}')
    print(f'  Drug categories: {drugs}')
    print(f'  Index: reports/case_studies_pharma/index.html')

def build_html(case, n):
    now      = now_ist()
    cid      = f'CINEOS-PHARMA-2026-{n:03d}'
    conf     = case['conf']
    sev      = case['severity']
    a        = case['alert']
    cc       = '#DC2626' if sev=='critical' else '#D97706' if conf>=75 else '#2563EB'
    cbg      = '#FEF2F2' if sev=='critical' else '#FFFBEB' if conf>=75 else '#EFF6FF'
    ev_hash  = sha(case['title'])[:16]
    drug_risk= DRUG_RISK.get(case['drug_key'], 'Unregistered / counterfeit medicine — public health risk')
    legal    = 'NDPS Act 1985 §8 · Drugs and Cosmetics Act §17A · IT Act §65B · IPC §420' if case['drug_key'] in ('tramadol','codeine','alprazolam','xanax') else 'Drugs and Cosmetics Act 1940 §17A + §18 · IT Act 2000 §65B · IPC §420 + §468'

    phones_html   = ''.join(f'<div class="phone-item">📞 {p}</div>' for p in case['phones']) or '<span class="na">Not yet extracted</span>'
    websites_html = ''.join(f'<div class="web-item">🌐 {w[:60]}</div>' for w in case['websites']) or '<span class="na">Not yet extracted</span>'

    steps = [
        'File complaint: cdsco.gov.in/complaint',
        'Report to State Drug Controller (SDC)',
        'Request Telegram channel takedown via MHA',
        'File FIR: Drugs & Cosmetics Act §18 + IT Act §65B',
        'Cross-reference DEA-India database (200 sites Feb 2026)',
    ]
    if case['drug_key'] in ('tramadol','codeine','alprazolam','xanax'):
        steps[3] = 'File FIR: NDPS Act §8 + IT Act §65B (enhanced penalties)'

    steps_html  = ''.join(f'<div class="step"><span class="step-n">{i+1}</span><span>{s}</span></div>' for i,s in enumerate(steps))
    report_html = ''.join(f'<span class="agency">{r}</span>' for r in ['CDSCO — cdsco.gov.in','State Drug Controller','I4C — cybercrime.gov.in','DEA India liaison'])

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CINEOS Pharma Intelligence {cid}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --g:#166534;--gt:#F0FDF4;--gb:#BBF7D0;--gl:#DCFCE7;
  --ink:#0F172A;--b:#475569;--m:#94A3B8;--bo:#E2E8F0;
  --s:#F8FAFC;--w:#fff;--navy:#0D2B55;--teal:#0E7490
}}
body{{font-family:"Segoe UI",system-ui,sans-serif;background:var(--s);color:var(--ink);font-size:13px;line-height:1.6}}
.header{{background:var(--navy);padding:22px 36px 18px;color:#fff}}
.header-top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}}
.logo{{font-family:monospace;font-size:18px;font-weight:700;letter-spacing:.15em}}
.vert-badge{{background:#059669;color:#fff;font-family:monospace;font-size:10px;padding:3px 10px;border-radius:3px;margin-bottom:8px;display:inline-block}}
.sev-badge{{background:{cbg};color:{cc};border:2px solid {cc};border-radius:8px;padding:8px 18px;text-align:center}}
.sev-n{{font-size:22px;font-weight:700;line-height:1}}
.sev-l{{font-size:9px;text-transform:uppercase;letter-spacing:.1em;margin-top:2px}}
.case-title{{font-size:16px;font-weight:700;margin-bottom:3px}}
.case-sub{{font-size:11px;color:#9EC6F3}}
.drug-banner{{background:{'#7F1D1D' if sev=='critical' else '#92400E' if sev=='high' else '#1E3A5F'};padding:10px 36px;display:flex;align-items:center;gap:12px}}
.drug-name{{font-size:13px;font-weight:600;color:#fff}}
.drug-risk{{font-size:11px;color:rgba(255,255,255,.75);margin-top:2px}}
.meta{{background:#132244;padding:8px 36px;display:flex;gap:28px;border-bottom:2px solid #059669}}
.meta-item{{font-size:10px}}
.meta-lbl{{color:#7BAFD4;font-family:monospace;font-size:8px;text-transform:uppercase;display:block;margin-bottom:1px}}
.meta-val{{color:#fff;font-weight:600}}
.body{{padding:22px 36px;max-width:1000px}}
.section{{background:var(--w);border:1px solid var(--bo);border-radius:6px;overflow:hidden;margin-bottom:12px}}
.sec-title{{font-family:monospace;font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:var(--m);padding:8px 14px;background:var(--s);border-bottom:1px solid var(--bo)}}
.sec-body{{padding:13px}}
.phones{{display:flex;flex-wrap:wrap;gap:5px}}
.phone-item{{font-family:monospace;font-size:12px;font-weight:600;color:#DC2626;background:#FEF2F2;border:1px solid #FECACA;padding:4px 8px;border-radius:4px}}
.web-item{{font-family:monospace;font-size:11px;color:#0E7490;background:#F0FDFA;border:1px solid #99F6E4;padding:4px 8px;border-radius:4px}}
.na{{font-size:11px;color:var(--m);font-style:italic}}
.ev-box{{background:#0A1628;color:#7FD8E8;font-family:monospace;font-size:11px;padding:10px 14px;border-radius:5px;border:1px solid #059669}}
.ev-lbl{{color:#059669;font-size:8px;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:3px}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.step{{display:flex;align-items:flex-start;gap:8px;font-size:12px;color:var(--b);padding:4px 0}}
.step-n{{font-family:monospace;font-size:9px;font-weight:700;color:#fff;background:#059669;width:18px;height:18px;border-radius:3px;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px}}
.agencies{{display:flex;flex-wrap:wrap;gap:5px}}
.agency{{font-family:monospace;font-size:9px;background:#ECFDF5;color:#059669;border:1px solid #A7F3D0;padding:3px 8px;border-radius:3px;font-weight:600}}
.footer{{background:var(--navy);color:#7BAFD4;padding:12px 36px;font-size:9px;font-family:monospace;display:flex;justify-content:space-between;margin-top:20px}}
</style>
</head>
<body>
<div class="header">
  <div class="header-top">
    <div>
      <div class="logo">CINEOS</div>
      <div class="vert-badge">COUNTERFEIT PHARMA INTELLIGENCE</div>
      <div class="case-title">{case["title"]}</div>
      <div class="case-sub">Case ID: {cid} · {case["drug_name"]}</div>
    </div>
    <div class="sev-badge">
      <div class="sev-n">{sev.upper()}</div>
      <div class="sev-l">{conf}% confidence</div>
    </div>
  </div>
</div>
<div class="drug-banner">
  <div style="font-size:22px">⚠️</div>
  <div>
    <div class="drug-name">{case["drug_name"]}</div>
    <div class="drug-risk">{drug_risk}</div>
  </div>
</div>
<div class="meta">
  <div class="meta-item"><span class="meta-lbl">Case ID</span><span class="meta-val">{cid}</span></div>
  <div class="meta-item"><span class="meta-lbl">Detected</span><span class="meta-val">{now.strftime("%Y-%m-%d %H:%M IST")}</span></div>
  <div class="meta-item"><span class="meta-lbl">Evidence</span><span class="meta-val">IT Act §65B</span></div>
  <div class="meta-item"><span class="meta-lbl">Hash</span><span class="meta-val" style="font-size:9px;font-family:monospace">{ev_hash}...</span></div>
  <div class="meta-item"><span class="meta-lbl">Legal</span><span class="meta-val" style="font-size:9px">{'NDPS Act' if case['drug_key'] in ('tramadol','codeine','alprazolam','xanax') else 'D&C Act'}</span></div>
</div>
<div class="body">
  <div class="two">
    <div class="section">
      <div class="sec-title">Operator Phones Extracted</div>
      <div class="sec-body"><div class="phones">{phones_html}</div></div>
    </div>
    <div class="section">
      <div class="sec-title">Websites / Domains</div>
      <div class="sec-body"><div style="display:flex;flex-wrap:wrap;gap:5px">{websites_html}</div></div>
    </div>
  </div>
  <div class="section">
    <div class="sec-title">Evidence Hash — IT Act §65B</div>
    <div class="sec-body">
      <div class="ev-box">
        <span class="ev-lbl">SHA-256 Hash</span>
        {sha(case["title"])[:48]}...
        <br><br>
        <span class="ev-lbl">Detection Timestamp</span>
        {now.strftime("%Y-%m-%d %H:%M:%S IST")}
      </div>
    </div>
  </div>
  <div class="section">
    <div class="sec-title">Intelligence Detail</div>
    <div class="sec-body" style="font-size:12px;color:var(--b);line-height:1.7">
      {a.get("detail","No detail available")[:500]}
    </div>
  </div>
  <div class="section">
    <div class="sec-title">Legal Basis</div>
    <div class="sec-body" style="font-size:12px;color:var(--b);line-height:1.6">{legal}</div>
  </div>
  <div class="two">
    <div class="section">
      <div class="sec-title">Recommended Next Steps</div>
      <div class="sec-body">{steps_html}</div>
    </div>
    <div class="section">
      <div class="sec-title">Report To</div>
      <div class="sec-body">
        <div class="agencies">{report_html}</div>
        <div style="margin-top:10px;font-size:11px;color:var(--m)">
          Full §65B(2) evidence package + drug category dossier available on request.
        </div>
      </div>
    </div>
  </div>
</div>
<div class="footer">
  <span>CINEOS · Counterfeit Pharma Intelligence · Patent 64/049,190 · yugandhar@cineos.in · cineos.in</span>
  <span>RESTRICTED — CDSCO / Law Enforcement / Legal Use Only · {cid}</span>
</div>
</body>
</html>'''

def build_index(cases, files):
    rows = ''
    for i, (case, fname) in enumerate(zip(cases, files), 1):
        conf = case['conf']
        sev  = case['severity']
        cc   = '#DC2626' if sev=='critical' else '#D97706' if conf>=75 else '#2563EB'
        cbg  = '#FEF2F2' if sev=='critical' else '#FFFBEB' if conf>=75 else '#EFF6FF'
        rows += (f'<tr onclick="window.open(\'{fname}\')" style="cursor:pointer">'
                 f'<td class="mono" style="color:#94A3B8">CINEOS-PHARMA-2026-{i:03d}</td>'
                 f'<td><b>{case["title"][:55]}</b></td>'
                 f'<td style="font-size:12px">{case["drug_name"][:40]}</td>'
                 f'<td style="text-align:center"><span style="font-family:monospace;font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;color:{cc};background:{cbg}">{sev.upper()}</span></td>'
                 f'<td style="text-align:center;font-family:monospace;font-weight:700;color:{cc}">{conf}%</td>'
                 f'</tr>')

    crit  = sum(1 for c in cases if c['severity']=='critical')
    drugs = len(set(c['drug_key'] for c in cases if c['drug_key']))
    html  = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>CINEOS Pharma Intelligence Index</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"Segoe UI",system-ui,sans-serif;background:#F0FDF4;color:#0F172A;font-size:13px}}
.header{{background:#0D2B55;color:#fff;padding:20px 36px}}
.logo{{font-family:monospace;font-size:18px;font-weight:700;letter-spacing:.15em;margin-bottom:4px}}
h1{{font-size:20px;font-weight:600}}
.sub{{font-size:12px;color:#9EC6F3;margin-top:3px}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:14px 36px;background:#132244}}
.stat{{text-align:center}}
.stat-n{{font-family:monospace;font-size:26px;font-weight:700;color:#22c55e}}
.stat-l{{font-size:10px;color:#7BAFD4;margin-top:2px}}
.body{{padding:20px 36px}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #BBF7D0;border-radius:6px;overflow:hidden}}
thead th{{font-family:monospace;font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#94A3B8;padding:9px 10px;text-align:left;border-bottom:2px solid #E2E8F0;background:#F8FAFC}}
tbody td{{padding:9px 10px;border-bottom:1px solid #E2E8F0;font-size:12px}}
tbody tr:hover{{background:#F0FDF4}}
.mono{{font-family:monospace;font-size:11px}}
</style>
</head>
<body>
<div class="header">
  <div class="logo">CINEOS</div>
  <h1>Counterfeit Pharma Intelligence — Case Studies</h1>
  <div class="sub">CDSCO · State Drug Controllers · DEA-India · Brand Protection · {datetime.now(IST).strftime("%Y-%m-%d")} · Patent 64/049,190</div>
</div>
<div class="stats">
  <div class="stat"><div class="stat-n">{len(cases)}</div><div class="stat-l">Case Studies</div></div>
  <div class="stat"><div class="stat-n">{crit}</div><div class="stat-l">Critical (NDPS)</div></div>
  <div class="stat"><div class="stat-n">{drugs}</div><div class="stat-l">Drug Categories</div></div>
  <div class="stat"><div class="stat-n">§65B</div><div class="stat-l">Evidence Standard</div></div>
</div>
<div class="body">
  <table>
    <thead>
      <tr>
        <th>Case ID</th>
        <th>Alert Title</th>
        <th>Drug / Category</th>
        <th style="text-align:center">Severity</th>
        <th style="text-align:center">Confidence</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>
</body>
</html>'''
    open('reports/case_studies_pharma/index.html', 'w').write(html)

if __name__ == '__main__':
    print('=' * 55)
    print(f'  CINEOS COUNTERFEIT PHARMA CASE STUDIES')
    print(f'  {now_ist().strftime("%Y-%m-%d %H:%M IST")}')
    print('=' * 55)
    run()
