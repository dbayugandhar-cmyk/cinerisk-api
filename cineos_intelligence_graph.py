"""
CINEOS FRAUD ECOSYSTEM INTELLIGENCE GRAPH
India's first automated fraud attribution engine.

Ingests all CINEOS scan data and builds a queryable graph.
Given any input — phone, channel, UPI, brand — 
traverses connections to find the full operator network.

All data from public sources only.
IT Act 65B compliant evidence on every node.
"""
import json, os, hashlib, hmac, re, uuid
from datetime import datetime
from collections import defaultdict

SECRET = b'cineos_graph_2026'

def make_id(node_type: str, value: str) -> str:
    h = hashlib.sha256(f"{node_type}:{value}".encode()).hexdigest()[:12]
    return f"{node_type.upper()}_{h}"

def hash_evidence(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, default=str).encode()
    ).hexdigest()

class FraudIntelligenceGraph:
    """
    Core graph engine for Indian fraud ecosystem.
    Nodes + edges + traversal + confidence scoring.
    """

    def __init__(self):
        self.nodes = {}   # id → node data
        self.edges = []   # list of edge dicts
        self.index = {    # fast lookup
            'by_phone':   defaultdict(list),
            'by_upi':     defaultdict(list),
            'by_username':defaultdict(list),
            'by_network': defaultdict(list),
            'by_type':    defaultdict(list),
        }
        self.created_at = datetime.now().isoformat()

    def add_node(self, node_type: str, identifier: str,
                 properties: dict = None) -> str:
        node_id = make_id(node_type, identifier)
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                'id':           node_id,
                'type':         node_type,
                'identifier':   identifier,
                'properties':   properties or {},
                'evidence_hash':hash_evidence({'type':node_type,'id':identifier}),
                'added_at':     datetime.now().isoformat(),
                'confidence':   properties.get('confidence', 50),
            }
            self.index['by_type'][node_type].append(node_id)

            # Index by specific fields
            if node_type == 'PHONE':
                self.index['by_phone'][identifier].append(node_id)
            elif node_type == 'UPI':
                self.index['by_upi'][identifier].append(node_id)
            elif node_type == 'CHANNEL':
                username = properties.get('username', identifier)
                self.index['by_username'][username.lower()].append(node_id)
            elif node_type == 'NETWORK':
                self.index['by_network'][identifier.lower()].append(node_id)

        return node_id

    def add_edge(self, from_id: str, to_id: str,
                 relation: str, confidence: int = 70,
                 evidence: dict = None):
        # Avoid duplicates
        for e in self.edges:
            if (e['from'] == from_id and e['to'] == to_id
                    and e['relation'] == relation):
                return

        self.edges.append({
            'from':          from_id,
            'to':            to_id,
            'relation':      relation,
            'confidence':    confidence,
            'evidence_hash': hash_evidence(evidence or {}),
            'added_at':      datetime.now().isoformat(),
        })

    def traverse(self, start_id: str, max_depth: int = 3) -> dict:
        """BFS traversal from a starting node — finds full network."""
        visited  = set()
        queue    = [(start_id, 0)]
        subgraph = {'nodes': {}, 'edges': [], 'operators': []}

        while queue:
            node_id, depth = queue.pop(0)
            if node_id in visited or depth > max_depth:
                continue
            visited.add(node_id)

            if node_id in self.nodes:
                subgraph['nodes'][node_id] = self.nodes[node_id]
                if self.nodes[node_id]['type'] == 'OPERATOR':
                    subgraph['operators'].append(node_id)

            # Find connected edges
            for edge in self.edges:
                if edge['from'] == node_id:
                    subgraph['edges'].append(edge)
                    if edge['to'] not in visited:
                        queue.append((edge['to'], depth + 1))
                elif edge['to'] == node_id:
                    subgraph['edges'].append(edge)
                    if edge['from'] not in visited:
                        queue.append((edge['from'], depth + 1))

        return subgraph

    def find_by_phone(self, phone: str) -> dict:
        """Given a phone number — find all connected fraud operations."""
        phone = phone.replace('+91', '').replace(' ', '')[-10:]
        node_ids = self.index['by_phone'].get(phone, [])
        if not node_ids:
            return {'found': False, 'phone': phone}

        all_results = {'found': True, 'phone': phone, 'networks': []}
        for node_id in node_ids:
            subgraph = self.traverse(node_id)
            all_results['networks'].append(subgraph)
        return all_results

    def find_by_channel(self, username: str) -> dict:
        """Given a Telegram username — find operator and network."""
        node_ids = self.index['by_username'].get(username.lower(), [])
        if not node_ids:
            return {'found': False, 'username': username}

        results = {'found': True, 'username': username, 'networks': []}
        for node_id in node_ids:
            subgraph = self.traverse(node_id)
            results['networks'].append(subgraph)
        return results

    def operator_confidence(self, operator_id: str) -> int:
        """Score confidence in operator attribution 0-100."""
        if operator_id not in self.nodes:
            return 0

        score = 0
        # Find all edges from this operator
        op_edges = [e for e in self.edges
                    if e['from'] == operator_id or e['to'] == operator_id]

        for edge in op_edges:
            rel = edge['relation']
            if rel == 'USES_PHONE':        score += 40
            if rel == 'USES_UPI':          score += 35
            if rel == 'USES_WHATSAPP':     score += 30
            if rel == 'OPERATES':          score += 20
            if rel == 'AFFILIATED_WITH':   score += 15
            if rel == 'IMPERSONATES':      score += 20
            if rel == 'LINKED_TO':         score += 10

        return min(score, 95)

    def export_stix(self) -> dict:
        """Export graph as STIX 2.1 bundle."""
        stix_objects = []
        id_map = {}

        for node_id, node in self.nodes.items():
            stix_id = f"threat-actor--{str(uuid.uuid4())}"
            id_map[node_id] = stix_id

            if node['type'] == 'OPERATOR':
                stix_objects.append({
                    'type':             'threat-actor',
                    'spec_version':     '2.1',
                    'id':               stix_id,
                    'created':          node['added_at'],
                    'modified':         node['added_at'],
                    'name':             node['identifier'],
                    'description':      json.dumps(node['properties']),
                    'threat_actor_types': ['criminal'],
                    'confidence':       node['confidence'],
                })
            elif node['type'] == 'CHANNEL':
                stix_objects.append({
                    'type':         'indicator',
                    'spec_version': '2.1',
                    'id':           stix_id,
                    'created':      node['added_at'],
                    'modified':     node['added_at'],
                    'name':         f"Telegram: {node['identifier']}",
                    'pattern':      "[url:value = 't.me/" + node['identifier'] + "']",
                    'pattern_type': 'stix',
                    'valid_from':   node['added_at'],
                    'indicator_types': ['malicious-activity'],
                })
            elif node['type'] == 'PHONE':
                stix_objects.append({
                    'type':         'indicator',
                    'spec_version': '2.1',
                    'id':           stix_id,
                    'created':      node['added_at'],
                    'modified':     node['added_at'],
                    'name':         f"India fraud phone: +91-{node['identifier']}",
                    'pattern':      "[phone-number:value = '+91" + node['identifier'] + "']",
                    'pattern_type': 'stix',
                    'valid_from':   node['added_at'],
                    'indicator_types': ['malicious-activity'],
                })

        return {
            'type':    'bundle',
            'id':      f"bundle--{str(uuid.uuid4())}",
            'spec_version': '2.1',
            'objects': stix_objects,
        }

    def stats(self) -> dict:
        by_type = defaultdict(int)
        for node in self.nodes.values():
            by_type[node['type']] += 1

        by_relation = defaultdict(int)
        for edge in self.edges:
            by_relation[edge['relation']] += 1

        return {
            'total_nodes':  len(self.nodes),
            'total_edges':  len(self.edges),
            'by_type':      dict(by_type),
            'by_relation':  dict(by_relation),
        }

    def save(self, path: str = 'reports/fraud_intelligence_graph.json'):
        os.makedirs('reports', exist_ok=True)
        data = {
            'version':    '1.0',
            'created_at': self.created_at,
            'updated_at': datetime.now().isoformat(),
            'source':     'CINEOS — India Trust Intelligence Network',
            'patent':     'US Provisional Patent 64/049,190',
            'legal_note': 'All data from public sources. IT Act 65B compliant.',
            'nodes':      self.nodes,
            'edges':      self.edges,
            'index':      {k: dict(v) for k, v in self.index.items()},
            'stats':      self.stats(),
        }
        json.dump(data, open(path, 'w'), indent=2, default=str)
        return path

    @classmethod
    def load(cls, path: str = 'reports/fraud_intelligence_graph.json'):
        g = cls()
        try:
            data = json.load(open(path))
            g.nodes  = data.get('nodes', {})
            g.edges  = data.get('edges', [])
            # Rebuild index
            for node_id, node in g.nodes.items():
                ntype = node['type']
                g.index['by_type'][ntype].append(node_id)
                if ntype == 'PHONE':
                    g.index['by_phone'][node['identifier']].append(node_id)
                elif ntype == 'UPI':
                    g.index['by_upi'][node['identifier']].append(node_id)
                elif ntype == 'CHANNEL':
                    u = node.get('properties',{}).get('username',
                                 node['identifier'])
                    g.index['by_username'][u.lower()].append(node_id)
            print(f"Graph loaded: {len(g.nodes)} nodes, {len(g.edges)} edges")
        except FileNotFoundError:
            print("No existing graph — starting fresh")
        return g


def ingest_all_cineos_data():
    """
    Ingest all existing CINEOS scan data into the graph.
    Runs once to bootstrap — then daily scanner adds incrementally.
    """
    g = FraudIntelligenceGraph()

    print("Ingesting all CINEOS intelligence into graph...\n")

    ingested = {
        'operators': 0, 'channels': 0, 'phones': 0,
        'upis': 0, 'networks': 0, 'edges': 0,
    }

    # ── KNOWN NETWORKS ────────────────────────────────────
    NETWORKS = [
        ('Reddy Anna Book',   'betting',    'ED case active'),
        ('Mahadev Book',      'betting',    'ED case active'),
        ('Fair786',           'betting',    'illegal platform'),
        ('Lotus365',          'betting',    'illegal platform'),
        ('Play99',            'betting',    'illegal platform'),
        ('BigDaddy',          'colour_pred','illegal lottery'),
        ('Yaarwin',           'colour_pred','illegal lottery'),
        ('Daman',             'colour_pred','illegal lottery'),
        ('Tiranga',           'colour_pred','illegal lottery'),
        ('91Club',            'colour_pred','illegal lottery'),
        ('BDGWin',            'colour_pred','illegal lottery'),
    ]
    for name, category, note in NETWORKS:
        nid = g.add_node('NETWORK', name, {
            'category': category,
            'note':     note,
            'confidence': 95,
        })
        ingested['networks'] += 1

    # ── INGEST CHANNEL DATABASE ───────────────────────────
    try:
        channels = json.load(open('reports/all_channels.json'))
        print(f"Ingesting {len(channels)} channels...")

        for ch in channels:
            username = ch.get('username', '')
            title    = ch.get('title', '')
            subs     = ch.get('subscribers', 0)
            if not username:
                continue

            ch_id = g.add_node('CHANNEL', username, {
                'username':    username,
                'title':       title,
                'subscribers': subs,
                'platform':    'telegram',
                'confidence':  80,
            })
            ingested['channels'] += 1

            # Link to known networks by name matching
            title_lower = title.lower() + username.lower()
            for name, _, _ in NETWORKS:
                if name.lower().replace(' ','') in title_lower.replace(' ',''):
                    net_id = make_id('NETWORK', name)
                    if net_id in g.nodes:
                        g.add_edge(ch_id, net_id, 'AFFILIATED_WITH', 85)
                        ingested['edges'] += 1

        print(f"  Channels: {ingested['channels']}")
    except Exception as e:
        print(f"Channel ingest error: {e}")

    # ── INGEST PHONE ATTRIBUTION ──────────────────────────
    KNOWN_PHONES = [
        {
            'phone':    '8306154335',
            'whatsapp': True,
            'channels': ['BCCI_MATCH_TOSS_FIXER0', 'BCCI_TOSS_MATCH_FIXER1'],
            'networks': ['Reddy Anna Book'],
            'violations': ['IT Act 66D', 'PGA 1867', 'BNS 318'],
            'confidence': 95,
            'source':   'Publicly posted in channel messages',
        },
        {
            'phone':    '9216328940',
            'whatsapp': True,
            'channels': ['BCCI_MATCH_TOSS_FIXER0', 'BCCI_TOSS_MATCH_FIXER1'],
            'networks': ['Reddy Anna Book'],
            'violations': ['IT Act 66D', 'PGA 1867', 'BNS 318'],
            'confidence': 95,
            'source':   'Publicly posted in channel messages',
        },
        {
            'phone':    '8441916068',
            'whatsapp': False,
            'channels': ['IPLBetting', 'ipltossmatchsessionn'],
            'networks': [],
            'confidence': 90,
            'source':   'Phone attribution scan',
        },
        {
            'phone':    '6378542162',
            'channels': ['Satta_khaiwal_gali_dishwar'],
            'confidence': 85,
            'source':   'Phone attribution scan',
        },
        {
            'phone':    '8696206466',
            'channels': [],
            'confidence': 75,
            'source':   'Deep scan',
        },
        {
            'phone':    '9911919102',
            'channels': [],
            'confidence': 75,
            'source':   'Deep scan',
        },
    ]

    for p_data in KNOWN_PHONES:
        phone    = p_data['phone']
        phone_id = g.add_node('PHONE', phone, {
            'number':     f"+91-{phone}",
            'whatsapp':   p_data.get('whatsapp', False),
            'source':     p_data.get('source', ''),
            'violations': p_data.get('violations', []),
            'confidence': p_data['confidence'],
        })
        ingested['phones'] += 1

        # Create operator node (unknown identity — police to complete)
        op_id = g.add_node('OPERATOR', f"UNKNOWN_OP_{phone[-4:]}", {
            'status':     'UNIDENTIFIED',
            'known_phone':f"+91-{phone}",
            'confidence': p_data['confidence'],
            'next_step':  'DoT subscriber lookup required',
        })
        ingested['operators'] += 1

        # Operator uses phone
        g.add_edge(op_id, phone_id, 'USES_PHONE',
                   p_data['confidence'])
        ingested['edges'] += 1

        # Phone linked to channels
        for ch_username in p_data.get('channels', []):
            ch_id = make_id('CHANNEL', ch_username)
            if ch_id not in g.nodes:
                g.add_node('CHANNEL', ch_username, {
                    'username':   ch_username,
                    'platform':   'telegram',
                    'confidence': 90,
                })
            g.add_edge(op_id, ch_id, 'OPERATES', p_data['confidence'])
            g.add_edge(phone_id, ch_id, 'USED_IN', p_data['confidence'])
            ingested['edges'] += 2

        # Linked to networks
        for net_name in p_data.get('networks', []):
            net_id = make_id('NETWORK', net_name)
            if net_id in g.nodes:
                g.add_edge(op_id, net_id, 'AFFILIATED_WITH', 80)
                ingested['edges'] += 1

    print(f"  Phones:    {ingested['phones']}")
    print(f"  Operators: {ingested['operators']}")

    # ── INGEST IPL OPERATOR PROFILES ─────────────────────
    try:
        profiles = json.load(open('reports/operator_profiles_ipl.json'))
        for op in profiles.get('operators', []):
            op_id = g.add_node('OPERATOR', op['id'], {
                'name':       op.get('name', ''),
                'confidence': op.get('confidence', 50),
                'violations': op.get('violations', []),
                'status':     'PARTIALLY_IDENTIFIED',
            })
            # Link channels
            for ch in op.get('channels', []):
                ch_id = make_id('CHANNEL', ch)
                if ch_id not in g.nodes:
                    g.add_node('CHANNEL', ch, {
                        'username':  ch,
                        'platform':  'telegram',
                        'confidence': 85,
                    })
                g.add_edge(op_id, ch_id, 'OPERATES',
                           op.get('confidence', 50))
                ingested['edges'] += 1

            # Link networks
            for net in op.get('network', []):
                net_id = g.add_node('NETWORK', net, {
                    'category':  'betting',
                    'confidence': 70,
                })
                g.add_edge(op_id, net_id, 'AFFILIATED_WITH', 70)
                ingested['edges'] += 1

        print(f"  IPL operators ingested")
    except:
        pass

    # ── INGEST COUNTERFEIT SELLERS ────────────────────────
    try:
        sellers = json.load(open('reports/seller_auth_scores.json'))
        confirmed = [s for s in sellers if s.get('auth_score', 0) >= 50]

        for seller in confirmed:
            company = seller.get('company', 'Unknown')
            gst     = seller.get('gst', '')
            city    = seller.get('city', '')
            brand   = seller.get('brand', '')
            score   = seller.get('auth_score', 0)

            # Seller as operator
            op_id = g.add_node('OPERATOR', f"SELLER_{company[:20]}", {
                'company':    company,
                'gst_number': gst,
                'city':       city,
                'platform':   'indiamart',
                'status':     'IDENTIFIED_BY_GST',
                'confidence': score,
            })
            ingested['operators'] += 1

            # Brand being counterfeited
            brand_id = g.add_node('BRAND', brand, {
                'name': brand,
                'confidence': 95,
            })

            g.add_edge(op_id, brand_id, 'COUNTERFEITS', score)
            ingested['edges'] += 1

        print(f"  Sellers: {len(confirmed)}")
    except:
        pass

    # ── BCCI IMPERSONATION NODES ──────────────────────────
    bcci_id = g.add_node('BRAND', 'BCCI', {
        'full_name':  'Board of Control for Cricket in India',
        'confidence': 100,
    })

    for ch_name in ['BCCI_MATCH_TOSS_FIXER0', 'BCCI_TOSS_MATCH_FIXER1']:
        ch_id = make_id('CHANNEL', ch_name)
        if ch_id in g.nodes:
            g.add_edge(ch_id, bcci_id, 'IMPERSONATES', 95)
            ingested['edges'] += 1

    # ── SAVE GRAPH ────────────────────────────────────────
    path = g.save()
    stats = g.stats()

    print(f"\n{'='*60}")
    print(f"  FRAUD INTELLIGENCE GRAPH BUILT")
    print(f"{'='*60}")
    print(f"  Total nodes:  {stats['total_nodes']:,}")
    print(f"  Total edges:  {stats['total_edges']:,}")
    print(f"")
    print(f"  By node type:")
    for ntype, count in sorted(stats['by_type'].items(),
                                key=lambda x: -x[1]):
        print(f"    {ntype:15}: {count:,}")
    print(f"")
    print(f"  By relationship:")
    for rel, count in sorted(stats['by_relation'].items(),
                              key=lambda x: -x[1]):
        print(f"    {rel:20}: {count:,}")
    print(f"")
    print(f"  Saved: {path}")

    # ── DEMO: QUERY THE GRAPH ─────────────────────────────
    print(f"\n{'='*60}")
    print(f"  GRAPH QUERY DEMO")
    print(f"{'='*60}")

    # Query 1: Give me phone → find operator network
    print(f"\nQUERY: Who operates +91-8306154335?")
    result = g.find_by_phone('8306154335')
    if result['found']:
        for net in result['networks']:
            ops = net.get('operators', [])
            for op_id in ops:
                op = net['nodes'].get(op_id, {})
                conf = g.operator_confidence(op_id)
                print(f"  Operator: {op.get('identifier',op_id)}")
                print(f"  Confidence: {conf}%")
                ch_edges = [e for e in net['edges']
                           if e['from']==op_id and e['relation']=='OPERATES']
                if ch_edges:
                    print(f"  Operates channels: {len(ch_edges)}")
    else:
        print(f"  Phone not in graph")

    # Query 2: Find all Reddy Anna affiliated channels
    print(f"\nQUERY: All channels affiliated with Reddy Anna?")
    reddyanna_id = make_id('NETWORK', 'Reddy Anna Book')
    affiliated = [
        e['from'] for e in g.edges
        if e['to'] == reddyanna_id
        and e['relation'] == 'AFFILIATED_WITH'
    ]
    print(f"  {len(affiliated)} channels affiliated with Reddy Anna Book")
    for ch_id in affiliated[:10]:
        ch = g.nodes.get(ch_id, {})
        props = ch.get('properties', {})
        subs  = props.get('subscribers', 0)
        subs_str = (f"{subs/1000000:.1f}M" if subs>=1000000
                    else f"{subs/1000:.0f}K" if subs>=1000
                    else str(subs))
        print(f"  → @{props.get('username', ch.get('identifier',''))}"
              f" ({subs_str} subs)")

    # Query 3: Find all BCCI impersonators
    print(f"\nQUERY: All channels impersonating BCCI?")
    bcci_fakes = [
        e['from'] for e in g.edges
        if e['to'] == bcci_id and e['relation'] == 'IMPERSONATES'
    ]
    print(f"  {len(bcci_fakes)} BCCI impersonator channels confirmed")
    for ch_id in bcci_fakes:
        ch = g.nodes.get(ch_id, {})
        print(f"  → @{ch.get('identifier',ch_id)}")
        print(f"    Violations: IT Act 66D — cheating by personation")

    # Export STIX
    stix = g.export_stix()
    json.dump(stix,
              open('reports/fraud_graph_stix.json','w'),
              indent=2)
    print(f"\n  STIX 2.1 export: reports/fraud_graph_stix.json")
    print(f"  ({len(stix['objects'])} STIX objects)")

    return g

# Run
g = ingest_all_cineos_data()
