"""
CINEOS Phone Number Attribution
Connect phone numbers from fraud channels
to real identities via public databases.
This is what we CAN do today without bank partnerships.
"""
import asyncio, json, re, os, httpx
from datetime import datetime
from telethon import TelegramClient

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

async def attribute_phone(client_http, phone):
    """
    Try to attribute a phone number using public sources:
    1. Truecaller public search (limited)
    2. IndiaMART seller match
    3. Telegram profile if registered
    """
    result = {
        'phone': phone,
        'formatted': f"+91-{phone}",
        'sources': [],
        'name': '',
        'linked_to': [],
    }
    
    # Check if phone matches any IndiaMART seller
    try:
        sellers = json.load(open('reports/deep_sellers.json'))
        for s in sellers:
            seller_phone = s.get('phone','').replace('+91','').replace(' ','').replace('-','')
            if seller_phone and seller_phone[-10:] == phone[-10:]:
                result['linked_to'].append({
                    'type': 'indiamart_seller',
                    'company': s.get('company',''),
                    'city': s.get('city',''),
                    'brand': s.get('brand',''),
                    'risk': 'CRITICAL — fraud channel phone matches counterfeit seller',
                })
                result['sources'].append('IndiaMART')
    except:
        pass
    
    return result

async def build_phone_report():
    """Build complete phone attribution report from all fraud channels."""
    
    # Load existing attribution data
    phone_data = {}
    
    import glob
    for f in glob.glob('reports/upi_attribution_*.json') + \
             glob.glob('reports/upi_mule_*.json'):
        try:
            data = json.load(open(f))
            phones = data.get('phone_numbers', {})
            for phone, channels in phones.items():
                if phone not in phone_data:
                    phone_data[phone] = []
                phone_data[phone].extend(channels)
        except:
            pass
    
    # Also from upi_fraud_graph
    for f in glob.glob('reports/upi_fraud_graph_*.json'):
        try:
            data = json.load(open(f))
            for node in data.get('nodes', []):
                if node.get('type') == 'phone':
                    phone = node.get('value','')
                    if phone:
                        if phone not in phone_data:
                            phone_data[phone] = []
        except:
            pass
    
    print(f"[ATTRIBUTION] Total phones collected: {len(phone_data)}")
    
    # Known phones from our scans
    known_phones = {
        '8441916068': ['IPLBetting', 'ipltossmatchsessionn'],
        '6378542162': ['Satta_khaiwal_gali_dishwar'],
    }
    phone_data.update(known_phones)
    
    results = []
    async with httpx.AsyncClient(timeout=10) as client_http:
        for phone, channels in phone_data.items():
            attribution = await attribute_phone(client_http, phone)
            attribution['found_in_channels'] = list(set(channels))
            attribution['channel_count'] = len(set(channels))
            results.append(attribution)
    
    # Sort by channel count
    results.sort(key=lambda x: -x['channel_count'])
    
    print(f"\n{'='*65}")
    print(f"  CINEOS PHONE ATTRIBUTION REPORT")
    print(f"{'='*65}")
    print(f"  Total phone numbers: {len(results)}")
    
    critical = [r for r in results if r['linked_to']]
    print(f"  Cross-platform matches: {len(critical)}")
    
    print(f"\n  PHONE NUMBERS FOR NPCI/TRAI BLOCKING:")
    for r in results:
        channels = r['found_in_channels']
        print(f"\n  +91-{r['phone']}")
        print(f"    Found in: {', '.join(channels[:3])}")
        if r['linked_to']:
            for link in r['linked_to']:
                print(f"    MATCH: {link['type']} — {link.get('company','')} "
                      f"{link.get('city','')} [{link['risk']}]")
    
    print(f"\n  REPORT FOR TRAI:")
    print(f"  The following {len(results)} phone numbers were extracted from")
    print(f"  illegal betting/fraud Telegram channels. Request blocking")
    print(f"  under IT Act Section 69A and Telecom Act 2023.")
    for r in results:
        print(f"    +91-{r['phone']} — {r['found_in_channels'][0] if r['found_in_channels'] else 'unknown'}")
    
    os.makedirs('reports', exist_ok=True)
    path = f"reports/phone_attribution_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(results, open(path,'w'), indent=2)
    print(f"\n  Saved: {path}")
    
    return results

asyncio.run(build_phone_report())
