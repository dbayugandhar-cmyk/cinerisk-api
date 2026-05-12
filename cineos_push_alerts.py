"""
CINEOS Alert Pusher
Pushes ALL local alerts to Railway every morning.
Add to crontab after blindspot_fixes:
5 9 * * * cd ~/Desktop/cinerisk && python3 cineos_push_alerts.py
"""
import json, urllib.request, time
from datetime import datetime, timezone, timedelta

IST      = timezone(timedelta(hours=5, minutes=30))
RAILWAY  = 'https://cinerisk-api-production.up.railway.app/api/alert'
API_KEY  = 'cineos_internal_2026'
LOCAL    = 'reports/alerts/live_alerts.json'

def push():
    print(f'[{datetime.now(IST).strftime("%H:%M IST")}] Pushing alerts to Railway...')
    try:
        alerts = json.load(open(LOCAL))
    except Exception as e:
        print(f'  Could not load local alerts: {e}')
        return

    pushed = dupes = failed = 0
    for a in alerts:
        try:
            data = json.dumps(a).encode()
            req  = urllib.request.Request(
                RAILWAY, data=data,
                headers={'Content-Type':'application/json','X-API-Key':API_KEY},
                method='POST')
            r = json.loads(urllib.request.urlopen(req, timeout=8).read())
            if r.get('status') == 'duplicate':
                dupes += 1
            else:
                pushed += 1
            time.sleep(0.08)
        except Exception as e:
            failed += 1

    print(f'  Pushed: {pushed}  Dupes: {dupes}  Failed: {failed}')

    # Verify
    try:
        s = json.loads(urllib.request.urlopen(
            'https://cinerisk-api-production.up.railway.app/api/stats',
            timeout=8).read())
        print(f'  Railway now: {s["alerts"]} alerts')
    except:
        pass

if __name__ == '__main__':
    push()
