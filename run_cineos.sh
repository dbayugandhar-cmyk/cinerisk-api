#!/bin/bash
# CINEOS Full Pipeline — L1 threat intel → L2 detector → L4 scan
# Usage: ./run_cineos.sh
# Usage: ./run_cineos.sh "Mortal Kombat II" "AMC 12" "Screen 4"

cd "$(dirname "$0")"

export TMDB_API_KEY="28ff1ef4ae81f137ddd9cbeec2634033"
export DATABASE_URL="${DATABASE_URL}"
export CINEOS_API="https://cinerisk-api-production.up.railway.app"
export CONFIDENCE_THRESHOLD="0.35"
export DURATION_THRESHOLD="3"

# Args override env
FILM="${1:-}"
THEATER="${2:-Test Theater}"
SCREEN="${3:-Screen 1}"

echo "================================================="
echo "  CINEOS FULL PIPELINE"
echo "  $(date)"
echo "================================================="

# Step 1 — Layer 1: run threat intel, pick top CRITICAL film
if [ -z "$FILM" ]; then
    echo ""
    echo "[L1] Running threat intelligence..."
    python3 layer1_pipeline.py 2>&1 | grep -E "CTI|CRITICAL|HIGH|Error|Saved"
    echo ""
    # Read top CRITICAL film from saved index
    FILM=$(python3 -c "
import json, sys
try:
    data = json.load(open('cineos_threat_index.json'))
    top = next((f for f in data['films'] if f['cti_level']=='CRITICAL'), data['films'][0])
    print(top['title'])
except Exception as e:
    print('Mortal Kombat II')
")
    echo "[L1] Top threat: $FILM"
fi

echo ""
echo "[L2] Starting detector"
echo "     Theater : $THEATER"
echo "     Screen  : $SCREEN"
echo "     Film    : $FILM"
echo "     Camera  : webcam 0"
echo ""
echo "     Keys: Q=quit  R=reset timer  T=dark mode toggle"
echo "================================================="
echo ""

# Step 2 — Layer 2: run detector with top film
THEATER_NAME="$THEATER" \
FILM_TITLE="$FILM" \
SCREEN_NUMBER="$SCREEN" \
python3 theater/detector_rtsp.py 0

# Start Layer 4 background worker in background
echo "[L4] Starting background scanner..."
DATABASE_URL="${DATABASE_URL}" \
TMDB_API_KEY="28ff1ef4ae81f137ddd9cbeec2634033" \
python3 cineos_layer4_worker.py --no-api > /tmp/cineos_l4.log 2>&1 &
echo "[L4] Worker PID: $! — logs at /tmp/cineos_l4.log"
