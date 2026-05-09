"""
CINEOS Multilingual Signal Detection
Finds fraud/piracy channels in Hindi, Telugu, Tamil,
Kannada, Malayalam that English queries miss completely.
"""
import asyncio, json, os
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest

API_ID = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

# ── MULTILINGUAL SEARCH TERMS ─────────────────────────────
TERMS = {

    'hindi_betting': [
        'सट्टा मटका', 'क्रिकेट सट्टा', 'आईपीएल सट्टा',
        'ऑनलाइन सट्टा', 'क्रिकेट बेटिंग', 'फ्री टिप्स',
        'मैच फिक्सिंग', 'आईपीएल टिप्स', 'लॉटरी टिप्स',
    ],

    'hindi_piracy': [
        'फ्री मूवी', 'हिंदी मूवी डाउनलोड', 'वेब सीरीज फ्री',
        'नेटफ्लिक्स फ्री', 'हॉटस्टार फ्री', 'मूवी लीक',
        'बॉलीवुड डाउनलोड', 'ओटीटी फ्री',
    ],

    'hindi_investment': [
        'गारंटीड रिटर्न', 'रोज कमाई', 'घर बैठे कमाई',
        'क्रिप्टो मुनाफा', 'शेयर मार्केट टिप्स फ्री',
        'निवेश गारंटी', 'डेली इनकम',
    ],

    'telugu_betting': [
        'telugu cricket betting', 'telugu ipl betting',
        'telugu satta', 'telugu cricket tips free',
        'telugu match tips', 'ipl telugu tips',
        'cricket betting telugu', 'telugu betting tips',
    ],

    'telugu_piracy': [
        'telugu movies free', 'telugu movie download',
        'telugu web series free', 'telugu ott free',
        'telugu movies leaked', 'telugu new movies free',
        'telugu hotstar free', 'telugu netflix free',
    ],

    'telugu_investment': [
        'telugu stock tips', 'telugu crypto profit',
        'telugu investment guaranteed', 'telugu share tips',
        'telugu earning app', 'telugu daily income',
    ],

    'tamil_betting': [
        'tamil cricket betting', 'tamil ipl betting',
        'tamil satta', 'tamil cricket tips free',
        'tamilnadu betting tips', 'tamil match tips',
        'cricket betting tamil', 'tamil ipl tips',
    ],

    'tamil_piracy': [
        'tamil movies free download', 'tamil movie leak',
        'tamilblasters new link', 'tamil ott free',
        'tamil web series free', 'tamil hotstar free',
        'isaimini new link', 'tamilrockers new link',
    ],

    'kannada_betting': [
        'kannada cricket betting', 'kannada ipl betting',
        'kannada satta', 'kannada cricket tips',
        'kannada betting tips', 'kannada match tips',
    ],

    'kannada_piracy': [
        'kannada movies free', 'kannada movie download',
        'kannada ott free', 'kannada web series free',
        'kannada movies leaked', 'kannada new movies',
    ],

    'malayalam_betting': [
        'malayalam cricket betting', 'kerala ipl betting',
        'kerala satta', 'malayalam cricket tips',
        'kerala betting tips', 'malayalam match tips',
    ],

    'malayalam_piracy': [
        'malayalam movies free', 'malayalam movie download',
        'malayalam ott free', 'malayalam web series free',
        'malayalam movies leaked', 'kerala movies free',
    ],
}

async def multilingual_scan():
    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()
    print(f"[MULTILINGUAL] Connected — scanning {sum(len(v) for v in TERMS.values())} terms")
    print(f"Languages: Hindi, Telugu, Tamil, Kannada, Malayalam\n")

    # Load existing
    try:
        known = set(json.load(open('discovered_channels.json')))
    except:
        known = set()

    all_new = {}
    by_language = {}

    for category, terms in TERMS.items():
        language = category.split('_')[0]
        signal_type = category.split('_')[1]
        cat_new = 0

        for term in terms:
            try:
                result = await client(SearchRequest(q=term, limit=50))
                for chat in result.chats:
                    if hasattr(chat, 'username') and chat.username:
                        uname = chat.username
                        if uname not in known and uname not in all_new:
                            subs = getattr(chat, 'participants_count', 0) or 0
                            all_new[uname] = {
                                'channel': uname,
                                'title': getattr(chat, 'title', ''),
                                'subscribers': subs,
                                'url': f"https://t.me/{uname}",
                                'language': language,
                                'signal_type': signal_type,
                                'found_via': term,
                            }
                            cat_new += 1
            except Exception as e:
                pass

        if cat_new > 0:
            print(f"  [{language:10} {signal_type:12}] {cat_new} new channels")
            by_language[language] = by_language.get(language, 0) + cat_new

    await client.disconnect()

    channels = sorted(all_new.values(), key=lambda x: -x['subscribers'])
    total_reach = sum(c['subscribers'] for c in channels)

    print(f"\n{'='*65}")
    print(f"  CINEOS MULTILINGUAL SCAN RESULTS")
    print(f"{'='*65}")
    print(f"  New channels found: {len(channels)}")
    print(f"  Total reach: {total_reach:,}")
    print(f"\n  BY LANGUAGE:")
    for lang, count in sorted(by_language.items(), key=lambda x: -x[1]):
        print(f"    {lang:12}: {count} channels")
    print(f"\n  TOP 20 BY SUBSCRIBERS:")
    for c in channels[:20]:
        print(f"    @{c['channel']:40} {c['subscribers']:>8,} [{c['language']}]")

    # Save
    os.makedirs('reports', exist_ok=True)
    path = f"reports/multilingual_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(channels, open(path,'w'), indent=2, ensure_ascii=False)

    # Update seed list
    updated = list(known | set(all_new.keys()))
    json.dump(updated, open('discovered_channels.json','w'))
    print(f"\n  Seed list: {len(known)} → {len(updated)} channels")
    print(f"  Saved: {path}")

    return channels

asyncio.run(multilingual_scan())
