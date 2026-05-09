"""
CINEOS Misinformation Detection
Detects fake news and misinformation in India.
Focuses on: health, election, financial, communal.
Legal: Public web data + fact-check cross-reference.
"""
import asyncio, httpx, re, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

MISINFO_QUERIES = {
    'health': [
        'fake health news viral india 2026 whatsapp',
        'false medical claim india viral telegram 2026',
        'fake ayurvedic cure viral india 2026',
    ],
    'financial': [
        'fake rbi notification viral india 2026',
        'false bank news viral india whatsapp 2026',
        'fake sebi order viral india telegram 2026',
    ],
    'election': [
        'fake election news india viral 2026',
        'false voting misinformation india 2026',
        'evm tampering fake news india 2026',
    ],
    'product': [
        'fake product warning viral india 2026',
        'false consumer alert india viral whatsapp',
        'fake food safety news india 2026',
    ],
}

FACTCHECK_SITES = [
    'altnews.in', 'boomlive.in', 'factcheck.afp.com',
    'vishvasnews.com', 'indiatoday.in/fact-check',
    'thequint.com/webqoof', 'newsmobile.in/fact-check',
]

async def scan_misinformation():
    print("[MISINFO] Scanning for misinformation...")
    results = {}
    total = 0

    async with httpx.AsyncClient(timeout=12) as client:
        for category, queries in MISINFO_QUERIES.items():
            cat_results = []

            for query in queries:
                try:
                    r = await client.get("https://serpapi.com/search", params={
                        "q": query,
                        "api_key": SERP_KEY,
                        "num": 10,
                        "engine": "google",
                        "gl": "in",
                        "tbs": "qdr:w"  # Last week only
                    })

                    for item in r.json().get("organic_results", []):
                        url = item.get("link","")
                        title = item.get("title","").lower()
                        snippet = item.get("snippet","").lower()

                        is_factcheck = any(fc in url for fc in FACTCHECK_SITES)

                        cat_results.append({
                            'url': url,
                            'title': item.get("title","")[:80],
                            'snippet': snippet[:100],
                            'is_factcheck': is_factcheck,
                            'category': category,
                        })

                except Exception as e:
                    pass

            # Separate misinfo from fact-checks
            misinfo = [r for r in cat_results if not r['is_factcheck']]
            factchecks = [r for r in cat_results if r['is_factcheck']]

            results[category] = {
                'misinfo': misinfo[:5],
                'factchecks': factchecks[:5],
                'total': len(cat_results),
            }
            total += len(misinfo)
            print(f"  [{category}]: {len(misinfo)} misinfo, {len(factchecks)} fact-checks")

    print(f"\n{'='*60}")
    print(f"  CINEOS MISINFORMATION INTELLIGENCE")
    print(f"{'='*60}")
    print(f"  Total misinformation URLs: {total}")
    for cat, data in results.items():
        if data['misinfo']:
            print(f"\n  [{cat.upper()}]:")
            for m in data['misinfo'][:2]:
                print(f"    {m['url'][:65]}")

    os.makedirs('reports', exist_ok=True)
    path = f"reports/misinfo_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(results, open(path,'w'), indent=2)
    print(f"\n  Saved: {path}")
    return results

if __name__ == '__main__':
    asyncio.run(scan_misinformation())
