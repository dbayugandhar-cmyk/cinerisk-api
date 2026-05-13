import json,re,os,time,hashlib,urllib.request,urllib.parse
from datetime import datetime,timezone,timedelta
try:
    import instaloader
    INSTA_OK=True
except:
    INSTA_OK=False

IST=timezone(timedelta(hours=5,minutes=30))
SERP_KEY=os.environ.get('SERP_API_KEY','2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1')
RAILWAY='https://cinerisk-api-production.up.railway.app/api/alert'
API_KEY_R='cineos_internal_2026'
ALERTS_FILE='reports/alerts/live_alerts.json'
os.makedirs('reports/alerts',exist_ok=True)

def now_ist(): return datetime.now(IST)
def sha(t): return hashlib.sha256(t.encode()).hexdigest()[:16]

UPI_RE=re.compile(r'\b([a-zA-Z0-9.\-_]{2,40}@(?:paytm|gpay|okaxis|ybl|okhdfcbank|okicici|oksbi|apl|upi|ibl|axl|hdfcbank|icici|sbi|kotak|waaxis|waicici|wairtel|freecharge|jiomoney|airtel|[a-zA-Z]{2,20}))\b',re.IGNORECASE)
PHONE_RE=re.compile(r'(?:\+91|91|0)?([6-9]\d{9})\b')

LEGAL={'investment_fraud':'IT Act 2000 §66D + SEBI Act §12A + IPC §420','crypto_fraud':'PMLA 2002 §3 + IT Act §65B + SEBI §12A','illegal_betting':'IT Act §65B + Public Gambling Act 1867 + OGA 2025 §8','colour_prediction':'IT Act §65B + OGA 2025 §8 + FEMA 1999','ai_scam':'IT Act §66D + §66C + IPC §419 §420','loan_fraud':'IT Act §66D + RBI Master Direction + IPC §420','counterfeit_marketplace':'IT Act §65B + Trade Marks Act §29'}
STEPS={'investment_fraud':['Preserve evidence','Report SEBI SCORES: scores.gov.in','Send YouTube takedown','Share cybercrime@sebi.gov.in','File NCCRP: cybercrime.gov.in'],'crypto_fraud':['Preserve evidence','File ED: enforcement.gov.in','Report FIU-IND: fiuindia.gov.in','Send platform takedown','File NCCRP'],'illegal_betting':['Preserve evidence','File NOGC: nogc.gov.in','Report state cybercrime','Send platform takedown','Share with ED if crypto'],'colour_prediction':['Preserve evidence','File NOGC: nogc.gov.in','Report Play Store/App Store','Send platform takedown','Report MeitY if Chinese'],'ai_scam':['Do NOT pay','Report I4C: 1930','File FIR','Send platform takedown','Report TRAI'],'loan_fraud':['Preserve evidence','File RBI Sachet: sachet.rbi.org.in','Report I4C: 1930','Send platform takedown','File FIR']}
REPT={'investment_fraud':['SEBI SCORES — scores.gov.in','cybercrime@sebi.gov.in','YouTube abuse'],'crypto_fraud':['ED — enforcement.gov.in','FIU-IND — fiuindia.gov.in','CERT-In'],'illegal_betting':['NOGC — nogc.gov.in','State cybercrime','Platform abuse'],'colour_prediction':['NOGC — nogc.gov.in','MeitY — meity.gov.in','Play Store'],'ai_scam':['I4C — 1930','MHA Cybercrime','TRAI'],'loan_fraud':['RBI Sachet — sachet.rbi.org.in','I4C — 1930','RBI']}

def serp_yt(q):
    p={'engine':'youtube','search_query':q,'api_key':SERP_KEY,'no_cache':'true'}
    try:
        return json.loads(urllib.request.urlopen('https://serpapi.com/search?'+urllib.parse.urlencode(p),timeout=15).read())
    except Exception as e:
        print(f'  YT error: {e}'); return {}

def serp_web(q):
    p={'q':q,'api_key':SERP_KEY,'engine':'google','num':10,'gl':'in','no_cache':'true'}
    try:
        return json.loads(urllib.request.urlopen('https://serpapi.com/search?'+urllib.parse.urlencode(p),timeout=15).read())
    except: return {}

# Known legitimate channels to exclude
LEGITIMATE_CHANNELS = {
    'anurag dwivedi','ndtv profit','zee business','cnbc tv18',
    'moneycontrol','economic times','livemint','business standard',
    'stocks trader institute','booming bulls','uvstar tech',
    'the muscular tourist','studyiq','uppcs','singh at work',
    'abhi vlogs','nishus vlogs','data trader','market shouts',
}

def classify(title,desc=''):
    t=(title+' '+desc).lower()
    if any(k in t for k in ['digital arrest','fake ed','fake cbi','deepfake']): return 'ai_scam','critical'
    if any(k in t for k in ['bitcoin','crypto','usdt','pig butcher']): return 'crypto_fraud','critical'
    if any(k in t for k in ['colour prediction','91club','okwin','daman','bdg','wingo']): return 'colour_prediction','critical'
    if any(k in t for k in ['betting','satta','matka','cricket id','toss prediction']): return 'illegal_betting','critical'
    if any(k in t for k in ['guaranteed profit','sebi','sure shot tips','intraday sure']): return 'investment_fraud','high'
    if any(k in t for k in ['instant loan','no cibil','loan without','loan app']): return 'loan_fraud','high'
    if any(k in t for k in ['first copy','replica','original duplicate']): return 'counterfeit_marketplace','high'
    return 'investment_fraud','medium'

YT_QUERIES=[
    '91club okwin daman game colour prediction Telegram India',
    'BDG win wingo tiranga lottery earn India Telegram',
    'satta matka online India Telegram betting ID 2026',
    'Mahadev book reddy anna cricket betting India',
    'laser247 betbhai9 cricbet99 diamond exchange India',
    'digital arrest scam fake ED CBI India fraud call',
    'deepfake video ED officer India scam WhatsApp',
    'fake crypto trading platform India USDT invest',
    'pig butchering India WhatsApp Telegram crypto',
    'instant loan no cibil check India fake app',
    'bank account kit sell earn commission India',
    'UPI earn commission India work online fraud',
    'fake stock tips guaranteed profit Telegram India',
    'SEBI fraud India arrested stock tips channel',
    'counterfeit medicine fake tablet India sell Telegram',
    'IPL toss fix sure shot prediction India Telegram',
    'cricket ID online betting India WhatsApp',
    'colour prediction app earn money India fraud',
    'online fraud India arrested cybercrime 2026',
    'ED arrests crypto fraud India 2026 crore',
]

IG_QUERIES=[
    'site:instagram.com colour prediction India earn money',
    'site:instagram.com "guaranteed profit" stock tips India',
    'site:instagram.com betting tips India cricket IPL',
    'site:instagram.com crypto investment India daily profit',
    'site:instagram.com 91club okwin daman game India',
    'site:instagram.com online earning India fraud',
    'site:instagram.com instant loan India no cibil',
    'site:instagram.com satta matka India online earn',
    'site:instagram.com forex trading India guaranteed',
    'site:instagram.com work from home India earn daily',
]

def scan_youtube(existing_ids):
    print('\n[YOUTUBE] Scanning',len(YT_QUERIES),'queries...')
    new_alerts=[]
    for q in YT_QUERIES:
        data=serp_yt(q)
        for v in data.get('video_results',[]):
            title=v.get('title',''); ch=v.get('channel',{}).get('name','')
            link=v.get('link',''); ch_link=v.get('channel',{}).get('link','')
            views=v.get('views',0); desc=v.get('description','') or ''
            if not title or not ch: continue
            phones=list(set(PHONE_RE.findall(desc)))
            upis=list(set(UPI_RE.findall(desc)))
            tg=re.findall(r't\.me/([a-zA-Z0-9_]+)',desc)
            wa=re.findall(r'chat\.whatsapp\.com/([A-Za-z0-9]+)',desc)
            # Skip known legitimate channels
            if ch.lower() in LEGITIMATE_CHANNELS: continue
            if any(leg in ch.lower() for leg in ['news','ndtv','zee','cnbc','mint','times','standard','profit tv','study','upsc']): continue
            cat,sev=classify(title,desc)
            if not cat: continue  # skip non-fraud content
            if (phones or upis or tg) and sev!='critical': sev='critical'
            aid=sha(f'yt_{ch}_{cat}_{title[:30]}')  # dedup per channel+category+title
            if aid not in existing_ids:
                a={'id':aid,'title':f'[YouTube] {ch} — {title[:60]}','category':cat,'severity':sev,'platform':'YouTube','detail':f'Channel: {ch} · {desc[:120]}','detected_at':now_ist().isoformat(),'source':'youtube_scan','evidence_hash':sha(f'{ch}{title}{desc[:50]}'),'legal_basis':LEGAL.get(cat,'IT Act §65B'),'next_steps':STEPS.get(cat,['Preserve evidence']),'report_to':REPT.get(cat,['I4C — 1930']),'attribution':{'name':ch,'email':'','phone':phones[0] if phones else '','upi':upis[0] if upis else '','address':'','source':'youtube_scan'},'chain':{'channels_found':[ch_link or f'youtube/{ch}'],'channel_title':ch,'video_title':title,'subscribers':views or 0,'reach':views or 0,'phones':phones,'upis':upis,'telegram_links':tg,'whatsapp_links':wa,'sample_post':desc[:300] or title,'keywords_matched':[w for w in q.split() if len(w)>4][:5],'evidence_hashes':[sha(f'{ch}{title}{desc[:50]}')],'legal_basis':LEGAL.get(cat,'IT Act §65B'),'recommended_action':STEPS.get(cat,['Preserve evidence'])[0],'report_to':REPT.get(cat,['I4C']),'captured_at':now_ist().isoformat()}}
                new_alerts.append(a); existing_ids.add(aid)
                if phones or upis or tg:
                    print(f'  ✓ {ch[:40]:40} 📞{len(phones)} 💳{len(upis)} 🔗{len(tg)} [{cat}]')
        time.sleep(1.5)
    print(f'  YouTube: {len(new_alerts)} new alerts')
    return new_alerts

def scan_instagram(existing_ids):
    print('\n[INSTAGRAM] Scanning via search...')
    new_alerts=[]
    found_usernames=set()
    for q in IG_QUERIES:
        data=serp_web(q)
        for r in data.get('organic_results',[]):
            link=r.get('link','')
            if 'instagram.com/' in link:
                m=re.search(r'instagram\.com/([a-zA-Z0-9._]{3,30})',link)
                if m:
                    u=m.group(1)
                    if u not in ('p','reel','stories','explore','tv','accounts','about'):
                        found_usernames.add(u)
        time.sleep(1)
    print(f'  Found {len(found_usernames)} Instagram accounts')
    # Extract phones/UPIs from SerpAPI snippets directly
    for q in IG_QUERIES:
        data=serp_web(q)
        for r in data.get('organic_results',[]):
            link=r.get('link','')
            snippet=r.get('snippet','') or ''
            title=r.get('title','') or ''
            if 'instagram.com/' not in link: continue
            m=re.search(r'instagram\.com/([a-zA-Z0-9._]{3,30})',link)
            if not m: continue
            username=m.group(1)
            if username in ('p','reel','stories','explore','tv'): continue
            phones=list(set(PHONE_RE.findall(snippet)))
            upis=list(set(UPI_RE.findall(snippet)))
            tg=re.findall(r't\.me/([a-zA-Z0-9_]+)',snippet)
            cat_kws={'colour_prediction':['colour prediction','91club','okwin','daman','bdg','wingo'],'illegal_betting':['betting','satta','matka','cricket'],'crypto_fraud':['crypto','bitcoin','usdt','trading'],'investment_fraud':['guaranteed','profit','stock','sebi'],'upi_mule':['account kit','earn commission','kyc'],'loan_fraud':['instant loan','no cibil','loan app']}
            cat=None
            for c,kws in cat_kws.items():
                if any(k in (snippet+title).lower() for k in kws): cat=c; break
            if not cat: continue
            sev='critical' if (phones or upis) else 'high'
            aid=sha(f'ig_snip_{username}_{cat}')
            if aid not in existing_ids:
                a={'id':aid,'title':f'[Instagram] @{username} — {cat.replace("_"," ")}','category':cat,'severity':sev,'platform':'Instagram','detail':snippet[:150],'detected_at':now_ist().isoformat(),'source':'instagram_scan','evidence_hash':sha(f'ig_{username}_{snippet[:50]}'),'legal_basis':LEGAL.get(cat,'IT Act §65B'),'next_steps':STEPS.get(cat,['Preserve evidence']),'report_to':REPT.get(cat,['I4C — 1930']),'attribution':{'name':username,'email':'','phone':phones[0] if phones else '','upi':upis[0] if upis else '','address':'','source':'instagram_snippet'},'chain':{'channels_found':[link],'channel_title':username,'subscribers':0,'reach':0,'phones':phones,'upis':upis,'telegram_links':tg,'sample_post':snippet[:300],'keywords_matched':[],'evidence_hashes':[sha(f'ig_{username}_{snippet[:50]}')],'legal_basis':LEGAL.get(cat,'IT Act §65B'),'recommended_action':STEPS.get(cat,['Preserve evidence'])[0],'report_to':REPT.get(cat,['I4C']),'captured_at':now_ist().isoformat()}}
                new_alerts.append(a); existing_ids.add(aid)
                if phones or upis or tg:
                    print(f'  ✓ @{username[:35]:35} 📞{len(phones)} 💳{len(upis)} 🔗{len(tg)} [{cat}]')
        time.sleep(1)
    if not INSTA_OK:
        pass
    # Skip instaloader (Instagram blocks without login)
    # Extract from SerpAPI snippets instead
    print('  (Extracting from search snippets — no login needed)')
    for username in []: # disabled
        try:
            profile = None
            bio=profile.biography or ''; followers=profile.followers
            full_name=profile.full_name or ''; ext_url=profile.external_url or ''
            phones=list(set(PHONE_RE.findall(bio))); upis=list(set(UPI_RE.findall(bio)))
            tg=re.findall(r't\.me/([a-zA-Z0-9_]+)',bio+ext_url)
            cat_kws={'investment_fraud':['guaranteed profit','sebi','stock tips','trading signal'],'crypto_fraud':['crypto','bitcoin','usdt','guaranteed'],'colour_prediction':['colour prediction','91club','okwin','daman','earn daily','bdg'],'illegal_betting':['betting','satta','matka','cricket id'],'upi_mule':['account kit','bank account earn','kyc sell'],'loan_fraud':['instant loan','no cibil','loan app']}
            cat=None
            for c,kws in cat_kws.items():
                if any(k in (bio+username).lower() for k in kws): cat=c; break
            if not cat and not phones and not upis and not tg:
                time.sleep(2); continue
            if not cat: cat='investment_fraud'
            sev='critical' if (phones or upis or followers>10000) else 'high'
            if phones or upis or tg or followers>5000:
                print(f'  ✓ @{username[:35]:35} {followers:>8,} 📞{len(phones)} 💳{len(upis)} 🔗{len(tg)} [{cat}]')
            aid=sha(f'ig_{username}_{cat}')
            if aid not in existing_ids:
                a={'id':aid,'title':f'[Instagram] @{username} — {cat.replace("_"," ")} · {followers:,} followers','category':cat,'severity':sev,'platform':'Instagram','detail':f'Bio: {bio[:150]}','detected_at':now_ist().isoformat(),'source':'instagram_scan','evidence_hash':sha(f'ig_{username}_{bio[:50]}'),'legal_basis':LEGAL.get(cat,'IT Act §65B'),'next_steps':STEPS.get(cat,['Preserve evidence']),'report_to':REPT.get(cat,['I4C — 1930']),'attribution':{'name':full_name or username,'email':'','phone':phones[0] if phones else '','upi':upis[0] if upis else '','address':'','source':'instagram_scan'},'chain':{'channels_found':[f'instagram.com/{username}'],'channel_title':full_name or username,'subscribers':followers,'reach':followers,'phones':phones,'upis':upis,'telegram_links':tg,'whatsapp_links':[],'sample_post':bio[:300],'external_url':ext_url,'keywords_matched':[],'evidence_hashes':[sha(f'ig_{username}_{bio[:50]}')],'legal_basis':LEGAL.get(cat,'IT Act §65B'),'recommended_action':STEPS.get(cat,['Preserve evidence'])[0],'report_to':REPT.get(cat,['I4C']),'captured_at':now_ist().isoformat()}}
                new_alerts.append(a); existing_ids.add(aid)
            time.sleep(2.5)
        except instaloader.exceptions.ProfileNotExistsException: pass
        except instaloader.exceptions.LoginRequiredException: pass
        except Exception as e:
            if '429' in str(e) or 'block' in str(e).lower():
                print('  Instagram rate limited — waiting 60s'); time.sleep(60)
    print(f'  Instagram: {len(new_alerts)} new alerts')
    return new_alerts

def run():
    print('='*58)
    print(f'  CINEOS YOUTUBE + INSTAGRAM SCAN')
    print(f'  {now_ist().strftime("%Y-%m-%d %H:%M IST")}')
    print('='*58)
    try: existing=json.load(open(ALERTS_FILE))
    except: existing=[]
    existing_ids={a.get('id','') for a in existing}
    yt=scan_youtube(existing_ids)
    ig=scan_instagram(existing_ids)
    all_new=yt+ig
    print(f'\n[TOTAL] {len(all_new)} new ({len(yt)} YouTube + {len(ig)} Instagram)')
    if not all_new: return
    merged=all_new+existing
    seen=set(); deduped=[]
    for a in merged:
        if a.get('id') not in seen: seen.add(a.get('id')); deduped.append(a)
    deduped.sort(key=lambda a:{'critical':0,'high':1,'medium':2,'low':3}.get(a.get('severity','low'),3))
    json.dump(deduped[:2000],open(ALERTS_FILE,'w'),indent=2,default=str)
    pushed=0
    for a in all_new[:100]:
        try:
            r=json.loads(urllib.request.urlopen(urllib.request.Request(RAILWAY,json.dumps(a).encode(),{'Content-Type':'application/json','X-API-Key':API_KEY_R},method='POST'),timeout=8).read())
            if r.get('status')!='duplicate': pushed+=1
            time.sleep(0.1)
        except: pass
    print(f'[RAILWAY] Pushed {pushed}')
    from collections import Counter
    print('[SUMMARY]',dict(Counter(a['category'] for a in all_new)))
    with_ph=[a for a in all_new if a.get('chain',{}).get('phones')]
    with_tg=[a for a in all_new if a.get('chain',{}).get('telegram_links')]
    print(f'With phones: {len(with_ph)}  With TG links: {len(with_tg)}')
    print('='*58)

if __name__=='__main__': run()
