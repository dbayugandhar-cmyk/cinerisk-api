"""
CINEOS UPI Fraud Attribution Graph
RaptorX-style: connects UPI IDs → phones → Telegram channels → sellers
Sells to: Paytm, PhonePe, NPCI, banks

Graph nodes:
  - UPI ID (e.g. fraud123@paytm)
  - Phone number (e.g. 9876543210)
  - Telegram channel (e.g. @CricketBetting)
  - Seller (e.g. Ajay Enterprises, Ghaziabad)
  - Bank account (IFSC + account)
  - GST number

Graph edges:
  - UPI shared in Telegram channel
  - Phone linked to UPI
  - Seller uses same UPI as fraud channel
  - Multiple channels share same UPI (mule pattern)
"""
import asyncio, json, re, os, hashlib
from datetime import datetime
from collections import defaultdict
from telethon import TelegramClient

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

UPI_HANDLES = [
    'okaxis','okicici','okhdfcbank','oksbi','paytm',
    'gpay','phonepe','ybl','apl','upi','ibl','axl',
    'rbl','kotak','fbl','icici','hdfc','sbi','axis',
    'indus','pnb','bob','boi','canara','idbi','yesbank',
    'aubank','idfcfirst','dbs','sc','citibank',
]

PHONE_PATTERN   = re.compile(r'\b[6-9]\d{9}\b')
IFSC_PATTERN    = re.compile(r'\b[A-Z]{4}0[A-Z0-9]{6}\b')
ACCOUNT_PATTERN = re.compile(r'\b\d{9,18}\b')

class FraudGraph:
    """
    Graph connecting fraud entities.
    Nodes: upi, phone, channel, seller, bank
    Edges: shared_in, linked_to, same_operator
    """
    def __init__(self):
        self.nodes = {}   # id → {type, value, metadata}
        self.edges = []   # {from, to, relation, evidence}
        self.clusters = {} # operator → [node_ids]

    def add_node(self, node_id, node_type, value, metadata=None):
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                'id': node_id,
                'type': node_type,
                'value': value,
                'metadata': metadata or {},
                'risk_score': 0,
                'seen_count': 1,
            }
        else:
            self.nodes[node_id]['seen_count'] += 1
        return node_id

    def add_edge(self, from_id, to_id, relation, evidence=''):
        self.edges.append({
            'from': from_id,
            'to': to_id,
            'relation': relation,
            'evidence': evidence,
            'timestamp': datetime.now().isoformat(),
        })

    def get_node_id(self, node_type, value):
        return hashlib.md5(f"{node_type}:{value}".encode()).hexdigest()[:12]

    def score_nodes(self):
        """Score each node by connection count and type."""
        connection_count = defaultdict(int)
        for edge in self.edges:
            connection_count[edge['from']] += 1
            connection_count[edge['to']] += 1

        for node_id, node in self.nodes.items():
            connections = connection_count[node_id]
            seen = node['seen_count']

            # Higher score = higher risk
            if node['type'] == 'upi':
                # UPI in multiple channels = mule
                score = min(100, connections * 25 + seen * 10)
            elif node['type'] == 'phone':
                score = min(100, connections * 20 + seen * 8)
            elif node['type'] == 'channel':
                score = min(100, 50 + connections * 10)
            else:
                score = min(100, connections * 15)

            self.nodes[node_id]['risk_score'] = score
            self.nodes[node_id]['connections'] = connections

    def find_mule_patterns(self):
        """Find UPI IDs appearing in multiple fraud channels — mule pattern."""
        upi_channels = defaultdict(set)
        for edge in self.edges:
            from_node = self.nodes.get(edge['from'], {})
            to_node   = self.nodes.get(edge['to'], {})

            if from_node.get('type') == 'upi' and to_node.get('type') == 'channel':
                upi_channels[edge['from']].add(edge['to'])
            elif to_node.get('type') == 'upi' and from_node.get('type') == 'channel':
                upi_channels[edge['to']].add(edge['from'])

        mules = {}
        for upi_id, channels in upi_channels.items():
            if len(channels) >= 2:
                upi_node = self.nodes.get(upi_id, {})
                mules[upi_id] = {
                    'upi': upi_node.get('value',''),
                    'found_in_channels': len(channels),
                    'channel_ids': list(channels),
                    'risk': 'CRITICAL' if len(channels) >= 3 else 'HIGH',
                }
        return mules

    def find_operator_clusters(self):
        """
        Cluster connected nodes into operator groups.
        If UPI A and UPI B both appear in Channel X,
        they may be the same operator.
        """
        # Build adjacency
        adj = defaultdict(set)
        for edge in self.edges:
            adj[edge['from']].add(edge['to'])
            adj[edge['to']].add(edge['from'])

        # Find connected components
        visited = set()
        clusters = []

        def dfs(node_id, cluster):
            if node_id in visited:
                return
            visited.add(node_id)
            cluster.append(node_id)
            for neighbor in adj[node_id]:
                dfs(neighbor, cluster)

        for node_id in self.nodes:
            if node_id not in visited:
                cluster = []
                dfs(node_id, cluster)
                if len(cluster) > 1:
                    clusters.append(cluster)

        return clusters

    def to_dict(self):
        self.score_nodes()
        return {
            'nodes': list(self.nodes.values()),
            'edges': self.edges,
            'stats': {
                'total_nodes': len(self.nodes),
                'total_edges': len(self.edges),
                'upi_nodes': sum(1 for n in self.nodes.values() if n['type']=='upi'),
                'phone_nodes': sum(1 for n in self.nodes.values() if n['type']=='phone'),
                'channel_nodes': sum(1 for n in self.nodes.values() if n['type']=='channel'),
                'mule_patterns': len(self.find_mule_patterns()),
            }
        }

async def extract_fraud_entities(client, channel_name, graph):
    """
    Scan a Telegram channel and extract all fraud entities.
    Add them as nodes to the graph with edges to the channel.
    """
    try:
        entity = await client.get_entity(channel_name)
        messages = await client.get_messages(entity, limit=500)

        channel_id = graph.get_node_id('channel', channel_name)
        subs = getattr(entity, 'participants_count', 0) or 0
        graph.add_node(channel_id, 'channel', channel_name, {
            'subscribers': subs,
            'title': getattr(entity, 'title', ''),
            'url': f"https://t.me/{channel_name}",
        })

        found = {'upi': 0, 'phone': 0, 'ifsc': 0}

        for msg in messages:
            if not msg.text:
                continue
            text = msg.text

            # Extract UPI IDs
            for handle in UPI_HANDLES:
                pattern = rf'[\w.+\-]{{3,}}@{handle}'
                upis = re.findall(pattern, text, re.I)
                for upi in upis:
                    upi = upi.lower()
                    upi_id = graph.get_node_id('upi', upi)
                    graph.add_node(upi_id, 'upi', upi, {
                        'handle': handle,
                        'first_seen': msg.date.isoformat() if msg.date else '',
                    })
                    graph.add_edge(channel_id, upi_id, 'shares_upi',
                                  f"Found in @{channel_name}")
                    found['upi'] += 1

            # Extract phone numbers
            phones = PHONE_PATTERN.findall(text)
            for phone in phones:
                phone_id = graph.get_node_id('phone', phone)
                graph.add_node(phone_id, 'phone', phone, {
                    'first_seen': msg.date.isoformat() if msg.date else '',
                })
                graph.add_edge(channel_id, phone_id, 'shares_phone',
                              f"Found in @{channel_name}")
                found['phone'] += 1

            # Extract IFSC codes (bank accounts)
            ifscs = IFSC_PATTERN.findall(text)
            for ifsc in ifscs:
                ifsc_id = graph.get_node_id('bank', ifsc)
                graph.add_node(ifsc_id, 'bank', ifsc, {
                    'type': 'ifsc_code',
                })
                graph.add_edge(channel_id, ifsc_id, 'shares_bank',
                              f"IFSC in @{channel_name}")
                found['ifsc'] += 1

        total = sum(found.values())
        if total > 0:
            print(f"  @{channel_name:40} UPI:{found['upi']:3} "
                  f"Phone:{found['phone']:3} Bank:{found['ifsc']:2}")

        return found

    except Exception as e:
        print(f"  @{channel_name}: {e}")
        return {}

async def cross_reference_sellers(graph):
    """
    Cross-reference fraud graph with IndiaMART sellers.
    If a seller's phone matches a fraud channel phone — CRITICAL.
    """
    try:
        sellers = json.load(open('reports/deep_sellers.json'))
    except:
        return

    for seller in sellers:
        phone = seller.get('phone','').replace('+91','').replace(' ','')
        if not phone or len(phone) < 10:
            continue

        phone_id = graph.get_node_id('phone', phone[-10:])
        if phone_id in graph.nodes:
            # This seller's phone is in a fraud channel!
            seller_id = graph.get_node_id('seller', seller.get('company',''))
            graph.add_node(seller_id, 'seller', seller.get('company',''), {
                'city': seller.get('city',''),
                'brand': seller.get('brand',''),
                'platform': 'IndiaMART',
                'risk': 'CRITICAL — phone matches fraud channel',
            })
            graph.add_edge(seller_id, phone_id, 'shares_phone_with_fraud',
                          f"Seller phone matches Telegram fraud channel")
            print(f"  CRITICAL MATCH: {seller.get('company','')} "
                  f"phone matches fraud channel!")

async def build_upi_fraud_graph():
    """Main function — build complete UPI fraud attribution graph."""
    print("="*65)
    print("  CINEOS UPI FRAUD ATTRIBUTION GRAPH")
    print("  RaptorX-style: UPI → Phone → Telegram → Seller")
    print("="*65)

    graph = FraudGraph()

    # Top fraud channels to scan
    SCAN_CHANNELS = [
        'Crypto_IPL_Bettingolgy_Tatah',
        'MATKA_KALYAN_MILAN_SATTA',
        'CricketBetting',
        'IPLBetting',
        'ipltossmatchsessionn',
        'rajveer_betbook247_mahakal',
        'sattamatkaji2026India',
        'SATTA_MATKA_SATKA_DP_BOSS',
        'MATKA_SRIDEVI_DPBOSS_KALYAN',
        'ipl_match_free_tips0',
        'ipl_tips_best_betting1',
        'ipl_best_cricket_betting_tips',
    ]

    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()
    print(f"[GRAPH] Connected — scanning {len(SCAN_CHANNELS)} channels\n")

    for channel in SCAN_CHANNELS:
        await extract_fraud_entities(client, channel, graph)

    await client.disconnect()

    # Cross-reference with sellers
    print("\n[GRAPH] Cross-referencing with IndiaMART sellers...")
    await cross_reference_sellers(graph)

    # Analyze graph
    print("\n[GRAPH] Analyzing fraud patterns...")
    graph.score_nodes()
    mules = graph.find_mule_patterns()
    clusters = graph.find_operator_clusters()
    stats = graph.to_dict()['stats']

    print(f"\n{'='*65}")
    print(f"  FRAUD GRAPH RESULTS")
    print(f"{'='*65}")
    print(f"  Total nodes:      {stats['total_nodes']}")
    print(f"  Total edges:      {stats['total_edges']}")
    print(f"  UPI IDs found:    {stats['upi_nodes']}")
    print(f"  Phone numbers:    {stats['phone_nodes']}")
    print(f"  Channels mapped:  {stats['channel_nodes']}")
    print(f"  Mule patterns:    {stats['mule_patterns']}")
    print(f"  Operator clusters:{len(clusters)}")

    if mules:
        print(f"\n  UPI MULE ACCOUNTS (appear in 2+ channels):")
        for uid, m in list(mules.items())[:10]:
            print(f"    {m['upi']:40} → {m['found_in_channels']} channels "
                  f"[{m['risk']}]")

    # Top risk nodes
    sorted_nodes = sorted(graph.nodes.values(),
                         key=lambda x: -x['risk_score'])
    high_risk = [n for n in sorted_nodes if n['risk_score'] >= 70]
    if high_risk:
        print(f"\n  HIGH RISK NODES (score ≥ 70):")
        for n in high_risk[:10]:
            print(f"    [{n['risk_score']:3}/100] {n['type']:8} {n['value'][:40]}")

    if clusters:
        print(f"\n  OPERATOR CLUSTERS (connected fraud entities):")
        big_clusters = sorted(clusters, key=lambda x: -len(x))[:3]
        for i, cluster in enumerate(big_clusters, 1):
            print(f"  Cluster {i} — {len(cluster)} connected entities:")
            for node_id in cluster[:5]:
                n = graph.nodes.get(node_id, {})
                print(f"    {n.get('type','?'):8} {n.get('value','?')[:40]}")

    # Save
    os.makedirs('reports', exist_ok=True)
    graph_data = graph.to_dict()
    graph_data['mule_patterns'] = mules
    graph_data['clusters'] = clusters
    path = f"reports/upi_fraud_graph_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    json.dump(graph_data, open(path,'w'), indent=2, default=str)
    print(f"\n  Saved: {path}")
    print(f"{'='*65}")

    return graph

if __name__ == '__main__':
    asyncio.run(build_upi_fraud_graph())
