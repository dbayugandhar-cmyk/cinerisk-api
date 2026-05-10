"""
CINEOS Instagram Account Enricher
Takes Instagram post URLs found by scanner.
Extracts: account handle, follower count, bio, post count.
Converts anonymous posts to attributed accounts.
"""
import httpx, json, os, asyncio, re
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY', '')

async def enrich_instagram_account(post_url: str) -> dict:
    """Extract account info from Instagram post URL."""
    result = {'url': post_url, 'enriched': False}

    # Extract username from URL
    match = re.search(r'instagram\.com/([^/?]+)', post_url)
    if not match:
        return result

    username = match.group(1)
    if username in ('p', 'reel', 'stories', 'explore'):
        return result

    result['username'] = username

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            # Search for account info
            r = await client.get("https://serpapi.com/search", params={
                "engine":   "google",
                "q":        f"site:instagram.com/{username} followers bio",
                "api_key":  SERP_KEY,
                "num":      3,
            })
            data = r.json()

            # Try to get account snippet
            for item in data.get('organic_results', []):
                if username.lower() in item.get('link','').lower():
                    snippet = item.get('snippet', '')
                    result['snippet']  = snippet
                    result['enriched'] = True

                    # Extract follower count from snippet
                    fol_match = re.search(r'([\d,\.]+[KMk]?)\s*[Ff]ollowers', snippet)
                    if fol_match:
                        result['followers'] = fol_match.group(1)
                    break

        except Exception as e:
            result['error'] = str(e)

    return result

async def enrich_all_instagram():
    """Enrich all Instagram findings with account data."""
    # Load omni scan results which contain Instagram findings
    instagram_posts = []
    for f in os.listdir('reports'):
        if 'omni' in f and f.endswith('.json'):
            try:
                data = json.load(open(f'reports/{f}'))
                for item in data:
                    if isinstance(item, dict):
                        link = item.get('link', item.get('url', ''))
                        if 'instagram.com' in link:
                            instagram_posts.append(link)
            except:
                pass

    if not instagram_posts:
        print("No Instagram findings to enrich")
        print("Run cineos_omni_scanner.py first to populate findings")
        return

    instagram_posts = list(set(instagram_posts))[:50]
    print(f"Enriching {len(instagram_posts)} Instagram posts...")

    enriched = []
    async with asyncio.Semaphore(3):
        for url in instagram_posts:
            result = await enrich_instagram_account(url)
            if result.get('enriched'):
                enriched.append(result)
                username  = result.get('username', '')
                followers = result.get('followers', 'unknown')
                print(f"  @{username:30} {followers} followers")

    print(f"\nEnriched: {len(enriched)}/{len(instagram_posts)} Instagram accounts")
    json.dump(enriched,
              open('reports/instagram_enriched.json', 'w'),
              indent=2)
    return enriched

asyncio.run(enrich_all_instagram())
