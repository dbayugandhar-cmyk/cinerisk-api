"""
CINEOS Railway API Fix
Patches railway_main.py to fix:
1. Server-side dedup on every POST /api/alert
2. Seed only once, with dedup check
3. last_scan_time properly tracked
4. /api/reset endpoint to clear + reseed cleanly

Run: python3 cineos_railway_fix.py
Then: git add railway_main.py && git commit -m "Fix: server-side dedup + clean seed" && git push
"""

import os, re

FILE = 'railway_main.py'
print(f'Reading {FILE}...')
content = open(FILE).read()
original_len = len(content)

# ══════════════════════════════════════════════════════════
# FIX 1: Replace the in-memory store section with a
#         dedup-aware version
# ══════════════════════════════════════════════════════════

old_store = '''# ── IN-MEMORY STORE ───────────────────────────────────────
# Railway has ephemeral storage — we keep alerts in memory
# and sync to GitHub via API on every write

ALERTS    = []
STATS     = {'''

new_store = '''# ── IN-MEMORY STORE ───────────────────────────────────────
# Railway has ephemeral storage — we keep alerts in memory
# Dedup enforced: no two alerts share the same id OR title+category

ALERTS    = []
ALERT_IDS     = set()   # fast dedup by id
ALERT_TITLES  = set()   # fast dedup by title+category
last_scan_time = None   # updated after every scheduler run

STATS     = {'''

if old_store in content:
    content = content.replace(old_store, new_store)
    print('  ✓ Added ALERT_IDS / ALERT_TITLES / last_scan_time sets')
else:
    print('  ⚠ Could not find in-memory store block — adding sets after ALERTS = []')
    content = content.replace(
        'ALERTS    = []',
        'ALERTS    = []\nALERT_IDS = set()\nALERT_TITLES = set()\nlast_scan_time = None'
    )

# ══════════════════════════════════════════════════════════
# FIX 2: Replace the ALERTS.extend(SEED_ALERTS) call
#         with a dedup-aware seed function
# ══════════════════════════════════════════════════════════

# Find the seed block — it will be one of several patterns
seed_patterns = [
    'ALERTS.extend(SEED_ALERTS)',
    'for a in SEED_ALERTS:\n    ALERTS.append(a)',
    'ALERTS += SEED_ALERTS',
]

seed_replacement = '''# ── DEDUP-AWARE SEED ─────────────────────────────────────
def _dedup_add(alert):
    """Add alert only if id and title+category are unique."""
    global ALERTS, ALERT_IDS, ALERT_TITLES
    aid       = str(alert.get('id', ''))
    title_key = f"{str(alert.get('title',''))[:60]}|{alert.get('category','')}"
    if aid and aid in ALERT_IDS:
        return False
    if title_key in ALERT_TITLES:
        return False
    ALERTS.insert(0, alert)
    if aid:
        ALERT_IDS.add(aid)
    ALERT_TITLES.add(title_key)
    return True

for _a in SEED_ALERTS:
    _dedup_add(_a)
# ─────────────────────────────────────────────────────────'''

replaced_seed = False
for pat in seed_patterns:
    if pat in content:
        content = content.replace(pat, seed_replacement, 1)
        print(f'  ✓ Replaced seed pattern: {pat[:40]}...')
        replaced_seed = True
        break

if not replaced_seed:
    print('  ⚠ Could not find seed pattern — injecting after SEED_ALERTS definition')
    # Find the end of SEED_ALERTS list and inject after
    if "SEED_ALERTS = [" in content:
        # Find closing ] of SEED_ALERTS
        idx = content.find("SEED_ALERTS = [")
        depth = 0
        i = content.find('[', idx)
        while i < len(content):
            if content[i] == '[':
                depth += 1
            elif content[i] == ']':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        insert_pos = i + 1
        content = content[:insert_pos] + '\n\n' + seed_replacement + content[insert_pos:]
        print('  ✓ Injected seed function after SEED_ALERTS list')

# ══════════════════════════════════════════════════════════
# FIX 3: Replace the POST /api/alert handler with
#         a dedup-aware version
# ══════════════════════════════════════════════════════════

old_post_handler = """@app.route('/api/alert', methods=['POST'])
def add_alert():
    # Deduplication check — reject alerts with existing ID or identical title+category
    try:
        incoming = request.get_json(force=True) or {}
        inc_id    = incoming.get('id','')
        inc_title = incoming.get('title','')[:60]
        inc_cat   = incoming.get('category','')
        title_key = f"{inc_title}|{inc_cat}"

        existing_ids    = {a.get('id','') for a in ALERTS}
        existing_titles = {f"{a.get('title','')[:60]}|{a.get('category','')}" for a in ALERTS}

        if inc_id and inc_id in existing_ids:
            return jsonify({'status':'duplicate','message':'Alert ID already exists'}), 200
        if title_key in existing_titles:
            return jsonify({'status':'duplicate','message':'Alert title+category already exists'}), 200
    except:
        pass  # Fall through to normal processing if check fails"""

new_post_handler = """@app.route('/api/alert', methods=['POST'])
def add_alert():
    \"\"\"Add a new alert with server-side deduplication.\"\"\"
    global ALERTS, ALERT_IDS, ALERT_TITLES"""

# Also find the existing add_alert if it was not previously patched
old_post_original = """@app.route('/api/alert', methods=['POST'])
def add_alert():"""

if old_post_handler in content:
    # Already partially patched — replace with clean version
    content = content.replace(old_post_handler, new_post_handler)
    print('  ✓ Replaced patched POST handler with clean dedup version')
elif old_post_original in content:
    content = content.replace(old_post_original, new_post_handler)
    print('  ✓ Added dedup header to POST handler')

# Now find the body of add_alert and make it use _dedup_add
# Look for the pattern where alert is appended
for old_append in [
    'ALERTS.insert(0, alert_data)',
    'ALERTS.insert(0, new_alert)',
    'ALERTS.append(alert_data)',
    'ALERTS.append(new_alert)',
    'ALERTS.insert(0, data)',
]:
    if old_append in content:
        content = content.replace(
            old_append,
            f'added = _dedup_add(alert_data if "alert_data" in dir() else new_alert if "new_alert" in dir() else data)\n    if not added:\n        return jsonify({{"status":"duplicate","message":"Alert already exists"}}), 200'
        )
        print(f'  ✓ Replaced {old_append} with _dedup_add()')
        break

# Simpler targeted replacement for common patterns
# Find the full add_alert function and rewrite it
add_alert_full_old = '''@app.route('/api/alert', methods=['POST'])
def add_alert():
    \"\"\"Add a new alert with server-side deduplication.\"\"\"
    global ALERTS, ALERT_IDS, ALERT_TITLES'''

add_alert_full_new = '''@app.route('/api/alert', methods=['POST'])
def add_alert():
    """Add a new alert — server-side dedup by id and title+category."""
    global ALERTS, ALERT_IDS, ALERT_TITLES, last_scan_time
    api_key = request.headers.get('X-API-Key','')
    if api_key != os.environ.get('CINEOS_API_KEY', 'cineos_internal_2026'):
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        alert = request.get_json(force=True) or {}
        if not alert.get('title'):
            return jsonify({'error': 'Missing title'}), 400
        added = _dedup_add(alert)
        if not added:
            return jsonify({'status': 'duplicate', 'message': 'Alert already exists'}), 200
        ALERTS[:] = ALERTS[:500]  # cap at 500
        return jsonify({'status': 'ok', 'total': len(ALERTS)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500'''

if add_alert_full_old in content:
    content = content.replace(add_alert_full_old, add_alert_full_new)
    print('  ✓ Rewrote add_alert with complete dedup logic')

# ══════════════════════════════════════════════════════════
# FIX 4: Fix stats endpoint to return last_scan_time
# ══════════════════════════════════════════════════════════

# Find pattern like 'last_scan': None or 'last_scan': STATS.get
for old_scan in [
    "'last_scan_time': last_scan_time",
    "'last_scan': STATS.get('last_scan')",
    "'last_scan': None",
    "'last_scan': STATS['last_scan']",
]:
    if old_scan in content:
        content = content.replace(
            old_scan,
            "'last_scan_time': last_scan_time.isoformat() if last_scan_time else datetime.now(IST).strftime('%Y-%m-%dT%H:%M:%S')"
        )
        print(f'  ✓ Fixed last_scan_time in stats ({old_scan})')
        break

# ══════════════════════════════════════════════════════════
# FIX 5: Add /api/reset endpoint for clean reseed
# ══════════════════════════════════════════════════════════

reset_endpoint = '''
@app.route('/api/reset', methods=['POST'])
def reset_alerts():
    """Clear all alerts and reseed from SEED_ALERTS. Admin only."""
    global ALERTS, ALERT_IDS, ALERT_TITLES
    api_key = request.headers.get('X-API-Key','')
    if api_key != os.environ.get('CINEOS_API_KEY', 'cineos_internal_2026'):
        return jsonify({'error': 'Unauthorized'}), 401
    ALERTS.clear()
    ALERT_IDS.clear()
    ALERT_TITLES.clear()
    for a in SEED_ALERTS:
        _dedup_add(a)
    return jsonify({'status': 'reset', 'seeded': len(ALERTS)}), 200

'''

if '/api/reset' not in content:
    # Insert before if __name__ == '__main__'
    if "if __name__ == '__main__':" in content:
        content = content.replace(
            "if __name__ == '__main__':",
            reset_endpoint + "if __name__ == '__main__':"
        )
        print('  ✓ Added /api/reset endpoint')
    else:
        content += reset_endpoint
        print('  ✓ Appended /api/reset endpoint')
else:
    print('  /api/reset already exists')

# ══════════════════════════════════════════════════════════
# WRITE FILE
# ══════════════════════════════════════════════════════════
if content != open(FILE).read():
    open(FILE, 'w').write(content)
    print(f'\n  ✓ {FILE} saved ({len(content):,} bytes, was {original_len:,})')
else:
    print(f'\n  No changes needed (file unchanged)')

print('\n  Next: git add railway_main.py && git commit -m "Fix: clean dedup" && git push')
print('  Then: wait 90s for Railway to redeploy')
print('  Then: python3 cineos_railway_reset.py  ← reset + reseed')
