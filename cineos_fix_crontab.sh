#!/bin/bash
# CINEOS Crontab Fix
# Removes duplicate 9am cineos_update_internal entries
# Shows clean crontab after fix

echo "========================================"
echo "  CINEOS CRONTAB FIX"
echo "========================================"

echo ""
echo "[BEFORE] Current crontab:"
crontab -l 2>/dev/null | cat -n

echo ""
echo "Fixing duplicates..."

# Remove all entries and rebuild cleanly
crontab -l 2>/dev/null > /tmp/cron_backup.txt
echo "Backup saved: /tmp/cron_backup.txt"

# Write clean crontab — one entry per job, no duplicates
PYTHON="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
DIR="cd ~/Desktop/cinerisk &&"
LOG=">> ~/Desktop/cinerisk/logs"

cat > /tmp/cron_clean.txt << 'CRONEOF'
# CINEOS Automation — clean crontab (no duplicates)
# Updated: auto-fix script

# Weekly report — Mondays 8am
0 8 * * 1 cd ~/Desktop/cinerisk && /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 cineos_weekly_report.py >> ~/Desktop/cinerisk/logs/weekly.log 2>&1

# Daily digest email — 8am every day
0 8 * * * cd ~/Desktop/cinerisk && export GMAIL_APP_PASSWORD='xoxv akwr ufhd rlfl' && /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 cineos_automation.py --mode digest >> ~/Desktop/cinerisk/logs/digest.log 2>&1

# Blindspot fixes — 8:30am daily
30 8 * * * cd ~/Desktop/cinerisk && /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 cineos_blindspot_fixes.py >> ~/Desktop/cinerisk/logs/blindspot.log 2>&1

# Channel discovery — 9am daily
0 9 * * * cd ~/Desktop/cinerisk && /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 cineos_channel_discovery.py >> ~/Desktop/cinerisk/logs/discovery.log 2>&1

# Today updater (cineos_today.html + git push) — 9:05am daily
5 9 * * * cd ~/Desktop/cinerisk && /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 cineos_update_internal.py >> ~/Desktop/cinerisk/logs/today_updater.log 2>&1

# Multilingual scanner — 10am daily
0 10 * * * cd ~/Desktop/cinerisk && TELEGRAM_API_ID=38636931 TELEGRAM_API_HASH=852280f65386a00114ff7453eac7849b SERP_API_KEY=2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1 /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 cineos_multilingual_scanner.py >> ~/Desktop/cinerisk/logs/multilingual.log 2>&1

CRONEOF

# Install clean crontab
crontab /tmp/cron_clean.txt

echo ""
echo "[AFTER] Clean crontab:"
crontab -l | grep -v '^#' | grep -v '^$' | cat -n

echo ""
echo "Jobs active: $(crontab -l | grep -v '^#' | grep -v '^$' | wc -l | tr -d ' ')"

# Make sure logs directory exists
mkdir -p ~/Desktop/cinerisk/logs
echo "Logs directory: ~/Desktop/cinerisk/logs ✓"

echo ""
echo "========================================"
echo "  CRONTAB FIXED"
echo "========================================"
