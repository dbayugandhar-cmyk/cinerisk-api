import asyncio, httpx, time

API = "https://cinerisk-api-production.up.railway.app"

async def test():
    print("\n=== CINEOS Pipeline Test ===\n")
    async with httpx.AsyncClient(timeout=30) as c:

        r = await c.get(f"{API}/theater/stats")
        stats = r.json()
        print(f"[1] API health: {r.status_code} - stats: {stats}")

        payload = {
            "theater_name": "CINEOS Test Theater",
            "screen_number": "Screen 1",
            "seat_location": "Row G, Seat 7",
            "zone": "CENTER",
            "detection_type": "PHONE",
            "confidence": 0.85,
            "film_title": "Michael",
            "device_id": f"test-{int(time.time())}"
        }
        r = await c.post(f"{API}/theater/incident", json=payload)
        print(f"[2] POST incident: {r.status_code} - {r.text[:120]}")

        print("[3] Waiting 10s for Layer 4 scan...")
        await asyncio.sleep(10)

        r = await c.get(f"{API}/theater/incidents")
        incidents = r.json().get("incidents", [])
        alerted = [i for i in incidents if i.get("alerted")]
        print(f"[4] alerted=true incidents: {len(alerted)}")
        for a in alerted[:3]:
            print(f"    -> {a.get('film_title')} | zone={a.get('zone')} | conf={a.get('confidence')}")

        r = await c.get(f"{API}/theater/alerts")
        if r.status_code == 200:
            data = r.json()
            print(f"[5] /theater/alerts: {data.get('count', 0)} confirmed alerts")
            for a in data.get("alerts", [])[:2]:
                print(f"    -> {a.get('film_title')} | gap={a.get('gap_minutes')}min | platforms={a.get('platforms')}")
        else:
            print(f"[5] /theater/alerts: {r.status_code} - {r.text[:100]}")

        r = await c.get(f"{API}/theater/scan_status/Michael")
        if r.status_code == 200:
            print(f"[6] Scan status for Michael: {r.json()}")
        else:
            print(f"[6] scan_status: {r.status_code}")

        print("\nDone. Check Railway logs for [LAYER4] lines:")
        print("https://railway.app/dashboard -> your project -> Deployments -> View Logs\n")

asyncio.run(test())
