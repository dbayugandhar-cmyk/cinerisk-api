"""
CINEOS Railway Scheduler Patch
Updates Railway to scan every 2 hours aggressively.
Run: python3 cineos_railway_scheduler_patch.py
Then: git add railway_main.py && git commit && git push
"""

FILE = 'railway_main.py'
content = open(FILE).read()

# ── EXPAND SCAN HOURS ─────────────────────────────────────
old_hours = 'SCAN_HOURS_IST = {8, 12, 18, 22}'
new_hours = 'SCAN_HOURS_IST = {6, 8, 10, 12, 14, 16, 18, 20, 22}'

if old_hours in content:
    content = content.replace(old_hours, new_hours)
    print('Expanded scan hours: 4/day → 9/day')
elif new_hours in content:
    print('Scan hours already expanded')
else:
    # Find whatever format it uses
    import re
    m = re.search(r'SCAN_HOURS_IST\s*=\s*\{[^}]+\}', content)
    if m:
        content = content.replace(m.group(), new_hours)
        print(f'Replaced: {m.group()} → {new_hours}')
    else:
        print('Could not find SCAN_HOURS_IST — check railway_main.py')

# ── ADD AGGRESSIVE SCAN QUERIES ───────────────────────────
# Find the SerpAPI query list and expand it
old_queries_marker = "# SerpAPI queries for fraud detection"

expanded_queries = '''
# ── AGGRESSIVE MULTI-CATEGORY QUERY SET ──────────────────
SCAN_QUERIES = {
    'piracy': [
        'IPL 2026 live stream free Telegram illegal',
        'hotstar free stream Telegram channel India',
        'OTT piracy India Telegram movie download 2026',
        'JioHotstar piracy India stream free',
    ],
    'illegal_betting': [
        'site:t.me satta matka betting India 2026',
        'Mahadev Book Reddy Anna cricket betting Telegram',
        'online cricket id betbhai9 laser247 Telegram India',
        'IPL toss prediction sure shot Telegram India 2026',
        'satta king faridabad ghaziabad result Telegram',
    ],
    'colour_prediction': [
        '91club OKWIN Jalwa BDG Win Telegram India 2026',
        'colour prediction game Telegram India earn withdraw',
        'Daman game Tiranga lottery Telegram India 2026',
        'wingo bdg colour trading Telegram India 2026',
    ],
    'crypto_fraud': [
        'crypto investment fraud India Telegram arrested 2026',
        'fake crypto platform India ED PMLA chargesheet 2026',
        'pig butchering WhatsApp Telegram India 2026',
        'Bitcoin USDT fraud India Telegram arrested',
    ],
    'ai_scam': [
        'digital arrest scam India AI voice 2026',
        'deepfake fraud India WhatsApp Telegram 2026',
        'AI voice clone fraud CBI ED impersonation India',
        'fake official call India digital arrest MHA',
    ],
    'investment_fraud': [
        'SEBI unregistered advisor Telegram India 2026',
        'stock tips guaranteed profit Telegram India fraud',
        'fake IPO subscription Telegram India fraud arrested',
        'option trading fraud India Telegram profit guarantee',
    ],
    'upi_mule': [
        'bank account kit sell India Telegram earn 2026',
        'UPI mule arrested India cybercrime 2026',
        'money mule India Telegram bank account fraud',
        'sim card bank kit Telegram India earn commission',
    ],
    'enforcement_news': [
        'cybercrime arrested India Telegram fraud crore 2026',
        'ED crypto fraud India PMLA chargesheet 2026',
        'SEBI action unregistered advisor India crore 2026',
        'I4C cybercrime India Telegram arrested today 2026',
        'CERT-In advisory phishing India 2026',
    ],
}
'''

if 'SCAN_QUERIES' not in content:
    # Insert after imports
    insert_after = 'from flask_cors import CORS'
    if insert_after in content:
        content = content.replace(
            insert_after,
            insert_after + '\n' + expanded_queries
        )
        print('Added SCAN_QUERIES dict')
    else:
        print('Could not insert SCAN_QUERIES — adding at top of scheduler')

# ── WRITE AND VERIFY ──────────────────────────────────────
open(FILE, 'w').write(content)
print(f'Written: {len(content):,} bytes')

import subprocess
r = subprocess.run(['python3', '-m', 'py_compile', FILE], capture_output=True, text=True)
if r.returncode == 0:
    print('SYNTAX OK — safe to push')
else:
    print(f'SYNTAX ERROR: {r.stderr}')
    # Restore
    print('Check railway_main.py manually')
