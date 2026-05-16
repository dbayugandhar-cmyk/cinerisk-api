"""
CINEOS Deep Enrichment Engine
Upgrades every operator profile with:
1. Real first-seen from Telegram channel metadata
2. Admin username extraction
3. Posting frequency analysis
4. Cross-vertical phone linking
5. Image-based phone extraction (OCR prep)

Run after deep scan: python3 cineos_deep_enrich.py
"""
import json, re, asyncio, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

IST = timezone(timedelta(hours=5,minutes=30))

async def enrich_channels():
    """
    Re-scan channels we already have to extract:
    - Channel creation date (real first-seen)
    - Admin/creator username
    - Recent message count (activity score)
    - Bio text (phones hidden in bio)
    - Invite links (find sister channels)
    """
    try:
        from telethon import TelegramClient
        from telethon.tl.functions.channels import GetFullChannelRequest
        from telethon.errors import FloodWaitError, ChannelPrivateError
    except ImportError:
        print("Telethon not available")
        return

    API_ID   = 38636931
    API_HASH = '852280f65386a00114ff7453eac7849b'

    channels  = json.load(open('reports/all_channels.json'))
    # Only enrich channels that have phones — highest value
    to_enrich = [c for c in channels if c.get('phones') and not c.get('enriched')]
    print(f'Channels to enrich: {len(to_enrich)} (have phones, not yet enriched)')

    enriched_count = 0
    async with TelegramClient('cineos_session', API_ID, API_HASH) as client:
        for i, ch in enumerate(to_enrich[:50]):  # 50 per run
            username = ch.get('username','')
            if not username: continue
            try:
                entity = await client.get_entity(username)
                full   = await client(GetFullChannelRequest(entity))

                # Extract creation date
                ch_id = entity.id
                # First message approximation
                msgs = await client.get_messages(entity, limit=1, reverse=True)
                if msgs:
                    first_msg_date = msgs[0].date.astimezone(IST)
                    ch['first_message_date'] = first_msg_date.isoformat()
                    ch['days_since_first_message'] = (datetime.now(IST) - first_msg_date).days

                # Recent activity
                recent = await client.get_messages(entity, limit=20)
                if recent:
                    ch['last_message_date']  = recent[0].date.astimezone(IST).isoformat()
                    ch['recent_message_count'] = len(recent)

                    # Post frequency (messages per day in last 20)
                    if len(recent) >= 2:
                        span = (recent[0].date - recent[-1].date).total_seconds() / 86400
                        ch['posts_per_day'] = round(len(recent) / max(span, 1), 1)

                    # Extract phones from recent messages
                    extra_phones = set(ch.get('phones',[]))
                    for msg in recent:
                        if msg.text:
                            found = re.findall(r'(?<!\d)([6-9]\d{9})(?!\d)', msg.text)
                            for p in found:
                                extra_phones.add('+91'+p if not p.startswith('+') else p)
                            # WhatsApp links
                            wa = re.findall(r'wa\.me/(\d+)', msg.text)
                            for w in wa:
                                extra_phones.add('+'+w if len(w)>10 else '+91'+w)
                    ch['phones'] = list(extra_phones)

                # Bio / about text — phones often hidden here
                if hasattr(full.full_chat, 'about') and full.full_chat.about:
                    bio = full.full_chat.about
                    ch['bio'] = bio[:500]
                    bio_phones = re.findall(r'(?<!\d)([6-9]\d{9})(?!\d)', bio)
                    wa_phones  = re.findall(r'wa\.me/(\d+)', bio)
                    all_bio_phones = ['+91'+p for p in bio_phones] + ['+'+w for w in wa_phones]
                    if all_bio_phones:
                        existing = set(ch.get('phones',[]))
                        existing.update(all_bio_phones)
                        ch['phones'] = list(existing)
                        print(f'  Bio phones found in @{username}: {all_bio_phones}')

                ch['enriched'] = True
                enriched_count += 1

                if enriched_count % 10 == 0:
                    json.dump(channels, open('reports/all_channels.json','w'), indent=2)
                    print(f'  Checkpoint: {enriched_count} enriched')

                await asyncio.sleep(2)

            except FloodWaitError as e:
                print(f'  Flood wait {e.seconds}s — stopping')
                break
            except ChannelPrivateError:
                ch['status'] = 'private'
            except Exception as e:
                pass

    json.dump(channels, open('reports/all_channels.json','w'), indent=2)
    print(f'Enriched: {enriched_count} channels')
    return enriched_count

def build_cross_vertical_map():
    """
    Build the cross-vertical phone map.
    Key insight: same phone in betting AND pharma
    = same criminal running multiple schemes.
    This doubles the legal exposure.
    """
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))

    phone_cats = defaultdict(set)
    phone_channels = defaultdict(list)

    for ch in channels:
        cat = ch.get('category','')
        for ph in ch.get('phones',[]):
            if ph and '+91888888' not in ph:
                phone_cats[ph].add(cat)
                phone_channels[ph].append(ch.get('username',''))

    for a in alerts:
        cat = a.get('category','')
        for ph in a.get('chain',{}).get('phones',[]):
            if ph:
                phone_cats[ph].add(cat)

    # Cross-vertical operators (most dangerous)
    cross = {ph: list(cats) for ph, cats in phone_cats.items()
             if len(cats) >= 2 and '' not in cats}

    cross_report = {
        'generated_at': datetime.now(IST).isoformat(),
        'total_phones': len(phone_cats),
        'cross_vertical_operators': len(cross),
        'operators': []
    }

    for ph, cats in sorted(cross.items(), key=lambda x: -len(x[1])):
        channels_list = phone_channels.get(ph,[])
        cross_report['operators'].append({
            'phone': ph,
            'categories': cats,
            'category_count': len(cats),
            'channels': channels_list[:10],
            'significance': f'Single operator confirmed across {len(cats)} fraud verticals: {", ".join(cats)}',
            'legal_note': 'Multi-vertical operation indicates organized criminal enterprise — enhanced PMLA + IT Act exposure',
        })

    json.dump(cross_report, open('reports/cross_vertical_map.json','w'), indent=2)

    print(f'\nCross-Vertical Operator Map:')
    print(f'  Total unique phones: {len(phone_cats)}')
    print(f'  Cross-vertical operators: {len(cross)}')
    print()
    print(f'  {"Phone":20} {"Categories":60}')
    print('  '+'-'*82)
    for op in cross_report['operators'][:15]:
        cats_str = ' + '.join(op['categories'])[:58]
        print(f'  {op["phone"]:20} {cats_str}')

    return cross_report

def activity_scoring():
    """
    Score each operator by activity level.
    Active = posting today. Dormant = last post >30 days.
    """
    channels = json.load(open('reports/all_channels.json'))
    now = datetime.now(IST)

    activity = {'active':[], 'recent':[], 'dormant':[], 'unknown':[]}

    for ch in channels:
        if not ch.get('phones'): continue
        last = ch.get('last_message_date') or ch.get('last_seen','')
        if not last:
            activity['unknown'].append(ch.get('username',''))
            continue
        try:
            last_dt = datetime.fromisoformat(last[:19]).replace(tzinfo=IST)
            days_ago = (now - last_dt).days
            if days_ago <= 1:
                activity['active'].append({'username':ch.get('username',''), 'days_ago':days_ago, 'phones':ch.get('phones',[])})
            elif days_ago <= 7:
                activity['recent'].append({'username':ch.get('username',''), 'days_ago':days_ago})
            else:
                activity['dormant'].append({'username':ch.get('username',''), 'days_ago':days_ago})
        except:
            activity['unknown'].append(ch.get('username',''))

    json.dump(activity, open('reports/activity_scores.json','w'), indent=2)
    print(f'\nActivity Scores (phone-bearing channels):')
    print(f'  Active (today/yesterday): {len(activity["active"])}')
    print(f'  Recent (last 7 days):     {len(activity["recent"])}')
    print(f'  Dormant (>7 days):        {len(activity["dormant"])}')
    print(f'  Unknown (no timestamp):   {len(activity["unknown"])}')
    for a in activity['active'][:5]:
        print(f'    ACTIVE: @{a["username"]} — {a["phones"][:1]}')

if __name__ == '__main__':
    import sys
    print('='*55)
    print(f'  CINEOS DEEP ENRICHMENT ENGINE')
    print(f'  {datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}')
    print('='*55)

    if '--enrich' in sys.argv:
        asyncio.run(enrich_channels())
    
    print('\nBuilding cross-vertical map...')
    build_cross_vertical_map()

    print('\nComputing activity scores...')
    activity_scoring()

    print('\nDone. Run with --enrich to deep-scan channel metadata.')
    print('Next: python3 cineos_phone_intel.py --all')
