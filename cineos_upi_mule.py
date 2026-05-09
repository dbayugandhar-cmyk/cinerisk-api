"""
CINEOS UPI Mule Pattern Detection
Detects UPI IDs used in fraud channels.
Finds patterns: same UPI across multiple channels,
QR codes, payment links, phone numbers.
"""
import asyncio, re, json, os
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.messages import SearchRequest
from telethon.tl.types import InputMessagesFilterEmpty

API_ID = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

# Top fraud channels by subscriber count
FRAUD_CHANNELS = [
    'Anuragt_bookqc_Malikc',
    'News_Crypto5',
    'Mahadevsd_Bookuoo',
    'CRYPTO_reddy_annag',
    'Crypto_IPL_Bettingolgy_Tatah',
    'Crypto_Prediction_Baazigar',
    'MATKA_KALYAN_MILAN_SATTA',
    'Free_Crypto_Pumps_Signals_Vip',
    'rajveer_betbook247_mahakal',
    'Trading_Trader_Free',
]

UPI_HANDLES = [
    'okaxis','okicici','okhdfcbank','oksbi','paytm',
    'gpay','phonepe','ybl','apl','upi','ibl','axl',
    'rbl','kotak','fbl','icici','hdfc','sbi','axis',
    'indus','pnb','bob','boi','canara','idbi',
]

async def extract_payment_data(client, channel: str) -> dict:
    findings = {
        'channel': channel,
        'upi_ids': set(),
        'phones': set(),
        'qr_mentions': 0,
        'payment_links': set(),
        'messages_scanned': 0,
    }

    try:
        entity = await client.get_entity(channel)
        messages = await client.get_messages(entity, limit=200)
        findings['messages_scanned'] = len(messages)

        for msg in messages:
            if not msg.text:
                continue
            text = msg.text

            # UPI IDs
            for handle in UPI_HANDLES:
                pattern = rf'[\w.+-]+@{handle}'
                upi_matches = re.findall(pattern, text, re.I)
                for m in upi_matches:
                    findings['upi_ids'].add(m.lower())

            # Generic UPI pattern
            generic = re.findall(
                r'[a-zA-Z0-9._-]{3,}@[a-zA-Z]{2,20}', text)
            for g in generic:
                if any(h in g.lower() for h in UPI_HANDLES):
                    findings['upi_ids'].add(g.lower())

            # Phone numbers
            phones = re.findall(r'[6-9]\d{9}', text)
            findings['phones'].update(phones)

            # QR code mentions
            if any(x in text.lower() for x in
                   ['qr code', 'scan qr', 'qr scan', 'pay qr']):
                findings['qr_mentions'] += 1

            # Payment links
            pay_links = re.findall(
                r'(?:upipay|paytm|phonepe|gpay)\.(?:me|in)/[^\s]+',
                text, re.I)
            findings['payment_links'].update(pay_links)

        if findings['upi_ids'] or findings['phones']:
            print(f"  @{channel}: {len(findings['upi_ids'])} UPI, "
                  f"{len(findings['phones'])} phones, "
                  f"{findings['qr_mentions']} QR mentions")

    except Exception as e:
        print(f"  @{channel}: {e}")

    # Convert sets to lists
    findings['upi_ids'] = list(findings['upi_ids'])
    findings['phones'] = list(findings['phones'])
    findings['payment_links'] = list(findings['payment_links'])
    return findings

async def detect_mule_patterns(all_findings: list) -> list:
    """
    Detect UPI mule patterns:
    - Same UPI ID appearing in multiple fraud channels
    - Phone numbers linked to multiple channels
    - High-volume payment collection patterns
    """
    upi_channels = {}
    phone_channels = {}

    for f in all_findings:
        channel = f['channel']
        for upi in f['upi_ids']:
            if upi not in upi_channels:
                upi_channels[upi] = []
            upi_channels[upi].append(channel)

        for phone in f['phones']:
            if phone not in phone_channels:
                phone_channels[phone] = []
            phone_channels[phone].append(channel)

    # Flag mules — appear in 2+ channels
    mules = []
    for upi, channels in upi_channels.items():
        if len(channels) >= 2:
            mules.append({
                'type': 'UPI_MULE',
                'identifier': upi,
                'found_in_channels': channels,
                'risk': 'CRITICAL' if len(channels) >= 3 else 'HIGH',
            })

    for phone, channels in phone_channels.items():
        if len(channels) >= 2:
            mules.append({
                'type': 'PHONE_MULE',
                'identifier': phone,
                'found_in_channels': channels,
                'risk': 'HIGH',
            })

    return mules

async def full_upi_scan():
    print("[UPI MULE] Starting pattern detection...")
    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()

    all_findings = []
    for channel in FRAUD_CHANNELS:
        print(f"\n  Scanning @{channel}...")
        f = await extract_payment_data(client, channel)
        all_findings.append(f)

    await client.disconnect()

    # Detect mule patterns
    mules = await detect_mule_patterns(all_findings)

    # Aggregate stats
    all_upi = set()
    all_phones = set()
    for f in all_findings:
        all_upi.update(f['upi_ids'])
        all_phones.update(f['phones'])

    print(f"\n{'='*65}")
    print(f"  CINEOS UPI MULE DETECTION RESULTS")
    print(f"{'='*65}")
    print(f"  Channels scanned:  {len(FRAUD_CHANNELS)}")
    print(f"  Messages scanned:  {sum(f['messages_scanned'] for f in all_findings):,}")
    print(f"  Unique UPI IDs:    {len(all_upi)}")
    print(f"  Unique phones:     {len(all_phones)}")
    print(f"  Mule patterns:     {len(mules)}")

    if all_upi:
        print(f"\n  UPI IDs DETECTED:")
        for upi in list(all_upi)[:10]:
            print(f"    {upi}")

    if mules:
        print(f"\n  MULE PATTERNS ({len(mules)}):")
        for m in mules:
            print(f"    {m['risk']}: {m['identifier']} in {m['found_in_channels']}")

    os.makedirs('reports', exist_ok=True)
    path = f"reports/upi_mule_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump({
        'findings': all_findings,
        'mules': mules,
        'summary': {
            'channels_scanned': len(FRAUD_CHANNELS),
            'unique_upi': list(all_upi),
            'unique_phones': list(all_phones),
            'mule_patterns': mules,
        }
    }, open(path,'w'), indent=2, default=str)
    print(f"\n  Saved: {path}")
    return all_findings, mules

if __name__ == '__main__':
    asyncio.run(full_upi_scan())
