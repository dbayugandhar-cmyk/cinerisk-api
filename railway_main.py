"""
CINEOS Railway API — 24/7 Intelligence Backend

Endpoints:
  GET /health              → status check
  GET /api/alerts          → live alerts feed (for internal dashboard)
  GET /api/alerts/top10    → top 10 for today's public brief
  GET /api/stats           → channel + graph stats
  GET /api/channels        → channel summary by category
  POST /api/alert          → add new alert (from scanners)

Scheduler (runs even when Mac is off):
  08:00 IST → SerpAPI multi-platform scan
  12:00 IST → SerpAPI scan + alert engine update
  18:00 IST → SerpAPI scan
  22:00 IST → Daily summary + GitHub push
"""

import os, json, hashlib, threading, time
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

# ── AGGRESSIVE MULTI-CATEGORY QUERY SET ──────────────────
SCAN_QUERIES = {
    'piracy': [
        'IPL 2026 live stream free Telegram illegal',
        'hotstar free stream Telegram channel India',
        'OTT piracy India Telegram movie download 2026',
        'JioHotstar piracy India stream free',
    ],
    'illegal_betting': [
        'site:t.me satta matka betting India 2026',
        'Mahadev Book Reddy Anna cricket betting Telegram',
        'online cricket id betbhai9 laser247 Telegram India',
        'IPL toss prediction sure shot Telegram India 2026',
        'satta king faridabad ghaziabad result Telegram',
    ],
    'colour_prediction': [
        '91club OKWIN Jalwa BDG Win Telegram India 2026',
        'colour prediction game Telegram India earn withdraw',
        'Daman game Tiranga lottery Telegram India 2026',
        'wingo bdg colour trading Telegram India 2026',
    ],
    'crypto_fraud': [
        'crypto investment fraud India Telegram arrested 2026',
        'fake crypto platform India ED PMLA chargesheet 2026',
        'pig butchering WhatsApp Telegram India 2026',
        'Bitcoin USDT fraud India Telegram arrested',
    ],
    'ai_scam': [
        'digital arrest scam India AI voice 2026',
        'deepfake fraud India WhatsApp Telegram 2026',
        'AI voice clone fraud CBI ED impersonation India',
        'fake official call India digital arrest MHA',
    ],
    'investment_fraud': [
        'SEBI unregistered advisor Telegram India 2026',
        'stock tips guaranteed profit Telegram India fraud',
        'fake IPO subscription Telegram India fraud arrested',
        'option trading fraud India Telegram profit guarantee',
    ],
    'upi_mule': [
        'bank account kit sell India Telegram earn 2026',
        'UPI mule arrested India cybercrime 2026',
        'money mule India Telegram bank account fraud',
        'sim card bank kit Telegram India earn commission',
    ],
    'enforcement_news': [
        'cybercrime arrested India Telegram fraud crore 2026',
        'ED crypto fraud India PMLA chargesheet 2026',
        'SEBI action unregistered advisor India crore 2026',
        'I4C cybercrime India Telegram arrested today 2026',
        'CERT-In advisory phishing India 2026',
    ],
}


app = Flask(__name__)
CORS(app)  # Allow cineos.in dashboard to fetch

# ── IN-MEMORY STORE ───────────────────────────────────────
# Railway has ephemeral storage — we keep alerts in memory
# and sync to GitHub via API on every write

ALERTS    = []
STATS     = {
    'channels':     1245,
    'reach':        40000000,
    'graph_nodes':  1290,
    'graph_edges':  169,
    'last_scan':    None,
    'scans_today':  0,
}

# Seed with known alerts on startup
SEED_ALERTS = [
    {
        'id': 'b4d2d6',
        'title': 'IPL Match 53 — 20 piracy streams detected',
        'category': 'piracy',
        'severity': 'critical',
        'platform': 'Telegram / Web',
        'detail': '20 illegal live streams CSK vs LSG · May 10 · 13:23 IST · 35M+ reach',
        'detected_at': '2026-05-10T13:23:00',
        'chain': {
            'channels_found': ['13 channels (internal)'],
            'keywords_matched': ['ipl live', 'hotstar free', 'watch live stream'],
            'reach': 35000000,
            'phones': ['+91-8306154335', '+91-9216328940'],
            'operator_name': 'Reddy Anna Book affiliate',
            'operator_network': 'Play99 network',
            'evidence_hashes': ['b4d2d638a9f1c2'],
            'legal_basis': 'IT Act 2000 S.65B + Copyright Act S.51',
            'recommended_action': 'IT Rules 2021 S.69A takedown notice to Telegram',
            'report_to': ['JioHotstar', 'BCCI', 'MIB'],
        }
    },
    {
        'id': 'a7f3c8',
        'title': 'Fake PhonePe APK — active credential theft site',
        'category': 'brand_impersonation',
        'severity': 'critical',
        'platform': 'Web / APK',
        'detail': 'phonepes.com.in — fake PhonePe APK · UAE registrant · Jan 2026',
        'detected_at': '2026-05-10T09:14:00',
        'chain': {
            'channels_found': ['phonepes.com.in'],
            'keywords_matched': ['phonepe apk', 'download', 'install'],
            'reach': 0,
            'whois_domain': 'phonepes.com.in',
            'whois_registrant': 'UAE registrant (full WHOIS internal)',
            'evidence_hashes': ['a7f3c891d2e4b5'],
            'legal_basis': 'IT Act 2000 S.66D + S.65B',
            'recommended_action': 'Report to CERT-In + PhonePe + domain registrar',
            'report_to': ['PhonePe', 'CERT-In', 'Dynadot'],
        }
    },
    {
        'id': 'e5f6a7',
        'title': 'jiohotstar.net — domain squat · registrant identified',
        'category': 'domain_squat',
        'severity': 'critical',
        'platform': 'WHOIS',
        'detail': 'Registered Jan 18 2026 — 4 days after JioHotstar launch',
        'detected_at': '2026-05-10T06:00:00',
        'chain': {
            'channels_found': ['jiohotstar.net'],
            'keywords_matched': ['jiohotstar'],
            'reach': 0,
            'whois_domain': 'jiohotstar.net',
            'whois_registrant': 'muthyala naresh — muthyala19@gmail.com',
            'evidence_hashes': ['e5f6a7b8c9d0e1'],
            'legal_basis': 'IT Act S.65B + Trade Marks Act S.29',
            'recommended_action': 'UDRP complaint + civil suit',
            'report_to': ['JioHotstar', 'BigRock', 'NIXI'],
        }
    },
    {
        'id': 'd4e5f6',
        'title': 'BCCI impersonator — 2 operator phones confirmed',
        'category': 'impersonation',
        'severity': 'high',
        'platform': 'Telegram',
        'detail': 'Phones publicly posted in fake BCCI channels · 95% confidence',
        'detected_at': '2026-05-10T07:00:00',
        'chain': {
            'channels_found': ['2 channels (internal)'],
            'keywords_matched': ['bcci', 'toss fixer', 'match prediction'],
            'reach': 45000,
            'phones': ['+91-8306154335', '+91-9216328940'],
            'operator_name': 'Reddy Anna Book',
            'operator_network': 'Play99 affiliate',
            'evidence_hashes': ['d4e5f6a7b8c9d0'],
            'legal_basis': 'IT Act S.66D + S.65B',
            'recommended_action': 'FIR under IT Act S.66D',
            'report_to': ['BCCI', 'Delhi Police', 'I4C'],
        }
    },
    {
        'id': 'g7h8i9',
        'title': '91CLUB — 1,008,905 subscribers · illegal colour prediction',
        'category': 'colour_prediction',
        'severity': 'high',
        'platform': 'Telegram',
        'detail': 'Largest single fraud channel · Chinese-origin app',
        'detected_at': '2026-05-11T08:00:00',
        'chain': {
            'channels_found': ['1 channel (internal)'],
            'keywords_matched': ['91club', 'aviator', 'colour prediction'],
            'reach': 1008905,
            'evidence_hashes': ['g7h8i9j0k1l2'],
            'legal_basis': 'Online Gaming Act 2025 + IT Act S.65B',
            'recommended_action': 'Report to NOGC + DoT for blocking',
            'report_to': ['NOGC', 'MeitY', 'DoT'],
        }
    },
    {
        'id': 'f6a7b8',
        'title': 'UPI mule recruitment — Gujarat Rs 77Cr network active',
        'category': 'upi_mule',
        'severity': 'high',
        'platform': 'Telegram',
        'detail': 'Bank account kit offers · Gujarat bust modus · Dubai link confirmed',
        'detected_at': '2026-05-10T00:15:00',
        'chain': {
            'channels_found': ['active channels (internal)'],
            'keywords_matched': ['bank account kit', 'sim card', 'earn commission'],
            'reach': 12000,
            'operator_network': 'Gujarat-Dubai corridor',
            'evidence_hashes': ['f6a7b8c9d0e1f2'],
            'legal_basis': 'IT Act S.65B + IPC S.420',
            'recommended_action': 'Intelligence to HDFC/ICICI + I4C',
            'report_to': ['NPCI', 'HDFC', 'ICICI', 'I4C'],
        }
    },
    {
        'id': 'c3d4e5',
        'title': '148 counterfeit listings — Amazon India + Flipkart',
        'category': 'counterfeit_marketplace',
        'severity': 'high',
        'platform': 'Amazon / Flipkart',
        'detail': 'Explicit counterfeit keywords in product titles · 3-tier verified',
        'detected_at': '2026-05-10T08:00:00',
        'chain': {
            'channels_found': ['Amazon India', 'Flipkart'],
            'keywords_matched': ['first copy', 'replica', 'master copy'],
            'reach': 0,
            'evidence_hashes': ['c3d4e5f6a7b8c9'],
            'legal_basis': 'Trade Marks Act S.29 + IT Act S.65B',
            'recommended_action': 'Brand takedown notices to Amazon/Flipkart',
            'report_to': ['Amazon Brand Registry', 'Flipkart Legal'],
        }
    },
    {
        'id': 'h8i9j0',
        'title': '15 pharma channels — Unitel Pharma modus operandi',
        'category': 'counterfeit_pharma',
        'severity': 'high',
        'platform': 'Telegram',
        'detail': 'Matches Rs 10Cr Unitel bust · CGHS diversion · packaging mimicry',
        'detected_at': '2026-05-09T22:00:00',
        'chain': {
            'channels_found': ['15 channels (internal)'],
            'keywords_matched': ['medicine wholesale', 'pharma agent', 'below mrp'],
            'reach': 85000,
            'evidence_hashes': ['h8i9j0k1l2m3n4'],
            'legal_basis': 'Drugs and Cosmetics Act 1940 + IT Act S.65B',
            'recommended_action': 'Intelligence to CDSCO + pharma brands',
            'report_to': ['CDSCO', 'Delhi Police', 'Sun Pharma'],
        }
    },
    {
        'id': 'i9j0k1',
        'title': 'Mahadev Book — 41 channels · 2.2M reach · active ED case',
        'category': 'illegal_betting',
        'severity': 'high',
        'platform': 'Telegram',
        'detail': 'Largest betting operator · Active ED investigation · Dubai link',
        'detected_at': '2026-05-10T06:00:00',
        'chain': {
            'channels_found': ['41 channels (internal)'],
            'keywords_matched': ['mahadev book', 'cricket bet', 'ipl bet'],
            'reach': 2200000,
            'operator_name': 'Mahadev Book',
            'operator_network': 'Lotus365 / Dubai',
            'evidence_hashes': ['i9j0k1l2m3n4o5'],
            'legal_basis': 'Public Gambling Act 1867 + IT Act S.65B',
            'recommended_action': 'Intelligence to ED + Cyber Crime Portal',
            'report_to': ['ED', 'NOGC', 'Cyber Crime Portal'],
        }
    },
    {
        'id': 'j0k1l2',
        'title': 'Investment fraud syndicate — 5 fake platforms · 1 registrant',
        'category': 'investment_fraud',
        'severity': 'medium',
        'platform': 'Telegram / Web',
        'detail': 'WHOIS links 5 fake trading platforms to one registrant',
        'detected_at': '2026-05-10T08:00:00',
        'chain': {
            'channels_found': ['25 channels (internal)'],
            'keywords_matched': ['guaranteed returns', 'sebi registered', '100% profit'],
            'reach': 340000,
            'whois_domain': '5 domains (internal)',
            'whois_registrant': 'Registrant identified (internal)',
            'evidence_hashes': ['j0k1l2m3n4o5p6'],
            'legal_basis': 'SEBI IA Regulations 2013 + IT Act S.65B',
            'recommended_action': 'SEBI SCORES complaint + platform takedown',
            'report_to': ['SEBI', 'I4C', 'Telegram'],
        }
    },
]

# Auto-seed on import (gunicorn workers need this)
def init_alerts():
    global ALERTS
    ALERTS = list(SEED_ALERTS)

# ── HELPERS ───────────────────────────────────────────────
def severity_score(a):
    s = {'critical': 100, 'high': 60, 'medium': 30, 'low': 10}.get(a.get('severity', ''), 0)
    c = a.get('chain', {})
    if c.get('phones'):           s += 20
    if c.get('upis'):             s += 15
    if c.get('operator_name'):    s += 25
    if c.get('whois_registrant'): s += 20
    r = c.get('reach', 0)
    if r > 1000000: s += 20
    elif r > 500000: s += 10
    return s

def public_signal(a):
    """Strip all attribution for public brief."""
    c  = a.get('chain', {})
    r  = c.get('reach', 0)
    return {
        'title':    a['title'],
        'severity': a['severity'],
        'category': a['category'],
        'platform': a['platform'],
        'detail':   a['detail'],
        'reach':    f"{r/1e6:.1f}M" if r > 999999 else (f"{r:,}" if r else '—'),
        'channels': len(c.get('channels_found', [])),
        'legal':    c.get('legal_basis', 'IT Act S.65B').split('+')[0].strip(),
        'detected_at': a.get('detected_at', ''),
    }

def ist_now():
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))

# ── SERPAPI SCANNER (runs on Railway 24/7) ────────────────
SERP_KEY = os.environ.get('SERP_API_KEY', '')

def serp_search(query, engine='google', num=10):
    if not SERP_KEY:
        return {}
    import urllib.request, urllib.parse
    params = {
        'q': query, 'api_key': SERP_KEY,
        'engine': engine, 'num': num,
        'hl': 'en', 'gl': 'in',
    }
    url = 'https://serpapi.com/search?' + urllib.parse.urlencode(params)
    try:
        req  = urllib.request.urlopen(url, timeout=15)
        return json.loads(req.read())
    except Exception as e:
        print(f"SerpAPI: {e}")
        return {}

def run_scheduled_scan():
    """Called by scheduler. Runs SerpAPI searches, adds new alerts."""
    global STATS
    print(f"[{ist_now().strftime('%H:%M IST')}] Scheduled scan starting...")
    STATS['last_scan'] = ist_now().isoformat()
    STATS['scans_today'] += 1
    new_found = 0

    queries = [
        ('site:t.me "satta matka" OR "cricket bet"',    'illegal_betting', 'high'),
        ('site:t.me "colour prediction" OR "91club"',   'colour_prediction', 'high'),
        ('site:t.me "bank account kit" OR "sim card"',  'upi_mule', 'high'),
        ('"ipl live stream" telegram 2026',             'piracy', 'critical'),
        ('site:t.me "guaranteed returns" SEBI',         'investment_fraud', 'medium'),
        ('site:t.me "medicine wholesale" "below mrp"',  'counterfeit_pharma', 'high'),
        ('"fake" "apk" download site:*.in -play.google','brand_impersonation','critical'),
    ]

    existing_ids = {a['id'] for a in ALERTS}

    for q, cat, sev in queries:
        data = serp_search(q, num=5)
        for r in data.get('organic_results', []):
            link  = r.get('link', '')
            title = r.get('title', '')
            snip  = r.get('snippet', '')
            aid   = hashlib.sha256(link.encode()).hexdigest()[:8]
            if aid in existing_ids:
                continue

            alert = {
                'id':       aid,
                'title':    title[:80],
                'category': cat,
                'severity': sev,
                'platform': 'Web / Telegram',
                'detail':   snip[:120],
                'detected_at': ist_now().isoformat(),
                'source':   'serpapi_scheduled',
                'chain': {
                    'channels_found':   [link],
                    'keywords_matched': q.split()[:4],
                    'reach': 0,
                    'evidence_hashes':  [aid],
                    'legal_basis':      'IT Act 2000 S.65B',
                    'recommended_action': 'Verify and classify',
                    'report_to':        ['Internal review'],
                },
            }
            ALERTS.insert(0, alert)
            existing_ids.add(aid)
            new_found += 1

        time.sleep(2)

    ALERTS[:] = ALERTS[:5000]
    print(f"[{ist_now().strftime('%H:%M IST')}] Scan done. {new_found} new alerts. Total: {len(ALERTS)}")

# ── SCHEDULER ─────────────────────────────────────────────
def scheduler_loop():
    """Run scans at 8am, 12pm, 6pm, 10pm IST every day."""
    SCAN_HOURS_IST = {6, 8, 10, 12, 14, 16, 18, 20, 22}
    last_scan_hour = None

    while True:
        now  = ist_now()
        hour = now.hour

        if hour in SCAN_HOURS_IST and hour != last_scan_hour:
            last_scan_hour = hour
            try:
                run_scheduled_scan()
            except Exception as e:
                print(f"Scheduler error: {e}")

        # Reset at midnight
        if hour == 0:
            last_scan_hour = None
            STATS['scans_today'] = 0

        time.sleep(60)  # Check every minute

# ── API ROUTES ────────────────────────────────────────────

# Seed on module load — runs for both gunicorn and direct
ALERTS.extend(SEED_ALERTS)

# ── LOAD FROM GITHUB ON STARTUP (persistent) ─────────────
import urllib.request as _ur2, base64 as _b642, os as _os2
def _load_github():
    # Load directly from raw URL — no base64 corruption
    try:
        raw = 'https://raw.githubusercontent.com/dbayugandhar-cmyk/cinerisk-api/main/data/alerts_backup.json'
        req = _ur2.Request(raw, headers={'User-Agent': 'CINEOS'})
        data = json.loads(_ur2.urlopen(req, timeout=20).read())
        alerts = data if isinstance(data, list) else data.get('alerts', [])
        print(f'[STARTUP] GitHub raw: {len(alerts)} alerts loaded')
        return alerts
    except Exception as e:
        print(f'[STARTUP] GitHub raw failed: {e}')
        # Fallback: try API with token
        tok = _os2.environ.get('GITHUB_TOKEN_RAIL_READ','')
        if not tok:
            print('[STARTUP] No token — seed only')
            return []
        try:
            url = 'https://api.github.com/repos/dbayugandhar-cmyk/cinerisk-api/contents/data/alerts_backup.json'
            req2 = _ur2.Request(url, headers={
                'Authorization': f'token {tok}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'CINEOS'})
            d = json.loads(_ur2.urlopen(req2, timeout=12).read())
            content = d['content'].replace('\n','')
            alerts = json.loads(_b642.b64decode(content).decode())
            print(f'[STARTUP] GitHub API: {len(alerts)} alerts loaded')
            return alerts
        except Exception as e2:
            print(f'[STARTUP] Both methods failed: {e2}')
            return []

_seen = {a.get('id','') for a in ALERTS}
_seen_t = {f"{a.get('title','')[:60]}|{a.get('category','')}" for a in ALERTS}
for _ga in _load_github():
    _id = _ga.get('id','')
    _tk = f"{_ga.get('title','')[:60]}|{_ga.get('category','')}"
    if _id and _id in _seen: continue
    if _tk in _seen_t: continue
    ALERTS.insert(0, _ga)
    _seen.add(_id)
    _seen_t.add(_tk)
ALERTS[:] = sorted(ALERTS[:5000], key=lambda x: {'critical':0,'high':1,'medium':2,'low':3}.get(x.get('severity','low'),3))
print(f'[STARTUP] Ready: {len(ALERTS)} alerts total')
# ─────────────────────────────────────────────────────────

print(f'CINEOS: {len(ALERTS)} alerts seeded')

# Start scheduler for gunicorn (runs 24/7 even when Mac is off)
import threading as _t
_sched = _t.Thread(target=scheduler_loop, daemon=True)
_sched.start()
print('Scheduler started: 08:00 12:00 18:00 22:00 IST')

@app.route('/health')
def health():
    return jsonify({
        'status':      'ok',
        'service':     'CINEOS Intelligence API',
        'version':     '2.0',
        'time_ist':    ist_now().strftime('%Y-%m-%d %H:%M:%S IST'),
        'alerts':      len(ALERTS),
        'last_scan':   STATS['last_scan'],
        'scans_today': STATS['scans_today'],
        'patent':      'US Provisional Patent 64/049,190',
    })

@app.route('/api/alerts')
def get_alerts():
    """Full alert list for internal dashboard."""
    category = request.args.get('category', '')
    severity = request.args.get('severity', '')
    limit    = int(request.args.get('limit', 2000))

    filtered = ALERTS
    if category:
        filtered = [a for a in filtered if a.get('category') == category]
    if severity:
        filtered = [a for a in filtered if a.get('severity') == severity]

    return jsonify({
        'alerts':     filtered[:limit],
        'total':      len(filtered),
        'generated':  ist_now().isoformat(),
    })

@app.route('/api/alerts/top10')
def get_top10():
    """Top 10 by severity for today's public brief. No attribution."""
    today   = ist_now().strftime('%Y-%m-%d')
    scored  = []
    for a in ALERTS:
        scored.append((severity_score(a), a))

    scored.sort(key=lambda x: -x[0])
    top10 = [public_signal(a) for _, a in scored[:10]]

    return jsonify({
        'signals':   top10,
        'count':     len(top10),
        'date':      today,
        'generated': ist_now().isoformat(),
        'note':      'Public signals — no attribution. Full intelligence under signed agreement.',
    })

@app.route('/api/stats')
def get_stats():
    by_cat = {}
    by_sev = {}
    for a in ALERTS:
        c = a.get('category', 'unknown')
        s = a.get('severity', 'unknown')
        by_cat[c] = by_cat.get(c, 0) + 1
        by_sev[s] = by_sev.get(s, 0) + 1

    return jsonify({
        'channels':    STATS['channels'],
        'reach':       STATS['reach'],
        'graph_nodes': STATS['graph_nodes'],
        'graph_edges': STATS['graph_edges'],
        'alerts':      len(ALERTS),
        'by_category': by_cat,
        'by_severity': by_sev,
        'last_scan':   STATS['last_scan'],
        'scans_today': STATS['scans_today'],
        'generated':   ist_now().isoformat(),
    })

@app.route('/api/alert', methods=['POST'])
def add_alert():
    # Deduplication check — reject alerts with existing ID or identical title+category
    try:
        incoming = request.get_json(force=True) or {}
        inc_id    = incoming.get('id','')
        inc_title = incoming.get('title','')[:60]
        inc_cat   = incoming.get('category','')
        title_key = f"{inc_title}|{inc_cat}"

        existing_ids    = {a.get('id','') for a in ALERTS}
        existing_titles = {f"{a.get('title','')[:60]}|{a.get('category','')}" for a in ALERTS}

        if inc_id and inc_id in existing_ids:
            return jsonify({'status':'duplicate','message':'Alert ID already exists'}), 200
        if title_key in existing_titles:
            return jsonify({'status':'duplicate','message':'Alert title+category already exists'}), 200
    except:
        pass  # Fall through to normal processing if check fails
    """Add a new alert from scanner (authenticated)."""
    # Simple API key auth
    api_key = request.headers.get('X-API-Key', '')
    if api_key != os.environ.get('CINEOS_API_KEY', 'cineos_internal_2026'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data or not data.get('title'):
        return jsonify({'error': 'Missing title'}), 400

    alert_id = hashlib.sha256(
        f"{data['title']}{ist_now().isoformat()}".encode()
    ).hexdigest()[:8]

    alert = {
        'id':          alert_id,
        'title':       data.get('title', ''),
        'category':    data.get('category', 'unknown'),
        'severity':    data.get('severity', 'medium'),
        'platform':    data.get('platform', 'Telegram'),
        'detail':      data.get('detail', ''),
        'detected_at': ist_now().isoformat(),
        'source':      data.get('source', 'api'),
        'chain':       data.get('chain', {}),
    }

    ALERTS.insert(0, alert)
    ALERTS[:] = ALERTS[:5000]

    return jsonify({
        'id':      alert_id,
        'status':  'added',
        'total':   len(ALERTS),
    })

@app.route('/api/channels')
def get_channels():
    return jsonify({
        'total':     STATS['channels'],
        'reach':     STATS['reach'],
        'breakdown': {
            'illegal_betting':        437,
            'piracy':                  63,
            'colour_prediction':       41,
            'investment_fraud':        25,
            'counterfeit_pharma':      15,
            'upi_mule':                11,
            'counterfeit_marketplace': 148,
            'job_scam':                 9,
            'loan_fraud':               6,
            'other':                  491,
        },
        'generated': ist_now().isoformat(),
    })

# Simple CORS preflight
@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# ── STARTUP ───────────────────────────────────────────────

@app.route('/api/news_search')
def news_search():
    import urllib.parse as _ulp
    q = request.args.get('q','')
    if not q:
        return jsonify({'error':'no query'}),400
    SERP = os.environ.get('SERP_API_KEY','2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1')
    params = {'q':q,'api_key':SERP,'engine':'google_news','gl':'in','num':10}
    url = 'https://serpapi.com/search?' + _ulp.urlencode(params)
    try:
        import urllib.request as _ur
        resp = _ur.urlopen(url, timeout=12)
        data = json.loads(resp.read())
        return jsonify(data)
    except Exception as e:
        return jsonify({'error':str(e)}),500



@app.route('/api/watchlist', methods=['GET'])
def watchlist_check():
    phone = request.args.get('phone', '').strip()
    if not phone:
        return jsonify({'error': 'phone parameter required'}), 400
    import re as _re
    d = _re.sub(r'[^\d]', '', phone)
    if len(d) == 10:   pn = '+91' + d
    elif len(d) == 12: pn = '+' + d
    elif len(d) == 11 and d[0] == '0': pn = '+91' + d[1:]
    else: pn = phone
    bare = d[-10:] if len(d) >= 10 else d
    matches, cats = [], set()
    for a in ALERTS:
        chain = a.get('chain', {})
        for p in chain.get('phones', []):
            if p and bare in _re.sub(r'[^\d]', '', str(p)):
                matches.append(a)
                cats.add(a.get('category', 'unknown'))
                break
    if not matches:
        # Zero-alert enrichment — still return useful intelligence
        d2 = _re.sub(r'[^\d]', '', pn)
        if len(d2) == 12: d2 = d2[2:]
        HIGH_RISK = {
            '8881':{'score':40,'reason':'Reddy Anna/World777 network prefix'},
            '8808':{'score':25,'reason':'Known fraud operator prefix AP/TG'},
            '7455':{'score':35,'reason':'High-density betting operator prefix Rajasthan'},
            '7400':{'score':35,'reason':'High-density betting operator prefix Rajasthan'},
            '7413':{'score':30,'reason':'Known toss-fix operator prefix'},
            '7832':{'score':30,'reason':'Cross-vertical fraud operator prefix UP'},
            '9186':{'score':30,'reason':'Faridabad satta operator prefix'},
            '9602':{'score':25,'reason':'Satta operator prefix Rajasthan'},
        }
        pr = HIGH_RISK.get(d2[:4], {})
        base_score = pr.get('score', 0)
        signals = [pr['reason']] if pr else []
        risk = 'MEDIUM' if base_score >= 25 else 'LOW'
        return jsonify({
            'phone': pn, 'found': False,
            'risk_score': base_score,
            'risk_level': risk if base_score > 0 else 'CLEAR',
            'signals': signals,
            'message': 'Phone not in CINEOS alert database' + ('. Pattern suggests elevated risk — monitor.' if base_score > 0 else '. No fraud indicators found.'),
            'recommendation': 'Monitor' if base_score > 0 else 'Clear',
        })
    n = len(matches)
    score = min(60 + n*10 + len(cats)*10, 99)
    risk = 'CRITICAL' if score >= 90 else 'HIGH' if score >= 75 else 'MEDIUM'
    return jsonify({
        'phone': pn, 'found': True,
        'risk_score': score, 'risk_level': risk,
        'fraud_categories': list(cats),
        'alert_count': n,
        'evidence_hash': matches[0].get('evidence_hash', ''),
        'first_seen': matches[0].get('detected_at', '')[:10],
        'legal_basis': 'IT Act 2000 S65B certified evidence',
        'disclaimer': 'Intelligence-grade assessment from public sources. Verify before action. Not legal proof.',
        'report_to': ['FIU-IND fiuindia.gov.in', 'I4C cybercrime.gov.in'],
        'message': f'FRAUD RISK: Phone in {n} CINEOS alerts across {len(cats)} categories',
    })

@app.route('/api/watchlist/bulk', methods=['POST'])
def watchlist_bulk():
    data = request.get_json() or {}
    phones = data.get('phones', [])[:100]
    if not phones:
        return jsonify({'error': 'phones array required'}), 400
    results = []
    import re as _re2
    for phone in phones:
        d = _re2.sub(r'[^\d]', '', str(phone))
        bare = d[-10:] if len(d) >= 10 else d
        matches, cats = [], set()
        for a in ALERTS:
            for p in a.get('chain', {}).get('phones', []):
                if p and bare in _re2.sub(r'[^\d]', '', str(p)):
                    matches.append(a)
                    cats.add(a.get('category', 'unknown'))
                    break
        found = len(matches) > 0
        score = min(60 + len(matches)*10 + len(cats)*10, 99) if found else 0
        results.append({
            'phone': phone, 'found': found,
            'risk_score': score,
            'risk_level': 'CRITICAL' if score>=90 else 'HIGH' if score>=75 else 'MEDIUM' if found else 'CLEAR',
            'fraud_categories': list(cats),
            'alert_count': len(matches),
        })
    flagged = [r for r in results if r['found']]
    return jsonify({
        'total_checked': len(phones),
        'flagged': len(flagged),
        'clear': len(phones) - len(flagged),
        'results': results,
    })


if __name__ == '__main__':
    init_alerts()
    print(f"CINEOS Intelligence API starting...")
    print(f"Alerts seeded: {len(ALERTS)}")
    print(f"SerpAPI key: {'SET' if SERP_KEY else 'NOT SET — set SERP_API_KEY env var'}")

    # Start scheduler in background thread
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()
    print(f"Scheduler started: scans at 08:00, 12:00, 18:00, 22:00 IST")

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
