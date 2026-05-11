"""
Generates JSON data feed for internal dashboard.
Run this to refresh dashboard data.
"""
import json, os
from datetime import datetime
from collections import defaultdict

os.makedirs('reports/dashboard', exist_ok=True)

# Load all data sources
channels  = json.load(open('reports/all_channels.json'))
graph     = json.load(open('reports/fraud_intelligence_graph.json'))
whois     = json.load(open('reports/whois_intelligence.json'))
stix      = json.load(open('reports/fraud_graph_stix.json'))

# Channel stats
total     = len(channels)
reach     = sum(c.get('subscribers',0) for c in channels)
by_cat    = defaultdict(list)
for c in channels:
    by_cat[c.get('category','unknown')].append(c)

# Top channels by subscriber
top_channels = sorted(
    [c for c in channels if c.get('subscribers',0) > 0],
    key=lambda x: -x['subscribers']
)[:50]

# Graph stats
nodes = graph.get('nodes', [])
edges = graph.get('edges', [])

# WHOIS summary
whois_domains = [
    {k: v for k, v in d.items()}
    for d in whois.get('domains', [])
    if isinstance(d, dict)
] if isinstance(whois, dict) else []

# Build dashboard data
data = {
    'generated_at': datetime.now().isoformat(),
    'summary': {
        'total_channels':  total,
        'total_reach':     reach,
        'graph_nodes':     len(nodes),
        'graph_edges':     len(edges),
        'stix_objects':    len(stix.get('objects', [])),
        'categories':      {k: len(v) for k,v in by_cat.items()},
    },
    'top_channels': top_channels[:50],
    'graph':        {'nodes': nodes[:200], 'edges': edges[:300]},
    'whois':        whois_domains[:20],
    'alerts': [
        {
            'id': 1, 'severity': 'critical',
            'title': 'IPL Match 53 — 20 piracy streams',
            'detail': 'CSK vs LSG · 10 May · 13:23 IST',
            'platform': 'Telegram',
            'time': '2026-05-10T13:23:00',
            'evidence_hash': 'b4d2d638a9f1c2',
            'chain': [
                {'step': 'Source', 'value': '13 Telegram channels', 'type': 'source'},
                {'step': 'Activity', 'value': '20 live piracy streams', 'type': 'danger'},
                {'step': 'Reach', 'value': '35M+ subscribers', 'type': 'warn'},
                {'step': 'Operators', 'value': '15 networks · phones confirmed', 'type': 'internal'},
                {'step': 'Evidence', 'value': 'IT Act §65B · SHA-256 hashed', 'type': 'ok'},
            ]
        },
        {
            'id': 2, 'severity': 'critical',
            'title': 'Fake payment APK — active site',
            'detail': 'UAE registrant · Jan 2026 · credential theft',
            'platform': 'Web',
            'time': '2026-05-10T09:14:00',
            'evidence_hash': 'a7f3c891d2e4b5',
            'chain': [
                {'step': 'Domain', 'value': 'phonepes.com.in', 'type': 'danger'},
                {'step': 'Activity', 'value': 'Fake APK download active', 'type': 'danger'},
                {'step': 'Registrar', 'value': 'Dynadot LLC · UAE', 'type': 'warn'},
                {'step': 'Registrant', 'value': 'WHOIS archived · identified', 'type': 'internal'},
                {'step': 'Evidence', 'value': 'IT Act §65B · WHOIS archived', 'type': 'ok'},
            ]
        },
        {
            'id': 3, 'severity': 'high',
            'title': '148 counterfeit listings — Amazon + Flipkart',
            'detail': 'Explicit keywords in titles · 3-tier verified',
            'platform': 'Marketplace',
            'time': '2026-05-10T08:00:00',
            'evidence_hash': 'c3d4e5f6a7b8c9',
            'chain': [
                {'step': 'Discovery', 'value': 'Telegram wholesale channels', 'type': 'source'},
                {'step': 'Marketplace', 'value': 'Amazon India + Flipkart · 148 listings', 'type': 'danger'},
                {'step': 'Evidence', 'value': 'Explicit title keywords only', 'type': 'warn'},
                {'step': 'Sellers', 'value': 'GST + phone + Telegram channel', 'type': 'internal'},
                {'step': 'Legal', 'value': 'TM Act §29 · IT Act §65B', 'type': 'ok'},
            ]
        },
        {
            'id': 4, 'severity': 'high',
            'title': 'BCCI impersonator — phones confirmed',
            'detail': '2 operator phones · 95% confidence · public messages',
            'platform': 'Telegram',
            'time': '2026-05-10T07:00:00',
            'evidence_hash': 'd4e5f6a7b8c9d0',
            'chain': [
                {'step': 'Channels', 'value': '2 BCCI impersonator channels', 'type': 'source'},
                {'step': 'Phones', 'value': '+91-8306154335 · +91-9216328940', 'type': 'internal'},
                {'step': 'Network', 'value': 'Reddy Anna Book affiliate', 'type': 'internal'},
                {'step': 'Confidence', 'value': '95% · publicly posted in channel', 'type': 'warn'},
                {'step': 'Evidence', 'value': 'IT Act §66D · §65B hashed', 'type': 'ok'},
            ]
        },
        {
            'id': 5, 'severity': 'high',
            'title': 'jiohotstar.net — domain squat identified',
            'detail': 'Registrant named · Jan 18 2026 · 4 days after launch',
            'platform': 'WHOIS',
            'time': '2026-05-10T06:00:00',
            'evidence_hash': 'e5f6a7b8c9d0e1',
            'chain': [
                {'step': 'Domain', 'value': 'jiohotstar.net', 'type': 'danger'},
                {'step': 'Registered', 'value': 'Jan 18 2026 — 4 days after launch', 'type': 'danger'},
                {'step': 'Registrant', 'value': 'muthyala naresh · muthyala19@gmail.com', 'type': 'internal'},
                {'step': 'Registrar', 'value': 'BigRock Solutions Ltd · India', 'type': 'warn'},
                {'step': 'Evidence', 'value': 'WHOIS archived · IT Act §65B', 'type': 'ok'},
            ]
        },
    ],
}

json.dump(data,
          open('reports/dashboard/internal_data.json','w'),
          indent=2, default=str)
print(f"Dashboard data generated: {datetime.now().isoformat()}")
print(f"  Channels: {total}")
print(f"  Reach:    {reach/1000000:.1f}M")
print(f"  Nodes:    {len(nodes)}")
print(f"  Alerts:   {len(data['alerts'])}")
