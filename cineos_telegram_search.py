"""
CINEOS Telegram Native Search
Uses Telegram's own search API to find channels by keyword.
Much better than Google — finds channels not indexed anywhere.
Runs AFTER deep scan to add new channels to queue.

Run: python3 cineos_telegram_search.py
Crontab: 30 5 * * * (after deep scan completes)
"""
import asyncio, json, re, time
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.errors import FloodWaitError

API_ID   = 38636931
API_HASH = '852280f65386a00114ff7453eac7849b'
SESSION  = 'cineos_session'
IST      = timezone(timedelta(hours=5, minutes=30))
CHANNELS_FILE = 'reports/all_channels.json'

# Keywords in multiple languages that operators actually use
SEARCH_TERMS = [
    # English betting
    'cricket betting id', 'online cricket id', 'betting id whatsapp',
    'mahadev book id', 'reddy anna id', 'laser247 id',
    'diamond exchange id', 'sky exchange cricket',
    # Hindi betting
    'क्रिकेट सट्टा', 'ऑनलाइन बेटिंग', 'क्रिकेट आईडी',
    'सट्टा मटका', 'कल्याण मटका', 'फरीदाबाद सट्टा',
    # Telugu betting
    'క్రికెట్ బెట్టింగ్', 'రెడ్డి అన్న',
    # Colour prediction
    '91club earn', 'daman game earn', 'colour prediction earn',
    'bdg win prediction', 'tiranga game',
    # UPI mule
    'bank account sell', 'upi id sell', 'sim card sell india',
    'account kit earn', 'otp service india',
    # Pharma
    'medicine online india cod', 'generic medicine delivery',
    # Crypto fraud
    'usdt inr buy sell', 'crypto p2p india',
    'bitcoin earn daily india',
    # Investment fraud
    'stock tips guaranteed', 'sebi registered tips',
    'sure shot intraday calls',
]

CATEGORY_MAP = {
    'cricket': 'illegal_betting', 'satta': 'illegal_betting',
    'matka': 'illegal_betting', 'betting': 'illegal_betting',
    'mahadev': 'illegal_betting', 'reddy': 'illegal_betting',
    'laser': 'illegal_betting', 'exchange': 'illegal_betting',
    'book id': 'illegal_betting', 'सट्टा': 'illegal_betting',
    'क्रिकेट': 'illegal_betting', 'రెడ్డి': 'illegal_betting',
    '91club': 'colour_prediction', 'daman': 'colour_prediction',
    'colour prediction': 'colour_prediction', 'bdg': 'colour_prediction',
    'tiranga': 'colour_prediction',
    'account sell': 'upi_mule', 'upi sell': 'upi_mule',
    'sim sell': 'upi_mule', 'otp service': 'upi_mule',
    'medicine': 'counterfeit_pharma', 'generic': 'counterfeit_pharma',
    'usdt': 'crypto_fraud', 'bitcoin earn': 'crypto_fraud',
    'stock tips': 'investment_fraud', 'sebi': 'investment_fraud',
}

def detect_cat(text):
    t = text.lower()
    for kw, cat in CATEGORY_MAP.items():
        if kw in t:
            return cat
    return 'unknown'

async def search_telegram(client, query, limit=20):
    """Use Telegram's native search to find channels."""
    try:
        result = await client(SearchRequest(q=query, limit=limit))
        channels = []
        for chat in result.chats:
            if hasattr(chat, 'username') and chat.username:
                channels.append({
                    'username': chat.username,
                    'title': getattr(chat, 'title', ''),
                    'subscribers': getattr(chat, 'participants_count', 0) or 0,
                })
        return channels
    except FloodWaitError as e:
        print(f'  Flood wait {e.seconds}s')
        await asyncio.sleep(e.seconds + 2)
        return []
    except Exception as e:
        return []

async def run():
    ts = datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')
    print(f'[{ts}] CINEOS Telegram Native Search')
    print('='*50)

    channels = json.load(open(CHANNELS_FILE))
    existing = {c.get('username','').lower() for c in channels}
    print(f'Existing channels: {len(existing)}')

    new_channels = []

    async with TelegramClient(SESSION, API_ID, API_HASH) as client:
        for i, term in enumerate(SEARCH_TERMS):
            print(f'[{i+1:2}/{len(SEARCH_TERMS)}] Searching: "{term}"')
            results = await search_telegram(client, term, limit=20)
            added = 0
            for ch in results:
                uname = ch['username']
                if uname.lower() not in existing and len(uname) >= 5:
                    cat = detect_cat(ch['title'] + ' ' + uname + ' ' + term)
                    new_channels.append({
                        'username': uname,
                        'title': ch['title'],
                        'category': cat,
                        'subscribers': ch['subscribers'],
                        'source': 'telegram_search',
                        'search_term': term,
                        'discovered_at': datetime.now(IST).isoformat(),
                        'phones': [],
                        'upi_ids': [],
                        'last_scanned': None,
                        'status': 'pending_scan',
                    })
                    existing.add(uname.lower())
                    added += 1
            if added:
                print(f'  → {added} new channels found')
            await asyncio.sleep(2)

    print()
    print('='*50)
    print(f'New channels discovered: {len(new_channels)}')

    if new_channels:
        channels.extend(new_channels)
        json.dump(channels, open(CHANNELS_FILE,'w'), indent=2, default=str)
        print('Saved. Will be scanned at next 4:30am deep scan.')
        print()
        top = sorted(new_channels, key=lambda x: x.get('subscribers',0), reverse=True)
        print('Top new channels by subscribers:')
        for c in top[:10]:
            print(f'  @{c["username"]:40} {c.get("subscribers",0):>8,} subs  [{c["category"]}]')

    print('='*50)
    return len(new_channels)

def main():
    asyncio.run(run())

if __name__ == '__main__':
    main()
