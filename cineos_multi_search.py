"""
CINEOS Multi-Source Intelligence Search Engine
Goes beyond the alerts database to query:
  1. CINEOS internal DB (phones, channels, alerts)
  2. SerpAPI live web search (news, court records)
  3. TRAI MNRL (disconnected numbers check)
  4. WHOIS (domain intelligence)
  5. IndiaMART (seller lookup via SerpAPI)
  6. Pattern intelligence (prefix + carrier)

Input:  Any identifier
Output: Aggregated intelligence from ALL sources
        with source attribution and confidence
"""
import json, re, os, time, hashlib, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5,minutes=30))
SERP_KEY = os.environ.get('SERP_API_KEY',
    '2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1')

# ── TRAI PREFIX DATABASE (offline) ─────────────────────────────
TRAI_PREFIXES = {
    # Format: prefix4: (carrier, circle)
    '7455': ('Jio','Rajasthan'), '7400': ('Jio','Rajasthan'),
    '7832': ('Jio','Rajasthan'), '7413': ('Jio','Rajasthan'),
    '8881': ('Jio','AP/Telangana'), '8808': ('Jio','AP/Telangana'),
    '8824': ('Airtel','AP/Telangana'), '8888': ('Jio','AP/Telangana'),
    '9186': ('Jio','AP/Telangana'), '9602': ('Jio','Rajasthan'),
    '9274': ('Jio','Gujarat'), '9521': ('Airtel','UP East'),
    '7976': ('Jio','Rajasthan'), '7704': ('Jio','UP West'),
    '9818': ('Airtel','Delhi'), '9999': ('Airtel','Delhi'),
    '8383': ('Jio','Delhi'), '8696': ('Jio','Rajasthan'),
    '7732': ('Jio','Haryana'), '6720': ('Jio','Sikkim'),
    '9799': ('Airtel','Rajasthan'), '7665': ('Jio','Rajasthan'),
    '7348': ('Jio','West Bengal'), '9687': ('Jio','Gujarat'),
    '6029': ('Jio','Andhra Pradesh'),
}

HIGH_RISK_PREFIXES = {
    '8881': 45, '8808': 35, '7455': 40, '7400': 38,
    '7413': 32, '7832': 30, '8888': 28, '9186': 32,
    '9602': 25, '9274': 22, '7976': 25, '7704': 25,
}

def normalize_phone(raw):
    d = re.sub(r'[^\d]', '', str(raw))
    if len(d) == 10 and d[0] in '6789': return '+91' + d
    if len(d) == 12 and d[:2] == '91': return '+' + d
    return None

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]

# ── SOURCE 1: CINEOS INTERNAL DB ───────────────────────────────
def search_cineos_db(identifier):
    """Search CINEOS alerts + channels database."""
    try:
        alerts   = json.load(open('reports/alerts/live_alerts.json'))
        channels = json.load(open('reports/all_channels.json'))
    except:
        return {'source': 'CINEOS_DB', 'found': False, 'error': 'DB not loaded'}

    norm_ph = normalize_phone(identifier)
    is_phone = norm_ph is not None
    id_lower = identifier.lower().replace('+91','')

    matched_alerts   = []
    matched_channels = []

    for a in alerts:
        text = str(a)
        if is_phone:
            bare = norm_ph.replace('+','').replace(' ','')[-10:]
            if bare in re.sub(r'[^\d]','',text):
                matched_alerts.append(a)
        else:
            if id_lower in text.lower():
                matched_alerts.append(a)

    for c in channels:
        if is_phone:
            bare = norm_ph.replace('+','').replace(' ','')[-10:]
            if any(bare in p.replace('+','').replace(' ','') 
                   for p in c.get('phones',[])):
                matched_channels.append(c)
        else:
            text = (c.get('username','') + ' ' + 
                   c.get('title','') + ' ' + 
                   str(c.get('bio',''))).lower()
            if id_lower in text:
                matched_channels.append(c)

    phones = list(set(
        p for c in matched_channels 
        for p in c.get('phones',[]) if p
    ))
    cats = list(set(
        a.get('category','') 
        for a in matched_alerts if a.get('category')
    ))
    total_reach = sum(
        c.get('subscribers',0) for c in matched_channels
    )

    dates = sorted([
        a.get('detected_at','') 
        for a in matched_alerts if a.get('detected_at','')
    ])

    return {
        'source':        'CINEOS_DB',
        'found':         len(matched_alerts) > 0 or len(matched_channels) > 0,
        'alert_count':   len(matched_alerts),
        'channel_count': len(matched_channels),
        'phones':        phones[:5],
        'categories':    cats,
        'total_reach':   total_reach,
        'first_seen':    dates[0][:10] if dates else None,
        'last_seen':     dates[-1][:10] if dates else None,
        'confidence':    min(99, len(phones)*15 + len(matched_alerts)*8) if (phones or matched_alerts) else 0,
    }

# ── SOURCE 2: SERP WEB SEARCH ──────────────────────────────────
def search_web(identifier, operator_name=None, max_results=8):
    """Live web search for news, court records, enforcement actions.
    
    KEY INSIGHT: Direct phone number searches fail on Google.
    Always search by operator name or brand when available.
    Fall back to carrier/circle pattern for unknown phones.
    """
    norm_ph = normalize_phone(identifier)
    
    # Build queries based on what we know
    queries = []
    
    if operator_name and operator_name not in ('Unknown operator', 'Unknown', '—'):
        # Best case: we know the operator name
        clean_name = operator_name.replace('Network','').replace('Operator','').strip()
        queries = [
            f'{clean_name} arrested India 2026',
            f'{clean_name} betting fraud India ED 2026',
            f'{clean_name} cybercrime India Telegram',
        ]
    elif norm_ph:
        # Phone present but unknown operator
        # Search by prefix pattern + geography
        bare10 = norm_ph.replace('+91','')
        prefix = bare10[:4]
        carrier_info = TRAI_PREFIXES.get(prefix, ('',''))
        circle = carrier_info[1] if carrier_info else ''
        queries = [
            f'online betting fraud arrested {circle} India 2026',
            f'Telegram betting fraud arrested {circle} cybercrime 2026',
        ]
    else:
        # Brand/keyword search
        queries = [
            f'{identifier} fraud arrested India 2026',
            f'{identifier} cyber crime India arrested',
            f'{identifier} ED PMLA India 2026',
        ]

    results = []
    seen_titles = set()

    for q in queries[:2]:  # 2 queries to save API calls
        try:
            params = {
                'q': q, 'api_key': SERP_KEY,
                'engine': 'google', 'tbm': 'nws',
                'num': 5, 'gl': 'in', 'no_cache': 'true',
            }
            url = 'https://serpapi.com/search?' + urllib.parse.urlencode(params)
            data = json.loads(urllib.request.urlopen(url, timeout=10).read())
            
            for r in data.get('news_results', data.get('organic_results', []))[:4]:
                title = r.get('title','')
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    results.append({
                        'title':   title,
                        'snippet': r.get('snippet','')[:200],
                        'link':    r.get('link',''),
                        'date':    r.get('date',''),
                        'source':  r.get('source',''),
                    })
        except Exception as e:
            pass
        time.sleep(0.5)

    # Classify results
    enforcement_hits = []
    fraud_hits = []
    other_hits = []

    for r in results:
        text = (r['title'] + ' ' + r['snippet']).lower()
        if any(w in text for w in ['arrested','fir','ed ','cybercrime police',
                                    'seized','enforcement directorate']):
            enforcement_hits.append(r)
        elif any(w in text for w in ['fraud','scam','betting','fake','cheating',
                                      'cyber crime','phishing']):
            fraud_hits.append(r)
        else:
            other_hits.append(r)

    return {
        'source':           'WEB_SEARCH',
        'found':            len(results) > 0,
        'total_results':    len(results),
        'enforcement_hits': enforcement_hits,
        'fraud_hits':       fraud_hits,
        'other_hits':       other_hits[:2],
        'high_value':       len(enforcement_hits) > 0,
        'confidence_boost': 20 if enforcement_hits else (10 if fraud_hits else 0),
    }

# ── SOURCE 3: TRAI MNRL CHECK ──────────────────────────────────
def check_mnrl(phone):
    """Check if phone is on TRAI Mobile Number Revocation List."""
    norm = normalize_phone(phone)
    if not norm:
        return {'source': 'TRAI_MNRL', 'found': False, 'error': 'Invalid phone'}

    # Try to load MNRL cache
    mnrl_file = 'reports/trai_mnrl_cache.json'
    mnrl_set = set()

    try:
        if os.path.exists(mnrl_file):
            mnrl_data = json.load(open(mnrl_file))
            mnrl_set = set(mnrl_data.get('numbers', []))
    except:
        pass

    bare10 = norm.replace('+91','')
    is_revoked = bare10 in mnrl_set or norm in mnrl_set

    return {
        'source':     'TRAI_MNRL',
        'found':      True,
        'is_revoked': is_revoked,
        'status':     'REVOKED' if is_revoked else 'ACTIVE',
        'note':       ('Phone is on TRAI MNRL — permanently disconnected. '
                       'If active in fraud channels = identity theft or mule.' 
                       if is_revoked else
                       'Phone not on MNRL revocation list — currently active'),
    }

# ── SOURCE 4: CARRIER/CIRCLE LOOKUP (offline) ──────────────────
def lookup_carrier(phone):
    """Offline TRAI prefix lookup. Upgrade to datayuge API for post-MNP accuracy."""
    norm = normalize_phone(phone)
    if not norm:
        return {'source': 'CARRIER', 'found': False}

    bare10 = norm.replace('+91','')
    prefix4 = bare10[:4]
    prefix3 = bare10[:3]

    carrier, circle = TRAI_PREFIXES.get(prefix4, 
                       TRAI_PREFIXES.get(prefix3, 
                       ('Unknown', 'Unknown')))
    risk_score = HIGH_RISK_PREFIXES.get(prefix4, 0)

    return {
        'source':     'CARRIER_LOOKUP',
        'found':      carrier != 'Unknown',
        'carrier':    carrier,
        'circle':     circle,
        'prefix':     prefix4,
        'risk_score': risk_score,
        'risk_note':  (f'Prefix {prefix4} matches known fraud operator series '
                       f'({circle} {carrier})' if risk_score >= 25 else
                       f'Prefix {prefix4} — standard telecom allocation'),
    }

# ── SOURCE 5: WHOIS (for domains) ──────────────────────────────
def lookup_whois(domain):
    """WHOIS lookup for domain intelligence."""
    try:
        import subprocess
        result = subprocess.run(
            ['python3','-c',
             f'import whois; w=whois.whois("{domain}"); '
             f'print(w.registrar,"|",w.creation_date,"|",w.country)'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split('|')
            return {
                'source':    'WHOIS',
                'found':     True,
                'registrar': parts[0].strip() if parts else 'Unknown',
                'created':   str(parts[1].strip())[:10] if len(parts)>1 else 'Unknown',
                'country':   parts[2].strip() if len(parts)>2 else 'Unknown',
            }
    except:
        pass
    return {'source': 'WHOIS', 'found': False}

# ── SOURCE 6: INDIAMART SEARCH ─────────────────────────────────
def search_indiamart(identifier):
    """Search IndiaMART for fraud seller listings."""
    try:
        query = f'site:indiamart.com {identifier}'
        params = {
            'q': query, 'api_key': SERP_KEY,
            'engine': 'google', 'num': 5, 'no_cache': 'true',
        }
        url = 'https://serpapi.com/search?' + urllib.parse.urlencode(params)
        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
        results = data.get('organic_results',[])[:3]
        return {
            'source':  'INDIAMART',
            'found':   len(results) > 0,
            'results': [{'title':r.get('title',''), 
                         'link':r.get('link',''),
                         'snippet':r.get('snippet','')[:150]} 
                        for r in results],
        }
    except:
        return {'source': 'INDIAMART', 'found': False}

# ── MASTER SEARCH ──────────────────────────────────────────────
def full_search(raw_input, sources=None):
    """
    Run all intelligence sources and aggregate results.
    """
    if sources is None:
        sources = ['cineos', 'carrier', 'mnrl', 'web']

    print(f'\nCINEOS MULTI-SOURCE INTELLIGENCE SEARCH')
    print(f'Query: {raw_input}')
    print(f'Time:  {datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}')
    print('='*60)

    results = {}
    start = time.time()

    # Always run CINEOS DB first (fast, free)
    print('[1/4] Searching CINEOS database...')
    results['cineos'] = search_cineos_db(raw_input)
    print(f'      Found: {results["cineos"]["found"]} · '
          f'Alerts: {results["cineos"]["alert_count"]} · '
          f'Channels: {results["cineos"]["channel_count"]}')

    # Carrier lookup (instant, offline)
    norm_ph = normalize_phone(raw_input)
    if norm_ph and 'carrier' in sources:
        print('[2/4] Carrier/circle lookup...')
        results['carrier'] = lookup_carrier(raw_input)
        c = results['carrier']
        print(f'      {c["carrier"]} · {c["circle"]} · Risk: {c["risk_score"]}%')

    # MNRL check (fast, local)
    if norm_ph and 'mnrl' in sources:
        print('[3/4] TRAI MNRL revocation check...')
        results['mnrl'] = check_mnrl(raw_input)
        print(f'      Status: {results["mnrl"]["status"]}')

    # Web search (slower, uses API)
    if 'web' in sources:
        print('[4/4] Live web search (news + enforcement)...')
        # Resolve operator name for better search quality
        op_name = None
        if results.get('cineos',{}).get('found'):
            cats = results['cineos'].get('categories',[])
            # Try to get operator name from channels
            try:
                from cineos_resurrection_api import get_resurrection_profile
                profile = get_resurrection_profile(raw_input)
                op_name = profile.get('primary_name')
            except:
                pass
        results['web'] = search_web(raw_input, operator_name=op_name)
        
        # IMPORTANT: If web search ran on geography (no operator name found),
        # mark results as geographic context, not phone-specific confirmation
        if not op_name and results['cineos'].get('alert_count', 0) == 0:
            results['web']['geographic_only'] = True
            results['web']['confidence_boost'] = 0  # No boost for geographic hits
            for hit in results['web'].get('enforcement_hits', []):
                hit['note'] = 'Geographic context — arrests in same area, not this specific phone'
            # Reclassify enforcement hits as context only
            results['web']['context_hits'] = results['web'].pop('enforcement_hits', [])
            results['web']['enforcement_hits'] = []
        w = results['web']
        print(f'      Results: {w["total_results"]} · '
              f'Enforcement hits: {len(w["enforcement_hits"])}')

    elapsed = time.time() - start

    # ── AGGREGATE CONFIDENCE ──────────────────────────────────
    base_conf = results.get('cineos',{}).get('confidence', 0)
    carrier_risk = results.get('carrier',{}).get('risk_score', 0)
    web_boost = results.get('web',{}).get('confidence_boost', 0)
    mnrl_boost = 15 if results.get('mnrl',{}).get('is_revoked') else 0

    # Carrier boost only applies when NO CINEOS data found
    # Known operator: carrier confirms, doesn't add much
    # Unknown phone: carrier prefix gives pattern signal only
    if base_conf > 0:
        # Already in DB — carrier is confirmation only
        carrier_boost = carrier_risk // 8
    else:
        # Not in DB — carrier prefix is the only signal
        # Cap at MEDIUM level — no hard evidence
        carrier_boost = carrier_risk // 2  # ~20-25% for high-risk prefix

    total_conf = min(99, base_conf + carrier_boost + web_boost + mnrl_boost)
    
    # Cap unknown phones at MEDIUM unless web confirms
    if base_conf == 0 and web_boost == 0 and not mnrl_boost:
        total_conf = min(total_conf, 42)  # Hard cap: pattern-only = LOW

    cineos_found = results.get('cineos',{}).get('found', False)
    web_found = (len(results.get('web',{}).get('enforcement_hits',[])) > 0 or
                 len(results.get('web',{}).get('fraud_hits',[])) > 0)

    if total_conf >= 85:   risk = 'CRITICAL'
    elif total_conf >= 70: risk = 'HIGH'
    elif total_conf >= 40: risk = 'MEDIUM'
    elif total_conf > 0:   risk = 'LOW'
    else:                  risk = 'CLEAR'

    # ── BUILD SUMMARY ─────────────────────────────────────────
    summary = {
        'query':        raw_input,
        'risk_level':   risk,
        'confidence':   total_conf,
        'sources_hit':  sum(1 for r in results.values() if r.get('found')),
        'sources_total':len(results),
        'elapsed_sec':  round(elapsed, 2),
        'results':      results,
        'signals': [],
    }

    # Add signals
    db = results.get('cineos',{})
    if db.get('found'):
        summary['signals'].append(
            f'CINEOS DB: {db["alert_count"]} alerts, '
            f'{db["channel_count"]} channels, '
            f'{db["total_reach"]:,} reach'
        )
    carr = results.get('carrier',{})
    if carr.get('risk_score',0) >= 25:
        summary['signals'].append(carr['risk_note'])
    if results.get('mnrl',{}).get('is_revoked'):
        summary['signals'].append('TRAI MNRL: Number permanently disconnected — active in fraud channels = high risk')
    web = results.get('web',{})
    if web.get('enforcement_hits'):
        summary['signals'].append(
            f'Web: {len(web["enforcement_hits"])} enforcement/arrest news hits found'
        )
    elif web.get('fraud_hits'):
        summary['signals'].append(
            f'Web: {len(web["fraud_hits"])} fraud-related news hits found'
        )

    return summary


def print_summary(summary):
    print()
    print('='*60)
    print(f'RESULT: {summary["risk_level"]} · {summary["confidence"]}% confidence')
    print(f'Sources: {summary["sources_hit"]}/{summary["sources_total"]} returned data')
    print(f'Time: {summary["elapsed_sec"]}s')
    print()
    if summary['signals']:
        print('SIGNALS:')
        for s in summary['signals']:
            print(f'  ⚡ {s}')
    print()

    web = summary['results'].get('web',{})
    if web.get('enforcement_hits'):
        print('ENFORCEMENT/ARREST HITS:')
        for r in web['enforcement_hits'][:3]:
            print(f'  [{r.get("date","")[:10]}] {r["title"][:70]}')
            print(f'    {r["source"]} · {r["link"][:60]}')
    elif web.get('fraud_hits'):
        print('FRAUD-RELATED WEB RESULTS:')
        for r in web['fraud_hits'][:3]:
            print(f'  {r["title"][:70]}')


if __name__ == '__main__':
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else '+917455697977'
    summary = full_search(query)
    print_summary(summary)
