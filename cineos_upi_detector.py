"""
CINEOS UPI Fraud Detection
Detects UPI IDs shared in fraud Telegram channels.
Reports to NPCI and banks for blocking.
Legal: Monitors only public channel data.
"""
import asyncio, re, json, os
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest

API_ID = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

UPI_PATTERN = r'[a-zA-Z0-9._-]+@[a-zA-Z]{2,}'
PHONE_PATTERN = r'[6-9]\d{9}'
BANK_PATTERN = r'\b([A-Z]{4}0[A-Z0-9]{6})\b'

FRAUD_CHANNELS_TO_SCAN = [
    'Crypto_IPL_Bettingolgy_Tatah',
    'Crypto_Prediction_Baazigar',
    'MATKA_KALYAN_MILAN_SATTA',
    'CricketBetting',
    'IPLBetting',
    'ReddyAnnaBookOfficialReddy',
]

async def scan_channel_for_upi(client, channel: str) -> list:
    """Scan a Telegram channel for UPI IDs and payment details."""
    findings = []
    try:
        entity = await client.get_entity(channel)
        messages = await client.get_messages(entity, limit=100)

        for msg in messages:
            if not msg.text:
                continue
            text = msg.text

            # Find UPI IDs
            upi_ids = re.findall(UPI_PATTERN, text)
            # Filter valid UPI handles
            valid_upi = [u for u in upi_ids if any(
                u.endswith(f'@{h}') for h in [
                    'okaxis','okicici','okhdfcbank','oksbi',
                    'paytm','gpay','phonepe','ybl','apl',
                    'upi','ibl','axl','rbl','kotak',
                ]
            )]

            # Find phone numbers
            phones = re.findall(PHONE_PATTERN, text)

            if valid_upi or phones:
                findings.append({
                    'channel': channel,
                    'message_id': msg.id,
                    'date': msg.date.isoformat(),
                    'upi_ids': valid_upi,
                    'phones': phones[:3],
                    'text_snippet': text[:200],
                })
                for upi in valid_upi:
                    print(f"  UPI FOUND: {upi} in @{channel}")

    except Exception as e:
        print(f"  @{channel}: {e}")

    return findings

async def full_upi_scan():
    """Scan all fraud channels for UPI IDs."""
    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()
    print(f"[UPI] Scanning {len(FRAUD_CHANNELS_TO_SCAN)} channels...")

    all_findings = []
    for channel in FRAUD_CHANNELS_TO_SCAN:
        print(f"\n  Scanning @{channel}...")
        findings = await scan_channel_for_upi(client, channel)
        all_findings.extend(findings)

    await client.disconnect()

    # Aggregate unique UPI IDs
    all_upi = {}
    for f in all_findings:
        for upi in f['upi_ids']:
            if upi not in all_upi:
                all_upi[upi] = {
                    'upi_id': upi,
                    'found_in_channels': [],
                    'first_seen': f['date'],
                    'occurrences': 0,
                }
            all_upi[upi]['found_in_channels'].append(f['channel'])
            all_upi[upi]['occurrences'] += 1

    upi_list = sorted(all_upi.values(),
                     key=lambda x: -x['occurrences'])

    print(f"\n{'='*60}")
    print(f"  CINEOS UPI FRAUD DETECTION RESULTS")
    print(f"{'='*60}")
    print(f"  Channels scanned: {len(FRAUD_CHANNELS_TO_SCAN)}")
    print(f"  Unique UPI IDs:   {len(upi_list)}")
    print(f"  Total findings:   {len(all_findings)}")

    if upi_list:
        print(f"\n  FLAGGED UPI IDs:")
        for u in upi_list[:10]:
            print(f"    {u['upi_id']:40} {u['occurrences']}x in {u['found_in_channels'][:2]}")

    # Save
    os.makedirs('reports', exist_ok=True)
    path = f"reports/upi_fraud_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump({
        'upi_ids': upi_list,
        'raw_findings': all_findings,
        'scanned_at': datetime.now().isoformat(),
    }, open(path,'w'), indent=2, default=str)
    print(f"\n  Saved: {path}")
    print(f"{'='*60}")

    return upi_list

if __name__ == '__main__':
    asyncio.run(full_upi_scan())
