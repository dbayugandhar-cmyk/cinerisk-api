"""
CINEOS Alert Engine
Detect → Attribute → Evidence → Report

Every scanner calls add_alert() when it finds something.
Alerts immediately appear in internal dashboard.
Top 10 by severity score go to cineos_today.html at 9am.
"""
import json, os, hashlib
from datetime import datetime
from collections import defaultdict

os.makedirs('reports/alerts', exist_ok=True)
os.makedirs('reports/pdfs', exist_ok=True)

ALERTS_FILE = 'reports/alerts/live_alerts.json'

def load_alerts():
    try:
        return json.load(open(ALERTS_FILE))
    except:
        return []

def save_alerts(alerts):
    json.dump(alerts, open(ALERTS_FILE,'w'), indent=2, default=str)

def severity_score(a):
    s = {'critical':100,'high':60,'medium':30,'low':10}.get(a.get('severity',''),0)
    c = a.get('chain',{})
    if c.get('phones'):             s += 20
    if c.get('upis'):               s += 15
    if c.get('operator_name'):      s += 25
    if c.get('whois_registrant'):   s += 20
    r = c.get('reach',0)
    if r > 1000000: s += 20
    elif r > 500000: s += 10
    elif r > 100000: s += 5
    return s

def add_alert(title, category, severity, platform, detail,
              channels_found=None, keywords_matched=None, reach=0,
              phones=None, upis=None,
              whois_domain=None, whois_registrant=None,
              operator_name=None, operator_network=None,
              evidence_hashes=None, legal_basis=None,
              recommended_action=None, report_to=None):

    alerts = load_alerts()
    h = hashlib.sha256(f"{title}{datetime.now().isoformat()}".encode()).hexdigest()[:16]

    alert = {
        'id': h,
        'title': title,
        'category': category,
        'severity': severity,
        'platform': platform,
        'detail': detail,
        'chain': {
            'channels_found':   channels_found or [],
            'keywords_matched': keywords_matched or [],
            'reach':            reach,
            'phones':           phones or [],
            'upis':             upis or [],
            'whois_domain':     whois_domain or '',
            'whois_registrant': whois_registrant or '',
            'operator_name':    operator_name or '',
            'operator_network': operator_network or '',
            'evidence_hashes':  evidence_hashes or [],
            'legal_basis':      legal_basis or 'IT Act 2000 S.65B',
            'recommended_action': recommended_action or '',
            'report_to':        report_to or [],
            'captured_at':      datetime.now().isoformat(),
        },
        'detected_at': datetime.now().isoformat(),
        'status': 'active',
        'published': False,
    }

    alerts.insert(0, alert)
    save_alerts(alerts[:500])
    return h

def get_top10():
    alerts  = load_alerts()
    today   = datetime.now().strftime('%Y-%m-%d')
    scored  = []
    for a in alerts:
        d = a.get('detected_at','')[:10]
        if d == today or a.get('severity') == 'critical':
            scored.append((severity_score(a), a))
    scored.sort(key=lambda x: -x[0])
    top10 = [a for _,a in scored[:10]]
    ids   = {a['id'] for a in top10}
    for a in load_alerts():
        if a['id'] in ids:
            a['published'] = True
    save_alerts(load_alerts())
    return top10

def public_signal(a):
    c = a.get('chain',{})
    r = c.get('reach',0)
    return {
        'title':    a['title'],
        'severity': a['severity'],
        'category': a['category'],
        'platform': a['platform'],
        'detail':   a['detail'],
        'reach':    f"{r/1e6:.1f}M" if r>999999 else (f"{r:,}" if r else '—'),
        'channels': len(c.get('channels_found',[])),
        'legal':    c.get('legal_basis','IT Act S.65B').split('+')[0].strip(),
    }

def seed():
    data = [
        dict(title="IPL Match 53 — 20 piracy streams detected",
             category="piracy", severity="critical",
             platform="Telegram / Web",
             detail="20 illegal live streams during CSK vs LSG, May 10, 13:23 IST",
             channels_found=["13 channels (internal)"],
             keywords_matched=["ipl live","hotstar free","watch live stream"],
             reach=35000000,
             phones=["+91-8306154335","+91-9216328940"],
             operator_name="Reddy Anna Book affiliate",
             operator_network="Play99 network",
             evidence_hashes=["b4d2d638a9f1c2"],
             legal_basis="IT Act 2000 S.65B + Copyright Act S.51",
             recommended_action="IT Rules 2021 S.69A takedown notice to Telegram",
             report_to=["JioHotstar","BCCI","MIB"]),

        dict(title="Fake PhonePe APK — active credential theft site",
             category="brand_impersonation", severity="critical",
             platform="Web / APK",
             detail="phonepes.com.in — fake PhonePe APK, UAE registrant, Jan 2026",
             channels_found=["phonepes.com.in"],
             keywords_matched=["phonepe apk","download","install"],
             whois_domain="phonepes.com.in",
             whois_registrant="[UAE registrant — full WHOIS internal]",
             evidence_hashes=["a7f3c891d2e4b5"],
             legal_basis="IT Act 2000 S.66D + S.65B",
             recommended_action="Report to CERT-In + PhonePe + domain registrar",
             report_to=["PhonePe","CERT-In","Dynadot"]),

        dict(title="jiohotstar.net — domain squat, registrant identified",
             category="domain_squat", severity="critical",
             platform="WHOIS",
             detail="Registered Jan 18 2026 — 4 days after JioHotstar launch",
             channels_found=["jiohotstar.net"],
             keywords_matched=["jiohotstar"],
             whois_domain="jiohotstar.net",
             whois_registrant="muthyala naresh — muthyala19@gmail.com",
             evidence_hashes=["e5f6a7b8c9d0e1"],
             legal_basis="IT Act 2000 S.65B + Trade Marks Act S.29",
             recommended_action="UDRP complaint + civil suit — registrant identified",
             report_to=["JioHotstar","BigRock","NIXI"]),

        dict(title="BCCI impersonator — 2 operator phones confirmed",
             category="impersonation", severity="high",
             platform="Telegram",
             detail="Phones publicly posted in fake BCCI channels — 95% confidence",
             channels_found=["2 channels (internal)"],
             keywords_matched=["bcci","toss fixer","match prediction"],
             reach=45000,
             phones=["+91-8306154335","+91-9216328940"],
             operator_name="Reddy Anna Book",
             operator_network="Play99 affiliate",
             evidence_hashes=["d4e5f6a7b8c9d0"],
             legal_basis="IT Act 2000 S.66D + S.65B",
             recommended_action="FIR under IT Act S.66D — evidence ready",
             report_to=["BCCI","Delhi Police","I4C"]),

        dict(title="91CLUB — 1,008,905 subscribers, illegal colour prediction",
             category="colour_prediction", severity="high",
             platform="Telegram",
             detail="Largest single fraud channel in database — Chinese-origin app",
             channels_found=["1 channel (internal)"],
             keywords_matched=["91club","aviator","colour prediction"],
             reach=1008905,
             evidence_hashes=["g7h8i9j0k1l2"],
             legal_basis="Online Gaming Act 2025 + IT Act S.65B",
             recommended_action="Report to NOGC + DoT for channel blocking",
             report_to=["NOGC","MeitY","DoT"]),

        dict(title="UPI mule recruitment — Gujarat Rs 77Cr network active",
             category="upi_mule", severity="high",
             platform="Telegram",
             detail="Bank account kit offers — Gujarat bust modus, Dubai link confirmed",
             channels_found=["active channels (internal)"],
             keywords_matched=["bank account kit","sim card","earn commission"],
             reach=12000,
             operator_network="Gujarat-Dubai corridor",
             evidence_hashes=["f6a7b8c9d0e1f2"],
             legal_basis="IT Act 2000 S.65B + IPC S.420",
             recommended_action="Intelligence to HDFC/ICICI risk teams + I4C",
             report_to=["NPCI","HDFC","ICICI","I4C"]),

        dict(title="148 counterfeit listings — Amazon India + Flipkart",
             category="counterfeit_marketplace", severity="high",
             platform="Amazon / Flipkart",
             detail="Explicit counterfeit keywords in product titles — 3-tier verified",
             channels_found=["Amazon India","Flipkart"],
             keywords_matched=["first copy","replica","master copy","duplicate brand"],
             evidence_hashes=["c3d4e5f6a7b8c9"],
             legal_basis="Trade Marks Act 1999 S.29 + IT Act S.65B",
             recommended_action="Brand takedown notices to Amazon/Flipkart",
             report_to=["Amazon Brand Registry","Flipkart Legal"]),

        dict(title="15 pharma channels — Unitel Pharma modus operandi",
             category="counterfeit_pharma", severity="high",
             platform="Telegram",
             detail="Matches Rs 10Cr Unitel bust — CGHS diversion, packaging mimicry",
             channels_found=["15 channels (internal)"],
             keywords_matched=["medicine wholesale","pharma agent","below mrp"],
             reach=85000,
             evidence_hashes=["h8i9j0k1l2m3n4"],
             legal_basis="Drugs and Cosmetics Act 1940 + IT Act S.65B",
             recommended_action="Intelligence to CDSCO + pharma brands after deep scan",
             report_to=["CDSCO","Delhi Police","Sun Pharma"]),

        dict(title="Mahadev Book — 41 channels, 2.2M reach, active ED case",
             category="illegal_betting", severity="high",
             platform="Telegram",
             detail="Largest betting operator. Active ED investigation. Dubai link.",
             channels_found=["41 channels (internal)"],
             keywords_matched=["mahadev book","cricket bet","ipl bet"],
             reach=2200000,
             operator_name="Mahadev Book",
             operator_network="Lotus365 / Dubai",
             evidence_hashes=["i9j0k1l2m3n4o5"],
             legal_basis="Public Gambling Act 1867 + IT Act S.65B",
             recommended_action="Intelligence to ED + Cyber Crime Portal",
             report_to=["ED","NOGC","Cyber Crime Portal"]),

        dict(title="Investment fraud syndicate — 5 fake platforms, 1 registrant",
             category="investment_fraud", severity="medium",
             platform="Telegram / Web",
             detail="WHOIS links 5 fake trading platforms to one registrant",
             channels_found=["25 channels (internal)"],
             keywords_matched=["guaranteed returns","sebi registered","100% profit"],
             reach=340000,
             whois_domain="5 domains (internal)",
             whois_registrant="[Registrant identified — internal]",
             evidence_hashes=["j0k1l2m3n4o5p6"],
             legal_basis="SEBI IA Regulations 2013 + IT Act S.65B",
             recommended_action="SEBI SCORES complaint + platform takedown",
             report_to=["SEBI","I4C","Telegram"]),
    ]

    for d in data:
        add_alert(**d)
    print(f"  Seeded {len(data)} alerts")

if __name__ == '__main__':
    seed()
    alerts = load_alerts()
    print(f"  Total: {len(alerts)} alerts in engine")
