import json,re,os,time,hashlib,urllib.request,urllib.parse
from datetime import datetime,timezone,timedelta

IST=timezone(timedelta(hours=5,minutes=30))
SERP_KEY=os.environ.get('SERP_API_KEY','2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1')
RAILWAY='https://cinerisk-api-production.up.railway.app/api/alert'
API_KEY_R='cineos_internal_2026'
ALERTS_FILE='reports/alerts/live_alerts.json'
CHANNELS_FILE='reports/all_channels.json'
GRAPH_FILE='reports/fraud_intelligence_graph.json'
MATCHES_FILE='reports/news_matches.json'
os.makedirs('reports',exist_ok=True)

def now_ist(): return datetime.now(IST)
def sha(t): return hashlib.sha256(t.encode()).hexdigest()[:16]

PHONE_RE=re.compile(r'(?:\+91|91|0)?([6-9]\d{9})\b')
UPI_RE=re.compile(r'\b([a-zA-Z0-9.\-_]{2,40}@(?:paytm|gpay|okaxis|ybl|oksbi|upi|hdfcbank|icici|sbi|kotak|[a-zA-Z]{2,20}))\b',re.IGNORECASE)
DOMAIN_RE=re.compile(r'\b([a-zA-Z0-9\-]{3,40}\.(?:com|in|net|org|co\.in|app|io))\b',re.IGNORECASE)
TG_RE=re.compile(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{3,32})')
STATE_RE=re.compile(r'\b(Maharashtra|Gujarat|Telangana|Karnataka|Tamil Nadu|Andhra Pradesh|Delhi|Rajasthan|Uttar Pradesh|West Bengal|Punjab|Kerala|Haryana|Bihar|Odisha|Assam|Madhya Pradesh)\b',re.IGNORECASE)

FRAUD_CATEGORIES={
    'illegal_betting': ['betting','satta','matka','cricket id','book id','bookie',
                        'mahadev','reddy anna','laser247','betbhai','cricbet',
                        'tiger365','diamond exchange','radhe exchange','fairplay',
                        'world777','lotus365','match fix','toss fix','bet id'],
    'crypto_fraud':    ['crypto','bitcoin','usdt','tether','blockchain','btc','eth',
                        'guaranteed return','daily profit','trading signal','pump',
                        'p2p trader','usdt inr','coin signal','defi earn','nft fraud'],
    'investment_fraud':['investment fraud','stock tips','sebi unregistered','ponzi',
                        'guaranteed profit','option trading','insider tip','ipo allotment',
                        'fake portfolio','wealth manager fraud','pig butchering'],
    'colour_prediction':['colour prediction','color prediction','91club','daman',
                         'okwin','jalwa','bdg win','wingo','tiranga','aviator',
                         'crash game','colour trade'],
    'upi_mule':        ['mule account','bank account kit','upi mule','hawala',
                        'money transfer agent','otp bypass','sim swap','atm card sell',
                        'fake kyc','account kit sell','upi earn commission',
                        'current account sell','mule network'],
    'counterfeit_pharma':['counterfeit medicine','fake drug','spurious medicine',
                          'ozempic','mounjaro','tramadol','sildenafil','tadalafil',
                          'alprazolam','kamagra','steroid','anabolic','hgh',
                          'prescription drug','illegal pharmacy','cdsco','dcgi'],
    'digital_arrest':  ['digital arrest','fake ed','fake cbi','fake police',
                        'fake customs','courier seized','money laundering notice',
                        'deepfake call','sextortion'],
    'piracy':          ['piracy','illegal stream','cracked ott','free hotstar',
                        'free netflix','ipl piracy','torrent','copyright violation'],
    'loan_fraud':      ['loan fraud','fake loan app','illegal lending','no cibil',
                        'loan without document','processing fee fraud',
                        'loan harassment','nbfc fraud'],
    'brand_impersonation':['fake paytm','fake phonepe','fake amazon','fake flipkart',
                            'fake hdfc','fake icici','fake sbi','brand impersonation',
                            'phishing site','fake payment'],
}

LEGAL={'illegal_betting':'IT Act §65B + Public Gambling Act 1867 + OGA 2025 §8','crypto_fraud':'PMLA 2002 §3 + IT Act §65B + SEBI §12A','investment_fraud':'IT Act §66D + SEBI Act §12A + IPC §420','colour_prediction':'IT Act §65B + OGA 2025 §8 + FEMA 1999','upi_mule':'IT Act §66 + PMLA §3 + IPC §420','digital_arrest':'IT Act §66D + §66C + IPC §419 §420','piracy':'IT Act §65B + Copyright Act §51','loan_fraud':'IT Act §66D + RBI Master Direction + IPC §420'}

def extract_entities(text):
    return {'phones':list(set(PHONE_RE.findall(text))),'upis':list(set(UPI_RE.findall(text))),'domains':list(set(DOMAIN_RE.findall(text))),'channels':list(set(TG_RE.findall(text))),'states':list(set(STATE_RE.findall(text)))}

def detect_category(text):
    t=text.lower()
    for cat,kws in FRAUD_CATEGORIES.items():
        if any(k in t for k in kws): return cat
    return 'unknown'

NEWS_QUERIES=[
    # ── ENFORCEMENT ACTIONS ──────────────────────────────────────
    # ED / PMLA
    'Enforcement Directorate arrested India fraud crore 2026',
    'ED attachment India cyber fraud PMLA 2026',
    'ED arrested online betting India 2026',
    'ED arrested crypto fraud India hawala 2026',
    # I4C / MHA Cybercrime
    'I4C cybercrime arrested India 2026',
    'cybercrime police arrested India Telegram fraud 2026',
    'NCRP complaint India arrested cybercrime 2026',
    '1930 helpline cybercrime arrested India 2026',
    # State police — AP/TG (primary betting geography)
    'Telangana cybercrime arrested betting 2026',
    'Andhra Pradesh cybercrime arrested online betting 2026',
    'Visakhapatnam Hyderabad cybercrime arrested 2026',
    # State police — Maharashtra / Gujarat (mule networks)
    'Maharashtra cybercrime arrested UPI mule 2026',
    'Gujarat cybercrime arrested mule account 2026',
    'Ahmedabad Pune Mumbai cybercrime arrested 2026',
    # State police — Rajasthan (Radhe Exchange geography)
    'Rajasthan cybercrime arrested online betting 2026',
    # State police — others
    'Delhi cybercrime arrested fraud Telegram 2026',
    'Karnataka cybercrime arrested fraud 2026',
    'UP cybercrime arrested Telegram fraud 2026',

    # ── REGULATOR ACTIONS ────────────────────────────────────────
    # SEBI
    'SEBI action fraud India stock tips unregistered 2026',
    'SEBI order penalty fraud India 2026',
    'SEBI arrested unregistered advisor India 2026',
    # RBI
    'RBI action illegal lending app India 2026',
    'RBI cancelled NBFC India fraud 2026',
    'RBI alert payment fraud India 2026',
    # CDSCO / DCGI — pharma
    'CDSCO drug alert spurious medicine India 2026',
    'DCGI crackdown counterfeit medicine India 2026',
    'state drug controller seized fake medicine India 2026',
    'CDSCO not of standard quality drug India 2026',
    # TRAI — telecom fraud
    'TRAI action SMS fraud India 2026',
    'DoT disconnected fraud numbers India 2026',
    'TRAI bulk SMS fraud India arrested 2026',

    # ── VERTICAL SPECIFIC ────────────────────────────────────────
    # Betting
    'online betting arrested India cricket ID 2026',
    'satta matka arrested India 2026',
    'Mahadev Book arrested India 2026',
    'Reddy Anna arrested India 2026',
    'illegal betting app India arrested crore 2026',
    # Banking / UPI fraud
    'UPI mule network arrested India 2026',
    'mule account India arrested FIU 2026',
    'hawala USDT India arrested ED 2026',
    'OTP bypass SIM swap India arrested 2026',
    'fake KYC Aadhaar India arrested 2026',
    # Pharma
    'counterfeit medicine Telegram India arrested 2026',
    'fake Ozempic seized India 2026',
    'tramadol without prescription India arrested 2026',
    'steroid anabolic India seized arrested 2026',
    'illegal pharmacy online India arrested 2026',
    # Crypto
    'crypto fraud India arrested ED PMLA 2026',
    'pig butchering India arrested crypto 2026',
    'fake trading app India arrested 2026',
    # Colour prediction
    'colour prediction fraud India arrested 2026',
    '91club daman fraud India arrested 2026',
    # Digital arrest
    'digital arrest scam India arrested 2026',
    'fake CBI ED police call India arrested 2026',
    # Piracy
    'IPL piracy India arrested streaming 2026',
    'OTT piracy India arrested 2026',
]

def fetch_news():
    print('[NEWS] Fetching enforcement news...')
    articles=[]
    for q in NEWS_QUERIES:
        params={'q':q,'api_key':SERP_KEY,'engine':'google','tbm':'nws','tbs':'qdr:w','num':10,'gl':'in','no_cache':'true'}
        url='https://serpapi.com/search?'+urllib.parse.urlencode(params)
        try:
            data=json.loads(urllib.request.urlopen(url,timeout=15).read())
            for r in data.get('news_results',data.get('organic_results',[])):
                articles.append({'title':r.get('title',''),'snippet':r.get('snippet','') or r.get('description',''),'link':r.get('link',''),'date':r.get('date',''),'source':r.get('source',''),'query':q})
        except Exception as e: print(f'  Error: {e}')
        time.sleep(1.5)
    seen=set(); unique=[]
    for a in articles:
        k=a['title'][:60]
        if k not in seen and a['title']: seen.add(k); unique.append(a)
    print(f'  Found {len(unique)} unique articles')
    return unique

def crossref(article,alerts,channels,graph):
    full=article.get('title','')+' '+article.get('snippet','')
    full_l=full.lower()
    ents=extract_entities(full)
    cat=detect_category(full)
    matches=[]
    db_phones={v.get('identifier','') or v.get('properties',{}).get('number','').replace('+91',''):v for v in graph.get('nodes',{}).values() if v.get('type')=='PHONE'}
    for ph in ents['phones']:
        clean=ph.replace('+91','').replace(' ','').replace('-','')
        if clean in db_phones: matches.append({'type':'PHONE_EXACT','confidence':100,'entity':f'+91{clean}','detail':f'Phone +91{clean} in both news and CINEOS database'})
    db_ch={c.get('username','').lower():c for c in channels}
    for ch in ents['channels']:
        if ch.lower() in db_ch: matches.append({'type':'CHANNEL_EXACT','confidence':95,'entity':f'@{ch}','detail':f'Channel @{ch} monitored by CINEOS'})
    db_domains={v.get('domain','').lower() for v in graph.get('nodes',{}).values() if v.get('type')=='DOMAIN'}
    for d in ents['domains']:
        if d.lower() in db_domains: matches.append({'type':'DOMAIN_EXACT','confidence':90,'entity':d,'detail':f'Domain {d} in CINEOS graph'})
    for op in [v for v in graph.get('nodes',{}).values() if v.get('type')=='OPERATOR']:
        name=op.get('label','').lower()
        words=[w for w in name.split() if len(w)>3]
        if sum(1 for w in words if w in full_l)>=2 or (len(words)==1 and name in full_l):
            matches.append({'type':'OPERATOR_FUZZY','confidence':85,'entity':op.get('label',''),'detail':f'Operator {op.get("label","")} name matches news'})
    if cat!='unknown' and ents['states']:
        cat_count=len([a for a in alerts if a.get('category')==cat])
        if cat_count: matches.append({'type':'CATEGORY_STATE','confidence':70,'entity':f'{cat} in {ents["states"][0]}','detail':f'CINEOS has {cat_count} {cat} alerts including {ents["states"][0]}'})
    if not matches: return None
    best=max(m['confidence'] for m in matches)
    earliest=min((a.get('detected_at','z') for a in alerts if a.get('category')==cat),default=None)
    days=None
    if earliest:
        try:
            art_date=now_ist()
            if 'day' in article.get('date','').lower():
                n=int(re.search(r'(\d+)',article.get('date','')).group(1))
                art_date=now_ist()-timedelta(days=n)
            cineos_dt=datetime.fromisoformat(earliest.replace('Z','+00:00')).astimezone(IST)
            days=(art_date-cineos_dt).days
        except: pass
    return {'article':article,'matches':matches,'confidence':best,'category':cat,'entities':ents,'days_ahead':days}

def answer_query(question,alerts,channels,graph):
    q=question.lower()
    ents=extract_entities(question)
    cat=detect_category(question)
    findings=[]
    db_phones={v.get('identifier','') or v.get('properties',{}).get('number','').replace('+91',''):v for v in graph.get('nodes',{}).values() if v.get('type')=='PHONE'}
    for ph in ents['phones']:
        clean=ph.replace('+91','').replace(' ','').replace('-','')
        if clean in db_phones: findings.append({'type':'PHONE_FOUND','entity':f'+91{clean}','detail':'This phone is in CINEOS database — extracted from Telegram fraud channels','confidence':100})
    db_ch={c.get('username','').lower():c for c in channels}
    for ch in ents['channels']:
        if ch.lower() in db_ch:
            c=db_ch[ch.lower()]
            findings.append({'type':'CHANNEL_FOUND','entity':f'@{ch}','detail':f'Monitored · {c.get("subscribers",0):,} subs · {c.get("category","")}','confidence':95})
    keywords=[w for w in q.split() if len(w)>4 and w not in ('about','where','which','there','fraud','scam','india')]
    kw_matches=[(sum(1 for k in keywords if k in json.dumps(a).lower()),a) for a in alerts]
    kw_matches=[(s,a) for s,a in kw_matches if s>=2]
    kw_matches.sort(key=lambda x:-x[0])
    if kw_matches: findings.append({'type':'KEYWORD_MATCH','entity':' + '.join(keywords[:3]),'detail':f'{len(kw_matches)} alerts match your query','top_alerts':[a["title"] for _,a in kw_matches[:3]],'confidence':min(95,50+len(kw_matches)*3)})
    for op in [v for v in graph.get('nodes',{}).values() if v.get('type')=='OPERATOR']:
        name=op.get('label','').lower()
        if any(w in name for w in keywords if len(w)>4):
            findings.append({'type':'OPERATOR_FOUND','entity':op.get('label',''),'detail':f'In CINEOS graph · {op.get("reach",0):,} reach · {len(op.get("channels",[]))} channels','phones':op.get('phones',[]),'confidence':90})
    if cat!='unknown':
        cat_ch=[c for c in channels if c.get('category')==cat]
        cat_al=[a for a in alerts if a.get('category')==cat]
        reach=sum(c.get('subscribers',0) for c in cat_ch)
        findings.append({'type':'CATEGORY','entity':cat,'detail':f'{len(cat_ch)} channels · {len(cat_al)} alerts · {reach:,} reach','confidence':80})
    if not findings:
        print(f'\nNo direct match. Database: {len(channels)} channels · {len(alerts)} alerts')
        return
    best=max(f['confidence'] for f in findings)
    print(f'\n{"="*60}')
    print(f'CINEOS Query: {question}')
    print(f'{"="*60}')
    for f in findings:
        print(f'\n[{f["confidence"]}%] {f["type"]}')
        print(f'  Entity:  {f["entity"]}')
        print(f'  Detail:  {f["detail"]}')
        if f.get('phones'): print(f'  Phones:  {f["phones"]}')
        if f.get('top_alerts'):
            for t in f['top_alerts']: print(f'    • {t[:70]}')
    print(f'\nOverall confidence: {best}%')
    print(f'Evidence standard: IT Act §65B | Database updated hourly')
    print('='*60)

def run_crossref():
    print('='*60)
    print(f'  CINEOS NEWS CROSS-REFERENCE ENGINE')
    print(f'  {now_ist().strftime("%Y-%m-%d %H:%M IST")}')
    print('='*60)
    try: alerts=json.load(open(ALERTS_FILE))
    except: alerts=[]
    try: channels=json.load(open(CHANNELS_FILE))
    except: channels=[]
    try: graph=json.load(open(GRAPH_FILE))
    except: graph={'nodes':{},'edges':[]}
    print(f'Database: {len(alerts)} alerts · {len(channels)} channels · {len(graph["nodes"])} nodes')
    articles=fetch_news()
    results=[]
    print(f'\n[MATCHING] {len(articles)} articles vs database...')
    for art in articles:
        r=crossref(art,alerts,channels,graph)
        if r and r['confidence']>=40:
            results.append(r)
            ahead=f' · {r["days_ahead"]}d BEFORE arrest' if r.get('days_ahead',0)>0 else ''
            print(f'  [{r["confidence"]:3}%] {art["title"][:60]}{ahead}')
    results.sort(key=lambda x:-x['confidence'])
    json.dump(results,open(MATCHES_FILE,'w'),indent=2,default=str)
    print(f'\n{len(results)} matches found · saved to {MATCHES_FILE}')
    print('\nTOP 3 MATCHES:')
    for r in results[:3]:
        print(f'\n  {r["confidence"]}% — {r["article"]["title"][:65]}')
        if r.get('days_ahead',0)>0: print(f'  ⚡ CINEOS detected {r["days_ahead"]} days BEFORE this news')
        for m in r['matches'][:2]: print(f'    • {m["detail"][:70]}')

import sys
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--query':
        try: alerts=json.load(open(ALERTS_FILE))
        except: alerts=[]
        try: channels=json.load(open(CHANNELS_FILE))
        except: channels=[]
        try: graph=json.load(open(GRAPH_FILE))
        except: graph={'nodes':{},'edges':[]}
        answer_query(' '.join(sys.argv[2:]),alerts,channels,graph)
    else:
        run_crossref()
