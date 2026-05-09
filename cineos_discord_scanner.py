"""
CINEOS Discord Intelligence Scanner
Finds public Discord servers for piracy/fraud.
Uses public directories — no auth needed.
"""
import asyncio, httpx, re, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

DISCORD_QUERIES = [
    'site:disboard.org cricket streaming india server',
    'site:disboard.org ipl free stream server',
    'site:disboard.org movies free download india',
    'site:disboard.org crypto signals india guaranteed',
    'site:disboard.org betting tips cricket india',
    'site:top.gg cricket stream india bot',
    'discord.gg "ipl stream" OR "cricket free" india 2026',
    'discord.gg "free movies" india 2026 join',
    'discord.gg "crypto signals" india guaranteed profit',
    'discord server "ipl betting" india invite link 2026',
]

async def scan_discord():
    print("[DISCORD] Scanning public directories...")
    servers = []
    seen = set()

    async with httpx.AsyncClient(timeout=12) as client:
        for query in DISCORD_QUERIES:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "q": query,
                    "api_key": SERP_KEY,
                    "num": 10,
                    "engine": "google",
                    "gl": "in"
                })

                for item in r.json().get("organic_results",[]):
                    url = item.get("link","")
                    title = item.get("title","")
                    snippet = item.get("snippet","")
                    combined = url + title + snippet

                    # Extract Discord invite links
                    invites = re.findall(
                        r'discord\.gg/([A-Za-z0-9]{6,20})', combined)
                    for inv in invites:
                        if inv not in seen:
                            seen.add(inv)
                            servers.append({
                                'invite': f"https://discord.gg/{inv}",
                                'title': title[:60],
                                'source': url[:60],
                                'snippet': snippet[:100],
                                'query': query[:50],
                            })
                            print(f"  FOUND: discord.gg/{inv} — {title[:40]}")

                    # Also capture disboard listings
                    if 'disboard.org' in url:
                        servers.append({
                            'invite': url,
                            'title': title[:60],
                            'source': 'disboard.org',
                            'snippet': snippet[:100],
                            'query': query[:50],
                        })

            except Exception as e:
                pass

    print(f"\n{'='*60}")
    print(f"  CINEOS DISCORD INTELLIGENCE")
    print(f"{'='*60}")
    print(f"  Servers found: {len(servers)}")
    for s in servers[:10]:
        print(f"  {s['invite'][:50]}")
        print(f"    {s['title'][:50]}")

    os.makedirs('reports', exist_ok=True)
    path = f"reports/discord_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(servers, open(path,'w'), indent=2)
    print(f"\n  Saved: {path}")
    return servers

if __name__ == '__main__':
    asyncio.run(scan_discord())
