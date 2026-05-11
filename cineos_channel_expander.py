"""
CINEOS Channel Expander — Target 5,000+ channels

Strategy:
1. Start from known channels
2. Read every message for t.me links
3. Follow every link → new channel
4. Repeat until rate limit
5. Run daily → compounds automatically

This is how CINEOS goes from 1,115 to 5,000+
"""
import asyncio, json, os, re, hashlib
from datetime import datetime
from collections import defaultdict
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.errors import FloodWaitError

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

# All fraud categories to expand
SEARCH_TERMS = {
    'betting': [
        'satta matka', 'cricket betting', 'ipl betting',
        'toss fixer', 'match prediction', 'cbtf tips',
        'sky exchange', 'lotus book', 'reddy anna',
        'mahadev book', 'betbhai', 'laser247',
        'fairplay bet', 'wolf777', 'diamondexch',
        'tiger exchange', '1xbet india', 'parimatch india',
        'satta king', 'dpboss', 'kalyan matka',
        'milan matka', 'rajdhani matka', 'time bazar',
    ],
    'piracy': [
        'tamilrockers', 'movierulz', 'filmyzilla',
        'kuttymovies', 'isaimini', 'vegamovies',
        'cinemavilla', '9xmovies', 'bolly4u',
        'hd movies download', 'web series download',
        'ott free', 'hotstar free', 'netflix free',
        'prime video free', 'jiocinema free',
        'tamil movies', 'telugu movies', 'kannada movies',
        'hindi dubbed', 'south indian movies',
    ],
    'colour_prediction': [
        'colour prediction', 'color trading',
        'bigdaddy game', 'bdgwin', 'daman game',
        'yaarwin', '91club', 'tiranga game',
        'ok win', 'wingo predict', 'aviator game',
        'crash game earn', 'colour game earn',
        'prediction hack', 'colour trick',
    ],
    'investment_fraud': [
        'sebi tips free', 'stock tips guarantee',
        'option tips 100', 'sure shot nifty',
        'guaranteed profit trading', 'crypto pump signal',
        'bitcoin signal vip', 'crypto earn daily',
        'forex signal india', 'mutual fund tips',
        'pig butchering', 'investment scheme',
        'multibagger stock', 'penny stock tips',
    ],
    'task_fraud': [
        'task earn daily', 'youtube task earn',
        'like task money', 'part time earn telegram',
        'work from home task', 'online task earn',
        'rating task india', 'google task earn',
        'amazon task earn', 'instagram task earn',
    ],
    'loan_fraud': [
        'instant loan no cibil', 'loan without documents',
        'emergency loan telegram', 'quick loan india',
        'loan agent commission', 'loan recovery agent',
        'instant approval loan', 'fake loan app',
    ],
    'digital_arrest': [
        'digital arrest script', 'cbi officer call',
        'ed officer fraud', 'police impersonation',
        'aadhaar freeze fraud', 'cyber crime call',
    ],
    'pharma_fraud': [
        'medicine wholesale cheap', 'pharma agent wanted',
        'cancer medicine cheap', 'insulin cheap buy',
        'medicine below mrp', 'pharmaceutical wholesale',
        'generic medicine cheap', 'fake medicine sell',
    ],
    'counterfeit': [
        'first copy wholesale', 'replica shoes sell',
        'master copy brand', 'duplicate product sell',
        'aaa quality wholesale', 'super clone sell',
        'inspired by wholesale', '7a quality sell',
    ],
}

async def expand_channels():
    """
    Main expansion engine.
    Searches Telegram for each category,
    then deep scans found channels for links
    to discover even more channels.
    """
    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()

    # Load existing channels
    existing = json.load(open('reports/all_channels.json'))
    known    = {c.get('username','').lower()
                for c in existing if c.get('username')}

    print(f"  Starting channels: {len(existing)}")
    print(f"  Known usernames:   {len(known)}")

    new_channels  = []
    channel_links = defaultdict(set)  # username → linked channels

    # ── PHASE 1: SEARCH BY KEYWORD ────────────────────────
    print(f"\n[PHASE 1] Keyword search across all categories...")

    for category, terms in SEARCH_TERMS.items():
        print(f"\n  Category: {category} ({len(terms)} terms)")
        category_found = 0

        for term in terms:
            try:
                result = await client(
                    SearchRequest(q=term, limit=20))

                for chat in result.chats:
                    username = getattr(chat,'username','') or ''
                    title    = getattr(chat,'title','') or ''
                    subs     = getattr(
                        chat,'participants_count',0) or 0

                    if not username:
                        continue
                    if username.lower() in known:
                        continue
                    if subs < 200:  # minimum threshold
                        continue

                    known.add(username.lower())
                    category_found += 1

                    new_channels.append({
                        'username':      username,
                        'title':         title,
                        'subscribers':   subs,
                        'category':      category,
                        'discovered_by': term,
                        'platform':      'telegram',
                        'found_at':      datetime.now().isoformat(),
                        'evidence_hash': hashlib.sha256(
                            username.encode()).hexdigest(),
                    })

                await asyncio.sleep(1.5)

            except FloodWaitError as e:
                print(f"    Rate limit: wait {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                await asyncio.sleep(1)

        print(f"    New channels found: {category_found}")

    print(f"\n  Phase 1 complete: {len(new_channels)} new channels")

    # ── PHASE 2: READ LINKED CHANNELS FROM MESSAGES ───────
    print(f"\n[PHASE 2] Reading messages for linked channels...")
    print(f"  Scanning top channels by subscriber count...")

    # Scan new high-subscriber channels for links
    high_value = sorted(
        new_channels,
        key=lambda x: -x.get('subscribers', 0)
    )[:100]  # top 100 new channels

    link_discovered = []

    for ch in high_value:
        try:
            entity   = await client.get_entity(ch['username'])
            messages = await client.get_messages(entity, limit=100)
            all_text = ' '.join(m.text for m in messages if m.text)

            # Find all Telegram links in messages
            links = re.findall(
                r't\.me/([A-Za-z0-9_]{5,})', all_text)
            links = [l for l in links
                     if l.lower() not in known
                     and not l.startswith('joinchat')]

            if links:
                channel_links[ch['username']].update(links)

            # Try to get info on linked channels
            for link in links[:5]:  # max 5 per channel
                try:
                    linked = await client.get_entity(link)
                    link_subs = getattr(
                        linked, 'participants_count', 0) or 0
                    link_title = getattr(linked, 'title', '') or ''

                    if link_subs >= 200 and link.lower() not in known:
                        known.add(link.lower())
                        link_discovered.append({
                            'username':      link,
                            'title':         link_title,
                            'subscribers':   link_subs,
                            'category':      ch['category'],
                            'discovered_by': f"linked_from_{ch['username']}",
                            'platform':      'telegram',
                            'found_at':      datetime.now().isoformat(),
                            'evidence_hash': hashlib.sha256(
                                link.encode()).hexdigest(),
                        })
                    await asyncio.sleep(2)
                except:
                    await asyncio.sleep(1)

            await asyncio.sleep(5)  # rate limit protection

        except FloodWaitError as e:
            print(f"  Rate limit: {e.seconds}s — waiting...")
            await asyncio.sleep(min(e.seconds, 60))
        except Exception:
            await asyncio.sleep(2)

    print(f"  Link-discovered channels: {len(link_discovered)}")

    # ── PHASE 3: EXISTING CHANNEL LINK EXPANSION ──────────
    print(f"\n[PHASE 3] Expanding from existing database...")

    # Read messages from existing high-value channels
    # to find channels we missed
    existing_top = sorted(
        existing,
        key=lambda x: -x.get('subscribers', 0)
    )[:50]

    existing_discovered = []

    for ch in existing_top:
        username = ch.get('username','')
        if not username:
            continue
        try:
            entity   = await client.get_entity(username)
            messages = await client.get_messages(entity, limit=200)
            all_text = ' '.join(m.text for m in messages if m.text)

            links = re.findall(
                r't\.me/([A-Za-z0-9_]{5,})', all_text)
            new_links = [l for l in links
                        if l.lower() not in known
                        and not l.startswith('joinchat')]

            for link in new_links[:3]:
                try:
                    linked = await client.get_entity(link)
                    link_subs = getattr(
                        linked, 'participants_count', 0) or 0
                    link_title = getattr(linked, 'title', '') or ''

                    if link_subs >= 200:
                        known.add(link.lower())
                        existing_discovered.append({
                            'username':      link,
                            'title':         link_title,
                            'subscribers':   link_subs,
                            'category':      ch.get('category','unknown'),
                            'discovered_by': f"existing_{username}",
                            'platform':      'telegram',
                            'found_at':      datetime.now().isoformat(),
                            'evidence_hash': hashlib.sha256(
                                link.encode()).hexdigest(),
                        })
                    await asyncio.sleep(2)
                except:
                    await asyncio.sleep(1)

            await asyncio.sleep(5)

        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds, 60))
        except Exception:
            await asyncio.sleep(2)

    print(f"  Existing-expansion finds: {len(existing_discovered)}")

    await client.disconnect()

    # ── COMBINE + SAVE ─────────────────────────────────────
    all_new = new_channels + link_discovered + existing_discovered

    # Deduplicate
    seen     = {c.get('username','').lower() for c in existing}
    unique   = []
    for ch in all_new:
        u = ch.get('username','').lower()
        if u and u not in seen:
            seen.add(u)
            unique.append(ch)

    # Add to main database
    existing.extend(unique)

    os.makedirs('reports', exist_ok=True)
    json.dump(existing,
              open('reports/all_channels.json','w'),
              indent=2, default=str)

    # Category breakdown
    by_cat = defaultdict(int)
    for ch in unique:
        by_cat[ch.get('category','unknown')] += 1

    total_reach = sum(ch.get('subscribers',0) for ch in unique)

    print(f"\n{'='*55}")
    print(f"  CHANNEL EXPANSION COMPLETE")
    print(f"{'='*55}")
    print(f"  Previous total:  {len(existing) - len(unique)}")
    print(f"  New channels:    {len(unique)}")
    print(f"  New total:       {len(existing)}")
    print(f"  New reach:       {total_reach/1000000:.1f}M subscribers")
    print(f"\n  BY CATEGORY:")
    for cat, count in sorted(by_cat.items(),
                              key=lambda x: -x[1]):
        print(f"    {cat:25} +{count}")

    return len(existing), unique

total, new = asyncio.run(expand_channels())

# Update intelligence graph
print(f"\n  Rebuilding intelligence graph...")
os.system('python3 cineos_intelligence_graph.py 2>/dev/null')

import subprocess, json
result = subprocess.run(
    ['git','log','--oneline','-1'],
    capture_output=True, text=True)

print(f"""
{'='*55}
  CINEOS DATABASE STATUS
{'='*55}
  Total channels: {total}
  Target:         5,000+
  Gap:            {max(0, 5000 - total)} more to find

  HOW TO REACH 5,000:
  Run this script daily — rate limit resets 8am
  Each run adds 200-500 channels
  After 10 days: 3,000+
  After 20 days: 5,000+

  The graph grows automatically.
  The moat deepens every day.
""")
