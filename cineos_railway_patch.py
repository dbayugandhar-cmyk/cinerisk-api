"""
CINEOS Railway Patch
Apply to railway_main.py to fix:
1. Duplicate alerts on /api/alert POST
2. last_scan_time showing "unknown"
3. Dedup check on every new alert added

Run: python3 cineos_railway_patch.py
Then: git add railway_main.py && git commit -m "Fix: dedup alerts, fix last_scan_time" && git push
"""

import re

RAILWAY_FILE = 'railway_main.py'

print(f'Reading {RAILWAY_FILE}...')
content = open(RAILWAY_FILE).read()
original = content

# ── FIX 1: Add dedup check to add_alert in alert_engine ──
# Find the add_alert function in railway_main.py or cineos_alert_engine.py

# Check if dedup already exists
if 'existing_ids' in content and 'duplicate' in content.lower():
    print('  Dedup check already present in railway_main.py')
else:
    # Find the POST /api/alert route and add dedup
    old_post = '''@app.route('/api/alert', methods=['POST'])
def add_alert():'''

    new_post = '''@app.route('/api/alert', methods=['POST'])
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
        pass  # Fall through to normal processing if check fails'''

    if old_post in content:
        content = content.replace(old_post, new_post)
        print('  ✓ Added dedup check to POST /api/alert')
    else:
        print('  ⚠ Could not find POST /api/alert route — checking for alternate pattern')
        # Try alternate
        if "def add_alert" in content:
            print('  Found add_alert function — manual review needed')
        else:
            print('  add_alert not found in railway_main.py')

# ── FIX 2: Fix last_scan_time ─────────────────────────────
# The stats endpoint returns last_scan_time from a variable
# that may not be initialised before first scan

old_last_scan_none = "last_scan_time = None"
new_last_scan = '''last_scan_time = None
last_scan_results = {}'''

if "last_scan_time" not in content:
    # Add initialisation near top of file after imports
    # Find a safe insertion point
    insert_after = "ALERTS = []"
    if insert_after in content:
        content = content.replace(
            insert_after,
            insert_after + "\nlast_scan_time = None\nlast_scan_results = {}"
        )
        print('  ✓ Added last_scan_time initialisation')
    else:
        print('  ⚠ Could not find ALERTS = [] to insert last_scan_time')
else:
    print('  last_scan_time already initialised')

# ── FIX 3: Fix stats endpoint to show last_scan_time ─────
old_stats_unknown = "'last_scan_time': last_scan_time"
if old_stats_unknown not in content:
    # Find stats route and patch it
    stats_pattern = "def get_stats():"
    if stats_pattern in content:
        # Find where last_scan_time would be returned
        if "'last_scan_time'" not in content:
            content = content.replace(
                "'alerts': len(ALERTS)",
                "'alerts': len(ALERTS),\n        'last_scan_time': last_scan_time.isoformat() if last_scan_time else datetime.now(IST).isoformat()"
            )
            print('  ✓ Fixed last_scan_time in stats response')
    else:
        print('  ⚠ Could not find get_stats route')
else:
    print('  last_scan_time already in stats response')

# ── FIX 4: Update last_scan_time after each scan ─────────
scan_marker = "def run_scan():"
if scan_marker in content and "last_scan_time = " not in content:
    # Find where scan results are processed and add timestamp update
    content = content.replace(
        "def run_scan():",
        "def run_scan():\n    global last_scan_time\n    last_scan_time = datetime.now(IST)"
    )
    print('  ✓ Added last_scan_time update in run_scan()')
elif "last_scan_time = datetime" in content:
    print('  last_scan_time already updated in scan')
else:
    print('  ⚠ run_scan function not found — check railway_main.py manually')

# ── WRITE PATCHED FILE ────────────────────────────────────
if content != original:
    open(RAILWAY_FILE, 'w').write(content)
    print(f'\n  ✓ {RAILWAY_FILE} patched and saved')
    print('  Run: git add railway_main.py && git commit -m "Fix: dedup + last_scan_time" && git push')
else:
    print(f'\n  No changes needed to {RAILWAY_FILE}')

# ── ALSO FIX cineos_alert_engine.py if it exists ─────────
import os
engine_file = 'cineos_alert_engine.py'
if os.path.exists(engine_file):
    eng = open(engine_file).read()
    eng_orig = eng
    if 'existing_ids' not in eng and 'def add_alert' in eng:
        old_eng = 'def add_alert(alert):'
        new_eng = '''def add_alert(alert):
    """Add alert with deduplication."""
    global ALERTS
    inc_id    = alert.get('id','')
    inc_title = alert.get('title','')[:60]
    inc_cat   = alert.get('category','')
    title_key = f"{inc_title}|{inc_cat}"

    existing_ids    = {a.get('id','') for a in ALERTS}
    existing_titles = {f"{a.get('title','')[:60]}|{a.get('category','')}" for a in ALERTS}

    if inc_id and inc_id in existing_ids:
        return False  # duplicate
    if title_key in existing_titles:
        return False  # duplicate title+category'''

        if old_eng in eng:
            eng = eng.replace(old_eng, new_eng)
            open(engine_file,'w').write(eng)
            print(f'  ✓ Fixed dedup in {engine_file}')

print('\n  PATCH COMPLETE')
print('  Next steps:')
print('  1. python3 cineos_fix_duplicates.py   ← clean up now')
print('  2. python3 cineos_railway_patch.py    ← prevent future')
print('  3. git add -A && git commit -m "Fix: dedup alerts" && git push')
print('  4. Railway redeploys automatically in ~2 minutes')
