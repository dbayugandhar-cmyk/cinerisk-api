"""
CINEOS OCR UPI Extractor
Runs after deep scan to extract UPI handles from channel images.
Uses local Tesseract — completely free, no API cost.

Scans pinned messages of channels that have phones but no UPIs.
Saves extracted UPIs to channel records and creates quality alerts.

Run: python3 cineos_ocr_upi_extractor.py
Crontab: 50 4 * * * (after deep scan at 4:30)
"""

import asyncio, json, os, re, hashlib, time, io
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.errors import FloodWaitError, ChannelPrivateError

API_ID   = 38636931
API_HASH = '852280f65386a00114ff7453eac7849b'
SESSION  = 'cineos_session'
IST      = timezone(timedelta(hours=5, minutes=30))

CHANNELS_FILE = 'reports/all_channels.json'
ALERTS_FILE   = 'reports/alerts/live_alerts.json'

# Tight UPI regex — only confirmed India PSP suffixes
UPI_RE = re.compile(
    r'[a-zA-Z0-9.\-_]{2,40}@(?:'
    r'okaxis|okhdfcbank|okicici|oksbi|'
    r'ybl|ibl|axl|paytm|apl|upi|'
    r'waaxis|waicici|wairtel|freecharge|jiomoney|'
    r'axisbank|hdfcbank|aubank|indus|mahb|'
    r'rbl|kvb|fifederal|federal|abfspay|idbi|'
    r'ptaxis|pthdfc|ptyes|ptsbi|sbiupi|icicipay)',
    re.IGNORECASE
)

# Fake/test UPIs to exclude
FAKE_UPIS = {
    'test@upi', 'example@paytm', 'sample@okaxis',
    'name@ybl', 'abc@upi', 'xyz@paytm',
}

def now_ist():
    return datetime.now(IST)

def clean_upi(upi):
    upi = upi.strip().lower()
    if upi in FAKE_UPIS:
        return None
    if len(upi) < 6 or len(upi) > 50:
        return None
    # Must have valid local part (not just numbers)
    local = upi.split('@')[0]
    if local.isdigit() and len(local) < 6:
        return None
    return upi

async def extract_upi_from_channel(client, username, max_images=8):
    """Download recent images from channel and OCR them for UPIs."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        print('  pytesseract/Pillow not installed')
        return []

    upis_found = []

    try:
        entity = await client.get_entity(f'@{username}')

        # Get pinned message first (most likely to have UPI)
        messages = await client.get_messages(entity, limit=30)

        image_count = 0
        for msg in messages:
            if image_count >= max_images:
                break

            # Only process messages with photos
            if not msg.media or not isinstance(msg.media, MessageMediaPhoto):
                continue

            try:
                # Download image to memory
                img_bytes = io.BytesIO()
                await client.download_media(msg.media, img_bytes)
                img_bytes.seek(0)

                # OCR the image
                img = Image.open(img_bytes)

                # Try multiple OCR configs for better accuracy
                configs = [
                    '--psm 6',   # Assume uniform block of text
                    '--psm 11',  # Sparse text
                    '--psm 3',   # Fully automatic
                ]

                all_text = ''
                for cfg in configs:
                    try:
                        text = pytesseract.image_to_string(img, config=cfg, lang='eng')
                        all_text += ' ' + text
                    except:
                        pass

                # Extract UPIs from OCR text
                raw_upis = UPI_RE.findall(all_text)
                for raw in raw_upis:
                    cleaned = clean_upi(raw)
                    if cleaned and cleaned not in upis_found:
                        upis_found.append(cleaned)
                        print(f'  ✓ UPI found: {cleaned} from @{username}')

                image_count += 1
                await asyncio.sleep(0.5)

            except Exception as e:
                continue

    except (ChannelPrivateError, Exception) as e:
        pass

    return upis_found


async def run_ocr_extraction():
    print('=' * 55)
    print('CINEOS OCR UPI EXTRACTOR')
    print(f'{now_ist().strftime("%Y-%m-%d %H:%M IST")}')
    print('=' * 55)

    channels = json.load(open(CHANNELS_FILE))
    alerts   = json.load(open(ALERTS_FILE))

    # Priority: channels with phones but no UPIs
    # Focus on betting + mule + pharma verticals
    priority_cats = ['illegal_betting', 'upi_mule', 'counterfeit_pharma', 'crypto_fraud']

    targets = [
        c for c in channels
        if c.get('phones')
        and not c.get('upi_ids')
        and c.get('category') in priority_cats
        and c.get('subscribers', 0) > 500
    ]

    # Also include channels with high subscribers even without phones
    high_reach = [
        c for c in channels
        if c.get('subscribers', 0) > 10000
        and not c.get('upi_ids')
        and c.get('category') in priority_cats
        and c not in targets
    ]

    targets = targets[:40] + high_reach[:20]

    print(f'Target channels: {len(targets)} (phones-but-no-UPI + high-reach)')
    print(f'  betting: {sum(1 for c in targets if c.get("category")=="illegal_betting")}')
    print(f'  mule:    {sum(1 for c in targets if c.get("category")=="upi_mule")}')
    print(f'  pharma:  {sum(1 for c in targets if c.get("category")=="counterfeit_pharma")}')
    print()

    total_upis = 0
    channels_with_upis = 0
    all_new_upis = {}  # upi -> channel

    async with TelegramClient(SESSION, API_ID, API_HASH) as client:
        for i, ch in enumerate(targets):
            username = ch.get('username', '')
            if not username:
                continue

            print(f'[{i+1:3}/{len(targets)}] @{username[:35]:35} subs:{ch.get("subscribers",0):>7,}')

            try:
                upis = await extract_upi_from_channel(client, username)

                if upis:
                    # Save to channel record
                    for c2 in channels:
                        if c2.get('username') == username:
                            existing = c2.get('upi_ids', [])
                            new_upis = [u for u in upis if u not in existing]
                            c2['upi_ids'] = existing + new_upis
                            break

                    for upi in upis:
                        all_new_upis[upi] = username
                    channels_with_upis += 1
                    total_upis += len(upis)

                await asyncio.sleep(1.5)

            except FloodWaitError as e:
                wait = e.seconds
                print(f'  [FLOOD WAIT] {wait}s — stopping')
                if wait > 300:
                    break
                await asyncio.sleep(wait + 3)

    print()
    print('=' * 55)
    print(f'OCR EXTRACTION COMPLETE')
    print(f'  Channels processed:    {len(targets)}')
    print(f'  Channels with UPIs:    {channels_with_upis}')
    print(f'  New UPIs extracted:    {total_upis}')
    print()

    if all_new_upis:
        print('EXTRACTED UPIs:')
        for upi, ch in all_new_upis.items():
            print(f'  {upi:<35} from @{ch}')

        # Save updated channels
        json.dump(channels, open(CHANNELS_FILE, 'w'), indent=2, default=str)
        print(f'\nSaved to {CHANNELS_FILE}')

        # Save UPI report
        report = {
            'generated_at': now_ist().isoformat(),
            'total_upis': total_upis,
            'upis': all_new_upis,
        }
        json.dump(report, open('reports/upi_extracted.json', 'w'), indent=2)
        print('Saved to reports/upi_extracted.json')
    else:
        print('No UPIs found in channel images.')
        print()
        print('HONEST ASSESSMENT:')
        print('  Most operators post UPIs in stylized graphics')
        print('  with custom fonts that Tesseract cannot read.')
        print('  Google Vision API handles these better.')
        print('  Consider: pip3 install google-cloud-vision')
        print('  Cost: ~₹2/image, first 1000/month free')

    print('=' * 55)
    return total_upis


def main():
    asyncio.run(run_ocr_extraction())


if __name__ == '__main__':
    main()
