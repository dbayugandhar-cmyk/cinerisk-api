#!/usr/bin/env python3
"""
CINEOS Banking Fraud Intelligence Scanner
Monitors Telegram for: loan fraud, mule recruitment,
KYC fraud, OTP bypass, SIM swap, fake banking apps
"""
import asyncio, json, re, hashlib, os
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.errors import FloodWaitError

IST = timezone(timedelta(hours=5, minutes=30))
API_ID   = 38636931
API_HASH = '852280f65386a00114ff7453eac7849b'
SESSION  = 'cineos_session'

BANK_SEEDS = [
    # Mule recruitment
    'bank account kit', 'bank kit', 'account rent',
    'sell bank account', 'account buyer', 'mule account',
    'account on rent', 'zero balance account', 'current account sell',
    # KYC fraud
    'KYC bypass', 'fake KYC', 'Aadhaar kit', 'PAN sell',
    'KYC documents', 'verified account sell', 'KYC for sale',
    'CIBIL bypass', 'fake CIBIL', 'credit score fake',
    # OTP / SIM fraud
    'OTP bypass', 'OTP service', 'SIM swap', 'SIM card sell',
    'virtual number', 'OTP on hire', 'SMS bypass',
    # Fake loan apps
    'instant loan', 'loan without CIBIL', 'fake loan app',
    'loan fraud', 'loan recovery threat', 'digital arrest loan',
    # Investment fraud
    'SEBI unregistered tips', 'stock tips Telegram',
    'option selling tips', 'F&O tips fraud', 'fake trading app',
    # Money mule / hawala
    'hawala transfer', 'USDT to INR', 'crypto to cash',
    'informal transfer', 'settlement service',
    # Phishing
    'fake PhonePe', 'fake BHIM', 'fake bank APK',
    'UPI phishing', 'net banking phishing',
]

BANK_PATTERNS = {
    'phone':   r'(?<![\d])([6-9]\d{9})(?!\d)',
    'upi':     r'[\w.+-]+@(?:okaxis|okhdfcbank|okicici|oksbi|ybl|ibl|axl|paytm|apl|waicici|wahdfc|pingpay|upi|fbl|rbl|kotak|federal|airtel|jio)',
    'ifsc':    r'[A-Z]{4}0[A-Z0-9]{6}',
    'account': r'(?:account|a/c|acc)\s*(?:no\.?|number)?\s*:?\s*([\d]{9,18})',
    'amount':  r'(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{2})?)',
    'aadhaar': r'(?:aadhaar|aadhar)\s*:?\s*([\d]{4}\s[\d]{4}\s[\d]{4})',
}

BANK_CATEGORIES = {
    'upi_mule':          ['bank account kit','bank kit','mule account','account rent','account sell'],
    'kyc_fraud':         ['KYC bypass','fake KYC','Aadhaar kit','PAN sell','CIBIL bypass'],
    'otp_bypass':        ['OTP bypass','OTP service','SIM swap','SMS bypass'],
    'loan_fraud':        ['instant loan','loan without CIBIL','fake loan app','digital arrest loan'],
    'investment_fraud':  ['SEBI','stock tips','option selling','F&O tips','fake trading'],
    'hawala':            ['hawala','USDT to INR','crypto to cash','informal transfer'],
    'phishing':          ['fake PhonePe','fake BHIM','fake bank APK','UPI phishing'],
}

def categorize(text):
    tl = text.lower()
    for cat, kws in BANK_CATEGORIES.items():
        if any(k.lower() in tl for k in kws):
            return cat
    return 'banking_fraud'

def extract_entities(text):
    entities = {}
    for name, pattern in BANK_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            entities[name] = list(set(matches[:5]))
    return entities

def confidence(entities, ch_count=1):
    score = 60
    if entities.get('phone'):    score += 10
    if entities.get('upi'):      score += 10
    if entities.get('ifsc'):     score += 8
    if entities.get('account'):  score += 8
    if entities.get('aadhaar'):  score += 5
    if ch_count >= 2:            score += 10
    if ch_count >= 3:            score += 10
    return min(score, 99)

async def scan_banking():
    now = datetime.now(IST)
    print(f"CINEOS Banking Fraud Scanner — {now.strftime('%Y-%m-%d %H:%M IST')}")
    
    alerts = []
    try:
        async with TelegramClient(SESSION, API_ID, API_HASH) as client:
            # Search for banking fraud channels
            for seed in BANK_SEEDS[:20]:
                try:
                    async for result in client.iter_messages('me', limit=1):
                        pass
                    # Search public channels
                    results = await client(functions.contacts.SearchRequest(
                        q=seed, limit=10
                    ))
                    for chat in results.chats[:3]:
                        msgs = await client.get_messages(chat, limit=30)
                        for msg in msgs:
                            if msg.text and len(msg.text) > 20:
                                entities = extract_entities(msg.text)
                                cat = categorize(msg.text)
                                conf = confidence(entities)
                                if conf >= 60 and entities:
                                    ev_hash = hashlib.sha256(
                                        (msg.text + str(msg.date)).encode()
                                    ).hexdigest()[:16]
                                    alerts.append({
                                        'id': f'BANK-{ev_hash}',
                                        'title': f'{cat.replace("_"," ").title()} — @{chat.username or "unknown"}',
                                        'detail': msg.text[:200],
                                        'category': cat,
                                        'severity': 'critical' if conf >= 85 else 'high' if conf >= 70 else 'medium',
                                        'confidence': conf,
                                        'vertical': 'banking_fraud',
                                        'attribution': entities,
                                        'evidence_hash': ev_hash,
                                        'detected_at': datetime.now(IST).isoformat(),
                                        'platform': 'Telegram',
                                        'legal_basis': 'IT Act 2000 §65B · PMLA 2002 §3 · IPC §420',
                                        'report_to': ['FIU-IND', 'RBI', 'I4C cybercrime.gov.in'],
                                    })
                except Exception as e:
                    pass
    except Exception as e:
        print(f"Scanner error: {e}")
    
    # Save to vertical-specific file
    os.makedirs('reports/banking', exist_ok=True)
    existing = []
    try:
        existing = json.load(open('reports/banking/alerts.json'))
    except:
        pass
    
    seen = set(a['id'] for a in existing)
    new_alerts = [a for a in alerts if a['id'] not in seen]
    all_alerts = (existing + new_alerts)[-5000:]
    json.dump(all_alerts, open('reports/banking/alerts.json','w'), indent=2)
    print(f"Banking alerts: +{len(new_alerts)} new, {len(all_alerts)} total")

if __name__ == '__main__':
    asyncio.run(scan_banking())
