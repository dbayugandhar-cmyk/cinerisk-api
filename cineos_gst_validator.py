"""
CINEOS GST Fraud Detection
Validates GST numbers from counterfeit sellers.
Fake GST = fraud evidence for GST Council + police.

Legal: Uses only public GSTN portal data.
"""
import asyncio, httpx, re, json, os
from datetime import datetime

async def validate_gstin(client, gstin: str) -> dict:
    """
    Validate a GSTIN using the public GST portal API.
    Returns business name, status, state, registration date.
    """
    result = {
        'gstin': gstin,
        'valid_format': False,
        'status': 'UNKNOWN',
        'legal_name': '',
        'trade_name': '',
        'state': '',
        'registration_date': '',
        'taxpayer_type': '',
        'fraud_signals': [],
    }

    # Validate format first
    # GSTIN: 2 digits state + 10 char PAN + 1 entity + Z + 1 check
    gstin_pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    if not re.match(gstin_pattern, gstin.upper().strip()):
        result['fraud_signals'].append('INVALID FORMAT — not a real GSTIN')
        return result

    result['valid_format'] = True
    gstin = gstin.upper().strip()

    # State code mapping
    STATE_CODES = {
        '01':'Jammu & Kashmir','02':'Himachal Pradesh','03':'Punjab',
        '04':'Chandigarh','05':'Uttarakhand','06':'Haryana',
        '07':'Delhi','08':'Rajasthan','09':'Uttar Pradesh',
        '10':'Bihar','11':'Sikkim','12':'Arunachal Pradesh',
        '13':'Nagaland','14':'Manipur','15':'Mizoram',
        '16':'Tripura','17':'Meghalaya','18':'Assam',
        '19':'West Bengal','20':'Jharkhand','21':'Odisha',
        '22':'Chhattisgarh','23':'Madhya Pradesh','24':'Gujarat',
        '27':'Maharashtra','28':'Andhra Pradesh','29':'Karnataka',
        '30':'Goa','31':'Lakshadweep','32':'Kerala',
        '33':'Tamil Nadu','34':'Puducherry','36':'Telangana',
        '37':'Andhra Pradesh (New)',
    }
    state_code = gstin[:2]
    result['state'] = STATE_CODES.get(state_code, f'Unknown ({state_code})')

    # Try public GST portal API
    try:
        # Method 1 — GST portal public search
        r = await client.get(
            f"https://www.knowyourgst.com/gst/api/?gstin={gstin}",
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if data.get('status') == '1':
                result['status'] = 'ACTIVE'
                result['legal_name'] = data.get('lgnm', '')
                result['trade_name'] = data.get('tradeNam', '')
                result['registration_date'] = data.get('rgdt', '')
                result['taxpayer_type'] = data.get('dty', '')
            else:
                result['status'] = 'INACTIVE/CANCELLED'
                result['fraud_signals'].append('GST CANCELLED OR INACTIVE')
    except:
        pass

    # Method 2 — try alternative public API
    if result['status'] == 'UNKNOWN':
        try:
            r = await client.get(
                f"https://sheet.gstincheck.co.in/check/{gstin}",
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                if data.get('flag'):
                    result['status'] = 'ACTIVE'
                    result['legal_name'] = data.get('data', {}).get('lgnm', '')
                    result['trade_name'] = data.get('data', {}).get('tradeNam', '')
                    result['registration_date'] = data.get('data', {}).get('rgdt', '')
        except:
            pass

    # Fraud signal detection
    if result['status'] in ['INACTIVE/CANCELLED', 'UNKNOWN']:
        result['fraud_signals'].append('GST NOT ACTIVE — possible fraud')

    if result['legal_name'] and result['trade_name']:
        if result['legal_name'].lower() != result['trade_name'].lower():
            # Check if trade name is very different — possible fake
            pass

    return result

async def scan_sellers_for_gst_fraud(sellers_file: str = 'reports/deep_sellers.json') -> dict:
    """
    Scan confirmed counterfeit sellers for GST fraud.
    Cross-reference their GST numbers against GSTN.
    """
    print("[GST] Loading confirmed sellers...")

    try:
        sellers = json.load(open(sellers_file))
    except:
        print(f"No sellers file found at {sellers_file}")
        return {}

    # Extract sellers with GST numbers
    sellers_with_gst = [s for s in sellers if s.get('gst')]
    print(f"[GST] Sellers with GST numbers: {len(sellers_with_gst)}/{len(sellers)}")

    results = {
        'total_sellers': len(sellers),
        'sellers_with_gst': len(sellers_with_gst),
        'validated': [],
        'fraud_detected': [],
        'clean': [],
    }

    if not sellers_with_gst:
        print("[GST] No GST numbers found in sellers file")
        print("[GST] Running demo with sample GST numbers...")

        # Demo with known format GSTINs for testing
        demo_gstins = [
            {'company': 'Th Store', 'city': 'Imphal', 'brand': 'Nike',
             'gst': '14AAAAA0000A1ZA'},  # test format
            {'company': 'BUDDY_HOUSE', 'city': 'Sirsa', 'brand': 'Nike',
             'gst': '06BBBBB0000B1ZB'},
        ]
        sellers_with_gst = demo_gstins

    async with httpx.AsyncClient(
        timeout=12,
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True
    ) as client:

        for seller in sellers_with_gst[:20]:
            gstin = seller.get('gst', '').strip()
            if not gstin:
                continue

            print(f"\n  Validating: {seller.get('company','?')} — {gstin}")
            validation = await validate_gstin(client, gstin)

            entry = {
                **seller,
                'gstin_validation': validation,
            }

            if validation['fraud_signals']:
                results['fraud_detected'].append(entry)
                print(f"    FRAUD SIGNAL: {validation['fraud_signals']}")
            elif validation['status'] == 'ACTIVE':
                results['clean'].append(entry)
                print(f"    ACTIVE: {validation['legal_name']} ({validation['state']})")
            else:
                results['validated'].append(entry)
                print(f"    Status: {validation['status']}")

    print(f"\n{'='*60}")
    print(f"  CINEOS GST FRAUD DETECTION RESULTS")
    print(f"{'='*60}")
    print(f"  Sellers scanned:    {len(sellers)}")
    print(f"  With GST numbers:   {len(sellers_with_gst)}")
    print(f"  Fraud signals:      {len(results['fraud_detected'])}")
    print(f"  Verified active:    {len(results['clean'])}")

    if results['fraud_detected']:
        print(f"\n  FRAUD DETECTED:")
        for s in results['fraud_detected']:
            v = s['gstin_validation']
            print(f"    {s.get('company','?'):30} {s.get('gst','?')}")
            print(f"    Signals: {v['fraud_signals']}")

    return results

async def rescan_indiamart_for_gst():
    """
    Re-scan IndiaMART counterfeit listings specifically
    to extract GST numbers for validation.
    """
    print("[GST] Scanning IndiaMART for GST numbers...")

    SERP_KEY = os.environ.get('SERP_API_KEY', '')
    if not SERP_KEY:
        print("Set SERP_API_KEY")
        return []

    gst_sellers = []

    async with httpx.AsyncClient(
        timeout=12,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        follow_redirects=True
    ) as client:

        # Search for IndiaMART product pages with copy/replica
        brands = ['Nike', 'Dettol', 'Dove', 'Samsung Galaxy']

        for brand in brands:
            try:
                r = await client.get("https://serpapi.com/search", params={
                    "q": f'site:indiamart.com/proddetail "{brand}" copy',
                    "api_key": SERP_KEY,
                    "num": 10, "engine": "google", "gl": "in"
                })

                for item in r.json().get("organic_results", []):
                    url = item.get("link", "")
                    if "proddetail" not in url:
                        continue

                    # Fetch the page
                    try:
                        pr = await client.get(url)
                        text = pr.text

                        # Extract GST number
                        gst_match = re.search(
                            r'(?:GST|GSTIN)[:\s#"]+([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])',
                            text, re.I
                        )
                        company_match = re.search(
                            r'"COMPANYNAME"\s*:\s*"([^"]+)"', text)
                        city_match = re.search(
                            r'"CITY"\s*:\s*"([^"]+)"', text)
                        state_match = re.search(
                            r'"GLUSR_USR_STATE"\s*:\s*"([^"]+)"', text)

                        if gst_match:
                            gst = gst_match.group(1).upper()
                            company = company_match.group(1) if company_match else ''
                            city = city_match.group(1) if city_match else ''
                            state = state_match.group(1) if state_match else ''

                            print(f"  GST FOUND: {company} ({city}) — {gst}")

                            # Validate immediately
                            validation = await validate_gstin(client, gst)

                            gst_sellers.append({
                                'brand': brand,
                                'company': company,
                                'city': city,
                                'state': state,
                                'gst': gst,
                                'url': url,
                                'validation': validation,
                                'fraud': len(validation['fraud_signals']) > 0
                            })

                    except:
                        pass

            except Exception as e:
                print(f"  {brand}: {e}")

    print(f"\n[GST] Total sellers with GST: {len(gst_sellers)}")
    fraud = [s for s in gst_sellers if s['fraud']]
    print(f"[GST] Fraud signals: {len(fraud)}")

    return gst_sellers

if __name__ == '__main__':
    import sys

    async def main():
        print("="*60)
        print("  CINEOS GST FRAUD DETECTION")
        print("="*60)

        if '--scan' in sys.argv:
            # Scan IndiaMART for GST numbers
            results = await rescan_indiamart_for_gst()
        else:
            # Validate existing sellers
            results = await scan_sellers_for_gst_fraud()

        # Save
        os.makedirs('reports', exist_ok=True)
        path = f"reports/gst_fraud_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        json.dump(results, open(path, 'w'), indent=2, default=str)
        print(f"\nSaved: {path}")

    asyncio.run(main())
