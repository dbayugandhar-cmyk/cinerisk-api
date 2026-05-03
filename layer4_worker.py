import asyncio, asyncpg, os, httpx
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "dba.yugandhar@gmail.com")
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", "alerts@cineos.io")
POLL_INTERVAL = 600  # every 10 minutes

async def scan_film(film_title: str) -> dict:
    query = f'"{film_title}" CAM torrent download'
    results = {"hits": 0, "platforms": [], "first_url": "", "query": query}
    slug = film_title.lower().replace(" ", "-").replace(":", "").replace("'", "")
    check_url = f"https://whereyouwatch.com/movies/{slug}/"
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        try:
            r = await client.get(check_url)
            if r.status_code == 200:
                body = r.text.lower()
                found = [k for k in ["cam", "telesync", "torrent", "download"] if k in body]
                if len(found) >= 2:
                    results["hits"] += 1
                    results["platforms"].append("whereyouwatch.com")
                    results["first_url"] = check_url
        except Exception as e:
            print(f"[WORKER] scan error: {e}")
    return results

async def send_email_alert(incident, scan):
    if not SENDGRID_API_KEY:
        print("[WORKER] No SendGrid key — skipping email")
        return
    body = f"""
CINEOS ALERT — CAM LEAK DETECTED

Film: {incident['film_title']}
Theater: {incident['theater_name']}
Zone: {incident['zone']}
Confidence: {int(incident['confidence']*100)}%
Detected at: {incident['detected_at']}

Platforms found: {', '.join(scan['platforms'])}
First URL: {scan['first_url']}

— CINEOS Layer 4 Auto-Monitor
US Prov. Pat. 64/049,190
"""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
                json={
                    "personalizations": [{"to": [{"email": ALERT_EMAIL_TO}]}],
                    "from": {"email": ALERT_EMAIL_FROM},
                    "subject": f"[CINEOS] CAM Alert — {incident['film_title']}",
                    "content": [{"type": "text/plain", "value": body}]
                }
            )
            print(f"[WORKER] Email sent: {r.status_code}")
        except Exception as e:
            print(f"[WORKER] Email error: {e}")

async def process_unalerted():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            "SELECT * FROM incidents WHERE alerted = false AND confidence >= 0.5 ORDER BY detected_at DESC"
        )
        print(f"[WORKER] Found {len(rows)} unalerted incidents")
        for row in rows:
            incident = dict(row)
            film = incident['film_title']
            if not film or film == 'string':
                continue
            print(f"[WORKER] Scanning for: {film}")
            scan = await scan_film(film)
            detected_at = incident['detected_at']
            now = datetime.now(timezone.utc)
            gap_minutes = int((now - detected_at).total_seconds() / 60)
            await conn.execute(
                "UPDATE incidents SET alerted = true WHERE id = $1",
                incident['id']
            )
            try:
                await conn.execute(
                    """INSERT INTO scan_results 
                    (incident_id, film_title, hits_found, platforms, first_hit_url, gap_minutes, scan_query)
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    ON CONFLICT DO NOTHING""",
                    incident['id'], film, scan['hits'],
                    ','.join(scan['platforms']), scan['first_url'],
                    gap_minutes, scan['query']
                )
            except Exception as e:
                print(f"[WORKER] scan_results insert error: {e}")
            if scan['hits'] > 0:
                print(f"[WORKER] CAM FOUND for {film} — sending alert")
                await send_email_alert(incident, scan)
            else:
                print(f"[WORKER] Clean scan for {film} — gap: {gap_minutes}min")
    finally:
        await conn.close()

async def main():
    print("[WORKER] Layer 4 auto-monitor started")
    while True:
        try:
            await process_unalerted()
        except Exception as e:
            print(f"[WORKER] cycle error: {e}")
        print(f"[WORKER] Sleeping {POLL_INTERVAL}s")
        await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
