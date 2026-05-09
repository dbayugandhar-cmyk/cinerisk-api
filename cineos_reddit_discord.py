"""
CINEOS Reddit + Discord Stream Discovery
No authentication needed — public data only.
"""
import asyncio, httpx, re, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

async def scan_reddit_streams(event: str = 'IPL 2026') -> list:
    """Find illegal streams posted on Reddit."""
    print(f"[REDDIT] Scanning for: {event}")
    results = []
    
    async with httpx.AsyncClient(timeout=12,
        headers={"User-Agent":"Mozilla/5.0"},
        follow_redirects=True) as client:
        
        # Scan known piracy subreddits directly
        subreddits = [
            'IPLstreams', 'cricketstreams', 'soccerstreams',
            'nbastreams', 'MMAstreams', 'boxing',
        ]
        
        for sub in subreddits:
            try:
                r = await client.get(
                    f"https://www.reddit.com/r/{sub}/new.json?limit=25",
                    headers={"User-Agent": "CINEOS/1.0"}
                )
                if r.status_code != 200:
                    continue
                    
                posts = r.json().get('data',{}).get('children',[])
                for post in posts:
                    p = post.get('data',{})
                    title = p.get('title','').lower()
                    url = p.get('url','')
                    selftext = p.get('selftext','').lower()
                    combined = title + ' ' + selftext
                    
                    # Check for stream signals
                    if any(x in combined for x in 
                           ['stream','watch','live','free','link']):
                        results.append({
                            'subreddit': sub,
                            'title': p.get('title','')[:80],
                            'url': f"https://reddit.com{p.get('permalink','')}",
                            'score': p.get('score',0),
                            'comments': p.get('num_comments',0),
                            'created': datetime.fromtimestamp(
                                p.get('created_utc',0)).strftime('%Y-%m-%d %H:%M'),
                        })
                
                print(f"  r/{sub}: {len(posts)} posts scanned")
                
            except Exception as e:
                print(f"  r/{sub}: {e}")
        
        # Also search Google for Reddit stream links
        if SERP_KEY:
            queries = [
                f'site:reddit.com "{event}" stream watch free',
                f'site:reddit.com IPL cricket stream links 2026',
            ]
            for q in queries:
                try:
                    r = await client.get("https://serpapi.com/search", params={
                        "q": q, "api_key": SERP_KEY,
                        "num": 10, "engine": "google"
                    })
                    for item in r.json().get("organic_results",[]):
                        link = item.get("link","")
                        if "reddit.com" in link:
                            results.append({
                                'subreddit': 'google_found',
                                'title': item.get("title","")[:80],
                                'url': link,
                                'score': 0,
                                'comments': 0,
                                'created': 'recent',
                            })
                except: pass
    
    return results

async def scan_discord_servers(event: str = 'IPL 2026') -> list:
    """Find public Discord servers for illegal streams."""
    print(f"[DISCORD] Scanning for: {event}")
    results = []
    
    async with httpx.AsyncClient(timeout=12,
        headers={"User-Agent":"Mozilla/5.0"},
        follow_redirects=True) as client:
        
        # Search disboard.org — public Discord server directory
        search_terms = ['cricket', 'ipl', 'sports stream', 'free stream']
        
        for term in search_terms:
            try:
                r = await client.get(
                    f"https://disboard.org/servers/tag/{term.replace(' ','-')}",
                )
                if r.status_code == 200:
                    # Find Discord invite links
                    invites = re.findall(r'discord\.gg/(\w+)', r.text)
                    server_names = re.findall(
                        r'<span[^>]*class="[^"]*server-name[^"]*"[^>]*>([^<]+)', r.text)
                    member_counts = re.findall(
                        r'(\d[\d,]+)\s*[Mm]embers', r.text)
                    
                    for i, invite in enumerate(invites[:5]):
                        results.append({
                            'server': server_names[i] if i < len(server_names) else 'Unknown',
                            'invite': f"https://discord.gg/{invite}",
                            'members': member_counts[i] if i < len(member_counts) else '0',
                            'tag': term,
                            'source': 'disboard.org'
                        })
                    print(f"  disboard/{term}: {len(invites)} servers found")
            except Exception as e:
                print(f"  disboard/{term}: {e}")
        
        # Also search Google for Discord invite links
        if SERP_KEY:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "q": f'discord.gg IPL cricket stream free 2026',
                    "api_key": SERP_KEY, "num": 10, "engine": "google"
                })
                for item in r.json().get("organic_results",[]):
                    combined = item.get("link","") + item.get("snippet","")
                    invites = re.findall(r'discord\.gg/(\w+)', combined)
                    for inv in invites:
                        results.append({
                            'server': item.get("title","")[:50],
                            'invite': f"https://discord.gg/{inv}",
                            'members': '0',
                            'tag': 'google_found',
                            'source': 'google'
                        })
            except: pass
    
    return results

async def full_platform_scan(event: str = 'IPL 2026') -> dict:
    """Scan Reddit + Discord + Telegram for a live event."""
    print(f"\n{'='*60}")
    print(f"CINEOS MULTI-PLATFORM SCAN — {event}")
    print(f"{'='*60}\n")
    
    reddit, discord = await asyncio.gather(
        scan_reddit_streams(event),
        scan_discord_servers(event)
    )
    
    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Reddit posts:    {len(reddit)}")
    print(f"  Discord servers: {len(discord)}")
    
    if reddit:
        print(f"\nTOP REDDIT POSTS:")
        for p in sorted(reddit, key=lambda x:-x['score'])[:5]:
            print(f"  r/{p['subreddit']}: {p['title'][:50]}")
            print(f"    {p['url'][:65]}")
    
    if discord:
        print(f"\nDISCORD SERVERS FOUND:")
        for d in discord[:5]:
            print(f"  {d['server'][:40]} — {d['members']} members")
            print(f"    {d['invite']}")
    
    print(f"{'='*60}")
    
    return {'reddit': reddit, 'discord': discord}

if __name__ == '__main__':
    result = asyncio.run(full_platform_scan('IPL 2026'))
    
    os.makedirs('reports', exist_ok=True)
    json.dump(result, 
              open(f"reports/multiplatform_{datetime.now().strftime('%Y%m%d_%H%M')}.json",'w'),
              indent=2)
