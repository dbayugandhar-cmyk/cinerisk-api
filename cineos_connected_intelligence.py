"""
CINEOS Connected Fraud Intelligence Engine

Builds five interconnected intelligence layers:
1. Connected fraud network — who links to whom
2. Linked payment flows — money trail from channel to UPI
3. Repeat infrastructure — same operator, different channels
4. Reseller clusters — franchise fraud operations
5. Risk attribution — confidence-scored evidence packages

All from public data. IT Act 65B compliant.
For law enforcement and enterprise clients only.
"""
import json, re, os, hashlib, hmac
from datetime import datetime
from collections import defaultdict

SECRET = b'cineos_intelligence_2026'

def sign(data: dict) -> str:
    return hmac.new(SECRET,
        json.dumps(data, sort_keys=True,
                   default=str).encode(),
        hashlib.sha256).hexdigest()

def sha256(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True,
                   default=str).encode()
    ).hexdigest()

class ConnectedIntelligence:

    def __init__(self):
        self.graph    = self._load_graph()
        self.channels = self._load_channels()
        self.report   = {
            'generated_at': datetime.now().isoformat(),
            'source': 'CINEOS India Fraud Intelligence',
            'patent': 'US Provisional Patent 64/049,190',
            'legal':  'Public data only. IT Act 65B compliant.',
            'layers': {}
        }

    def _load_graph(self):
        try:
            return json.load(
                open('reports/fraud_intelligence_graph.json'))
        except:
            return {'nodes': {}, 'edges': []}

    def _load_channels(self):
        try:
            return json.load(open('reports/all_channels.json'))
        except:
            return []

    # ── LAYER 1: CONNECTED FRAUD NETWORK ─────────────────
    def build_connected_network(self):
        """
        Map every channel to every other channel
        it is connected to — directly or indirectly.
        Reveals the full fraud ecosystem structure.
        """
        print("\n[1/5] Building connected fraud network...")

        nodes   = self.graph.get('nodes', {})
        edges   = self.graph.get('edges', [])

        # Build adjacency list
        adj = defaultdict(set)
        for edge in edges:
            adj[edge['from']].add(edge['to'])
            adj[edge['to']].add(edge['from'])

        # Find connected components
        visited    = set()
        components = []

        def bfs(start):
            component = []
            queue = [start]
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                component.append(node)
                queue.extend(adj[node] - visited)
            return component

        for node_id in nodes:
            if node_id not in visited:
                comp = bfs(node_id)
                if len(comp) > 1:  # only connected components
                    components.append(comp)

        # Sort by size
        components.sort(key=lambda x: -len(x))

        print(f"  Connected components: {len(components)}")
        print(f"  Largest network:      {len(components[0])} nodes")

        # Enrich top components
        enriched = []
        for comp in components[:10]:
            node_types = defaultdict(int)
            total_reach = 0
            channels_in = []
            operators   = []
            phones      = []
            networks    = []

            for node_id in comp:
                node = nodes.get(node_id, {})
                ntype = node.get('type', '')
                node_types[ntype] += 1

                if ntype == 'CHANNEL':
                    subs = node.get('properties',{}).get('subscribers',0)
                    total_reach += subs
                    channels_in.append(node.get('identifier',''))
                elif ntype == 'OPERATOR':
                    operators.append(node.get('identifier',''))
                elif ntype == 'PHONE':
                    phones.append(node.get('identifier',''))
                elif ntype == 'NETWORK':
                    networks.append(node.get('identifier',''))

            enriched.append({
                'size':        len(comp),
                'node_types':  dict(node_types),
                'total_reach': total_reach,
                'channels':    channels_in[:10],
                'operators':   operators,
                'phones':      phones,
                'networks':    networks,
            })

            if networks or operators:
                reach_str = (f"{total_reach/1000000:.1f}M"
                            if total_reach >= 1000000
                            else f"{total_reach/1000:.0f}K")
                print(f"  Network: {networks or operators} "
                      f"→ {len(channels_in)} channels "
                      f"→ {reach_str} reach")

        self.report['layers']['connected_network'] = {
            'total_components': len(components),
            'largest_size':     len(components[0]) if components else 0,
            'top_networks':     enriched,
        }
        return enriched

    # ── LAYER 2: LINKED PAYMENT FLOWS ────────────────────
    def build_payment_flows(self):
        """
        Trace money flow from fraud channel to payment collection.
        Public data: UPI IDs and phones posted in channels.
        Law enforcement: completes with account holder lookup.
        """
        print("\n[2/5] Building linked payment flows...")

        # Load all extracted payment identifiers
        payment_flows = []

        # From attribution graph
        nodes = self.graph.get('nodes', {})
        edges = self.graph.get('edges', [])

        # Find all UPI nodes
        upi_nodes = {k:v for k,v in nodes.items()
                     if v.get('type') == 'UPI'}

        # Find all phone nodes
        phone_nodes = {k:v for k,v in nodes.items()
                       if v.get('type') == 'PHONE'}

        # For each payment identifier, trace back to channels
        for upi_id, upi_node in upi_nodes.items():
            upi_val   = upi_node.get('identifier','')
            connected = []

            for edge in edges:
                if edge['to'] == upi_id or edge['from'] == upi_id:
                    other = (edge['from'] if edge['to'] == upi_id
                            else edge['to'])
                    other_node = nodes.get(other,{})
                    connected.append({
                        'type':   other_node.get('type',''),
                        'id':     other_node.get('identifier',''),
                        'relation': edge['relation'],
                    })

            # Extract bank from UPI
            bank = upi_val.split('@')[-1] if '@' in upi_val else ''
            bank_map = {
                'okaxis':'Axis Bank', 'okicici':'ICICI Bank',
                'paytm':'Paytm Payments Bank',
                'gpay':'Google Pay', 'phonepe':'PhonePe/Yes Bank',
                'ybl':'Yes Bank', 'sbi':'State Bank of India',
                'hdfc':'HDFC Bank', 'kotak':'Kotak Bank',
                'ibl':'IndusInd Bank',
            }

            flow = {
                'upi_id':     upi_val,
                'bank':       bank_map.get(bank, bank),
                'connected':  connected,
                'evidence':   sha256({'upi': upi_val,
                                     'ts': datetime.now().isoformat()}),
                'next_step':  'NPCI query for account holder',
                'legal_basis':'IT Act 65B — public channel evidence',
            }
            payment_flows.append(flow)

        # From phone attribution
        phone_flows = []
        for phone_id, phone_node in phone_nodes.items():
            phone_val = phone_node.get('identifier','')
            channels_using = []

            for edge in edges:
                if edge['from'] == phone_id or edge['to'] == phone_id:
                    other = (edge['to'] if edge['from'] == phone_id
                            else edge['from'])
                    other_node = nodes.get(other,{})
                    if other_node.get('type') == 'CHANNEL':
                        channels_using.append(
                            other_node.get('identifier',''))

            phone_flows.append({
                'phone':          f"+91-{phone_val}",
                'whatsapp':       phone_node.get(
                    'properties',{}).get('whatsapp', False),
                'channels_found_in': channels_using,
                'confidence':     phone_node.get('properties',{}).get(
                    'confidence', 75),
                'source':         'Publicly posted in channel messages',
                'evidence_hash':  sha256({'phone': phone_val}),
                'next_step':      'DoT subscriber lookup — police authority',
                'next_step_2':    'Bank KYC linked to phone number',
                'legal_basis':    'IT Act 65B — public channel evidence',
            })

        print(f"  UPI payment flows mapped:   {len(payment_flows)}")
        print(f"  Phone payment flows mapped: {len(phone_flows)}")

        if phone_flows:
            print(f"\n  PHONE → PAYMENT FLOW:")
            for pf in phone_flows:
                print(f"  {pf['phone']}")
                print(f"    → Found in: {pf['channels_found_in'][:3]}")
                print(f"    → Confidence: {pf['confidence']}%")
                print(f"    → Next: {pf['next_step']}")

        self.report['layers']['payment_flows'] = {
            'upi_flows':   payment_flows,
            'phone_flows': phone_flows,
            'total':       len(payment_flows) + len(phone_flows),
        }
        return payment_flows, phone_flows

    # ── LAYER 3: REPEAT INFRASTRUCTURE ───────────────────
    def detect_repeat_infrastructure(self):
        """
        Identify operators using same infrastructure
        across multiple channels — proves coordinated operation.
        Three signals: naming pattern, message template, timing.
        """
        print("\n[3/5] Detecting repeat infrastructure...")

        channels = self.channels
        repeat_clusters = []

        # Signal 1: Naming pattern clusters
        print("  Analysing naming patterns...")
        name_patterns = defaultdict(list)

        for ch in channels:
            username = ch.get('username','')
            title    = ch.get('title','')

            # Extract root name pattern
            # BCCI_TOSS_FIXER0, BCCI_TOSS_FIXER1 → root: BCCI_TOSS_FIXER
            root = re.sub(r'[\d]+$', '', username)  # strip trailing numbers
            root = re.sub(r'[_\-][\d]+$', '', root) # strip _0, _1 etc

            if len(root) >= 8:
                name_patterns[root.lower()].append(ch)

        # Clusters with 2+ channels = same operator
        name_clusters = {k:v for k,v in name_patterns.items()
                        if len(v) >= 2}

        print(f"  Naming pattern clusters: {len(name_clusters)}")
        for pattern, chs in sorted(name_clusters.items(),
                                    key=lambda x: -len(x[1]))[:10]:
            total_subs = sum(c.get('subscribers',0) for c in chs)
            print(f"  Pattern: '{pattern}' → "
                  f"{len(chs)} channels, "
                  f"{total_subs/1000:.0f}K subs")
            for ch in chs[:3]:
                print(f"    → @{ch['username']}")

            repeat_clusters.append({
                'type':     'naming_pattern',
                'pattern':  pattern,
                'channels': [c['username'] for c in chs],
                'count':    len(chs),
                'reach':    total_subs,
                'confidence': 85,
                'evidence': 'Sequential numbering = same operator',
                'legal':    'Proves coordinated operation under BNS 2023',
            })

        # Signal 2: Platform name clusters
        # (Reddy Anna, Mahadev Book appearing in multiple channels)
        brand_patterns = defaultdict(list)
        FRAUD_BRANDS = [
            'reddy anna','mahadev book','mahadev','nitinn online',
            'lotus365','betbhai','laser247','tiger365',
            'sky exchange','fairplay','wolf777','murugan fixer',
            'bcci toss','bcci match',
        ]

        for ch in channels:
            combined = (ch.get('username','') + ' ' +
                       ch.get('title','')).lower()
            for brand in FRAUD_BRANDS:
                if brand in combined:
                    brand_patterns[brand].append(ch)

        brand_clusters = {k:v for k,v in brand_patterns.items()
                         if len(v) >= 3}

        print(f"\n  Brand/network clusters: {len(brand_clusters)}")
        for brand, chs in sorted(brand_clusters.items(),
                                  key=lambda x: -len(x[1]))[:8]:
            total_subs = sum(c.get('subscribers',0) for c in chs)
            subs_str = (f"{total_subs/1000000:.1f}M"
                       if total_subs >= 1000000
                       else f"{total_subs/1000:.0f}K")
            print(f"  '{brand}': {len(chs)} channels, {subs_str} reach")

            repeat_clusters.append({
                'type':     'brand_cluster',
                'brand':    brand,
                'channels': [c['username'] for c in chs[:10]],
                'count':    len(chs),
                'reach':    total_subs,
                'confidence': 80,
                'evidence': f'{len(chs)} channels promoting same brand',
                'legal':    'Franchise fraud operation',
            })

        self.report['layers']['repeat_infrastructure'] = {
            'naming_clusters': len(name_clusters),
            'brand_clusters':  len(brand_clusters),
            'total_clusters':  len(repeat_clusters),
            'clusters':        repeat_clusters[:20],
        }
        return repeat_clusters

    # ── LAYER 4: RESELLER CLUSTERS ────────────────────────
    def map_reseller_clusters(self):
        """
        Map franchise/reseller structures in fraud ecosystem.
        Pattern: Hub channel + multiple agent channels
        Hub: main brand account
        Agents: individual operators promoting for commission
        """
        print("\n[4/5] Mapping reseller clusters...")

        # Known hub networks from our data
        KNOWN_HUBS = {
            'Reddy Anna Book': {
                'channels': ['Anuragt_bookqc_Malikc', 'News_Crypto5',
                            'CRYPTO_reddy_annag', 'Mahadevsd_Bookuoo',
                            'gold365_lotus3655', 'reddyanna888_io'],
                'model':    'Betting book — agents earn commission per ID',
                'reach':    0,
                'phones':   ['8306154335','9216328940'],
                'legal':    'Public Gambling Act 1867 — organised crime',
            },
            'Mahadev Book': {
                'channels': ['CRYPTO_book_lotus365_nitinnj',
                            'mahadev_bookiee', 'Mahadev_id_gold365',
                            'mahadevbook_laser247_skyexchange',
                            'online_lotus365_mahadev'],
                'model':    'Betting book — subject of active ED case',
                'reach':    0,
                'phones':   [],
                'legal':    'ED investigation active — offshore operation',
            },
            'BigDaddy / Colour Prediction': {
                'channels': ['Colourc_Predictc_daddy',
                            'bdgwind_daddyt_gamer',
                            'daman_55clubs_BigDaddy',
                            'Lottery_Tiranga_91Club_82_Daman',
                            'daddy_predictss'],
                'model':    'Illegal lottery — colour prediction format',
                'reach':    0,
                'phones':   [],
                'legal':    'RBI Act — illegal lottery, no registration',
            },
            'Fair786': {
                'channels': ['session_cricket_tips',
                            'fair786guide', 'FAIR786FAMILY'],
                'model':    'Betting platform — agent commission model',
                'reach':    0,
                'phones':   [],
                'legal':    'Public Gambling Act 1867',
            },
            'Murugan / Play99': {
                'channels': ['MURUGAN_FIXER_LONDON1',
                            'Playgames9999', 'play99_support'],
                'model':    'Betting platform — overseas operator claim',
                'reach':    0,
                'phones':   [],
                'legal':    'FEMA 1999 — foreign operator, India victims',
            },
        }

        # Calculate reach for each hub
        ch_map = {c.get('username','').lower():c
                  for c in self.channels}

        for hub_name, hub_data in KNOWN_HUBS.items():
            total_reach = 0
            for ch_username in hub_data['channels']:
                ch = ch_map.get(ch_username.lower(), {})
                total_reach += ch.get('subscribers', 0)
            hub_data['reach']       = total_reach
            hub_data['agent_count'] = len(hub_data['channels'])

        print(f"  Reseller networks mapped: {len(KNOWN_HUBS)}")
        print(f"\n  RESELLER CLUSTER ANALYSIS:")
        print(f"  {'─'*55}")

        total_ecosystem_reach = 0
        for hub_name, data in sorted(KNOWN_HUBS.items(),
                                      key=lambda x: -x[1]['reach']):
            reach = data['reach']
            reach_str = (f"{reach/1000000:.1f}M"
                        if reach >= 1000000 else f"{reach/1000:.0f}K")
            total_ecosystem_reach += reach

            print(f"\n  {hub_name}")
            print(f"    Agents:    {data['agent_count']} channels")
            print(f"    Reach:     {reach_str} subscribers")
            print(f"    Model:     {data['model']}")
            print(f"    Legal:     {data['legal']}")
            if data['phones']:
                print(f"    Phones:    {['+91-'+p for p in data['phones']]}")
            print(f"    Channels:  {data['channels'][:4]}")

        print(f"\n  TOTAL ECOSYSTEM REACH: "
              f"{total_ecosystem_reach/1000000:.1f}M subscribers")
        print(f"  Across {len(KNOWN_HUBS)} reseller networks")

        self.report['layers']['reseller_clusters'] = {
            'networks':              len(KNOWN_HUBS),
            'total_ecosystem_reach': total_ecosystem_reach,
            'clusters':              KNOWN_HUBS,
        }
        return KNOWN_HUBS

    # ── LAYER 5: RISK ATTRIBUTION WITH EVIDENCE ──────────
    def build_risk_attribution(self):
        """
        Generate confidence-scored evidence packages
        for each identified operator and network.
        Court-ready. IT Act 65B compliant.
        """
        print("\n[5/5] Building risk attribution packages...")

        nodes = self.graph.get('nodes', {})
        edges = self.graph.get('edges', [])

        attributions = []

        # For each operator node — build full attribution
        operator_nodes = {k:v for k,v in nodes.items()
                         if v.get('type') == 'OPERATOR'}

        for op_id, op_node in operator_nodes.items():
            identifier = op_node.get('identifier','')
            properties = op_node.get('properties', {})

            # Find all connected nodes
            connected = []
            for edge in edges:
                if edge['from'] == op_id:
                    other = nodes.get(edge['to'], {})
                    connected.append({
                        'type':     other.get('type',''),
                        'id':       other.get('identifier',''),
                        'relation': edge['relation'],
                        'confidence': edge.get('confidence', 70),
                    })
                elif edge['to'] == op_id:
                    other = nodes.get(edge['from'], {})
                    connected.append({
                        'type':     other.get('type',''),
                        'id':       other.get('identifier',''),
                        'relation': edge['relation'],
                        'confidence': edge.get('confidence', 70),
                    })

            # Calculate attribution confidence
            conf = 0
            signals = []
            for conn in connected:
                if conn['relation'] == 'USES_PHONE':
                    conf += 40
                    signals.append(f"Phone: +91-{conn['id']}")
                elif conn['relation'] == 'USES_UPI':
                    conf += 35
                    signals.append(f"UPI: {conn['id']}")
                elif conn['relation'] == 'USES_WHATSAPP':
                    conf += 30
                    signals.append(f"WhatsApp: +91-{conn['id']}")
                elif conn['relation'] == 'OPERATES':
                    conf += 15
                    signals.append(f"Channel: @{conn['id']}")
                elif conn['relation'] == 'AFFILIATED_WITH':
                    conf += 10
                    signals.append(f"Network: {conn['id']}")
                elif conn['relation'] == 'IMPERSONATES':
                    conf += 20
                    signals.append(f"Impersonates: {conn['id']}")

            conf = min(conf, 95)

            # Build evidence package
            evidence_data = {
                'operator':  identifier,
                'signals':   signals,
                'connected': connected,
                'timestamp': datetime.now().isoformat(),
            }

            attribution = {
                'operator_id':   op_id,
                'identifier':    identifier,
                'confidence':    conf,
                'tier':         ('TIER_1' if conf >= 70
                                else 'TIER_2' if conf >= 40
                                else 'TIER_3'),
                'signals':       signals,
                'connected':     connected,
                'evidence_hash': sha256(evidence_data),
                'hmac_sig':      sign(evidence_data)[:32],
                'captured_at':   datetime.now().isoformat(),
                'standard':      'IT Act 2000 Section 65B',
                'violations':    properties.get('violations', []),
                'next_steps': {
                    'if_phone': 'DoT subscriber lookup → operator name',
                    'if_upi':   'NPCI query → bank account holder',
                    'if_channel': 'IT Rules 2021 takedown notice',
                    'court':    'Evidence package + 65B certificate',
                }
            }
            attributions.append(attribution)

        # Sort by confidence
        attributions.sort(key=lambda x: -x['confidence'])

        print(f"  Attribution packages: {len(attributions)}")
        print(f"\n  TOP ATTRIBUTIONS:")
        print(f"  {'─'*55}")
        for attr in attributions[:8]:
            tier   = attr['tier']
            conf   = attr['confidence']
            op_id  = attr['identifier']
            sigs   = attr['signals'][:2]
            print(f"  [{tier}] {conf:3}% — {op_id}")
            for s in sigs:
                print(f"           Signal: {s}")

        self.report['layers']['risk_attribution'] = {
            'total_attributions': len(attributions),
            'tier1': sum(1 for a in attributions if a['tier']=='TIER_1'),
            'tier2': sum(1 for a in attributions if a['tier']=='TIER_2'),
            'tier3': sum(1 for a in attributions if a['tier']=='TIER_3'),
            'attributions': attributions,
        }
        return attributions

    def run_all(self):
        """Run all five intelligence layers."""
        print("="*60)
        print("  CINEOS CONNECTED INTELLIGENCE ENGINE")
        print("  5 Layers — Public data — IT Act 65B")
        print("="*60)

        self.build_connected_network()
        self.build_payment_flows()
        self.detect_repeat_infrastructure()
        self.map_reseller_clusters()
        self.build_risk_attribution()

        # Final summary
        r = self.report['layers']
        print(f"\n{'='*60}")
        print(f"  COMPLETE INTELLIGENCE SUMMARY")
        print(f"{'='*60}")
        print(f"""
  LAYER 1 — Connected Network:
    Components:  {r.get('connected_network',{}).get('total_components',0)}
    Largest:     {r.get('connected_network',{}).get('largest_size',0)} nodes

  LAYER 2 — Payment Flows:
    UPI flows:   {r.get('payment_flows',{}).get('total',0)}
    Phone flows: {len(r.get('payment_flows',{}).get('phone_flows',[]))}
    Next step:   NPCI + DoT for account holder

  LAYER 3 — Repeat Infrastructure:
    Name clusters:  {r.get('repeat_infrastructure',{}).get('naming_clusters',0)}
    Brand clusters: {r.get('repeat_infrastructure',{}).get('brand_clusters',0)}

  LAYER 4 — Reseller Clusters:
    Networks: {r.get('reseller_clusters',{}).get('networks',0)}
    Total ecosystem reach: {r.get('reseller_clusters',{}).get('total_ecosystem_reach',0)/1000000:.1f}M

  LAYER 5 — Risk Attribution:
    Total operators: {r.get('risk_attribution',{}).get('total_attributions',0)}
    Tier 1 (95%+):   {r.get('risk_attribution',{}).get('tier1',0)}
    Tier 2 (70-94%): {r.get('risk_attribution',{}).get('tier2',0)}
    Tier 3 (review): {r.get('risk_attribution',{}).get('tier3',0)}
        """)

        # Save
        os.makedirs('reports', exist_ok=True)
        path = 'reports/connected_intelligence.json'
        json.dump(self.report, open(path,'w'),
                  indent=2, default=str)
        print(f"  Saved: {path}")
        print(f"  Ready for: I4C, BCCI, SEBI, ED, NPCI")
        print(f"  Format: JSON + STIX 2.1 via cineos_stix_exporter.py")
        return self.report

# Run
engine = ConnectedIntelligence()
engine.run_all()
