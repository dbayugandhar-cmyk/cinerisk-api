"""
CINEOS Physical Supply Chain Intelligence
Track counterfeit products through QR codes,
batch numbers, and distributor networks.
Identifies leak points in legitimate supply chains.
"""
import asyncio, httpx, re, json, os, hashlib
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

def generate_product_qr_hash(
    brand: str,
    batch: str,
    mfg_date: str,
    location: str
) -> dict:
    """
    Generate a verifiable product hash for supply chain tracking.
    Brands embed this in QR codes on packaging.
    CINEOS verifies authenticity by checking hash.
    """
    product_data = f"{brand}|{batch}|{mfg_date}|{location}"
    auth_hash = hashlib.sha256(product_data.encode()).hexdigest()[:16].upper()

    return {
        'brand': brand,
        'batch': batch,
        'mfg_date': mfg_date,
        'location': location,
        'auth_hash': auth_hash,
        'verify_url': f"https://cinerisk-api-production.up.railway.app/v1/verify/{auth_hash}",
        'qr_data': f"CINEOS|{brand}|{auth_hash}",
        'generated_at': datetime.now().isoformat(),
    }

def verify_product_hash(
    auth_hash: str,
    brand: str,
    batch: str,
    mfg_date: str,
    location: str
) -> dict:
    """Verify a product hash matches the packaging data."""
    expected = generate_product_qr_hash(brand, batch, mfg_date, location)
    is_genuine = expected['auth_hash'] == auth_hash.upper()

    return {
        'is_genuine': is_genuine,
        'auth_hash': auth_hash,
        'verdict': 'GENUINE' if is_genuine else 'COUNTERFEIT — hash mismatch',
        'brand': brand,
        'verified_at': datetime.now().isoformat(),
    }

async def scan_supply_chain_leaks(brand: str) -> list:
    """Find where counterfeit products enter the supply chain."""
    print(f"[SUPPLY] Scanning {brand} supply chain...")
    leaks = []

    async with httpx.AsyncClient(timeout=12) as client:
        queries = [
            f'{brand} wholesale supplier india unauthorized dealer',
            f'{brand} factory seconds india sell',
            f'{brand} expired stock india sell distributor',
            f'{brand} diversion stock india unauthorized',
        ]

        for q in queries:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "q": q,
                    "api_key": SERP_KEY,
                    "num": 5,
                    "engine": "google",
                    "gl": "in"
                })
                for item in r.json().get("organic_results",[]):
                    url = item.get("link","")
                    if any(x in url for x in
                           ['indiamart','tradeindia','meesho','olx']):
                        leaks.append({
                            'brand': brand,
                            'url': url,
                            'title': item.get("title","")[:80],
                            'leak_type': 'unauthorized_distributor',
                            'risk': 'HIGH',
                        })
                        print(f"  LEAK: {url[:65]}")
            except:
                pass

    return leaks

async def full_supply_chain_scan():
    print("[SUPPLY CHAIN] Starting scan...")

    brands = ['Nike', 'Dettol', 'Dove', 'Samsung Galaxy']
    all_leaks = []

    for brand in brands:
        leaks = await scan_supply_chain_leaks(brand)
        all_leaks.extend(leaks)

    # Demo QR generation
    print(f"\n[SUPPLY CHAIN] Demo QR Hash Generation:")
    demo_products = [
        ('Nike', 'B2026Q1', '2026-01-15', 'Chennai'),
        ('Dettol', 'DET2026M3', '2026-03-01', 'Mumbai'),
        ('Dove', 'DOV2026A', '2026-04-01', 'Kolkata'),
    ]

    qr_codes = []
    for brand, batch, date, loc in demo_products:
        qr = generate_product_qr_hash(brand, batch, date, loc)
        qr_codes.append(qr)
        print(f"  {brand} batch {batch}: {qr['auth_hash']}")
        print(f"    Verify: {qr['verify_url']}")

        # Verify genuine
        v = verify_product_hash(qr['auth_hash'], brand, batch, date, loc)
        print(f"    Status: {v['verdict']}")

        # Test fake
        v2 = verify_product_hash('FAKEHASH123456', brand, batch, date, loc)
        print(f"    Fake test: {v2['verdict']}")

    print(f"\n{'='*60}")
    print(f"  CINEOS SUPPLY CHAIN INTELLIGENCE")
    print(f"{'='*60}")
    print(f"  Supply chain leaks: {len(all_leaks)}")
    print(f"  QR codes generated: {len(qr_codes)}")
    print(f"  Brands covered: {len(brands)}")

    os.makedirs('reports', exist_ok=True)
    path = f"reports/supply_chain_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump({
        'leaks': all_leaks,
        'qr_codes': qr_codes,
    }, open(path,'w'), indent=2)
    print(f"\n  Saved: {path}")
    return all_leaks, qr_codes

if __name__ == '__main__':
    asyncio.run(full_supply_chain_scan())
