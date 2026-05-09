import asyncio, json, os
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest

API_ID = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

SEARCH_TERMS = [
    'IPL stream', 'IPL free', 'IPL live', 'IPL 2026',
    'cricket stream', 'cricket free', 'cricket live',
    'hotstar free', 'JioHotstar free', 'hotstar piracy',
    'IPL betting', 'cricket betting', 'satta matka',
    'tamilblasters', 'movierulz', 'filmyzilla',
    'web series download', 'OTT free', 'movie download',
    'netflix free', 'amazon prime free',
]

async def deep_scan():
    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()
    print(f"[TELETHON] Connected — starting deep scan")
    print(f"[TELETHON] Searching {len(SEARCH_TERMS)} terms...\n")

    all_channels = {}

    for term in SEARCH_TERMS:
        try:
            result = await client(SearchRequest(q=term, limit=50))
            count = 0
            for chat in result.chats:
                if hasattr(chat, 'username') and chat.username:
                    uname = chat.username
                    if uname not in all_channels:
                        subs = getattr(chat, 'participants_count', 0) or 0
                        all_channels[uname] = {
                            'channel': uname,
                            'title': getattr(chat, 'title', ''),
                            'subscribers': subs,
                            'url': f"https://t.me/{uname}",
                            'found_via': term,
                        }
                        count += 1
            print(f"  [{term}]: {count} new channels")
        except Exception as e:
            print(f"  [{term}]: error — {e}")

    await client.disconnect()

    channels = sorted(all_channels.values(), key=lambda x: -x['subscribers'])

    print(f"\n{'='*65}")
    print(f"  CINEOS TELEGRAM DEEP SCAN")
    print(f"{'='*65}")
    print(f"  Total channels found: {len(channels)}")
    print(f"  Total reach: {sum(c['subscribers'] for c in channels):,}")
    print(f"\n  TOP 20:")
    for c in channels[:20]:
        print(f"    @{c['channel']:35} {c['subscribers']:>8,} subs")

    # Save report
    os.makedirs('reports', exist_ok=True)
    path = f"reports/telegram_deep_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(channels, open(path,'w'), indent=2)
    print(f"\n  Saved: {path}")

    # Update discovered_channels.json
    try:
        known = set(json.load(open('discovered_channels.json')))
    except:
        known = set()
    updated = list(known | {c['channel'] for c in channels})
    json.dump(updated, open('discovered_channels.json','w'))
    print(f"  Seed list updated: {len(updated)} total channels")

    return channels

asyncio.run(deep_scan())
