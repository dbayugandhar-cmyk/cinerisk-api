"""
CINEOS Railway API keepalive.
Runs via LaunchD — Python has Desktop access, bash does not.
"""
import urllib.request, time, os
from datetime import datetime

API  = "https://cinerisk-api-production.up.railway.app"
LOG  = "/Users/yugandharmallavarapu/Desktop/cinerisk/logs/keepalive.log"

def log(msg):
    with open(LOG, 'a') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    print(msg)

try:
    req  = urllib.request.urlopen(f"{API}/health", timeout=10)
    code = req.getcode()
    log(f"Ping OK — status {code}")
except Exception as e:
    log(f"Ping failed — {e}")

# Sleep 10 min then exit (LaunchD KeepAlive restarts)
time.sleep(600)
