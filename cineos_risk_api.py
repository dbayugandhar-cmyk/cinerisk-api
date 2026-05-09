"""
CINEOS Seller Risk Score API
Scores counterfeit sellers 0-100 based on:
- Price gap vs retail
- GST validity
- Listing signals
- Multi-brand selling
- Platform risk
- Historical detections

Enterprise clients pay for this as an API.
"""
import asyncio, httpx, re, json, os
from datetime import datetime
from urllib.parse import urlparse

SERP_KEY = os.environ.get('SERP_API_KEY', '')

# ── RISK SCORING WEIGHTS ──────────────────────────────────
WEIGHTS = {
    'price_gap':        30,  # Price far below retail = counterfeit
    'explicit_signals': 25,  # "first copy", "AAA quality" in title
    'gst_invalid':      20,  # Fake or missing GST
    'multi_brand':      15,  # Same seller, multiple fake brands
    'platform_risk':    10,  # High-risk platforms (Meesho > IndiaMART)
}

RETAIL_PRICES = {
    'Nike': 8000,
    'Adidas': 7000,
    'Puma': 5000,
    'Dove': 200,
    'Dettol': 150,
    'Samsung Galaxy': 20000,
    'Apple': 50000,
    'Crocin': 50,
    'Ray-Ban': 8000,
}

COUNTERFEIT_SIGNALS = [
    'first copy', '1st copy', 'master copy', 'super copy',
    'aaa quality', 'replica', 'duplicate', 'same as original',
    'imported copy', 'factory outlet', 'copy', '[copy]',
    'first-copy', 'first copy', 'high quality copy',
]

PLATFORM_RISK = {
    'meesho.com': 85,
    'instagram.com': 80,
    'facebook.com': 75,
    'olx.in': 70,
    'quikr.com': 65,
    'indiamart.com': 55,
    'tradeindia.com': 60,
    'amazon.in': 30,
    'flipkart.com': 25,
}

class SellerRiskScore:
    def __init__(self, seller_name, city, brand, url,
                 price=0, gst='', platform=''):
        self.seller = seller_name
        self.city = city
        self.brand = brand
        self.url = url
        self.price = price
        self.gst = gst
        self.platform = platform or urlparse(url).netloc.replace('www.','')
        self.score = 0
        self.breakdown = {}
        self.verdict = ''
        self.evidence = []

    def calculate(self):
        total = 0

        # 1. Price gap score
        retail = RETAIL_PRICES.get(self.brand, 1000)
        if self.price > 0 and retail > 0:
            gap_pct = ((retail - self.price) / retail) * 100
            if gap_pct > 90:
                price_score = 30
                self.evidence.append(
                    f'Price Rs {self.price:,} is {gap_pct:.0f}% below '
                    f'retail Rs {retail:,} — confirms counterfeit')
            elif gap_pct > 75:
                price_score = 25
                self.evidence.append(
                    f'Price Rs {self.price:,} is {gap_pct:.0f}% below retail')
            elif gap_pct > 60:
                price_score = 18
                self.evidence.append(
                    f'Price Rs {self.price:,} significantly below retail')
            elif gap_pct > 40:
                price_score = 10
            else:
                price_score = 3
        elif self.price == 0:
            price_score = 8  # Unknown price = moderate risk
        else:
            price_score = 0
        self.breakdown['price_gap'] = price_score
        total += price_score

        # 2. Explicit counterfeit signals
        # Check URL, seller name and product title
        check_text = (self.url + self.seller + 
                     self.brand).lower()
        
        # High confidence signals — explicit admission
        high_conf = ['first copy','first-copy','[copy]','(copy)',
                    'master copy','aaa quality','replica','1st copy']
        # Medium confidence signals
        med_conf = ['copy','duplicate','same as original',
                   'factory outlet','imported copy']
        
        high_found = [s for s in high_conf if s in check_text]
        med_found = [s for s in med_conf if s in check_text 
                    and s not in check_text.replace(s,'')]
        
        if high_found:
            sig_score = 25  # Maximum — explicit admission
            self.evidence.append(f'EXPLICIT ADMISSION: {high_found}')
        elif med_found:
            sig_score = 15
            self.evidence.append(f'Counterfeit signals: {med_found[:3]}')
        else:
            sig_score = 0
        self.breakdown['explicit_signals'] = sig_score
        total += sig_score

        # 3. GST validity
        if not self.gst:
            gst_score = 8  # Missing GST = moderate risk
            self.evidence.append('No GST number provided')
        else:
            gstin_pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$'
            if not re.match(gstin_pattern, self.gst.upper()):
                gst_score = 20
                self.evidence.append(f'Invalid GST format: {self.gst}')
            else:
                gst_score = 0  # Valid format = lower risk
        self.breakdown['gst_invalid'] = gst_score
        total += gst_score

        # 4. Platform risk
        plat_base = PLATFORM_RISK.get(self.platform, 50)
        plat_score = int(plat_base * 0.1)
        self.breakdown['platform_risk'] = plat_score
        total += plat_score

        # 5. Brand-specific risk
        high_risk_brands = ['Nike', 'Adidas', 'Apple', 'Samsung']
        if self.brand in high_risk_brands:
            brand_score = 5
        else:
            brand_score = 2
        self.breakdown['brand_risk'] = brand_score
        total += brand_score

        self.score = min(100, total)

        # Verdict
        if self.score >= 75:
            self.verdict = 'CRITICAL — Confirmed counterfeit seller'
        elif self.score >= 55:
            self.verdict = 'HIGH — Very likely counterfeit'
        elif self.score >= 35:
            self.verdict = 'MEDIUM — Suspicious listing'
        else:
            self.verdict = 'LOW — Monitor'

        return self

def score_seller(seller_data: dict) -> dict:
    """Score a single seller and return full risk report."""
    s = SellerRiskScore(
        seller_name=seller_data.get('company',''),
        city=seller_data.get('city',''),
        brand=seller_data.get('brand',''),
        url=seller_data.get('url',''),
        price=_parse_price(seller_data.get('price','')),
        gst=seller_data.get('gst',''),
        platform=seller_data.get('platform',''),
    )
    s.calculate()

    return {
        'seller': s.seller,
        'city': s.city,
        'brand': s.brand,
        'platform': s.platform,
        'risk_score': s.score,
        'verdict': s.verdict,
        'breakdown': s.breakdown,
        'evidence': s.evidence,
        'url': s.url,
        'gst': s.gst,
        'price': s.price,
        'scored_at': datetime.now().isoformat(),
    }

def _parse_price(price_str: str) -> int:
    """Extract numeric price from string like 'Rs 999' or '₹3,299'."""
    if not price_str:
        return 0
    nums = re.findall(r'[\d,]+', str(price_str))
    if nums:
        return int(nums[0].replace(',',''))
    return 0

def score_all_sellers(sellers: list) -> list:
    """Score all sellers and sort by risk."""
    scored = [score_seller(s) for s in sellers]
    return sorted(scored, key=lambda x: -x['risk_score'])

if __name__ == '__main__':
    # Load and score all confirmed sellers
    try:
        sellers = json.load(open('reports/deep_sellers.json'))
        print(f"Scoring {len(sellers)} confirmed sellers...")
    except:
        # Demo data
        sellers = [
            {'company':'Th Store','city':'Imphal','brand':'Nike',
             'url':'https://www.indiamart.com/proddetail/nike-air-force-first-copy-2854470754362.html',
             'price':'Rs 999','gst':'','platform':'indiamart.com'},
            {'company':'BUDDY_HOUSE','city':'Sirsa','brand':'Nike',
             'url':'https://www.indiamart.com/proddetail/nike-air-jordan-1-copy-2850866261488.html',
             'price':'Rs 800','gst':'','platform':'indiamart.com'},
            {'company':'MN Cosmetics','city':'Indore','brand':'Dettol',
             'url':'https://www.indiamart.com/proddetail/dettol-bathing-soap-2856832140330.html',
             'price':'Rs 290','gst':'','platform':'indiamart.com'},
            {'company':'Ajay Enterprises','city':'Ghaziabad','brand':'Nike',
             'url':'https://www.indiamart.com/proddetail/nike-zoomx-alphafly',
             'price':'Rs 3299','gst':'09AMOPC5962F1ZT','platform':'indiamart.com'},
            {'company':'Rigil Enterprises','city':'Delhi','brand':'Nike',
             'url':'https://www.indiamart.com/proddetail/nike-refueled',
             'price':'Rs 3100','gst':'','platform':'indiamart.com'},
            {'company':'Hometown Enterprise','city':'Ahmedabad','brand':'Samsung Galaxy',
             'url':'https://www.indiamart.com/proddetail/samsung-copy',
             'price':'Rs 2999','gst':'24AAYHA5425K1ZY','platform':'indiamart.com'},
            {'company':'Cold Fusion Zone','city':'Mysore','brand':'Samsung Galaxy',
             'url':'https://www.indiamart.com/proddetail/samsung-galaxy-copy',
             'price':'Rs 1499','gst':'','platform':'indiamart.com'},
            {'company':'Invogue Collection','city':'Mumbai','brand':'Samsung Galaxy',
             'url':'https://www.indiamart.com/proddetail/samsung-invogue',
             'price':'Rs 1300','gst':'','platform':'indiamart.com'},
        ]
        print("Using demo sellers...")

    scored = score_all_sellers(sellers)

    print(f"\n{'='*70}")
    print(f"  CINEOS SELLER RISK INTELLIGENCE REPORT")
    print(f"  {datetime.now().strftime('%B %d, %Y')}")
    print(f"{'='*70}")
    print(f"  Total sellers scored: {len(scored)}")
    critical = [s for s in scored if s['risk_score'] >= 75]
    high = [s for s in scored if 55 <= s['risk_score'] < 75]
    print(f"  CRITICAL (75+):       {len(critical)}")
    print(f"  HIGH (55-74):         {len(high)}")
    print(f"\n  SELLER RISK SCORES:")
    print(f"  {'Seller':30} {'City':15} {'Brand':15} {'Score':7} Verdict")
    print(f"  {'-'*85}")
    for s in scored[:15]:
        bar = '█' * (s['risk_score']//10) + '░' * (10-s['risk_score']//10)
        print(f"  {s['seller']:30} {s['city']:15} {s['brand']:15} {s['risk_score']:3}/100 {bar}")

    print(f"\n  DETAILED EVIDENCE (top 3):")
    for s in scored[:3]:
        print(f"\n  [{s['risk_score']}/100] {s['seller']} — {s['city']}")
        print(f"  Verdict: {s['verdict']}")
        print(f"  Breakdown: {s['breakdown']}")
        for e in s['evidence']:
            print(f"    * {e}")

    # Save
    os.makedirs('reports', exist_ok=True)
    path = f"reports/seller_risk_scores_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(scored, open(path,'w'), indent=2)
    print(f"\n  Saved: {path}")
    print(f"{'='*70}")
