"""
CINEOS Deep Scan — Session 2 (jyo talla)
Scans second half of channels simultaneously with session 1.
Run at same time as cineos_telegram_deep_scan.py
Crontab: 30 4 * * * (same time as session 1)
"""
import asyncio, json, re, hashlib, os, sys
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.errors import (FloodWaitError, ChannelPrivateError,
    UsernameNotOccupiedError, ChatAdminRequiredError)

API_ID   = 38636931
API_HASH = '852280f65386a00114ff7453eac7849b'
SESSION  = 'cineos_session2'
IST      = timezone(timedelta(hours=5, minutes=30))
MSG_LIMIT= 20
DELAY    = 5.0
MAX_FLOOD= 300

CHANNELS_FILE = 'reports/all_channels.json'
ALERTS_FILE   = 'reports/alerts/live_alerts.json'

UPI_RE = re.compile(
    r'\b([a-zA-Z0-9.\-_]{2,40}@(?:'
    r'okaxis|okhdfcbank|okicici|oksbi|ybl|ibl|axl|paytm|apl|'
    r'waaxis|waicici|wairtel|freecharge|jiomoney|'
    r'axisbank|hdfcbank|aubank|indus|rbl|kvb|federal|'
    r'abfspay|idbi|ptaxis|pthdfc|ptyes|ptsbi|sbiupi|icicipay))\b',
    re.IGNORECASE)
PHONE_RE = re.compile(r'(?<!\d)([6-9]\d{9})(?!\d)')
FAKE = {'+919999999999','+910000000000','+911234567890','+917777777777'}

def clean_phone(p):
    d = re.sub(r'[\s\-]','',p)
    if len(d)==10 and d[0] in '6789': return '+91'+d
    if len(d)==12 and d[:2]=='91': return '+'+d
    return None

async def run():
    ts = datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')
    print(f'[{ts}] CINEOS Deep Scan — Session 2 (jyo talla)')
    print('='*55)

    channels = json.load(open(CHANNELS_FILE))
    active = [c for c in channels if c.get('status') != 'deleted']

    # Session 2 scans the SECOND half
    mid = len(active)//2
    my_channels = active[mid:]
    print(f'Session 2 scanning: channels {mid+1}-{len(active)} ({len(my_channels)} channels)')

    alerts = json.load(open(ALERTS_FILE))
    existing_ids = {a.get('id') for a in alerts}

    scanned = 0
    errors = 0
    new_phones = set()
    new_upis = set()
    new_alerts = []

    async with TelegramClient(SESSION, API_ID, API_HASH) as client:
        me = await client.get_me()
        print(f'Connected as: {me.first_name}')

        for ch in my_channels:
            username = ch.get('username','')
            if not username: continue
            try:
                entity = await client.get_entity(f'@{username}')
                msgs = await client.get_messages(entity, limit=MSG_LIMIT)
                text_all = ' '.join([m.text or '' for m in msgs if m.text])

                # Extract phones
                phones = []
                for m in PHONE_RE.findall(text_all):
                    p = clean_phone(m)
                    if p and p not in FAKE:
                        phones.append(p)
                        new_phones.add(p)

                # Extract UPIs
                upis = []
                for u in UPI_RE.findall(text_all):
                    upis.append(u)
                    new_upis.add(u)

                if phones or upis:
                    alert_id = hashlib.sha256(f's2_{username}'.encode()).hexdigest()[:16]
                    if alert_id not in existing_ids:
                        subs = getattr(entity,'participants_count',0) or 0
                        alert = {
                            'id': alert_id,
                            'title': f'@{username} — scan_s2 · {subs:,} subscribers',
                            'category': ch.get('category','illegal_betting'),
                            'severity': 'critical' if phones else 'high',
                            'platform': 'Telegram',
                            'detected_at': datetime.now(IST).isoformat(),
                            'reach': subs,
                            'evidence_hash': alert_id,
                            'chain': {
                                'phones': list(set(phones)),
                                'upis': list(set(upis)),
                                'channels_found': [f'https://t.me/{username}'],
                            }
                        }
                        new_alerts.append(alert)
                        existing_ids.add(alert_id)
                        print(f'  NEW @{username}: {len(phones)} phones {len(upis)} UPIs')

                # Update channel record
                ch['last_scanned'] = datetime.now(IST).isoformat()
                ch['subscribers'] = getattr(entity,'participants_count',0) or 0
                if phones: ch['phones'] = list(set(phones))
                if upis: ch['upi_ids'] = list(set(upis))
                ch['status'] = 'active'
                scanned += 1
                await asyncio.sleep(DELAY)

            except FloodWaitError as e:
                if e.seconds > MAX_FLOOD:
                    print(f'  [FLOOD WAIT] {e.seconds}s — stopping session 2')
                    break
                await asyncio.sleep(e.seconds + 2)
            except (ChannelPrivateError, UsernameNotOccupiedError):
                ch['status'] = 'deleted'
                errors += 1
            except Exception as e:
                errors += 1
                await asyncio.sleep(2)

    # Save results
    if new_alerts:
        alerts.extend(new_alerts)
        json.dump(alerts, open(ALERTS_FILE,'w'), indent=2, default=str)

    json.dump(channels, open(CHANNELS_FILE,'w'), indent=2, default=str)

    print()
    print('='*55)
    print(f'Session 2 complete:')
    print(f'  Scanned: {scanned} channels')
    print(f'  New alerts: {len(new_alerts)}')
    print(f'  New phones: {len(new_phones)}')
    print(f'  New UPIs: {len(new_upis)}')

def main():
    asyncio.run(run())

if __name__ == '__main__':
    main()
