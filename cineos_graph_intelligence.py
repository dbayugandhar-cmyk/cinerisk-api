"""
CINEOS Piracy Graph Intelligence
Automatically maps piracy networks from a single seed URL.
Legal: Only uses public data — WHOIS, DNS, search engines, 
       public Telegram channels, public websites.
"""
import asyncio, httpx, re, json, datetime
from urllib.parse import urlparse

# ── GRAPH NODE TYPES ─────────────────────────────────────
NODE_TYPES = {
    'source':    {'color': '#ff3355', 'icon': '🔴'},
    'mirror':    {'color': '#ff8c00', 'icon': '🟠'},
    'telegram':  {'color': '#3d7fff', 'icon': '📱'},
    'cdn':       {'color': '#b060ff', 'icon': '☁️'},
    'reseller':  {'color': '#ffcc00', 'icon': '💰'},
    'social':    {'color': '#00e87a', 'icon': '📣'},
}

class PiracyNode:
    def __init__(self, url, node_type, title='', subscribers=0, parent=None):
        self.url = url
        self.domain = urlparse(url).netloc.lower().replace('www.','')
        self.node_type = node_type
        self.title = title
        self.subscribers = subscribers
        self.parent = parent
        self.children = []
        self.discovered_at = datetime.datetime.now().isoformat()
    
    def to_dict(self):
        return {
            'url': self.url,
            'domain': self.domain,
            'type': self.node_type,
            'title': self.title,
            'subscribers': self.subscribers,
            'parent': self.parent,
            'children': len(self.children),
            'discovered_at': self.discovered_at,
        }

class PiracyGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = []
    
    def add_node(self, node: PiracyNode):
        if node.url not in self.nodes:
            self.nodes[node.url] = node
            if node.parent:
                self.edges.append({'from': node.parent, 'to': node.url, 
                                   'type': node.node_type})
    
    def to_report(self):
        return {
            'total_nodes': len(self.nodes),
            'by_type': {t: len([n for n in self.nodes.values() 
                               if n.node_type == t]) 
                       for t in NODE_TYPES},
            'nodes': [n.to_dict() for n in self.nodes.values()],
            'edges': self.edges,
        }

# ── DISCOVERY FUNCTIONS ───────────────────────────────────

# Known piracy domain patterns
PIRACY_DOMAINS = [
    'movierulz','tamilblasters','filmyzilla','ibomma','moviesda',
    'tamilmv','kuttymovies','isaimini','hdmovies','9xmovies',
    'filmywap','bolly4u','vegamovies','hdhub4u','rdxhd',
    'worldfree4u','downloadhub','1337x','yts','rarbg',
    'fitgirl','igg-games','steamunlocked','dodi-repacks',
    'thepiratebay','nyaa','torrentgalaxy','limetorrents',
    'vipbox','hesgoal','crackstreams','sportsurge','cricfree',
]

def is_piracy_domain(url: str) -> bool:
    """Check if URL belongs to a known piracy domain."""
    domain = urlparse(url).netloc.lower()
    return any(p in domain for p in PIRACY_DOMAINS)

async def find_mirrors(client, domain: str, title: str, serp_key: str) -> list:
    """Find actual mirror/alternative piracy sites."""
    mirrors = []
    try:
        # Extract base name from domain for searching
        base = domain.split('.')[0].lower()
        queries = [
            f'{base} mirror alternative proxy new domain 2025',
            f'"{title}" download "{base}" OR "{base}2" OR "{base}3"',
        ]
        for q in queries[:2]:
            r = await client.get("https://serpapi.com/search", params={
                "q": q, "api_key": serp_key, "num": 10, "engine": "google"
            }, timeout=10)
            for item in r.json().get("organic_results", []):
                link = item.get("link","")
                if not link or domain in link:
                    continue
                # Only accept actual piracy domains
                if is_piracy_domain(link):
                    mirrors.append(link)
    except:
        pass
    return list(set(mirrors))[:5]

async def find_telegram_channels(client, title: str, serp_key: str) -> list:
    """Find Telegram channels sharing content."""
    channels = []
    try:
        r = await client.get("https://serpapi.com/search", params={
            "q": f'"{title}" telegram channel t.me stream download',
            "api_key": serp_key, "num": 10, "engine": "google"
        }, timeout=10)
        for item in r.json().get("organic_results", []):
            link = item.get("link","")
            snippet = item.get("snippet","")
            # Find t.me links
            tg = re.findall(r't\.me/(\w+)', link + snippet)
            channels.extend([f"https://t.me/{c}" for c in tg if len(c) > 3])
    except:
        pass
    return list(set(channels))[:5]

async def get_cdn_info(client, domain: str) -> dict:
    """Get CDN/hosting info from public DNS data."""
    info = {'cdn': 'unknown', 'ip': '', 'registrar': ''}
    try:
        # DNS lookup
        r = await client.get(f"https://dns.google/resolve?name={domain}&type=A", 
                            timeout=8)
        data = r.json()
        answers = data.get("Answer", [])
        if answers:
            ip = answers[0].get("data","")
            info['ip'] = ip
            
            # Identify CDN from IP ranges
            if ip.startswith('104.') or ip.startswith('172.64.') or ip.startswith('162.158.'):
                info['cdn'] = 'Cloudflare'
            elif ip.startswith('151.101.') or ip.startswith('199.232.'):
                info['cdn'] = 'Fastly'
            elif ip.startswith('13.') or ip.startswith('52.') or ip.startswith('54.'):
                info['cdn'] = 'Amazon AWS'
            elif ip.startswith('104.21.') or ip.startswith('172.67.'):
                info['cdn'] = 'Cloudflare Pages'
    except:
        pass
    
    try:
        # WHOIS via public API
        r = await client.get(f"https://rdap.org/domain/{domain}", timeout=8)
        data = r.json()
        entities = data.get("entities", [])
        for e in entities:
            roles = e.get("roles", [])
            if "registrar" in roles:
                vcard = e.get("vcardArray", [[]])[1]
                for field in vcard:
                    if field[0] == "fn":
                        info['registrar'] = field[3][:40]
    except:
        pass
    
    return info

async def find_social_clips(client, title: str, serp_key: str) -> list:
    """Find social media clips of pirated content."""
    clips = []
    try:
        r = await client.get("https://serpapi.com/search", params={
            "q": f'"{title}" full movie site:youtube.com OR site:dailymotion.com OR site:vimeo.com',
            "api_key": serp_key, "num": 5, "engine": "google"
        }, timeout=10)
        for item in r.json().get("organic_results", []):
            link = item.get("link","")
            if any(s in link for s in ['youtube.com','dailymotion.com','vimeo.com']):
                clips.append(link)
    except:
        pass
    return clips[:3]

async def find_resellers(client, domain: str, title: str, serp_key: str) -> list:
    """Find resellers/IPTV services using public search."""
    resellers = []
    try:
        r = await client.get("https://serpapi.com/search", params={
            "q": f'"{title}" IPTV subscription buy channel list',
            "api_key": serp_key, "num": 5, "engine": "google"
        }, timeout=10)
        for item in r.json().get("organic_results", []):
            link = item.get("link","")
            t = item.get("title","").lower()
            if any(w in t for w in ['iptv','subscription','buy','resell','panel']):
                resellers.append(link)
    except:
        pass
    return resellers[:3]

# ── MAIN GRAPH BUILDER ────────────────────────────────────

async def build_piracy_graph(
    seed_url: str,
    title: str,
    serp_key: str,
    depth: int = 2
) -> PiracyGraph:
    """
    Build complete piracy network graph from a seed URL.
    Automatically discovers mirrors, Telegram, CDN, resellers.
    """
    print(f"\n[CINEOS-GRAPH] Building piracy graph")
    print(f"  Seed: {seed_url}")
    print(f"  Title: {title}")
    print(f"  Depth: {depth}")
    
    graph = PiracyGraph()
    start = datetime.datetime.now()
    
    # Add seed node
    seed = PiracyNode(seed_url, 'source', title)
    graph.add_node(seed)
    
    async with httpx.AsyncClient(
        timeout=15,
        headers={"User-Agent":"Mozilla/5.0"},
        follow_redirects=True
    ) as client:
        
        domain = urlparse(seed_url).netloc.replace('www.','')
        
        print(f"\n[CINEOS-GRAPH] Layer 1: Direct discovery from {domain}")
        
        # Run all discoveries concurrently
        tasks = await asyncio.gather(
            find_mirrors(client, domain, title, serp_key),
            find_telegram_channels(client, title, serp_key),
            get_cdn_info(client, domain),
            find_social_clips(client, title, serp_key),
            find_resellers(client, domain, title, serp_key),
            return_exceptions=True
        )
        
        mirrors, tg_channels, cdn_info, social_clips, resellers = tasks
        
        # Add mirror nodes
        if isinstance(mirrors, list):
            for m in mirrors:
                node = PiracyNode(m, 'mirror', parent=seed_url)
                graph.add_node(node)
                seed.children.append(node)
                print(f"  MIRROR: {m[:60]}")
        
        # Add Telegram nodes
        if isinstance(tg_channels, list):
            for ch in tg_channels:
                node = PiracyNode(ch, 'telegram', parent=seed_url)
                graph.add_node(node)
                seed.children.append(node)
                print(f"  TELEGRAM: {ch}")
        
        # Add CDN node
        if isinstance(cdn_info, dict) and cdn_info.get('cdn') != 'unknown':
            cdn_url = f"cdn://{cdn_info['cdn']}/{cdn_info['ip']}"
            node = PiracyNode(cdn_url, 'cdn', 
                            title=f"{cdn_info['cdn']} ({cdn_info['registrar']})",
                            parent=seed_url)
            graph.add_node(node)
            print(f"  CDN: {cdn_info['cdn']} | IP: {cdn_info['ip']}")
        
        # Add social clips
        if isinstance(social_clips, list):
            for clip in social_clips:
                node = PiracyNode(clip, 'social', parent=seed_url)
                graph.add_node(node)
                print(f"  SOCIAL: {clip[:60]}")
        
        # Add resellers
        if isinstance(resellers, list):
            for res in resellers:
                node = PiracyNode(res, 'reseller', parent=seed_url)
                graph.add_node(node)
                print(f"  RESELLER: {res[:60]}")
        
        # Layer 2 — discover from mirrors
        if depth >= 2 and isinstance(mirrors, list):
            print(f"\n[CINEOS-GRAPH] Layer 2: Expanding from {len(mirrors)} mirrors")
            for mirror in mirrors[:2]:
                m_domain = urlparse(mirror).netloc.replace('www.','')
                m_cdn = await get_cdn_info(client, m_domain)
                if m_cdn.get('cdn') != 'unknown':
                    cdn_url = f"cdn://{m_cdn['cdn']}/{m_cdn['ip']}"
                    if cdn_url not in graph.nodes:
                        node = PiracyNode(cdn_url, 'cdn',
                                        title=m_cdn['cdn'], parent=mirror)
                        graph.add_node(node)
                        print(f"  Mirror CDN: {m_cdn['cdn']}")
    
    elapsed = (datetime.datetime.now() - start).total_seconds()
    report = graph.to_report()
    report['title'] = title
    report['seed_url'] = seed_url
    report['scan_time'] = round(elapsed, 1)
    
    return graph, report

# ── PRINT REPORT ──────────────────────────────────────────
def print_graph_report(report: dict):
    print(f"\n{'='*65}")
    print(f"  CINEOS PIRACY NETWORK GRAPH — {report.get('title','')}")
    print(f"{'='*65}")
    print(f"  Seed URL    : {report.get('seed_url','')[:50]}")
    print(f"  Scan time   : {report.get('scan_time',0)}s")
    print(f"  Total nodes : {report['total_nodes']}")
    print()
    print(f"  BY TYPE:")
    for t, count in report['by_type'].items():
        if count:
            icon = NODE_TYPES[t]['icon']
            print(f"    {icon} {t:12}: {count}")
    print()
    print(f"  NETWORK NODES:")
    for node in report['nodes']:
        icon = NODE_TYPES.get(node['type'],{}).get('icon','•')
        subs = f" ({node['subscribers']:,} subs)" if node['subscribers'] else ""
        print(f"  {icon} [{node['type']:10}] {node['url'][:55]}{subs}")
    print(f"{'='*65}")

if __name__ == '__main__':
    import argparse, os
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True, help='Seed piracy URL')
    ap.add_argument('--title', required=True, help='Content title')
    ap.add_argument('--depth', type=int, default=2)
    args = ap.parse_args()
    
    serp_key = os.environ.get('SERP_API_KEY','')
    if not serp_key:
        print("ERROR: Set SERP_API_KEY environment variable")
        exit(1)
    
    graph, report = asyncio.run(build_piracy_graph(
        args.url, args.title, serp_key, args.depth
    ))
    print_graph_report(report)
    
    # Save report
    os.makedirs('reports', exist_ok=True)
    path = f"reports/piracy_graph_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nGraph saved: {path}")
