"""
CINEOS Alert Gate
=================
Core rule: Physical device MUST be detected for any alert.
Pose/glow/IR pulse alone = never alert.

US Prov. Pat. 64/049,190
"""

from dataclasses import dataclass
from typing import Optional


# Physical device signals — anchor signals
# A device MUST be present for any alert
PHYSICAL_SIGNALS = {
    "PHONE",
    "LENS_REFLECTION",
    "LENS_IPHONE_PRO",
    "LENS_CAMCORDER",
    "LENS_HIDDEN_CAM",
    "LENS_PHONE_SINGLE",
    "LENS_PHONE_DUAL",
    "LENS_PHONE_TRIPLE",
    "LENS_PHONE_QUAD",
}

# Supporting signals — boost confidence only, never alert alone
SUPPORTING_SIGNALS = {
    "PHONE_RAISED",
    "CAMCORDER_POSITION",
    "RECORDING_POSITION",
    "PHONE_GLOW",
    "IR_AF_PULSE",
}

# Already confirmed — immediate alert
CONFIRMED_SIGNALS = {
    "RECORDING_CONFIRMED",
}

# Valid alert pairs — ALL require a physical signal
VALID_PAIRS = {
    frozenset({"PHONE", "PHONE_RAISED"}),
    frozenset({"PHONE", "CAMCORDER_POSITION"}),
    frozenset({"PHONE", "PHONE_GLOW"}),
    frozenset({"PHONE", "IR_AF_PULSE"}),
    frozenset({"PHONE", "LENS_REFLECTION"}),
    frozenset({"LENS_REFLECTION", "PHONE_RAISED"}),
    frozenset({"LENS_REFLECTION", "IR_AF_PULSE"}),
    frozenset({"LENS_REFLECTION", "PHONE_GLOW"}),
    frozenset({"LENS_CAMCORDER", "PHONE_RAISED"}),
    frozenset({"LENS_CAMCORDER", "IR_AF_PULSE"}),
}


@dataclass
class AlertDecision:
    should_alert: bool
    confidence: float
    level: str
    reason: str
    signals: list


class AlertGate:
    """
    Multi-signal gate. Physical device required for all alerts.
    Pose alone, glow alone, IR pulse alone = never alert.
    """

    def __init__(self, window_seconds=8.0, fps=30):
        self.window_frames = int(window_seconds * fps)
        self.zone_evidence = {}
        self.frame_number = 0
        self.last_alert = {}
        self.alert_cooldown = int(10.0 * fps)

    def add_signal(self, zone: str, signal_type: str,
                   confidence: float) -> Optional[AlertDecision]:
        if zone not in self.zone_evidence:
            self.zone_evidence[zone] = {}

        if signal_type not in self.zone_evidence[zone]:
            self.zone_evidence[zone][signal_type] = []

        self.zone_evidence[zone][signal_type].append({
            "frame": self.frame_number,
            "confidence": confidence
        })

        # Clean old evidence
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
        # Cooldown check
        if self.frame_number - self.last_alert.get(zone, -999) < self.alert_cooldown:
            return None

        active_signals = set(self.zone_evidence.get(zone, {}).keys())
        if not active_signals:
            return None

        # Max confidence per signal
        max_conf = {}
        for sig, events in self.zone_evidence.get(zone, {}).items():
            max_conf[sig] = max(e["confidence"] for e in events)

        # Rule 1 — Already confirmed
        if active_signals & CONFIRMED_SIGNALS:
            best = max(active_signals & CONFIRMED_SIGNALS,
                      key=lambda s: max_conf.get(s, 0))
            self.last_alert[zone] = self.frame_number
            return AlertDecision(True, max_conf[best], "CRITICAL",
                               f"Recording confirmed: {best}",
                               list(active_signals))

        # Rule 2 — Hidden camera immediate alert
        if "LENS_HIDDEN_CAM" in active_signals:
            self.last_alert[zone] = self.frame_number
            return AlertDecision(True, max_conf.get("LENS_HIDDEN_CAM", 0.85),
                               "CRITICAL", "Hidden camera lens detected",
                               list(active_signals))

        # Rule 3 — Physical device REQUIRED
        physical_present = active_signals & PHYSICAL_SIGNALS
        if not physical_present:
            return None  # No device = no alert, no matter what else fires

        best_physical = max(physical_present, key=lambda s: max_conf.get(s, 0))
        physical_conf = max_conf[best_physical]

        # Rule 4 — Physical + supporting signal
        support_present = active_signals & SUPPORTING_SIGNALS
        if support_present:
            best_support = max(support_present, key=lambda s: max_conf.get(s, 0))
            support_conf = max_conf[best_support]
            combined = min(0.93, physical_conf * 0.65 + support_conf * 0.35)
            if combined > 0.65:  # Higher threshold — device+support must both be strong
                self.last_alert[zone] = self.frame_number
                return AlertDecision(True, combined, "HIGH",
                                   f"Device: {best_physical} + {best_support}",
                                   list(active_signals))

        # Rule 5 — Physical signal sustained alone (high confidence)
        phys_events = self.zone_evidence[zone].get(best_physical, [])
        if len(phys_events) >= 15 and physical_conf > 0.80:
            self.last_alert[zone] = self.frame_number
            return AlertDecision(True, physical_conf, "HIGH",
                               f"Device sustained: {best_physical} x{len(phys_events)}",
                               list(active_signals))

        return None  # Not enough evidence yet

    def tick(self):
        self.frame_number += 1
