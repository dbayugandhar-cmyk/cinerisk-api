import asyncio
import asyncpg
import os
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL", "")

# In-memory session state
# Key: (theater, screen, zone) → session dict
active_sessions = {}

SESSION_TIMEOUT = 300      # 5 min inactivity = session closed
ESCALATE_L2 = 10           # 10 detections = staff alert
ESCALATE_L3 = 30           # 30 detections = manager SMS
ESCALATE_L4 = 60           # 60 detections = studio alert (full film recording)

async def get_db():
    if not DATABASE_URL:
        return None
    try:
        return await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"[SESSION] DB error: {e}")
        return None

async def update_session(theater, screen, film, zone, confidence):
    key = (theater, screen, zone)
    now = datetime.now(timezone.utc)

    if key not in active_sessions:
        # New session
        active_sessions[key] = {
            "theater": theater,
            "screen": screen,
            "film": film,
            "zone": zone,
            "started_at": now,
            "last_seen_at": now,
            "count": 1,
            "max_confidence": confidence,
            "escalation_level": 1,
            "db_id": None,
        }
        print(f"[SESSION] New session — {theater} {screen} {zone} zone")

        # Write to DB
        conn = await get_db()
        if conn:
            try:
                row = await conn.fetchrow('''
                    INSERT INTO detection_sessions
                    (theater_name, screen_number, film_title, zone, max_confidence)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                ''', theater, screen, film, zone, confidence)
                active_sessions[key]["db_id"] = str(row["id"])
            except Exception as e:
                print(f"[SESSION] Insert error: {e}")
            finally:
                await conn.close()
        return 1, active_sessions[key]

    # Existing session
    session = active_sessions[key]
    elapsed = (now - session["last_seen_at"]).total_seconds()

    # Check if session timed out
    if elapsed > SESSION_TIMEOUT:
        print(f"[SESSION] Session expired — {zone} zone. Duration: {int((session['last_seen_at'] - session['started_at']).total_seconds())}s")
        del active_sessions[key]
        return await update_session(theater, screen, film, zone, confidence)

    # Update session
    session["last_seen_at"] = now
    session["count"] += 1
    session["max_confidence"] = max(session["max_confidence"], confidence)
    duration = int((now - session["started_at"]).total_seconds())

    # Determine escalation level
    old_level = session["escalation_level"]
    if session["count"] >= ESCALATE_L4:
        session["escalation_level"] = 4
    elif session["count"] >= ESCALATE_L3:
        session["escalation_level"] = 3
    elif session["count"] >= ESCALATE_L2:
        session["escalation_level"] = 2

    new_level = session["escalation_level"]

    # Log escalation change
    if new_level > old_level:
        label = {2: "STAFF ALERT", 3: "MANAGER SMS", 4: "STUDIO ALERT"}
        print(f"[SESSION] ESCALATE L{new_level} — {label[new_level]} — {zone} zone — {session['count']} detections — {duration}s")

    # Update DB every 10 detections
    if session["count"] % 10 == 0 and session["db_id"]:
        conn = await get_db()
        if conn:
            try:
                await conn.execute('''
                    UPDATE detection_sessions
                    SET last_seen_at = $1,
                        detection_count = $2,
                        max_confidence = $3,
                        duration_seconds = $4,
                        escalation_level = $5
                    WHERE id = $6
                ''', now, session["count"], session["max_confidence"],
                    duration, new_level, session["db_id"])
            except Exception as e:
                print(f"[SESSION] Update error: {e}")
            finally:
                await conn.close()

    return new_level, session

async def close_session(theater, screen, zone):
    key = (theater, screen, zone)
    if key in active_sessions:
        session = active_sessions[key]
        duration = int((session["last_seen_at"] - session["started_at"]).total_seconds())
        print(f"[SESSION] Closed — {zone} zone — {session['count']} detections — {duration}s")

        if session["db_id"]:
            conn = await get_db()
            if conn:
                try:
                    await conn.execute(
                        "UPDATE detection_sessions SET resolved = true, duration_seconds = $1 WHERE id = $2",
                        duration, session["db_id"]
                    )
                except Exception as e:
                    print(f"[SESSION] Close error: {e}")
                finally:
                    await conn.close()

        del active_sessions[key]

def get_active_sessions():
    return active_sessions
