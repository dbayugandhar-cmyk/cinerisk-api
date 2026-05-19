"""
CINEOS Telegram Hourly Scanner
Rescans top 200 high-value channels every hour.
Finds NEW phones, UPIs, channel links posted since last scan.
This is the real source of authentic timestamped intelligence.

Crontab: 0 * * * * (every hour, replaces hourly web scanner)
"""
import asyncio, json, re, hashlib, time, sys
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChannelPrivateError

API_ID   = 38636931
API_HASH = '852280f65386a00114ff7453eac7849b'
SESSION  = 'cineos_session'
IST      = timezone(timedelta(hours=5, minutes=30))

CHANNELS_FILE = 'reports/all_channels.json'
ALERTS_FILE   = 'reports/alerts/live_alerts.json'

PHONE_RE = re.compile(r'(?<!\d)(?:\+91|91)?([6-9]\d{9})(?!\d)')
UPI_RE   = re.compile(
    r'[a-zA-Z0-9.\-_]{2,40}@(?:okaxis|okhdfcbank|oksbi|ybl|ibl|'
    r'paytm|apl|upi|axisbank|hdfcbank|ptaxis|sbiupi|icicipay)', re.I)
TG_RE    = re.compile(r't\.me/([a-zA-Z0-9_]{5,32})', re.I)

FAKE_PHONES = {'9999999999','8888888888','7777777777','1234567890','0000000000'}
CAT_KEYWORDS = {
    'illegal_betting': ['mahadev','reddy anna','laser','cricbet','betbhai','tiger','world777',
                        'radhe','diamond','sky exchange','fairplay','betting','satta','book id'],
    'upi_mule':        ['upi mule','mule account','bank account rent','earn commission bank'],
    'crypto_fraud':    ['crypto','bitcoin','usdt','binance','trading signal','pump'],
    'counterfeit_pharma': ['medicine','tablet','capsule','pharma','drug','generic'],
    'colour_prediction': ['colour prediction','91club','daman','bdg','wingo','tiranga'],
    'investment_fraud':  ['guaranteed return','sure profit','trading course','forex signal'],
}

def now_ist():
    return datetime.now(IST)

def detect_cat(text):
    t = text.lower()
    for cat, kws in CAT_KEYWORDS.items():
        if any(k in t for k in kws):
            return cat
    return 'unknown'

def clean_phone(raw):
    d = re.sub(r'\D','',raw)
    if len(d)==10 and d[0] in '6789' and d not in FAKE_PHONES:
        return '+91'+d
    if len(d)==12 and d[:2]=='91' and d[2] in '6789':
        return '+'+d
    return None

def make_alert(channel, new_phones, new_upis, text_sample, cat):
    ts = now_ist().isoformat()
    title = f"@{channel['username']} — {cat.replace('_',' ')} · {channel.get('subscribers',0):,} subscribers"
    h = hashlib.sha256((title+ts).encode()).hexdigest()[:8]
    ch_link = f"t.me/{channel['username']}"
    reach = channel.get('subscribers', 0)
    sev = 'critical' if new_phones or new_upis else 'high'
    return {
        'id': h,
        'title': title,
        'category': cat,
        'severity': sev,
        'platform': 'Telegram',
        'detail': text_sample[:200],
        'source': f'telegram_hourly_scan',
        'detected_at': ts,
        'reach': reach,
        'evidence_hash': h,
        'chain': {
            'phones': new_phones,
            'upis': new_upis,
            'channels_found': [ch_link],
            'reach': reach,
            'operator_name': channel.get('operator_name',''),
            'legal_basis': 'IT Act §65B(2)',
        }
    }

async def scan_channel(client, ch, since_hours=2):
    """Scan a channel for new content posted in last N hours."""
    username = ch.get('username','')
    if not username:
        return [], [], []

    new_phones, new_upis, new_links = [], [], []
    existing_phones = set(ch.get('phones',[]))
    existing_upis   = set(ch.get('upi_ids',[]))
    cutoff = now_ist() - timedelta(hours=since_hours)

    try:
        entity = await client.get_entity(f'@{username}')
        msgs = await client.get_messages(entity, limit=50)

        for msg in msgs:
            if not msg.date:
                continue
            msg_time = msg.date.astimezone(IST)
            if msg_time < cutoff:
                break  # Messages are in reverse chronological order

            text = msg.text or msg.caption or ''
            if not text:
                continue

            # Extract phones
            for raw in PHONE_RE.findall(text):
                p = clean_phone(raw)
                if p and p not in existing_phones and p not in new_phones:
                    new_phones.append(p)

            # Extract UPIs
            for upi in UPI_RE.findall(text):
                u = upi.lower().strip()
                if u not in existing_upis and u not in new_upis:
                    new_upis.append(u)

            # Extract new channel links
            for link in TG_RE.findall(text):
                if link.lower() != username.lower():
                    new_links.append(link)

    except (ChannelPrivateError, Exception):
        pass

    return new_phones, new_upis, new_links


async def run_hourly_scan():
    ts = now_ist().strftime('%Y-%m-%d %H:%M IST')
    print(f'[{ts}] CINEOS TELEGRAM HOURLY SCANNER')
    print('='*50)

    channels = json.load(open(CHANNELS_FILE))
    alerts   = json.load(open(ALERTS_FILE))

    # Priority: high-subscriber channels with phones already found
    # These are confirmed fraud operators — rescan them
    priority = sorted(
        [c for c in channels if c.get('phones') and c.get('subscribers',0) > 10000],
        key=lambda x: x.get('subscribers',0), reverse=True
    )[:50]

    # Also add high-subscriber channels without phones (may have new posts)
    discovery = sorted(
        [c for c in channels if not c.get('phones') and c.get('subscribers',0) > 50000
         and c.get('category') in ['illegal_betting','upi_mule','crypto_fraud']],
        key=lambda x: x.get('subscribers',0), reverse=True
    )[:30]

    targets = priority + discovery
    print(f'Scanning {len(targets)} channels (top {len(priority)} priority + {len(discovery)} discovery)')
    print()

    new_alerts = []
    total_new_phones = 0
    total_new_upis = 0
    channels_updated = 0
    flood_hits = 0

    async with TelegramClient(SESSION, API_ID, API_HASH) as client:
        for i, ch in enumerate(targets):
            username = ch.get('username','')
            subs = ch.get('subscribers',0)

            try:
                new_phones, new_upis, new_links = await scan_channel(client, ch, since_hours=2)

                if new_phones or new_upis:
                    print(f'  [{i+1:2}] @{username:35} NEW: phones={new_phones} upis={new_upis}')

                    # Update channel record
                    for c2 in channels:
                        if c2.get('username') == username:
                            c2['phones'] = list(set(c2.get('phones',[]) + new_phones))
                            c2['upi_ids'] = list(set(c2.get('upi_ids',[]) + new_upis))
                            c2['last_scanned'] = now_ist().isoformat()
                            break

                    # Find existing alert for this channel and update it
                    updated = False
                    for a in alerts:
                        ch_links = a.get('chain',{}).get('channels_found',[])
                        if any(username.lower() in str(l).lower() for l in ch_links):
                            if new_phones:
                                existing = a['chain'].get('phones',[])
                                a['chain']['phones'] = list(set(existing + new_phones))
                            if new_upis:
                                existing = a['chain'].get('upis',[])
                                a['chain']['upis'] = list(set(existing + new_upis))
                            a['detected_at'] = now_ist().isoformat()
                            updated = True
                            break

                    # Create new alert if none exists
                    if not updated:
                        cat = ch.get('category', detect_cat(username))
                        sample_text = f"New operator contact: {' '.join(new_phones + new_upis)}"
                        alert = make_alert(ch, new_phones, new_upis, sample_text, cat)
                        # Check not duplicate
                        existing_ids = {a['id'] for a in alerts}
                        if alert['id'] not in existing_ids:
                            alerts.append(alert)
                            new_alerts.append(alert)

                    total_new_phones += len(new_phones)
                    total_new_upis += len(new_upis)
                    channels_updated += 1

                await asyncio.sleep(1.2)

            except FloodWaitError as e:
                flood_hits += 1
                wait = e.seconds
                print(f'  [FLOOD] {wait}s wait')
                if wait > 120:
                    print(f'  [FLOOD] Long wait — stopping early')
                    break
                await asyncio.sleep(wait + 2)
            except Exception as e:
                continue

    print()
    print('='*50)
    print(f'HOURLY SCAN COMPLETE — {now_ist().strftime("%H:%M IST")}')
    print(f'  Channels scanned:   {len(targets)}')
    print(f'  Channels updated:   {channels_updated}')
    print(f'  New phones found:   {total_new_phones}')
    print(f'  New UPIs found:     {total_new_upis}')
    print(f'  New alerts created: {len(new_alerts)}')
    print(f'  Flood hits:         {flood_hits}')

    if channels_updated > 0 or new_alerts:
        json.dump(channels, open(CHANNELS_FILE,'w'), indent=2, default=str)
        json.dump(alerts,   open(ALERTS_FILE,'w'),   indent=2, default=str)
        print(f'  Saved to disk ✓')

        if new_alerts:
            print()
            print('NEW ALERTS:')
            for a in new_alerts:
                print(f'  [{a["severity"].upper()}] {a["title"][:60]}')
                print(f'  phones:{a["chain"]["phones"]} upis:{a["chain"]["upis"]}')

    print('='*50)
    return len(new_alerts), total_new_phones, total_new_upis


def main():
    asyncio.run(run_hourly_scan())

if __name__ == '__main__':
    main()
