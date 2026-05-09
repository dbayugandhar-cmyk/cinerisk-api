"""
CINEOS Financial Fraud Intelligence
Detects investment scams, fake trading apps,
illegal betting and financial fraud on public platforms.

Legal: Monitors only PUBLIC channels and websites.
Purpose: Generate evidence for SEBI, RBI, law enforcement.
"""
import asyncio, httpx, re, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

# ── FRAUD SIGNAL CATEGORIES ───────────────────────────────
FRAUD_SIGNALS = {
    'fake_investment': [
        'guaranteed returns', 'daily profit', '100% profit',
        'risk free investment', 'double your money', 'mlm',
        'pyramid scheme', 'ponzi', 'get rich quick',
        'passive income guaranteed', 'daily income',
        '1000% returns', 'fixed returns', 'no risk profit',
    ],
    'fake_trading_app': [
        'fake sebi', 'unregistered broker', 'fake nse',
        'copy trading profit', 'trading signals guaranteed',
        'option tips guaranteed', 'intraday tips 100%',
        'algo trading profit', 'free trading signals',
    ],
    'illegal_betting': [
        '1xbet', 'bet365', 'reddy anna', 'khelo365',
        'satta matka', 'online satta', '96win', 'fairplay',
        'betway india', 'ipl betting tips', 'match fixing',
        'cricket betting', 'odds tips guaranteed',
    ],
    'crypto_scam': [
        'crypto doubler', 'bitcoin investment guaranteed',
        'crypto arbitrage profit', 'defi guaranteed',
        'nft guaranteed profit', 'crypto signal group',
        'pump and dump', 'token presale guaranteed',
    ],
    'fake_ipo': [
        'ipo allotment guaranteed', 'ipo tips insider',
        'grey market premium tips', 'ipo guaranteed listing',
        'sebi registered fake', 'nse tips guaranteed',
    ]
}

# ── LEGITIMATE SIGNALS (reduce false positives) ───────────
LEGITIMATE_SIGNALS = [
    'sebi registered', 'amfi registered', 'rbi approved',
    'nse listed', 'bse listed', 'zerodha', 'groww',
    'angel broking', 'upstox', 'hdfc securities',
]

class FraudChannel:
    def __init__(self, channel, fraud_types, signals_found,
                 subscribers, url):
        self.channel = channel
        self.fraud_types = fraud_types
        self.signals_found = signals_found
        self.subscribers = subscribers
        self.url = url
        self.severity = (
            'CRITICAL' if subscribers > 10000 else
            'HIGH' if subscribers > 1000 else
            'MEDIUM'
        )

async def scan_telegram_for_fraud(event_context: str = "IPL 2026") -> dict:
    """
    Scan Telegram channels for financial fraud signals.
    Extends existing Live Shield with fraud detection.
    """
    print(f"[FRAUD] Scanning Telegram for financial fraud...")
    
    fraud_channels = []
    
    # Known fraud-related channel patterns to check
    channels_to_scan = [
        # Trading/investment scam channels
        'TradingProfit', 'StockMarketTips', 'InvestmentProfit',
        'CryptoSignals', 'ForexTips', 'OptionsTips',
        'IPOAllotment', 'ShareMarketTips', 'MutualFundTips',
        'CryptoIndia', 'BitcoinIndia', 'StockTipsIndia',
        # Betting channels (from existing list)
        'CricketBetting', 'IPLBetting', 'CricketTips',
        'CricketOdds', 'IPLTips', 'BettingTips',
        'CricketWinTips', 'IPLWinPrediction',
    ]
    
    async with httpx.AsyncClient(
        timeout=12,
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True
    ) as client:
        
        tasks = [
            check_channel_for_fraud(client, ch)
            for ch in channels_to_scan
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, FraudChannel):
                fraud_channels.append(result)
                print(f"  FRAUD: @{result.channel} "
                      f"({result.subscribers:,} subs) "
                      f"— {result.fraud_types}")
        
        # Also discover new fraud channels via Google
        discovered = await discover_fraud_channels(client)
        for ch in discovered:
            if ch not in [f.channel for f in fraud_channels]:
                result = await check_channel_for_fraud(client, ch)
                if isinstance(result, FraudChannel):
                    fraud_channels.append(result)
    
    # Sort by severity then subscribers
    fraud_channels.sort(
        key=lambda x: (
            {'CRITICAL':0,'HIGH':1,'MEDIUM':2}.get(x.severity,3),
            -x.subscribers
        )
    )
    
    total_reach = sum(f.subscribers for f in fraud_channels)
    by_type = {}
    for f in fraud_channels:
        for t in f.fraud_types:
            by_type[t] = by_type.get(t, 0) + 1
    
    return {
        'scanned_at': datetime.now().isoformat(),
        'fraud_channels': len(fraud_channels),
        'total_subscriber_reach': total_reach,
        'by_fraud_type': by_type,
        'channels': [
            {
                'channel': f.channel,
                'url': f.url,
                'fraud_types': f.fraud_types,
                'signals': f.signals_found[:5],
                'subscribers': f.subscribers,
                'severity': f.severity,
            }
            for f in fraud_channels
        ]
    }

async def check_channel_for_fraud(
    client: httpx.AsyncClient, channel: str
) -> FraudChannel:
    """Check a single Telegram channel for fraud signals."""
    try:
        r = await client.get(f"https://t.me/s/{channel}")
        if r.status_code != 200:
            return None
        
        text = r.text.lower()
        
        # Check for legitimate signals first
        is_legitimate = any(s in text for s in LEGITIMATE_SIGNALS)
        if is_legitimate:
            return None
        
        # Find fraud signals
        found_types = []
        found_signals = []
        
        for fraud_type, signals in FRAUD_SIGNALS.items():
            matched = [s for s in signals if s in text]
            if matched:
                found_types.append(fraud_type)
                found_signals.extend(matched[:3])
        
        if not found_types:
            return None
        
        # Get subscriber count
        subs = 0
        subs_match = re.search(
            r'(\d[\d\s,]*)\s*(members|subscribers)', r.text, re.I)
        if subs_match:
            subs = int(re.sub(r'[^\d]', '', subs_match.group(1)) or 0)
        
        return FraudChannel(
            channel=channel,
            fraud_types=found_types,
            signals_found=found_signals,
            subscribers=subs,
            url=f"https://t.me/{channel}"
        )
    except:
        return None

async def discover_fraud_channels(client: httpx.AsyncClient) -> list:
    """Discover new fraud channels via Google."""
    new_channels = []
    try:
        queries = [
            "telegram channel guaranteed returns investment india 2026",
            "t.me trading profit guaranteed india sebi",
            "telegram crypto signals guaranteed india",
        ]
        for q in queries[:2]:
            r = await client.get("https://serpapi.com/search", params={
                "q": q, "api_key": SERP_KEY,
                "num": 5, "engine": "google"
            })
            for item in r.json().get("organic_results", []):
                combined = item.get("link","") + item.get("snippet","")
                channels = re.findall(
                    r't\.me/([a-zA-Z][a-zA-Z0-9_]{3,30})', combined)
                new_channels.extend(channels)
    except:
        pass
    return list(set(new_channels))[:10]

async def scan_web_for_fraud(query_context: str = "India") -> dict:
    """Scan web for fake trading apps and investment scam websites."""
    print(f"[FRAUD] Scanning web for fraudulent financial sites...")
    
    fraud_sites = []
    
    if not SERP_KEY:
        return {'fraud_sites': [], 'total': 0}
    
    search_queries = [
        'guaranteed returns investment india site:telegram.me OR site:instagram.com',
        '"guaranteed profit" "trading" india 2026 -sebi -registered',
        'fake trading app india sebi warning 2026',
        '"100% profit" OR "daily income" trading india telegram',
        'illegal betting app india IPL 2026',
    ]
    
    async with httpx.AsyncClient(timeout=10) as client:
        for query in search_queries[:3]:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "q": query, "api_key": SERP_KEY,
                    "num": 5, "engine": "google"
                })
                
                for item in r.json().get("organic_results", []):
                    link = item.get("link", "")
                    title = item.get("title", "").lower()
                    snippet = item.get("snippet", "").lower()
                    combined = f"{title} {snippet}"
                    
                    # Check for fraud signals
                    fraud_found = []
                    for ftype, signals in FRAUD_SIGNALS.items():
                        matched = [s for s in signals if s in combined]
                        if matched:
                            fraud_found.append(ftype)
                    
                    # Skip legitimate sites
                    is_legit = any(s in combined for s in LEGITIMATE_SIGNALS)
                    is_legit = is_legit or any(
                        d in link for d in [
                            'sebi.gov.in', 'rbi.org.in',
                            'zerodha.com', 'groww.in',
                            'moneycontrol.com', 'economictimes.com'
                        ]
                    )
                    
                    if fraud_found and not is_legit:
                        fraud_sites.append({
                            'url': link,
                            'fraud_types': fraud_found,
                            'title': item.get("title", "")[:80],
                            'snippet': item.get("snippet", "")[:100],
                        })
                        print(f"  FRAUD SITE: {link[:60]}")
            except:
                pass
    
    return {
        'fraud_sites': fraud_sites,
        'total': len(fraud_sites)
    }

def generate_sebi_report(
    telegram_results: dict,
    web_results: dict
) -> str:
    """Generate evidence report for SEBI submission."""
    now = datetime.now()
    
    channels = telegram_results.get('channels', [])
    sites = web_results.get('fraud_sites', [])
    total_reach = telegram_results.get('total_subscriber_reach', 0)
    
    report = f"""
CINEOS FINANCIAL FRAUD INTELLIGENCE REPORT
==========================================
Generated: {now.strftime('%B %d, %Y %H:%M IST')}
Platform: CINEOS Anti-Piracy & Fraud Intelligence
Patent: US Provisional Patent Application 64/049,190
Contact: yugandhar@cineos.in | cineos.in

EXECUTIVE SUMMARY
-----------------
Telegram Fraud Channels: {len(channels)}
Total Subscriber Reach:  {total_reach:,}
Fraudulent Websites:     {len(sites)}
Detection Method:        Automated public channel monitoring

RECOMMENDED SEBI ACTION
-----------------------
File complaint at: sebi.gov.in/grievance
SEBI SCORES portal: scores.sebi.gov.in
Cyber Cell: cybercrime.gov.in

FRAUD CHANNELS ON TELEGRAM (PUBLIC)
------------------------------------
"""
    
    for ch in channels[:20]:
        report += f"""
Channel: @{ch['channel']}
URL: {ch['url']}
Subscribers: {ch['subscribers']:,}
Severity: {ch['severity']}
Fraud Types: {', '.join(ch['fraud_types'])}
Signals Found: {', '.join(ch['signals'][:3])}
"""
    
    if sites:
        report += f"\nFRAUDULENT WEBSITES\n-------------------\n"
        for site in sites[:10]:
            report += f"\nURL: {site['url']}\n"
            report += f"Type: {', '.join(site['fraud_types'])}\n"
            report += f"Title: {site['title']}\n"
    
    report += f"""
LEGAL BASIS
-----------
SEBI (Prohibition of Fraudulent and Unfair Trade Practices) Regulations 2003
Securities and Exchange Board of India Act, 1992
Information Technology Act 2000 Section 66D (cheating by personation)
Indian Penal Code Section 420 (cheating)

CERTIFICATION
-------------
All data collected via automated monitoring of publicly accessible
Telegram channels and websites. No unauthorized access performed.
Detection timestamp: {now.isoformat()}
CINEOS | cineos.in | yugandhar@cineos.in
"""
    
    return report

if __name__ == '__main__':
    async def main():
        print("="*60)
        print("  CINEOS FINANCIAL FRAUD INTELLIGENCE")
        print("="*60)
        
        # Scan Telegram
        tg_results = await scan_telegram_for_fraud()
        
        # Scan web
        web_results = await scan_web_for_fraud()
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"  FRAUD DETECTION SUMMARY")
        print(f"{'='*60}")
        print(f"  Telegram channels: {tg_results['fraud_channels']}")
        print(f"  Subscriber reach:  {tg_results['total_subscriber_reach']:,}")
        print(f"  Fraud websites:    {web_results['total']}")
        print(f"\n  BY FRAUD TYPE:")
        for ftype, count in tg_results['by_fraud_type'].items():
            print(f"    {ftype:30} {count} channels")
        
        print(f"\n  TOP FRAUD CHANNELS:")
        for ch in tg_results['channels'][:5]:
            print(f"    [{ch['severity']:8}] @{ch['channel']:25} "
                  f"{ch['subscribers']:>8,} subs  "
                  f"{ch['fraud_types'][0]}")
        
        # Generate SEBI report
        report = generate_sebi_report(tg_results, web_results)
        os.makedirs('reports', exist_ok=True)
        path = f"reports/CINEOS_Fraud_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        open(path, 'w').write(report)
        print(f"\n  SEBI report saved: {path}")
        print(f"{'='*60}")
    
    asyncio.run(main())
