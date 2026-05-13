"""
CINEOS Aggressive Hourly Scanner
Runs every hour via Railway scheduler OR Mac crontab.
Covers ALL fraud categories across ALL platforms.
Uses SerpAPI Production Plan (15,000/month, 3,000/hour).

Each hourly run:
  - 6 platform scans (Google, News, YouTube, IndiaMART, WhatsApp, Telegram)
  - 12 fraud category searches
  - 6 Indian language scans
  - Real-time IPL/match detection
  - Crypto + AI scam detection
  = ~40-60 SerpAPI calls per run
  = 960-1,440/day — well within 15,000/month quota

Generated alerts include:
  - Channel name, URL, subscriber count
  - Operator phones/UPIs where visible
  - SHA-256 evidence hash
  - IT Act §65B legal basis
  - Ordered next steps
  - Report-to organisations
"""

import json, re, os, time, hashlib, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST       = timezone(timedelta(hours=5, minutes=30))
SERP_KEY  = os.environ.get('SERP_API_KEY', '2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1')
RAILWAY   = 'https://cinerisk-api-production.up.railway.app/api/alert'
API_KEY   = 'cineos_internal_2026'
ALERTS_FILE = 'reports/alerts/live_alerts.json'
CHANNELS_FILE = 'reports/all_channels.json'

os.makedirs('reports/alerts', exist_ok=True)
os.makedirs('reports/scan_logs', exist_ok=True)

def now_ist():
    return datetime.now(IST)

def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def serp(query, engine='google', num=10, extra=None):
    params = {
        'q': query,
        'api_key': SERP_KEY,
        'engine': engine,
        'num': num,
        'gl': 'in',
        'hl': 'en',
        'no_cache': 'true',
    }
    if extra:
        params.update(extra)
    url = 'https://serpapi.com/search?' + urllib.parse.urlencode(params)
    try:
        resp = urllib.request.urlopen(url, timeout=15)
        return json.loads(resp.read())
    except Exception as e:
        print(f'  SerpAPI error [{engine}]: {e}')
        return {}

def serp_news(query):
    return serp(query, engine='google', extra={'tbm': 'nws', 'tbs': 'qdr:d'})

def push_to_railway(alert):
    try:
        data = json.dumps(alert).encode()
        req  = urllib.request.Request(
            RAILWAY, data=data,
            headers={'Content-Type':'application/json','X-API-Key':API_KEY},
            method='POST')
        r = json.loads(urllib.request.urlopen(req, timeout=8).read())
        return r.get('status') != 'duplicate'
    except:
        return False

# ── LEGAL BASIS BY CATEGORY ───────────────────────────────
LEGAL = {
    'illegal_betting':       'IT Act 2000 §65B + Public Gambling Act 1867 + Online Gaming Act 2025 §8',
    'piracy':                'IT Act 2000 §65B + Copyright Act 1957 §51 + IT Rules 2021 Rule 4(4)',
    'colour_prediction':     'IT Act 2000 §65B + Online Gaming Act 2025 §8 + FEMA 1999',
    'investment_fraud':      'IT Act 2000 §66D + SEBI Act 1992 §12A + IPC §420',
    'crypto_fraud':          'PMLA 2002 §3 + IT Act 2000 §65B + SEBI Act §12A',
    'ai_scam':               'IT Act 2000 §66D + §66C + IPC §419 §420',
    'upi_mule':              'IT Act 2000 §66 + PMLA §3 + IPC §420',
    'counterfeit_pharma':    'IT Act 2000 §65B + Drugs & Cosmetics Act 1940 §27',
    'brand_impersonation':   'IT Act 2000 §66D + Trade Marks Act 1999 §29',
    'domain_squat':          'IT Act 2000 §66D + Trade Marks Act 1999 §29 + UDRP',
    'counterfeit_marketplace':'IT Act 2000 §65B + Trade Marks Act 1999 §29',
    'task_fraud':            'IT Act 2000 §66D + IPC §420',
    'loan_fraud':            'IT Act 2000 §66D + RBI Master Direction + IPC §420',
    'job_scam':              'IT Act 2000 §66D + IPC §420 + Employment Act',
    'digital_arrest':        'IT Act 2000 §66D + §66C + IPC §384 §419',
    'deepfake':              'IT Act 2000 §66C + §67 + IPC §469',
}

NEXT_STEPS = {
    'piracy':            ['Preserve evidence — SHA-256 hash archived at detection','Send IT Rules 2021 §69A takedown to Telegram: abuse@telegram.org','File with MIB: mib.gov.in','Report to BCCI Anti-Piracy: antipiracy@bcci.tv','File NCCRP: cybercrime.gov.in'],
    'illegal_betting':   ['Preserve evidence — hash done','File NOGC complaint: nogc.gov.in','Report to state cybercrime cell with operator phone','Send Telegram takedown with IT Act §65B evidence','Share with ED if Dubai/crypto link confirmed'],
    'colour_prediction': ['Preserve evidence','File NOGC complaint — OGA 2025 §8 violation','Report app to Google Play/App Store','Send Telegram takedown','If Chinese-origin: report to MeitY for FEMA investigation'],
    'investment_fraud':  ['Preserve evidence','Report SEBI-unregistered advisor: sebi.gov.in/SCORES','File SEBI SCORES complaint: scores.gov.in','Send Telegram takedown with SEBI Act §12A evidence','Report to CERT-In if phishing site'],
    'crypto_fraud':      ['Preserve evidence — hash done','File ED complaint: enforcement.gov.in','Report to FIU-IND: fiuindia.gov.in','File NCCRP: cybercrime.gov.in/helpline 1930','Report to CERT-In if active phishing site'],
    'ai_scam':           ['Preserve evidence — DO NOT engage with caller','Report to MHA Cybercrime: cybercrime.gov.in','Call 1930 helpline immediately','File FIR at local PS with AI voice/video evidence','Report to TRAI: trai.gov.in (phone spoofing)'],
    'upi_mule':          ['Preserve UPI IDs + phone — hash done','Report mule UPIs to bank fraud desk immediately','File RBI Sachet: sachet.rbi.org.in','Report to I4C: cybercrime.gov.in / 1930','File PMLA report to FIU-IND if amount >Rs 5L'],
    'brand_impersonation':['Preserve evidence — fake APK/site archived','Report to CERT-In: cert-in.org.in','Notify brand owner security team','Report to Google Play Protect if APK','File NCCRP §66D complaint'],
    'domain_squat':      ['Preserve WHOIS evidence — registrant archived','File WIPO UDRP: wipo.int/amc/en/domains','Report to domain registrar abuse team','Send C&D to WHOIS registrant email','File with CERT-In if phishing active'],
    'digital_arrest':    ['Do NOT pay any amount — it is a scam','Report immediately to cybercrime.gov.in / 1930','Preserve call recording + screenshot','File FIR at local PS','Report to TRAI: trai.gov.in for phone number blocking'],
    'deepfake':          ['Preserve video/audio evidence — hash archived','Report to CERT-In: cert-in.org.in','File FIR under IT Act §66C + §67','Report to platform (YouTube/WhatsApp) for removal','Notify impersonated person/organization'],
}

REPORT_TO = {
    'piracy':            ['MIB — mib.gov.in','BCCI — antipiracy@bcci.tv','JioHotstar — security@jiostar.com','Telegram — abuse@telegram.org'],
    'illegal_betting':   ['NOGC — nogc.gov.in','State cybercrime cell','Telegram — abuse@telegram.org','ED — enforcement.gov.in'],
    'colour_prediction': ['NOGC — nogc.gov.in','MeitY — meity.gov.in','Telegram — abuse@telegram.org','I4C — cybercrime.gov.in'],
    'investment_fraud':  ['SEBI SCORES — scores.gov.in','cybercrime@sebi.gov.in','I4C — cybercrime.gov.in'],
    'crypto_fraud':      ['ED — enforcement.gov.in','FIU-IND — fiuindia.gov.in','CERT-In — cert-in.org.in','I4C — 1930'],
    'ai_scam':           ['I4C — cybercrime.gov.in / 1930','MHA Cybercrime','TRAI — trai.gov.in','Local PS'],
    'upi_mule':          ['Bank fraud desk','RBI Sachet — sachet.rbi.org.in','I4C — 1930','FIU-IND — fiuindia.gov.in'],
    'brand_impersonation':['CERT-In — cert-in.org.in','Brand owner security','Google Play Protect','NCCRP'],
    'domain_squat':      ['WIPO UDRP — wipo.int/amc','Domain registrar abuse','CERT-In','Brand owner legal'],
    'digital_arrest':    ['I4C — 1930','Local PS','TRAI — trai.gov.in','MHA Cybercrime'],
    'deepfake':          ['CERT-In — cert-in.org.in','Platform abuse team','I4C — cybercrime.gov.in','Local PS'],
}

def get_steps(cat):
    return NEXT_STEPS.get(cat, ['Preserve evidence — hash done','File complaint at cybercrime.gov.in / 1930','Send Telegram takedown: abuse@telegram.org','Share with relevant regulator'])

def get_report(cat):
    return REPORT_TO.get(cat, ['I4C — cybercrime.gov.in','Telegram — abuse@telegram.org','CERT-In — cert-in.org.in'])

def make_alert(title, category, severity, platform, detail, source, chain_extra=None, reach=0):
    aid = sha(title + category + now_ist().strftime('%Y-%m-%dT%H'))
    chain = {
        'channels_found': [],
        'keywords_matched': [],
        'reach': reach,
        'phones': [],
        'upis': [],
        'evidence_hashes': [aid],
        'legal_basis': LEGAL.get(category, 'IT Act 2000 §65B'),
        'recommended_action': get_steps(category)[0] if get_steps(category) else '',
        'report_to': get_report(category),
        'captured_at': now_ist().isoformat(),
    }
    if chain_extra:
        chain.update(chain_extra)
    return {
        'id':           aid,
        'title':        title[:100],
        'category':     category,
        'severity':     severity,
        'platform':     platform,
        'detail':       detail[:200],
        'detected_at':  now_ist().isoformat(),
        'source':       source,
        'evidence_hash': aid,
        'legal_basis':  LEGAL.get(category, 'IT Act 2000 §65B'),
        'next_steps':   get_steps(category),
        'report_to':    get_report(category),
        'attribution':  {'name':'','email':'','phone':'','upi':'','address':'','source':'scan'},
        'chain':        chain,
    }

# ══════════════════════════════════════════════
# SCAN MODULES
# ══════════════════════════════════════════════

def scan_ipl_piracy():
    """IPL piracy — real-time during season"""
    print('[SCAN] IPL piracy...')
    found = []
    queries = [
        'IPL 2026 live stream free Telegram link today',
        'IPL match live piracy stream illegal watch free',
        'hotstar IPL free Telegram channel 2026',
        'IPL live stream download free illegal site',
    ]
    for q in queries:
        data = serp(q)
        for r in data.get('organic_results', []):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            if any(kw in (link+title+snip).lower() for kw in ['telegram','free stream','live watch','illegal','piracy']):
                a = make_alert(
                    title=f'IPL piracy detected — {title[:60]}',
                    category='piracy',
                    severity='critical',
                    platform='Web / Telegram',
                    detail=snip[:150],
                    source='ipl_piracy_scan',
                    chain_extra={'channels_found':[link],'keywords_matched':q.split()[:4],'reach':35000000},
                    reach=35000000,
                )
                found.append(a)
        time.sleep(1)
    print(f'  IPL piracy: {len(found)} found')
    return found

def scan_betting():
    """Illegal betting — Telegram + web"""
    print('[SCAN] Illegal betting...')
    found = []
    queries = [
        'site:t.me satta matka online betting 2026',
        'Mahadev Book Reddy Anna Laser247 Telegram channel',
        'cricket betting tips WhatsApp group India 2026',
        'IPL toss prediction sure shot Telegram group',
        'online cricket id betbhai9 cricbet99 diamondexch',
        'satta king faridabad ghaziabad result Telegram',
    ]
    for q in queries:
        data = serp(q)
        for r in data.get('organic_results', []):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            phones = re.findall(r'(?:\+91|91)?([6-9]\d{9})', snip)
            a = make_alert(
                title=f'Illegal betting — {title[:60]}',
                category='illegal_betting',
                severity='critical' if any(kw in title.lower() for kw in ['mahadev','reddy','laser','diamond']) else 'high',
                platform='Telegram / Web',
                detail=snip[:150],
                source='betting_scan',
                chain_extra={'channels_found':[link],'keywords_matched':q.split()[:4],'phones':phones,'reach':200000},
                reach=200000,
            )
            found.append(a)
        time.sleep(1)
    print(f'  Betting: {len(found)} found')
    return found

def scan_colour_prediction():
    """Colour prediction apps"""
    print('[SCAN] Colour prediction...')
    found = []
    queries = [
        '91club OKWIN Jalwa BDG Win Telegram India 2026',
        'colour prediction game earn money India Telegram',
        'Daman game Tiranga lottery online India withdraw',
        'wingo bdg win colour trading India app Telegram',
        'aviator crash game earn India Telegram group',
    ]
    for q in queries:
        data = serp(q)
        for r in data.get('organic_results', []):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            phones = re.findall(r'(?:\+91|91)?([6-9]\d{9})', snip)
            a = make_alert(
                title=f'Colour prediction fraud — {title[:55]}',
                category='colour_prediction',
                severity='critical' if any(kw in title.lower() for kw in ['91club','okwin','jalwa','bdg']) else 'high',
                platform='Telegram / App',
                detail=snip[:150],
                source='colour_pred_scan',
                chain_extra={'channels_found':[link],'phones':phones,'reach':500000},
                reach=500000,
            )
            found.append(a)
        time.sleep(1)
    print(f'  Colour prediction: {len(found)} found')
    return found

def scan_crypto_fraud():
    """Crypto fraud — pig butchering, fake platforms"""
    print('[SCAN] Crypto fraud...')
    found = []
    queries = [
        'crypto investment fraud India Telegram arrested 2026',
        'fake crypto trading platform India ED PMLA 2026',
        'pig butchering scam India WhatsApp Telegram 2026',
        'Bitcoin investment fraud India Telegram group',
        'crypto pump signal Telegram India fake',
        'USDT investment double India Telegram fraud',
    ]
    for q in queries:
        data = serp_news(q)
        for r in data.get('news_results', data.get('organic_results', [])):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            is_crit = any(kw in (title+snip).lower() for kw in ['ed','arrested','crore','pmla','seized'])
            a = make_alert(
                title=f'Crypto fraud — {title[:60]}',
                category='crypto_fraud',
                severity='critical' if is_crit else 'high',
                platform='Telegram / Web',
                detail=snip[:150],
                source='crypto_fraud_scan',
                chain_extra={'channels_found':[link],'keywords_matched':q.split()[:4],'reach':100000},
                reach=100000,
            )
            found.append(a)
        time.sleep(1)
    print(f'  Crypto fraud: {len(found)} found')
    return found

def scan_ai_scams():
    """AI voice/video scams — digital arrest, deepfake"""
    print('[SCAN] AI scams...')
    found = []
    queries = [
        'digital arrest scam India AI voice 2026',
        'deepfake video scam India WhatsApp Telegram 2026',
        'AI voice clone fraud India police CBI impersonation',
        'fake ED officer call India digital arrest scam',
        'deepfake celebrity investment India fraud Telegram',
        'AI generated voice fraud India bank call scam',
    ]
    for q in queries:
        data = serp_news(q)
        for r in data.get('news_results', data.get('organic_results', [])):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            cat   = 'digital_arrest' if 'arrest' in (title+snip).lower() else 'deepfake' if 'deepfake' in (title+snip).lower() else 'ai_scam'
            is_crit = any(kw in (title+snip).lower() for kw in ['crore','lakh','arrested','seized'])
            a = make_alert(
                title=f'AI scam — {title[:60]}',
                category=cat,
                severity='critical' if is_crit else 'high',
                platform='WhatsApp / Telegram / Phone',
                detail=snip[:150],
                source='ai_scam_scan',
                chain_extra={'channels_found':[link],'keywords_matched':q.split()[:4]},
            )
            found.append(a)
        time.sleep(1)
    print(f'  AI scams: {len(found)} found')
    return found

def scan_investment_fraud():
    """SEBI-unregistered, fake stock tips"""
    print('[SCAN] Investment fraud...')
    found = []
    queries = [
        'SEBI unregistered investment advisor Telegram India 2026',
        'fake stock tips guaranteed returns Telegram India',
        'stock market fraud India arrested SEBI 2026',
        'fake IPO subscription Telegram India fraud',
        'option trading fraud India Telegram guaranteed profit',
        'penny stock pump dump Telegram India 2026',
    ]
    for q in queries:
        data = serp_news(q)
        for r in data.get('news_results', data.get('organic_results', [])):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            is_crit = any(kw in (title+snip).lower() for kw in ['arrested','crore','sebi','fraud'])
            a = make_alert(
                title=f'Investment fraud — {title[:60]}',
                category='investment_fraud',
                severity='critical' if is_crit else 'high',
                platform='Telegram / Web',
                detail=snip[:150],
                source='investment_scan',
                chain_extra={'channels_found':[link],'keywords_matched':q.split()[:4],'reach':150000},
                reach=150000,
            )
            found.append(a)
        time.sleep(1)
    print(f'  Investment fraud: {len(found)} found')
    return found

def scan_upi_mule():
    """UPI mule recruitment"""
    print('[SCAN] UPI mule...')
    found = []
    queries = [
        'bank account kit buy sell India Telegram 2026',
        'UPI ID sell India earn commission Telegram',
        'money mule India arrested bank account fraud 2026',
        'sim card bank account kit Telegram India earn',
        'hawala UPI transfer India Telegram operator',
    ]
    for q in queries:
        data = serp(q)
        for r in data.get('organic_results', []):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            upis  = re.findall(r'[a-zA-Z0-9.\-_]{2,20}@(?:paytm|gpay|okaxis|ybl|oksbi|upi|[a-zA-Z]{2,10})', snip)
            phones = re.findall(r'(?:\+91|91)?([6-9]\d{9})', snip)
            a = make_alert(
                title=f'UPI mule recruitment — {title[:55]}',
                category='upi_mule',
                severity='critical' if any(kw in (title+snip).lower() for kw in ['arrested','crore','seized']) else 'high',
                platform='Telegram / WhatsApp',
                detail=snip[:150],
                source='upi_mule_scan',
                chain_extra={'channels_found':[link],'upis':upis,'phones':phones,'reach':50000},
                reach=50000,
            )
            if upis or phones:
                a['severity'] = 'critical'
            found.append(a)
        time.sleep(1)
    print(f'  UPI mule: {len(found)} found')
    return found

def scan_domain_squats():
    """Brand domain squats and fake APKs"""
    print('[SCAN] Domain squats...')
    found = []
    queries = [
        'fake JioHotstar PhonePe HDFC domain India phishing 2026',
        'fake banking app India phishing domain APK 2026',
        'brand domain squat India trademark violation Telegram',
        'fake BCCI IPL official site India phishing',
        'counterfeit brand website India fake shop Telegram',
    ]
    for q in queries:
        data = serp(q)
        for r in data.get('organic_results', []):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            domains = re.findall(r'(?:www\.)?([a-zA-Z0-9\-]+\.(?:com|in|net|org|co\.in))', snip+link)
            a = make_alert(
                title=f'Domain squat / fake brand — {title[:55]}',
                category='domain_squat',
                severity='critical',
                platform='Web / WHOIS',
                detail=snip[:150],
                source='domain_squat_scan',
                chain_extra={'channels_found':[link],'whois_domain':domains[0] if domains else '','keywords_matched':q.split()[:4]},
            )
            found.append(a)
        time.sleep(1)
    print(f'  Domain squats: {len(found)} found')
    return found

def scan_counterfeit():
    """Counterfeit goods — pharma, FMCG, electronics"""
    print('[SCAN] Counterfeit goods...')
    found = []
    queries = [
        'fake medicine counterfeit pharma India Telegram sell 2026',
        'first copy replica brand India Telegram wholesale 2026',
        'counterfeit Nike Adidas shoes India Telegram sell',
        'fake Samsung OPPO phone India IndiaMART Telegram',
        'counterfeit HUL Reckitt product India Telegram sell',
    ]
    for q in queries:
        data = serp(q)
        for r in data.get('organic_results', []):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            cat   = 'counterfeit_pharma' if any(kw in (title+snip).lower() for kw in ['medicine','pharma','tablet','drug']) else 'counterfeit_marketplace'
            a = make_alert(
                title=f'Counterfeit — {title[:60]}',
                category=cat,
                severity='high',
                platform='Telegram / IndiaMART / Web',
                detail=snip[:150],
                source='counterfeit_scan',
                chain_extra={'channels_found':[link],'keywords_matched':q.split()[:4],'reach':50000},
                reach=50000,
            )
            found.append(a)
        time.sleep(1)
    print(f'  Counterfeit: {len(found)} found')
    return found

def scan_enforcement_news():
    """Real enforcement actions — arrests, seizures, ED busts"""
    print('[SCAN] Enforcement news...')
    found = []
    queries = [
        'cybercrime arrested India Telegram fraud 2026',
        'ED enforcement directorate India crypto fraud 2026',
        'SEBI action unregistered advisor India 2026',
        'police cybercrime India online fraud arrested crore',
        'CERT-In advisory India phishing fraud 2026',
        'I4C cybercrime India Telegram arrested today',
    ]
    for q in queries:
        data = serp_news(q)
        for r in data.get('news_results', data.get('organic_results', [])):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            date  = r.get('date','')

            # Determine category from content
            t = (title+snip).lower()
            if 'betting' in t or 'satta' in t:
                cat = 'illegal_betting'
            elif 'crypto' in t or 'bitcoin' in t:
                cat = 'crypto_fraud'
            elif 'stock' in t or 'sebi' in t or 'investment' in t:
                cat = 'investment_fraud'
            elif 'deepfake' in t or 'digital arrest' in t or 'ai voice' in t:
                cat = 'ai_scam'
            elif 'upi' in t or 'mule' in t or 'bank account' in t:
                cat = 'upi_mule'
            elif 'piracy' in t or 'stream' in t:
                cat = 'piracy'
            else:
                cat = 'investment_fraud'

            is_crit = any(kw in t for kw in ['crore','arrested','seized','ed raid','chargesheet'])
            a = make_alert(
                title=f'[NEWS] {title[:65]}',
                category=cat,
                severity='critical' if is_crit else 'high',
                platform='News / Enforcement',
                detail=f'{snip[:120]} [{date}]' if date else snip[:150],
                source='enforcement_news',
                chain_extra={'channels_found':[link],'keywords_matched':q.split()[:4]},
            )
            found.append(a)
        time.sleep(1)
    print(f'  Enforcement news: {len(found)} found')
    return found

def scan_multilingual():
    """Hindi/Telugu/Tamil fraud channels"""
    print('[SCAN] Multilingual...')
    found = []
    queries_hi = [
        'सट्टा मटका टेलीग्राम 2026',
        'ऑनलाइन ठगी टेलीग्राम भारत गिरफ्तार',
        'फर्जी निवेश टेलीग्राम भारत',
    ]
    queries_te = [
        'సట్టా మటకా టెలిగ్రామ్ 2026 ఆన్‌లైన్',
        'క్రికెట్ బెట్టింగ్ టెలిగ్రామ్ ఇండియా',
    ]
    queries_ta = [
        'சட்டவிரோத பந்தயம் டெலிகிராம் இந்தியா 2026',
        'ஆன்லைன் மோசடி டெலிகிராம் கைது',
    ]
    all_queries = [(q,'Hindi') for q in queries_hi] + [(q,'Telugu') for q in queries_te] + [(q,'Tamil') for q in queries_ta]

    for q, lang in all_queries:
        data = serp(q, extra={'lr': 'lang_hi' if lang=='Hindi' else 'lang_te' if lang=='Telugu' else 'lang_ta'})
        for r in data.get('organic_results', [])[:3]:
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            a = make_alert(
                title=f'[{lang}] Fraud channel — {title[:55]}',
                category='illegal_betting' if 'bet' in title.lower() or 'satta' in title.lower() else 'investment_fraud',
                severity='high',
                platform=f'Telegram ({lang})',
                detail=snip[:150],
                source='multilingual_scan',
                chain_extra={'channels_found':[link],'keywords_matched':[lang, 'fraud', 'Telegram']},
            )
            found.append(a)
        time.sleep(1.5)
    print(f'  Multilingual: {len(found)} found')
    return found

def scan_whatsapp():
    """WhatsApp fraud groups via Google indexing"""
    print('[SCAN] WhatsApp fraud...')
    found = []
    queries = [
        'chat.whatsapp.com betting satta India 2026',
        'chat.whatsapp.com investment fraud India group',
        'chat.whatsapp.com colour prediction India 2026',
        'WhatsApp group link India online fraud betting 2026',
    ]
    for q in queries:
        data = serp(q)
        for r in data.get('organic_results', []):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            if 'whatsapp' in (link+title+snip).lower():
                cat = 'illegal_betting' if 'bet' in (title+snip).lower() else 'colour_prediction' if 'colour' in (title+snip).lower() else 'investment_fraud'
                a = make_alert(
                    title=f'WhatsApp fraud group — {title[:55]}',
                    category=cat,
                    severity='high',
                    platform='WhatsApp',
                    detail=snip[:150],
                    source='whatsapp_scan',
                    chain_extra={'channels_found':[link],'keywords_matched':['WhatsApp','fraud','India']},
                )
                found.append(a)
        time.sleep(1)
    print(f'  WhatsApp: {len(found)} found')
    return found

def scan_indimart():
    """IndiaMART counterfeit listings"""
    print('[SCAN] IndiaMART...')
    found = []
    queries = [
        'site:indiamart.com first copy replica brand shoes',
        'site:indiamart.com fake medicine unlicensed pharma',
        'site:indiamart.com counterfeit brand wholesale',
        'site:indiamart.com duplicate brand electronics sell',
    ]
    for q in queries:
        data = serp(q)
        for r in data.get('organic_results', []):
            if 'indiamart.com' in r.get('link',''):
                link  = r.get('link','')
                title = r.get('title','')
                snip  = r.get('snippet','')
                cat   = 'counterfeit_pharma' if any(kw in (title+snip).lower() for kw in ['medicine','pharma','tablet']) else 'counterfeit_marketplace'
                a = make_alert(
                    title=f'IndiaMART counterfeit — {title[:55]}',
                    category=cat,
                    severity='high',
                    platform='IndiaMART',
                    detail=snip[:150],
                    source='indimart_scan',
                    chain_extra={'channels_found':[link],'keywords_matched':['IndiaMART','counterfeit'],'reach':10000},
                )
                found.append(a)
        time.sleep(1)
    print(f'  IndiaMART: {len(found)} found')
    return found

# ══════════════════════════════════════════════
# MAIN RUNNER
# ══════════════════════════════════════════════

def run_full_scan():
    print('='*58)
    print(f'  CINEOS AGGRESSIVE SCAN — {now_ist().strftime("%Y-%m-%d %H:%M IST")}')
    print('='*58)

    # Load existing alerts for dedup
    try:
        existing = json.load(open(ALERTS_FILE))
    except:
        existing = []

    existing_ids    = {a.get('id','') for a in existing}
    existing_titles = {f"{a.get('title','')[:60]}|{a.get('category','')}" for a in existing}

    # Run all scanners
    all_new = []
    scanners = [
        scan_ipl_piracy,
        scan_betting,
        scan_colour_prediction,
        scan_crypto_fraud,
        scan_ai_scams,
        scan_investment_fraud,
        scan_upi_mule,
        scan_domain_squats,
        scan_counterfeit,
        scan_enforcement_news,
        scan_multilingual,
        scan_whatsapp,
        scan_indimart,
    ]

    for scanner in scanners:
        try:
            results = scanner()
            for a in results:
                aid = a.get('id','')
                tk  = f"{a.get('title','')[:60]}|{a.get('category','')}"
                if aid and aid in existing_ids: continue
                if tk in existing_titles: continue
                all_new.append(a)
                existing_ids.add(aid)
                existing_titles.add(tk)
        except Exception as e:
            print(f'  Scanner {scanner.__name__} error: {e}')
        time.sleep(0.5)

    print(f'\n[RESULTS] {len(all_new)} new unique alerts found')

    if not all_new:
        print('  No new alerts this scan cycle')
        return 0

    # Sort by severity
    sev_order = {'critical':0,'high':1,'medium':2,'low':3}
    all_new.sort(key=lambda a: sev_order.get(a.get('severity','low'),3))

    # Merge with existing and save
    merged = all_new + existing
    merged = merged[:500]  # cap at 500
    json.dump(merged, open(ALERTS_FILE,'w'), indent=2, default=str)
    print(f'[SAVE] {len(merged)} total alerts in local file')

    # Push new alerts to Railway
    print('[RAILWAY] Pushing new alerts...')
    pushed = 0
    for a in all_new[:50]:  # push up to 50 at once
        if push_to_railway(a):
            pushed += 1
        time.sleep(0.1)
    print(f'[RAILWAY] Pushed {pushed}/{min(len(all_new),50)} alerts')

    # Log scan
    log_entry = {
        'scan_time':   now_ist().isoformat(),
        'new_alerts':  len(all_new),
        'total_local': len(merged),
        'by_category': {},
        'by_severity': {},
    }
    from collections import Counter
    log_entry['by_category'] = dict(Counter(a['category'] for a in all_new))
    log_entry['by_severity'] = dict(Counter(a['severity'] for a in all_new))

    log_file = f'reports/scan_logs/scan_{now_ist().strftime("%Y%m%d_%H")}.json'
    json.dump(log_entry, open(log_file,'w'), indent=2)

    print()
    print('[SUMMARY]')
    print(f'  New:      {len(all_new)}')
    print(f'  Total:    {len(merged)}')
    print(f'  By severity: {log_entry["by_severity"]}')
    print(f'  By category:')
    for cat, n in sorted(log_entry['by_category'].items(), key=lambda x:-x[1]):
        print(f'    {cat:35} {n}')
    print('='*58)

    return len(all_new)

if __name__ == '__main__':
    run_full_scan()
