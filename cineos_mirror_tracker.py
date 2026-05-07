"""
CINEOS Mirror Propagation Tracker
Uses India scanner hits to map piracy spread across sites
"""
import asyncio, json, datetime, os, sys
sys.path.insert(0, '.')

PIRACY_NETWORK = {
    "tamilblasters": {"type":"SOURCE",     "hours":0,  "region":"Tamil/Telugu", "tier":1},
    "tamilmv":       {"type":"SOURCE",     "hours":2,  "region":"Tamil",        "tier":1},
    "isaimini":      {"type":"SOURCE",     "hours":3,  "region":"Tamil",        "tier":1},
    "ibomma":        {"type":"SOURCE",     "hours":4,  "region":"Telugu",       "tier":1},
    "movierulz":     {"type":"AGGREGATOR", "hours":6,  "region":"Pan-India",    "tier":2},
    "moviesda":      {"type":"MIRROR",     "hours":8,  "region":"Tamil",        "tier":2},
    "kuttymovies":   {"type":"MIRROR",     "hours":10, "region":"Tamil",        "tier":2},
    "filmyzilla":    {"type":"MIRROR",     "hours":12, "region":"Hindi",        "tier":2},
    "hdhub4u":       {"type":"AGGREGATOR", "hours":18, "region":"Hindi",        "tier":3},
    "9xmovies":      {"type":"MIRROR",     "hours":20, "region":"Hindi",        "tier":3},
    "vegamovies":    {"type":"MIRROR",     "hours":24, "region":"Hindi",        "tier":3},
    "skymovieshd":   {"type":"MIRROR",     "hours":30, "region":"Hindi",        "tier":3},
    "moviesdacom":   {"type":"MIRROR",     "hours":8,  "region":"Tamil",        "tier":2},
    "moviesflix":    {"type":"MIRROR",     "hours":16, "region":"Multi",        "tier":3},
}

async def track_propagation(film_title: str) -> dict:
    from cineos_india import full_india_scan
    
    print(f"Scanning: {film_title}")
    result = await full_india_scan(film_title)
    hits = result.get("hits", [])
    
    timeline = []
    seen_domains = set()
    
    for hit in hits:
        url = hit.url if hasattr(hit,'url') else hit.get('url','')
        language = hit.language if hasattr(hit,'language') else hit.get('language','Unknown')
        quality = hit.quality if hasattr(hit,'quality') else hit.get('quality','Unknown')
        
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lstrip('www.')
        base = next((k for k in PIRACY_NETWORK if k in domain), None)
        
        if domain not in seen_domains:
            seen_domains.add(domain)
            info = PIRACY_NETWORK.get(base, {"type":"UNKNOWN","hours":999,"region":"Unknown","tier":4})
            timeline.append({
                "domain": domain,
                "url": url,
                "type": info["type"],
                "estimated_hours": info["hours"],
                "region": info["region"],
                "tier": info["tier"],
                "language": language,
                "quality": quality,
            })
    
    timeline.sort(key=lambda x: x["estimated_hours"])
    
    # Predict mirrors not yet found
    predicted = []
    if hits:
        for domain, info in PIRACY_NETWORK.items():
            already = any(domain in t["domain"] for t in timeline)
            if not already and info["tier"] <= 3:
                predicted.append({
                    "domain": domain,
                    "type": info["type"],
                    "estimated_hours": info["hours"],
                    "region": info["region"],
                    "status": "PREDICTED — not yet detected"
                })
        predicted.sort(key=lambda x: x["estimated_hours"])
    
    return {
        "film": film_title,
        "verdict": result.get("verdict","CLEAN"),
        "confirmed_sites": len(timeline),
        "predicted_mirrors": len(predicted),
        "scanned_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "timeline": timeline,
        "predicted": predicted[:5],
        "summary": {
            "sources": len([t for t in timeline if t["type"]=="SOURCE"]),
            "mirrors": len([t for t in timeline if t["type"]=="MIRROR"]),
            "aggregators": len([t for t in timeline if t["type"]=="AGGREGATOR"]),
            "languages": list(set(t["language"] for t in timeline if t["language"])),
            "fastest_hours": timeline[0]["estimated_hours"] if timeline else 0,
        }
    }

def print_report(data: dict):
    film = data["film"]
    tl = data["timeline"]
    pred = data["predicted"]
    s = data["summary"]
    
    print(f"\n{'='*70}")
    print(f"  CINEOS Mirror Propagation — {film}")
    print(f"  Verdict: {data['verdict']} | Scanned: {data['scanned_at']}")
    print(f"{'='*70}")
    print(f"  Confirmed: {data['confirmed_sites']} sites | Predicted: {data['predicted_mirrors']} more")
    print(f"  Sources: {s['sources']} | Mirrors: {s['mirrors']} | Aggregators: {s['aggregators']}")
    print(f"  Languages: {', '.join(s['languages'])}")
    print(f"  Est. first spread: ~{s['fastest_hours']}h after release")
    
    if tl:
        print(f"\n  CONFIRMED SPREAD:")
        print(f"  {'Est.Hours':>10}  {'Type':12} {'Tier':5} {'Region':12} {'Domain'}")
        print(f"  {'-'*65}")
        for t in tl:
            h = f"~{t['estimated_hours']}h" if t['estimated_hours'] < 999 else "unknown"
            print(f"  {h:>10}  {t['type']:12} T{t['tier']:4} {t['region']:12} {t['domain']}")
    
    if pred:
        print(f"\n  PREDICTED NEXT MIRRORS (not yet detected):")
        for p in pred:
            print(f"  ~{p['estimated_hours']}h  {p['type']:12} {p['region']:12} {p['domain']} — {p['status']}")
    
    print(f"{'='*70}\n")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    
    result = asyncio.run(track_propagation(args.film))
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_report(result)
