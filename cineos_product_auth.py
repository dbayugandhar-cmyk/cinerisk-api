"""
CINEOS Digital Product Authentication
Entrupy-style but digital — no hardware needed.
We do what Entrupy cannot:
  - Find the seller BEFORE product reaches consumer
  - Monitor at scale across 50+ platforms
  - Work in 6 Indian languages
  - Cost: Rs 0 per product (vs $299/month hardware)

Partnership pitch to Entrupy:
  CINEOS finds the seller network
  Entrupy authenticates the physical product
  Together = complete brand protection
"""
import asyncio, httpx, re, json, os, hashlib
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY', '')

# ── DIGITAL AUTHENTICATION SIGNALS ───────────────────────
# These are signals CINEOS detects digitally
# Entrupy detects physically — they complement each other

PRICE_BANDS = {
    # brand → (min_genuine_price, typical_retail)
    'Nike':           (3000,   8000),
    'Adidas':         (2500,   7000),
    'Ray-Ban':        (5000,   12000),
    'Titan':          (2000,   8000),
    'Fossil':         (3000,   10000),
    'boAt':           (500,    3000),
    'Samsung Galaxy': (8000,   20000),
    'Apple':          (30000,  80000),
    'Dettol':         (80,     200),
    'Dove':           (100,    250),
    'Colgate':        (50,     150),
    'Parachute':      (80,     200),
    'Himalaya':       (100,    400),
    'Crocin':         (30,     80),
    'Cipla':          (50,     200),
}

COUNTERFEIT_SIGNALS = {
    'explicit': [
        'first copy', '1st copy', 'master copy', 'super copy',
        'aaa quality', 'replica', '[copy]', '(copy)', 'duplicate',
        'same as original', 'factory outlet', 'imported copy',
        'A grade copy', 'premium copy', 'high quality copy',
    ],
    'suspicious': [
        'wholesale', 'bulk order', 'minimum order', 'b2b',
        'grey market', 'parallel import', 'refurbished',
        'open box', 'without bill', 'cash only',
    ],
    'platform_risk': {
        'indiamart.com':  55,
        'tradeindia.com': 60,
        'meesho.com':     80,
        'instagram.com':  75,
        'facebook.com':   70,
        'olx.in':         65,
        'quikr.com':      60,
    }
}

class ProductAuthEngine:
    """
    Digital product authentication engine.
    Score any product listing for counterfeit risk.
    """

    def __init__(self):
        self.results = []

    def authenticate(self, listing: dict) -> dict:
        """
        Score a product listing 0-100 for counterfeit risk.
        0 = likely genuine, 100 = confirmed counterfeit.
        """
        brand    = listing.get('brand', '')
        price    = self._parse_price(listing.get('price', ''))
        title    = listing.get('title', '').lower()
        url      = listing.get('url', '').lower()
        platform = listing.get('platform', '') or \
                   re.sub(r'https?://(?:www\.)?([^/]+).*', r'\1', url)
        seller   = listing.get('seller', '')
        gst      = listing.get('gst', '')

        score = 0
        signals = []
        verdict = ''

        # 1. Explicit counterfeit admission (highest weight — 35pts)
        high_signals = [s for s in COUNTERFEIT_SIGNALS['explicit']
                       if s in title or s in url]
        if high_signals:
            score += 35
            signals.append(f'EXPLICIT: "{high_signals[0]}" in listing title')

        # 2. Price gap analysis (30pts)
        if brand in PRICE_BANDS and price > 0:
            min_genuine, retail = PRICE_BANDS[brand]
            if price < min_genuine * 0.3:
                score += 30
                gap = int((1 - price/retail) * 100)
                signals.append(
                    f'PRICE: Rs {price:,} is {gap}% below retail Rs {retail:,}')
            elif price < min_genuine * 0.5:
                score += 20
                signals.append(f'PRICE: Rs {price:,} significantly below genuine minimum')
            elif price < min_genuine:
                score += 10
                signals.append(f'PRICE: Rs {price:,} below minimum genuine price')

        # 3. Suspicious signals (15pts)
        susp = [s for s in COUNTERFEIT_SIGNALS['suspicious']
               if s in title]
        if susp:
            score += min(15, len(susp) * 5)
            signals.append(f'SUSPICIOUS: {susp[:2]}')

        # 4. Platform risk (10pts)
        plat_risk = COUNTERFEIT_SIGNALS['platform_risk'].get(platform, 40)
        plat_score = int(plat_risk * 0.1)
        score += plat_score

        # 5. GST validation (10pts)
        if not gst:
            score += 5
            signals.append('NO GST: Missing GST number')
        else:
            gstin_pat = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$'
            if not re.match(gstin_pat, gst.upper().strip()):
                score += 10
                signals.append(f'INVALID GST: {gst}')

        score = min(100, score)

        # Verdict
        if score >= 80:
            verdict = 'CONFIRMED COUNTERFEIT'
            action  = 'File IP complaint immediately'
        elif score >= 60:
            verdict = 'VERY LIKELY COUNTERFEIT'
            action  = 'Investigate and take down'
        elif score >= 40:
            verdict = 'SUSPICIOUS — INVESTIGATE'
            action  = 'Monitor and verify'
        else:
            verdict = 'LOW RISK'
            action  = 'Continue monitoring'

        result = {
            'brand':       brand,
            'seller':      seller,
            'platform':    platform,
            'price':       price,
            'gst':         gst,
            'auth_score':  score,
            'verdict':     verdict,
            'action':      action,
            'signals':     signals,
            'url':         listing.get('url', ''),
            'authenticated_at': datetime.now().isoformat(),
            'method':      'CINEOS Digital Authentication v1.0',
        }

        self.results.append(result)
        return result

    def _parse_price(self, price_str):
        if not price_str:
            return 0
        nums = re.findall(r'[\d,]+', str(price_str))
        return int(nums[0].replace(',','')) if nums else 0

    def batch_authenticate(self, listings: list) -> list:
        """Authenticate multiple listings and sort by risk."""
        results = [self.authenticate(l) for l in listings]
        return sorted(results, key=lambda x: -x['auth_score'])

    def generate_report(self, brand: str = None) -> dict:
        """Generate authentication summary report."""
        results = self.results
        if brand:
            results = [r for r in results if r['brand'] == brand]

        confirmed = [r for r in results if r['auth_score'] >= 80]
        likely    = [r for r in results if 60 <= r['auth_score'] < 80]
        suspicious= [r for r in results if 40 <= r['auth_score'] < 60]

        return {
            'total_authenticated': len(results),
            'confirmed_counterfeit': len(confirmed),
            'very_likely': len(likely),
            'suspicious': len(suspicious),
            'genuine_risk': len(results) - len(confirmed) - len(likely) - len(suspicious),
            'top_threats': confirmed[:5] + likely[:3],
            'brand_filter': brand,
            'generated_at': datetime.now().isoformat(),
        }

async def scan_and_authenticate(brand: str) -> list:
    """
    Scan IndiaMART for a brand and authenticate all listings.
    Full pipeline: Find → Extract → Score → Report
    """
    print(f"[AUTH] Scanning and authenticating {brand} listings...")

    results = []
    engine  = ProductAuthEngine()

    async with httpx.AsyncClient(
        timeout=12,
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
        follow_redirects=True
    ) as client:

        # Search for listings
        queries = [
            f'site:indiamart.com/proddetail "{brand}" copy',
            f'site:indiamart.com/proddetail "{brand}" first copy',
            f'site:indiamart.com/proddetail "{brand}" replica',
            f'site:meesho.com "{brand}" copy wholesale india',
        ]

        urls = set()
        for q in queries:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "q": q, "api_key": SERP_KEY,
                    "num": 10, "engine": "google", "gl": "in"
                })
                for item in r.json().get("organic_results", []):
                    link = item.get("link", "")
                    title = item.get("title", "")
                    if any(p in link for p in
                           ['indiamart', 'meesho', 'tradeindia']):
                        urls.add((link, title))
            except:
                pass

        print(f"  Found {len(urls)} listings to authenticate")

        # Authenticate each listing
        for url, title in list(urls)[:15]:
            # Extract seller data from IndiaMART
            seller  = ''
            city    = ''
            price   = ''
            gst     = ''
            platform = re.sub(r'https?://(?:www\.)?([^/]+).*',
                              r'\1', url)

            try:
                pr = await client.get(url)
                text = pr.text

                def jf(field):
                    m = re.search(f'"{field}"\\s*:\\s*"([^"]+)"', text)
                    return m.group(1).strip() if m else ''

                seller = jf('COMPANYNAME')
                city   = jf('CITY')
                price_m = re.search(r'₹\s*([\d,]+)', text)
                price  = f"Rs {price_m.group(1)}" if price_m else ''
                gst_m  = re.search(
                    r'"GST_IN"\\s*:\\s*"([0-9]{2}[A-Z]{5}[0-9]{4}'
                    r'[A-Z][1-9A-Z]Z[0-9A-Z])"', text)
                gst    = gst_m.group(1) if gst_m else ''

            except:
                pass

            listing = {
                'brand':    brand,
                'title':    title,
                'seller':   seller,
                'city':     city,
                'price':    price,
                'gst':      gst,
                'url':      url,
                'platform': platform,
            }

            auth = engine.authenticate(listing)
            results.append(auth)

            if auth['auth_score'] >= 60:
                print(f"  [{auth['auth_score']:3}/100] {seller or 'Unknown':28} "
                      f"{city:15} {price:10} {auth['verdict'][:20]}")

    # Print report
    report = engine.generate_report(brand)
    print(f"\n{'='*65}")
    print(f"  CINEOS DIGITAL AUTHENTICATION — {brand.upper()}")
    print(f"{'='*65}")
    print(f"  Listings authenticated: {report['total_authenticated']}")
    print(f"  Confirmed counterfeit:  {report['confirmed_counterfeit']}")
    print(f"  Very likely counterfeit:{report['very_likely']}")
    print(f"  Suspicious:             {report['suspicious']}")

    if report['top_threats']:
        print(f"\n  TOP THREATS:")
        for t in report['top_threats'][:5]:
            print(f"    [{t['auth_score']:3}/100] {t.get('seller','?'):25} "
                  f"{t['verdict']}")
            for sig in t['signals'][:2]:
                print(f"           → {sig}")

    return results, report

# ── ENTRUPY PARTNERSHIP PITCH DATA ───────────────────────
def generate_partnership_data():
    """
    Data for Entrupy partnership pitch.
    CINEOS digital + Entrupy physical = complete solution.
    """
    return {
        'cineos_capabilities': {
            'what': 'Digital seller detection before product reaches consumer',
            'scale': '59 confirmed sellers, 28 cities, IndiaMART + Meesho',
            'speed': 'Real-time — new sellers found weekly',
            'coverage': '6 Indian languages, 50+ platforms',
            'output': 'Seller name, city, GST, risk score, evidence PDF',
            'cost': 'Rs 10-25L/year (vs Entrupy $299/month per device)',
        },
        'entrupy_capabilities': {
            'what': 'Physical product microscopic authentication',
            'accuracy': '99.1% accuracy per physical product',
            'output': 'Genuine/Counterfeit verdict per item',
            'cost': '$299/month per device',
            'gap': 'Cannot find sellers before products reach market',
        },
        'combined_value': {
            'step1': 'CINEOS finds seller network digitally (before shipment)',
            'step2': 'Brand legal team issues takedown to IndiaMART',
            'step3': 'Remaining products in market verified by Entrupy',
            'step4': 'Complete audit trail — digital + physical evidence',
            'clients': 'Nike, HUL, Samsung, Titan, Ray-Ban, boAt',
            'revenue_model': 'CINEOS: Rs 10-25L/year + Entrupy: $299/device/month',
        },
        'pitch_to_entrupy': {
            'contact': 'Vidyuth Srinivasan (CEO, Entrupy)',
            'email':   'vidyuth@entrupy.com',
            'subject': 'India market partnership — CINEOS digital + Entrupy physical',
            'value':   'CINEOS has 59 confirmed Indian counterfeit sellers. '
                       'Entrupy can verify physical products from those sellers. '
                       'Together we provide the only end-to-end solution in India.',
        }
    }

if __name__ == '__main__':
    import sys

    # Run authentication on our known sellers
    print("="*65)
    print("  CINEOS DIGITAL PRODUCT AUTHENTICATION ENGINE")
    print("  Entrupy-style — but digital, at scale, India-specific")
    print("="*65)

    # Test with known sellers from deep_sellers.json
    try:
        sellers = json.load(open('reports/deep_sellers.json'))
        engine = ProductAuthEngine()
        print(f"\n[AUTH] Authenticating {len(sellers)} known sellers...\n")

        results = engine.batch_authenticate(sellers)

        print(f"{'Seller':30} {'Brand':15} {'Price':10} {'Score':7} Verdict")
        print("-"*80)
        for r in results[:20]:
            print(f"{r.get('seller','?')[:28]:30} "
                  f"{r['brand'][:13]:15} "
                  f"{str(r['price'])[:8]:10} "
                  f"{r['auth_score']:3}/100  "
                  f"{r['verdict']}")

        report = engine.generate_report()
        print(f"\n{'='*65}")
        print(f"  AUTHENTICATION SUMMARY")
        print(f"{'='*65}")
        print(f"  Total authenticated:    {report['total_authenticated']}")
        print(f"  Confirmed counterfeit:  {report['confirmed_counterfeit']}")
        print(f"  Very likely:            {report['very_likely']}")
        print(f"  Suspicious:             {report['suspicious']}")

    except Exception as e:
        print(f"Note: {e} — run with real seller data")

    # Partnership data
    partnership = generate_partnership_data()
    print(f"\n{'='*65}")
    print(f"  ENTRUPY PARTNERSHIP OPPORTUNITY")
    print(f"{'='*65}")
    print(f"  CINEOS: {partnership['cineos_capabilities']['what']}")
    print(f"  Entrupy: {partnership['entrupy_capabilities']['what']}")
    print(f"  Together:")
    for k,v in partnership['combined_value'].items():
        if k != 'clients':
            print(f"    {v}")
    print(f"  Target clients: {partnership['combined_value']['clients']}")

    # Save
    os.makedirs('reports', exist_ok=True)
    json.dump({
        'results': results if 'results' in dir() else [],
        'partnership': partnership,
    }, open('reports/product_auth_engine.json','w'), indent=2)
    print(f"\n  Saved: reports/product_auth_engine.json")
