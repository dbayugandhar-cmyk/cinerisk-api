"""
CINEOS Suspect Registry Intelligence
I4C built a suspect registry with 21.65 lakh entries from banks.
CINEOS can ENRICH this registry with Telegram/social data.

What CINEOS adds that banks cannot see:
  - Phone numbers from Telegram fraud channels
  - UPI IDs shared in betting/scam channels
  - Seller details from IndiaMART counterfeits
  - App Store fraud app developers

This is the PERFECT partnership pitch to I4C.
We don't compete — we add the social layer to their bank layer.
"""
import json, os
from datetime import datetime

def build_cineos_suspect_data():
    """
    Compile all phone numbers, UPIs and identifiers
    CINEOS has found across all platforms.
    Format for sharing with I4C Suspect Registry.
    """

    suspects = []

    # From phone attribution
    phone_suspects = [
        {
            'identifier': '+91-8441916068',
            'type': 'phone',
            'found_in': ['@IPLBetting', '@ipltossmatchsessionn'],
            'fraud_type': 'illegal_betting',
            'channels': 2,
            'combined_subscribers': 19220,
            'evidence': 'Same phone in 2 IPL betting channels — operator confirmed',
            'severity': 'CRITICAL',
        },
        {
            'identifier': '+91-6378542162',
            'type': 'phone',
            'found_in': ['@Satta_khaiwal_gali_dishwar'],
            'fraud_type': 'satta_matka',
            'channels': 1,
            'combined_subscribers': 0,
            'evidence': 'Satta Matka promotion channel',
            'severity': 'HIGH',
        },
    ]
    suspects.extend(phone_suspects)

    # From seller database
    try:
        sellers = json.load(open('reports/deep_sellers.json'))
        gst_suspects = [s for s in sellers if s.get('gst') and s.get('risk_score',0) >= 60]
        for s in gst_suspects:
            suspects.append({
                'identifier': s['gst'],
                'type': 'gst_number',
                'company': s.get('company',''),
                'city': s.get('city',''),
                'found_in': ['IndiaMART'],
                'fraud_type': 'counterfeit_seller',
                'evidence': f"Counterfeit {s.get('brand','')} seller",
                'severity': 'HIGH',
            })
    except: pass

    # From auth scores
    try:
        auth = json.load(open('reports/seller_auth_scores.json'))
        confirmed = [a for a in auth if a.get('auth_score',0) >= 75]
        for a in confirmed:
            if a.get('company'):
                suspects.append({
                    'identifier': a.get('url',''),
                    'type': 'indiamart_listing',
                    'company': a.get('company',''),
                    'city': a.get('city',''),
                    'brand_counterfeited': a.get('brand',''),
                    'found_in': ['IndiaMART'],
                    'fraud_type': 'confirmed_counterfeit',
                    'auth_score': a.get('auth_score'),
                    'evidence': f"Auth score {a.get('auth_score')}/100 — {a.get('verdict','')}",
                    'severity': 'CRITICAL' if a.get('auth_score',0)>=75 else 'HIGH',
                })
    except: pass

    # Summary
    print("="*65)
    print("  CINEOS SUSPECT REGISTRY DATA")
    print("  Ready for sharing with I4C")
    print("="*65)
    print(f"  Total suspects compiled: {len(suspects)}")
    by_type = {}
    for s in suspects:
        t = s['type']
        by_type[t] = by_type.get(t, 0) + 1
    for t, count in by_type.items():
        print(f"  {t:25}: {count}")

    critical = [s for s in suspects if s.get('severity') == 'CRITICAL']
    print(f"\n  CRITICAL severity: {len(critical)}")
    for s in critical[:5]:
        print(f"    {s['identifier'][:40]} — {s['fraud_type']}")

    # Save in I4C-compatible format
    os.makedirs('reports', exist_ok=True)
    report = {
        'generated_at': datetime.now().isoformat(),
        'source': 'CINEOS Intelligence Platform',
        'patent': 'US Provisional Patent 64/049,190',
        'contact': 'yugandhar@cineos.in',
        'total_suspects': len(suspects),
        'platforms_monitored': [
            'Telegram (354 channels)',
            'IndiaMART (59 sellers)',
            'Instagram (127 posts)',
            'WhatsApp (6 groups)',
            'YouTube (16 channels)',
            'ShareChat (53 posts)',
            'Meesho (20 listings)',
        ],
        'suspects': suspects,
        'pitch_to_i4c': (
            'CINEOS provides the social media intelligence layer that '
            'I4C\'s Suspect Registry lacks. Banks provide transaction data. '
            'CINEOS provides Telegram channel data. Combined = '
            'complete fraud operator picture. Proposed partnership: '
            'CINEOS daily feed into I4C Suspect Registry. '
            'Contract: Rs 1-5 Cr/year.'
        )
    }
    path = 'reports/CINEOS_I4C_SuspectData.json'
    json.dump(report, open(path,'w'), indent=2)
    print(f"\n  Saved: {path}")
    print(f"\n  I4C PARTNERSHIP PITCH:")
    print(f"  Phone: 011-2343 8207 / 011-2343 8208")
    print(f"  Email: cybercrime@mha.gov.in")
    print(f"  Angle: We enrich I4C Suspect Registry with Telegram data")
    return report

build_cineos_suspect_data()
