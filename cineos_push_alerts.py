import os
"""
CINEOS Alert Pusher
Pushes ALL local alerts to Railway every morning.
Add to crontab after blindspot_fixes:
5 9 * * * cd ~/Desktop/cinerisk && python3 cineos_push_alerts.py
"""
import json, base64, urllib.request, time
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


def sync_to_github(alerts):
    TOKEN = os.environ.get('GITHUB_TOKEN_RAIL_READ','')
    if not TOKEN:
        print('  GitHub sync: no token')
        return
    REPO = 'dbayugandhar-cmyk/cinerisk-api'
    PATH = 'data/alerts_backup.json'
    url  = f'https://api.github.com/repos/{REPO}/contents/{PATH}'
    hdrs = {'Authorization':f'token {TOKEN}','Accept':'application/vnd.github.v3+json','User-Agent':'CINEOS','Content-Type':'application/json'}
    try:
        resp = json.loads(urllib.request.urlopen(urllib.request.Request(url,headers=hdrs),timeout=10).read())
        sha  = resp.get('sha','')
    except:
        sha = ''
    try:
        b64  = base64.b64encode(json.dumps(alerts[:10000],indent=2,default=str).encode()).decode()
        body = {'message':f'alerts: {len(alerts)}','content':b64}
        if sha: body['sha'] = sha
        req2 = urllib.request.Request(url,data=json.dumps(body).encode(),headers=hdrs,method='PUT')
        urllib.request.urlopen(req2,timeout=20)
        print(f'  GitHub sync: {len(alerts)} alerts written')
    except Exception as e:
        print(f'  GitHub sync failed: {e}')

if __name__ == '__main__':
    push()
    # Always sync full backup to GitHub so Railway loads correctly
    alerts = json.load(open('reports/alerts/live_alerts.json'))
    sync_to_github(alerts)