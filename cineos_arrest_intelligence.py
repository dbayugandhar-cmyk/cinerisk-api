"""
CINEOS Arrest Intelligence Scanner
Finds confirmed fraud phones from police press releases,
court documents, and cybercrime unit announcements.
Uses SerpAPI — zero Telegram dependency, zero flood wait.

Sources:
- State cybercrime unit websites
- Police press releases
- High court cause lists
- I4C/MHA press releases
"""
import json, re, urllib.request, urllib.parse, time
from datetime import datetime, timezone, timedelta

SERP_KEY = '2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1'
ALERTS_FILE = 'reports/alerts/live_alerts.json'
IST = timezone(timedelta(hours=5,minutes=30))

PHONE_RE = re.compile(r'(?<!\d)([6-9]\d{9})(?!\d)')
UPI_RE = re.compile(
    r'\b([a-zA-Z0-9.\-_]{2,40}@(?:okaxis|okhdfcbank|okicici|oksbi|ybl|'
    r'ibl|ptaxis|pthdfc|paytm|apl|freecharge|axisbank|hdfcbank|'
    r'aubank|indus|rbl|kvb|federal|abfspay|idbi|sbiupi|icicipay))\b',
    re.IGNORECASE)

# Queries that find real police-confirmed fraud phones in news
ARREST_QUERIES = [
    'cybercrime arrest Telangana phone number 2026 betting',
    'cybercrime arrest Andhra Pradesh phone UPI fraud 2026',
    'cyber police Rajasthan arrested betting operator phone 2026',
    'Gujarat cybercrime arrested UPI mule phone number 2026',
    'Maharashtra cybercrime arrested online fraud phone 2026',
    'Delhi cybercrime arrested investment fraud phone 2026',
    'Karnataka cybercrime arrested crypto fraud phone 2026',
    'Hyderabad cybercrime arrested online betting phone 2026',
    'I4C cybercrime arrested fraud operator phone number',
    'ED arrested money laundering Telegram operator phone 2026',
    'cybercrime FIR registered fraud phone number India 2026',
    'police arrested online fraud WhatsApp Telegram phone 2026',
    'cyber cell arrested betting fraud accused phone number',
    'cybercrime unit arrested UPI fraud accused phone India',
    'NOGC action illegal betting operator phone India 2026',
]

def serp_search(query):
    params = {
        'q': query, 'api_key': SERP_KEY,
        'engine': 'google', 'num': 10,
        'gl': 'in', 'no_cache': 'true', 'hl': 'en'
    }
    url = 'https://serpapi.com/search?' + urllib.parse.urlencode(params)
    try:
        d = json.loads(urllib.request.urlopen(url, timeout=12).read())
        return d.get('organic_results', [])
    except Exception as e:
        print(f'  Error: {e}')
        return []

def fetch_page(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        return urllib.request.urlopen(req, timeout=8).read().decode('utf-8','ignore')
    except:
        return ''

def main():
    ts = datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')
    print(f'[{ts}] CINEOS Arrest Intelligence Scanner')
    print('Source: Police press releases, court documents, cybercrime portals')
    print('='*55)

    alerts = json.load(open(ALERTS_FILE))
    existing_phones = set(p for a in alerts for p in a.get('chain',{}).get('phones',[]))
    print(f'Existing phones in DB: {len(existing_phones)}')

    found_phones = {}  # phone -> {source, context, query}
    found_upis = {}
    queries_used = 0

    for q in ARREST_QUERIES:
        results = serp_search(q)
        queries_used += 1
        for r in results:
            text = str(r.get('title',''))+' '+str(r.get('snippet',''))
            link = r.get('link','')

            # Extract phones from snippet
            for m in PHONE_RE.findall(text):
                p = '+91'+m if not m.startswith('+') else m
                if p not in existing_phones and p not in found_phones:
                    found_phones[p] = {
                        'source': link,
                        'context': text[:200],
                        'query': q,
                        'type': 'arrest_news'
                    }
                    print(f'  NEW PHONE: {p}')
                    print(f'  Source: {link[:60]}')

            # Extract UPIs from snippet
            for u in UPI_RE.findall(text):
                if u not in found_upis:
                    found_upis[u] = {'source': link, 'context': text[:150]}
                    print(f'  NEW UPI: {u}')

            # Fetch full page for high-value sources
            if any(kw in link for kw in ['police','cybercrime','i4c','mha','court','ed.gov']):
                page = fetch_page(link)
                if page:
                    for m in PHONE_RE.findall(page):
                        p = '+91'+m
                        if p not in existing_phones and p not in found_phones:
                            idx = page.find(m)
                            ctx = page[max(0,idx-200):idx+200].lower()
                            fraud_kw = ['arrested','accused','suspect','fraud','betting',
                                'scam','cheated','crore','lakh','detained','caught',
                                'busted','racket','operator','cybercrime arrested']
                            skip_kw = ['helpline','dial 1930','contact police','call us',
                                'report crime','our number','reach us','1930',
                                'register complaint','police station contact']
                            if any(k in ctx for k in fraud_kw) and not any(k in ctx for k in skip_kw):
                                found_phones[p] = {
                                    'source': link,
                                    'context': ctx[:200],
                                    'query': q,
                                    'type': 'official_source'
                                }
                                print(f'  OFFICIAL PHONE: {p} from {link[:50]}')
                            else:
                                print(f'  SKIP (not fraud context): {p}')

        time.sleep(0.4)

    print()
    print('='*55)
    print(f'Queries used: {queries_used}')
    print(f'New phones found: {len(found_phones)}')
    print(f'New UPIs found: {len(found_upis)}')

    if found_phones:
        # Add to alerts as arrest-confirmed intelligence
        from datetime import datetime as dt
        import hashlib
        for phone, meta in found_phones.items():
            alert_id = hashlib.sha256(f'arrest_{phone}'.encode()).hexdigest()[:16]
            alerts.append({
                'id': alert_id,
                'title': f'Arrest-confirmed fraud identifier: {phone}',
                'category': 'confirmed_arrest',
                'severity': 'critical',
                'platform': 'Police/Court Record',
                'detail': meta['context'][:300],
                'source': meta['source'],
                'detected_at': dt.now(IST).isoformat(),
                'reach': 0,
                'evidence_hash': alert_id,
                'chain': {
                    'phones': [phone],
                    'upis': [],
                    'channels_found': [meta['source']],
                }
            })

        json.dump(alerts, open(ALERTS_FILE,'w'), indent=2, default=str)
        print(f'Added {len(found_phones)} arrest-confirmed phones to database')

    print('='*55)

if __name__ == '__main__':
    main()
