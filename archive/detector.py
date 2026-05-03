import cv2
import numpy as np
from datetime import datetime
import json
import os

INCIDENT_LOG = os.path.expanduser("~/incidents.json")

def log_incident(confidence, bbox):
    incidents = []
    if os.path.exists(INCIDENT_LOG):
        with open(INCIDENT_LOG, 'r') as f:
            incidents = json.load(f)
    incident = {
        "id": len(incidents) + 1,
        "timestamp": datetime.now().isoformat(),
        "confidence": round(confidence, 2),
        "location": f"x:{bbox[0]}, y:{bbox[1]}",
        "status": "detected",
        "theater": "Demo Theater",
        "screen": "Screen 1"
    }
    incidents.append(incident)
    with open(INCIDENT_LOG, 'w') as f:
        json.dump(incidents, f, indent=2)
    print(f"INCIDENT LOGGED: {incident['timestamp']} | Confidence: {confidence:.0%}")
    return incident

def detect_phone_screen(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)
    threshold = max(180, mean_brightness + 60)
    _, bright_mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detections = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 800:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / h if h > 0 else 0
        if 0.4 <= aspect_ratio <= 2.5:
            confidence = 0.0
            frame_area = frame.shape[0] * frame.shape[1]
            size_ratio = area / frame_area
            if 0.01 <= size_ratio <= 0.3:
                confidence += 0.35
            roi = gray[y:y+h, x:x+w]
            roi_brightness = np.mean(roi)
            contrast = roi_brightness - mean_brightness
            if contrast > 40:
                confidence += 0.35
            rect_area = w * h
            fill_ratio = area / rect_area if rect_area > 0 else 0
            if fill_ratio > 0.6:
                confidence += 0.30
            if confidence >= 0.65:
                detections.append({'bbox': (x, y, w, h), 'confidence': confidence})
    return detections

def main():
    print("CINEMA PIRACY SOLUTION - AI Detector")
    print("US Provisional Patent App. 64/049,190")
    print("Press Q to quit | Press D to toggle dark mode")
    print("Test: hold your phone screen up to camera in a dim room")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open camera")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    alert_cooldown = 0
    total_incidents = 0
    dark_mode = False
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if dark_mode:
            frame = cv2.convertScaleAbs(frame, alpha=0.4, beta=0)
        detections = detect_phone_screen(frame)
        for detection in detections:
            x, y, w, h = detection['bbox']
            confidence = detection['confidence']
            color = (0, 0, 255) if confidence >= 0.85 else (0, 165, 255)
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            label = f"RECORDING DETECTED {confidence:.0%}"
            cv2.rectangle(frame, (x, y-30), (x+len(label)*10, y), color, -1)
            cv2.putText(frame, label, (x+5, y-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
            if alert_cooldown <= 0:
                log_incident(confidence, detection['bbox'])
                total_incidents += 1
                alert_cooldown = 30
        if alert_cooldown > 0:
            alert_cooldown -= 1
        fh, fw = frame.shape[:2]
        status_color = (0, 0, 255) if detections else (0, 200, 0)
        status_text = f"ALERT: {len(detections)} RECORDING(S) DETECTED" if detections else "MONITORING - NO THREATS DETECTED"
        cv2.rectangle(frame, (0, 0), (fw, 40), (0, 0, 0), -1)
        cv2.putText(frame, status_text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        cv2.rectangle(frame, (0, fh-50), (fw, fh), (0, 0, 0), -1)
        cv2.putText(frame, f"Cinema Piracy Solution | Incidents: {total_incidents} | {datetime.now().strftime('%H:%M:%S')}", (10, fh-15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 1)
        cv2.putText(frame, "US Prov. App. 64/049,190 | cinemapiracysolution.com", (10, fh-35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100,100,100), 1)
        cv2.imshow('Cinema Piracy Solution - AI Detector', frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('d'):
            dark_mode = not dark_mode
            print(f"Dark mode: {'ON' if dark_mode else 'OFF'}")
    cap.release()
    cv2.destroyAllWindows()
    print(f"Session complete. Total incidents: {total_incidents}")

if __name__ == "__main__":
    main()
