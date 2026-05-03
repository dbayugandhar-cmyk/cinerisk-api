import cv2
import numpy as np
from datetime import datetime
import json
import os

try:
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    import mediapipe as mp
    NEW_MEDIAPIPE = True
except:
    NEW_MEDIAPIPE = False

INCIDENT_LOG = os.path.expanduser("~/incidents_v2.json")

def log_incident(confidence, reason, bbox):
    incidents = []
    if os.path.exists(INCIDENT_LOG):
        with open(INCIDENT_LOG, 'r') as f:
            incidents = json.load(f)
    incident = {
        "id": len(incidents) + 1,
        "timestamp": datetime.now().isoformat(),
        "confidence": round(confidence, 2),
        "reason": reason,
        "location": f"x:{bbox[0]}, y:{bbox[1]}",
        "status": "detected",
        "theater": "Demo Theater",
        "screen": "Screen 1"
    }
    incidents.append(incident)
    with open(INCIDENT_LOG, 'w') as f:
        json.dump(incidents, f, indent=2)
    print(f"INCIDENT LOGGED | {reason} | Confidence: {confidence:.0%} | {incident['timestamp']}")
    return incident

def detect_phone_screen(frame, mean_brightness):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
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
                detections.append({
                    'bbox': (x, y, w, h),
                    'confidence': confidence,
                    'reason': 'Bright screen detected'
                })
    return detections

def detect_hand_posture(frame):
    """Detect hand holding phone using contour and skin color analysis"""
    detections = []
    
    # Convert to HSV for skin detection
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Skin color range in HSV
    lower_skin = np.array([0, 20, 70], dtype=np.uint8)
    upper_skin = np.array([20, 255, 255], dtype=np.uint8)
    skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
    
    # Also include slightly darker skin tones
    lower_skin2 = np.array([170, 20, 70], dtype=np.uint8)
    upper_skin2 = np.array([180, 255, 255], dtype=np.uint8)
    skin_mask2 = cv2.inRange(hsv, lower_skin2, upper_skin2)
    skin_mask = cv2.bitwise_or(skin_mask, skin_mask2)
    
    # Clean up mask
    kernel = np.ones((5,5), np.uint8)
    skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)
    skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)
    
    contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    fh, fw = frame.shape[:2]
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 2000:
            continue
            
        x, y, w, h = cv2.boundingRect(contour)
        
        confidence = 0.0
        reason_parts = []
        
        # Hand in upper half of frame = raised toward screen
        if y < fh * 0.6:
            confidence += 0.35
            reason_parts.append("hand elevated")
        
        # Aspect ratio check — hand holding phone is taller than wide
        aspect = h / w if w > 0 else 0
        if 1.2 <= aspect <= 4.0:
            confidence += 0.35
            reason_parts.append("recording grip")
        
        # Size check
        size_ratio = area / (fw * fh)
        if 0.02 <= size_ratio <= 0.25:
            confidence += 0.30
            reason_parts.append("hand size match")
        
        if confidence >= 0.65:
            detections.append({
                'bbox': (x, y, w, h),
                'confidence': confidence,
                'reason': f"Hand posture: {', '.join(reason_parts)}"
            })
    
    return detections

def main():
    print("=" * 60)
    print("CINEMA PIRACY SOLUTION v2 - Smart AI Detector")
    print("US Provisional Patent App. 64/049,190")
    print("Detection: Screen brightness + Hand posture analysis")
    print("=" * 60)
    print("\nDetection modes:")
    print("  1. Bright screen detection (orange box)")
    print("  2. Hand posture detection (red box)")
    print("  3. Combined = HIGH CONFIDENCE alert")
    print("\nPress Q to quit | Press D to toggle dark mode\n")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open camera")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    alert_cooldown = 0
    total_incidents = 0
    dark_mode = False

    print("Camera active. Smart detection running...\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if dark_mode:
            frame = cv2.convertScaleAbs(frame, alpha=0.3, beta=0)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)

        screen_detections = detect_phone_screen(frame, mean_brightness)
        hand_detections = detect_hand_posture(frame)

        all_detections = []

        for det in screen_detections:
            x, y, w, h = det['bbox']
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 165, 255), 2)
            cv2.putText(frame, f"SCREEN {det['confidence']:.0%}",
                       (x, y-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,165,255), 2)
            all_detections.append(det)

        for det in hand_detections:
            x, y, w, h = det['bbox']
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
            cv2.putText(frame, f"HAND {det['confidence']:.0%}",
                       (x, y-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
            all_detections.append(det)

        fh, fw = frame.shape[:2]

        if screen_detections and hand_detections:
            combined = min(1.0, screen_detections[0]['confidence'] + hand_detections[0]['confidence'] * 0.5)
            cv2.rectangle(frame, (5, 50), (fw-5, 115), (0, 0, 150), -1)
            cv2.putText(frame, f"HIGH CONFIDENCE PIRACY DETECTED: {combined:.0%}",
                       (15, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255,255,255), 2)
            if alert_cooldown <= 0:
                log_incident(combined, "COMBINED: Screen + Hand posture", screen_detections[0]['bbox'])
                total_incidents += 1
                alert_cooldown = 45
        elif all_detections and alert_cooldown <= 0:
            best = max(all_detections, key=lambda x: x['confidence'])
            if best['confidence'] >= 0.70:
                log_incident(best['confidence'], best['reason'], best['bbox'])
                total_incidents += 1
                alert_cooldown = 30

        if alert_cooldown > 0:
            alert_cooldown -= 1

        has_detection = len(all_detections) > 0
        status_color = (0, 0, 255) if has_detection else (0, 200, 0)
        status_text = f"ALERT: {len(all_detections)} SIGNAL(S) DETECTED" if has_detection else "MONITORING - CLEAR"
        cv2.rectangle(frame, (0, 0), (fw, 45), (0,0,0), -1)
        cv2.putText(frame, status_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, status_color, 2)

        cv2.rectangle(frame, (0, fh-55), (fw, fh), (0,0,0), -1)
        cv2.putText(frame, f"Cinema Piracy Solution v2 | Incidents: {total_incidents} | {datetime.now().strftime('%H:%M:%S')}",
                   (10, fh-30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200,200,200), 1)
        cv2.putText(frame, "US Prov. App. 64/049,190 | cinemapiracysolution.com",
                   (10, fh-10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100,100,100), 1)

        cv2.imshow('Cinema Piracy Solution v2', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('d'):
            dark_mode = not dark_mode
            print(f"Dark mode: {'ON' if dark_mode else 'OFF'}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nSession complete. Total incidents: {total_incidents}")

if __name__ == "__main__":
    main()
