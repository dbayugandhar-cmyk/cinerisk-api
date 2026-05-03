import cv2
import numpy as np
import time
import datetime

import urllib.request
import json as _json

SUPABASE_URL = "https://fuaybehxfusfywghuxwp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1YXliZWh4ZnVzZnl3Z2h1eHdwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDM1NDcwODEsImV4cCI6MjA1OTEyMzA4MX0.mbYxdL8NilgZOT4_vyWGK73h64UVxqCpT5SEzO3Kcks"

def log_to_supabase(reason):
    try:
        incident = {
            "theater": "Demo Theater",
            "screen": "Screen 1",
            "seat": "Unknown",
            "detection_type": reason,
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }
        data = _json.dumps(incident).encode()
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
        urllib.request.urlopen(req)
        print(f"  -> Logged to Supabase: {reason}")
    except Exception as e:
        print(f"  -> Supabase error: {e}")

MIN_AREA = 6000
ALERT_COOLDOWN = 60
last_alert_time = 0

def detect_phone(frame, gray):
    # Method 1: shape/edge detection (works for bright screens)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 20, 80)
    dilated = cv2.dilate(edges, np.ones((3,3), np.uint8), iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    frame_area = frame.shape[0] * frame.shape[1]
    best_box = None
    
    for c in contours:
        area = cv2.contourArea(c)
        if area < MIN_AREA or area > frame_area * 0.75:
            continue
        rect = cv2.minAreaRect(c)
        w, h = rect[1]
        if w == 0 or h == 0:
            continue
        aspect = max(w, h) / min(w, h)
        if not (1.4 <= aspect <= 2.8):  # phone portrait/landscape ratio
            continue
        hull = cv2.convexHull(c)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0
        if solidity > 0.65:
            best_box = np.intp(cv2.boxPoints(rect))

    # Method 2: circle detection for camera lenses (works for dark back of phone)
    circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, 1, 20,
                                param1=50, param2=25, minRadius=8, maxRadius=35)
    camera_detected = False
    if circles is not None:
        circles = np.uint16(np.around(circles))
        # If we see 2-4 circles close together = camera module
        pts = [(c[0], c[1]) for c in circles[0]]
        for i, p1 in enumerate(pts):
            nearby = [p2 for j, p2 in enumerate(pts) if i != j and
                      abs(p1[0]-p2[0]) < 80 and abs(p1[1]-p2[1]) < 80]
            if len(nearby) >= 1:
                camera_detected = True
                for c in circles[0]:
                    cv2.circle(frame, (c[0], c[1]), c[2], (0, 165, 255), 2)

    return best_box, camera_detected

cap = cv2.VideoCapture(0)
time.sleep(2)

print("CINEMA PIRACY DETECTOR — multi-mode detection")
print("Detects front screen AND back camera module")
print("Press Q to quit\n")

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    box, camera_detected = detect_phone(frame, gray)

    phone_detected = box is not None or camera_detected

    if box is not None:
        cv2.drawContours(frame, [box], 0, (0, 0, 255), 2)

    now = time.time()
    if phone_detected:
        reason = "SCREEN" if box is not None else ""
        if camera_detected:
            reason += ("+CAMERA" if reason else "CAMERA")
        status = f"PHONE DETECTED [{reason}] - RECORDING ALERT"
        color = (0, 0, 255)
        if now - last_alert_time > ALERT_COOLDOWN:
            last_alert_time = now
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] ALERT fired — detected via: {reason}")
            log_to_supabase(reason)
    else:
        status = "MONITORING - CLEAR"
        color = (0, 255, 0)

    cv2.putText(frame, status, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.imshow("Cinema Piracy Detector", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
