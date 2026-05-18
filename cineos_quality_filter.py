"""
CINEOS Alert Quality Filter
Runs after every scan cycle.
Keeps only alerts with real intelligence value.
Archives noise to separate file.
"""
import json, re
from datetime import datetime, timezone, timedelta
from collections import Counter

IST = timezone(timedelta(hours=5,minutes=30))

# Domains that are legitimate sources — not fraud channels
LEGIT_DOMAINS = {
    'rbi.org.in','sbi.co.in','hdfcbank.com','icicibank.com',
    'npci.org.in','bankofindia','canarabank','pnbindia',
    'cybercrime.gov.in','india.gov.in','sebi.gov.in','cdsco.gov.in',
    'indiatoday.in','ndtv.com','thehindu.com','livemint.com',
    'economictimes','hindustantimes.com','business-standard.com',
    'timesofindia','newindianexpress.com','deccanchronicle.com',
    'telanganatoday.com','thehansindia.com','thenewsmill.com',
    'unigox.com','coindesk.com','coingecko.com','binance.com',
    'instagram.com','facebook.com','youtube.com','twitter.com',
    'indiafilings.com','mca.gov.in','meity.gov.in',
}

def is_quality_alert(alert):
    """
    Quality alert = has at least one real intelligence attribute.
    News article = has none of these.
    """
    chain = alert.get('chain', {})
    
    # Has confirmed phone number
    if chain.get('phones'):
        return True, 'has_phones'
    
    # Has real Telegram channel
    channels = chain.get('channels_found', [])
    if any('t.me/' in str(c) for c in channels):
        return True, 'has_telegram'
    
    # Has real reach (subscriber count)
    if alert.get('reach', 0) > 0:
        return True, 'has_reach'
    
    # Has UPI handle
    if chain.get('upis'):
        return True, 'has_upi'
    
    # Has domain that is NOT a legit news site
    domains = chain.get('domains', [])
    for d in domains:
        if not any(ld in str(d).lower() for ld in LEGIT_DOMAINS):
            return True, 'has_fraud_domain'
    
    # Has IFSC code (banking fraud)
    detail = alert.get('detail', '') + alert.get('title', '')
    if re.search(r'[A-Z]{4}0[A-Z0-9]{6}', detail):
        return True, 'has_ifsc'
    
    # Has arrest/FIR with specific amount (enforcement intelligence)
    if re.search(r'(?:arrested|FIR|seized|busted).*?(?:crore|lakh|Rs\.?\s*\d)', 
                 detail, re.I):
        return True, 'enforcement_with_amount'
    
    # Source is a Telegram channel directly
    source = str(alert.get('source', ''))
    if 't.me/' in source or source.startswith('@'):
        return True, 'telegram_source'
    
    return False, 'news_only'


def run_quality_filter(dry_run=False):
    alerts = json.load(open('reports/alerts/live_alerts.json'))
    before = len(alerts)
    
    kept = []
    archived = []
    reasons = Counter()
    
    for a in alerts:
        quality, reason = is_quality_alert(a)
        if quality:
            kept.append(a)
            reasons[reason] += 1
        else:
            archived.append(a)
    
    print(f'CINEOS QUALITY FILTER')
    print(f'  Before: {before} alerts')
    print(f'  Keep:   {len(kept)} quality alerts')
    print(f'  Remove: {len(archived)} news-only alerts')
    print()
    print('KEPT BY REASON:')
    for r, n in reasons.most_common():
        print(f'  {r:30} {n}')
    print()
    
    # Category breakdown of what's kept
    cats = Counter(a.get('category','') for a in kept)
    print('QUALITY ALERTS BY CATEGORY:')
    for cat, n in cats.most_common():
        with_ph = sum(1 for a in kept if a.get('category')==cat and a.get('chain',{}).get('phones'))
        reach = sum(a.get('reach',0) for a in kept if a.get('category')==cat)
        print(f'  {cat:30} {n:>4}  phones:{with_ph:>3}  reach:{reach:>12,}')
    
    if not dry_run:
        # Save quality alerts
        json.dump(kept, open('reports/alerts/live_alerts.json','w'), 
                  indent=2, default=str)
        
        # Archive noise separately (useful for pattern analysis)
        try:
            existing_arch = json.load(open('reports/alerts/archived_noise.json'))
        except:
            existing_arch = []
        
        existing_ids = {a.get('id','') for a in existing_arch}
        new_arch = [a for a in archived if a.get('id','') not in existing_ids]
        json.dump(existing_arch + new_arch, 
                  open('reports/alerts/archived_noise.json','w'),
                  indent=2, default=str)
        
        print(f'\nSaved {len(kept)} quality alerts')
        print(f'Archived {len(archived)} noise alerts ({len(new_arch)} new)')
    else:
        print('\n[DRY RUN — no changes made]')
    
    return len(kept), len(archived)

if __name__ == '__main__':
    import sys
    dry = '--dry-run' in sys.argv
    run_quality_filter(dry_run=dry)
