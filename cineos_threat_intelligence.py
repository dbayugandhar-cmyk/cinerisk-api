"""
CINEOS Digital Threat Intelligence
Three verticals — all using public data only:

1. Financial Fraud Detection
2. Counterfeit Product Detection  
3. Misinformation Detection

Legal: Public data only. No unauthorized access.
Purpose: Evidence for regulators, brands, law enforcement.
"""
import asyncio, httpx, re, json, os, datetime
from urllib.parse import urlparse

SERP_KEY = os.environ.get('SERP_API_KEY','')

# ══════════════════════════════════════════════════════════
# VERTICAL 1 — FINANCIAL FRAUD DETECTION
# Target clients: SEBI, RBI, NSE, Zerodha, HDFC Bank
# Revenue: Rs 50L-5Cr/year government, Rs 10-50L/month banks
# ══════════════════════════════════════════════════════════

FINANCIAL_FRAUD_SIGNALS = {
    'illegal_betting': [
        '1xbet', 'bet365', 'betway', 'reddy anna', 'satta matka',
        'online satta', '96win', 'fairplay', 'ipl betting',
        'cricket betting odds', 'match fixing tips',
    ],
    'fake_investment': [
        'guaranteed returns', 'daily profit guaranteed',
        'risk free investment', 'double your money',
        'fixed monthly returns', 'no loss trading',
        '100 percent profit', 'assured returns',
        'guaranteed profit trading', 'sebi registered tips',
    ],
    'fake_trading_app': [
        'copy trading guaranteed', 'algo profit guaranteed',
        'intraday tips 100 accuracy', 'option tips sure shot',
        'nifty sure shot calls', 'free premium signals',
    ],
    'crypto_scam': [
        'crypto doubler', 'bitcoin guaranteed profit',
        'crypto arbitrage guaranteed', 'token presale guaranteed',
        'nft guaranteed returns', 'defi fixed returns',
    ],
    'fake_ipo': [
        'ipo allotment guaranteed', 'ipo grey market tips insider',
        'guaranteed ipo listing gain', 'ipo sure shot profit',
    ]
}

async def scan_financial_fraud(deep: bool = True) -> dict:
    """Deep scan for financial fraud across Telegram, web, Instagram."""
    results = {'channels':[], 'websites':[], 'social':[], 'apps':[]}
    
    if not SERP_KEY:
        return results
    
    async with httpx.AsyncClient(timeout=12,
        headers={"User-Agent":"Mozilla/5.0"},
        follow_redirects=True) as client:
        
        queries = [
            # Telegram channels
            'site:t.me "guaranteed returns" OR "daily profit" india',
            'site:t.me "cricket betting" OR "satta matka" india 2026',
            'site:t.me "stock tips guaranteed" OR "option tips 100%" india',
            'site:t.me "crypto guaranteed" OR "bitcoin profit" india',
            # Websites
            '"guaranteed returns" investment india telegram -sebi -registered',
            '"daily profit" trading india website -zerodha -groww',
            # Apps
            'fake trading app india sebi warning 2026',
            '"unregistered" investment app india fraud 2026',
            # Instagram
            '"guaranteed profit" investment instagram india reel',
        ]
        
        seen_urls = set()
        
        for q in queries:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "q": q, "api_key": SERP_KEY,
                    "num": 10, "engine": "google", "gl": "in"
                })
                
                for item in r.json().get("organic_results", []):
                    url = item.get("link","")
                    title = item.get("title","").lower()
                    snippet = item.get("snippet","").lower()
                    combined = f"{title} {snippet} {url}".lower()
                    
                    if url in seen_urls: continue
                    
                    # Skip legitimate financial sites
                    legit = ['zerodha','groww','sebi.gov','rbi.org',
                            'moneycontrol','economictimes','ndtv',
                            'bseindia','nseindia','amfiindia']
                    if any(l in url.lower() for l in legit): continue
                    
                    # Detect fraud type
                    fraud_types = []
                    for ftype, signals in FINANCIAL_FRAUD_SIGNALS.items():
                        if any(s in combined for s in signals):
                            fraud_types.append(ftype)
                    
                    if not fraud_types: continue
                    
                    seen_urls.add(url)
                    entry = {
                        'url': url,
                        'title': item.get("title","")[:80],
                        'fraud_types': fraud_types,
                        'snippet': snippet[:100],
                        'detected_at': datetime.datetime.now().isoformat()
                    }
                    
                    if 't.me/' in url:
                        ch = re.search(r't\.me/([a-zA-Z]\w{3,30})', url)
                        if ch:
                            entry['channel'] = ch.group(1)
                            results['channels'].append(entry)
                    elif 'instagram.com' in url:
                        results['social'].append(entry)
                    else:
                        results['websites'].append(entry)
                        
            except: pass
    
    return results

# ══════════════════════════════════════════════════════════
# VERTICAL 2 — COUNTERFEIT PRODUCT DETECTION
# Target: HUL, P&G, Sun Pharma, Amazon, Flipkart
# Revenue: Rs 10-50L/month per brand
# ══════════════════════════════════════════════════════════

MAJOR_INDIA_BRANDS = {
    'fmcg': ['Dove','Surf Excel','Lifebuoy','Horlicks','Boost',
             'Colgate','Dettol','Ariel','Pantene','Head Shoulders'],
    'pharma': ['Crocin','Dolo','Pan D','Omez','Glycomet',
               'Ecosprin','Combiflam','Augmentin'],
    'electronics': ['Samsung Galaxy','Realme','Redmi','boAt',
                    'OnePlus','JBL','Sony WH'],
    'luxury': ['Ray-Ban','Fossil','Titan','Tanishq','Manyavar'],
    'sports': ['Nike','Adidas','Puma','Reebok','Bata']
}

COUNTERFEIT_SIGNALS = [
    'first copy', '1st copy', 'replica', 'super copy',
    'imported copy', 'master copy', 'AAA quality',
    'original quality', 'same as original', 'factory outlet',
    'wholesale price', 'bulk available', 'original box',
    'super duplicate', 'high quality copy', 'identical',
    'unboxed', 'open box same as original'
]

COUNTERFEIT_PLATFORMS = [
    'meesho.com', 'indiamart.com', 'tradeindia.com',
    'sulekha.com', 'olx.in', 'quikr.com',
    'facebook.com/marketplace', 'instagram.com',
    'glowroad.com', 'shop101.com'
]

async def scan_counterfeits(brand: str, category: str = 'fmcg') -> dict:
    """Deep scan for counterfeit products of a specific brand."""
    results = []
    
    if not SERP_KEY:
        return {'brand': brand, 'listings': []}
    
    async with httpx.AsyncClient(timeout=12,
        headers={"User-Agent":"Mozilla/5.0"},
        follow_redirects=True) as client:
        
        # Build targeted queries
        platform_q = ' OR '.join(f'site:{p}' for p in COUNTERFEIT_PLATFORMS[:5])
        queries = [
            f'"{brand}" "first copy" supplier indiamart',
            f'"{brand}" duplicate wholesale indiamart',
            f'"{brand}" fake supplier wholesale india 2026',
            f'"{brand}" copy manufacturer india bulk order',
        ]
        
        seen = set()
        for q in queries:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "q": q, "api_key": SERP_KEY,
                    "num": 10, "engine": "google", "gl": "in"
                })
                
                for item in r.json().get("organic_results", []):
                    url = item.get("link","")
                    if url in seen: continue
                    
                    title = item.get("title","").lower()
                    snippet = item.get("snippet","").lower()
                    combined = f"{title} {snippet}".lower()
                    
                    # Must mention brand in title specifically
                    if brand.lower() not in title.lower(): continue
                    
                    # Must have counterfeit signals
                    signals_found = [s for s in COUNTERFEIT_SIGNALS 
                                   if s in combined]
                    if not signals_found: continue
                    
                    # Skip unrelated categories
                    unrelated = ['tour','hotel','package','travel','achkan',
                                'sherwani','hair','loreal','pantene']
                    if any(u in title.lower() for u in unrelated): continue
                    
                    # Skip official brand sites
                    if any(b.lower().replace(' ','') in urlparse(url).netloc
                          for b in [brand]): continue
                    
                    seen.add(url)
                    platform = urlparse(url).netloc.replace('www.','')
                    results.append({
                        'url': url,
                        'platform': platform,
                        'title': item.get("title","")[:80],
                        'signals': signals_found[:3],
                        'snippet': snippet[:100],
                        'risk': 'HIGH' if any(p in url for p in 
                                ['meesho','indiamart','instagram']) else 'MEDIUM'
                    })
                    
            except: pass
    
    return {
        'brand': brand,
        'category': category,
        'total_listings': len(results),
        'high_risk': len([r for r in results if r['risk']=='HIGH']),
        'listings': results,
        'scanned_at': datetime.datetime.now().isoformat()
    }

async def scan_multiple_brands(brands: list) -> list:
    """Scan multiple brands for counterfeits."""
    results = []
    for brand in brands:
        r = await scan_counterfeits(brand)
        results.append(r)
        print(f"  {brand:20} {r['total_listings']} listings "
              f"({r['high_risk']} high risk)")
    return sorted(results, key=lambda x: -x['total_listings'])

# ══════════════════════════════════════════════════════════
# VERTICAL 3 — MISINFORMATION DETECTION
# Target: Election Commission, Health Ministry, news agencies
# Revenue: Rs 50L-2Cr/year government contracts
# ══════════════════════════════════════════════════════════

MISINFO_CATEGORIES = {
    'health_misinfo': [
        'corona cure home remedy', 'cancer cure natural',
        'diabetes cure permanent', 'covid fake', 'vaccine kills',
        'government hiding cure', 'big pharma conspiracy',
        'ayurvedic cure cancer', 'miracle cure',
    ],
    'election_misinfo': [
        'voting machine hacked', 'evm tampered', 'fake election result',
        'election fraud india', 'booth capturing evidence',
        'vote count manipulation',
    ],
    'communal_misinfo': [
        'fake riot video', 'morphed image viral',
        'fake news viral whatsapp', 'edited video viral',
    ],
    'financial_misinfo': [
        'bank going bankrupt india', 'rbi printing money',
        'rupee collapse fake', 'gold price manipulation',
        'sensex crash prediction', 'economy collapse india',
    ]
}

MISINFO_PLATFORMS = [
    'whatsapp.com', 'facebook.com', 'twitter.com',
    'instagram.com', 'youtube.com', 'telegram.me',
    'sharechat.com', 'moj.tv', 'josh.app'
]

async def scan_misinformation(topic: str, category: str = 'health') -> dict:
    """Scan for misinformation on a specific topic."""
    results = []
    
    if not SERP_KEY:
        return {'topic': topic, 'misinfo_urls': []}
    
    async with httpx.AsyncClient(timeout=12) as client:
        
        signals = MISINFO_CATEGORIES.get(
            f'{category}_misinfo', 
            MISINFO_CATEGORIES['health_misinfo']
        )
        
        queries = [
            f'"{topic}" fake news india viral 2026',
            f'"{topic}" misinformation india fact check',
            f'"{topic}" false claim viral whatsapp india',
            f'"{topic}" morphed video OR edited image viral india',
        ]
        
        seen = set()
        for q in queries[:3]:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "q": q, "api_key": SERP_KEY,
                    "num": 10, "engine": "google", "gl": "in"
                })
                
                for item in r.json().get("organic_results", []):
                    url = item.get("link","")
                    if url in seen: continue
                    
                    title = item.get("title","").lower()
                    snippet = item.get("snippet","").lower()
                    combined = f"{title} {snippet}".lower()
                    
                    # Check for misinfo signals
                    signals_found = [s for s in signals if s in combined]
                    
                    # Also check fact-check sites reporting on it
                    is_factcheck = any(fc in url for fc in [
                        'altnews', 'boomlive', 'factchecker',
                        'vishvasnews', 'indiatoday/fact-check',
                        'thequint/webqoof', 'newsmobile'
                    ])
                    
                    if not signals_found and not is_factcheck: continue
                    
                    seen.add(url)
                    results.append({
                        'url': url,
                        'title': item.get("title","")[:80],
                        'signals': signals_found[:3],
                        'is_factcheck_report': is_factcheck,
                        'snippet': snippet[:100],
                        'platform': urlparse(url).netloc.replace('www.','')
                    })
                    
            except: pass
    
    misinfo = [r for r in results if not r['is_factcheck_report']]
    factchecks = [r for r in results if r['is_factcheck_report']]
    
    return {
        'topic': topic,
        'category': category,
        'misinfo_urls': len(misinfo),
        'factcheck_reports': len(factchecks),
        'results': results,
        'scanned_at': datetime.datetime.now().isoformat()
    }

# ══════════════════════════════════════════════════════════
# COMBINED INTELLIGENCE REPORT
# ══════════════════════════════════════════════════════════

async def full_threat_intelligence_scan() -> dict:
    """Run all three verticals and generate combined report."""
    now = datetime.datetime.now()
    print(f"[CINEOS] Full Threat Intelligence Scan — {now.strftime('%Y-%m-%d %H:%M')}")
    print("="*60)
    
    # 1. Financial fraud
    print("\n[1/3] Financial Fraud Detection...")
    fraud = await scan_financial_fraud()
    print(f"  Telegram channels: {len(fraud['channels'])}")
    print(f"  Fraud websites:    {len(fraud['websites'])}")
    print(f"  Social media:      {len(fraud['social'])}")
    
    # 2. Counterfeits — top brands
    print("\n[2/3] Counterfeit Detection...")
    brands = ['Dove', 'Dettol', 'Nike', 'Samsung Galaxy', 'Crocin']
    counterfeits = await scan_multiple_brands(brands)
    
    # 3. Misinformation
    print("\n[3/3] Misinformation Detection...")
    misinfo_topics = [
        ('COVID vaccine', 'health'),
        ('Election EVM', 'election'),
        ('Bank collapse India', 'financial'),
    ]
    misinfo_results = []
    for topic, category in misinfo_topics:
        r = await scan_misinformation(topic, category)
        misinfo_results.append(r)
        print(f"  {topic:25} {r['misinfo_urls']} misinfo URLs")
    
    # Save report
    report = {
        'generated_at': now.isoformat(),
        'financial_fraud': fraud,
        'counterfeits': counterfeits,
        'misinformation': misinfo_results,
        'summary': {
            'fraud_channels': len(fraud['channels']),
            'fraud_websites': len(fraud['websites']),
            'counterfeit_listings': sum(c['total_listings'] for c in counterfeits),
            'misinfo_urls': sum(m['misinfo_urls'] for m in misinfo_results),
        }
    }
    
    os.makedirs('reports', exist_ok=True)
    path = f"reports/CINEOS_ThreatIntel_{now.strftime('%Y%m%d_%H%M')}.json"
    json.dump(report, open(path,'w'), indent=2, default=str)
    
    print(f"\n{'='*60}")
    print(f"  THREAT INTELLIGENCE SUMMARY")
    print(f"{'='*60}")
    print(f"  Fraud channels     : {report['summary']['fraud_channels']}")
    print(f"  Fraud websites     : {report['summary']['fraud_websites']}")
    print(f"  Counterfeit listings: {report['summary']['counterfeit_listings']}")
    print(f"  Misinfo URLs       : {report['summary']['misinfo_urls']}")
    print(f"  Report saved: {path}")
    print(f"{'='*60}")
    
    return report

if __name__ == '__main__':
    asyncio.run(full_threat_intelligence_scan())
