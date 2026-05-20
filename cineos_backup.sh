#!/bin/bash
# CINEOS Complete Backup
# Run: bash cineos_backup.sh
# Creates encrypted backup of everything critical

BACKUP_DIR="$HOME/Desktop/CINEOS_BACKUP_$(date +%Y%m%d_%H%M)"
mkdir -p "$BACKUP_DIR"

echo "CINEOS BACKUP — $(date)"
echo "================================"

# 1. Telegram session (most critical)
cp ~/Desktop/cinerisk/cineos_session.session "$BACKUP_DIR/" 2>/dev/null && \
    echo "✓ Telegram session" || echo "✗ Session not found"

# 2. Channel database
cp ~/Desktop/cinerisk/reports/all_channels.json "$BACKUP_DIR/" && \
    echo "✓ All channels ($(python3 -c "import json; print(len(json.load(open('$HOME/Desktop/cinerisk/reports/all_channels.json'))))" ) channels)" || echo "✗ Channels not found"

# 3. Local alerts
cp ~/Desktop/cinerisk/reports/alerts/live_alerts.json "$BACKUP_DIR/" && \
    echo "✓ Live alerts" || echo "✗ Alerts not found"

# 4. All Python scripts not on GitHub
cp ~/Desktop/cinerisk/*.py "$BACKUP_DIR/"
echo "✓ All Python scripts"

# 5. Crontab
crontab -l > "$BACKUP_DIR/crontab_backup.txt" && \
    echo "✓ Crontab saved"

# 6. Environment variables and keys
cat > "$BACKUP_DIR/CREDENTIALS.txt" << 'CREDS'
# CINEOS Critical Credentials
# KEEP THIS FILE SECURE — DO NOT SHARE

Telegram API:
  API_ID:   38636931
  API_HASH: 852280f65386a00114ff7453eac7849b
  Username: yugan66
  Session:  cineos_session.session (in this backup)

SerpAPI:
  Key: 2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1
  Remaining: ~16,000 searches

Supabase:
  URL: https://pgvbnwiflefhunkbbwah.supabase.co
  Key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBndmJud2lmbGVmaHVua2Jid2FoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkyMDYyMTYsImV4cCI6MjA5NDc4MjIxNn0.sO2B6lEW9b36hLy3Z3GzsaGeVA6-y0L7XJLGvNVkAvQ

Railway:
  URL: https://cinerisk-api-production.up.railway.app
  API Key: cineos_internal_2026
  Deploy: auto from GitHub on push

GitHub:
  Repo: https://github.com/dbayugandhar-cmyk/cinerisk-api
  Token: YOUR_GITHUB_TOKEN_HERE

GitHub (read for Railway):
  Token: YOUR_GITHUB_TOKEN_HERE
CREDS
echo "✓ Credentials file saved"

# 7. Create zip
cd "$HOME/Desktop"
zip -r "CINEOS_BACKUP_$(date +%Y%m%d).zip" "CINEOS_BACKUP_$(date +%Y%m%d_%H%M)/" -x "*.pyc" 2>/dev/null
echo "✓ Zip created: CINEOS_BACKUP_$(date +%Y%m%d).zip"

echo "================================"
echo "Backup complete: $BACKUP_DIR"
echo "IMPORTANT: Copy zip to Google Drive or external drive"
echo "================================"
