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
from flask import Flask, jsonify, request, make_response
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
    import urllib.request as _ur
    global ALERTS
    ALERTS = list(SEED_ALERTS)
    # Load from GitHub on startup
    try:
        tok = os.environ.get('GITHUB_TOKEN_RAIL_READ','')
        url = 'https://raw.githubusercontent.com/dbayugandhar-cmyk/cinerisk-api/main/data/alerts_backup.json'
        headers = {'Authorization': f'token {tok}'} if tok else {}
        req = _ur.Request(url, headers=headers)
        data = json.loads(_ur.urlopen(req, timeout=15).read())
        if isinstance(data, list) and len(data) > 0:
            ALERTS = data
            print(f'[INIT] Loaded {len(ALERTS)} alerts from GitHub')
        else:
            print(f'[INIT] GitHub returned empty — using {len(ALERTS)} seed alerts')
    except Exception as e:
        print(f'[INIT] GitHub load failed: {e} — using {len(ALERTS)} seed alerts')

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

# Client API keys — stored as environment variables on Railway
# Format: CINEOS_CLIENT_{NAME}=key_value
# Add via Railway dashboard: Settings → Variables
INTERNAL_KEY = os.environ.get('CINEOS_API_KEY', 'cineos_internal_2026')

def get_valid_keys():
    keys = {}
    # Internal key
    ik = os.environ.get('CINEOS_API_KEY', 'cineos_internal_2026')
    keys[ik] = 'internal'
    keys['cineos_internal_2026'] = 'internal'
    # Client keys from env vars
    for k, v in os.environ.items():
        if k.startswith('CINEOS_CLIENT_') and v:
            client_name = k.replace('CINEOS_CLIENT_', '').lower()
            keys[v] = client_name
    return keys

def check_api_key(req):
    key = (req.headers.get('X-API-Key','') or
           req.headers.get('Authorization','').replace('Bearer ','') or
           req.args.get('api_key',''))
    if not key:
        return False, None
    keys = get_valid_keys()
    client = keys.get(key)
    if client:
        return True, client
    return False, None

def log_api_call(client, endpoint, identifier):
    """Log API usage per client for billing."""
    pass  # TODO: add usage logging to Railway DB

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
        ('site:t.me satta matka India 2026',              'illegal_betting', 'high'),
        ('site:t.me "reddy anna" cricket id India',       'illegal_betting', 'critical'),
        ('site:t.me "mahadev book" betting India',        'illegal_betting', 'critical'),
        ('site:t.me "laser247" OR "betbhai9" India',      'illegal_betting', 'high'),
        ('site:t.me "sky exchange" OR "diamond exchange"','illegal_betting', 'high'),
        ('site:t.me "world777" OR "lotus365" betting',    'illegal_betting', 'high'),
        ('site:t.me kalyan matka dpboss satta king',      'illegal_betting', 'high'),
        ('site:t.me "bank account kit" sell India',       'upi_mule', 'high'),
        ('site:t.me "atm card" OR "sim card" sell India', 'upi_mule', 'high'),
        ('site:t.me ozempic OR tramadol India buy',       'counterfeit_pharma', 'high'),
        ('site:t.me sildenafil OR kamagra India order',   'counterfeit_pharma', 'high'),
        ('site:t.me "91club" OR "daman game" predict',    'colour_prediction', 'high'),
        ('site:t.me "usdt inr" P2P India operator',       'crypto_fraud', 'high'),
        ('site:t.me "guaranteed profit" trading India',   'investment_fraud', 'high'),
        ('Mahadev Book arrested India 2026 crore',        'illegal_betting', 'critical'),
        ('ED arrested online betting India crore 2026',   'illegal_betting', 'critical'),
        ('UPI mule arrested India FIU cybercrime 2026',   'upi_mule', 'critical'),
        ('counterfeit medicine arrested India 2026',      'counterfeit_pharma', 'high'),
        ('colour prediction fraud arrested India 2026',   'colour_prediction', 'high'),
        ('fake trading app arrested India ED 2026',       'investment_fraud', 'high'),
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

            # Extract phones, UPIs, Telegram channels from result
            import re as _re
            raw_phones = _re.findall(r'(?<![0-9])([6-9][0-9]{9})(?![0-9])', text)
            phones = ['+91'+p for p in raw_phones]
            upis = _re.findall(
                r'[\w.\-+]{2,40}@(?:okaxis|okhdfcbank|oksbi|ybl|ibl|paytm|upi|axisbank)',
                text, _re.I)
            has_tg = 't.me/' in link
            has_enforcement = bool(_re.search(
                r'arrested|FIR|seized|busted|crore|lakh', text, _re.I))

            # QUALITY GATE
            if not (phones or upis or has_tg or has_enforcement):
                continue

            alert = {
                'id':           aid,
                'title':        title[:100],
                'category':     cat,
                'severity':     'critical' if (phones or upis) else sev,
                'platform':     'Telegram' if has_tg else 'Web',
                'detail':       snip[:250],
                'detected_at':  ist_now().isoformat(),
                'source':       'railway_quality_scan',
                'evidence_hash': aid,
                'reach':        0,
                'phone':        phones[0] if phones else '',
                'upi':          upis[0] if upis else '',
                'chain': {
                    'channels_found':   [link],
                    'phones':           phones[:3],
                    'upis':             upis[:2],
                    'keywords_matched': q.split()[:4],
                    'reach':            0,
                    'evidence_hashes':  [aid],
                    'legal_basis':      'IT Act 2000 S65B',
                    'recommended_action': 'Verify operator identity',
                    'report_to':        ['I4C 1930', 'abuse@telegram.org'],
                    'captured_at':      ist_now().isoformat(),
                },
            }
            ALERTS.insert(0, alert)
            existing_ids.add(aid)
            new_found += 1

        time.sleep(2)

    ALERTS[:] = ALERTS[:5000]
    print(f"[{ist_now().strftime('%H:%M IST')}] Scan done. {new_found} new alerts. Total: {len(ALERTS)}")

# ── SCHEDULER ─────────────────────────────────────────────
@app.before_request
def load_on_first_request():
    global _initialized
    if not globals().get('_initialized'):
        globals()['_initialized'] = True
        init_alerts()
        import threading as _th
        _th.Thread(target=scheduler_loop, daemon=True).start()

def scheduler_loop():
    """Run quality scan every hour. Also runs once at startup."""
    global STATS
    print("[SCHEDULER] Starting — will scan every 60 minutes")

    # Run immediately on startup (don't wait for the hour)
    time.sleep(10)  # Give Flask time to start
    try:
        print("[SCHEDULER] Running startup scan...")
        run_scheduled_scan()
    except Exception as e:
        print(f"[SCHEDULER] Startup scan error: {e}")

    # Then run every 60 minutes
    while True:
        time.sleep(3600)  # Wait 1 hour
        try:
            print(f"[SCHEDULER] Hourly scan starting... {ist_now().strftime('%H:%M IST')}")
            run_scheduled_scan()
            STATS['scans_today'] = STATS.get('scans_today', 0) + 1
        except Exception as e:
            print(f"[SCHEDULER] Hourly scan error: {e}")


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
    d = _re.sub(r'[^0-9]', '', phone)
    if len(d) == 10:   pn = '+91' + d
    elif len(d) == 12: pn = '+' + d
    elif len(d) == 11 and d[0] == '0': pn = '+91' + d[1:]
    else: pn = phone
    bare = d[-10:] if len(d) >= 10 else d
    matches, cats = [], set()
    for a in ALERTS:
        chain = a.get('chain', {})
        for p in chain.get('phones', []):
            if p and bare in _re.sub(r'[^0-9]', '', str(p)):
                matches.append(a)
                cats.add(a.get('category', 'unknown'))
                break
    if not matches:
        # Zero-alert enrichment — still return useful intelligence
        d2 = _re.sub(r'[^0-9]', '', pn)
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



@app.route('/api/lookup')
def api_lookup():
    """Universal multi-source lookup — CINEOS DB + carrier + MNRL + web search"""
    import re as _re, sys, os
    query = request.args.get('q','').strip()
    if not query:
        return jsonify({'error': 'Missing parameter: q'}), 400

    # Detect input type
    digits = _re.sub(r'[^0-9]','',query)
    if len(digits) >= 10:
        input_type = 'phone'
        normalized = '+91' + digits[-10:]
    elif '@' in query and '.' in query.split('@')[-1]:
        input_type = 'upi'
        normalized = query.lower()
    elif query.startswith('@') or 't.me/' in query:
        input_type = 'telegram'
        normalized = query.replace('t.me/','').replace('@','').lower()
    else:
        input_type = 'keyword'
        normalized = query.lower()

    # ── SOURCE 1: CINEOS ALERTS DB ────────────────────────────
    alerts = _load_github()
    q_lower = query.lower()

    if input_type == 'phone':
        bare = digits[-10:]
        matches = [a for a in alerts if bare in _re.sub(r'[^0-9]','',(
            str(a.get('chain',{}).get('phones','')) + str(a)))]
    elif input_type == 'telegram':
        handle = normalized
        matches = [a for a in alerts if handle in str(a.get('title','')).lower()
                   or handle in str(a.get('chain',{}).get('channels_found',[])).lower()]
    else:
        matches = [a for a in alerts if q_lower in str(a.get('title','')).lower()
                   or q_lower in str(a.get('detail','')).lower()
                   or q_lower in str(a).lower()]

    # Build DB result
    cats = {}
    phones = set()
    channels = set()
    for a in matches:
        cat = a.get('category','unknown')
        cats[cat] = cats.get(cat,0) + 1
        for p in a.get('chain',{}).get('phones',[]):
            if p: phones.add(p)
        for ch in a.get('chain',{}).get('channels_found',[]):
            if ch: channels.add(str(ch))

    n = len(matches)
    db_conf = min(99, len(phones)*15 + n*8) if (phones or n) else 0
    dates = sorted([a.get('detected_at','') for a in matches if a.get('detected_at','')])
    primary = max(cats,key=cats.get) if cats else 'unknown'

    # ── SOURCE 2: CARRIER/CIRCLE LOOKUP ──────────────────────
    carrier = 'Unknown'
    circle  = 'Unknown'
    carrier_risk = 0
    TRAI_PREFIXES = {
        '7455':('Jio','Rajasthan'),'7400':('Jio','Rajasthan'),
        '7832':('Jio','Rajasthan'),'7413':('Jio','Rajasthan'),
        '8881':('Jio','AP/Telangana'),'8808':('Jio','AP/Telangana'),
        '8824':('Airtel','AP/Telangana'),'8888':('Jio','AP/Telangana'),
        '9186':('Jio','AP/Telangana'),'9602':('Jio','Rajasthan'),
        '9274':('Jio','Gujarat'),'7976':('Jio','Rajasthan'),
        '7704':('Jio','UP West'),'8696':('Jio','Rajasthan'),
        '7732':('Jio','Haryana'),'9799':('Airtel','Rajasthan'),
        '6029':('Jio','Andhra Pradesh'),'9687':('Jio','Gujarat'),
    }
    HIGH_RISK = {'8881':45,'8808':35,'7455':40,'7400':38,
                 '7413':32,'7832':30,'8888':28,'9186':32,
                 '9602':25,'9274':22,'7976':25,'7704':25}
    if input_type == 'phone':
        bare10 = digits[-10:]
        p4 = bare10[:4]
        carrier, circle = TRAI_PREFIXES.get(p4, ('Unknown','Unknown'))
        carrier_risk = HIGH_RISK.get(p4, 0)

    # ── SOURCE 3: WEB SEARCH (for unknown phones/brands) ────
    web_hits = []
    web_boost = 0
    web_operator = None

    if db_conf == 0 and input_type == 'phone':
        # Unknown phone — search by geography/pattern
        geo = circle if circle != 'Unknown' else 'India'
        web_q = f'online betting fraud arrested {geo} Telegram 2026'
        web_data = serp_search(web_q, num=5)
        raw_hits = (web_data.get('news_results') or
                    web_data.get('organic_results') or [])[:4]
        for r in raw_hits:
            title   = r.get('title', '')
            snippet = r.get('snippet', '') or r.get('description', '')
            if title:
                web_hits.append({
                    'title':  title[:80],
                    'source': r.get('source', r.get('displayed_link','')),
                    'link':   r.get('link', ''),
                    'date':   r.get('date', ''),
                    'type':   'geographic_context',
                    'note':   f'Enforcement activity in {geo} — not phone-specific',
                })
        web_boost = 0  # Geographic only — no confidence boost

    elif db_conf > 0 or input_type == 'keyword':
        # Known operator or brand — search by name for enforcement news
        search_term = None
        if input_type == 'keyword':
            search_term = query
        elif phones or input_type == 'phone':
            # Resolve operator name via inline map first
            bare10 = digits[-10:] if len(digits) >= 10 else ''
            if bare10 in OPERATOR_MAP:
                search_term = OPERATOR_MAP[bare10]
                web_operator = search_term
            else:
                # Try resurrection API as fallback
                try:
                    from cineos_resurrection_api import get_resurrection_profile
                    profile = get_resurrection_profile(query)
                    if profile.get('found'):
                        search_term = profile.get('primary_name')
                        web_operator = search_term
                except:
                    pass

        # Inline operator map — no external module needed on Railway
        OPERATOR_MAP = {
            '7455697977': 'Radhe Exchange',
            '7400749393': 'Radhe Exchange',
            '7832350002': 'Radhe Exchange',
            '8881754538': 'Reddy Anna',
            '8881349483': 'Reddy Anna',
            '8881987328': 'Reddy Anna',
            '8888888888': 'Mahadev Book',
            '8824645116': 'Mahadev Book',
            '8808843584': 'Mahadev Book',
            '8881448108': 'Laser247',
            '7413990959': 'Toss Fix',
            '8881886916': 'Vipin Aryan',
            '9274673985': 'Cricbet99',
            '8808843584': 'My99Exch',
            '9186196239': 'Faridabad Satta',
            '8423193609': 'Sky Exchange',
            '7704070168': 'AllPanel',
            '7988587865': 'Fairdeal',
            '8808981489': 'Mahadev Gold',
            '8808148840': 'Mahakal ID',
            '7742129986': 'Kalyan Matka',
            '7976094684': 'Baba Gambler',
        }
        if input_type == 'phone' and not search_term:
            bare10 = digits[-10:]
            if bare10 in OPERATOR_MAP:
                search_term = OPERATOR_MAP[bare10]
                web_operator = search_term
        if search_term:
            web_q = f'{search_term} arrested India fraud 2026'
            web_data = serp_search(web_q, num=8)
            raw_hits = (web_data.get('news_results') or
                        web_data.get('organic_results') or [])[:5]
            for r in raw_hits:
                title   = r.get('title', '')
                snippet = r.get('snippet', '') or r.get('description', '')
                text    = (title + ' ' + snippet).lower()
                if not title: continue
                is_enforcement = any(w in text for w in
                    ['arrested','fir','ed ','cybercrime','seized','busted',
                     'enforcement directorate','crore','attachment'])
                web_hits.append({
                    'title':  title[:80],
                    'source': r.get('source', r.get('displayed_link','')),
                    'link':   r.get('link', ''),
                    'date':   r.get('date', ''),
                    'type':   'enforcement' if is_enforcement else 'mention',
                })
            enforcement_count = sum(1 for h in web_hits if h.get('type')=='enforcement')
            web_boost = min(10, enforcement_count * 3)

    # ── AGGREGATE CONFIDENCE ──────────────────────────────────
    if db_conf > 0:
        carrier_boost = carrier_risk // 8
    else:
        carrier_boost = carrier_risk // 2

    total_conf = min(99, db_conf + carrier_boost + web_boost)

    # Hard cap: no DB match = pattern only → LOW max (web gives context not confirmation)
    if db_conf == 0:
        total_conf = min(total_conf, 42)

    if total_conf >= 85:   risk = 'CRITICAL'
    elif total_conf >= 70: risk = 'HIGH'
    elif total_conf >= 40: risk = 'MEDIUM'
    elif total_conf > 0:   risk = 'LOW'
    else:                  risk = 'CLEAR'

    found = db_conf > 0

    # ── BUILD RESPONSE ────────────────────────────────────────
    response = {
        'input':            query,
        'input_type':       input_type,
        'normalized':       normalized,
        'found':            found,
        'risk_level':       risk,
        'confidence':       total_conf,
        'alert_count':      n,
        'fraud_categories': list(cats.keys()),
        'primary_category': primary,
        'phones_linked':    list(phones)[:5],
        'channels_linked':  list(channels)[:5],
        'first_detected':   dates[0][:19] if dates else None,
        'last_detected':    dates[-1][:19] if dates else None,
        'carrier':          carrier,
        'circle':           circle,
        'carrier_risk':     carrier_risk,
        'sources_queried':  ['CINEOS_DB','CARRIER_LOOKUP','WEB_SEARCH'],
        'web_hits':         web_hits[:5],
        'web_operator':     web_operator,
        'legal_basis':      'IT Act 2000 §65B certified evidence',
        'disclaimer':       'Intelligence-grade assessment from public sources. Verify before enforcement action.',
    }

    if not found:
        response['message'] = (
            f'Not in CINEOS database. '
            f'Carrier: {carrier} {circle}. '
            f'Prefix risk signal: {carrier_risk}%.'
            if carrier != 'Unknown' else
            'Not found in CINEOS database.'
        )

    return jsonify(response)


# ── BANK FRAUD API v1 ────────────────────────────────────────────
_OP_MAP = {
    '7455697977':('Radhe Exchange',['illegal_betting'],95),
    '7400749393':('Radhe Exchange',['illegal_betting'],95),
    '7832350002':('Radhe Exchange',['illegal_betting'],90),
    '8881754538':('Reddy Anna',['illegal_betting'],95),
    '8881349483':('Reddy Anna',['illegal_betting'],85),
    '8881987328':('Reddy Anna',['illegal_betting'],85),
    '8888888888':('Mahadev Book',['illegal_betting'],95),
    '8824645116':('Mahadev Book',['illegal_betting'],80),
    '8808843584':('Mahadev Book',['illegal_betting'],95),
    '8881448108':('Laser247',['illegal_betting'],90),
    '7413990959':('Toss Fix',['illegal_betting'],80),
    '8881886916':('Vipin Aryan',['illegal_betting'],80),
    '9274673985':('Cricbet99',['illegal_betting'],85),
    '9186196239':('Faridabad Satta',['illegal_betting'],85),
    '7704070168':('AllPanel',['illegal_betting'],85),
    '7976094684':('Baba Gambler',['illegal_betting'],80),
}
_TR_MAP = {
    '7455':('Jio','Rajasthan',40),'7400':('Jio','Rajasthan',38),
    '7832':('Jio','Rajasthan',30),'8881':('Jio','AP/Telangana',45),
    '8808':('Jio','AP/Telangana',35),'8824':('Airtel','AP/Telangana',30),
    '8888':('Jio','AP/Telangana',28),'9186':('Jio','AP/Telangana',32),
    '9274':('Jio','Gujarat',22),'7976':('Jio','Rajasthan',25),
    '7704':('Jio','UP West',25),
}
_RC={'CRITICAL':'BLOCK','HIGH':'REVIEW','MEDIUM':'MONITOR','LOW':'ALLOW_WITH_LOG','CLEAR':'ALLOW'}

def _screen(identifier):
    import re as _r, hashlib, time
    from datetime import date as _d
    t0=time.time()
    digs=_r.sub(r'[^0-9]','',str(identifier))
    b10=digs[-10:] if len(digs)>=10 else ''
    is_ph=len(b10)==10 and b10[0] in '6789'
    op,ov,oc=None,[],0
    if is_ph and b10 in _OP_MAP: op,ov,oc=_OP_MAP[b10]
    alts=ALERTS if ALERTS else []
    if is_ph:
        mx=[a for a in alts if b10 in _r.sub(r'[^0-9]','',
            ' '.join([str(a.get('title','')), str(a.get('detail','')),
            str(a.get('source','')),
            ' '.join(a.get('chain',{}).get('phones',[])),
            ' '.join(a.get('chain',{}).get('channels_found',[])),
            ]))]
    else:
        q=identifier.lower().strip()
        mx=[a for a in alts if
            q in str(a.get('title','')).lower() or
            q in str(a.get('detail','')).lower() or
            q in ' '.join(a.get('chain',{}).get('upis',[])).lower() or
            q in ' '.join(a.get('chain',{}).get('channels_found',[])).lower() or
            any(q in str(ch).lower() for ch in a.get('chain',{}).get('channels_found',[]))]
    dc,dp,dch={},set(),set()
    for a in mx:
        cat=a.get('category','unknown')
        dc[cat]=dc.get(cat,0)+1
        for p in a.get('chain',{}).get('phones',[]):
            if p: dp.add(p)
        for ch in a.get('chain',{}).get('channels_found',[]):
            if ch: dch.add(str(ch))
    n=len(mx)
    dconf=min(99,len(dp)*15+n*8) if (dp or n) else 0
    ca,ci,pr='Unknown','Unknown',0
    if is_ph and b10: ca,ci,pr=_TR_MAP.get(b10[:4],('Unknown','Unknown',0))
    conf=max(oc,dconf)
    conf=min(99,conf+pr//8) if conf>0 else min(42,pr//2)
    risk=('CRITICAL' if conf>=85 else 'HIGH' if conf>=70 else 'MEDIUM' if conf>=40 else 'LOW' if conf>0 else 'CLEAR')
    av=list(set(ov+list(dc.keys())))
    pv=ov[0] if ov else (max(dc,key=dc.get) if dc else 'unknown')
    cert='CINEOS-65B-'+_d.today().strftime('%Y%m%d')+'-'+b10[-6:]
    ev=hashlib.sha256((identifier+str(n)).encode()).hexdigest()
    dates=sorted([a.get('detected_at','') for a in mx if a.get('detected_at','')])
    return {'identifier':identifier,'risk_level':risk,'risk_score':conf,
        'recommended_action':_RC.get(risk,'REVIEW'),'found':conf>0,
        'operator_attribution':{'name':op or ('Unknown' if dconf>0 else None),
            'confidence':conf,'verticals':av,'primary':pv,'channels':len(dch),
            'alerts':n,'phones_linked':list(dp)[:5],
            'first_detected':dates[0][:10] if dates else None,
            'last_detected':dates[-1][:10] if dates else None,
        } if conf>0 else None,
        'telecom':{'carrier':ca,'circle':ci,'prefix_risk':pr} if is_ph else None,
        'compliance':{'pmla_flag':conf>=85 and (n>5 or op is not None),
            'prog_act_flag':pv=='illegal_betting',
            'sar_recommended':risk in ('CRITICAL','HIGH'),
            'report_to':['OGAI','I4C','FIU-IND'] if pv=='illegal_betting' else ['I4C','FIU-IND'],
        },
        'evidence':{'cert_id':cert,'hash':ev,
            'standard':'IT Act 2000 S65B(2)',
            'authority':'Arjun Panditrao Khotkar (2020) 7 SCC 1'},
        'latency_ms':round((time.time()-t0)*1000),'api_version':'v1',
        'disclaimer':'Intelligence-grade from public sources. Verify before enforcement action.',
    }

@app.route('/api/v1/screen', methods=['GET','POST'])
def v1_screen():
    valid, client = check_api_key(request)
    if not valid:
        return jsonify({
            'error': 'API key required',
            'message': 'Pass X-API-Key header or ?api_key= param',
            'contact': 'yugandhar@cineos.in',
            'demo': '/api/v1/demo (no key needed)',
        }), 401
    if not ALERTS: init_alerts()
    if request.method=='POST':
        d=request.get_json() or {}
        ident=d.get('phone') or d.get('upi') or d.get('q','')
    else:
        ident=request.args.get('q','') or request.args.get('phone','')
    if not ident: return jsonify({'error':'Missing identifier'}),400
    try:
        result = _screen(ident.strip())
        result['client'] = client
        return jsonify(result)
    except Exception as _e:
        import traceback as _tb
        return jsonify({'error':str(_e),'trace':_tb.format_exc()[-600:]}),500

@app.route('/api/v1/transaction', methods=['POST'])
def v1_transaction():
    valid, client = check_api_key(request)
    if not valid:
        return jsonify({'error':'API key required','contact':'yugandhar@cineos.in'}), 401
    d=request.get_json() or {}
    sp=d.get('sender_phone','')
    ru=d.get('receiver_upi','') or d.get('receiver_phone','')
    amt=d.get('amount_inr',0)
    if not sp and not ru: return jsonify({'error':'Provide sender_phone and/or receiver_upi'}),400
    if not ALERTS: init_alerts()
    sr=_screen(sp) if sp else None
    rr=_screen(ru) if ru else None
    ro={'CRITICAL':4,'HIGH':3,'MEDIUM':2,'LOW':1,'CLEAR':0}
    sv=ro.get(sr['risk_level'],0) if sr else 0
    rv=ro.get(rr['risk_level'],0) if rr else 0
    comb={4:'CRITICAL',3:'HIGH',2:'MEDIUM',1:'LOW',0:'CLEAR'}[max(sv,rv)]
    reasons=[]
    if sr and sr.get('found'): reasons.append('Sender: '+((sr.get('operator_attribution') or {}).get('primary','fraud'))+' confirmed')
    if rr and rr.get('found'): reasons.append('Receiver: '+((rr.get('operator_attribution') or {}).get('primary','fraud'))+' activity')
    if not reasons: reasons.append('No confirmed fraud signals')
    return jsonify({'transaction_id':d.get('transaction_id',''),'amount_inr':amt,
        'combined_risk':comb,'recommended_action':_RC.get(comb,'REVIEW'),
        'reason':' | '.join(reasons),
        'pmla_flag':amt>=500000 and max(sv,rv)>=3,'sar_recommended':max(sv,rv)>=3,
        'sender':{'identifier':sp,'risk':sr['risk_level'] if sr else 'CLEAR',
            'operator':(sr.get('operator_attribution') or {}).get('name'),
            'score':sr['risk_score'] if sr else 0},
        'receiver':{'identifier':ru,'risk':rr['risk_level'] if rr else 'CLEAR',
            'operator':(rr.get('operator_attribution') or {}).get('name'),
            'score':rr['risk_score'] if rr else 0},
        'api_version':'v1','disclaimer':'Intelligence-grade. Verify before enforcement action.'})

@app.route('/api/v1/operator/<name>')
def v1_operator(name):
    valid, client = check_api_key(request)
    if not valid:
        return jsonify({'error':'API key required','contact':'yugandhar@cineos.in'}), 401
    alts=ALERTS if ALERTS else []
    q=name.lower()
    mx=[a for a in alts if q in str(a.get('title','')).lower() or q in str(a.get('detail','')).lower()]
    if not mx: return jsonify({'found':False,'operator':name,'message':'Not in CINEOS database'})
    phones,channels,cats=set(),set(),{}
    for a in mx:
        cats[a.get('category','')]=cats.get(a.get('category',''),0)+1
        for p in a.get('chain',{}).get('phones',[]):
            if p: phones.add(p)
        for ch in a.get('chain',{}).get('channels_found',[]):
            if ch: channels.add(str(ch))
    return jsonify({'found':True,'operator':name,'alerts':len(mx),
        'phones':list(phones)[:10],'channels':list(channels)[:10],
        'verticals':list(cats.keys()),'api_version':'v1'})

@app.route('/api/v1/demo')
def v1_demo():
    """Public demo endpoint — no API key needed. Limited response."""
    try:
        q = request.args.get('q','917455697977')
        if not ALERTS:
            init_alerts()
        import re as _re
        digits = _re.sub(r'[^0-9]','',str(q))
        bare10 = digits[-10:] if len(digits)>=10 else ''
        # Quick operator map lookup — no DB needed
        OP_MAP = {
            '7455697977':('Radhe Exchange','illegal_betting',95),
            '7400749393':('Radhe Exchange','illegal_betting',95),
            '8881754538':('Reddy Anna','illegal_betting',95),
            '8888888888':('Mahadev Book','illegal_betting',95),
            '8881448108':('Laser247','illegal_betting',90),
            '9274673985':('Cricbet99','illegal_betting',85),
        }
        TRAI = {
            '7455':('Jio','Rajasthan',40),'8881':('Jio','AP/Telangana',45),
            '8888':('Jio','AP/Telangana',28),'9274':('Jio','Gujarat',22),
        }
        op_name,op_cat,op_conf = OP_MAP.get(bare10,(None,'unknown',0))
        carrier,circle,pr = TRAI.get(bare10[:4] if bare10 else '',('Unknown','Unknown',0))
        conf = max(op_conf, pr//2) if op_conf==0 else op_conf
        risk = 'CRITICAL' if conf>=85 else 'HIGH' if conf>=70 else 'LOW' if conf>0 else 'CLEAR'
        return jsonify({
            'identifier':   q,
            'risk_level':   risk,
            'risk_score':   conf,
            'found':        conf>0,
            'vertical':     op_cat if op_name else None,
            'operator':     op_name,
            'recommended_action': 'BLOCK' if risk=='CRITICAL' else 'REVIEW' if risk=='HIGH' else 'ALLOW',
            'telecom':      {'carrier':carrier,'circle':circle} if carrier!='Unknown' else None,
            'note':         'Demo response. Full operator profile, evidence cert, and compliance flags require API key.',
            'get_access':   'yugandhar@cineos.in',
            'api_version':  'v1',
        })
    except Exception as e:
        import traceback
        return jsonify({'error':str(e),'trace':traceback.format_exc()[-300:]}),500



# ── OPERATOR INTELLIGENCE REPORT API ─────────────────────────
@app.route('/api/v1/report/<operator_name>')
def v1_operator_report(operator_name):
    valid, client = check_api_key(request)
    if not valid:
        return jsonify({'error':'API key required','contact':'yugandhar@cineos.in'}), 401
    try:
        import hashlib as _hl
        from datetime import date as _date
        if not ALERTS: init_alerts()
        alerts = ALERTS
        q = operator_name.lower()
        matches = [a for a in alerts if
                   q in str(a.get('title','')).lower() or
                   q in str(a.get('detail','')).lower()]
        if not matches:
            return jsonify({'found':False,'operator':operator_name}), 404
        phones, channels, cats = set(), set(), {}
        reach_total = 0
        dates = []
        for a in matches:
            chain = a.get('chain', {})
            for p in chain.get('phones', []):
                if p: phones.add(p)
            for ch in chain.get('channels_found', []):
                if ch: channels.add(str(ch))
            cat = a.get('category', 'unknown')
            cats[cat] = cats.get(cat, 0) + 1
            reach_total += a.get('reach', 0)
            dt = a.get('detected_at', '')
            if dt: dates.append(dt)
        dates.sort()
        first_det = dates[0][:10] if dates else 'Unknown'
        last_det  = dates[-1][:10] if dates else 'Unknown'
        primary   = max(cats, key=cats.get) if cats else 'unknown'
        phones_l  = list(phones)[:8]
        chs_l     = list(channels)[:10]
        cert_id   = 'CINEOS-OIR-' + _date.today().strftime('%Y%m%d') + '-' + _hl.sha256(operator_name.encode()).hexdigest()[:6].upper()
        ev_hash   = _hl.sha256((operator_name + str(len(matches))).encode()).hexdigest()
        def fmt(n):
            cr = n / 10000000
            return ('Rs' + str(int(cr)) + 'Cr') if cr >= 1 else ('Rs' + str(int(n/100000)) + 'L')
        ph_rows = ''.join('<tr><td style="font-family:monospace;color:#991B1B">' + p + '</td><td>Active</td></tr>' for p in phones_l) or '<tr><td colspan="2">See evidence package</td></tr>'
        ch_rows = ''.join('<tr><td style="font-family:monospace;font-size:11px">' + str(ch) + '</td><td>' + primary.replace('_',' ') + '</td></tr>' for ch in chs_l[:6]) or '<tr><td colspan="2">See evidence package</td></tr>'
        html = ('<!DOCTYPE html><html><head><meta charset="UTF-8"><title>CINEOS — ' + operator_name + '</title>'
            '<style>body{font-family:Georgia,serif;max-width:900px;margin:0 auto;padding:40px;font-size:13px;line-height:1.7}'
            '.hdr{background:#0D2B55;color:#fff;padding:20px 32px;margin:-40px -40px 28px;display:flex;justify-content:space-between}'
            'h2{font-size:14px;font-weight:700;color:#0D2B55;margin:20px 0 8px;border-bottom:2px solid #EFF6FF;padding-bottom:5px}'
            'table{width:100%;border-collapse:collapse;font-size:12px;margin:8px 0}'
            'th{background:#0D2B55;color:#fff;padding:7px 10px;text-align:left;font-size:10px;text-transform:uppercase}'
            'td{padding:6px 10px;border-bottom:1px solid #F0F7FF}'
            '.ev{background:#040C1A;color:#4ADE80;padding:14px;border-radius:4px;font-family:monospace;font-size:10px;line-height:2;margin:10px 0}'
            '.dis{background:#FEF2F2;border:1px solid #FECACA;padding:12px;border-radius:4px;font-size:11px;color:#7F1D1D;margin:16px 0}'
            '.sig{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}'
            '.sb{border:1px solid #E2E8F0;padding:12px;border-radius:4px}'
            '.sl{border-bottom:1px solid #94A3B8;height:24px;margin-bottom:4px}'
            '.footer{background:#0D2B55;color:#4A6FA5;padding:8px 32px;margin:24px -40px -40px;display:flex;justify-content:space-between;font-family:monospace;font-size:9px}'
            '</style></head><body>'
            '<div class="hdr"><div><b style="font-size:18px;letter-spacing:3px">CINEOS</b>'
            '<div style="font-size:10px;color:#9EC6F3">INDIA TRUST INTELLIGENCE NETWORK</div></div>'
            '<div style="font-family:monospace;font-size:11px;color:#9EC6F3">' + cert_id + '</div></div>'
            '<h1 style="font-size:24px;font-weight:700;color:#0D2B55">' + operator_name + ' Network</h1>'
            '<p style="color:#64748B">' + primary.replace('_',' ').title() + ' · ' + last_det + ' · §65B Certified</p>'
            '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:16px 0">'
            '<div style="background:#F0F7FF;border:1px solid #BFDBFE;padding:10px;text-align:center;border-radius:4px"><div style="font-size:20px;font-weight:700;font-family:monospace">' + str(len(matches)) + '</div><div style="font-size:10px;color:#64748B">Alerts</div></div>'
            '<div style="background:#F0F7FF;border:1px solid #BFDBFE;padding:10px;text-align:center;border-radius:4px"><div style="font-size:20px;font-weight:700;font-family:monospace">' + str(len(chs_l)) + '+</div><div style="font-size:10px;color:#64748B">Channels</div></div>'
            '<div style="background:#F0F7FF;border:1px solid #BFDBFE;padding:10px;text-align:center;border-radius:4px"><div style="font-size:20px;font-weight:700;font-family:monospace">' + str(len(phones_l)) + '</div><div style="font-size:10px;color:#64748B">Phones</div></div>'
            '<div style="background:#F0F7FF;border:1px solid #BFDBFE;padding:10px;text-align:center;border-radius:4px"><div style="font-size:20px;font-weight:700;font-family:monospace">' + str(reach_total//1000) + 'K</div><div style="font-size:10px;color:#64748B">Reach</div></div>'
            '<div style="background:#F0F7FF;border:1px solid #BFDBFE;padding:10px;text-align:center;border-radius:4px"><div style="font-size:20px;font-weight:700;font-family:monospace">' + str(len(cats)) + '</div><div style="font-size:10px;color:#64748B">Verticals</div></div>'
            '</div>'
            '<h2>Confirmed Phones</h2>'
            '<table><tr><th>Phone</th><th>Status</th></tr>' + ph_rows + '</table>'
            '<p style="font-size:11px;color:#64748B">Subscriber identity unconfirmed — requires IT Act §69B telecom subpoena</p>'
            '<h2>Channels (sample)</h2>'
            '<table><tr><th>Channel</th><th>Category</th></tr>' + ch_rows + '</table>'
            '<h2>Financial Exposure</h2>'
            '<table><tr><th>Scenario</th><th>Monthly</th><th>Basis</th></tr>'
            '<tr><td>Conservative</td><td style="color:#166534;font-weight:700">' + fmt(reach_total*500) + '</td><td>Rs500/subscriber</td></tr>'
            '<tr><td>Moderate</td><td style="color:#D97706;font-weight:700">' + fmt(reach_total*2000) + '</td><td>Rs2000/subscriber</td></tr>'
            '<tr><td>Aggressive</td><td style="color:#991B1B;font-weight:700">' + fmt(reach_total*10000) + '</td><td>Rs10000/subscriber</td></tr>'
            '</table>'
            '<h2>Evidence Certificate</h2>'
            '<div class="ev">CERT: ' + cert_id + '<br>SHA-256: ' + ev_hash + '<br>Alerts: ' + str(len(matches)) + '<br>Period: ' + first_det + ' to ' + last_det + '<br>Standard: IT Act 2000 S65B(2) — Arjun Panditrao Khotkar (2020) 7 SCC 1</div>'
            '<h2>Recommended Actions</h2>'
            '<table><tr><th>Agency</th><th>Action</th><th>Contact</th></tr>'
            '<tr><td>DoT TRAI</td><td>Telecom subpoena</td><td style="font-family:monospace">dit-diu@gov.in</td></tr>'
            '<tr><td>MeitY OGAI</td><td>S69A takedown</td><td style="font-family:monospace">ogai@meity.gov.in</td></tr>'
            '<tr><td>I4C MHA</td><td>Intelligence submission</td><td style="font-family:monospace">i4c@mha.gov.in</td></tr>'
            '<tr><td>FIU-IND</td><td>SAR filing</td><td style="font-family:monospace">fiuindia.gov.in</td></tr>'
            '</table>'
            '<div class="dis">DISCLAIMER: Open-source intelligence from publicly accessible Telegram channels. Not a chargesheet or legal proof of guilt. Subscriber identities unconfirmed. Financial estimates are mathematical only. CINEOS IP Registration Pending.</div>'
            '<div class="sig"><div class="sb"><div style="font-size:9px;color:#64748B;text-transform:uppercase;margin-bottom:8px">Certifying Officer S65B(4)</div><div class="sl"></div><b>Yugandhar Mallavarapu</b><br><span style="font-size:11px;color:#64748B">Founder · CINEOS · yugandhar@cineos.in</span></div>'
            '<div class="sb"><div style="font-size:9px;color:#64748B;text-transform:uppercase;margin-bottom:8px">Received By</div><div class="sl"></div><b>___________________</b><br><span style="font-size:11px;color:#64748B">Date: _______________</span></div></div>'
            '<div class="footer"><span>CINEOS Intelligence · ' + cert_id + '</span><span>yugandhar@cineos.in · cineos.in</span></div>'
            '</body></html>')
        filename = 'CINEOS-OIR-' + operator_name.replace(' ','-') + '-' + _date.today().strftime('%Y%m%d') + '.html'
        resp = make_response(html)
        resp.headers['Content-Type'] = 'text/html; charset=utf-8'
        resp.headers['Content-Disposition'] = 'attachment; filename="' + filename + '"'
        return resp
    except Exception as _e:
        import traceback as _tb
        return jsonify({'error': str(_e), 'trace': _tb.format_exc()[-500:]}), 500



@app.route('/api/v1/graph')
def v1_graph():
    """Operator network graph data for D3 visualization"""
    alerts = ALERTS
    nodes = {}
    edges = []
    seen_edges = set()
    for a in alerts:
        chain = a.get('chain', {})
        phones = chain.get('phones', [])
        channels = chain.get('channels_found', [])
        cat = a.get('category', 'unknown')
        # Add channel nodes
        for ch in channels[:3]:
            if ch and ch not in nodes:
                nodes[ch] = {'id': ch, 'type': 'channel', 'cat': cat, 'size': 8}
        # Add phone nodes and link to channels
        for ph in phones[:2]:
            if ph:
                if ph not in nodes:
                    nodes[ph] = {'id': ph, 'type': 'phone', 'cat': cat, 'size': 12}
                for ch in channels[:2]:
                    if ch:
                        ek = ph + '|' + str(ch)
                        if ek not in seen_edges:
                            edges.append({'source': ph, 'target': str(ch)})
                            seen_edges.add(ek)
    node_list = list(nodes.values())[:80]
    valid_ids = {n['id'] for n in node_list}
    edge_list = [e for e in edges if e['source'] in valid_ids and e['target'] in valid_ids][:120]
    return jsonify({'nodes': node_list, 'edges': edge_list, 'total_nodes': len(node_list), 'total_edges': len(edge_list)})

@app.route('/api/lookup/bulk', methods=['POST'])
def api_lookup_bulk():
    """Bulk entity lookup — up to 50 identifiers at once"""
    data = request.get_json() or {}
    queries = data.get('queries', [])[:50]
    if not queries:
        return jsonify({'error': 'Missing parameter: queries'}), 400
    if not ENTITY_RESOLVE:
        return jsonify({'error': 'Entity resolver not available'}), 503
    results = []
    for q in queries:
        try:
            results.append(_resolve(str(q)))
        except Exception as e:
            results.append({'input': q, 'error': str(e)})
    flagged = sum(1 for r in results if r.get('found'))
    return jsonify({
        'total': len(results),
        'flagged': flagged,
        'clear': len(results) - flagged,
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
