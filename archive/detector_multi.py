import cv2
import numpy as np
import time
import datetime
import urllib.request
import json
import ssl
import os
from ultralytics import YOLO

SUPABASE_URL = "https://fuaybehxfusfywghuxwp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1YXliZWh4ZnVzZnl3Z2h1eHdwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcxNTIzNDgsImV4cCI6MjA5MjcyODM0OH0.mbYxdL8NilgZOT4_vyWGK73h64UVxqCpT5SEzO3Kcks"

TARGET_CLASSES = { 67: "PHONE", 72: "CAMCORDER", 73: "CAMCORDER" }
PER_TARGET_COOLDOWN = 60
zone_last_alert = {"LEFT": 0, "CENTER": 0, "RIGHT": 0}
total_incidents = 0
device_counter = 0
session_start = datetime.datetime.now()
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# Colors (BGR)
RED     = (0, 0, 255)
GREEN   = (0, 255, 136)
AMBER   = (0, 149, 255)
WHITE   = (255, 255, 255)
BLACK   = (0, 0, 0)
DARK    = (12, 12, 18)
GRAY    = (80, 80, 90)

def get_zone(cx, fw):
    if cx < fw // 3: return "LEFT"
    elif cx < 2 * fw // 3: return "CENTER"
    else: return "RIGHT"

def play_alert():
    os.system("afplay /System/Library/Sounds/Sosumi.aiff &")

def log_to_supabase(reason, zone):
    global total_incidents, device_counter
    try:
        device_counter += 1
        incident = {
            "theater_name": "Demo Theater",
            "screen_number": "Screen 1",
            "seat_location": "Row F, Seat 14",
            "detection_type": reason,
            "detected_at": datetime.datetime.now().isoformat()
        }
        data = json.dumps(incident).encode()
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/incidents",
            data=data,
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Prefer": "return=minimal"
            },
            method="POST"
        )
        urllib.request.urlopen(req, context=ssl_ctx)
        total_incidents += 1
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] ALERT - {reason} at Row F Seat 14 — logged to database")
        play_alert()
    except Exception as e:
        print(f"  -> Supabase error: {e}")

def draw_ui(frame, detections, fw, fh):
    # Dark top bar
    cv2.rectangle(frame, (0, 0), (fw, 56), DARK, -1)
    cv2.rectangle(frame, (0, 56), (fw, 57), (30, 30, 40), -1)

    # Status
    count = len(detections)
    if count == 0:
        status = "MONITORING — CLEAR"
        status_color = GREEN
    elif count == 1:
        status = f"ALERT - {count} DEVICE DETECTED"
        status_color = RED
    else:
        status = f"ALERT - {count} DEVICES DETECTED"
        status_color = RED

    cv2.putText(frame, status, (16, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, status_color, 2)

    # Clock top right
    clock = datetime.datetime.now().strftime("%H:%M:%S")
    cv2.putText(frame, clock, (fw - 100, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, GRAY, 1)

    # Patent bottom left
    cv2.rectangle(frame, (0, fh - 28), (fw, fh), DARK, -1)
    cv2.putText(frame, "US Prov. Pat. 64/049,190  |  Cinema Piracy Solution",
                (12, fh - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.38, GRAY, 1)

    # Incident counter bottom right
    cv2.putText(frame, f"Session incidents: {total_incidents}",
                (fw - 200, fh - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.38, GRAY, 1)

    # Zone dividers
    cv2.line(frame, (fw//3, 57), (fw//3, fh-28), (25, 25, 35), 1)
    cv2.line(frame, (2*fw//3, 57), (2*fw//3, fh-28), (25, 25, 35), 1)

    # Zone labels
    for z, x in [("LEFT", fw//6), ("CENTER", fw//2), ("RIGHT", 5*fw//6)]:
        cv2.putText(frame, z, (x - 20, fh - 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, GRAY, 1)

    # Each detection box
    for (x1, y1, x2, y2, cx, cy, label, conf) in detections:
        is_cam = "CAM" in label
        box_color = AMBER if is_cam else RED
        conf_pct = int(conf * 100)

        # Clean bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

        # Corner accents
        corner = 12
        cv2.line(frame, (x1, y1), (x1 + corner, y1), box_color, 3)
        cv2.line(frame, (x1, y1), (x1, y1 + corner), box_color, 3)
        cv2.line(frame, (x2, y1), (x2 - corner, y1), box_color, 3)
        cv2.line(frame, (x2, y1), (x2, y1 + corner), box_color, 3)
        cv2.line(frame, (x1, y2), (x1 + corner, y2), box_color, 3)
        cv2.line(frame, (x1, y2), (x1, y2 - corner), box_color, 3)
        cv2.line(frame, (x2, y2), (x2 - corner, y2), box_color, 3)
        cv2.line(frame, (x2, y2), (x2, y2 - corner), box_color, 3)

        # Label background
        label_text = f"{label}  {conf_pct}%"
        (lw, lh), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(frame, (x1, y1 - lh - 12), (x1 + lw + 12, y1), DARK, -1)
        cv2.rectangle(frame, (x1, y1 - lh - 12), (x1 + lw + 12, y1), box_color, 1)
        cv2.putText(frame, label_text, (x1 + 6, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, box_color, 2)

        # Seat location tag
        zone = get_zone(cx, fw)
        seat_tag = f"Row F  Seat 14  |  {zone}"
        cv2.putText(frame, seat_tag, (x1 + 4, y2 + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, WHITE, 1)

    return frame

print("Loading YOLO model...")
model = YOLO("yolo11n.pt")
print("Model ready — Cinema Piracy Detector starting...\n")

cap = cv2.VideoCapture(0)
time.sleep(2)

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    fh, fw = frame.shape[:2]
    results = model(frame, verbose=False, conf=0.50)
    now = time.time()
    detections = []

    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            if cls_id not in TARGET_CLASSES:
                continue
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            # Angle detection
            pw = x2 - x1
            ph = y2 - y1
            aspect = pw / ph if ph > 0 else 1
            cy_norm = cy / fh
            if aspect > 0.7 or cy_norm < 0.80:
                label = TARGET_CLASSES[cls_id]
                posture = "LANDSCAPE" if aspect > 0.7 else "PORTRAIT"
                detections.append((x1, y1, x2, y2, cx, cy, label, conf))

    # Fire alerts
    for (x1, y1, x2, y2, cx, cy, label, conf) in detections:
        zone = get_zone(cx, fw)
        if now - zone_last_alert[zone] > PER_TARGET_COOLDOWN:
            zone_last_alert[zone] = now
            log_to_supabase(label, zone)

    frame = draw_ui(frame, detections, fw, fh)
    cv2.imshow("Cinema Piracy Detector", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print(f"\nSession ended — Total incidents logged: {total_incidents}")
