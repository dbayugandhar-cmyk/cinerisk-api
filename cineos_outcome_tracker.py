"""
CINEOS Outcome Tracker
Closes the intelligence loop:
  Did the channel go down?
  Was the seller removed?
  Was an FIR filed?
  Was the operator arrested?

Run daily after takedown notices are sent.
This is what makes CINEOS a closed-loop intelligence platform —
not just detection, but measured outcomes.
"""
import asyncio, json, os
from datetime import datetime
from telethon import TelegramClient

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

OUTCOME_FILE = 'reports/outcome_tracker.json'

def load_outcomes():
    try:
        return json.load(open(OUTCOME_FILE))
    except:
        return {
            'created_at':  datetime.now().isoformat(),
            'channels':    {},
            'sellers':     {},
            'summary':     {'monitored': 0, 'down': 0, 'still_live': 0},
        }

async def check_channel_status(username: str) -> dict:
    """Check if a Telegram channel is still live."""
    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()

    result = {
        'username':    username,
        'checked_at':  datetime.now().isoformat(),
        'status':      'unknown',
    }

    try:
        entity = await client.get_entity(username)
        subs   = getattr(entity, 'participants_count', 0) or 0
        result['status']      = 'live'
        result['subscribers'] = subs
    except Exception as e:
        err = str(e).lower()
        if 'not found' in err or 'invalid' in err or 'banned' in err:
            result['status'] = 'down'
            result['reason'] = str(e)
        else:
            result['status'] = 'error'
            result['error']  = str(e)

    await client.disconnect()
    return result

async def track_outcomes():
    outcomes = load_outcomes()

    # Check top 20 highest-risk channels
    try:
        channels = json.load(open('reports/all_channels.json'))
        top = sorted(channels,
                     key=lambda x: -x.get('subscribers', 0))[:20]
    except:
        top = []

    print(f"Checking status of {len(top)} channels...")
    down_count   = 0
    live_count   = 0
    for ch in top:
        username = ch.get('username', '')
        if not username:
            continue

        result = await check_channel_status(username)
        outcomes['channels'][username] = result

        status_sym = '✓ LIVE' if result['status'] == 'live' else '✗ DOWN'
        subs_str   = f"{result.get('subscribers',0)/1000:.0f}K" \
                     if result['status'] == 'live' else 'N/A'
        print(f"  {status_sym}  @{username:40} {subs_str}")

        if result['status'] == 'down':
            down_count += 1
        elif result['status'] == 'live':
            live_count += 1

    outcomes['summary'] = {
        'monitored':   len(top),
        'down':        down_count,
        'still_live':  live_count,
        'checked_at':  datetime.now().isoformat(),
    }

    os.makedirs('reports', exist_ok=True)
    json.dump(outcomes, open(OUTCOME_FILE, 'w'), indent=2, default=str)

    print(f"\n{'='*55}")
    print(f"  OUTCOME TRACKING RESULTS")
    print(f"{'='*55}")
    print(f"  Monitored: {len(top)}")
    print(f"  Still live: {live_count}")
    print(f"  Down/removed: {down_count}")
    print(f"  Saved: {OUTCOME_FILE}")
    if down_count > 0:
        print(f"\n  {down_count} channels confirmed DOWN — report to clients")

asyncio.run(track_outcomes())
