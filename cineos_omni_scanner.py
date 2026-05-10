"""
CINEOS Omni-Platform Scanner
Scans EVERY platform where fraud happens in India.
This is what makes CINEOS impossible to replicate:
  - 6 Indian languages
  - 12 platforms simultaneously  
  - India-specific fraud patterns
  - Real-time attribution graph
  
Platforms:
  Telegram    ✓ (built)
  Discord     ✓ (built)
  Reddit      ✓ (built)
  Instagram   ✓ (built)
  WhatsApp    ✓ (built)
  Snapchat    → build now
  YouTube     → build now
  Twitter/X   → build now
  LinkedIn    → build now
  ShareChat   → build now (India-specific)
  Koo         → build now (India-specific)
  Josh/Moj    → build now (India short video)
  Meesho      → build now
  IndiaMART   ✓ (built)
  Dark Web    ✓ (built)
  Pastebin    ✓ (built)
"""
import asyncio, httpx, re, json, os
from datetime import datetime
from telethon import TelegramClient

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"
SERP_KEY = os.environ.get('SERP_API_KEY','')

# ── INDIA-SPECIFIC FRAUD PATTERNS ────────────────────────
# These are patterns ONLY an India-focused platform knows
INDIA_FRAUD_PATTERNS = {
    'betting': {
        'english': ['betting','satta','matka','cricket tips','ipl bet',
                    'reddy anna','mahadev book','lotusbook','betbhai'],
        'hindi':   ['सट्टा','मटका','बेटिंग','क्रिकेट टिप्स','आईपीएल बेट'],
        'telugu':  ['బెట్టింగ్','సట్టా','క్రికెట్ టిప్స్'],
        'tamil':   ['பெட்டிங்','சட்டா','கிரிக்கெட் டிப்ஸ்'],
        'kannada': ['ಬೆಟ್ಟಿಂಗ್','ಸಟ್ಟಾ','ಕ್ರಿಕೆಟ್'],
        'malayalam':['ബെറ്റ്','ക്രിക്കറ്റ്'],
    },
    'investment_fraud': {
        'english': ['guaranteed returns','daily profit','mlm','earn from home',
                    'stock tips','sebi registered','zerodha tips','groww tips',
                    'free signals','pump','pump and dump','100x coin'],
        'hindi':   ['रोज कमाओ','घर बैठे कमाई','गारंटीड रिटर्न','निवेश'],
        'telugu':  ['రోజు సంపాదన','గ్యారెంటీ రిటర్న్స్','ఇన్వెస్ట్మెంట్'],
    },
    'counterfeit': {
        'english': ['first copy','master copy','1st copy','aaa grade',
                    'replica','copy shoes','copy watch','original quality',
                    'same as branded','wholesale copy'],
        'hindi':   ['फर्स्ट कॉपी','नकली','थोक','ओरिजिनल क्वालिटी'],
        'telugu':  ['ఫస్ట్ కాపీ','నకిలీ','హోల్సేల్'],
    },
    'job_scam': {
        'english': ['work from home','data entry job','online job','part time job',
                    'earn 5000 daily','paid tasks','telegram job'],
        'hindi':   ['घर से काम','ऑनलाइन जॉब','डेटा एंट्री','पार्ट टाइम'],
    },
    'loan_fraud': {
        'english': ['instant loan','quick loan','aadhar loan','loan without cibil',
                    'loan app','personal loan 5 minutes'],
        'hindi':   ['तुरंत लोन','आधार लोन','बिना सिबिल लोन'],
    },
    'crypto_fraud': {
        'english': ['bitcoin doubler','crypto pump','free crypto','airdrop',
                    'web3 earning','defi profit','nft mint','100x guaranteed'],
        'hindi':   ['क्रिप्टो पंप','फ्री बिटकॉइन','एयरड्रॉप'],
    },
    'piracy': {
        'english': ['free download','hd movies','web series download',
                    'netflix free','hotstar free','ott free'],
        'hindi':   ['फिल्म डाउनलोड','वेब सीरीज','फ्री मूवी'],
        'telugu':  ['సినిమా డౌన్లోడ్','తెలుగు మూవీ'],
        'tamil':   ['தமிழ் படம்','டவுன்லோட்'],
    },
}

ALL_PATTERNS = []
for category, langs in INDIA_FRAUD_PATTERNS.items():
    for lang, terms in langs.items():
        for term in terms:
            ALL_PATTERNS.append({
                'term': term,
                'category': category,
                'language': lang,
            })

print(f"Total India-specific fraud patterns: {len(ALL_PATTERNS)}")
print(f"Categories: {list(INDIA_FRAUD_PATTERNS.keys())}")
print(f"Languages: English, Hindi, Telugu, Tamil, Kannada, Malayalam")

class OmniScanner:
    """Scan all platforms where India fraud happens."""

    def __init__(self):
        self.findings = {p: [] for p in [
            'telegram','discord','reddit','instagram',
            'whatsapp','youtube','twitter','sharechat',
            'koo','meesho','indiamart','snapchat','linkedin'
        ]}
        self.total = 0

    async def scan_youtube(self, client, query, category):
        """YouTube fraud channel detection."""
        try:
            r = await client.get("https://serpapi.com/search", params={
                "engine": "youtube",
                "search_query": f"{query} india fraud",
                "api_key": SERP_KEY,
            }, timeout=10)
            results = r.json().get("video_results", [])
            for v in results[:5]:
                title = v.get("title","").lower()
                if any(p['term'] in title for p in ALL_PATTERNS):
                    self.findings['youtube'].append({
                        "title": v.get("title",""),
                        "channel": v.get("channel",{}).get("name",""),
                        "views": v.get("views",""),
                        "url": v.get("link",""),
                        "category": category,
                        "platform": "youtube",
                    })
                    self.total += 1
        except Exception as e:
            pass

    async def scan_twitter(self, client, query, category):
        """Twitter/X fraud detection via SerpAPI."""
        try:
            r = await client.get("https://serpapi.com/search", params={
                "engine": "google",
                "q": f"site:twitter.com OR site:x.com {query} india fraud scam",
                "api_key": SERP_KEY,
                "num": 10, "gl": "in",
            }, timeout=10)
            for item in r.json().get("organic_results", []):
                link = item.get("link","")
                if "twitter.com" in link or "x.com" in link:
                    self.findings['twitter'].append({
                        "title": item.get("title",""),
                        "snippet": item.get("snippet","")[:100],
                        "url": link,
                        "category": category,
                        "platform": "twitter",
                    })
                    self.total += 1
        except:
            pass

    async def scan_sharechat(self, client, query, category):
        """ShareChat — India's largest vernacular platform."""
        try:
            r = await client.get("https://serpapi.com/search", params={
                "engine": "google",
                "q": f"site:sharechat.com {query}",
                "api_key": SERP_KEY,
                "num": 10, "gl": "in",
            }, timeout=10)
            for item in r.json().get("organic_results", []):
                if "sharechat.com" in item.get("link",""):
                    self.findings['sharechat'].append({
                        "title": item.get("title",""),
                        "url": item.get("link",""),
                        "category": category,
                        "platform": "sharechat",
                    })
                    self.total += 1
        except:
            pass

    async def scan_meesho(self, client, brand, category):
        """Meesho — 150M users, major counterfeit hub."""
        try:
            r = await client.get("https://serpapi.com/search", params={
                "engine": "google",
                "q": f"site:meesho.com {brand} copy OR replica OR first copy",
                "api_key": SERP_KEY,
                "num": 10, "gl": "in",
            }, timeout=10)
            for item in r.json().get("organic_results", []):
                if "meesho.com" in item.get("link",""):
                    title = item.get("title","").lower()
                    if any(p['term'] in title for p in ALL_PATTERNS
                           if p['category']=='counterfeit'):
                        self.findings['meesho'].append({
                            "title": item.get("title",""),
                            "url": item.get("link",""),
                            "brand": brand,
                            "category": "counterfeit",
                            "platform": "meesho",
                        })
                        self.total += 1
        except:
            pass

    async def scan_koo(self, client, query, category):
        """Koo — Indian Twitter alternative, fraud hotspot."""
        try:
            r = await client.get("https://serpapi.com/search", params={
                "engine": "google",
                "q": f"site:kooapp.com {query} fraud OR scam OR fake",
                "api_key": SERP_KEY,
                "num": 10, "gl": "in",
            }, timeout=10)
            for item in r.json().get("organic_results", []):
                if "kooapp.com" in item.get("link",""):
                    self.findings['koo'].append({
                        "title": item.get("title",""),
                        "url": item.get("link",""),
                        "category": category,
                        "platform": "koo",
                    })
                    self.total += 1
        except:
            pass

    async def scan_snapchat(self, client, query, category):
        """Snapchat — growing fraud vector in India."""
        try:
            r = await client.get("https://serpapi.com/search", params={
                "engine": "google",
                "q": f"site:snapchat.com {query} india scam OR fraud",
                "api_key": SERP_KEY,
                "num": 10, "gl": "in",
            }, timeout=10)
            for item in r.json().get("organic_results", []):
                if "snapchat.com" in item.get("link",""):
                    self.findings['snapchat'].append({
                        "title": item.get("title",""),
                        "url": item.get("link",""),
                        "category": category,
                        "platform": "snapchat",
                    })
                    self.total += 1
        except:
            pass

    async def scan_linkedin(self, client, query, category):
        """LinkedIn — job scams and fake investment profiles."""
        try:
            r = await client.get("https://serpapi.com/search", params={
                "engine": "google",
                "q": f"site:linkedin.com {query} india fake scam",
                "api_key": SERP_KEY,
                "num": 10, "gl": "in",
            }, timeout=10)
            for item in r.json().get("organic_results", []):
                if "linkedin.com" in item.get("link",""):
                    self.findings['linkedin'].append({
                        "title": item.get("title",""),
                        "url": item.get("link",""),
                        "category": category,
                        "platform": "linkedin",
                    })
                    self.total += 1
        except:
            pass

    async def run_full_scan(self):
        """Run complete omni-platform scan."""
        print("="*65)
        print("  CINEOS OMNI-PLATFORM SCANNER")
        print("  Every platform. Every language. Every fraud type.")
        print("="*65)

        scan_queries = [
            ("IPL betting satta", "betting"),
            ("guaranteed returns telegram", "investment_fraud"),
            ("work from home job india", "job_scam"),
            ("instant loan aadhar", "loan_fraud"),
            ("crypto pump signal india", "crypto_fraud"),
            ("first copy shoes wholesale", "counterfeit"),
            ("free netflix hotstar telegram", "piracy"),
        ]

        brands_for_meesho = [
            "Nike", "Adidas", "Samsung", "Apple",
            "Dove", "Dettol", "boAt", "Ray-Ban",
        ]

        async with httpx.AsyncClient(
            headers={'User-Agent':'Mozilla/5.0'},
            timeout=15
        ) as client:
            # Scan all platforms
            tasks = []
            for query, category in scan_queries:
                tasks.extend([
                    self.scan_youtube(client, query, category),
                    self.scan_twitter(client, query, category),
                    self.scan_sharechat(client, query, category),
                    self.scan_koo(client, query, category),
                    self.scan_snapchat(client, query, category),
                    self.scan_linkedin(client, query, category),
                ])

            # Meesho brand scans
            for brand in brands_for_meesho[:4]:
                tasks.append(self.scan_meesho(client, brand, "counterfeit"))

            # Run all concurrently
            print(f"\n[SCAN] Running {len(tasks)} concurrent platform scans...")
            await asyncio.gather(*tasks, return_exceptions=True)

        print(f"\n{'='*65}")
        print(f"  OMNI-SCAN RESULTS")
        print(f"{'='*65}")
        print(f"  Total findings: {self.total}")
        print()
        for platform, findings in self.findings.items():
            if findings:
                print(f"  {platform.upper():15} {len(findings)} findings")
                for f in findings[:3]:
                    print(f"    → {f.get('title','?')[:60]}")

        # Save
        os.makedirs('reports', exist_ok=True)
        path = f"reports/omni_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        json.dump({
            'scanned_at': datetime.now().isoformat(),
            'total_findings': self.total,
            'platforms': self.findings,
            'patterns_used': len(ALL_PATTERNS),
        }, open(path,'w'), indent=2)
        print(f"\n  Saved: {path}")
        return self.findings

if __name__ == '__main__':
    scanner = OmniScanner()
    asyncio.run(scanner.run_full_scan())
