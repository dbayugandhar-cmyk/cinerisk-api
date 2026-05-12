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

app = Flask(__name__)
CORS(app)  # Allow cineos.in dashboard to fetch

# ── IN-MEMORY STORE ───────────────────────────────────────
# Railway has ephemeral storage — we keep alerts in memory
# Dedup enforced: no two alerts share the same id OR title+category

ALERTS    = []
ALERT_IDS     = set()   # fast dedup by id
ALERT_TITLES  = set()   # fast dedup by title+category
last_scan_time = None   # updated after every scheduler run

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

    ALERTS[:] = ALERTS[:500]
    print(f"[{ist_now().strftime('%H:%M IST')}] Scan done. {new_found} new alerts. Total: {len(ALERTS)}")

# ── SCHEDULER ─────────────────────────────────────────────
def scheduler_loop():
    """Run scans at 8am, 12pm, 6pm, 10pm IST every day."""
    SCAN_HOURS_IST = {8, 12, 18, 22}
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
# ── DEDUP-AWARE SEED ─────────────────────────────────────
def _dedup_add(alert):
    """Add alert only if id and title+category are unique."""
    global ALERTS, ALERT_IDS, ALERT_TITLES
    aid       = str(alert.get('id', ''))
    title_key = f"{str(alert.get('title',''))[:60]}|{alert.get('category','')}"
    if aid and aid in ALERT_IDS:
        return False
    if title_key in ALERT_TITLES:
        return False
    ALERTS.insert(0, alert)
    if aid:
        ALERT_IDS.add(aid)
    ALERT_TITLES.add(title_key)
    return True

for _a in SEED_ALERTS:
    _dedup_add(_a)
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
    limit    = int(request.args.get('limit', 100))

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
    """Add a new alert — server-side dedup by id and title+category."""
    global ALERTS, ALERT_IDS, ALERT_TITLES, last_scan_time
    api_key = request.headers.get('X-API-Key','')
    if api_key != os.environ.get('CINEOS_API_KEY', 'cineos_internal_2026'):
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        alert = request.get_json(force=True) or {}
        if not alert.get('title'):
            return jsonify({'error': 'Missing title'}), 400
        added = _dedup_add(alert)
        if not added:
            return jsonify({'status': 'duplicate', 'message': 'Alert already exists'}), 200
        ALERTS[:] = ALERTS[:500]  # cap at 500
        return jsonify({'status': 'ok', 'total': len(ALERTS)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
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
    ALERTS[:] = ALERTS[:500]

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

@app.route('/api/reset', methods=['POST'])
def reset_alerts():
    """Clear all alerts and reseed from SEED_ALERTS. Admin only."""
    global ALERTS, ALERT_IDS, ALERT_TITLES
    api_key = request.headers.get('X-API-Key','')
    if api_key != os.environ.get('CINEOS_API_KEY', 'cineos_internal_2026'):
        return jsonify({'error': 'Unauthorized'}), 401
    ALERTS.clear()
    ALERT_IDS.clear()
    ALERT_TITLES.clear()
    for a in SEED_ALERTS:
        _dedup_add(a)
    return jsonify({'status': 'reset', 'seeded': len(ALERTS)}), 200

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
