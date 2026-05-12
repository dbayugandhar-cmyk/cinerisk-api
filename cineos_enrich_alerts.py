"""
CINEOS Alert Enrichment
For every alert, extracts and enriches:
  - Name (from WHOIS / channel bio / operator graph)
  - Email (from WHOIS / channel bio)
  - Phone (from graph / channel messages)
  - UPI ID (from channel messages)
  - Address (from WHOIS / Truecaller / ED filings)
"""

import json, re, urllib.request, urllib.parse, time, os
from datetime import datetime

SERP_KEY    = '2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1'
ALERTS_FILE = 'reports/alerts/live_alerts.json'
GRAPH_FILE  = 'reports/fraud_intelligence_graph.json'
CHANNELS_FILE = 'reports/all_channels.json'

def serp_search(query, num=5):
    params = {'q':query,'api_key':SERP_KEY,'engine':'google','num':num,'gl':'in'}
    url = 'https://serpapi.com/search?' + urllib.parse.urlencode(params)
    try:
        return json.loads(urllib.request.urlopen(url, timeout=12).read())
    except:
        return {}

def whois_lookup(domain):
    """Extract registrant details from WHOIS via SerpAPI."""
    data = serp_search(f'whois {domain} registrant email phone address', num=5)
    results = []
    for r in data.get('organic_results', []):
        snippet = r.get('snippet', '')
        results.append(snippet)
    return ' '.join(results)

def extract_emails(text):
    return list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)))

def extract_phones(text):
    phones = re.findall(r'(?:\+91|91|0)?[6-9]\d{9}', text)
    return list(set(phones))

def extract_upis(text):
    upi_re = re.compile(
        r'\b([a-zA-Z0-9.\-_]{2,256}@(?:paytm|gpay|okaxis|ybl|okhdfcbank|'
        r'okicici|oksbi|apl|upi|ibl|axl|hdfcbank|icici|sbi|kotak|'
        r'waaxis|waicici|[a-zA-Z]{2,20}))\b', re.IGNORECASE)
    return list(set(upi_re.findall(text)))

# Load data
print('Loading data...')
alerts   = json.load(open(ALERTS_FILE))
graph    = json.load(open(GRAPH_FILE))
channels = json.load(open(CHANNELS_FILE))

# Build channel lookup
ch_map = {c.get('username','').lower(): c for c in channels}

# Build operator lookup from graph
op_nodes = {k:v for k,v in graph['nodes'].items() if v.get('type') == 'OPERATOR'}
ph_nodes = {k:v for k,v in graph['nodes'].items() if v.get('type') == 'PHONE'}

enriched = 0

for alert in alerts:
    chain    = alert.get('chain', {})
    category = alert.get('category', '')
    title    = alert.get('title', '')

    # Init attribution fields if missing
    if 'attribution' not in alert:
        alert['attribution'] = {
            'name':    '',
            'email':   '',
            'phone':   '',
            'upi':     '',
            'address': '',
            'source':  '',
        }

    attr = alert['attribution']

    # ── Already has registrant from WHOIS ──────────────────
    registrant = chain.get('whois_registrant', '')
    if registrant and not attr['name']:
        # Parse "muthyala naresh — muthyala19@gmail.com"
        parts = re.split(r'[—\-·]', registrant)
        if parts:
            attr['name']   = parts[0].strip()
            attr['source'] = 'WHOIS'
        emails = extract_emails(registrant)
        if emails and not attr['email']:
            attr['email'] = emails[0]

    # ── Get phones from graph nodes ────────────────────────
    channels_in_alert = chain.get('channels_found', [])
    for ch_name in channels_in_alert:
        ch_clean = ch_name.lstrip('@').lower()
        ch = ch_map.get(ch_clean, {})

        # Phone from channel
        phones = ch.get('phones', [])
        if phones and not attr['phone']:
            attr['phone']  = phones[0]
            attr['source'] = attr['source'] or 'channel_scan'

        # UPI from channel
        upis = ch.get('upi_ids', [])
        if upis and not attr['upi']:
            attr['upi']    = upis[0]
            attr['source'] = attr['source'] or 'channel_scan'

    # ── Get phones from graph edges ────────────────────────
    if not attr['phone']:
        for edge in graph.get('edges', []):
            if edge.get('relation') in ('has_phone', 'uses_phone'):
                node = graph['nodes'].get(edge.get('to'), {})
                if node.get('type') == 'PHONE':
                    # Check if this phone is linked to any of our alert's channels
                    from_node = graph['nodes'].get(edge.get('from'), {})
                    if from_node.get('username', '').lower() in [
                        c.lstrip('@').lower() for c in channels_in_alert]:
                        attr['phone']  = node.get('phone', node.get('label',''))
                        attr['source'] = 'fraud_graph'

    # ── Domain squat: enrich via WHOIS search ─────────────
    if category == 'domain_squat' and not attr['email']:
        domain = chain.get('whois_domain', '')
        if domain:
            print(f'  WHOIS enrichment: {domain}...')
            whois_text = whois_lookup(domain)
            emails = extract_emails(whois_text)
            phones = extract_phones(whois_text)
            if emails:
                attr['email']  = emails[0]
                attr['source'] = 'WHOIS_search'
            if phones:
                attr['phone']  = phones[0]
            time.sleep(2)

    # ── Operator name from graph ───────────────────────────
    op_name = chain.get('operator_name', '')
    if op_name and not attr['name']:
        attr['name']   = op_name
        attr['source'] = attr['source'] or 'operator_graph'

    # ── Mark completeness ──────────────────────────────────
    fields_filled = sum(1 for v in [
        attr['name'], attr['email'], attr['phone'],
        attr['upi'], attr['address']
    ] if v)
    attr['completeness'] = f'{fields_filled}/5 fields'
    alert['attribution'] = attr

    if any([attr['name'], attr['email'], attr['phone'], attr['upi']]):
        enriched += 1

# Save
json.dump(alerts, open(ALERTS_FILE,'w'), indent=2, default=str)
print(f'\nEnriched: {enriched}/{len(alerts)} alerts have attribution data')

# Summary
print('\nAttribution coverage:')
for field in ['name','email','phone','upi','address']:
    count = sum(1 for a in alerts if a.get('attribution',{}).get(field,''))
    print(f'  {field:10} {count:3}/{len(alerts)} alerts')
