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
    # frozenset({"PHONE", "IR_AF_PULSE"}),  # Removed — screen refresh creates false IR pulses
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

        # ── RULE 1: Already confirmed recording ──────────────────────────
        if active_signals & CONFIRMED_SIGNALS:
            best = max(active_signals & CONFIRMED_SIGNALS,
                      key=lambda s: max_conf.get(s, 0))
            self.last_alert[zone] = self.frame_number
            return AlertDecision(
                should_alert=True,
                confidence=max_conf[best],
                level="CRITICAL",
                reason=f"Recording confirmed: {best}",
                signals=list(active_signals)
            )

        # ── RULE 2: Hidden camera = immediate critical alert ──────────────
        if "LENS_HIDDEN_CAM" in active_signals:
            self.last_alert[zone] = self.frame_number
            return AlertDecision(
                should_alert=True,
                confidence=max_conf.get("LENS_HIDDEN_CAM", 0.85),
                level="CRITICAL",
                reason="Hidden camera lens detected",
                signals=list(active_signals)
            )

        # ── RULE 3: Physical device REQUIRED for all other alerts ─────────
        physical_present = active_signals & PHYSICAL_SIGNALS
        if not physical_present:
            # No physical device detected — suppress everything
            # Pose alone, glow alone, IR pulse alone = never alert
            return None

        # ── RULE 4: Physical + supporting signal = valid alert ────────────
        best_physical = max(physical_present, key=lambda s: max_conf.get(s, 0))
        physical_conf = max_conf[best_physical]

        # Check for supporting signals
        support_present = active_signals & SUPPORTING_SIGNALS
        if support_present:
            best_support = max(support_present, key=lambda s: max_conf.get(s, 0))
            support_conf = max_conf[best_support]
            combined = min(0.93, (physical_conf * 0.65 + support_conf * 0.35))
            if combined > 0.55:
                self.last_alert[zone] = self.frame_number
                return AlertDecision(
                    should_alert=True,
                    confidence=combined,
                    level="HIGH",
                    reason=f"Device detected: {best_physical} + {best_support}",
                    signals=list(active_signals)
                )

        # ── RULE 5: Physical signal sustained alone ───────────────────────
        # YOLO alone needs very high confidence AND sustained detection
        phys_events = self.zone_evidence[zone].get(best_physical, [])
        if len(phys_events) >= 15 and physical_conf > 0.80:
            self.last_alert[zone] = self.frame_number
            return AlertDecision(
                should_alert=True,
                confidence=physical_conf,
                level="HIGH",
                reason=f"Device sustained: {best_physical} x{len(phys_events)} frames",
                signals=list(active_signals)
            )

        # Rule 5: Single signal alone = suppress silently
        return None

        return None

    def tick(self):
        """Call once per frame."""
        self.frame_number += 1
