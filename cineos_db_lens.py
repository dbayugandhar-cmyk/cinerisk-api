#!/usr/bin/env python3
"""
cineos_db_lens.py — Create lens_incidents table + wire detector to DB
=====================================================================
Usage:
  python3 cineos_db_lens.py --migrate        # create table in Railway DB
  python3 cineos_db_lens.py --status         # check table + row count
  python3 cineos_db_lens.py --query          # query recent incidents
  python3 cineos_db_lens.py --match SCREEN_ID SHOWTIME  # match watermark
  python3 cineos_db_lens.py --export         # export incidents to CSV
  python3 cineos_db_lens.py --patch          # patch detector_rtsp.py to write to DB
"""

import asyncio
import asyncpg
import os
import sys
import json
import argparse
import csv
from datetime import datetime, timezone, timedelta

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "${DATABASE_URL}"
)

# ── SQL schema ────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lens_incidents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theater_name    TEXT NOT NULL,
    screen_number   TEXT NOT NULL,
    film_title      TEXT NOT NULL,
    showtime        TIMESTAMPTZ,

    -- Seat precision
    seat_row        TEXT,           -- 'G'
    seat_number     INTEGER,        -- 14
    seat_id         TEXT,           -- 'G14'
    pixel_x         INTEGER,        -- raw camera pixel
    pixel_y         INTEGER,

    -- Lens classification
    device_type     TEXT,           -- PHONE / CAMCORDER / DSLR / UNKNOWN
    lens_area_px    FLOAT,          -- contour area in pixels
    lens_aperture_mm FLOAT,         -- estimated aperture in mm
    circularity     FLOAT,          -- 0-1, higher = more lens-like
    brightness_ratio FLOAT,         -- spot vs surrounding brightness
    confidence      FLOAT,          -- fused confidence 0-1

    -- Duration tracking
    first_seen      TIMESTAMPTZ DEFAULT NOW(),
    last_seen       TIMESTAMPTZ DEFAULT NOW(),
    duration_seconds FLOAT DEFAULT 0,
    sustained_frames INTEGER DEFAULT 0,

    -- Evidence
    ir_frame_path   TEXT,           -- S3 path to captured IR frame
    alerted         BOOLEAN DEFAULT FALSE,
    alert_sent_at   TIMESTAMPTZ,
    staff_action    TEXT,

    -- Watermark match
    watermark_screen_id TEXT,       -- decoded from piracy copy
    watermark_match BOOLEAN DEFAULT FALSE,
    matched_at      TIMESTAMPTZ,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_lens_screen_time
    ON lens_incidents (screen_number, first_seen);

CREATE INDEX IF NOT EXISTS idx_lens_film_time
    ON lens_incidents (film_title, first_seen);

CREATE INDEX IF NOT EXISTS idx_lens_seat
    ON lens_incidents (seat_row, seat_number);

CREATE INDEX IF NOT EXISTS idx_lens_device
    ON lens_incidents (device_type, confidence);

CREATE INDEX IF NOT EXISTS idx_lens_watermark
    ON lens_incidents (watermark_screen_id) WHERE watermark_screen_id IS NOT NULL;

-- View: active high-threat incidents
CREATE OR REPLACE VIEW lens_active_threats AS
SELECT
    theater_name,
    screen_number,
    film_title,
    seat_id,
    device_type,
    ROUND(lens_aperture_mm::numeric, 1) AS aperture_mm,
    ROUND(confidence::numeric, 3) AS conf,
    ROUND(duration_seconds::numeric, 0) AS duration_s,
    first_seen,
    alerted
FROM lens_incidents
WHERE
    first_seen > NOW() - INTERVAL '4 hours'
    AND confidence >= 0.65
ORDER BY
    CASE device_type WHEN 'DSLR' THEN 1 WHEN 'CAMCORDER' THEN 2 ELSE 3 END,
    lens_aperture_mm DESC,
    duration_seconds DESC;

-- View: watermark match candidates
CREATE OR REPLACE VIEW lens_match_candidates AS
SELECT
    id,
    screen_number,
    film_title,
    seat_id,
    device_type,
    lens_aperture_mm,
    duration_seconds,
    confidence,
    first_seen,
    last_seen,
    ir_frame_path
FROM lens_incidents
WHERE
    confidence >= 0.70
    AND duration_seconds >= 30
ORDER BY lens_aperture_mm DESC, duration_seconds DESC;
"""

UPDATE_DURATION_SQL = """
INSERT INTO lens_incidents (
    theater_name, screen_number, film_title,
    seat_row, seat_number, seat_id, pixel_x, pixel_y,
    device_type, lens_area_px, lens_aperture_mm,
    circularity, brightness_ratio, confidence,
    duration_seconds, sustained_frames,
    alerted, staff_action
) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
ON CONFLICT DO NOTHING
RETURNING id;
"""


# ── DB helpers ────────────────────────────────────────────────────

async def get_conn():
    try:
        return await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"  DB connect error: {e}")
        return None


async def migrate():
    conn = await get_conn()
    if not conn: return False
    try:
        await conn.execute(SCHEMA_SQL)
        print("  Migration complete — lens_incidents table ready")
        return True
    except Exception as e:
        print(f"  Migration error: {e}")
        return False
    finally:
        await conn.close()


async def status():
    conn = await get_conn()
    if not conn: return
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM lens_incidents")
        today = await conn.fetchval(
            "SELECT COUNT(*) FROM lens_incidents WHERE created_at > NOW() - INTERVAL '24 hours'"
        )
        critical = await conn.fetchval(
            "SELECT COUNT(*) FROM lens_incidents WHERE device_type IN ('DSLR','CAMCORDER') AND created_at > NOW() - INTERVAL '24 hours'"
        )
        avg_conf = await conn.fetchval(
            "SELECT ROUND(AVG(confidence)::numeric, 3) FROM lens_incidents WHERE created_at > NOW() - INTERVAL '24 hours'"
        )
        print(f"\n  lens_incidents table:")
        print(f"    Total rows      : {count}")
        print(f"    Last 24h        : {today}")
        print(f"    Critical (24h)  : {critical}")
        print(f"    Avg confidence  : {avg_conf}")
    except Exception as e:
        print(f"  Status error: {e}")
    finally:
        await conn.close()


async def query_recent(limit=20):
    conn = await get_conn()
    if not conn: return
    try:
        rows = await conn.fetch(f"""
            SELECT screen_number, film_title, seat_id, device_type,
                   ROUND(lens_aperture_mm::numeric,1) as aperture,
                   ROUND(duration_seconds::numeric,0) as dur,
                   ROUND(confidence::numeric,2) as conf,
                   first_seen
            FROM lens_incidents
            ORDER BY first_seen DESC
            LIMIT {limit}
        """)
        print(f"\n  {'Screen':12} {'Film':22} {'Seat':6} {'Device':10} {'Aperture':10} {'Dur':6} {'Conf':6} {'Time'}")
        print(f"  {'-'*90}")
        for r in rows:
            print(f"  {r['screen_number']:12} {r['film_title'][:20]:22} {str(r['seat_id']):6} "
                  f"{str(r['device_type']):10} {str(r['aperture'])+'mm':10} "
                  f"{str(r['dur'])+'s':6} {str(r['conf']):6} "
                  f"{r['first_seen'].strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"  Query error: {e}")
    finally:
        await conn.close()


async def watermark_match(screen_id: str, showtime: str, window_minutes: int = 30):
    """
    Match a decoded watermark to lens incidents.
    screen_id: decoded from piracy copy watermark
    showtime:  ISO timestamp of the screening
    """
    conn = await get_conn()
    if not conn: return
    try:
        dt = datetime.fromisoformat(showtime)
        dt_end = dt + timedelta(minutes=window_minutes)

        rows = await conn.fetch("""
            SELECT
                id, seat_row, seat_number, seat_id,
                device_type, lens_aperture_mm, duration_seconds,
                confidence, first_seen, last_seen, ir_frame_path
            FROM lens_incidents
            WHERE
                screen_number = $1
                AND first_seen BETWEEN $2 AND $3
                AND confidence >= 0.65
            ORDER BY
                CASE device_type WHEN 'DSLR' THEN 1 WHEN 'CAMCORDER' THEN 2 ELSE 3 END,
                lens_aperture_mm DESC,
                duration_seconds DESC
        """, screen_id, dt, dt_end)

        print(f"\n{'='*65}")
        print(f"  WATERMARK MATCH RESULTS")
        print(f"  Screen: {screen_id}  |  Showtime: {showtime}")
        print(f"  Window: {window_minutes} minutes  |  Candidates: {len(rows)}")
        print(f"{'='*65}")

        if not rows:
            print(f"  No matches found in this window.")
            return

        for i, r in enumerate(rows, 1):
            threat = "CRITICAL" if r['device_type'] in ('DSLR','CAMCORDER') else "WARNING"
            print(f"\n  #{i} — {threat}")
            print(f"    Seat           : Row {r['seat_row']} · Seat {r['seat_number']} ({r['seat_id']})")
            print(f"    Device         : {r['device_type']}")
            print(f"    Lens aperture  : ~{r['lens_aperture_mm']:.1f}mm")
            print(f"    Duration       : {r['duration_seconds']:.0f} seconds pointing at screen")
            print(f"    Confidence     : {r['confidence']:.0%}")
            print(f"    First seen     : {r['first_seen'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Last seen      : {r['last_seen'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    IR frame       : {r['ir_frame_path'] or 'not saved'}")

            # Mark as matched
            await conn.execute("""
                UPDATE lens_incidents
                SET watermark_screen_id=$1, watermark_match=true, matched_at=NOW()
                WHERE id=$2
            """, screen_id, r['id'])

        print(f"\n  {len(rows)} candidate(s) marked as watermark match in DB.")
        print(f"{'='*65}\n")

    except Exception as e:
        print(f"  Match error: {e}")
    finally:
        await conn.close()


async def export_csv(out_path: str = "lens_incidents_export.csv"):
    conn = await get_conn()
    if not conn: return
    try:
        rows = await conn.fetch("SELECT * FROM lens_incidents ORDER BY first_seen DESC")
        if not rows:
            print("  No data to export"); return
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows([dict(r) for r in rows])
        print(f"  Exported {len(rows)} rows to {out_path}")
    except Exception as e:
        print(f"  Export error: {e}")
    finally:
        await conn.close()


# ── Write incident to DB (called from detector_rtsp.py) ───────────

async def write_lens_incident(
    theater: str, screen: str, film: str,
    seat_row: str, seat_num: int,
    pixel_x: int, pixel_y: int,
    device_type: str, lens_area: float, lens_aperture_mm: float,
    circularity: float, brightness_ratio: float, confidence: float,
    duration_sec: float, frames: int,
    alerted: bool = False, staff_action: str = None,
    db_url: str = None
) -> str:
    """Insert a lens incident into the DB. Returns incident UUID."""
    url = db_url or DATABASE_URL
    seat_id = f"{seat_row}{seat_num}" if seat_row else None
    try:
        conn = await asyncpg.connect(url)
        row = await conn.fetchrow(UPDATE_DURATION_SQL,
            theater, screen, film,
            seat_row, seat_num, seat_id, pixel_x, pixel_y,
            device_type, lens_area, lens_aperture_mm,
            circularity, brightness_ratio, confidence,
            duration_sec, frames,
            alerted, staff_action
        )
        await conn.close()
        return str(row['id']) if row else None
    except Exception as e:
        print(f"[DB] write_lens_incident error: {e}")
        return None


# ── Patch detector_rtsp.py ────────────────────────────────────────

DETECTOR_PATCH = '''
# ── CINEOS Lens DB integration (auto-patched by cineos_db_lens.py) ──
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
try:
    from cineos_db_lens import write_lens_incident as _write_lens_db
    from cineos_calibrate_lens import pixel_to_seat as _pixel_to_seat
    import numpy as _np
    _LENS_DB_AVAILABLE = True
    _lens_config = None
    _lens_config_path = os.path.expanduser('~/Desktop/cinerisk/lens_config.json')
    if os.path.exists(_lens_config_path):
        import json as _json
        _cfg = _json.load(open(_lens_config_path))
        if SCREEN in _cfg.get('screens', {}):
            _sc = _cfg['screens'][SCREEN]
            _lens_H = _np.array(_sc['homography'], dtype=_np.float64)
            _lens_layout = _sc['layout']
            _lens_config = {'H': _lens_H, 'layout': _lens_layout}
            print(f"[CINEOS] Lens calibration loaded for {SCREEN}")
        else:
            print(f"[CINEOS] No calibration for {SCREEN} — seat mapping disabled")
    else:
        print("[CINEOS] No lens_config.json — run cineos_calibrate_lens.py first")
    _LENS_DB_AVAILABLE = True
except ImportError as _e:
    _LENS_DB_AVAILABLE = False
    _lens_config = None
    print(f"[CINEOS] Lens DB not available: {_e}")

def _classify_lens_device(area_px: float, aperture_mm: float) -> str:
    """Classify device from lens aperture size."""
    if aperture_mm >= 12: return "DSLR"
    if aperture_mm >= 6:  return "CAMCORDER"
    if aperture_mm >= 2:  return "PHONE"
    return "UNKNOWN"

def _estimate_aperture_mm(area_px: float, distance_m: float = 8.0,
                           focal_length_mm: float = 4.0,
                           sensor_width_mm: float = 6.0,
                           frame_width_px: int = 1280) -> float:
    """
    Estimate real-world lens aperture in mm from pixel area.
    Based on: apparent_size = real_size * focal / distance
    At 8m with a 4mm focal length CCTV camera:
    A 5mm aperture phone lens appears as ~0.6mm on sensor = ~130px^2 at 1280px wide.
    """
    px_per_mm = frame_width_px / (distance_m * 1000 * sensor_width_mm / focal_length_mm)
    radius_px = (area_px / 3.14159) ** 0.5
    return round(radius_px / px_per_mm, 2)
'''

DETECTOR_WRITE_PATCH = '''
                        # ── Write lens detection to DB ──
                        if _LENS_DB_AVAILABLE:
                            _aperture = _estimate_aperture_mm(lens.get('area', 10), distance_m=8.0)
                            _device   = _classify_lens_device(lens.get('area', 10), _aperture)
                            _row, _seat_num = None, None
                            if _lens_config:
                                try:
                                    _row, _seat_num = _pixel_to_seat(
                                        lens['x'], lens['y'],
                                        _lens_config['H'], _lens_config['layout']
                                    )
                                except: pass
                            _inc_data = dict(
                                theater=THEATER, screen=SCREEN, film=FILM,
                                seat_row=_row, seat_num=_seat_num or 0,
                                pixel_x=int(lens['x']), pixel_y=int(lens['y']),
                                device_type=_device,
                                lens_area=float(lens.get('area', 0)),
                                lens_aperture_mm=_aperture,
                                circularity=float(lens.get('circularity', 0)),
                                brightness_ratio=float(lens.get('brightness_ratio', 0)),
                                confidence=float(lens.get('confidence', 0)),
                                duration_sec=0.0, frames=1,
                                alerted=False
                            )
                            loop.run_until_complete(write_lens_incident(**_inc_data))
                            _seat_str = f"Row {_row} Seat {_seat_num}" if _row else "unknown seat"
                            print(f"[DB] Lens written — {_device} ~{_aperture}mm @ {_seat_str}")
'''


def patch_detector():
    detector_path = os.path.expanduser("~/Desktop/cinerisk/theater/detector_rtsp.py")
    if not os.path.exists(detector_path):
        print(f"  ERROR: {detector_path} not found"); return

    src = open(detector_path).read()

    if "write_lens_incident" in src:
        print("  detector_rtsp.py already patched for lens DB writing")
        return

    # Insert import patch after the existing imports section
    insert_after = "from session_tracker import update_session, get_active_sessions"
    if insert_after not in src:
        print(f"  WARNING: Could not find insertion point — check detector_rtsp.py")
        print(f"  Add this manually after your imports:\n{DETECTOR_PATCH}")
        return

    src = src.replace(insert_after, insert_after + "\n" + DETECTOR_PATCH, 1)

    # Insert DB write after lens confirmation
    write_after = "loop.run_until_complete(report_incident(\n                    lens[\"zone\"],\n                    lens[\"confidence\"],\n                    detection_type=f\"LENS_{device_type}\"\n                ))"
    if write_after in src:
        src = src.replace(write_after, write_after + DETECTOR_WRITE_PATCH, 1)
        print("  Patched: lens DB write added after lens detection")
    else:
        print("  WARNING: Could not find lens detection block — add DB write manually")

    open(detector_path, "w").write(src)
    print(f"  detector_rtsp.py patched successfully")


# ── Main ───────────────────────────────────────────────────────────

async def run(args):
    print(f"\n{'='*55}")
    print(f"  CINEOS Lens DB")
    print(f"  {DATABASE_URL[:50]}...")
    print(f"{'='*55}")

    if args.migrate:
        await migrate()
    elif args.status:
        await status()
    elif args.query:
        await query_recent()
    elif args.match:
        screen_id, showtime = args.match[0], args.match[1]
        window = int(args.match[2]) if len(args.match) > 2 else 30
        await watermark_match(screen_id, showtime, window)
    elif args.export:
        await export_csv()
    elif args.patch:
        patch_detector()
    else:
        # Default: migrate + status
        await migrate()
        await status()

    print()

def main():
    ap = argparse.ArgumentParser(description="CINEOS Lens DB")
    ap.add_argument("--migrate", action="store_true", help="Create table")
    ap.add_argument("--status",  action="store_true", help="Show table stats")
    ap.add_argument("--query",   action="store_true", help="Show recent incidents")
    ap.add_argument("--match",   nargs="+", metavar=("SCREEN","SHOWTIME"),
                    help="Match watermark: SCREEN SHOWTIME [WINDOW_MINUTES]")
    ap.add_argument("--export",  action="store_true", help="Export to CSV")
    ap.add_argument("--patch",   action="store_true", help="Patch detector_rtsp.py")
    args = ap.parse_args()
    asyncio.run(run(args))

if __name__ == "__main__":
    main()
