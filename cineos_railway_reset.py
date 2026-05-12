"""
CINEOS Railway Reset
Clears Railway's in-memory duplicate alerts
and reseeds with your 88 clean unique alerts.

Run AFTER Railway has redeployed the fix:
  python3 cineos_railway_reset.py
"""

import json, urllib.request, time
from datetime import datetime

RAILWAY  = 'https://cinerisk-api-production.up.railway.app'
API_KEY  = 'cineos_internal_2026'
LOCAL    = 'reports/alerts/live_alerts.json'

def post(path, data=None, key=None):
    try:
        headers = {'Content-Type': 'application/json'}
        if key:
            headers['X-API-Key'] = key
        body = json.dumps(data or {}).encode()
        req  = urllib.request.Request(
            f'{RAILWAY}{path}', data=body,
            headers=headers, method='POST')
        resp = urllib.request.urlopen(req, timeout=12)
        return json.loads(resp.read())
    except Exception as e:
        return {'error': str(e)}

def get(path):
    try:
        resp = urllib.request.urlopen(f'{RAILWAY}{path}', timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        return {'error': str(e)}

print('='*58)
print('  CINEOS RAILWAY RESET + RESEED')
print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('='*58)

# ── Step 1: Check Railway is live ────────────────────────
print('\n[1] Checking Railway...')
h = get('/health')
if 'error' in h:
    print(f'  Railway not reachable: {h["error"]}')
    print('  Wait 2 more minutes for Railway to redeploy, then retry.')
    exit(1)
print(f'  Status: {h.get("status","?")}')

# ── Step 2: Get current state ────────────────────────────
print('\n[2] Current Railway state...')
stats = get('/api/stats')
print(f'  Alerts before reset: {stats.get("alerts","?")}')

# ── Step 3: Reset Railway (clear all + reseed from SEED_ALERTS) ──
print('\n[3] Resetting Railway (clear + reseed)...')
reset_result = post('/api/reset', key=API_KEY)
if 'error' in reset_result:
    print(f'  Reset endpoint error: {reset_result["error"]}')
    print('  The /api/reset endpoint may not be deployed yet.')
    print('  Wait 2 more minutes for Railway redeploy, then retry.')
    exit(1)
print(f'  Reset: {reset_result}')
time.sleep(1)

# ── Step 4: Push clean 88 unique alerts ──────────────────
print('\n[4] Pushing 88 clean unique alerts...')
alerts = json.load(open(LOCAL))
print(f'  Loading {len(alerts)} alerts from local file...')

pushed  = 0
dupes   = 0
failed  = 0

for alert in alerts:
    result = post('/api/alert', alert, key=API_KEY)
    if 'error' in result:
        failed += 1
        if failed <= 3:
            print(f'  Error: {result["error"]}')
    elif result.get('status') == 'duplicate':
        dupes += 1
    else:
        pushed += 1
    time.sleep(0.12)

    if (pushed + dupes + failed) % 20 == 0:
        print(f'  Progress: {pushed} pushed · {dupes} dupes · {failed} failed')

print(f'\n  Final: {pushed} pushed · {dupes} dupes · {failed} failed')

# ── Step 5: Verify ────────────────────────────────────────
print('\n[5] Verifying final state...')
time.sleep(2)
stats = get('/api/stats')
print(f'  Railway alerts:  {stats.get("alerts","?")}')
print(f'  By severity:     {stats.get("by_severity",{})}')
print(f'  Last scan:       {stats.get("last_scan_time","?")}')

# ── Step 6: Top 10 check ─────────────────────────────────
print('\n[6] Top 10 signals (checking for dupes):')
top = get('/api/alerts/top10')
signals = top.get('signals', [])
seen = set()
dupes_found = 0
for i, s in enumerate(signals[:10], 1):
    t = s.get('title','')[:55]
    flag = ' ← DUPE' if t in seen else ''
    if flag:
        dupes_found += 1
    seen.add(t)
    sev = s.get('severity','?').upper()[:4]
    cat = s.get('category','?')[:15]
    print(f'  {i:2}. [{sev}] {t}{flag}')

print()
if dupes_found == 0:
    print('  ✓ No duplicates in top 10 — Railway is clean')
else:
    print(f'  ⚠ Still {dupes_found} dupes — Railway may not have redeployed fix yet')
    print('    Wait 2 minutes and run this script again')

print('\n' + '='*58)
print(f'  DONE — Railway has {stats.get("alerts","?")} unique alerts')
print('='*58)
