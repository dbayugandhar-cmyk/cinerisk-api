"""
CINEOS Channel Discovery
Run from Mac weekly to find new piracy Telegram channels.
Results get added to the Railway seed list automatically.
"""
import asyncio, httpx, re, json
from datetime import datetime

KNOWN_CHANNELS_FILE = 'discovered_channels.json'

async def discover_new_channels():
    # Load existing known channels
    try:
        known = set(json.load(open(KNOWN_CHANNELS_FILE)))
    except:
        known = set()
    
    new_confirmed = []
    
    async with httpx.AsyncClient(
        timeout=12,
        headers={"User-Agent":"Mozilla/5.0"},
        follow_redirects=True
    ) as client:
        
        # Seed channels to cross-reference
        seeds = [
            "IPL_L","RealCricPoint","CricketStreamsLive",
            "IPLstreams","CricketBetting","IPLBetting",
            "SportsFreeStreams","T20Live","LiveCricket",
        ]
        
        candidates = set()
        
        print(f"[DISCOVERY] Scanning {len(seeds)} seed channels...")
        for seed in seeds:
            try:
                r = await client.get(f"https://t.me/s/{seed}")
                if r.status_code == 200:
                    found = re.findall(
                        r't\.me/([a-zA-Z][a-zA-Z0-9_]{4,30})', r.text)
                    for ch in found:
                        if ch not in known and ch not in seeds and \
                           ch not in ['share','joinchat','addstickers','s']:
                            candidates.add(ch)
            except: pass
        
        print(f"[DISCOVERY] {len(candidates)} candidates to verify...")
        
        # Verify each candidate
        piracy_signals = [
            'cricket','ipl','stream','live','sport',
            'football','premier','league','match','t20',
            'movie','download','free','leaked'
        ]
        
        for ch in list(candidates)[:30]:
            try:
                r = await client.get(f"https://t.me/s/{ch}")
                if r.status_code != 200:
                    continue
                text = r.text.lower()
                
                # Check piracy signals
                signal_count = sum(1 for s in piracy_signals if s in text)
                if signal_count < 2:
                    continue
                
                # Get subscriber count
                subs_match = re.search(
                    r'(\d[\d\s,]*)\s*(members|subscribers)', r.text, re.I)
                subs = 0
                if subs_match:
                    subs = int(re.sub(r'[^\d]','', subs_match.group(1)) or 0)
                
                new_confirmed.append({
                    'channel': ch,
                    'subscribers': subs,
                    'signals': signal_count,
                    'discovered_at': datetime.now().isoformat()
                })
                known.add(ch)
                print(f"  CONFIRMED: @{ch} ({subs:,} subs, {signal_count} signals)")
                
            except: pass
    
    # Save updated known channels
    json.dump(list(known), open(KNOWN_CHANNELS_FILE,'w'), indent=2)
    
    print(f"\n[DISCOVERY] Found {len(new_confirmed)} new channels")
    return new_confirmed

async def update_gateway_channels(new_channels: list):
    """Add new channels to the Railway seed list."""
    if not new_channels:
        print("No new channels to add")
        return
    
    content = open('cineos_api_gateway.py').read()
    
    # Find the CHANNELS list
    idx = content.find('"ChessOlympiadFree",')
    if idx == -1:
        print("Channel list not found")
        return
    
    # Add new channels before ChessOlympiadFree
    new_entries = '\n'.join([
        f'            "{c["channel"]}",'
        for c in new_channels
    ])
    
    old = '"ChessOlympiadFree",'
    new = new_entries + '\n            "ChessOlympiadFree",'
    
    content = content.replace(old, new, 1)
    open('cineos_api_gateway.py','w').write(content)
    
    print(f"Added {len(new_channels)} channels to gateway")

if __name__ == '__main__':
    import subprocess
    
    new = asyncio.run(discover_new_channels())
    
    if new:
        asyncio.run(update_gateway_channels(new))
        
        # Auto commit and push
        subprocess.run(['git','add','cineos_api_gateway.py',
                       KNOWN_CHANNELS_FILE])
        subprocess.run(['git','commit','-m',
            f'Discovery: +{len(new)} new Telegram channels'])
        subprocess.run(['git','push'])
        print("Pushed to Railway")
    
    print(f"\nTotal channels now: {len(json.load(open(KNOWN_CHANNELS_FILE)))}")
