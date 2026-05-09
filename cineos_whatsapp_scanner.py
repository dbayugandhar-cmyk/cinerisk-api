"""
CINEOS WhatsApp Group Detection
Finds public WhatsApp groups sharing fraud/piracy links.
Uses web-indexed group invite links — public data only.
"""
import asyncio, httpx, re, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

WA_QUERIES = [
    'chat.whatsapp.com "ipl betting" OR "cricket betting" india join',
    'chat.whatsapp.com "free movies" download india join group',
    'chat.whatsapp.com "guaranteed returns" investment india',
    'chat.whatsapp.com "satta matka" india join',
    'chat.whatsapp.com "nike copy" OR "first copy" india buy',
    'chat.whatsapp.com "crypto profit" guaranteed india',
    'chat.whatsapp.com "web series free" download india join',
    'chat.whatsapp.com "reddy anna" OR "mahadev book" india',
]

async def scan_whatsapp_groups():
    print("[WHATSAPP] Scanning for public group links...")
    groups = []
    seen = set()

    async with httpx.AsyncClient(timeout=12) as client:
        for query in WA_QUERIES:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "q": query,
                    "api_key": SERP_KEY,
                    "num": 10,
                    "engine": "google",
                    "gl": "in"
                })

                for item in r.json().get("organic_results", []):
                    url = item.get("link","")
                    snippet = item.get("snippet","")
                    combined = url + snippet

                    # Find WhatsApp invite links
                    wa_links = re.findall(
                        r'chat\.whatsapp\.com/([A-Za-z0-9]{20,})',
                        combined
                    )

                    for link in wa_links:
                        full_url = f"https://chat.whatsapp.com/{link}"
                        if full_url not in seen:
                            seen.add(full_url)
                            groups.append({
                                'invite_url': full_url,
                                'source': url[:60],
                                'snippet': snippet[:100],
                                'query': query[:60],
                            })
                            print(f"  FOUND: {full_url}")

            except Exception as e:
                pass

    print(f"\n{'='*60}")
    print(f"  CINEOS WHATSAPP INTELLIGENCE")
    print(f"{'='*60}")
    print(f"  Public groups found: {len(groups)}")
    for g in groups[:10]:
        print(f"  {g['invite_url']}")
        print(f"    Source: {g['source']}")

    os.makedirs('reports', exist_ok=True)
    path = f"reports/whatsapp_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(groups, open(path,'w'), indent=2)
    print(f"\n  Saved: {path}")
    print(f"{'='*60}")
    return groups

if __name__ == '__main__':
    asyncio.run(scan_whatsapp_groups())
