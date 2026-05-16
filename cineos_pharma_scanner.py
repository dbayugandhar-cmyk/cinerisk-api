#!/usr/bin/env python3
"""
CINEOS Counterfeit Pharma Intelligence Scanner
Monitors Telegram for: counterfeit medicine sales,
prescription fraud, fake CDSCO approvals, illegal pharma
"""
import asyncio, json, re, hashlib, os
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
API_ID   = 38636931
API_HASH = '852280f65386a00114ff7453eac7849b'
SESSION  = 'cineos_session'

PHARMA_SEEDS = [
    # Weight loss drugs (highest risk India 2026)
    'Ozempic India', 'Mounjaro India', 'semaglutide India',
    'weight loss injection', 'diabetes injection without prescription',
    # Sexual enhancement (DCGI crackdown May 2026)
    'sildenafil without prescription', 'tadalafil without prescription',
    'Viagra buy India', 'Cialis India', 'Kamagra India',
    # Cancer / serious disease fraud
    'cancer cure Telegram', 'cancer treatment without hospital',
    'stage 4 cancer treatment', 'tumor shrink medicine',
    # Controlled substances
    'tramadol without prescription', 'codeine syrup sell',
    'alprazolam sell', 'Xanax India buy', 'sleeping pills sell',
    # Fake CDSCO / regulatory fraud
    'CDSCO approved medicine', 'FDA approved India medicine',
    'government approved medicine online', 'import medicine India',
    # Unregulated pharma channels
    'medicine without prescription', 'online pharmacy no prescription',
    'buy medicine COD India', 'medicine home delivery',
    'Hobart pharma', 'pharma telegram channel',
    # Veterinary / fake antibiotics
    'antibiotic without prescription India',
    'steroid without prescription', 'HGH India',
]

PHARMA_PATTERNS = {
    'phone':    r'(?<![\d])([6-9]\d{9})(?!\d)',
    'upi':      r'[\w.+-]+@(?:okaxis|okhdfcbank|okicici|oksbi|ybl|ibl|axl|paytm|apl|upi)',
    'website':  r'https?://[\w.-]+\.(?:com|in|net|org|co\.in)[/\w.-]*',
    'price':    r'(?:Rs\.?|INR|₹)\s*([\d,]+)',
    'whatsapp': r'(?:whatsapp|wa\.me|WhatsApp)[^\d]*([6-9]\d{9})',
}

PHARMA_CATEGORIES = {
    'weight_loss_fraud':    ['Ozempic','Mounjaro','semaglutide','weight loss injection'],
    'sexual_enhancement':   ['sildenafil','tadalafil','Viagra','Cialis','Kamagra'],
    'cancer_fraud':         ['cancer cure','cancer treatment','tumor','stage 4'],
    'controlled_substance': ['tramadol','codeine','alprazolam','Xanax','sleeping pills'],
    'prescription_bypass':  ['without prescription','no prescription','COD medicine'],
    'fake_approval':        ['CDSCO approved','FDA approved','government approved'],
}

LEGAL_BASIS = {
    'weight_loss_fraud':    'Drugs & Cosmetics Act 1940 §17A · IT Act §65B · IPC §420',
    'sexual_enhancement':   'Drugs & Cosmetics Act 1940 §17A+§18 · IT Act §65B · IPC §420',
    'cancer_fraud':         'Drugs & Cosmetics Act §17A · Drugs & Magic Remedies Act 1954 · IT Act §65B',
    'controlled_substance': 'NDPS Act 1985 §8 · Drugs & Cosmetics Act §17A · IT Act §65B',
    'prescription_bypass':  'Drugs & Cosmetics Act §18 · IT Act §65B',
    'fake_approval':        'Drugs & Cosmetics Act §17A · IPC §468 (forgery) · IT Act §65B',
}

def categorize(text):
    tl = text.lower()
    for cat, kws in PHARMA_CATEGORIES.items():
        if any(k.lower() in tl for k in kws):
            return cat
    return 'counterfeit_pharma'

def extract_entities(text):
    entities = {}
    for name, pattern in PHARMA_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            entities[name] = list(set(str(m) for m in matches[:5]))
    return entities

if __name__ == '__main__':
    print("CINEOS Pharma Scanner initialized")
    print(f"Seed categories: {len(PHARMA_SEEDS)} keywords")
    print(f"Detection patterns: {len(PHARMA_PATTERNS)}")
    print(f"Legal frameworks: {len(LEGAL_BASIS)}")


def extract_all_phones(text):
    """Extract phones including wa.me."""
    import re
    phones = set()
    for pat in [r"(?<!\d)([6-9]\d{9})(?!\d)", r"wa\.me/(?:91)?([6-9]\d{9})"]:
        for m in re.findall(pat, text, re.IGNORECASE):
            d = re.sub(r"\D","",m)
            if len(d)==10 and d[0] in "6789": phones.add("+91"+d)
    return list(phones)
