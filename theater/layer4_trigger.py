import asyncio, httpx, os
from datetime import datetime, timezone

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
ALERT_EMAIL_TO   = os.getenv("ALERT_EMAIL_TO", "dba.yugandhar@gmail.com")
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", "alerts@cineos.io")
SERP_API_KEY     = os.getenv("SERP_API_KEY", "")
DATABASE_URL     = os.getenv("DATABASE_URL", "")
SCAN_THRESHOLD   = 0.50

async def get_db_conn():
    try:
        import asyncpg
        return await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"[LAYER4] DB connect error: {e}")
        return None

async def search_piracy(film_title: str) -> dict:
    query = f'"{film_title}" CAM torrent download 1080p'
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
            print(f"[LAYER4] check failed: {e}")
    if SERP_API_KEY:
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r = await client.get(
                    "https://serpapi.com/search",
                    params={"q": query, "api_key": SERP_API_KEY, "num": 5, "engine": "google"},
                )
                organic = r.json().get("organic_results", [])
                for item in organic:
                    link = item.get("link", "")
                    for site in ["torrentleech", "1337x", "rarbg", "yts", "extto"]:
                        if site in link and site not in results["platforms"]:
                            results["hits"] += 1
                            results["platforms"].append(site)
                if organic and not results["first_url"]:
                    results["first_url"] = organic[0].get("link", "")
            except Exception as e:
                print(f"[LAYER4] SerpApi error: {e}")
    return results

async def send_alert(incident: dict, scan: dict, gap_minutes: int):
    film    = incident.get("film_title", "Unknown")
    theater = incident.get("theater_name", "Unknown")
    zone    = incident.get("zone", "?")
    conf    = float(incident.get("confidence", 0))
    body_text = f"""
CINEOS LAYER 4 ALERT - CAM CONFIRMED
=====================================
Film:        {film}
Theater:     {theater}  |  Zone: {zone}
Confidence:  {conf:.0%}
Gap:         {gap_minutes} min ({gap_minutes/60:.1f} hours)
Platforms:   {', '.join(scan['platforms']) or 'Unknown'}
First URL:   {scan['first_url'] or 'N/A'}
Hits:        {scan['hits']}
Action:      Stage DMCA filing immediately
CINEOS US Prov. Pat. 64/049,190
"""
    print(body_text)
    if not SENDGRID_API_KEY:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {SENDGRID_API_KEY}",
                         "Content-Type": "application/json"},
                json={
                    "personalizations": [{"to": [{"email": ALERT_EMAIL_TO}]}],
                    "from": {"email": ALERT_EMAIL_FROM, "name": "CINEOS"},
                    "subject": f"[CINEOS] CAM confirmed - {film} - {gap_minutes}min gap",
                    "content": [{"type": "text/plain", "value": body_text}],
                },
            )
            print(f"[LAYER4] Email {'sent' if r.status_code == 202 else f'error {r.status_code}'}")
        except Exception as e:
            print(f"[LAYER4] Email failed: {e}")

async def run_scan_and_alert(incident_id: str, film_title: str,
                              theater_name: str, zone: str,
                              detected_at, confidence: float, db=None):
    if confidence < SCAN_THRESHOLD:
        return
    film = (film_title or "").strip()
    if not film or film in ("string", ""):
        return
    print(f"\n[LAYER4] Triggered for '{film}' | conf={confidence:.2f} | zone={zone}")
    scan = await search_piracy(film)
    try:
        if isinstance(detected_at, str):
            detected_dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
        else:
            detected_dt = detected_at if detected_at.tzinfo else detected_at.replace(tzinfo=timezone.utc)
        gap_minutes = int((datetime.now(timezone.utc) - detected_dt).total_seconds() / 60)
    except Exception:
        gap_minutes = 0
    conn = await get_db_conn()
    if conn:
        try:
            await conn.execute(
                """CREATE TABLE IF NOT EXISTS scan_results (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    incident_id UUID, film_title TEXT,
                    scan_time TIMESTAMPTZ DEFAULT NOW(),
                    hits_found INTEGER DEFAULT 0, platforms TEXT[],
                    first_hit_url TEXT, gap_minutes INTEGER, scan_query TEXT
                )""")
            await conn.execute(
                """INSERT INTO scan_results
                   (incident_id, film_title, hits_found, platforms, first_hit_url, gap_minutes, scan_query)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                incident_id, film, scan["hits"], scan["platforms"],
                scan["first_url"] or "", gap_minutes, scan["query"]
            )
            if scan["hits"] > 0:
                await conn.execute(
                    "UPDATE incidents SET alerted = true WHERE id = $1", incident_id
                )
        except Exception as e:
            print(f"[LAYER4] DB error: {e}")
        finally:
            await conn.close()
    if scan["hits"] > 0:
        incident_dict = {"id": incident_id, "film_title": film,
                         "theater_name": theater_name, "zone": zone,
                         "confidence": confidence, "detected_at": str(detected_at)}
        await send_alert(incident_dict, scan, gap_minutes)
        print(f"[LAYER4] CAM CONFIRMED on {scan['platforms']}")
    else:
        print(f"[LAYER4] Clean - scheduling 2h rescan for '{film}'")
        async def rescan():
            await asyncio.sleep(7200)
            print(f"[LAYER4] 2h rescan for '{film}'")
            scan2 = await search_piracy(film)
            if scan2["hits"] > 0:
                conn2 = await get_db_conn()
                if conn2:
                    try:
                        await conn2.execute(
                            "UPDATE incidents SET alerted = true WHERE id = $1", incident_id)
                        await conn2.execute(
                            """INSERT INTO scan_results
                               (incident_id, film_title, hits_found, platforms, first_hit_url, gap_minutes, scan_query)
                               VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                            incident_id, film, scan2["hits"], scan2["platforms"],
                            scan2["first_url"] or "", gap_minutes + 120, scan2["query"]
                        )
                    except Exception as e:
                        print(f"[LAYER4] rescan DB error: {e}")
                    finally:
                        await conn2.close()
                incident_dict = {"id": incident_id, "film_title": film,
                                 "theater_name": theater_name, "zone": zone,
                                 "confidence": confidence, "detected_at": str(detected_at)}
                await send_alert(incident_dict, scan2, gap_minutes + 120)
        asyncio.create_task(rescan())
