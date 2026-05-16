"""
CINEOS Deep Vertical Scanner
Goes 100 steps deeper than surface scanning.

BETTING: Match fixing, financial flow, hierarchy mapping
BANKING: Mule lifecycle, loan app APKs, OTP service mapping
PHARMA:  Supply chain, price intel, courier extraction
"""
import json, re, os, hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

IST = timezone(timedelta(hours=5,minutes=30))

# ── BETTING: MATCH FIXING INTELLIGENCE ───────────────────
def detect_match_fixing(text):
    """
    Detect match fixing signals beyond just betting.
    Fixing = specific insider information about outcomes.
    """
    FIXING_PATTERNS = {
        'TOSS_FIX': [
            r'toss (?:fix|sure|confirm|100%)',
            r'(?:sure|confirmed) toss',
            r'toss (?:winner|result) (?:fix|sure)',
            r'insider toss',
        ],
        'SCORE_FIX': [
            r'\d+ (?:runs?|wickets?) (?:fix|sure|confirm)',
            r'target (?:fix|sure|confirm)',
            r'over \d+ runs? (?:fix|sure)',
            r'powerplay (?:score|fix)',
        ],
        'PLAYER_FIX': [
            r'(?:player|batsman|bowler) (?:fix|paid|bribed)',
            r'inside (?:source|tip|info)',
            r'team (?:management|official)',
        ],
        'RESULT_FIX': [
            r'(?:match|game) (?:fix|sold|bought)',
            r'lose (?:on purpose|intentionally)',
            r'guaranteed (?:win|result|outcome)',
        ],
    }
    signals = {}
    for fix_type, patterns in FIXING_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                signals[fix_type] = True
                break
    return signals

def extract_financial_flow(text):
    """
    Extract financial flow signals from betting channel messages.
    Estimate revenue from message patterns.
    """
    flow = {}
    # Extract bet amounts mentioned
    amounts = re.findall(r'(?:Rs\.?|INR|₹)\s*([\d,]+)', text)
    if amounts:
        flow['amounts_mentioned'] = [a.replace(',','') for a in amounts[:5]]

    # Extract payment methods
    if re.search(r'UPI|Google Pay|PhonePe|Paytm', text, re.IGNORECASE):
        flow['payment_upi'] = True
    if re.search(r'USDT|crypto|bitcoin|BTC', text, re.IGNORECASE):
        flow['payment_crypto'] = True
    if re.search(r'cash|hawala|hand.?to.?hand', text, re.IGNORECASE):
        flow['payment_cash'] = True

    # Minimum bet / entry amounts
    min_bet = re.search(r'min(?:imum)?\s*(?:bet|entry|deposit)?\s*(?:Rs\.?|₹)?\s*(\d+)', text, re.IGNORECASE)
    if min_bet:
        flow['min_bet'] = min_bet.group(1)

    return flow

# ── BANKING: LOAN APP AND OTP SERVICE MAPPING ────────────
def extract_loan_app_intel(text):
    """Extract loan app names, APK references, and terms."""
    intel = {}

    # App names mentioned
    app_patterns = re.findall(r'(?:app|application)[:\s]+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)', text)
    if app_patterns:
        intel['app_names'] = app_patterns[:5]

    # APK distribution
    if re.search(r'\.apk|download|install|sideload', text, re.IGNORECASE):
        intel['apk_distribution'] = True

    # Interest rates
    rates = re.findall(r'(\d+(?:\.\d+)?)\s*%\s*(?:per\s*)?(?:month|week|day|annum)', text, re.IGNORECASE)
    if rates:
        intel['interest_rates'] = rates[:3]

    # Harassment tactics
    if re.search(r'contact list|gallery|photos|family|friends|expose|viral', text, re.IGNORECASE):
        intel['harassment_tactics'] = True
        intel['severity'] = 'CRITICAL'

    return intel

def extract_otp_service_intel(text):
    """Map OTP bypass service networks."""
    intel = {}

    # Platforms being bypassed
    platforms = []
    for platform in ['Aadhaar','PAN','DigiLocker','UIDAI','NSDL','Bank','UPI','BHIM','SIM']:
        if platform.lower() in text.lower():
            platforms.append(platform)
    if platforms: intel['platforms_targeted'] = platforms

    # Pricing
    prices = re.findall(r'(?:Rs\.?|₹)\s*(\d+)\s*(?:per\s*)?(?:OTP|SIM|number)', text, re.IGNORECASE)
    if prices: intel['prices'] = prices[:3]

    # Service type
    if re.search(r'SIM\s*swap', text, re.IGNORECASE):
        intel['service_type'] = 'SIM_SWAP'
    elif re.search(r'OTP\s*(?:forward|bypass|service)', text, re.IGNORECASE):
        intel['service_type'] = 'OTP_FORWARD'
    elif re.search(r'virtual\s*number', text, re.IGNORECASE):
        intel['service_type'] = 'VIRTUAL_NUMBER'

    return intel

# ── PHARMA: SUPPLY CHAIN AND PRICE INTELLIGENCE ──────────
def extract_pharma_supply_chain(text):
    """Extract pharmaceutical supply chain intelligence."""
    intel = {}

    # Wholesale / bulk indicators
    if re.search(r'wholesale|bulk|distributor|manufacturer|direct.*factory', text, re.IGNORECASE):
        intel['supply_role'] = 'WHOLESALE_SUPPLIER'
    elif re.search(r'resell|retail|single.*piece|single.*strip', text, re.IGNORECASE):
        intel['supply_role'] = 'RETAILER'

    # Drug prices
    price_pattern = re.findall(r'([A-Z][a-zA-Z]+(?:\s\d+\s?mg)?)[:\s]*(?:Rs\.?|₹)\s*(\d+)', text)
    if price_pattern:
        intel['price_list'] = {drug: price for drug, price in price_pattern[:5]}

    # Courier services
    couriers = re.findall(r'(?:Delhivery|BlueDart|DTDC|Ekart|Amazon|India Post|Speed Post|Xpressbees)', text, re.IGNORECASE)
    if couriers: intel['couriers'] = list(set(couriers))

    # Delivery cities
    cities = re.findall(r'(?:delivery|ship|available)\s+(?:in|to)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)', text)
    if cities: intel['delivery_cities'] = cities[:5]

    # Prescription bypass
    if re.search(r'no\s*prescription|without\s*prescription|no\s*doctor', text, re.IGNORECASE):
        intel['prescription_bypass'] = True
        intel['legal_violation'] = 'Drugs & Cosmetics Act §18'

    # Patient harm signals
    if re.search(r'side\s*effect|reaction|complication|died|death|overdose|hospital', text, re.IGNORECASE):
        intel['harm_signal'] = True
        intel['severity'] = 'CRITICAL'

    return intel

def run_deep_scan_on_alerts():
    """Apply deep scanning to all existing alerts."""
    alerts = json.load(open('reports/alerts/live_alerts.json'))
    enriched = 0

    for a in alerts:
        text = (a.get('title','') + ' ' + a.get('detail','')).lower()
        cat  = a.get('category','')
        chain = a.get('chain',{})

        if cat == 'illegal_betting':
            fixing = detect_match_fixing(text)
            flow   = extract_financial_flow(text)
            if fixing: chain['match_fixing_signals'] = fixing
            if flow:   chain['financial_flow'] = flow
            if fixing: a['severity'] = 'critical'
            if fixing: enriched += 1

        elif cat in ('upi_mule','loan_fraud'):
            loan = extract_loan_app_intel(text)
            otp  = extract_otp_service_intel(text)
            if loan: chain['loan_intel'] = loan
            if otp:  chain['otp_intel'] = otp
            if loan.get('harassment_tactics'): a['severity'] = 'critical'
            if loan or otp: enriched += 1

        elif cat == 'counterfeit_pharma':
            pharma = extract_pharma_supply_chain(text)
            if pharma: chain['pharma_supply_chain'] = pharma
            if pharma.get('harm_signal'): a['severity'] = 'critical'
            if pharma: enriched += 1

        a['chain'] = chain

    json.dump(alerts, open('reports/alerts/live_alerts.json','w'), indent=2)
    print(f'Deep scan complete: {enriched} alerts enriched with vertical intelligence')

    # Summary
    fixing_alerts = [a for a in alerts if a.get('chain',{}).get('match_fixing_signals')]
    harm_alerts   = [a for a in alerts if a.get('chain',{}).get('pharma_supply_chain',{}).get('harm_signal')]
    apk_alerts    = [a for a in alerts if a.get('chain',{}).get('loan_intel',{}).get('apk_distribution')]

    print(f'\nDeep Intelligence Summary:')
    print(f'  Match fixing signals detected: {len(fixing_alerts)}')
    print(f'  Pharma harm signals:           {len(harm_alerts)}')
    print(f'  Loan APK distribution:         {len(apk_alerts)}')

    # Show top match fixing alerts
    if fixing_alerts:
        print(f'\n  TOP MATCH FIXING ALERTS:')
        for a in fixing_alerts[:5]:
            signals = list(a.get('chain',{}).get('match_fixing_signals',{}).keys())
            print(f'    [{",".join(signals)}] {a["title"][:60]}')

if __name__ == '__main__':
    print('='*55)
    print(f'  CINEOS DEEP VERTICAL SCANNER')
    print(f'  {datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}')
    print('='*55)
    run_deep_scan_on_alerts()
