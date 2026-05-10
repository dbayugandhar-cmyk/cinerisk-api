#!/bin/bash
# Run this ONCE on Railway to set up the cron job
# Railway cron docs: https://docs.railway.app/reference/cron-jobs

echo "Add this to your Railway service settings:"
echo ""
echo "SERVICE NAME: cineos-daily-scanner"
echo "CRON SCHEDULE: 0 2 * * *"
echo "  (2:30 UTC = 8:00 AM IST every day)"
echo ""
echo "COMMAND: python3 cineos_daily_scanner.py"
echo ""
echo "ENV VARS already set in Railway:"
echo "  SERP_API_KEY"
echo "  GMAIL_APP_PASSWORD"
