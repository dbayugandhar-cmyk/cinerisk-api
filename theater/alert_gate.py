"""
CINEOS Alert Gate
=================
Core principle: NO single signal fires an alert alone.
Multiple independent signals must agree before any alert.

This is what separates CINEOS from a demo.
A real piracy recording creates multiple simultaneous signals.
A false positive (glasses, remote control, hand wave) creates only one.

Signal combinations required:
- YOLO alone: never alert (too many false positives)
- Pose alone: never alert (body movement too common)
- Glow alone: never alert (any bright light triggers)
- IR pulse alone: never alert (TV remotes, etc.)
- Lens alone: never alert (glasses, jewelry)

Valid combinations:
- YOLO + Pose: HIGH confidence (device seen + recording posture)
- YOLO + Glow: HIGH confidence (phone seen + screen light)
- Pose + IR pulse: HIGH confidence (recording posture + AF beam)
- Lens + Pose: HIGH confidence (lens confirmed + recording posture)
- Any 3+ signals: CRITICAL confidence
- Confirmation signal alone: CRITICAL (already multi-signal verified)

US Prov. Pat. 64/049,190
"""

from dataclasses import dataclass
from typing import Optional
import time


# Signals that are too noisy to fire alone
NOISY_SIGNALS = {
    "PHONE",           # YOLO — too many false positives alone
    "PHONE_RAISED",    # Pose — hand raise too common
    "CAMCORDER_POSITION",  # Pose — desk posture
    "RECORDING_POSITION",  # Pose — ambiguous
    "PHONE_GLOW",      # Glow — any bright light
    "IR_AF_PULSE",     # AF pulse — TV remotes
    "LENS_REFLECTION", # Lens — glasses, jewelry
}

# Signals that are strong enough to contribute to multi-signal
STRONG_SIGNALS = {
    "RECORDING_CONFIRMED",  # Already multi-signal verified
    "LENS_IPHONE_PRO",      # Very specific device signature
    "LENS_CAMCORDER",       # Very specific device signature
    "LENS_HIDDEN_CAM",      # Hidden camera = immediate alert
}

# Valid two-signal combinations
VALID_PAIRS = {
    frozenset({"PHONE", "PHONE_RAISED"}),
    frozenset({"PHONE", "CAMCORDER_POSITION"}),
    frozenset({"PHONE", "PHONE_GLOW"}),
    frozenset({"PHONE", "IR_AF_PULSE"}),
    frozenset({"PHONE", "LENS_REFLECTION"}),
    frozenset({"PHONE_RAISED", "IR_AF_PULSE"}),
    frozenset({"PHONE_RAISED", "PHONE_GLOW"}),
    frozenset({"CAMCORDER_POSITION", "IR_AF_PULSE"}),
    frozenset({"CAMCORDER_POSITION", "LENS_REFLECTION"}),
    frozenset({"LENS_REFLECTION", "IR_AF_PULSE"}),
    frozenset({"LENS_REFLECTION", "PHONE_RAISED"}),
    frozenset({"PHONE_GLOW", "IR_AF_PULSE"}),
}


@dataclass
class AlertDecision:
    should_alert: bool
    confidence: float
    level: str           # CRITICAL / HIGH / MEDIUM / SUPPRESSED
    reason: str
    signals: list


class AlertGate:
    """
    Multi-signal gate that prevents false positive alerts.
    
    Core rule: a signal alone never fires an alert.
    Two or more independent signals must agree.
    
    This directly addresses the known flaw in existing systems:
    US Patent 9482779 notes false positives when phone accidentally
    faces screen. AlertGate requires corroborating evidence.
    """

    def __init__(self, window_seconds: float = 3.0, fps: int = 30):
        self.window_frames = int(window_seconds * fps)
        self.zone_evidence = {}   # zone -> {signal: [frame_timestamps]}
        self.frame_number = 0
        self.last_alert = {}      # zone -> frame_number of last alert
        self.alert_cooldown = int(5.0 * fps)  # 5 second cooldown

    def add_signal(self, zone: str, signal_type: str,
                   confidence: float) -> Optional[AlertDecision]:
        """
        Add a detection signal for a zone.
        Returns AlertDecision if alert should fire, None otherwise.
        """
        if zone not in self.zone_evidence:
            self.zone_evidence[zone] = {}

        # Add to evidence window
        if signal_type not in self.zone_evidence[zone]:
            self.zone_evidence[zone][signal_type] = []

        self.zone_evidence[zone][signal_type].append({
            "frame": self.frame_number,
            "confidence": confidence
        })

        # Clean old evidence outside window
        cutoff = self.frame_number - self.window_frames
        for sig in list(self.zone_evidence[zone].keys()):
            self.zone_evidence[zone][sig] = [
                e for e in self.zone_evidence[zone][sig]
                if e["frame"] > cutoff
            ]
            if not self.zone_evidence[zone][sig]:
                del self.zone_evidence[zone][sig]

        return self._evaluate(zone)

    def _evaluate(self, zone: str) -> Optional[AlertDecision]:
        """Evaluate whether current evidence warrants an alert."""

        # Cooldown check
        last = self.last_alert.get(zone, -999)
        if self.frame_number - last < self.alert_cooldown:
            return None

        active_signals = set(self.zone_evidence.get(zone, {}).keys())
        if not active_signals:
            return None

        # Get max confidence per signal
        max_conf = {}
        for sig, events in self.zone_evidence.get(zone, {}).items():
            max_conf[sig] = max(e["confidence"] for e in events)

        # Rule 1: RECORDING_CONFIRMED or specific device = immediate alert
        strong = active_signals & STRONG_SIGNALS
        if strong:
            best_sig = max(strong, key=lambda s: max_conf.get(s, 0))
            self.last_alert[zone] = self.frame_number
            return AlertDecision(
                should_alert=True,
                confidence=max_conf[best_sig],
                level="CRITICAL",
                reason=f"Strong signal confirmed: {best_sig}",
                signals=list(active_signals)
            )

        # Rule 2: Hidden camera lens = immediate alert (no other signal needed)
        if "LENS_HIDDEN_CAM" in active_signals:
            self.last_alert[zone] = self.frame_number
            return AlertDecision(
                should_alert=True,
                confidence=max_conf.get("LENS_HIDDEN_CAM", 0.8),
                level="CRITICAL",
                reason="Hidden camera lens detected",
                signals=list(active_signals)
            )

        # Rule 3: Three or more signals = HIGH alert
        noisy_active = active_signals & NOISY_SIGNALS
        if len(noisy_active) >= 3:
            avg_conf = sum(max_conf.get(s, 0) for s in noisy_active) / len(noisy_active)
            combined_conf = min(0.95, avg_conf * 1.3)
            self.last_alert[zone] = self.frame_number
            return AlertDecision(
                should_alert=True,
                confidence=combined_conf,
                level="HIGH",
                reason=f"3+ signals: {list(noisy_active)}",
                signals=list(active_signals)
            )

        # Rule 4: Valid two-signal combination
        for pair in VALID_PAIRS:
            if pair.issubset(active_signals):
                s1, s2 = list(pair)
                conf = min(0.90, (max_conf.get(s1, 0) + max_conf.get(s2, 0)) / 2 * 1.2)
                if conf > 0.45:  # Minimum confidence for pair alert
                    self.last_alert[zone] = self.frame_number
                    return AlertDecision(
                        should_alert=True,
                        confidence=conf,
                        level="HIGH",
                        reason=f"Signal pair: {s1} + {s2}",
                        signals=list(active_signals)
                    )

        # Rule 5: Single signal alone = suppress, log silently
        if active_signals:
            return AlertDecision(
                should_alert=False,
                confidence=0.0,
                level="SUPPRESSED",
                reason=f"Single signal only: {list(active_signals)[0]} — waiting for corroboration",
                signals=list(active_signals)
            )

        return None

    def tick(self):
        """Call once per frame."""
        self.frame_number += 1
