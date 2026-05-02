"""
CINEOS → CineRisk Feedback Bridge (Layer 3)
============================================
Queries Supabase for observed incident data.
Compares predicted leak_day (Layer 1) vs observed first incident (Layer 2).
Outputs calibration deltas to improve the engine over time.

Run manually or as a scheduled job (daily):
  python3 feedback_bridge.py

Or via cron:
  0 6 * * * cd ~/Desktop/cinerisk && python3 feedback_bridge.py >> feedback.log 2>&1
"""

import os, json, httpx
from datetime import datetime

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://fuaybehxfusfywghuxwp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1YXliZWh4ZnVzZnl3Z2h1eHdwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcxNTIzNDgsImV4cCI6MjA5MjcyODM0OH0.mbYxdL8NilgZOT4_vyWGK73h64UVxqCpT5SEzO3Kcks")
CINERISK_API = os.getenv("CINERISK_API", "http://localhost:8000")

def run():
    print(f"\nCINEOS Feedback Bridge — Layer 3")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Pull screenings that have associated incidents
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

    with httpx.Client(timeout=10.0) as client:
        # Get all screenings
        r = client.get(f"{SUPABASE_URL}/rest/v1/screenings?select=*&limit=100",
                       headers=headers)
        screenings = r.json() if r.status_code == 200 else []

        # Get all incidents
        r = client.get(f"{SUPABASE_URL}/rest/v1/incidents?select=*&order=detected_at.asc&limit=1000",
                       headers=headers)
        incidents = r.json() if r.status_code == 200 else []

    if not screenings or not incidents:
        print("  No data available for calibration yet.")
        print("  Need at least 1 screening and 1 incident to run Layer 3.\n")
        return

    print(f"  Screenings: {len(screenings)}")
    print(f"  Incidents:  {len(incidents)}\n")

    calibration_data = []

    # Group incidents by film
    film_incidents = {}
    for inc in incidents:
        film = inc.get("film_title", "Unknown")
        if film not in film_incidents:
            film_incidents[film] = []
        film_incidents[film].append(inc)

    # For each film with a matching screening, compare predicted vs observed
    for screening in screenings:
        film = screening.get("film_title")
        if not film or film not in film_incidents:
            continue

        film_incs = film_incidents[film]
        first_inc = film_incs[0]  # Already sorted by detected_at asc

        # Calculate observed incident day (relative to screening start)
        try:
            screening_start = datetime.fromisoformat(
                screening.get("started_at","").replace("Z",""))
            first_detected  = datetime.fromisoformat(
                first_inc.get("detected_at","").replace("Z",""))
            observed_day = max(1, (first_detected - screening_start).days + 1)
        except Exception:
            observed_day = None

        # Get Layer 1 prediction
        genre    = screening.get("genre", "action")
        strategy = screening.get("release_strategy", "staggered")
        predicted_leak_low  = None
        predicted_leak_high = None

        try:
            with httpx.Client(timeout=6.0) as client:
                r = client.post(f"{CINERISK_API}/simulate", json={
                    "genre": genre, "hype": "medium",
                    "strategy": strategy, "budget_m": 100.0,
                    "film_title": film,
                })
            if r.status_code == 200:
                data = r.json()
                cur = next((s for s in data.get("strategies",[])
                            if s["strategy"]==strategy), None)
                if cur:
                    predicted_leak_low  = cur["leak_day_low"]
                    predicted_leak_high = cur["leak_day_high"]
        except Exception:
            pass

        entry = {
            "film":                film,
            "genre":               genre,
            "strategy":            strategy,
            "theater":             screening.get("theater_name"),
            "total_incidents":     len(film_incs),
            "observed_first_day":  observed_day,
            "predicted_leak_low":  predicted_leak_low,
            "predicted_leak_high": predicted_leak_high,
            "within_predicted_range": (
                predicted_leak_low is not None and
                observed_day is not None and
                predicted_leak_low <= observed_day <= predicted_leak_high
            ) if observed_day and predicted_leak_low else None,
        }
        calibration_data.append(entry)

        print(f"  Film: {film}")
        print(f"    Predicted leak: Day {predicted_leak_low}–{predicted_leak_high}")
        print(f"    Observed first: Day {observed_day}")
        print(f"    Within range:   {entry['within_predicted_range']}")
        print(f"    Incidents:      {len(film_incs)}")
        print()

    # Summary
    if calibration_data:
        accurate = [e for e in calibration_data if e["within_predicted_range"] is True]
        total_with_data = [e for e in calibration_data if e["within_predicted_range"] is not None]
        accuracy = len(accurate)/len(total_with_data) if total_with_data else 0

        print(f"  Layer 3 Summary")
        print(f"  ──────────────────────────────")
        print(f"  Films analysed:      {len(calibration_data)}")
        print(f"  With full data:      {len(total_with_data)}")
        print(f"  Predictions accurate: {len(accurate)}/{len(total_with_data)} ({accuracy:.0%})")
        print()

        # Save calibration report
        out = {
            "run_at":          datetime.now().isoformat(),
            "films_analysed":  len(calibration_data),
            "accuracy":        round(accuracy, 3),
            "calibration":     calibration_data,
        }
        with open("feedback_report.json", "w") as f:
            json.dump(out, f, indent=2)
        print(f"  Saved: feedback_report.json\n")

if __name__ == "__main__":
    run()
