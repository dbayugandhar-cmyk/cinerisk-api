"""
CINEOS Seller Identity Graph
Tracks counterfeit sellers across platforms.
Same seller selling fake products across
multiple brands = supply chain node.
"""
import asyncio, httpx, re, json, os
from urllib.parse import urlparse
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

class SellerNode:
    def __init__(self, seller_id, platform, name='', location='', contact=''):
        self.seller_id = seller_id
        self.platform = platform
        self.name = name
        self.location = location
        self.contact = contact
        self.brands_counterfeited = []
        self.listing_urls = []
        self.first_seen = datetime.now().isoformat()
        self.threat_score = 0
    
    def add_brand(self, brand, url):
        if brand not in self.brands_counterfeited:
            self.brands_counterfeited.append(brand)
        if url not in self.listing_urls:
            self.listing_urls.append(url)
        # Higher threat if selling multiple brands
        self.threat_score = len(self.brands_counterfeited) * 25

async def extract_seller_info(client, url, brand):
    """Extract seller identity from a listing URL."""
    seller = None
    try:
        r = await client.get(url, timeout=8)
        if r.status_code != 200:
            return None
        
        text = r.text
        platform = urlparse(url).netloc.lower()
        
        # Extract seller info by platform
        if 'indiamart' in platform:
            # IndiaMART seller name
            name_match = re.search(
                r'<h1[^>]*class="[^"]*company[^"]*"[^>]*>([^<]+)', text)
            loc_match = re.search(
                r'<span[^>]*class="[^"]*location[^"]*"[^>]*>([^<]+)', text)
            phone_match = re.search(r'\+91[-\s]?(\d{10})', text)
            gst_match = re.search(r'GST[:\s]+([0-9A-Z]{15})', text)
            
            seller = SellerNode(
                seller_id=f"indiamart_{hash(url) % 999999}",
                platform='IndiaMART',
                name=name_match.group(1).strip() if name_match else '',
                location=loc_match.group(1).strip() if loc_match else '',
                contact=phone_match.group(0) if phone_match else ''
            )
            if gst_match:
                seller.contact += f" GST:{gst_match.group(1)}"
        
        elif 'meesho' in platform:
            # Meesho seller info
            supplier_match = re.search(
                r'"supplierName"[:\s]+"([^"]+)"', text)
            seller = SellerNode(
                seller_id=f"meesho_{hash(url) % 999999}",
                platform='Meesho',
                name=supplier_match.group(1) if supplier_match else ''
            )
        
        elif 'facebook' in platform or 'instagram' in platform:
            # Facebook/Instagram too obfuscated for reliable extraction
            # Record URL only as evidence — no seller name extraction
            seller = SellerNode(
                seller_id=f"social_{hash(url) % 999999}",
                platform='Instagram/Facebook',
                name=f"Social seller ({urlparse(url).path[:30]})"
            )
        
        if seller:
            seller.add_brand(brand, url)
    
    except Exception as e:
        pass
    
    return seller

async def build_seller_graph(brand_results: list) -> dict:
    """
    Build seller identity graph from counterfeit scan results.
    Connects same sellers selling multiple fake brands.
    """
    print(f"[SELLER-GRAPH] Building seller network...")
    
    all_sellers = {}
    
    async with httpx.AsyncClient(
        timeout=10,
        headers={"User-Agent":"Mozilla/5.0"},
        follow_redirects=True
    ) as client:
        
        for result in brand_results:
            brand = result.get('brand','')
            listings = result.get('listings', [])
            
            print(f"  Analyzing {len(listings)} {brand} listings...")
            
            for listing in listings[:10]:
                url = listing.get('url','')
                if not url: continue
                
                seller = await extract_seller_info(client, url, brand)
                
                if seller and seller.name:
                    # Check if same seller found before
                    key = seller.name.lower().strip()
                    if key in all_sellers:
                        # Same seller — add this brand
                        all_sellers[key].add_brand(brand, url)
                        print(f"  REPEAT SELLER: {seller.name} "
                              f"— now selling {len(all_sellers[key].brands_counterfeited)} brands")
                    else:
                        all_sellers[key] = seller
    
    # Find high-threat sellers
    repeat_offenders = [
        s for s in all_sellers.values()
        if len(s.brands_counterfeited) > 1
    ]
    
    repeat_offenders.sort(key=lambda x: -x.threat_score)
    
    print(f"\n[SELLER-GRAPH] Total sellers: {len(all_sellers)}")
    print(f"[SELLER-GRAPH] Repeat offenders: {len(repeat_offenders)}")
    
    for s in repeat_offenders[:5]:
        print(f"  THREAT {s.threat_score}: {s.name} ({s.platform})")
        print(f"    Brands: {s.brands_counterfeited}")
        print(f"    Location: {s.location}")
    
    return {
        'total_sellers': len(all_sellers),
        'repeat_offenders': len(repeat_offenders),
        'sellers': [
            {
                'name': s.name,
                'platform': s.platform,
                'location': s.location,
                'contact': s.contact,
                'brands': s.brands_counterfeited,
                'listings': s.listing_urls[:3],
                'threat_score': s.threat_score,
            }
            for s in sorted(all_sellers.values(), 
                          key=lambda x: -x.threat_score)[:20]
        ],
        'high_threat': [
            {
                'name': s.name,
                'platform': s.platform,
                'location': s.location,
                'brands_count': len(s.brands_counterfeited),
                'brands': s.brands_counterfeited,
                'threat_score': s.threat_score,
            }
            for s in repeat_offenders
        ]
    }

async def scan_seller_network():
    """Full seller network scan across top brands."""
    from cineos_threat_intelligence import scan_counterfeits
    
    brands = ['Dove', 'Dettol', 'Nike', 'Samsung Galaxy', 'Crocin']
    brand_results = []
    
    print("Scanning brands for counterfeit listings...")
    for brand in brands:
        result = await scan_counterfeits(brand)
        brand_results.append(result)
        print(f"  {brand}: {result['total_listings']} listings")
    
    # Build seller graph
    graph = await build_seller_graph(brand_results)
    
    # Save
    os.makedirs('reports', exist_ok=True)
    path = f"reports/seller_graph_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(graph, open(path,'w'), indent=2)
    
    print(f"\n{'='*60}")
    print(f"  CINEOS SELLER INTELLIGENCE REPORT")
    print(f"{'='*60}")
    print(f"  Total sellers identified: {graph['total_sellers']}")
    print(f"  Repeat offenders: {graph['repeat_offenders']}")
    if graph['high_threat']:
        print(f"\n  HIGH THREAT SELLERS:")
        for s in graph['high_threat'][:5]:
            print(f"  [{s['threat_score']} pts] {s['name']} ({s['platform']})")
            print(f"    Selling fakes of: {', '.join(s['brands'])}")
    print(f"{'='*60}")
    print(f"  Report: {path}")
    
    return graph

if __name__ == '__main__':
    asyncio.run(scan_seller_network())
