"""
CINEOS Payment Trail Attribution
Links crypto wallets, UPI IDs and bank accounts
to fraud operators. Follows money trail.
"""
import asyncio, httpx, re, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

# Crypto patterns
CRYPTO_PATTERNS = {
    'bitcoin': r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b',
    'ethereum': r'\b0x[a-fA-F0-9]{40}\b',
    'tron': r'\bT[a-zA-Z0-9]{33}\b',
    'usdt_trc20': r'\bT[a-zA-Z0-9]{33}\b',
}

async def extract_crypto_from_channels() -> dict:
    """Extract crypto addresses from fraud Telegram channels."""
    from telethon import TelegramClient
    API_ID = 38636931
    API_HASH = "852280f65386a00114ff7453eac7849b"

    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()

    channels = [
        'Crypto_IPL_Bettingolgy_Tatah',
        'News_Crypto5',
        'Free_Crypto_Pumps_Signals_Vip',
        'Trading_Trader_Free',
        'Trade_Crypto_Free',
    ]

    all_wallets = {}
    for channel in channels:
        try:
            entity = await client.get_entity(channel)
            messages = await client.get_messages(entity, limit=200)

            for msg in messages:
                if not msg.text:
                    continue
                for crypto, pattern in CRYPTO_PATTERNS.items():
                    wallets = re.findall(pattern, msg.text)
                    for wallet in wallets:
                        if wallet not in all_wallets:
                            all_wallets[wallet] = {
                                'address': wallet,
                                'type': crypto,
                                'channels': [],
                                'occurrences': 0,
                            }
                        if channel not in all_wallets[wallet]['channels']:
                            all_wallets[wallet]['channels'].append(channel)
                        all_wallets[wallet]['occurrences'] += 1

        except Exception as e:
            print(f"  @{channel}: {e}")

    await client.disconnect()
    return all_wallets

async def trace_payment_trail():
    print("[PAYMENT TRAIL] Starting attribution scan...")

    # Extract crypto wallets from Telegram
    print("\n[1] Extracting crypto addresses from fraud channels...")
    wallets = await extract_crypto_from_channels()
    print(f"  Unique wallets found: {len(wallets)}")

    if wallets:
        print("\n  TOP WALLETS:")
        for addr, data in sorted(
            wallets.items(),
            key=lambda x: -x[1]['occurrences']
        )[:5]:
            print(f"  {data['type'].upper()}: {addr[:20]}...")
            print(f"    Channels: {data['channels']}")
            print(f"    Occurrences: {data['occurrences']}")

    # Mule pattern — same wallet in multiple channels
    mule_wallets = [
        (addr, data) for addr, data in wallets.items()
        if len(data['channels']) >= 2
    ]

    print(f"\n  Multi-channel wallets (mule pattern): {len(mule_wallets)}")

    result = {
        'wallets': wallets,
        'mule_wallets': [
            {'address': addr, **data}
            for addr, data in mule_wallets
        ],
        'total_unique': len(wallets),
        'mule_count': len(mule_wallets),
        'scanned_at': datetime.now().isoformat(),
    }

    os.makedirs('reports', exist_ok=True)
    path = f"reports/payment_trail_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(result, open(path,'w'), indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"  CINEOS PAYMENT TRAIL RESULTS")
    print(f"{'='*60}")
    print(f"  Crypto wallets:     {len(wallets)}")
    print(f"  Mule patterns:      {len(mule_wallets)}")
    print(f"  Saved: {path}")

    return result

if __name__ == '__main__':
    asyncio.run(trace_payment_trail())
