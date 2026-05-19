"""
CINEOS SerpAPI Channel Discovery
Finds NEW Telegram channel usernames via Google.
Uses queries that actually return t.me links.
Does NOT try to extract phones from Google (impossible).
Phones come from deep scan AFTER channels are added.

Run: python3 cineos_serp_discovery.py
Crontab: 0 6 * * * (already scheduled)
Budget: 50 queries/run = 50 SerpAPI credits
"""
import json, re, urllib.request, urllib.parse, time, os
from datetime import datetime, timezone, timedelta

SERP_KEY    = '2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1'
CHANNELS_FILE = 'reports/all_channels.json'
IST         = timezone(timedelta(hours=5, minutes=30))

TG_RE    = re.compile(r't\.me/([a-zA-Z0-9_]{5,32})', re.I)
SKIP     = {'joinchat','share','addstickers','proxy','socks','boost','c','s'}
CAT_MAP  = {
    'illegal_betting':    ['mahadev','reddy anna','radhe exchange','laser247','world777',
                           'sky exchange','diamond exchange','tiger exchange','betbhai',
                           'cricbet','fairplay','lotus book','satta matka','kalyan matka',
                           'cricket id','betting id','book id'],
    'colour_prediction':  ['91club','daman game','bdg win','tiranga game','ok win','jalwa'],
    'upi_mule':           ['upi mule','bank account kit','sim card sell','otp service',
                           'account rent','atm card commission'],
    'counterfeit_pharma': ['ozempic','tramadol','sildenafil','steroid','kamagra',
                           'medicine without prescription','generic medicine'],
    'crypto_fraud':       ['usdt inr p2p','crypto pump signal','bitcoin doubler india',
                           'fake trading app','crypto task earn'],
    'investment_fraud':   ['guaranteed profit trading','sebi tips free','sure shot calls',
                           'pig butchering','fake broker'],
}

# Queries proven to return t.me links
QUERY_TEMPLATES = [
    '{brand} telegram channel join link India',
    '{brand} t.me India 2026',
    '{brand} telegram group India join',
    'telegram {brand} India channel link',
    '{brand} whatsapp telegram India contact',
]

def serp_search(query):
    params = {
        'q': query, 'api_key': SERP_KEY,
        'engine': 'google', 'num': 10,
        'gl': 'in', 'hl': 'en', 'no_cache': 'true'
    }
    url = 'https://serpapi.com/search?' + urllib.parse.urlencode(params)
    try:
        d = json.loads(urllib.request.urlopen(url, timeout=12).read())
        return d.get('organic_results', [])
    except Exception as e:
        print(f'  SerpAPI error: {e}')
        return []

def extract_links(results):
    links = set()
    for r in results:
        text = str(r.get('title',''))+' '+str(r.get('snippet',''))+' '+str(r.get('link',''))
        for m in TG_RE.findall(text):
            if m.lower() not in SKIP and len(m) >= 5:
                links.add(m)
    return links

def main():
    ts = datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')
    print(f'[{ts}] CINEOS SerpAPI Channel Discovery')
    print('='*50)

    channels = json.load(open(CHANNELS_FILE))
    existing = {c.get('username','').lower() for c in channels}
    print(f'Existing channels: {len(existing)}')

    new_channels = []
    queries_used = 0
    budget = 50  # Use 50 queries max per run

    for cat, brands in CAT_MAP.items():
        if queries_used >= budget:
            break
        print(f'\n[{cat}]')
        for brand in brands[:3]:  # 3 brands per category
            if queries_used >= budget:
                break
            # Use best performing template
            q = f'{brand} telegram channel join link India'
            results = serp_search(q)
            queries_used += 1
            links = extract_links(results)
            new = [l for l in links if l.lower() not in existing]
            if new:
                print(f'  "{brand}": found {new}')
                for username in new:
                    new_channels.append({
                        'username': username,
                        'category': cat,
                        'source': 'serp_discovery',
                        'discovered_at': datetime.now(IST).isoformat(),
                        'subscribers': 0,
                        'phones': [],
                        'upi_ids': [],
                        'last_scanned': None,
                        'status': 'pending_scan',
                    })
                    existing.add(username.lower())
            time.sleep(0.4)

    print()
    print('='*50)
    print(f'Queries used: {queries_used}')
    print(f'New channels found: {len(new_channels)}')

    if new_channels:
        channels.extend(new_channels)
        json.dump(channels, open(CHANNELS_FILE,'w'), indent=2, default=str)
        print(f'Added to {CHANNELS_FILE}')
        print()
        print('New channels (will be scanned at 4:30am tomorrow):')
        for c in new_channels[:10]:
            print(f'  @{c["username"]} — {c["category"]}')
        if len(new_channels) > 10:
            print(f'  ...and {len(new_channels)-10} more')

    # Check remaining SerpAPI budget
    try:
        params = {'api_key': SERP_KEY, 'engine': 'google', 'q': 'test'}
        url = 'https://serpapi.com/account?' + urllib.parse.urlencode({'api_key': SERP_KEY})
        acct = json.loads(urllib.request.urlopen(url, timeout=10).read())
        remaining = acct.get('total_searches_left', 'unknown')
        print(f'\nSerpAPI remaining: {remaining} searches')
    except:
        pass

    print('='*50)
    return len(new_channels)

if __name__ == '__main__':
    main()
