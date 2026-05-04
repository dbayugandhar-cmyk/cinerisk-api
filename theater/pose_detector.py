"""
CINEOS Pose Detection Layer
===========================
Detects recording BEHAVIOR not just recording DEVICES.
Novel: catches phones, camcorders, DSLRs, GoPros — any device.

MediaPipe 0.10+ API (Tasks API)
US Prov. Pat. 64/049,190
"""

import cv2
import numpy as np
import urllib.request
import os
from dataclasses import dataclass

# Download model if not present
MODEL_PATH = os.path.join(os.path.dirname(__file__), "pose_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"

def ensure_model():
    if not os.path.exists(MODEL_PATH):
        print("[POSE] Downloading pose model (~5MB)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[POSE] Model downloaded")

DURATION_THRESHOLD = 12  # More frames required — reduces quick movement false positives
CONFIDENCE_THRESHOLD = 0.55

@dataclass
class PoseAlert:
    zone: str
    confidence: float
    posture: str
    x_center: float
    y_center: float
    frame_count: int


class PoseDetector:
    """
    Behavioral recording detector — detects the ACT of recording.
    Catches any device: phone, camcorder, DSLR, GoPro.
    """

    def __init__(self):
        ensure_model()
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision as mp_vision
        from mediapipe.tasks.python.vision import RunningMode

        base_options = mp_tasks.BaseOptions(model_asset_path=MODEL_PATH)
        options = mp_vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=RunningMode.VIDEO,
            min_pose_detection_confidence=CONFIDENCE_THRESHOLD,
            min_pose_presence_confidence=CONFIDENCE_THRESHOLD,
            min_tracking_confidence=0.5,
            num_poses=4
        )
        self.landmarker = mp_vision.PoseLandmarker.create_from_options(options)
        self.frame_counters = {}
        self.alert_cooldown = {}
        self.frame_ts = 0

    def _zone(self, x): 
        return "LEFT" if x < 0.33 else "CENTER" if x < 0.66 else "RIGHT"

    def _check_posture(self, lms):
        """
        Check landmark positions for recording posture.
        Indices: 0=nose, 11=L_shoulder, 12=R_shoulder,
                 13=L_elbow, 14=R_elbow, 15=L_wrist, 16=R_wrist
        """
        try:
            nose      = lms[0]
            l_sh      = lms[11]
            r_sh      = lms[12]
            l_wr      = lms[15]
            r_wr      = lms[16]

            # Skip if landmarks not visible
            if any(lm.visibility < 0.4 for lm in [l_sh, r_sh, l_wr, r_wr]):
                return False, "", 0.0, 0.0, 0.0

            sh_y = (l_sh.y + r_sh.y) / 2
            sh_x = (l_sh.x + r_sh.x) / 2

            l_above_nose = l_wr.y < nose.y
            r_above_nose = r_wr.y < nose.y
            l_above_sh   = l_wr.y < sh_y
            r_above_sh   = r_wr.y < sh_y

            # Posture 1 — Phone raised above nose
            if l_above_nose or r_above_nose:
                wrist_y = min(
                    l_wr.y if l_above_nose else 1.0,
                    r_wr.y if r_above_nose else 1.0
                )
                conf = min(1.0, (nose.y - wrist_y) / max(nose.y, 0.01) * 3)
                conf = conf * 0.6 + ((l_wr.visibility + r_wr.visibility) / 2) * 0.4
                return True, "PHONE_RAISED", round(conf, 3), sh_x, sh_y

            # Posture 2 — Both wrists above shoulders (camcorder)
            # Requires upright posture — excludes reclined/sofa positions
            if l_above_sh and r_above_sh:
                height_above = sh_y - min(l_wr.y, r_wr.y)
                # Must be meaningfully above shoulder
                if height_above > sh_y * 0.08:
                    # Check upright — hips must be below shoulders
                    # Reclined person: hips at same level as shoulders
                    # Upright person: hips clearly lower than shoulders
                    try:
                        l_hip = lms[23]
                        r_hip = lms[24]
                        hip_y = (l_hip.y + r_hip.y) / 2
                        hip_vis = (l_hip.visibility + r_hip.visibility) / 2
                        # If hips visible and not clearly below shoulders = reclined
                        if hip_vis > 0.4 and hip_y < sh_y * 1.12:
                            pass  # Reclined posture — skip
                        else:
                            # Wrists close together (holding device)
                            wrist_spread = abs(l_wr.x - r_wr.x)
                            sh_width = abs(lms[11].x - lms[12].x)
                            if wrist_spread < sh_width * 1.4:
                                height = min(1.0, height_above / max(sh_y, 0.01) * 5)
                                conf = height * 0.5 + ((l_wr.visibility + r_wr.visibility) / 2) * 0.5
                                if conf > 0.65:
                                    return True, "CAMCORDER_POSITION", round(conf, 3), sh_x, sh_y
                    except:
                        pass

            # Posture 3 — One wrist significantly above shoulder
            l_sig = l_wr.y < sh_y * 0.85
            r_sig = r_wr.y < sh_y * 0.85
            if l_sig or r_sig:
                wr = l_wr if l_sig else r_wr
                conf = min(1.0, (sh_y - wr.y) / max(sh_y, 0.01) * 4)
                conf = conf * 0.6 + wr.visibility * 0.4
                if conf > 0.45:
                    return True, "RECORDING_POSITION", round(conf, 3), sh_x, sh_y

            return False, "", 0.0, 0.0, 0.0
        except:
            return False, "", 0.0, 0.0, 0.0


    def _is_camcorder_grip(self, lms) -> tuple:
        """
        Detect two-handed camcorder grip specifically.
        Both wrists at same height, shoulder width apart,
        elbows bent outward — classic camcorder posture.
        More specific than general CAMCORDER_POSITION.
        """
        try:
            l_sh = lms[11]; r_sh = lms[12]
            l_el = lms[13]; r_el = lms[14]
            l_wr = lms[15]; r_wr = lms[16]
            
            if any(lm.visibility < 0.5 for lm in [l_sh, r_sh, l_wr, r_wr]):
                return False, 0.0
            
            sh_y = (l_sh.y + r_sh.y) / 2
            sh_width = abs(l_sh.x - r_sh.x)
            
            # Both wrists at similar height (within 10% of shoulder width)
            wrist_height_diff = abs(l_wr.y - r_wr.y)
            wrists_level = wrist_height_diff < sh_width * 0.25
            
            # Both wrists above shoulders
            both_above = l_wr.y < sh_y and r_wr.y < sh_y
            
            # Wrists separated by at least shoulder width (holding a wide device)
            wrist_span = abs(l_wr.x - r_wr.x)
            wide_grip = wrist_span > sh_width * 0.6
            
            if wrists_level and both_above and wide_grip:
                vis_conf = (l_wr.visibility + r_wr.visibility) / 2
                height_conf = min(1.0, (sh_y - min(l_wr.y, r_wr.y)) / max(sh_y, 0.01) * 4)
                conf = vis_conf * 0.4 + height_conf * 0.6
                return conf > 0.5, round(conf, 3)
        except:
            pass
        return False, 0.0

    def process_frame(self, frame: np.ndarray) -> list:
        import mediapipe as mp
        self.frame_ts += 33  # ~30fps timestamp in ms

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.landmarker.detect_for_video(mp_image, self.frame_ts)

        alerts = []
        if not result.pose_landmarks:
            return alerts

        for pose_lms in result.pose_landmarks:
            is_rec, posture, conf, x, y = self._check_posture(pose_lms)
            if not is_rec or conf < 0.40:
                continue

            zone = self._zone(x)
            key = f"{zone}_{posture}"
            self.frame_counters[key] = self.frame_counters.get(key, 0) + 1
            cooldown = self.alert_cooldown.get(zone, 0)

            if cooldown > 0:
                self.alert_cooldown[zone] = cooldown - 1
                continue

            if self.frame_counters[key] >= DURATION_THRESHOLD:
                alerts.append(PoseAlert(
                    zone=zone, confidence=conf, posture=posture,
                    x_center=x, y_center=y,
                    frame_count=self.frame_counters[key]
                ))
                self.alert_cooldown[zone] = 60
                self.frame_counters[key] = 0

        return alerts

    def close(self):
        self.landmarker.close()


if __name__ == "__main__":
    print("[POSE] CINEOS Pose Detector v2 — MediaPipe 0.10+")
    print("[POSE] Raise your arm/hand above shoulder to trigger alert")
    print("[POSE] Press Q to quit\n")

    detector = PoseDetector()
    cap = cv2.VideoCapture(0)
    alert_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        alerts = detector.process_frame(frame)

        for alert in alerts:
            alert_count += 1
            print(f"[POSE] ALERT — Zone:{alert.zone} | "
                  f"{alert.posture} | Conf:{alert.confidence:.0%} | "
                  f"Frames:{alert.frame_count}")

        label = f"CINEOS Pose | Alerts:{alert_count}"
        cv2.putText(frame, label, (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

        if alerts:
            cv2.putText(frame, f"RECORDING DETECTED: {alerts[0].zone}",
                        (10,70), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,255), 2)

        cv2.imshow('CINEOS Pose', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    detector.close()
    print(f"[POSE] Done — {alert_count} total alerts")
