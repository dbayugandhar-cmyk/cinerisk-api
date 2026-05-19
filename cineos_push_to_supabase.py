"""
CINEOS Supabase Sync
Pushes all local alerts to Supabase.
Run after deep scan: python3 cineos_push_to_supabase.py
Crontab: add after push_alerts at 9:15am
"""
from supabase import create_client
import json, time

URL = 'https://pgvbnwiflefhunkbbwah.supabase.co'
KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBndmJud2lmbGVmaHVua2Jid2FoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkyMDYyMTYsImV4cCI6MjA5NDc4MjIxNn0.sO2B6lEW9b36hLy3Z3GzsaGeVA6-y0L7XJLGvNVkAvQ'

def main():
    from datetime import datetime, timezone, timedelta
    IST = timezone(timedelta(hours=5,minutes=30))
    print(f'[{datetime.now(IST).strftime("%H:%M IST")}] Syncing to Supabase...')

    sb = create_client(URL, KEY)
    alerts = json.load(open('reports/alerts/live_alerts.json'))

    # Get existing IDs from Supabase
    existing = set()
    try:
        r = sb.table('alerts').select('id').execute()
        existing = {row['id'] for row in r.data}
        print(f'  Existing in Supabase: {len(existing)}')
    except: pass

    # Only push new alerts
    new_alerts = [a for a in alerts if str(a.get('id',''))[:50] not in existing]
    print(f'  New alerts to push: {len(new_alerts)}')

    pushed = failed = 0
    for i in range(0, len(new_alerts), 50):
        batch = new_alerts[i:i+50]
        try:
            rows = [{
                'id':           str(a.get('id',''))[:50],
                'title':        str(a.get('title',''))[:500],
                'category':     str(a.get('category','unknown'))[:50],
                'severity':     str(a.get('severity','high'))[:20],
                'platform':     str(a.get('platform','Telegram'))[:100],
                'detail':       str(a.get('detail',''))[:1000],
                'source':       str(a.get('source',''))[:200],
                'detected_at':  a.get('detected_at',''),
                'reach':        int(a.get('reach') or 0),
                'evidence_hash':str(a.get('evidence_hash',''))[:100],
                'chain':        a.get('chain',{}),
            } for a in batch]
            sb.table('alerts').upsert(rows).execute()
            pushed += len(batch)
        except Exception as e:
            failed += len(batch)
            print(f'  Batch error: {e}')
        time.sleep(0.1)

    # Verify final count
    r = sb.table('alerts').select('id', count='exact').execute()
    print(f'  Pushed: {pushed}  Failed: {failed}')
    print(f'  Supabase total: {r.count} alerts')

if __name__ == '__main__':
    main()
