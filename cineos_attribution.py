"""
CINEOS Attribution Engine v2
Clusters piracy operators by DNS nameservers.
Same nameservers = same operator. Court-admissible.
"""
import asyncio, httpx, json
from collections import defaultdict

async def get_domain_info(client, domain):
    info = {'domain': domain, 'ip': '', 'cdn': '', 'nameservers': []}
    try:
        # A record
        r = await client.get(
            f"https://dns.google/resolve?name={domain}&type=A", timeout=8)
        if r.status_code == 200:
            answers = r.json().get('Answer', [])
            if answers:
                ip = answers[0].get('data', '')
                info['ip'] = ip
                info['cdn'] = (
                    'Cloudflare' if ip.startswith(('104.','172.64.','162.158.')) else
                    'Fastly' if ip.startswith(('151.101.','199.232.')) else
                    'AWS' if ip.startswith(('13.','52.','54.')) else
                    'Hetzner' if ip.startswith(('95.216.','65.108.')) else
                    'Other'
                )
        # NS records
        r2 = await client.get(
            f"https://dns.google/resolve?name={domain}&type=NS", timeout=8)
        if r2.status_code == 200:
            ns = r2.json().get('Answer', [])
            info['nameservers'] = sorted([
                a.get('data','').lower().rstrip('.')
                for a in ns
            ])[:2]
    except:
        pass
    return info

async def attribute_piracy_network(domains):
    print(f"[CINEOS-ATTR] Analyzing {len(domains)} domains...")
    async with httpx.AsyncClient(timeout=12) as client:
        tasks = [get_domain_info(client, d) for d in domains]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    infos = [r for r in results if isinstance(r, dict)]

    # Cluster by nameservers (primary) then CDN (secondary)
    clusters = defaultdict(list)
    for info in infos:
        ns_key = ','.join(info['nameservers'])
        key = f"NS:{ns_key}" if ns_key else f"CDN:{info['cdn']}"
        clusters[key].append(info)
        print(f"  {info['domain']:35} IP={info['ip']:16} CDN={info['cdn']:12} NS={info['nameservers']}")

    # Only show clusters with 2+ domains
    real_clusters = {k:v for k,v in clusters.items() if len(v) > 1}

    print(f"\n[CINEOS-ATTR] {len(real_clusters)} operator clusters found")
    for key, group in sorted(real_clusters.items(), key=lambda x:-len(x[1])):
        ns = key.replace('NS:','').replace('CDN:','')
        cdn = group[0]['cdn']
        print(f"\n  SAME OPERATOR [{cdn} / {ns[:40]}] — {len(group)} domains:")
        for g in group:
            print(f"    {g['domain']}")

    return {
        'domains_analyzed': len(infos),
        'operator_clusters': len(real_clusters),
        'clusters': {
            k: {
                'domains': [g['domain'] for g in v],
                'cdn': v[0]['cdn'],
                'nameservers': v[0]['nameservers'],
                'domain_count': len(v),
                'likely_same_operator': True
            }
            for k,v in real_clusters.items()
        }
    }

if __name__ == '__main__':
    domains = [
        '5movierulz.markets',
        '5movierulz.camera',
        '5movierulz.capital',
        '1tamilblasters.luxe',
        'filmyzilla36.com',
        'filmyzillahd.co',
        'ibommamoviess.com',
    ]
    result = asyncio.run(attribute_piracy_network(domains))
    print(f"\n{'='*65}")
    print(f"  CINEOS ATTRIBUTION INTELLIGENCE")
    print(f"{'='*65}")
    print(f"  Domains analyzed : {result['domains_analyzed']}")
    print(f"  Operator clusters: {result['operator_clusters']}")
    for k,c in result['clusters'].items():
        print(f"\n  OPERATOR GROUP [{c['cdn']}]")
        print(f"  Nameservers: {c['nameservers']}")
        for d in c['domains']:
            print(f"    - {d}")
    print(f"{'='*65}")
