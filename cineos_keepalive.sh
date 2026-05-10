#!/bin/bash
# Ping Railway every 10 minutes to prevent sleep
# Run in background: bash cineos_keepalive.sh &
while true; do
  curl -s https://cinerisk-api-production.up.railway.app/v1/health > /dev/null 2>&1
  sleep 600
done
