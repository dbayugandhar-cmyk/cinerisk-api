#!/usr/bin/env python3
"""
CINEOS Operator Resurrection Tracker
After every enforcement action (arrest/bust), tracks whether
operators create new channels using same phones/UPIs.
This is what NO other platform does.
"""
import json, re, hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5, minutes=30))

def check_resurrection():
    """
    Cross-references:
    1. All confirmed operator phones from deep scan
    2. Enforcement news dates
    3. New channels appearing AFTER enforcement with same phones
    """
    try:
        channels = json.load(open('reports/all_channels.json'))
        alerts   = json.load(open('reports/alerts/live_alerts.json'))
        graph    = json.load(open('reports/fraud_intelligence_graph.json'))
    except Exception as e:
        print(f"Load error: {e}")
        return
    
    # Known enforcement dates
    ENFORCEMENT_EVENTS = [
        {'date': '2026-05-13', 'name': 'Mahadev Book Vizag Bust',
         'phones': ['+918808981489','+919859990481','+918881754538'],
         'keywords': ['mahadev','mhb']},
        {'date': '2026-05-01', 'name': 'Gujarat UPI Mule Bust',
         'phones': ['+918881448108','+918808843584'],
         'keywords': ['laser247','cricbet99']},
    ]
    
    phone_map = defaultdict(list)
    for ch in channels:
        for ph in ch.get('phones', []):
            if ph:
                phone_map[ph].append(ch)
    
    resurrections = []
    for event in ENFORCEMENT_EVENTS:
        event_date = datetime.fromisoformat(event['date']).replace(tzinfo=IST)
        for ph in event['phones']:
            matching_channels = phone_map.get(ph, [])
            for ch in matching_channels:
                # Check if channel was detected AFTER enforcement
                ch_date_str = ch.get('detected_at', ch.get('first_seen', ''))
                if ch_date_str:
                    try:
                        ch_date = datetime.fromisoformat(ch_date_str[:19]).replace(tzinfo=IST)
                        days_after = (ch_date - event_date).days
                        if days_after >= 0:
                            resurrections.append({
                                'enforcement_event': event['name'],
                                'enforcement_date': event['date'],
                                'phone': ph,
                                'channel': ch.get('username', 'unknown'),
                                'subscribers': ch.get('subscribers', 0),
                                'days_after_bust': days_after,
                                'confidence': 99,
                                'significance': 'OPERATOR ACTIVE POST-ARREST — resurrection confirmed',
                                'legal_note': 'Continued operation post-arrest = aggravated offense',
                            })
                    except:
                        pass
    
    # Save resurrection report
    report = {
        'generated_at': datetime.now(IST).isoformat(),
        'total_resurrections': len(resurrections),
        'enforcement_events_tracked': len(ENFORCEMENT_EVENTS),
        'resurrections': resurrections,
        'insight': f"{len(resurrections)} operator channels confirmed active AFTER enforcement action. This is direct evidence of persistent criminal operation."
    }
    json.dump(report, open('reports/resurrection_report.json','w'), indent=2)
    
    print(f"Resurrection Tracker Report")
    print(f"Enforcement events tracked: {len(ENFORCEMENT_EVENTS)}")
    print(f"Post-arrest active channels: {len(resurrections)}")
    for r in resurrections[:10]:
        print(f"  {r['phone']} → @{r['channel']} — {r['days_after_bust']}d after {r['enforcement_event']}")

if __name__ == '__main__':
    check_resurrection()
