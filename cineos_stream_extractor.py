"""
CINEOS Stream URL Extractor
Uses headless browser to extract actual stream URLs
from obfuscated piracy stream players.
Legal: Only accesses publicly accessible URLs.
"""
import asyncio, re, json, datetime
from playwright.async_api import async_playwright

STREAM_PATTERNS = [
    r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
    r'https?://[^\s"\'<>]+/live[^\s"\'<>]{0,50}',
    r'https?://[^\s"\'<>]+\.ts[^\s"\'<>]*',
    r'https?://[^\s"\'<>]+/stream[^\s"\'<>]{0,50}',
    r'https?://[^\s"\'<>]+/hls[^\s"\'<>]{0,50}',
]

async def extract_stream_urls(player_url: str, timeout: int = 15) -> dict:
    """
    Extract actual stream URLs from an obfuscated player page.
    Uses network request monitoring to catch m3u8/stream requests.
    """
    print(f"  Extracting: {player_url[:60]}")
    
    found_streams = []
    network_requests = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        # Monitor ALL network requests
        async def on_request(request):
            url = request.url
            if any(pat in url for pat in ['.m3u8', '/live', '.ts', '/stream', '/hls', 'cdn']):
                network_requests.append({
                    'url': url,
                    'type': request.resource_type,
                    'method': request.method
                })
        
        page.on('request', on_request)
        
        try:
            await page.goto(player_url, timeout=timeout*1000, 
                          wait_until='networkidle')
            await asyncio.sleep(3)  # Wait for JS to execute
            
            # Get page content after JS execution
            content = await page.content()
            
            # Extract from rendered content
            for pattern in STREAM_PATTERNS:
                matches = re.findall(pattern, content)
                found_streams.extend(matches)
            
            # Get page title
            title = await page.title()
            
        except Exception as e:
            print(f"  Error: {e}")
        finally:
            await browser.close()
    
    # Combine all found streams
    all_streams = list(set(
        [r['url'] for r in network_requests 
         if any(x in r['url'] for x in ['.m3u8','/live','.ts','/stream'])]
        + found_streams
    ))
    
    return {
        'player_url': player_url,
        'streams_found': all_streams,
        'network_requests': network_requests[:10],
        'total': len(all_streams)
    }

async def scan_telegram_for_streams(channel: str, limit_posts: int = 10) -> dict:
    """
    Scan a Telegram channel and extract actual stream URLs
    from any player links found.
    """
    print(f"\n[CINEOS] Scanning @{channel} for live streams...")
    
    import httpx
    
    player_links = []
    stream_results = []
    
    async with httpx.AsyncClient(
        timeout=15,
        headers={"User-Agent":"Mozilla/5.0"},
        follow_redirects=True
    ) as client:
        # Get latest posts
        r = await client.get(f"https://t.me/s/{channel}")
        if r.status_code == 200:
            text = r.text
            
            # Find all post IDs
            post_ids = re.findall(r't\.me/' + channel + r'/(\d+)', text)
            post_ids = list(set(post_ids))[-limit_posts:]
            
            print(f"  Found {len(post_ids)} posts to check")
            
            # Check each post for player links
            for post_id in post_ids:
                try:
                    pr = await client.get(f"https://t.me/{channel}/{post_id}")
                    if pr.status_code == 200:
                        post_text = pr.text
                        
                        # Find non-Telegram links
                        links = re.findall(
                            r'href="(https?://(?!t\.me)[^\s"<>]+)"', 
                            post_text
                        )
                        
                        for link in links:
                            # Skip CDN/image links
                            if any(x in link for x in 
                                   ['telesco.pe','cdn','whatsapp','twitter',
                                    '.jpg','.png','.gif']):
                                continue
                            
                            if link not in player_links:
                                player_links.append(link)
                                print(f"  Post {post_id}: {link[:60]}")
                except:
                    pass
    
    print(f"\n  Found {len(player_links)} player links")
    
    # Extract streams from each player
    if player_links:
        print(f"  Extracting stream URLs using headless browser...")
        for player_url in player_links[:5]:
            result = await extract_stream_urls(player_url)
            if result['streams_found']:
                stream_results.append(result)
                print(f"  STREAMS FOUND: {result['streams_found'][:2]}")
    
    return {
        'channel': channel,
        'player_links': player_links,
        'stream_results': stream_results,
        'total_streams': sum(r['total'] for r in stream_results)
    }

async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--channel', default='IPL_L')
    ap.add_argument('--url', default=None, help='Direct player URL to extract')
    args = ap.parse_args()
    
    if args.url:
        result = await extract_stream_urls(args.url)
        print(f"\nStreams found: {result['total']}")
        for s in result['streams_found']:
            print(f"  {s}")
        print(f"\nNetwork requests intercepted: {len(result['network_requests'])}")
        for r in result['network_requests'][:5]:
            print(f"  [{r['type']}] {r['url'][:80]}")
    else:
        result = await scan_telegram_for_streams(args.channel)
        print(f"\n{'='*60}")
        print(f"  @{result['channel']} — Stream Extraction Report")
        print(f"{'='*60}")
        print(f"  Player links found: {len(result['player_links'])}")
        print(f"  Total streams extracted: {result['total_streams']}")
        for sr in result['stream_results']:
            print(f"\n  Player: {sr['player_url'][:50]}")
            for s in sr['streams_found']:
                print(f"    Stream: {s}")
        print(f"{'='*60}")

if __name__ == '__main__':
    asyncio.run(main())
