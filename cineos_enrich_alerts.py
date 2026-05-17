"""
CINEOS Alert Enrichment
Joins alerts with channel database to surface phones, UPIs, domains.
Run after every deep scan or on demand.
"""
import json, re, hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5,minutes=30))

def enrich_alerts():
    alerts   = json.load(open('reports/alerts/live_alerts.json'))
    channels = json.load(open('reports/all_channels.json'))
    
    print(f'CINEOS ALERT ENRICHMENT')
    print(f'Alerts to enrich: {len(alerts)}')
    print(f'Channel DB size:  {len(channels)}')
    
    # Build lookup indexes
    # username → channel
    by_username = {}
    for c in channels:
        u = c.get('username','').lower().replace('@','')
        if u: by_username[u] = c
    
    # phone → channels
    phone_to_channels = defaultdict(list)
    for c in channels:
        for p in c.get('phones',[]):
            if p: phone_to_channels[p].append(c)
    
    enriched = 0
    phones_added = 0
    upis_added = 0
    reach_added = 0
    
    for alert in alerts:
        changed = False
        
        # Extract channel usernames from alert
        channels_in_alert = []
        chain = alert.get('chain', {})
        
        for ch_ref in chain.get('channels_found', []):
            # Extract username from t.me/username or @username
            u = re.sub(r'.*t\.me/', '', str(ch_ref)).lower().strip('/')
            u = u.replace('@','').split('?')[0]
            if u and u in by_username:
                channels_in_alert.append(by_username[u])
        
        # If we found matching channels, pull their data
        if channels_in_alert:
            all_phones = []
            all_upis   = []
            all_domains= []
            total_reach= 0
            
            for ch in channels_in_alert:
                for p in ch.get('phones', []):
                    if p and p not in all_phones:
                        all_phones.append(p)
                for u in ch.get('upis', []):
                    if u and u not in all_upis:
                        all_upis.append(u)
                for d in ch.get('domains', []):
                    if d and d not in all_domains:
                        all_domains.append(d)
                total_reach += ch.get('subscribers', 0)
            
            # Update alert
            if all_phones and not chain.get('phones'):
                chain['phones'] = all_phones
                alert['phone'] = all_phones[0]
                phones_added += 1
                changed = True
            
            if all_upis and not chain.get('upis'):
                chain['upis'] = all_upis
                alert['upi'] = all_upis[0]
                upis_added += 1
                changed = True
            
            if all_domains:
                chain['domains'] = all_domains
                alert['domain'] = all_domains[0] if all_domains else ''
                changed = True
            
            if total_reach and not alert.get('reach'):
                alert['reach'] = total_reach
                chain['reach'] = total_reach
                reach_added += 1
                changed = True
            
            # Update confidence based on identifiers found
            conf = chain.get('confidence', 65)
            if all_phones: conf = min(99, conf + 15)
            if all_upis:   conf = min(99, conf + 10)
            chain['confidence'] = conf
            
            if conf >= 85 and alert.get('severity') != 'critical':
                alert['severity'] = 'critical'
                changed = True
        
        # Also try to match by phone numbers in detail text
        if not chain.get('phones'):
            text = alert.get('detail','') + alert.get('title','')
            found_phones = re.findall(r'(?<!\d)([6-9]\d{9})(?!\d)', text)
            full_phones  = ['+91'+p for p in found_phones]
            
            if full_phones:
                chain['phones'] = full_phones
                alert['phone']  = full_phones[0]
                phones_added += 1
                changed = True
                
                # Find channels for these phones
                for fp in full_phones:
                    if fp in phone_to_channels:
                        chs = phone_to_channels[fp]
                        reach = sum(c.get('subscribers',0) for c in chs)
                        if reach and not alert.get('reach'):
                            alert['reach'] = reach
                            chain['reach'] = reach
                            reach_added += 1
        
        # Extract UPIs from text
        if not chain.get('upis'):
            text = alert.get('detail','') + alert.get('title','')
            found_upis = re.findall(
                r'[\w.+-]+@(?:okaxis|okhdfcbank|okicici|oksbi|ybl|ibl|axl|'
                r'paytm|apl|upi|fbl|icici|hdfc|sbi|axis|kotak|yes|indus|'
                r'federal|rbl|idbi|pnb|bob|canara)', 
                text, re.I
            )
            if found_upis:
                chain['upis'] = found_upis
                alert['upi']  = found_upis[0]
                upis_added += 1
                changed = True
        
        if changed:
            alert['chain'] = chain
            alert['enriched_at'] = datetime.now(IST).isoformat()
            enriched += 1
    
    # Save
    json.dump(alerts, open('reports/alerts/live_alerts.json','w'),
              indent=2, default=str)
    
    print(f'\nENRICHMENT COMPLETE:')
    print(f'  Alerts enriched:  {enriched}')
    print(f'  Phones added:     {phones_added}')
    print(f'  UPIs added:       {upis_added}')
    print(f'  Reach added:      {reach_added}')
    
    # Show sample enriched betting alert
    alerts2 = json.load(open('reports/alerts/live_alerts.json'))
    bet_with_phone = [a for a in alerts2 
                      if a.get('category')=='illegal_betting' 
                      and a.get('chain',{}).get('phones')]
    print(f'\n  Betting alerts with phones now: {len(bet_with_phone)}')
    
    mule_with_phone = [a for a in alerts2
                       if a.get('category')=='upi_mule'
                       and a.get('chain',{}).get('phones')]
    print(f'  UPI mule alerts with phones now: {len(mule_with_phone)}')
    
    if bet_with_phone:
        a = bet_with_phone[0]
        print(f'\nSAMPLE ENRICHED BETTING ALERT:')
        print(f'  Title:  {a.get("title","")[:70]}')
        print(f'  Phones: {a.get("chain",{}).get("phones",[])}')
        print(f'  Reach:  {a.get("reach",0):,}')
        print(f'  Conf:   {a.get("chain",{}).get("confidence",0)}%')

if __name__ == '__main__':
    enrich_alerts()
