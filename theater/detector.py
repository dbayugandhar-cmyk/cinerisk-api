"""
CINEOS Detector v1
==================
YOLO v8 phone detection pipeline.
Fires POST /theater/incident to theater_api.py on each detection above threshold.

Usage:
  # Live camera
  python3 detector.py --theater "AMC Times Square" --screen "Screen 7" --film "Nova Station"

  # Video file (for testing)
  python3 detector.py --source test_video.mp4 --theater "Demo" --screen "Screen 1"

Requirements:
  pip install ultralytics opencv-python httpx python-dotenv
"""

import cv2, time, argparse, os, httpx
from datetime import datetime

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("WARNING: ultralytics not installed. Run: pip install ultralytics")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Config ────────────────────────────────────────────────────────────
THEATER_API    = os.getenv("THEATER_API", "http://localhost:8001")
CONFIDENCE_MIN = float(os.getenv("CONFIDENCE_MIN", "0.50"))
COOLDOWN_SECS  = int(os.getenv("COOLDOWN_SECS", "60"))

# YOLO class IDs — class 67 = "cell phone" in COCO dataset
PHONE_CLASS_ID = 67

# Zone boundaries (fraction of frame width)
ZONE_BOUNDS = {"LEFT": (0.0, 0.33), "CENTER": (0.33, 0.67), "RIGHT": (0.67, 1.0)}

def get_zone(x_center_norm: float) -> str:
    for zone, (lo, hi) in ZONE_BOUNDS.items():
        if lo <= x_center_norm < hi:
            return zone
    return "CENTER"

def log_incident(theater: str, screen: str, zone: str,
                 confidence: float, film: str = None,
                 seat: str = None) -> bool:
    """POST incident to theater_api.py."""
    payload = {
        "theater_name":   theater,
        "screen_number":  screen,
        "zone":           zone,
        "confidence":     round(confidence, 4),
        "detection_type": "PHONE",
        "film_title":     film,
        "seat_location":  seat,
        "alerted":        confidence >= 0.75,
    }
    try:
        r = httpx.post(f"{THEATER_API}/theater/incident", json=payload, timeout=4.0)
        if r.status_code in (200, 201):
            print(f"  [LOGGED] {zone} zone | conf={confidence:.2f} | {'ALERTED' if payload['alerted'] else 'logged'}")
            return True
        else:
            print(f"  [API ERROR] {r.status_code}: {r.text[:80]}")
            return False
    except Exception as e:
        print(f"  [LOG FAILED] {e}")
        return False

def run_detector(source, theater: str, screen: str, film: str = None):
    """Main detection loop."""
    if not YOLO_AVAILABLE:
        print("ERROR: Install ultralytics first: pip install ultralytics")
        return

    print(f"\nCINEOS Detector v1")
    print(f"  Theater: {theater} | Screen: {screen}")
    print(f"  Film:    {film or 'Not specified'}")
    print(f"  Source:  {source}")
    print(f"  API:     {THEATER_API}")
    print(f"  Min confidence: {CONFIDENCE_MIN}")
    print(f"  Cooldown: {COOLDOWN_SECS}s\n")

    # Load model — yolov8n.pt is smallest/fastest, good for real-time
    model = YOLO("yolov8n.pt")
    cap   = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"ERROR: Cannot open source: {source}")
        return

    last_logged = {}   # zone → timestamp of last log (cooldown tracking)
    frame_count = 0

    print("Running... Press Q to quit.\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        if frame_count % 3 != 0:   # Process every 3rd frame for performance
            continue

        h, w = frame.shape[:2]
        results = model(frame, classes=[PHONE_CLASS_ID], verbose=False)

        for r in results:
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf < CONFIDENCE_MIN:
                    continue

                # Get zone from x-center position
                x1,y1,x2,y2 = box.xyxy[0].tolist()
                x_center_norm = ((x1 + x2) / 2) / w
                zone = get_zone(x_center_norm)

                # Cooldown check — don't flood the API
                now = time.time()
                if now - last_logged.get(zone, 0) < COOLDOWN_SECS:
                    continue

                # Draw detection on frame
                cv2.rectangle(frame, (int(x1),int(y1)), (int(x2),int(y2)),
                              (0,0,255) if conf>=0.75 else (0,165,255), 2)
                label = f"PHONE {conf:.0%} [{zone}]"
                cv2.putText(frame, label, (int(x1), int(y1)-8),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                           (0,0,255) if conf>=0.75 else (0,165,255), 1)

                # Log to API
                print(f"[{datetime.now().strftime('%H:%M:%S')}] PHONE detected | "
                      f"zone={zone} conf={conf:.2f}")

                success = log_incident(theater, screen, zone, conf, film)
                if success:
                    last_logged[zone] = now

        # Zone overlay
        zone_labels = ["LEFT", "CENTER", "RIGHT"]
        for i, (zone, (lo, hi)) in enumerate(ZONE_BOUNDS.items()):
            x_start = int(lo * w)
            x_end   = int(hi * w)
            cv2.line(frame, (x_end, 0), (x_end, h), (40, 40, 40), 1)
            cv2.putText(frame, zone, (x_start + 8, 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80,80,80), 1)

        cv2.imshow("CINEOS Detector", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("\nDetector stopped.")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="CINEOS YOLO Phone Detector")
    p.add_argument("--source",  default=0,           help="Camera index or video path (default: 0 = webcam)")
    p.add_argument("--theater", default="Demo Theater", help="Theater name")
    p.add_argument("--screen",  default="Screen 1",  help="Screen/auditorium number")
    p.add_argument("--film",    default=None,        help="Film title currently showing")
    args = p.parse_args()

    source = int(args.source) if str(args.source).isdigit() else args.source
    run_detector(source, args.theater, args.screen, args.film)
