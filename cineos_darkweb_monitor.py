"""
CINEOS Dark Web Intelligence
Monitors clear-web dark web indexes and paste sites
for leaked data, counterfeit networks, piracy.
NO Tor access needed — uses public indexes only.
Legal: Public clearnet indexes only.
"""
import asyncio, httpx, re, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

# Clear-web dark web indexes and paste sites
DARKWEB_QUERIES = {
    'leaked_data': [
        'site:pastebin.com india database leak 2026',
        'site:paste.ee india credentials leak 2026',
        'site:ghostbin.com india data breach',
        'india database leaked site:github.com 2026',
    ],
    'counterfeit_network': [
        'india counterfeit supplier wholesale hidden site:reddit.com',
        'nike first copy wholesale supplier india dark',
        'india branded goods replica wholesale telegram hidden',
        'counterfeit india supplier network telegram 2026',
    ],
    'piracy_distribution': [
        'india piracy site mirror list 2026 telegram',
        'tamilblasters movierulz new domain 2026',
        'piracy cdn india new link 2026',
        'filmyzilla new link 2026 working',
    ],
    'fraud_infrastructure': [
        'india betting site backend infrastructure 2026',
        'reddy anna mahadev book server location',
        'india online gambling server host 2026',
        'fake investment site india infrastructure',
    ],
    'paste_sites': [
        'site:pastebin.com "india" "upi" fraud 2026',
        'site:pastebin.com india bank details leaked',
        'site:pastebin.com india aadhaar leaked 2026',
    ],
}

async def scan_darkweb_intelligence():
    print("[DARKWEB] Scanning clear-web dark web indexes...")
    results = {}
    total = 0

    async with httpx.AsyncClient(timeout=15) as client:
        for category, queries in DARKWEB_QUERIES.items():
            cat_results = []
            for query in queries:
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

                        # Skip known legitimate sites
                        skip = ['wikipedia','stackoverflow','github.com/about']
                        if any(s in url for s in skip):
                            continue

                        cat_results.append({
                            'url': url,
                            'title': title[:80],
                            'snippet': snippet[:120],
                            'category': category,
                            'risk_level': 'HIGH' if any(
                                x in url for x in
                                ['pastebin','paste','leak','dump']) else 'MEDIUM'
                        })
                except:
                    pass

            results[category] = cat_results
            total += len(cat_results)
            print(f"  [{category}]: {len(cat_results)} results")

    print(f"\n{'='*60}")
    print(f"  CINEOS DARK WEB INTELLIGENCE")
    print(f"{'='*60}")
    print(f"  Total findings: {total}")
    for cat, items in results.items():
        if items:
            print(f"\n  [{cat.upper()}]:")
            for item in items[:2]:
                print(f"    {item['url'][:65]}")

    os.makedirs('reports', exist_ok=True)
    path = f"reports/darkweb_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(results, open(path,'w'), indent=2)
    print(f"\n  Saved: {path}")
    return results

if __name__ == '__main__':
    asyncio.run(scan_darkweb_intelligence())
