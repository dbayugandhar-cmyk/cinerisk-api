"""
CINEOS Instagram Deep Scanner
Finds fraud, counterfeit and piracy content on Instagram.
Uses Google search to find public Instagram posts.
Legal: Public posts only.
"""
import asyncio, httpx, re, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

INSTAGRAM_QUERIES = {
    'counterfeit_nike': [
        'site:instagram.com "first copy nike" OR "nike replica" india',
        'site:instagram.com "nike copy" price india buy',
        'site:instagram.com "aaa quality nike" india order',
    ],
    'counterfeit_samsung': [
        'site:instagram.com "samsung copy" OR "samsung replica" india',
        'site:instagram.com "first copy samsung" india buy',
    ],
    'counterfeit_fmcg': [
        'site:instagram.com "dove copy" OR "dettol wholesale" india',
        'site:instagram.com "first copy" soap shampoo india buy',
    ],
    'fraud_investment': [
        'site:instagram.com "guaranteed returns" investment india 2026',
        'site:instagram.com "daily profit" trading india telegram',
        'site:instagram.com "100% profit" crypto india',
    ],
    'fraud_betting': [
        'site:instagram.com "ipl betting" OR "cricket betting" tips india',
        'site:instagram.com "reddy anna" OR "mahadev book" india',
    ],
    'piracy_movies': [
        'site:instagram.com "free movie" download hindi telugu 2026',
        'site:instagram.com "web series free" download india link',
    ],
}

async def scan_instagram(category: str, queries: list) -> list:
    """Scan Instagram for a specific fraud/piracy category."""
    results = []
    seen = set()

    async with httpx.AsyncClient(timeout=12) as client:
        for query in queries:
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
                    if "instagram.com" not in url:
                        continue
                    if url in seen:
                        continue

                    title = item.get("title","")
                    snippet = item.get("snippet","")

                    seen.add(url)
                    results.append({
                        'url': url,
                        'title': title[:80],
                        'snippet': snippet[:120],
                        'category': category,
                        'query': query[:60],
                    })
                    print(f"  [{category}] {url[:65]}")

            except Exception as e:
                pass

    return results

async def full_instagram_scan():
    """Scan all Instagram categories."""
    print("[INSTAGRAM] Starting deep scan...")
    print(f"Categories: {len(INSTAGRAM_QUERIES)}")
    print(f"Total queries: {sum(len(v) for v in INSTAGRAM_QUERIES.values())}\n")

    all_results = {}
    total = 0

    for category, queries in INSTAGRAM_QUERIES.items():
        print(f"\n[{category}]")
        results = await scan_instagram(category, queries)
        all_results[category] = results
        total += len(results)
        print(f"  Found: {len(results)} posts")

    print(f"\n{'='*60}")
    print(f"  CINEOS INSTAGRAM SCAN RESULTS")
    print(f"{'='*60}")
    print(f"  Total posts found: {total}")

    for cat, results in all_results.items():
        if results:
            print(f"\n  [{cat}]: {len(results)} posts")
            for r in results[:2]:
                print(f"    {r['url'][:65]}")

    # Save
    os.makedirs('reports', exist_ok=True)
    path = f"reports/instagram_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump({
        'total': total,
        'by_category': all_results,
        'scanned_at': datetime.now().isoformat(),
    }, open(path,'w'), indent=2)
    print(f"\n  Saved: {path}")

    return all_results

if __name__ == '__main__':
    asyncio.run(full_instagram_scan())
