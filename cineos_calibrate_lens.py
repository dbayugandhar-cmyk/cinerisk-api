#!/usr/bin/env python3
"""
cineos_calibrate_lens.py — Camera-to-seat homography calibration
=================================================================
Run ONCE per screen at install time.
Click 4 known seat positions in the camera frame.
Writes a transform matrix to lens_config.json.
After calibration, every pixel coordinate maps to a row/seat automatically.

Usage:
  python3 cineos_calibrate_lens.py --screen "Screen 1" --camera 0
  python3 cineos_calibrate_lens.py --screen "Screen 4" --rtsp "rtsp://192.168.1.10/stream"
  python3 cineos_calibrate_lens.py --verify   # verify existing calibration
  python3 cineos_calibrate_lens.py --list     # list all calibrated screens

Controls during calibration:
  Click a seat in the camera view → enter its row/seat when prompted
  Press C to confirm 4 points → computes homography
  Press R to reset and start over
  Press Q to quit
"""

import cv2
import numpy as np
import json
import argparse
import os
import sys
import time
from datetime import datetime

CONFIG_FILE = os.path.expanduser("~/Desktop/cinerisk/lens_config.json")

# ── Theater layout (customise per venue) ──────────────────────────
THEATER_LAYOUT = {
    "rows": list("ABCDEFGHIJKL"),   # 12 rows A-L
    "cols": 12,                      # 12 seats per row
    "row_pitch_mm": 900,             # 900mm between rows
    "seat_pitch_mm": 550,            # 550mm between seats
    "screen_to_row_a_mm": 3500,      # 3.5m from screen to first row
}


# ── Load / save config ─────────────────────────────────────────────

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"screens": {}, "version": 2}

def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"  Saved: {CONFIG_FILE}")


# ── Seat coordinate system ─────────────────────────────────────────

def seat_to_world(row_letter: str, seat_num: int, layout: dict) -> tuple:
    """Convert row/seat to real-world mm coordinates (origin = seat A1)."""
    row_idx = layout["rows"].index(row_letter.upper())
    x_mm = (seat_num - 1) * layout["seat_pitch_mm"]
    y_mm = row_idx * layout["row_pitch_mm"]
    return (float(x_mm), float(y_mm))

def world_to_seat(x_mm: float, y_mm: float, layout: dict) -> tuple:
    """Convert world mm coordinates back to row/seat."""
    row_idx = int(round(y_mm / layout["row_pitch_mm"]))
    seat_num = int(round(x_mm / layout["seat_pitch_mm"])) + 1
    rows = layout["rows"]
    row_idx = max(0, min(len(rows)-1, row_idx))
    seat_num = max(1, min(layout["cols"], seat_num))
    return rows[row_idx], seat_num

def pixel_to_seat(px: float, py: float, H: np.ndarray, layout: dict) -> tuple:
    """Map pixel (px,py) → (row_letter, seat_number) using homography H."""
    pt = np.array([[[px, py]]], dtype=np.float32)
    world = cv2.perspectiveTransform(pt, H)[0][0]
    return world_to_seat(float(world[0]), float(world[1]), layout)


# ── Calibration UI ─────────────────────────────────────────────────

class CalibrationUI:
    def __init__(self, screen_name: str, source, layout: dict):
        self.screen_name = screen_name
        self.layout = layout
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            print(f"ERROR: Cannot open source '{source}'")
            sys.exit(1)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self.click_points = []   # list of (px, py, row, seat)
        self.frame = None
        self.win = f"CINEOS Calibration — {screen_name}"
        cv2.namedWindow(self.win, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.win, self._on_click)

    def _on_click(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(self.click_points) < 4:
            print(f"\n  Clicked pixel ({x}, {y})")
            row = input("  Enter row letter (A-L): ").strip().upper()
            seat = input("  Enter seat number (1-12): ").strip()
            if row in self.layout["rows"] and seat.isdigit():
                self.click_points.append((x, y, row, int(seat)))
                print(f"  Saved: pixel ({x},{y}) → seat {row}{seat}  [{len(self.click_points)}/4]")
            else:
                print("  Invalid input — try again")

    def _draw_overlay(self, frame):
        out = frame.copy()
        h, w = out.shape[:2]

        # Instructions
        lines = [
            f"CINEOS — {self.screen_name} calibration",
            f"Click 4 known seats in the frame. [{len(self.click_points)}/4 captured]",
            "C=compute  R=reset  Q=quit",
        ]
        for i, l in enumerate(lines):
            cv2.putText(out, l, (12, 24 + i*20),
                        cv2.FONT_HERSHEY_PLAIN, 0.48,
                        (0, 200, 140) if i == 0 else (180, 180, 180), 1)

        # Draw clicked points
        colors = [(0,200,140),(0,140,255),(255,140,0),(200,0,200)]
        for i, (px, py, row, seat) in enumerate(self.click_points):
            col = colors[i]
            cv2.circle(out, (px, py), 8, col, 2)
            cv2.circle(out, (px, py), 3, col, -1)
            cv2.putText(out, f"{row}{seat}", (px+10, py-6),
                        cv2.FONT_HERSHEY_PLAIN, 0.52, col, 1)

        # Seat grid overlay once homography is computed
        if hasattr(self, 'H') and self.H is not None:
            self._draw_seat_grid(out, w, h)

        return out

    def _draw_seat_grid(self, out, w, h):
        """Project the seat grid onto the camera frame for verification."""
        layout = self.layout
        H_inv = np.linalg.inv(self.H)
        for ri, row in enumerate(layout["rows"]):
            for ci in range(layout["cols"]):
                seat_num = ci + 1
                xw, yw = seat_to_world(row, seat_num, layout)
                pt = np.array([[[xw, yw]]], dtype=np.float32)
                px_pt = cv2.perspectiveTransform(pt, H_inv)[0][0]
                px, py = int(px_pt[0]), int(px_pt[1])
                if 0 <= px < w and 0 <= py < h:
                    cv2.circle(out, (px, py), 2, (0, 200, 140), -1)
                    if ci == 0:
                        cv2.putText(out, row, (px-14, py+4),
                                    cv2.FONT_HERSHEY_PLAIN, 0.35, (0, 160, 100), 1)

    def compute_homography(self):
        """Compute pixel→world homography from 4 point pairs."""
        if len(self.click_points) < 4:
            print(f"  Need 4 points, have {len(self.click_points)}")
            return None

        src_pts = np.array([[p[0], p[1]] for p in self.click_points], dtype=np.float32)
        dst_pts = np.array([seat_to_world(p[2], p[3], self.layout)
                            for p in self.click_points], dtype=np.float32)

        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if H is None:
            print("  ERROR: Homography failed — points may be collinear")
            return None

        # Validate — reproject each point
        print("\n  Validation (reprojection error):")
        errors = []
        for (px, py, row, seat) in self.click_points:
            r, s = pixel_to_seat(px, py, H, self.layout)
            ok = r == row and s == seat
            err = "OK" if ok else f"GOT {r}{s}"
            print(f"    Click ({px},{py}) → expected {row}{seat} → {err}")
            errors.append(0 if ok else 1)

        self.H = H
        return H

    def run(self):
        print(f"\n{'='*55}")
        print(f"  CINEOS Lens Calibration — {self.screen_name}")
        print(f"{'='*55}")
        print(f"  1. Set up camera pointing at the theater seats")
        print(f"  2. Click on 4 seats you can POSITIVELY IDENTIFY")
        print(f"     (e.g. Row A Seat 1, Row A Seat 12, Row L Seat 1, Row G Seat 6)")
        print(f"  3. Enter the row letter and seat number for each")
        print(f"  4. Press C to compute the homography")
        print(f"  5. Verify the green grid overlays on the correct seats")
        print(f"{'='*55}\n")

        self.H = None

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            self.frame = frame
            vis = self._draw_overlay(frame)
            cv2.imshow(self.win, vis)

            key = cv2.waitKey(30) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                self.click_points = []
                self.H = None
                print("  Reset — start over")
            elif key == ord('c'):
                if len(self.click_points) >= 4:
                    H = self.compute_homography()
                    if H is not None:
                        print(f"\n  Homography computed. Check green grid overlay.")
                        print(f"  Press S to save, R to reset, Q to quit.")
                else:
                    print(f"  Need 4 points ({len(self.click_points)} captured)")
            elif key == ord('s'):
                if self.H is not None:
                    self.cap.release()
                    cv2.destroyAllWindows()
                    return self.H, self.click_points

        self.cap.release()
        cv2.destroyAllWindows()
        return None, []


# ── Verification mode ──────────────────────────────────────────────

def verify_calibration(screen_name: str, source, cfg: dict):
    """Live verification — shows seat label under cursor."""
    if screen_name not in cfg["screens"]:
        print(f"  No calibration found for '{screen_name}'")
        return

    sc_cfg = cfg["screens"][screen_name]
    H = np.array(sc_cfg["homography"], dtype=np.float64)
    layout = sc_cfg.get("layout", THEATER_LAYOUT)

    cap = cv2.VideoCapture(source)
    win = f"CINEOS Verify — {screen_name}"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    mouse_pos = [0, 0]
    def on_mouse(event, x, y, *_): mouse_pos[0]=x; mouse_pos[1]=y
    cv2.setMouseCallback(win, on_mouse)

    print(f"\n  Verifying {screen_name} — move mouse over seats to see row/seat")
    print(f"  Press Q to quit\n")

    while True:
        ret, frame = cap.read()
        if not ret: break
        out = frame.copy()
        h, w = out.shape[:2]

        # Draw grid
        H_inv = np.linalg.inv(H)
        for ri, row in enumerate(layout["rows"]):
            for ci in range(layout["cols"]):
                xw, yw = seat_to_world(row, ci+1, layout)
                pt = np.array([[[xw, yw]]], dtype=np.float32)
                px_pt = cv2.perspectiveTransform(pt, H_inv)[0][0]
                px, py = int(px_pt[0]), int(px_pt[1])
                if 0 <= px < w and 0 <= py < h:
                    cv2.circle(out, (px, py), 2, (0, 200, 140), -1)

        # Seat under cursor
        mx, my = mouse_pos
        try:
            r, s = pixel_to_seat(mx, my, H, layout)
            label = f"Row {r} · Seat {s}"
            cv2.putText(out, label, (mx+12, my-8),
                        cv2.FONT_HERSHEY_PLAIN, 0.55, (0, 200, 140), 1)
            cv2.circle(out, (mx, my), 5, (0, 200, 140), 2)
        except: pass

        cv2.putText(out, f"VERIFYING: {screen_name} — move mouse over seats",
                    (12, 22), cv2.FONT_HERSHEY_PLAIN, 0.45, (0, 200, 140), 1)
        cv2.putText(out, "Q=quit", (12, 42), cv2.FONT_HERSHEY_PLAIN, 0.40, (120,120,120), 1)

        cv2.imshow(win, out)
        if cv2.waitKey(30) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()


# ── Main ───────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="CINEOS Lens Calibration")
    ap.add_argument("--screen",  default="Screen 1")
    ap.add_argument("--camera",  type=int, default=0)
    ap.add_argument("--rtsp",    type=str, default=None)
    ap.add_argument("--verify",  action="store_true")
    ap.add_argument("--list",    action="store_true")
    ap.add_argument("--rows",    type=int, default=12)
    ap.add_argument("--cols",    type=int, default=12)
    args = ap.parse_args()

    cfg = load_config()

    if args.list:
        print(f"\n  Calibrated screens ({len(cfg['screens'])}):")
        for name, sc in cfg["screens"].items():
            ts = sc.get("calibrated_at", "unknown")
            pts = len(sc.get("click_points", []))
            print(f"    {name:20s} — {pts} ref points — {ts[:10]}")
        return

    source = args.rtsp if args.rtsp else args.camera
    layout = dict(THEATER_LAYOUT)
    layout["rows"] = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")[:args.rows]
    layout["cols"] = args.cols

    if args.verify:
        verify_calibration(args.screen, source, cfg)
        return

    # Run calibration UI
    ui = CalibrationUI(args.screen, source, layout)
    H, click_points = ui.run()

    if H is None:
        print("\n  Calibration cancelled.")
        return

    # Save to config
    cfg["screens"][args.screen] = {
        "homography": H.tolist(),
        "layout": layout,
        "click_points": [
            {"px": p[0], "py": p[1], "row": p[2], "seat": p[3]}
            for p in click_points
        ],
        "calibrated_at": datetime.now().isoformat(),
        "source": str(source),
    }
    save_config(cfg)

    print(f"\n{'='*55}")
    print(f"  Calibration saved for {args.screen}")
    print(f"  Now run the detector with lens_config.json loaded:")
    print(f"  THEATER_NAME='Test Theater' SCREEN_NUMBER='{args.screen}' \\")
    print(f"  python3 theater/detector_rtsp.py {source}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
