"""
CINEOS Reddit Deep Scanner
Monitors India-specific subreddits for piracy,
fraud, counterfeit and scam discussions.
Uses Reddit public JSON API — no auth needed.
"""
import asyncio, httpx, json, os, re
from datetime import datetime

SUBREDDITS = {
    'piracy': [
        'piracy', 'DataHoarder', 'opendirectories',
        'IPLstreams', 'cricketstreams', 'india',
    ],
    'fraud': [
        'IndiaInvestments', 'personalfinanceindia',
        'CryptoCurrencyIndia', 'IndiaStocks',
        'LegalAdviceIndia', 'india',
    ],
    'counterfeit': [
        'india', 'IndiaShopping', 'desideals',
        'frugalmalefashionadvice',
    ],
}

FRAUD_KEYWORDS = [
    'guaranteed returns', 'daily profit', 'risk free',
    'ipl betting', 'cricket betting', 'satta',
    'first copy', 'replica', 'master copy',
    'tamilblasters', 'movierulz', 'filmyzilla',
    'free stream', 'hotstar free', 'netflix crack',
    'pump signal', 'crypto 100x', '1xbet',
]

async def scan_subreddit(client, subreddit: str, category: str) -> list:
    findings = []
    try:
        r = await client.get(
            f"https://www.reddit.com/r/{subreddit}/new.json?limit=50",
            headers={"User-Agent": "CINEOS-Intelligence/1.0"}
        )
        if r.status_code != 200:
            return []

        posts = r.json().get('data',{}).get('children',[])
        for post in posts:
            p = post.get('data',{})
            title = p.get('title','').lower()
            text = p.get('selftext','').lower()
            combined = title + ' ' + text

            matched = [kw for kw in FRAUD_KEYWORDS if kw in combined]
            if matched:
                findings.append({
                    'subreddit': subreddit,
                    'category': category,
                    'title': p.get('title','')[:80],
                    'url': f"https://reddit.com{p.get('permalink','')}",
                    'score': p.get('score',0),
                    'comments': p.get('num_comments',0),
                    'keywords_matched': matched,
                    'created': datetime.fromtimestamp(
                        p.get('created_utc',0)).strftime('%Y-%m-%d %H:%M'),
                })
    except Exception as e:
        pass
    return findings

async def deep_reddit_scan():
    print("[REDDIT] Starting deep scan...")
    all_findings = []

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for category, subs in SUBREDDITS.items():
            for sub in subs:
                findings = await scan_subreddit(client, sub, category)
                if findings:
                    print(f"  r/{sub} [{category}]: {len(findings)} matches")
                    all_findings.extend(findings)
                await asyncio.sleep(1)  # Rate limit Reddit

    # Sort by score
    all_findings.sort(key=lambda x: -x['score'])

    print(f"\n{'='*60}")
    print(f"  CINEOS REDDIT INTELLIGENCE")
    print(f"{'='*60}")
    print(f"  Total findings: {len(all_findings)}")

    by_cat = {}
    for f in all_findings:
        by_cat[f['category']] = by_cat.get(f['category'],0) + 1
    for cat, count in by_cat.items():
        print(f"  {cat}: {count}")

    if all_findings:
        print(f"\n  TOP FINDINGS:")
        for f in all_findings[:5]:
            print(f"  [{f['score']} upvotes] {f['title'][:55]}")
            print(f"    Keywords: {f['keywords_matched'][:3]}")
            print(f"    URL: {f['url'][:65]}")

    os.makedirs('reports', exist_ok=True)
    path = f"reports/reddit_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(all_findings, open(path,'w'), indent=2)
    print(f"\n  Saved: {path}")
    return all_findings

if __name__ == '__main__':
    asyncio.run(deep_reddit_scan())
