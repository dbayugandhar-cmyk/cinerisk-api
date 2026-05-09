"""
CINEOS Piracy Knowledge Graph
Persistent database of all piracy detections.
Every scan builds the graph automatically.
"""
import asyncio, httpx, json, os, hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse

DB_URL = os.environ.get('DATABASE_URL', '')

# ── DATABASE SCHEMA ───────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS kg_nodes (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    domain TEXT,
    node_type TEXT,
    cdn TEXT,
    nameservers TEXT,
    operator_cluster TEXT,
    subscriber_count INTEGER DEFAULT 0,
    hit_count INTEGER DEFAULT 1,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS kg_edges (
    id SERIAL PRIMARY KEY,
    from_node TEXT NOT NULL,
    to_node TEXT NOT NULL,
    relationship TEXT NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_node, to_node, relationship)
);

CREATE TABLE IF NOT EXISTS kg_events (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    title TEXT,
    node_id TEXT,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kg_operators (
    id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    cdn TEXT,
    nameservers TEXT,
    domain_count INTEGER DEFAULT 1,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    domains JSONB DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_nodes_domain ON kg_nodes(domain);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON kg_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_cluster ON kg_nodes(operator_cluster);
CREATE INDEX IF NOT EXISTS idx_edges_from ON kg_edges(from_node);
CREATE INDEX IF NOT EXISTS idx_edges_to ON kg_edges(to_node);
CREATE INDEX IF NOT EXISTS idx_events_type ON kg_events(event_type);
"""

def node_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]

def operator_id(nameservers: list) -> str:
    key = ','.join(sorted(nameservers))
    return hashlib.md5(key.encode()).hexdigest()[:12]

# ── DB CONNECTION ─────────────────────────────────────────
async def get_db():
    try:
        import asyncpg
        conn = await asyncpg.connect(DB_URL)
        return conn
    except ImportError:
        print("[KG] asyncpg not installed — pip3 install asyncpg")
        return None
    except Exception as e:
        print(f"[KG] DB connection failed: {e}")
        return None

async def init_db():
    conn = await get_db()
    if not conn: return False
    try:
        await conn.execute(SCHEMA)
        await conn.close()
        print("[KG] Database schema initialized")
        return True
    except Exception as e:
        print(f"[KG] Schema init failed: {e}")
        return False

# ── GRAPH OPERATIONS ──────────────────────────────────────
async def add_node(conn, url: str, node_type: str, 
                   cdn='', nameservers=None, 
                   subscribers=0, metadata=None):
    nid = node_id(url)
    domain = urlparse(url).netloc.lower().replace('www.','')
    ns = json.dumps(nameservers or [])
    meta = json.dumps(metadata or {})
    
    await conn.execute("""
        INSERT INTO kg_nodes 
            (id, url, domain, node_type, cdn, nameservers, 
             subscriber_count, metadata)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
        ON CONFLICT (id) DO UPDATE SET
            last_seen = NOW(),
            hit_count = kg_nodes.hit_count + 1,
            subscriber_count = GREATEST(kg_nodes.subscriber_count, $7)
    """, nid, url, domain, node_type, cdn, ns, subscribers, meta)
    
    return nid

async def add_edge(conn, from_url: str, to_url: str, 
                   relationship: str, confidence=1.0):
    from_id = node_id(from_url)
    to_id = node_id(to_url)
    
    await conn.execute("""
        INSERT INTO kg_edges (from_node, to_node, relationship, confidence)
        VALUES ($1,$2,$3,$4)
        ON CONFLICT (from_node, to_node, relationship) DO NOTHING
    """, from_id, to_id, relationship, confidence)

async def add_operator(conn, domains: list, 
                       nameservers: list, cdn: str):
    op_id = operator_id(nameservers)
    ns = ','.join(sorted(nameservers))
    doms = json.dumps(domains)
    
    await conn.execute("""
        INSERT INTO kg_operators 
            (id, fingerprint, cdn, nameservers, domain_count, domains)
        VALUES ($1,$2,$3,$4,$5,$6::jsonb)
        ON CONFLICT (id) DO UPDATE SET
            last_seen = NOW(),
            domain_count = $5,
            domains = $6::jsonb
    """, op_id, ns, cdn, ns, len(domains), doms)
    
    # Update cluster on nodes
    for domain in domains:
        await conn.execute("""
            UPDATE kg_nodes SET operator_cluster = $1
            WHERE domain = $2
        """, op_id, domain)
    
    return op_id

async def log_event(conn, event_type: str, 
                    title: str, node_id_val: str, data: dict):
    await conn.execute("""
        INSERT INTO kg_events (event_type, title, node_id, data)
        VALUES ($1,$2,$3,$4::jsonb)
    """, event_type, title, node_id_val, json.dumps(data))

# ── INGEST SCAN RESULTS ───────────────────────────────────
async def ingest_scan(title: str, category: str, 
                      hits: list, verdict: str):
    """
    Ingest scan results into knowledge graph.
    Called automatically after every scan.
    """
    conn = await get_db()
    if not conn: return
    
    try:
        print(f"[KG] Ingesting {len(hits)} hits for '{title}'")
        
        # Add content node
        content_url = f"content://{title.lower().replace(' ','-')}"
        content_id = await add_node(
            conn, content_url, 'content',
            metadata={'title': title, 'category': category, 
                     'verdict': verdict}
        )
        
        # Process each hit
        dns_cache = {}
        async with httpx.AsyncClient(timeout=8) as client:
            for hit in hits[:20]:
                url = hit.get('url','')
                if not url: continue
                
                domain = urlparse(url).netloc.lower().replace('www.','')
                
                # Get CDN + NS (with cache)
                cdn, nameservers = 'Unknown', []
                if domain not in dns_cache:
                    try:
                        r = await client.get(
                            f"https://dns.google/resolve?name={domain}&type=A")
                        answers = r.json().get('Answer',[])
                        if answers:
                            ip = answers[0].get('data','')
                            cdn = (
                                'Cloudflare' if ip.startswith(('104.','172.64.','162.158.')) else
                                'Fastly' if ip.startswith(('151.101.','199.232.')) else
                                'AWS' if ip.startswith(('13.','52.','54.')) else
                                'Other'
                            )
                        r2 = await client.get(
                            f"https://dns.google/resolve?name={domain}&type=NS")
                        ns_answers = r2.json().get('Answer',[])
                        nameservers = sorted([
                            a.get('data','').lower().rstrip('.')
                            for a in ns_answers
                        ])[:2]
                        dns_cache[domain] = (cdn, nameservers)
                    except:
                        dns_cache[domain] = ('Unknown', [])
                
                cdn, nameservers = dns_cache.get(domain, ('Unknown',[]))
                
                # Add piracy node
                piracy_id = await add_node(
                    conn, url, 'piracy_url',
                    cdn=cdn, nameservers=nameservers,
                    metadata={'platform': hit.get('platform',''),
                             'quality': hit.get('quality',''),
                             'title': title}
                )
                
                # Connect content → piracy
                await add_edge(conn, content_url, url, 'pirated_on', 1.0)
        
        # Run attribution clustering
        await run_attribution_clustering(conn)
        
        # Log event
        await log_event(conn, 'scan', title, content_id,
                       {'hits': len(hits), 'verdict': verdict,
                        'category': category})
        
        await conn.close()
        print(f"[KG] Ingested successfully")
        
    except Exception as e:
        print(f"[KG] Ingest error: {e}")
        await conn.close()

async def ingest_telegram(event: str, streams: list):
    """Ingest Telegram channel scan into knowledge graph."""
    conn = await get_db()
    if not conn: return
    
    try:
        event_url = f"event://{event.lower().replace(' ','-')}"
        await add_node(conn, event_url, 'event',
                      metadata={'event': event})
        
        for s in streams:
            if not s.get('subscriber_count', 0): continue
            ch_url = f"https://t.me/{s['channel']}"
            await add_node(
                conn, ch_url, 'telegram',
                subscribers=s.get('subscriber_count', 0),
                metadata={
                    'is_betting': s.get('is_betting', False),
                    'severity': s.get('severity',''),
                    'language': s.get('language','')
                }
            )
            await add_edge(conn, event_url, ch_url, 
                          'streamed_on', 1.0)
        
        await conn.close()
        print(f"[KG] Telegram scan ingested: {len(streams)} channels")
    except Exception as e:
        print(f"[KG] Telegram ingest error: {e}")

async def run_attribution_clustering(conn):
    """Cluster domains by nameservers and update operators."""
    try:
        rows = await conn.fetch("""
            SELECT domain, cdn, nameservers 
            FROM kg_nodes 
            WHERE node_type = 'piracy_url'
            AND nameservers != '[]'
            GROUP BY domain, cdn, nameservers
        """)
        
        from collections import defaultdict
        clusters = defaultdict(list)
        for row in rows:
            ns = json.loads(row['nameservers'])
            if ns:
                key = ','.join(sorted(ns))
                clusters[key].append((row['domain'], row['cdn']))
        
        for ns_key, domains in clusters.items():
            if len(domains) > 1:
                ns_list = ns_key.split(',')
                cdn = domains[0][1]
                domain_list = [d[0] for d in domains]
                await add_operator(conn, domain_list, ns_list, cdn)
                
    except Exception as e:
        print(f"[KG] Attribution error: {e}")

# ── QUERY THE GRAPH ───────────────────────────────────────
async def query_operator_network(domain: str) -> dict:
    """Find all domains operated by same operator as given domain."""
    conn = await get_db()
    if not conn: return {}
    
    try:
        # Find operator cluster
        row = await conn.fetchrow("""
            SELECT operator_cluster FROM kg_nodes 
            WHERE domain = $1
        """, domain)
        
        if not row or not row['operator_cluster']:
            return {'domain': domain, 'operator': None}
        
        cluster_id = row['operator_cluster']
        
        # Get all domains in cluster
        domains = await conn.fetch("""
            SELECT DISTINCT domain, cdn, nameservers, 
                   hit_count, first_seen, last_seen
            FROM kg_nodes
            WHERE operator_cluster = $1
            ORDER BY hit_count DESC
        """, cluster_id)
        
        op = await conn.fetchrow("""
            SELECT * FROM kg_operators WHERE id = $1
        """, cluster_id)
        
        await conn.close()
        return {
            'domain': domain,
            'operator_id': cluster_id,
            'operator_cdn': op['cdn'] if op else '',
            'operator_nameservers': op['nameservers'].split(',') if op else [],
            'controlled_domains': [dict(d) for d in domains],
            'total_domains': len(domains)
        }
    except Exception as e:
        print(f"[KG] Query error: {e}")
        return {}

async def get_graph_stats() -> dict:
    """Get overall knowledge graph statistics."""
    conn = await get_db()
    if not conn: return {}
    
    try:
        stats = {}
        
        stats['total_nodes'] = await conn.fetchval(
            "SELECT COUNT(*) FROM kg_nodes")
        stats['total_edges'] = await conn.fetchval(
            "SELECT COUNT(*) FROM kg_edges")
        stats['total_operators'] = await conn.fetchval(
            "SELECT COUNT(*) FROM kg_operators")
        stats['total_events'] = await conn.fetchval(
            "SELECT COUNT(*) FROM kg_events")
        
        # By type
        rows = await conn.fetch("""
            SELECT node_type, COUNT(*) as count 
            FROM kg_nodes GROUP BY node_type
        """)
        stats['by_type'] = {r['node_type']: r['count'] for r in rows}
        
        # Top operators
        ops = await conn.fetch("""
            SELECT id, cdn, domain_count, domains
            FROM kg_operators
            ORDER BY domain_count DESC LIMIT 5
        """)
        stats['top_operators'] = [dict(o) for o in ops]
        
        # Recent detections
        recent = await conn.fetch("""
            SELECT title, event_type, created_at,
                   data->>'hits' as hits
            FROM kg_events
            ORDER BY created_at DESC LIMIT 10
        """)
        stats['recent_events'] = [dict(r) for r in recent]
        
        await conn.close()
        return stats
    except Exception as e:
        print(f"[KG] Stats error: {e}")
        return {}

async def get_repeat_offenders(min_hits: int = 3) -> list:
    """Find domains that appear repeatedly across multiple scans."""
    conn = await get_db()
    if not conn: return []
    
    try:
        rows = await conn.fetch("""
            SELECT domain, cdn, operator_cluster,
                   hit_count, first_seen, last_seen,
                   COUNT(DISTINCT (metadata->>'title')) as titles_affected
            FROM kg_nodes
            WHERE node_type = 'piracy_url'
            AND hit_count >= $1
            GROUP BY domain, cdn, operator_cluster, 
                     hit_count, first_seen, last_seen
            ORDER BY hit_count DESC
            LIMIT 20
        """, min_hits)
        
        await conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[KG] Repeat offenders error: {e}")
        return []

if __name__ == '__main__':
    import sys
    
    async def main():
        print("=== CINEOS Knowledge Graph ===")
        
        # Init DB
        ok = await init_db()
        if not ok:
            print("Install asyncpg: pip3 install asyncpg --break-system-packages")
            return
        
        if '--stats' in sys.argv:
            stats = await get_graph_stats()
            print(json.dumps(stats, indent=2, default=str))
        
        elif '--ingest' in sys.argv:
            # Test ingest
            test_hits = [
                {'url':'https://www.5movierulz.markets/retro-2025/',
                 'platform':'5movierulz','quality':'CAM'},
                {'url':'https://www.filmyzilla36.com/retro-2025/',
                 'platform':'filmyzilla','quality':'HDRip'},
            ]
            await ingest_scan('Retro', 'india', test_hits, 'CONFIRMED')
        
        elif '--operators' in sys.argv:
            result = await query_operator_network('5movierulz.markets')
            print(json.dumps(result, indent=2, default=str))
        
        elif '--offenders' in sys.argv:
            offenders = await get_repeat_offenders(1)
            print(f"\nRepeat offenders ({len(offenders)}):")
            for o in offenders:
                print(f"  {o['domain']:35} hits={o['hit_count']} titles={o.get('titles_affected',0)}")
        
        else:
            print("Usage:")
            print("  python3 cineos_knowledge_graph.py --stats")
            print("  python3 cineos_knowledge_graph.py --ingest")
            print("  python3 cineos_knowledge_graph.py --operators")
            print("  python3 cineos_knowledge_graph.py --offenders")
    
    asyncio.run(main())
