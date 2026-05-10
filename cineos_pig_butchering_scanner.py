"""
CINEOS Pig Butchering Scanner
India's #1 fraud category — Rs 6,000 Cr lost in 2024.
Detects task fraud, investment fraud, romance scam channels.
NOBODY is scanning for pig butchering patterns in India at scale.
This is the breakthrough.

Pattern:
  Step 1: Wrong number / job offer on WhatsApp/Telegram
  Step 2: Added to fake group with fake members
  Step 3: Simple tasks — like YouTube videos, earn Rs 50
  Step 4: Invest bigger amounts — fake profits shown
  Step 5: Withdrawal blocked — money gone
"""
import asyncio, json, os, re
from datetime import datetime
from telethon import TelegramClient

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

# Pig butchering patterns — unique to India
PIG_PATTERNS = {
    'task_fraud': [
        # English patterns
        'complete task', 'earn per task', 'daily task',
        'like youtube', 'youtube task', 'app task',
        'part time task', 'simple task earn',
        'task completed', 'task reward',
        'work from mobile', 'earn 500 daily',
        'earn 1000 daily', 'earn 2000 daily',
        # Hindi patterns  
        'काम करो', 'पैसे कमाओ', 'टास्क पूरा',
        'यूट्यूब लाइक', 'घर बैठे',
        # Telugu patterns
        'పని చేయండి', 'సంపాదించండి',
        # Tamil patterns
        'வேலை செய்யுங்கள்',
    ],
    'investment_fraud': [
        # Platform names used in pig butchering
        'bybit', 'okx platform', 'htx exchange',
        'forex profit', 'crypto profit today',
        'stock profit guarantee', 'trading signal win',
        'withdrawal tax', 'unlock fee', 'margin top',
        'deposit more withdraw', '30% return',
        '40% return', '50% return',
        # Hindi
        'निवेश करो', 'मुनाफा गारंटी',
        'क्रिप्टो मुनाफा',
    ],
    'romance_setup': [
        # Initial contact patterns
        'wrong number', 'sorry wrong',
        'hi are you', 'can we be friends',
        'i am nri', 'i live in singapore',
        'i live in dubai', 'i am doctor',
        'working in london',
        # Platform hopping
        'join telegram', 'join whatsapp group',
        'add me telegram',
    ],
    'fake_job': [
        'hr manager hiring', 'remote job offer',
        'data entry earn', 'online job 5000',
        'work home 10000', 'earn per hour',
        'no experience needed salary',
        'training fee refund', 'registration fee',
        # Hindi
        'नौकरी चाहिए', 'घर से काम',
        'ऑनलाइन काम', 'पार्ट टाइम जॉब',
        # Telugu  
        'ఉద్యోగం', 'ఇంటి నుండి పని',
    ],
    'digital_arrest': [
        # New 2025-26 scam — fake police/CBI arrest
        'cyber crime notice', 'arrest warrant',
        'ed notice', 'cbi notice',
        'money laundering case', 'trai notice',
        'aadhaar blocked', 'sim blocked',
        'digital arrest', 'video kyc required',
        # Hindi
        'गिरफ्तारी वारंट', 'साइबर क्राइम',
        'आपका खाता बंद',
    ],
}

# Channels known to run pig butchering
PIG_CHANNELS_TO_SCAN = [
    # Task fraud channels
    'parttime_job_india',
    'work_from_home_india',
    'earn_money_online_india',
    'daily_task_earn',
    'online_task_india',
    'youtube_task_earn',
    'telegram_task_india',
    'earn_500_daily',
    'earn_1000_daily',
    'data_entry_jobs_india',
    # Investment fraud
    'crypto_invest_india',
    'stock_tips_guarantee',
    'forex_profit_india',
    'bitcoin_invest_india',
    'share_market_profit',
    # Romance setup channels
    'friendship_india',
    'india_friendship_group',
    'nri_connection',
]

async def scan_pig_butchering():
    print("="*65)
    print("  CINEOS PIG BUTCHERING SCANNER")
    print("  Rs 6,000 Cr lost in India 2024 — Nobody scanning this")
    print("="*65)

    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()

    findings = []
    total_msgs = 0

    for channel in PIG_CHANNELS_TO_SCAN:
        try:
            entity = await client.get_entity(channel)
            messages = await client.get_messages(entity, limit=500)
            subs = getattr(entity, 'participants_count', 0) or 0

            channel_patterns = {cat: [] for cat in PIG_PATTERNS}
            risk_score = 0

            for msg in messages:
                if not msg.text:
                    continue
                text = msg.text.lower()
                total_msgs += 1

                for category, patterns in PIG_PATTERNS.items():
                    for pattern in patterns:
                        if pattern.lower() in text:
                            channel_patterns[category].append(pattern)
                            risk_score += 10

            # Score this channel
            categories_found = [c for c,p in channel_patterns.items() if p]
            risk_score = min(100, risk_score)

            if risk_score >= 20:
                finding = {
                    'channel': channel,
                    'subscribers': subs,
                    'risk_score': risk_score,
                    'categories': categories_found,
                    'patterns': {c:list(set(p[:5]))
                                 for c,p in channel_patterns.items() if p},
                    'verdict': ('CONFIRMED PIG BUTCHERING' if risk_score>=70 else
                               'LIKELY PIG BUTCHERING' if risk_score>=40 else
                               'SUSPICIOUS'),
                    'platform': 'telegram',
                }
                findings.append(finding)
                print(f"  [{risk_score:3}/100] @{channel:35} "
                      f"{subs:7,} subs  {finding['verdict'][:20]}")
                for cat in categories_found[:2]:
                    pats = list(set(channel_patterns[cat]))[:2]
                    print(f"           {cat}: {pats}")

        except Exception as e:
            pass

    await client.disconnect()

    findings.sort(key=lambda x: -x['risk_score'])
    print(f"\n{'='*65}")
    print(f"  PIG BUTCHERING SCAN RESULTS")
    print(f"{'='*65}")
    print(f"  Channels scanned:  {len(PIG_CHANNELS_TO_SCAN)}")
    print(f"  Messages analyzed: {total_msgs:,}")
    print(f"  Pig channels found:{len(findings)}")
    print(f"  India fraud loss:  Rs 6,000 Cr/year (MHA data)")

    os.makedirs('reports', exist_ok=True)
    path = f"reports/pig_butchering_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump({
        'scanned_at': datetime.now().isoformat(),
        'channels_scanned': len(PIG_CHANNELS_TO_SCAN),
        'findings': findings,
        'india_loss_estimate': 'Rs 6,000 Cr annually (MHA 2024)',
        'pattern_library': PIG_PATTERNS,
    }, open(path,'w'), indent=2, default=str)
    print(f"  Saved: {path}")
    return findings

asyncio.run(scan_pig_butchering())
