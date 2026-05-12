"""
CINEOS Multi-Platform Scanner
Uses SerpAPI to scan beyond Telegram:
  Google → indexed Telegram posts, news, APK sites
  YouTube → piracy channels, fraud tutorials
  Google News → bust tracking, new fraud types
  IndiaMART → counterfeit seller discovery
"""
import json, os, time, hashlib
from datetime import datetime
import urllib.request, urllib.parse

SERP_KEY  = '2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1'
API_BASE  = 'https://serpapi.com/search'
os.makedirs('reports/multiplatform', exist_ok=True)

def serp_search(query, engine='google', num=10, **extra):
    params = {
        'q':      query,
        'api_key': SERP_KEY,
        'engine':  engine,
        'num':     num,
        'hl':      'en',
        'gl':      'in',  # India results
        **extra
    }
    url = API_BASE + '?' + urllib.parse.urlencode(params)
    try:
        req  = urllib.request.urlopen(url, timeout=15)
        data = json.loads(req.read())
        return data
    except Exception as e:
        print(f"    SerpAPI error: {e}")
        return {}

def scan_telegram_via_google():
    """Find public Telegram fraud channels indexed by Google."""
    queries = [
        'site:t.me "satta matka" OR "cricket bet" OR "ipl bet"',
        'site:t.me "colour prediction" OR "91club" OR "wingo"',
        'site:t.me "bank account kit" OR "sim card earn"',
        'site:t.me "medicine wholesale" OR "below mrp pharma"',
        'site:t.me "first copy" OR "replica brand" wholesale',
        'site:t.me "guaranteed returns" OR "100% profit" trading',
        'site:t.me "fake job" OR "work from home advance fee"',
    ]

    found = []
    for q in queries:
        print(f"  Google: {q[:50]}...")
        data = serp_search(q, num=10)
        for r in data.get('organic_results', []):
            link  = r.get('link','')
            title = r.get('title','')
            snip  = r.get('snippet','')
            if 't.me/' in link:
                username = link.split('t.me/')[-1].split('/')[0].split('?')[0]
                found.append({
                    'source': 'google_telegram',
                    'username': username,
                    'title':    title,
                    'snippet':  snip,
                    'url':      link,
                    'query':    q,
                    'found_at': datetime.now().isoformat(),
                    'hash':     hashlib.sha256(link.encode()).hexdigest()[:12],
                })
                print(f"    FOUND: @{username}")
        time.sleep(2)

    return found

def scan_youtube_fraud():
    """Find fraud-related YouTube channels."""
    queries = [
        'ipl live stream free 2026 telegram',
        'colour prediction strategy 91club wingo india',
        'satta matka result tips free',
        'hotstar free watch ipl telegram link',
    ]

    found = []
    for q in queries:
        print(f"  YouTube: {q[:50]}...")
        data = serp_search(q, engine='youtube')
        for r in data.get('video_results', []):
            title = r.get('title','')
            link  = r.get('link','')
            chan  = r.get('channel',{}).get('name','')
            found.append({
                'source':   'youtube',
                'title':    title,
                'channel':  chan,
                'url':      link,
                'query':    q,
                'found_at': datetime.now().isoformat(),
            })
            print(f"    FOUND: {title[:50]}")
        time.sleep(2)

    return found

def scan_news_busts():
    """Track real fraud busts to build reference incident database."""
    queries = [
        'UPI fraud arrest India 2026',
        'telegram betting operator arrested India 2026',
        'fake medicine seized Telegram India 2026',
        'colour prediction fraud arrested India 2026',
        'counterfeit marketplace seller arrested India 2026',
    ]

    incidents = []
    for q in queries:
        print(f"  News: {q[:50]}...")
        data = serp_search(q, engine='google',
                           tbm='nws',  # news results
                           num=5)
        for r in data.get('news_results',
                   data.get('organic_results',[])):
            incidents.append({
                'source':   'news',
                'title':    r.get('title',''),
                'snippet':  r.get('snippet',''),
                'url':      r.get('link',''),
                'date':     r.get('date',''),
                'query':    q,
                'found_at': datetime.now().isoformat(),
            })
            print(f"    NEWS: {r.get('title','')[:50]}")
        time.sleep(2)

    return incidents

def scan_indiamart_counterfeit():
    """Find counterfeit sellers on IndiaMART."""
    queries = [
        'site:indiamart.com "first copy" OR "replica" shoes',
        'site:indiamart.com "duplicate" OR "copy" branded bag',
        'site:indiamart.com "master copy" watch electronics',
    ]

    found = []
    for q in queries:
        print(f"  IndiaMART: {q[:50]}...")
        data = serp_search(q, num=10)
        for r in data.get('organic_results', []):
            if 'indiamart.com' in r.get('link',''):
                found.append({
                    'source':  'indiamart',
                    'title':   r.get('title',''),
                    'snippet': r.get('snippet',''),
                    'url':     r.get('link',''),
                    'query':   q,
                    'found_at':datetime.now().isoformat(),
                })
                print(f"    FOUND: {r.get('title','')[:50]}")
        time.sleep(2)

    return found

def run_all():
    print("="*55)
    print("  CINEOS MULTI-PLATFORM SCANNER")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Platforms: Google · YouTube · News · IndiaMART")
    print("="*55)

    results = {
        'scanned_at': datetime.now().isoformat(),
        'telegram_via_google': [],
        'youtube':             [],
        'news_incidents':      [],
        'indiamart':           [],
    }

    print("\n[1/4] Scanning Telegram channels via Google...")
    results['telegram_via_google'] = scan_telegram_via_google()

    print("\n[2/4] Scanning YouTube for piracy/fraud...")
    results['youtube'] = scan_youtube_fraud()

    print("\n[3/4] Scanning news for reference busts...")
    results['news_incidents'] = scan_news_busts()

    print("\n[4/4] Scanning IndiaMART for counterfeit...")
    results['indiamart'] = scan_indiamart_counterfeit()

    # Save
    out = 'reports/multiplatform/scan_'+datetime.now().strftime('%Y%m%d_%H%M')+'.json'
    json.dump(results, open(out,'w'), indent=2, default=str)

    print(f"\n{'='*55}")
    print(f"  SCAN COMPLETE")
    print(f"  Telegram channels found: {len(results['telegram_via_google'])}")
    print(f"  YouTube results:         {len(results['youtube'])}")
    print(f"  News incidents:          {len(results['news_incidents'])}")
    print(f"  IndiaMART listings:      {len(results['indiamart'])}")
    print(f"  Saved: {out}")
    print(f"  Credits used: ~{7+4+5+3} SerpAPI searches")

if __name__ == '__main__':
    run_all()
