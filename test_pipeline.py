import asyncio, httpx, time

API = "https://cinerisk-api-production.up.railway.app"

async def test():
    print("\n=== CINEOS Pipeline Test ===\n")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{API}/theater/stats")
        print(f"[1] API health: {r.status_code} - {r.json()['total_incidents']} incidents in DB")

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

        r = await c.get(f"{API}/theater/alerts")
        if r.status_code == 200:
            print(f"[5] /theater/alerts: {r.json().get('count', 0)} confirmed alerts")
        else:
            print(f"[5] /theater/alerts: not deployed yet (add new routes to theater_api.py)")

        print("\nCheck Railway logs for [LAYER4] lines to confirm trigger fired")
        print("https://railway.app/dashboard -> your project -> Deployments -> View Logs")

asyncio.run(test())
