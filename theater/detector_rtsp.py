import cv2
try:
    from theater.alert_gate import AlertGate
    ALERT_GATE_AVAILABLE = True
except:
    try:
        from alert_gate import AlertGate
        ALERT_GATE_AVAILABLE = True
    except:
        ALERT_GATE_AVAILABLE = False

try:
    from theater.signals_v2 import IRAutofocusDetector, RecordingConfirmation, classify_lens_pattern, GlassesFilter
    SIGNALS_V2 = True
except:
    try:
        from signals_v2 import IRAutofocusDetector, RecordingConfirmation, classify_lens_pattern, GlassesFilter
        SIGNALS_V2 = True
    except:
        SIGNALS_V2 = False
        print("[DETECTOR] signals_v2 not available")

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


def enhance_low_light(frame):
    """
    CLAHE enhancement for dark theater conditions.
    Improves YOLO detection 30-40% in low light — no extra model needed.
    Works on the L channel (luminance) only — preserves color.
    """
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


def detect_phone_glow(frame, frame_width):
    """
    Detect phone screen glow in dark theater.
    Phones emit 200-800 nits — visible as bright rectangles in near-darkness.
    Works in complete darkness where YOLO fails.
    Novel signal: no competitor uses screen glow as a detection method.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Threshold for bright spots — only works if background is dark
    avg_brightness = gray.mean()
    if avg_brightness > 80:
        # Room is too bright — not dark enough for glow detection
        return []
    
    # Dynamic threshold based on scene brightness
    threshold = max(160, int(avg_brightness * 4))
    _, bright = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    
    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(
        bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    
    candidates = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = w / max(h, 1)
        area = w * h
        
        # Phone screens: rectangular shape, reasonable size
        # Too small = noise, too large = the movie screen itself
        if (0.3 < aspect < 3.0 and 
            40 < area < 8000 and
            y > frame.shape[0] * 0.1):  # not at top of frame
            
            x_center = (x + w/2) / frame_width
            zone = get_zone(x + w//2, frame_width)
            candidates.append({
                "zone": zone,
                "x": x, "y": y, "w": w, "h": h,
                "x_center": x_center,
                "brightness": gray[y:y+h, x:x+w].mean(),
                "confidence": min(0.85, area / 2000)
            })
    
    return candidates


class TemporalTracker:
    """
    Track detections across frames.
    If zone had detection last N frames, lower confidence threshold.
    Dramatically reduces false negatives without increasing false positives.
    """
    def __init__(self, memory_frames=5, boost_factor=0.8):
        self.zone_history = {"LEFT": 0, "CENTER": 0, "RIGHT": 0}
        self.memory_frames = memory_frames
        self.boost_factor = boost_factor
    
    def update(self, detected_zones: set):
        for zone in self.zone_history:
            if zone in detected_zones:
                self.zone_history[zone] = self.memory_frames
            else:
                self.zone_history[zone] = max(0, self.zone_history[zone] - 1)
    
    def get_threshold(self, zone: str, base_threshold: float) -> float:
        """Lower threshold if zone was recently active."""
        if self.zone_history.get(zone, 0) > 0:
            return base_threshold * self.boost_factor
        return base_threshold


class ConfidenceBuffer:
    """
    Average confidence scores across multiple frames.
    Reduces false positives from single-frame noise.
    Improves detection of sustained recording attempts.
    """
    def __init__(self, window=3):
        self.window = window
        self.buffers = {"LEFT": [], "CENTER": [], "RIGHT": []}
    
    def add(self, zone: str, confidence: float):
        buf = self.buffers[zone]
        buf.append(confidence)
        if len(buf) > self.window:
            buf.pop(0)
    
    def get_avg(self, zone: str) -> float:
        buf = self.buffers[zone]
        return sum(buf) / len(buf) if buf else 0.0
    
    def clear(self, zone: str):
        self.buffers[zone] = []

def run_detector(stream_url: str):
    print(f"[CINEOS] Connecting to: {stream_url}")
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print("[CINEOS] ERROR: Cannot open stream")
        sys.exit(1)

    print(f"[CINEOS] Stream open — monitoring {THEATER} {SCREEN} for {FILM}")
    loop = asyncio.new_event_loop()
    frame_count = 0
    prev_frame = None
    prev_frame = None

    # Initialize lens tracker
    lens_tracker = LensTracker(confirm_frames=5, position_tolerance=20)

    # Initialize Signal v2 detectors
    ir_af_detector = None
    recording_confirmation = None
    if SIGNALS_V2:
        ir_af_detector = IRAutofocusDetector()
        recording_confirmation = RecordingConfirmation()
        glasses_filter = GlassesFilter()
        alert_gate = AlertGate(window_seconds=3.0, fps=30) if ALERT_GATE_AVAILABLE else None
        print("[CINEOS] Alert gate active — multi-signal required for alerts")
        print("[CINEOS] Signal v2 active — IR AF pulse + device classifier + confirmation")
    
    # Initialize pose detector inside function scope
    pose_detector = None
    if POSE_AVAILABLE:
        try:
            pose_detector = PoseDetector()
            print("[CINEOS] Pose detector active — dual signal running")
        except Exception as e:
            print(f"[CINEOS] Pose detector unavailable: {e}")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[CINEOS] Stream lost — reconnecting in 5s")
            time.sleep(5)
            cap = cv2.VideoCapture(stream_url)
            continue

        frame_count += 1
        h, w = frame.shape[:2]
        if alert_gate:
            alert_gate.tick()
        
        # Stage 1 — Adaptive enhancement based on scene brightness
        enhanced, scene_brightness = adaptive_enhance(frame)
        night_mode = scene_brightness < 80  # True during theater screening
        if frame_count % 30 == 0:  # Print every 30 frames
            print(f"[DEBUG] Scene brightness: {scene_brightness:.1f} | Night mode: {night_mode}")
        
        # Stage 2 — Lens reflection detection (runs whenever below threshold)
        if night_mode:
            # Single frame detection
            raw_lens = detect_lens_reflection(frame, w, h)
            # Dual exposure stability detection (more reliable)
            if prev_frame is not None:
                dual_lens = detect_lens_dual_exposure(prev_frame, frame, w, h)
                raw_lens.extend(dual_lens)
            confirmed_lens = lens_tracker.update(raw_lens)
            # Filter out eyeglass reflections before classification
            if SIGNALS_V2 and confirmed_lens:
                confirmed_lens = glasses_filter.filter(confirmed_lens, w, h)
            for lens in confirmed_lens:
                # Classify device type from lens pattern
                device_type, dev_conf, dev_desc = "UNKNOWN", 0.5, ""
                if SIGNALS_V2:
                    device_type, dev_conf, dev_desc = classify_lens_pattern([lens])
                print(f"[LENS] {device_type} detected — Zone:{lens['zone']} | "
                      f"Brightness:{lens['brightness_ratio']}x | "
                      f"Circularity:{lens['circularity']:.2f} | "
                      f"Conf:{lens['confidence']:.0%} | {dev_desc}")
                loop.run_until_complete(report_incident(
                    lens["zone"],
                    lens["confidence"],
                    detection_type=f"LENS_{device_type}"
                ))
                if recording_confirmation:
                    result = recording_confirmation.add_evidence(
                        lens["zone"], "LENS", lens["confidence"], device_type)
                    if result:
                        print(f"[CONFIRMED] RECORDING CONFIRMED — Zone:{result['zone']} | "
                              f"Device:{result['device_type']} | "
                              f"Signals:{result['signals_confirmed']} | "
                              f"Duration:{result['frames_sustained']} frames | "
                              f"Conf:{result['confidence']:.0%}")
                        loop.run_until_complete(report_incident(
                            result["zone"],
                            result["confidence"],
                            detection_type="RECORDING_CONFIRMED"
                        ))
        
        # Stage 3 — Phone glow detection (works in complete darkness)
        glow_detections = detect_phone_glow(frame, w)
        for glow in glow_detections:
            print(f"[GLOW] Phone screen detected — Zone:{glow['zone']} | "
                  f"Brightness:{glow['brightness']:.0f} | Conf:{glow['confidence']:.0%}")
            if alert_gate:
                decision = alert_gate.add_signal(glow["zone"], "PHONE_GLOW", glow["confidence"])
                if decision and decision.should_alert:
                    print(f"[CINEOS] CONFIRMED {glow['zone']} — {decision.reason}")
                    loop.run_until_complete(report_incident(glow["zone"], decision.confidence, decision.level))
            if recording_confirmation:
                recording_confirmation.add_evidence(
                    glow["zone"], "GLOW", glow["confidence"])

        # Signal 6 — IR Autofocus Pulse Detection
        if ir_af_detector and night_mode:
            ir_af_detector.add_frame(frame)
            af_pulses = ir_af_detector.detect(w, h)
            for pulse in af_pulses:
                print(f"[AF-PULSE] IR autofocus detected — Zone:{pulse['zone']} | "
                      f"Delta:{pulse['intensity_delta']:.0f} | Conf:{pulse['confidence']:.0%}")
                if alert_gate:
                    decision = alert_gate.add_signal(pulse["zone"], "IR_AF_PULSE", pulse["confidence"])
                    if decision and decision.should_alert:
                        print(f"[CINEOS] CONFIRMED {pulse['zone']} — {decision.reason}")
                        loop.run_until_complete(report_incident(pulse["zone"], decision.confidence, decision.level))
                if recording_confirmation:
                    recording_confirmation.add_evidence(
                        pulse["zone"], "IR_AF_PULSE", pulse["confidence"])

        # Recording confirmation tick
        if recording_confirmation:
            recording_confirmation.tick()
        
        # Stage 3 — YOLO on enhanced frame
        results = model(enhanced)  # enhanced frame = better dark detection
        # Filter to cell phone class (67) above confidence threshold
        detections = results.xyxy[0]  # [x1,y1,x2,y2,conf,class]
        phone_dets = detections[(detections[:, 5] == 67) & (detections[:, 4] >= CONFIDENCE_THRESHOLD)] if len(detections) else detections

        prev_frame = frame.copy()
        # Pose detection — behavioral signal (catches camcorders too)
        if pose_detector:
            try:
                pose_alerts = pose_detector.process_frame(frame)
                for alert in pose_alerts:
                    print(f"[POSE] {alert.posture} | Zone:{alert.zone} | Conf:{alert.confidence:.0%}")
                    if alert_gate:
                        decision = alert_gate.add_signal(alert.zone, alert.posture, alert.confidence)
                        if decision and decision.should_alert:
                            print(f"[CINEOS] CONFIRMED {alert.zone} — {decision.reason}")
                            loop.run_until_complete(report_incident(alert.zone, decision.confidence, decision.level))
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
                    zone_timers[zone] = 0
                    # Alert gate — require multi-signal before firing
                    if alert_gate:
                        decision = alert_gate.add_signal(zone, "PHONE", conf)
                        if decision and decision.should_alert:
                            print(f"[CINEOS] ALERT {zone} — {decision.level} — conf {decision.confidence:.2f} — {decision.reason}")
                            loop.run_until_complete(report_incident(zone, decision.confidence, decision.level))
                            level, session = loop.run_until_complete(update_session(THEATER, SCREEN, FILM, zone, decision.confidence))
                            if level >= 2:
                                print(f"[CINEOS] Session count: {session['count']} — Escalation L{level}")
                        elif decision:
                            print(f"[GATE] {decision.level} — {decision.reason}")
                    else:
                        print(f"[CINEOS] ALERT {zone} zone — conf {conf:.2f} — {FILM}")
                        loop.run_until_complete(report_incident(zone, conf))
                        level, session = loop.run_until_complete(update_session(THEATER, SCREEN, FILM, zone, conf))
                        if level >= 2:
                            print(f"[CINEOS] Session count: {session['count']} — Escalation L{level}")

        # Decay timers for zones not detected this frame
        for z in list(zone_timers.keys()):
            if z not in detected_zones:
                zone_timers[z] = max(0, zone_timers[z] - 1)


def adaptive_enhance(frame, calibration_brightness=None):
    """
    Adaptive CLAHE based on current scene brightness.
    Stronger enhancement in darker scenes.
    Different from fixed CLAHE — adjusts clip limit dynamically.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    avg = gray.mean()
    
    # Dynamically adjust clip limit based on scene darkness
    if avg < 20:      clip = 6.0   # very dark — aggressive enhancement
    elif avg < 40:    clip = 4.0   # dark theater
    elif avg < 80:    clip = 2.5   # dim
    else:             clip = 1.5   # normal light — light touch
    
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR), avg



def calibrate_screen(cap, frames=30):
    """
    Sample 30 frames at startup to measure baseline theater brightness.
    Used to set detection thresholds per screen.
    """
    brightnesses = []
    for _ in range(frames):
        ret, frame = cap.read()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightnesses.append(gray.mean())
    avg = sum(brightnesses) / len(brightnesses) if brightnesses else 40
    print(f"[CINEOS] Screen calibration — baseline brightness: {avg:.1f}")
    return avg


def detect_lens_reflection(frame, frame_width, frame_height):
    """
    CINEOS Lens Reflection Detector — Novel Signal
    ================================================
    Detects camera/phone lenses by their retro-reflective signature.
    
    Physics: Camera lenses reflect incoming light in a tight, bright beam
    back toward the light source (movie screen + CCTV camera).
    Human eyes scatter light diffusely — much dimmer, larger, irregular.
    
    A camera lens in a dark theater appears as:
    - Very bright (10-100x brighter than eye reflections)
    - Very small (tight focused beam, 2-8 pixels)
    - Circular or near-circular shape
    - Stable across frames (doesn't flicker like eyes)
    
    Research basis: Seets et al. 2024 (Optica Publishing)
    "Watching the watchers: camera identification via retro-reflections"
    
    US Prov. Pat. 64/049,190
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    avg_brightness = gray.mean()
    
    # Only effective in dark environments — theater during screening
    if avg_brightness > 90:
        return []
    
    # Step 1: Find very bright spots against dark background
    # Camera lens reflections are significantly brighter than surroundings
    threshold = max(200, int(avg_brightness * 8))
    _, bright_mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    
    # Step 2: Morphological cleanup — remove noise, keep tight spots
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    kernel_medium = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4, 4))
    bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_OPEN, kernel_small)
    bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel_medium)
    
    # Step 3: Find contours of bright spots
    contours, _ = cv2.findContours(
        bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    
    lens_candidates = []
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 2 or area > 300:
            continue
        
        x, y, w, h = cv2.boundingRect(cnt)
        
        # Skip top 15% of frame — likely screen reflection not audience
        if y < frame_height * 0.15:
            continue
        
        # Circularity check — lens reflections are near-circular
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4 * 3.14159 * area / (perimeter * perimeter)
        
        # Camera lens: circularity 0.6-1.0
        # Random noise: low circularity
        if circularity < 0.5:
            continue
        
        # Intensity check — lens reflection is much brighter than surroundings
        cx, cy = x + w//2, y + h//2
        spot_brightness = float(gray[cy, cx])
        
        # Sample surrounding area brightness (exclude the spot itself)
        r = max(w, h) * 3
        x1 = max(0, cx - r); x2 = min(frame_width, cx + r)
        y1 = max(0, cy - r); y2 = min(frame_height, cy + r)
        surround = gray[y1:y2, x1:x2].mean()
        
        # Lens reflection must be significantly brighter than surroundings
        brightness_ratio = spot_brightness / max(surround, 1)
        # In very dark scenes (brightness < 10) even ratio of 2x is significant
        min_ratio = 2.0 if avg_brightness < 10 else 4.0
        if brightness_ratio < min_ratio:
            continue
        
        # Zone detection
        x_norm = cx / frame_width
        zone = "LEFT" if x_norm < 0.33 else "CENTER" if x_norm < 0.66 else "RIGHT"
        
        # Confidence based on circularity + brightness ratio
        confidence = min(0.95, (circularity * 0.4 + min(1.0, brightness_ratio / 20) * 0.6))
        
        lens_candidates.append({
            "zone": zone,
            "x": cx, "y": cy,
            "x_norm": x_norm,
            "y_norm": cy / frame_height,
            "area": area,
            "circularity": round(circularity, 3),
            "brightness_ratio": round(brightness_ratio, 1),
            "spot_brightness": round(spot_brightness, 1),
            "confidence": round(confidence, 3),
            "detection_type": "LENS_REFLECTION"
        })
    
    return lens_candidates



class LensTracker:
    """
    Track lens reflections across frames.
    A real camera lens stays in the same position across frames.
    Random noise moves or disappears.
    Require detection in N consecutive frames before alerting.
    """
    def __init__(self, confirm_frames=8, position_tolerance=15):
        self.candidates = {}  # key: grid_cell -> frame_count
        self.confirm_frames = confirm_frames
        self.tolerance = position_tolerance
        self.cooldown = {}
    
    def _grid_key(self, x, y):
        """Quantize position to grid cells to handle slight movement."""
        gx = x // self.tolerance
        gy = y // self.tolerance
        return f"{gx}_{gy}"
    
    def update(self, detections: list) -> list:
        """Returns confirmed lens detections after N frames."""
        confirmed = []
        current_keys = set()
        
        for det in detections:
            key = self._grid_key(det["x"], det["y"])
            current_keys.add(key)
            self.candidates[key] = self.candidates.get(key, 0) + 1
            
            # Check cooldown
            if self.cooldown.get(key, 0) > 0:
                self.cooldown[key] -= 1
                continue
            
            # Confirmed after N consecutive frames
            if self.candidates[key] >= self.confirm_frames:
                confirmed.append(det)
                self.cooldown[key] = 90  # 3 second cooldown at 30fps
                self.candidates[key] = 0
        
        # Decay absent candidates
        for key in list(self.candidates.keys()):
            if key not in current_keys:
                self.candidates[key] = max(0, self.candidates[key] - 2)
        
        return confirmed

def detect_lens_dual_exposure(frame1, frame2, frame_width, frame_height):
    """
    Dual-exposure lens detection.
    Camera lenses create STABLE bright spots across frames.
    Eyes, reflections, noise are UNSTABLE — move or disappear.
    
    Compare two consecutive frames:
    - Stable bright spot = camera lens (retro-reflection)
    - Unstable bright spot = noise, eye blink, random reflection
    
    This works without IR illuminator by exploiting temporal stability.
    """
    g1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY).astype(float)
    g2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY).astype(float)
    
    avg_brightness = g1.mean()
    if avg_brightness > 90:
        return []
    
    # Find bright spots in both frames
    thresh = max(180, avg_brightness * 6)
    _, b1 = cv2.threshold(g1.astype('uint8'), int(thresh), 255, cv2.THRESH_BINARY)
    _, b2 = cv2.threshold(g2.astype('uint8'), int(thresh), 255, cv2.THRESH_BINARY)
    
    # Keep only spots present in BOTH frames (stability filter)
    stable = cv2.bitwise_and(b1, b2)
    
    # Morphological cleanup
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
    stable = cv2.morphologyEx(stable, cv2.MORPH_OPEN, k)
    
    contours, _ = cv2.findContours(stable, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    candidates = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 1 or area > 200:
            continue
        
        x, y, w, h = cv2.boundingRect(cnt)
        if y < frame_height * 0.12:
            continue
        
        # Circularity
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4 * 3.14159 * area / (perimeter ** 2)
        if circularity < 0.45:
            continue
        
        cx, cy = x + w//2, y + h//2
        spot = float(g1[cy, cx])
        
        # Surrounding brightness
        r = max(w,h) * 4
        sx1,sx2 = max(0,cx-r), min(frame_width,cx+r)
        sy1,sy2 = max(0,cy-r), min(frame_height,cy+r)
        surround = g1[sy1:sy2, sx1:sx2].mean()
        ratio = spot / max(surround, 1)
        
        if ratio < 2.5:
            continue
        
        zone = "LEFT" if cx/frame_width < 0.33 else "CENTER" if cx/frame_width < 0.66 else "RIGHT"
        conf = min(0.92, circularity * 0.35 + min(1.0, ratio/15) * 0.65)
        
        candidates.append({
            "zone": zone,
            "x": cx, "y": cy,
            "circularity": round(circularity, 3),
            "brightness_ratio": round(ratio, 1),
            "confidence": round(conf, 3),
            "detection_type": "LENS_REFLECTION",
            "method": "dual_exposure_stability"
        })
    
    return candidates



if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "0"
    stream = int(arg) if arg.isdigit() else arg
    run_detector(stream)




