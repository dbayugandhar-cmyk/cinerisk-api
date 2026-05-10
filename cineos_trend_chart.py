"""
CINEOS Historical Trend Tracker
Append-only — never overwrites.
After 7 days: weekly trend.
After 30 days: monthly curve.
After 90 days: quarterly intelligence.
This is what enterprise clients pay extra for.
"""
import json, os
from datetime import datetime

HISTORY_FILE = 'reports/channel_history.json'

def get_history():
    try:
        return json.load(open(HISTORY_FILE))
    except:
        return {'entries': [], 'created_at': datetime.now().isoformat()}

def add_today():
    history = get_history()

    try:
        channels   = json.load(open('reports/all_channels.json'))
        total      = len(channels)
        reach      = sum(c.get('subscribers', 0) for c in channels)

        cats = {
            'betting':    sum(1 for c in channels if any(k in c.get('username','').lower()+c.get('title','').lower() for k in ['satta','matka','bet','reddy','mahadev','lotus','ipl','toss'])),
            'crypto':     sum(1 for c in channels if any(k in c.get('username','').lower()+c.get('title','').lower() for k in ['crypto','bitcoin','pump','signal','stock','zerodha'])),
            'piracy':     sum(1 for c in channels if any(k in c.get('username','').lower()+c.get('title','').lower() for k in ['movie','film','tamilrockers','filmyzilla','download'])),
            'task_fraud': sum(1 for c in channels if any(k in c.get('username','').lower()+c.get('title','').lower() for k in ['earn','task','online','work','home','money'])),
            'colour':     sum(1 for c in channels if any(k in c.get('username','').lower()+c.get('title','').lower() for k in ['colour','color','daman','bdgwin','bigdaddy','yaarwin'])),
        }

        entry = {
            'date':             datetime.now().strftime('%Y-%m-%d'),
            'timestamp':        datetime.now().isoformat(),
            'total_channels':   total,
            'total_reach':      reach,
            'categories':       cats,
        }

        # Avoid duplicate entries for same day
        today = entry['date']
        history['entries'] = [e for e in history['entries'] if e.get('date') != today]
        history['entries'].append(entry)
        history['entries'].sort(key=lambda x: x['date'])
        history['last_updated'] = datetime.now().isoformat()

        os.makedirs('reports', exist_ok=True)
        json.dump(history, open(HISTORY_FILE, 'w'), indent=2)
        print(f"History: {len(history['entries'])} days | Today: {total} channels | {reach/1000000:.1f}M reach")
        return history

    except Exception as e:
        print(f"History error: {e}")
        return history

def print_trend():
    history = get_history()
    entries = history.get('entries', [])
    if len(entries) < 2:
        print("Need at least 2 days of data for trends")
        return

    print(f"\n{'DATE':12} {'CHANNELS':10} {'REACH':12} {'BETTING':9} {'PIRACY':8}")
    print("-" * 60)
    for e in entries[-14:]:  # last 14 days
        print(f"{e['date']:12} "
              f"{e['total_channels']:10,} "
              f"{e['total_reach']/1000000:8.1f}M   "
              f"{e.get('categories',{}).get('betting',0):9} "
              f"{e.get('categories',{}).get('piracy',0):8}")

if __name__ == '__main__':
    add_today()
    print_trend()
