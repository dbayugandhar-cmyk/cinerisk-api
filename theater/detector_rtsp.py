import cv2
import asyncio
import httpx
import os
import sys
import time
from datetime import datetime, timezone
from ultralytics import YOLO

API = os.getenv("CINEOS_API", "https://cinerisk-api-production.up.railway.app")
THEATER = os.getenv("THEATER_NAME", "Demo Theater")
FILM = os.getenv("FILM_TITLE", "Unknown")
SCREEN = os.getenv("SCREEN_NUMBER", "Screen 1")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))
DURATION_THRESHOLD = int(os.getenv("DURATION_THRESHOLD", "3"))  # seconds

model = YOLO("yolov8n.pt")

# Track detections per zone to filter false positives
zone_timers = {"LEFT": 0, "CENTER": 0, "RIGHT": 0}
last_reported = {"LEFT": 0, "CENTER": 0, "RIGHT": 0}
COOLDOWN = 300  # 5 min between reports per zone

def get_zone(x_center, frame_width):
    third = frame_width / 3
    if x_center < third:
        return "LEFT"
    elif x_center < third * 2:
        return "CENTER"
    return "RIGHT"

async def report_incident(zone, confidence):
    now = time.time()
    if now - last_reported[zone] < COOLDOWN:
        return
    last_reported[zone] = now
    payload = {
        "theater_name": THEATER,
        "screen_number": SCREEN,
        "zone": zone,
        "detection_type": "PHONE",
        "confidence": round(confidence, 3),
        "film_title": FILM,
        "device_id": f"cineos-rtsp-{SCREEN.replace(' ','-').lower()}-{int(now)}",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{API}/theater/incident",
                headers={"Content-Type": "application/json"},
                json=payload)
            print(f"[CINEOS] Reported {zone} zone — {r.status_code}")
    except Exception as e:
        print(f"[CINEOS] Report failed: {e}")

def run_detector(stream_url: str):
    print(f"[CINEOS] Connecting to: {stream_url}")
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print("[CINEOS] ERROR: Cannot open stream")
        sys.exit(1)

    print(f"[CINEOS] Stream open — monitoring {THEATER} {SCREEN} for {FILM}")
    loop = asyncio.new_event_loop()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[CINEOS] Stream lost — reconnecting in 5s")
            time.sleep(5)
            cap = cv2.VideoCapture(stream_url)
            continue

        h, w = frame.shape[:2]
        results = model(frame, classes=[67], verbose=False)  # class 67 = cell phone
        total_boxes = sum(len(r.boxes) for r in results)
        if total_boxes > 0: print(f"[DEBUG] {total_boxes} detection(s) this frame")

        detected_zones = set()
        for result in results:
            for box in result.boxes:
                conf = float(box.conf[0])
                if conf < CONFIDENCE_THRESHOLD:
                    continue
                x1, y1, x2, y2 = box.xyxy[0]
                x_center = (x1 + x2) / 2
                zone = get_zone(x_center, w)
                detected_zones.add(zone)
                zone_timers[zone] = zone_timers.get(zone, 0) + 1
                print(f"[TIMER] {zone} = {zone_timers[zone]}")
                if zone_timers[zone] >= 5:
                    print(f"[CINEOS] ALERT {zone} zone — conf {conf:.2f} — {FILM}")
                    loop.run_until_complete(report_incident(zone, conf))
                    zone_timers[zone] = 0

        # Decay timers for zones not detected this frame
        for z in list(zone_timers.keys()):
            if z not in detected_zones:
                zone_timers[z] = max(0, zone_timers[z] - 1)

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "0"
    stream = int(arg) if arg.isdigit() else arg
    run_detector(stream)
