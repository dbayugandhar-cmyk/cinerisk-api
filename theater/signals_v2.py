"""
CINEOS Signal Pack v2
=====================
Signal 5 — Multi-Lens Pattern Classifier
Signal 6 — IR Autofocus Pulse Detector
Signal 7 — Recording Confirmation (duration + orientation)

Novel: no commercial anti-piracy system combines these.
Research basis: Seets et al. 2024 (Optica Publishing)
US Prov. Pat. 64/049,190
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional


# ── Signal 5 — Multi-Lens Pattern Classifier ─────────────────────────
def classify_lens_pattern(reflections: list) -> tuple:
    """
    Classify recording device type from lens reflection geometry.

    iPhone 16 Pro:    3 lenses, triangular, ~8mm spacing  → IPHONE_PRO
    Samsung S25 Ultra:4 lenses, rectangular               → PHONE_QUAD
    Camcorder:        1 large lens, 30-60mm diameter      → CAMCORDER
    GoPro/action:     1 wide lens, fisheye shape          → ACTION_CAM
    Hidden camera:    1 tiny lens, <8px area              → HIDDEN_CAM
    Single phone:     1 medium lens                       → PHONE_SINGLE

    Returns: (device_type, confidence, description)
    Novel: first system to classify device type from optical signature.
    Research: retro-reflection pattern analysis, Seets et al. 2024
    """
    n = len(reflections)

    if n == 0:
        return "NONE", 0.0, ""

    if n == 1:
        area = reflections[0].get("area", 0)
        circularity = reflections[0].get("circularity", 0.5)

        if area > 120:
            return "CAMCORDER", 0.87, "Large single lens — professional camcorder"
        if area > 50 and circularity > 0.7:
            return "ACTION_CAM", 0.75, "Wide circular lens — GoPro/action camera"
        if area < 8:
            return "HIDDEN_CAM", 0.82, "Tiny lens — concealed recording device"
        if 8 <= area <= 50:
            return "PHONE_SINGLE", 0.70, "Single lens — older/budget phone"
        return "UNKNOWN_SINGLE", 0.50, "Single lens — unclassified"

    if n == 2:
        # Measure spacing
        r0, r1 = reflections[0], reflections[1]
        spacing = ((r0["x"]-r1["x"])**2 + (r0["y"]-r1["y"])**2) ** 0.5
        if spacing < 25:
            return "PHONE_DUAL", 0.76, "Dual lens — mid-range smartphone"
        return "PHONE_DUAL_WIDE", 0.70, "Wide dual lens — large format phone"

    if n == 3:
        # Check triangular arrangement — iPhone Pro/flagship pattern
        xs = [r["x"] for r in reflections]
        ys = [r["y"] for r in reflections]
        x_span = max(xs) - min(xs)
        y_span = max(ys) - min(ys)
        if x_span < 45 and y_span < 45:
            return "IPHONE_PRO", 0.88, "Triple lens triangular — iPhone Pro/flagship"
        return "PHONE_TRIPLE", 0.78, "Triple lens — Android flagship"

    if n >= 4:
        return "PHONE_QUAD", 0.83, "Quad lens — Samsung Ultra/flagship"

    return "UNKNOWN", 0.40, "Unclassified lens pattern"


# ── Signal 6 — IR Autofocus Pulse Detector ───────────────────────────
class IRAutofocusDetector:
    """
    Detect IR autofocus pulses from recording devices.

    Physics:
    When a camera auto-focuses, it fires a brief IR pulse to measure
    distance. This pulse appears as a sudden bright spot that:
    - Appears in frame N but NOT in frame N-1 or N+1
    - Creates a temporal flash signature — not present in continuous light
    - Works in complete darkness
    - Catches any camera using IR autofocus (phones, camcorders, DSLRs)

    Why novel:
    - No commercial anti-piracy system uses this signal
    - Works when lens is hidden (inside jacket, bag)
    - Works in complete darkness
    - Only requires standard CCTV camera with any IR sensitivity

    Research basis: US Patent 6861640 — detecting IR autofocus beams
    in theatrical performances. CINEOS extends this to software-only
    implementation on existing CCTV infrastructure.
    """

    def __init__(self):
        self.frame_buffer = []   # Rolling 3-frame buffer
        self.pulse_tracker = {}  # zone -> pulse count
        self.cooldown = {}       # zone -> cooldown frames
        self.BUFFER_SIZE = 3
        self.PULSE_THRESHOLD = 25     # brightness delta to count as pulse
        self.MIN_AREA = 1
        self.MAX_AREA = 200           # AF spots are small
        self.CONFIRM_PULSES = 2       # Need 2 pulses to alert (reduces false positives)

    def add_frame(self, frame: np.ndarray):
        """Add frame to rolling buffer."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        self.frame_buffer.append(gray)
        if len(self.frame_buffer) > self.BUFFER_SIZE:
            self.frame_buffer.pop(0)

    def detect(self, frame_width: int, frame_height: int) -> list:
        """
        Detect IR AF pulses using 3-frame temporal differencing.
        Returns list of pulse detections with zone and confidence.
        """
        if len(self.frame_buffer) < 3:
            return []

        g1, g2, g3 = self.frame_buffer[0], self.frame_buffer[1], self.frame_buffer[2]

        # Scene must be dark for AF pulse detection to work
        avg_brightness = g2.mean()
        if avg_brightness > 85:
            return []

        # Temporal flash = bright in middle frame vs both neighbors
        diff_prev = g2 - g1   # positive = brighter than previous
        diff_next = g2 - g3   # positive = brighter than next

        # Must be brighter than BOTH neighbors — true temporal flash
        flash = np.minimum(diff_prev, diff_next)
        flash = np.clip(flash, 0, 255).astype(np.uint8)

        # Threshold for significant flash
        _, bright = cv2.threshold(flash, self.PULSE_THRESHOLD, 255, cv2.THRESH_BINARY)

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (self.MIN_AREA < area < self.MAX_AREA):
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            # Skip top portion — likely screen itself
            if y < frame_height * 0.12:
                continue

            # Circularity — AF pulses tend to be circular
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
            circularity = 4 * 3.14159 * area / (perimeter ** 2)
            if circularity < 0.35:
                continue

            cx, cy = x + w//2, y + h//2
            zone = "LEFT" if cx/frame_width < 0.33 else \
                   "CENTER" if cx/frame_width < 0.66 else "RIGHT"

            # Pulse intensity
            pulse_intensity = float(g2[cy, cx])
            prev_intensity = float(g1[cy, cx])
            intensity_delta = pulse_intensity - prev_intensity

            confidence = min(0.92, (circularity * 0.3 +
                                     min(1.0, intensity_delta/60) * 0.5 +
                                     min(1.0, area/30) * 0.2))

            detections.append({
                "zone": zone,
                "x": cx, "y": cy,
                "area": area,
                "circularity": round(circularity, 3),
                "intensity_delta": round(intensity_delta, 1),
                "confidence": round(confidence, 3),
                "detection_type": "IR_AF_PULSE"
            })

        # Track pulses per zone
        confirmed = []
        detected_zones = {d["zone"] for d in detections}

        for det in detections:
            zone = det["zone"]

            # Cooldown check
            if self.cooldown.get(zone, 0) > 0:
                self.cooldown[zone] -= 1
                continue

            self.pulse_tracker[zone] = self.pulse_tracker.get(zone, 0) + 1

            if self.pulse_tracker[zone] >= self.CONFIRM_PULSES:
                confirmed.append(det)
                self.cooldown[zone] = 90  # 3 second cooldown
                self.pulse_tracker[zone] = 0

        # Decay zones with no pulses
        for zone in list(self.pulse_tracker.keys()):
            if zone not in detected_zones:
                self.pulse_tracker[zone] = max(0, self.pulse_tracker[zone] - 1)

        return confirmed


# ── Signal 7 — Recording Confirmation ────────────────────────────────
class RecordingConfirmation:
    """
    Confirm active recording by requiring sustained detection.

    Key insight: existing $50,000 hardware systems have a critical flaw —
    they alert when a phone accidentally faces the screen (false positive).

    CINEOS solves this by requiring:
    1. Sustained lens detection (not accidental exposure)
    2. Multiple signal types agreeing (YOLO + pose + lens)
    3. Gradual confidence increase over time

    Research basis: US Patent 9482779 — "calculate for how long a camera
    is facing the screen and only point out a pirate if facing for a
    substantial period of time." CINEOS implements this in software
    on existing CCTV — no dedicated hardware required.
    """

    CONFIRM_SECONDS = 3.0    # Sustained for 3 seconds
    FPS = 30

    def __init__(self):
        self.evidence = {}   # key -> {frames, signals, max_conf}
        self.confirmed = {}  # key -> confirmation timestamp
        self.cooldown = {}

    def add_evidence(self, zone: str, signal_type: str,
                     confidence: float, device_type: str = "UNKNOWN") -> Optional[dict]:
        """
        Add detection evidence. Returns confirmation dict if threshold met.

        Multiple signal types increase confidence:
        - Single signal (e.g. only YOLO): needs longer duration
        - Two signals (YOLO + pose): faster confirmation
        - Three signals: immediate high-confidence alert
        """
        key = f"{zone}_{device_type}"
        if key not in self.evidence:
            self.evidence[key] = {
                "frames": 0,
                "signals": set(),
                "max_conf": 0.0,
                "zone": zone,
                "device_type": device_type
            }

        ev = self.evidence[key]
        ev["frames"] += 1
        ev["signals"].add(signal_type)
        ev["max_conf"] = max(ev["max_conf"], confidence)

        # Multi-signal confirmation is faster
        n_signals = len(ev["signals"])
        if n_signals >= 3:
            frames_needed = self.CONFIRM_SECONDS * self.FPS * 0.3  # 0.9s
        elif n_signals == 2:
            frames_needed = self.CONFIRM_SECONDS * self.FPS * 0.6  # 1.8s
        else:
            frames_needed = self.CONFIRM_SECONDS * self.FPS        # 3.0s

        if ev["frames"] >= frames_needed:
            if self.cooldown.get(key, 0) == 0:
                result = {
                    "zone": zone,
                    "device_type": device_type,
                    "signals_confirmed": list(ev["signals"]),
                    "n_signals": n_signals,
                    "confidence": round(ev["max_conf"] * min(1.0, n_signals * 0.4 + 0.3), 3),
                    "frames_sustained": ev["frames"],
                    "detection_type": "RECORDING_CONFIRMED"
                }
                self.evidence[key] = {
                    "frames": 0, "signals": set(),
                    "max_conf": 0.0, "zone": zone, "device_type": device_type
                }
                self.cooldown[key] = 150  # 5 second cooldown
                return result

        return None

    def tick(self):
        """Call once per frame to decay cooldowns."""
        for key in list(self.cooldown.keys()):
            self.cooldown[key] = max(0, self.cooldown[key] - 1)

        # Decay evidence for zones with no recent signal
        for key in list(self.evidence.keys()):
            self.evidence[key]["frames"] = max(
                0, self.evidence[key]["frames"] - 1
            )
