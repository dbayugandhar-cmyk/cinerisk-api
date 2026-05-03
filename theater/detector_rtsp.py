import cv2
try:
    from theater.pose_detector import PoseDetector
    POSE_AVAILABLE = True
except:
    try:
        from pose_detector import PoseDetector
        POSE_AVAILABLE = True
    except:
        POSE_AVAILABLE = False
        print("[DETECTOR] Pose detector not available")
import warnings
warnings.filterwarnings("ignore")
import asyncio
import httpx
import os
import sys
import time
from datetime import datetime, timezone
import torch
import numpy as np
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from session_tracker import update_session, get_active_sessions

API = os.getenv("CINEOS_API", "https://cinerisk-api-production.up.railway.app")
THEATER = os.getenv("THEATER_NAME", "Demo Theater")
FILM = os.getenv("FILM_TITLE", "Unknown")
SCREEN = os.getenv("SCREEN_NUMBER", "Screen 1")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))
DURATION_THRESHOLD = int(os.getenv("DURATION_THRESHOLD", "3"))  # seconds

model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True, verbose=False)
model.conf = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))
model.classes = [67]  # cell phone only

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

async def report_incident(zone, confidence, detection_type="PHONE"):
    now = time.time()
    if now - last_reported[zone] < COOLDOWN:
        return
    last_reported[zone] = now
    payload = {
        "theater_name": THEATER,
        "screen_number": SCREEN,
        "zone": zone,
        "detection_type": detection_type,
        "confidence": round(confidence, 3),
        "film_title": FILM,
        "device_id": f"cineos-rtsp-{SCREEN.replace(' ','-').lower()}-{int(now)}",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{API}/theater/incident",
                headers={"Content-Type": "application/json", "X-API-Key": os.getenv("CINEOS_API_KEY", "cineos-prod-2026-secure-key")},
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
        results = model(frame)  # YOLOv5 torch hub inference
        # Filter to cell phone class (67) above confidence threshold
        detections = results.xyxy[0]  # [x1,y1,x2,y2,conf,class]
        phone_dets = detections[(detections[:, 5] == 67) & (detections[:, 4] >= CONFIDENCE_THRESHOLD)] if len(detections) else detections

        # Pose detection — behavioral signal (catches camcorders too)
        if pose_detector:
            try:
                pose_alerts = pose_detector.process_frame(frame)
                for alert in pose_alerts:
                    print(f"[POSE] {alert.posture} | Zone:{alert.zone} | Conf:{alert.confidence:.0%}")
                    import asyncio
                    asyncio.run(report_incident(
                        alert.zone,
                        alert.confidence,
                        detection_type=alert.posture
                    ))
            except Exception as e:
                pass
        total_boxes = len(phone_dets)
        if total_boxes > 0: print(f"[DEBUG] {total_boxes} detection(s) this frame")

        detected_zones = set()
        for det in phone_dets:
            x1, y1, x2, y2, conf, cls = det.tolist()
            if True:  # already filtered above
                if True:
                    x_center = (x1 + x2) / 2
                zone = get_zone(x_center, w)
                detected_zones.add(zone)
                zone_timers[zone] = zone_timers.get(zone, 0) + 1
                print(f"[TIMER] {zone} = {zone_timers[zone]}")
                if zone_timers[zone] >= 5:
                    print(f"[CINEOS] ALERT {zone} zone — conf {conf:.2f} — {FILM}")
                    loop.run_until_complete(report_incident(zone, conf))
                    level, session = loop.run_until_complete(update_session(THEATER, SCREEN, FILM, zone, conf))
                    if level >= 2:
                        print(f"[CINEOS] Session count: {session['count']} — Escalation L{level}")
                    zone_timers[zone] = 0

        # Decay timers for zones not detected this frame
        for z in list(zone_timers.keys()):
            if z not in detected_zones:
                zone_timers[z] = max(0, zone_timers[z] - 1)

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "0"
    stream = int(arg) if arg.isdigit() else arg
    run_detector(stream)

