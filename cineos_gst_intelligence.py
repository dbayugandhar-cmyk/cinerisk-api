"""
CINEOS GST Intelligence Scanner
Finds GST numbers linked to fraud operators via SerpAPI.
Verifies them against free GSTN public API.
Zero Telegram dependency — runs independently.

Run: python3 cineos_gst_intelligence.py
Crontab: 0 7 * * * (daily at 7am, independent of deep scan)
"""
import json, re, urllib.request, urllib.parse, time, hashlib
from datetime import datetime, timezone, timedelta

SERP_KEY      = '2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1'
ALERTS_FILE   = 'reports/alerts/live_alerts.json'
GST_FILE      = 'reports/gst_intelligence.json'
IST           = timezone(timedelta(hours=5, minutes=30))

# GST number regex — 15 character format
GST_RE = re.compile(
    r'\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b'
)

# Search queries that find GST numbers in fraud context
GST_QUERIES = [
    'telegram betting operator GST number India fraud',
    'online betting GST registration India fake',
    'illegal betting India GST FSSAI license fraud',
    'counterfeit medicine seller GST India telegram',
    'fake investment advisor GST SEBI India',
    'UPI fraud operator GST India registration',
    'online fraud GST number India cybercrime',
    'telegram fraud channel GST number India 2026',
    'satta matka GST number India registration',
    'colour prediction app GST India fake',
]

def serp_search(query):
    params = {
        'q': query, 'api_key': SERP_KEY,
        'engine': 'google', 'num': 10,
        'gl': 'in', 'no_cache': 'true'
    }
    url = 'https://serpapi.com/search?' + urllib.parse.urlencode(params)
    try:
        d = json.loads(urllib.request.urlopen(url, timeout=12).read())
        return d.get('organic_results', [])
    except Exception as e:
        print(f'  SerpAPI error: {e}')
        return []

def verify_gst(gst_number):
    """
    Verify GST number against public GSTN portal.
    Returns business name and status if valid.
    """
    try:
        # GSTN public search
        url = f'https://services.gst.gov.in/services/api/search/taxpayerDetails?gstin={gst_number}'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        })
        r = json.loads(urllib.request.urlopen(req, timeout=8).read())
        if r.get('errorCode') == 'SWEB_9000' or r.get('status_cd') == '1':
            d = r.get('data', {})
            return {
                'valid': True,
                'business_name': d.get('tradeNam') or d.get('lgnm', 'Unknown'),
                'status': d.get('sts', 'Unknown'),
                'state': d.get('pradr', {}).get('addr', {}).get('stcd', ''),
                'registration_date': d.get('rgdt', ''),
                'type': d.get('ctb', ''),
            }
        return {'valid': False, 'reason': 'Not found in GSTN'}
    except Exception as e:
        return {'valid': None, 'reason': f'Verification failed: {str(e)[:50]}'}

def detect_category(text):
    t = text.lower()
    if any(k in t for k in ['betting', 'satta', 'cricket id', 'casino']): return 'illegal_betting'
    if any(k in t for k in ['medicine', 'pharma', 'tablet', 'drug']): return 'counterfeit_pharma'
    if any(k in t for k in ['invest', 'trading', 'sebi', 'stock']): return 'investment_fraud'
    if any(k in t for k in ['upi', 'mule', 'account', 'sim']): return 'upi_mule'
    if any(k in t for k in ['crypto', 'bitcoin', 'usdt']): return 'crypto_fraud'
    return 'fraud'

def main():
    ts = datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')
    print(f'[{ts}] CINEOS GST Intelligence Scanner')
    print('='*55)
    print('No Telegram needed — SerpAPI + GSTN only')
    print()

    # Load existing GST intelligence
    try:
        gst_db = json.load(open(GST_FILE))
    except:
        gst_db = {}

    existing_gst = set(gst_db.keys())
    alerts = json.load(open(ALERTS_FILE))

    # First: extract GST numbers already in existing alerts
    print('[1/2] Extracting GST numbers from existing alerts...')
    alert_gst = {}
    for a in alerts:
        text = str(a.get('title','')) + ' ' + str(a.get('detail',''))
        gsts = GST_RE.findall(text)
        for g in gsts:
            if g not in alert_gst:
                alert_gst[g] = a.get('category','unknown')

    print(f'  Found {len(alert_gst)} GST numbers in existing alerts')

    # Second: search for new GST numbers via SerpAPI
    print()
    print('[2/2] Searching for fraud-linked GST numbers via SerpAPI...')
    queries_used = 0
    new_gst = {}

    for q in GST_QUERIES:
        results = serp_search(q)
        queries_used += 1
        for r in results:
            text = str(r.get('title',''))+' '+str(r.get('snippet',''))
            gsts = GST_RE.findall(text)
            for g in gsts:
                if g not in existing_gst and g not in new_gst:
                    cat = detect_category(text + ' ' + q)
                    new_gst[g] = {
                        'category': cat,
                        'source': r.get('link',''),
                        'context': text[:200],
                        'query': q,
                    }
                    print(f'  Found GST: {g} [{cat}]')
        time.sleep(0.4)

    print(f'\n  Queries used: {queries_used}')
    print(f'  New GST numbers found: {len(new_gst)}')

    # Verify all new GST numbers
    all_to_verify = {**{g: {'category': cat, 'source': 'existing_alert'}
                       for g, cat in alert_gst.items()
                       if g not in existing_gst}, **new_gst}

    if all_to_verify:
        print()
        print(f'Verifying {len(all_to_verify)} GST numbers against GSTN...')
        verified = 0
        fake = 0
        for gst, meta in all_to_verify.items():
            result = verify_gst(gst)
            entry = {
                'gst_number': gst,
                'category': meta.get('category','unknown'),
                'source': meta.get('source',''),
                'context': meta.get('context',''),
                'gstn_verified': result,
                'discovered_at': datetime.now(IST).isoformat(),
                'risk': 'HIGH' if result.get('valid') == False else
                        'CRITICAL' if result.get('valid') == True and
                        meta.get('category') in ['illegal_betting','upi_mule'] else 'MEDIUM'
            }
            gst_db[gst] = entry
            if result.get('valid') == True:
                verified += 1
                print(f'  VERIFIED: {gst} → {result.get("business_name","?")} [{result.get("status","?")}]')
            elif result.get('valid') == False:
                fake += 1
                print(f'  FAKE/INVALID: {gst} → not in GSTN')
            else:
                print(f'  UNKNOWN: {gst} → verification failed')
            time.sleep(0.5)

        print()
        print(f'  Verified (real businesses): {verified}')
        print(f'  Fake/invalid GST numbers:   {fake}')

    # Save
    json.dump(gst_db, open(GST_FILE, 'w'), indent=2, default=str)

    print()
    print('='*55)
    print(f'TOTAL GST INTELLIGENCE DATABASE: {len(gst_db)} records')
    print(f'Saved to: {GST_FILE}')
    print()

    # Summary
    real = [v for v in gst_db.values() if v.get('gstn_verified',{}).get('valid')==True]
    fake_list = [v for v in gst_db.values() if v.get('gstn_verified',{}).get('valid')==False]
    print(f'VERIFIED real businesses linked to fraud: {len(real)}')
    print(f'FAKE/INVALID GST numbers used by fraudsters: {len(fake_list)}')
    print()
    if real:
        print('TOP VALUE — Real businesses linked to fraud:')
        for r in real[:5]:
            biz = r.get('gstn_verified',{}).get('business_name','?')
            gst = r.get('gst_number','')
            cat = r.get('category','')
            print(f'  {gst} → {biz} [{cat}]')
    print('='*55)

if __name__ == '__main__':
    main()
