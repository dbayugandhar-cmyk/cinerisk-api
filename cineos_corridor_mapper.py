#!/usr/bin/env python3
"""
CINEOS Cross-Border Payment Corridor Mapper
Maps: India Telegram operator → UPI → crypto → Dubai/China/Nepal
This is what TRM Labs does for crypto, but for UPI+Telegram layer.
Nobody else maps this for India.
"""
import json, re
from collections import defaultdict, Counter

def map_corridors():
    channels = json.load(open('reports/all_channels.json'))
    alerts   = json.load(open('reports/alerts/live_alerts.json'))
    
    corridors = defaultdict(list)
    
    # Detect international payment indicators
    FOREIGN_PATTERNS = {
        'dubai_usdt':    [r'dubai', r'uae', r'USDT.*dubai', r'crypto.*dubai'],
        'nepal_hawala':  [r'nepal', r'kathmandu', r'NPR'],
        'china_corridor':[r'china', r'chinese', r'yuan', r'CNY', r'alipay'],
        'bangladesh':    [r'bangladesh', r'dhaka', r'BDT'],
        'usdt_p2p':      [r'P2P.*USDT', r'USDT.*P2P', r'tether.*India'],
    }
    
    # Known foreign UPI patterns
    FOREIGN_UIDS = [
        'daria.d@betviro',           # Russian/foreign operator
        'anastasia.n@pkheadwaysolutions',  # Foreign operator
        '15a53ad3-e34f-4152-898b-ed8a7bb3dfe4@fast',  # Crypto-linked
        'bcd02cc1-36d0-405d-9096-0e69219175c1@pypi',  # Suspicious
        'info@hobartpharma',          # Foreign pharma
    ]
    
    results = {
        'corridors': {},
        'foreign_upis': FOREIGN_UIDS,
        'high_risk_operators': [],
        'total_international_exposure': 0,
    }
    
    for pattern_name, patterns in FOREIGN_PATTERNS.items():
        matching_channels = []
        for ch in channels:
            text = json.dumps(ch).lower()
            if any(re.search(p.lower(), text) for p in patterns):
                matching_channels.append({
                    'channel': ch.get('username',''),
                    'subscribers': ch.get('subscribers',0),
                    'phones': ch.get('phones',[]),
                    'category': ch.get('category',''),
                })
        if matching_channels:
            results['corridors'][pattern_name] = {
                'channels': len(matching_channels),
                'total_reach': sum(c['subscribers'] for c in matching_channels),
                'examples': matching_channels[:3],
            }
    
    json.dump(results, open('reports/corridor_map.json','w'), indent=2)
    print("Cross-Border Corridor Map:")
    for corridor, data in results['corridors'].items():
        print(f"  {corridor}: {data['channels']} channels, {data['total_reach']:,} reach")
    print(f"Foreign UPI handles tracked: {len(FOREIGN_UIDS)}")

if __name__ == '__main__':
    map_corridors()
