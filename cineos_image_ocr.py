"""
CINEOS Image OCR Engine
Extracts phone numbers from images posted in fraud channels.
Pharma operators post price lists/contact info as JPG to evade text extraction.

Usage: python3 cineos_image_ocr.py
       from cineos_image_ocr import extract_phones_from_image_url
"""
import re, os, io, hashlib
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5,minutes=30))

def extract_phones_from_image_url(url):
    """Download image from URL and extract phone numbers via OCR."""
    try:
        import urllib.request
        from PIL import Image
        import pytesseract

        req = urllib.request.Request(url, headers={'User-Agent':'CINEOS/1.0'})
        data = urllib.request.urlopen(req, timeout=10).read()
        img  = Image.open(io.BytesIO(data))

        # Preprocess for better OCR
        img = img.convert('L')  # Grayscale
        # Increase size if small
        w, h = img.size
        if w < 400:
            img = img.resize((w*2, h*2), Image.LANCZOS)

        text = pytesseract.image_to_string(img, config='--psm 6')
        return extract_phones_from_text(text), text

    except Exception as e:
        return [], ''

def extract_phones_from_text(text):
    """Extract all Indian phone numbers from text."""
    phones = set()
    patterns = [
        r'(?<!\d)([6-9]\d{9})(?!\d)',
        r'wa\.me/(?:91)?([6-9]\d{9})',
        r'(?:call|contact|whatsapp|order)[^\d]{0,20}([6-9]\d{9})',
        r'\+91[-\s]?([6-9]\d{9})',
        r'0([6-9]\d{9})',
    ]
    for pat in patterns:
        for m in re.findall(pat, text, re.IGNORECASE):
            d = re.sub(r'\D', '', m)
            if len(d) == 10 and d[0] in '6789':
                phones.add('+91' + d)
    return list(phones)

async def scan_channel_images(channel_username, limit=20):
    """
    Scan recent images from a Telegram channel for hidden phone numbers.
    Most valuable for pharma channels that hide phones in images.
    """
    try:
        from telethon import TelegramClient
        from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
    except ImportError:
        print("Telethon not available")
        return []

    API_ID   = 38636931
    API_HASH = '852280f65386a00114ff7453eac7849b'

    found_phones = []
    async with TelegramClient('cineos_session', API_ID, API_HASH) as client:
        try:
            entity = await client.get_entity(channel_username)
            async for msg in client.iter_messages(entity, limit=limit):
                if not msg.media:
                    continue
                if not isinstance(msg.media, (MessageMediaPhoto, MessageMediaDocument)):
                    continue
                try:
                    # Download image to memory
                    data = await client.download_media(msg.media, bytes)
                    if not data:
                        continue

                    from PIL import Image
                    import pytesseract

                    img  = Image.open(io.BytesIO(data)).convert('L')
                    w, h = img.size
                    if w < 400:
                        img = img.resize((w*2, h*2), Image.LANCZOS)

                    text   = pytesseract.image_to_string(img, config='--psm 6')
                    phones = extract_phones_from_text(text)

                    if phones:
                        print(f'  Image OCR found: {phones} in @{channel_username}')
                        found_phones.extend(phones)

                        # Save evidence
                        ev = {
                            'channel':    channel_username,
                            'message_id': msg.id,
                            'phones':     phones,
                            'ocr_text':   text[:200],
                            'detected_at':datetime.now(IST).isoformat(),
                            'method':     'IMAGE_OCR',
                            'evidence':   hashlib.sha256(text.encode()).hexdigest()[:16],
                        }
                        # Append to OCR findings
                        import json
                        ocr_file = 'reports/ocr_findings.json'
                        findings = []
                        try: findings = json.load(open(ocr_file))
                        except: pass
                        findings.append(ev)
                        json.dump(findings, open(ocr_file,'w'), indent=2)

                except Exception as e:
                    pass

        except Exception as e:
            print(f'Error scanning @{channel_username}: {e}')

    return list(set(found_phones))

def scan_pharma_channels_for_images():
    """
    Scan all pharma channels for image-hidden phones.
    This is the key gap — pharma operators hide phones in images.
    """
    import json, asyncio

    channels = json.load(open('reports/all_channels.json'))
    pharma_no_phones = [
        c for c in channels
        if c.get('category') == 'counterfeit_pharma'
        and not c.get('phones')
        and c.get('username')
        and c.get('subscribers', 0) > 5000
    ]

    print(f'Pharma channels without phones: {len(pharma_no_phones)}')
    print(f'Scanning top 20 for image-hidden phones...')

    all_found = {}
    for ch in pharma_no_phones[:20]:
        username = ch.get('username','')
        print(f'  Scanning @{username[:40]}...')
        try:
            phones = asyncio.run(scan_channel_images(username, limit=15))
            if phones:
                ch['phones'] = phones
                ch['phone_method'] = 'IMAGE_OCR'
                all_found[username] = phones
                print(f'    Found: {phones}')
        except Exception as e:
            print(f'    Error: {e}')

    if all_found:
        json.dump(channels, open('reports/all_channels.json','w'), indent=2)
        print(f'\nUpdated {len(all_found)} pharma channels with OCR phones')

    return all_found

if __name__ == '__main__':
    import sys
    # Quick OCR test
    print('CINEOS Image OCR Engine')
    print('Testing OCR on sample text...')
    test = 'Contact us: 9876543210 or wa.me/919123456789'
    phones = extract_phones_from_text(test)
    print(f'Text extraction test: {phones}')
    print()

    if '--scan' in sys.argv:
        scan_pharma_channels_for_images()
    else:
        print('Run with --scan to scan pharma channels for image-hidden phones')
        print('Usage: python3 cineos_image_ocr.py --scan')
