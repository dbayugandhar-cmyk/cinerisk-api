import os, json, httpx, asyncio
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

TMDB_KEY = os.getenv("TMDB_API_KEY", "")

CINEOS_CAM_PATTERNS = {
    28:   (0.95, 11.5, 4),
    27:   (0.90, 9.0,  3),
    53:   (0.88, 10.5, 5),
    878:  (0.85, 8.0,  5),
    35:   (0.60, 4.0,  8),
    18:   (0.40, 2.5, 12),
    16:   (0.55, 5.0,  7),
    12:   (0.80, 7.5,  5),
    80:   (0.75, 6.5,  6),
    9648: (0.70, 6.0,  6),
}

GENRE_NAMES = {
    28:"Action",12:"Adventure",16:"Animation",35:"Comedy",80:"Crime",
    99:"Documentary",18:"Drama",10751:"Family",14:"Fantasy",36:"History",
    27:"Horror",10402:"Music",9648:"Mystery",10749:"Romance",
    878:"Science Fiction",10770:"TV Movie",53:"Thriller",10752:"War",37:"Western"
}

REVENUE_IMPACT = {
    28:0.191,27:0.185,53:0.175,878:0.165,35:0.095,
    18:0.060,16:0.120,12:0.170,80:0.155,9648:0.145
}

def _estimate_budget(popularity):
    if popularity >= 500: return 220.0
    if popularity >= 200: return 130.0
    if popularity >= 100: return 65.0
    if popularity >= 50:  return 30.0
    if popularity >= 20:  return 15.0
    return 8.0

def _primary_genre(genre_ids):
    if not genre_ids: return 18, "Drama"
    best = max(genre_ids, key=lambda g: CINEOS_CAM_PATTERNS.get(g,(0.50,3,10))[0])
    return best, GENRE_NAMES.get(best, "Unknown")

def _risk(genre_id, popularity, budget, days):
    base = CINEOS_CAM_PATTERNS.get(genre_id,(0.60,5,7))[0]
    pop = 1.35 if popularity>=500 else 1.20 if popularity>=200 else 1.10 if popularity>=100 else 1.00 if popularity>=50 else 0.85
    bud = 1.18 if budget>=200 else 1.06 if budget>=100 else 1.00 if budget>=50 else 0.92 if budget>=20 else 0.82
    urg = 1.15 if days<=7 else 1.08 if days<=14 else 1.00 if days<=30 else 0.90
    return round(min(0.97, max(0.10, base*pop*bud*urg)), 3)

def _revenue_at_risk(genre_id, budget, risk):
    impact = REVENUE_IMPACT.get(genre_id, 0.191)
    mult = {28:2.6,27:2.0,53:1.8,878:2.3,35:1.5,18:1.4,16:2.9,12:2.2,80:1.7,9648:1.6}.get(genre_id,1.8)
    return round(budget * mult * impact * risk, 1)

def _action(risk, days):
    if risk >= 0.85:
        return f"{'IMMEDIATE' if days<=7 else 'DEPLOY NOW'} — Deploy CINEOS all opening screens. Layer 4 scan every 10 min."
    if risk >= 0.70:
        return "HIGH PRIORITY — Deploy top 50% screens by attendance. Layer 4 every 30 min."
    if risk >= 0.50:
        return "MONITOR — Flagship screens only. Daily Layer 4 scan."
    return "STANDARD — Routine monitoring. Weekly Layer 4 scan."

def _level(risk):
    if risk >= 0.85: return "CRITICAL"
    if risk >= 0.70: return "HIGH"
    if risk >= 0.50: return "MEDIUM"
    return "LOW"

async def fetch_films():
    if not TMDB_KEY:
        print("[LAYER1] No TMDB key — set TMDB_API_KEY")
        return []
    films = []
    async with httpx.AsyncClient(timeout=15) as client:
        for page in range(1, 4):
            r = await client.get(
                "https://api.themoviedb.org/3/movie/upcoming",
                params={"api_key": TMDB_KEY, "region": "US", "page": page}
            )
            if r.status_code == 200:
                films.extend(r.json().get("results", []))
    print(f"[LAYER1] Fetched {len(films)} films from TMDB")
    return films

async def main():
    films = await fetch_films()
    if not films:
        return

    today = datetime.now(timezone.utc).date()
    threats = []

    for f in films:
        try:
            release = datetime.strptime(f["release_date"], "%Y-%m-%d").date()
            days = (release - today).days
            if days < -30 or days > 90: continue

            gid, gname = _primary_genre(f.get("genre_ids", []))
            budget = _estimate_budget(f.get("popularity", 10))
            pop = f.get("popularity", 10)
            # Skip very low popularity films — no piracy demand
            if pop < 5.0:
                continue

            risk = _risk(gid, pop, budget, days)
            rev = _revenue_at_risk(gid, budget, risk)
            _, avg_plat, avg_leak = CINEOS_CAM_PATTERNS.get(gid, (0.6, 5, 7))

            threats.append({
                "title": f["title"],
                "release_date": f["release_date"],
                "days_to_release": days,
                "genre": gname,
                "popularity": round(pop, 1),
                "budget_estimate_m": budget,
                "cam_risk_score": risk,
                "threat_level": _level(risk),
                "revenue_at_risk_m": rev,
                "est_leak_day": avg_leak,
                "platforms_at_risk": avg_plat,
                "cineos_action": _action(risk, days)
            })
        except Exception as e:
            print(f"  Error: {f.get('title')} — {e}")

    threats.sort(key=lambda x: x["cam_risk_score"], reverse=True)

    print(f"\n{'='*65}")
    print(f"  CINEOS OPENING WEEKEND THREAT BRIEFING")
    print(f"  {datetime.now().strftime('%B %d, %Y')}  |  {len(threats)} films analyzed")
    print(f"  US Prov. Pat. 64/049,190")
    print(f"{'='*65}\n")

    for t in threats[:10]:
        print(f"  {'🔴' if t['threat_level']=='CRITICAL' else '🟡' if t['threat_level']=='HIGH' else '🟢'} {t['title']}")
        print(f"     Release: {t['release_date']} ({t['days_to_release']}d)  |  {t['genre']}  |  Pop: {t['popularity']}")
        print(f"     CAM Risk: {t['cam_risk_score']:.0%}  [{t['threat_level']}]  |  Revenue at risk: ${t['revenue_at_risk_m']:.0f}M")
        print(f"     Est. leak: Day +{t['est_leak_day']}  |  ~{t['platforms_at_risk']:.0f} platforms")
        print(f"     ➤ {t['cineos_action']}")
        print()

    with open("cineos_threat_briefing.json", "w") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_films": len(threats),
            "critical": len([t for t in threats if t["threat_level"]=="CRITICAL"]),
            "high": len([t for t in threats if t["threat_level"]=="HIGH"]),
            "films": threats,
            "patent": "US Prov. Pat. 64/049,190",
            "data_source": "TMDB API + CINEOS Layer 4 empirical CAM patterns May 2026",
            "research_basis": "Ma et al. 2014 — 19.1% revenue impact from pre-release piracy"
        }, f, indent=2)

    print(f"  Saved: cineos_threat_briefing.json")
    print(f"{'='*65}")

asyncio.run(main())
