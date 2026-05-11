#!/bin/bash
# CINEOS Railway API keepalive
# Pings the Railway API every 10 minutes to prevent cold start

API="https://cinerisk-api-production.up.railway.app"
LOG="/Users/yugandharmallavarapu/Desktop/cinerisk/logs/keepalive.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Keepalive ping..." >> "$LOG"

response=$(curl -s -o /dev/null -w "%{http_code}" \
  --max-time 10 \
  "$API/health" 2>/dev/null)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Response: $response" >> "$LOG"

# Sleep 10 minutes then exit (LaunchD KeepAlive will restart)
sleep 600
