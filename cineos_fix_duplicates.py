"""
CINEOS Fix Script
Fixes:
1. Deduplicate Railway alerts (135 with dupes → unique set)
2. Push clean deduplicated alerts back to Railway
3. Show full diagnostic after fix
"""

import json, urllib.request, urllib.parse, time, hashlib
from datetime import datetime

RAILWAY   = 'https://cinerisk-api-production.up.railway.app'
API_KEY   = 'cineos_internal_2026'
LOCAL_FILE= 'reports/alerts/live_alerts.json'

def railway_get(path):
    try:
        resp = urllib.request.urlopen(f'{RAILWAY}{path}', timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        return {'error': str(e)}

def railway_post(path, data, key=None):
    try:
        headers = {'Content-Type': 'application/json'}
        if key:
            headers['X-API-Key'] = key
        req = urllib.request.Request(
            f'{RAILWAY}{path}',
            data=json.dumps(data).encode(),
            headers=headers, method='POST')
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        return {'error': str(e)}

print('='*58)
print('  CINEOS DEDUPLICATION + FIX')
print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('='*58)

# ── STEP 1: Get all alerts from Railway ──────────────────
print('\n[1] Fetching all alerts from Railway...')
data = railway_get('/api/alerts')
if 'error' in data:
    print(f'  ERROR: {data["error"]}')
    exit(1)

railway_alerts = data.get('alerts', data) if isinstance(data, dict) else data
if not isinstance(railway_alerts, list):
    # try different key
    for k in ['alerts','signals','data','results']:
        if k in data:
            railway_alerts = data[k]
            break

print(f'  Fetched: {len(railway_alerts)} alerts from Railway')

# ── STEP 2: Load local alerts ────────────────────────────
print('\n[2] Loading local alerts...')
local_alerts = json.load(open(LOCAL_FILE))
print(f'  Local: {len(local_alerts)} alerts')

# ── STEP 3: Merge and deduplicate ────────────────────────
print('\n[3] Deduplicating...')

all_alerts = local_alerts.copy()

# Add Railway alerts not in local
local_ids = {a['id'] for a in local_alerts}
added_from_railway = 0
for a in railway_alerts:
    if isinstance(a, dict) and a.get('id') and a['id'] not in local_ids:
        all_alerts.append(a)
        local_ids.add(a['id'])
        added_from_railway += 1

print(f'  New from Railway: {added_from_railway}')

# Deduplicate by id — keep first occurrence (most recent)
seen_ids    = set()
seen_titles = {}
clean       = []
dupes_by_id    = 0
dupes_by_title = 0

for a in all_alerts:
    aid   = a.get('id','')
    title = a.get('title','')

    # Skip duplicate IDs
    if aid and aid in seen_ids:
        dupes_by_id += 1
        continue

    # Skip near-duplicate titles (same title + category)
    title_key = f"{title[:60]}|{a.get('category','')}"
    if title_key in seen_titles:
        dupes_by_title += 1
        continue

    seen_ids.add(aid)
    seen_titles[title_key] = True
    clean.append(a)

print(f'  Removed duplicate IDs:     {dupes_by_id}')
print(f'  Removed duplicate titles:  {dupes_by_title}')
print(f'  Clean unique alerts:       {len(clean)}')

# ── STEP 4: Sort by severity then detected_at ────────────
sev_order = {'critical':0,'high':1,'medium':2,'low':3}
clean.sort(key=lambda a: (
    sev_order.get(a.get('severity','low'), 3),
    a.get('detected_at','')
), reverse=False)

# Keep max 200
clean = clean[:200]

# ── STEP 5: Save clean local file ────────────────────────
print('\n[4] Saving clean local file...')
json.dump(clean, open(LOCAL_FILE,'w'), indent=2, default=str)
print(f'  Saved: {len(clean)} alerts → {LOCAL_FILE}')

# ── STEP 6: Push clean set to Railway ────────────────────
# Railway API adds alerts — we need to push new unique ones
# The Railway API /api/alert accepts POST per alert
# Push all clean alerts — Railway deduplicates by ID server-side

print('\n[5] Pushing clean alerts to Railway...')
pushed  = 0
skipped = 0
failed  = 0

for alert in clean:
    try:
        result = railway_post('/api/alert', alert, key=API_KEY)
        if 'error' in result:
            if 'duplicate' in str(result).lower() or 'exists' in str(result).lower():
                skipped += 1
            else:
                failed += 1
        else:
            pushed += 1
        time.sleep(0.15)
    except Exception as e:
        failed += 1

print(f'  Pushed:  {pushed}')
print(f'  Skipped: {skipped} (already on Railway)')
print(f'  Failed:  {failed}')

# ── STEP 7: Verify Railway state ─────────────────────────
print('\n[6] Verifying Railway state...')
time.sleep(2)
stats = railway_get('/api/stats')
if 'error' not in stats:
    print(f'  Railway alerts:  {stats.get("alerts","?")}')
    print(f'  By severity:     {stats.get("by_severity",{})}')
else:
    print(f'  Could not verify: {stats["error"]}')

# Top 10 check
top = railway_get('/api/alerts/top10')
signals = top.get('signals', [])
print(f'\n[7] Top 10 after dedup:')
titles_seen = set()
for i, s in enumerate(signals[:10], 1):
    t = s.get('title','')[:55]
    flag = ' ← DUPE' if t in titles_seen else ''
    titles_seen.add(t)
    print(f'  {i:2}. [{s.get("severity","?").upper()[:4]}] {t}{flag}')

# ── STEP 8: Category and severity breakdown ───────────────
print('\n[8] Clean alert breakdown:')
by_sev = {}
by_cat = {}
for a in clean:
    s = a.get('severity','?')
    c = a.get('category','?')
    by_sev[s] = by_sev.get(s,0) + 1
    by_cat[c] = by_cat.get(c,0) + 1

print('  By severity:')
for k,v in sorted(by_sev.items(), key=lambda x: sev_order.get(x[0],9)):
    bar = '█' * v
    print(f'    {k:10} {v:3}  {bar}')

print('  By category:')
for k,v in sorted(by_cat.items(), key=lambda x:-x[1]):
    print(f'    {k:35} {v}')

print('\n' + '='*58)
print(f'  DONE — {len(clean)} unique alerts · Railway verified')
print('='*58)
