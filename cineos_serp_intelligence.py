"""
CINEOS SerpApi Intelligence Expander
Uses SerpApi to discover new fraud channels, sellers,
and network connections across the public web.

Three jobs:
1. Discover new Telegram channels not yet in database
2. Enrich existing channels with web presence data
3. Find operator footprints across platforms
"""
import asyncio, httpx, json, os, re
from datetime import datetime
from collections import defaultdict

SERP_KEY = os.environ.get('SERP_API_KEY','')

async def serp_search(client, query, engine='google',
                      num=10, gl='in', tbs=None):
    params = {
        'engine':  engine,
        'q':       query,
        'api_key': SERP_KEY,
        'num':     num,
        'gl':      gl,
    }
    if tbs:
        params['tbs'] = tbs
    try:
        r = await client.get(
            'https://serpapi.com/search',
            params=params)
        return r.json().get('organic_results', [])
    except:
        return []

async def expand_channel_database():
    """
    Find new Telegram fraud channels via web search.
    Looks for channels being discussed, warned about,
    or promoted across the public web.
    """
    print("\n[1/3] Expanding channel database via SerpApi...")

    # Load existing
    existing = json.load(open('reports/all_channels.json'))
    known    = {c.get('username','').lower() for c in existing}
    print(f"  Existing: {len(known)} channels")

    new_channels = []
    DISCOVERY_QUERIES = [
        # Channels being warned about
        'telegram channel india fraud warning 2026',
        'telegram satta matka channel india exposed',
        'fake zerodha telegram channel india',
        'illegal betting telegram india channel list',
        'telegram piracy channel india tamilrockers',
        # Channels being promoted (we find to monitor)
        'join telegram channel ipl betting india',
        'best telegram channel stock tips india free',
        'telegram crypto signal india channel link',
        'telegram earn money daily india channel',
        # Regional language searches
        'टेलीग्राम सट्टा चैनल भारत',
        'telegram channel india satta matka join',
        'telugu betting tips telegram channel',
        'tamil movies download telegram channel',
        # New fraud types
        'telegram digital arrest fraud india channel',
        'telegram colour prediction india bigdaddy',
        'telegram pig butchering india fraud channel',
        'fake medicine telegram channel india',
        'loan app fraud telegram india channel',
        # Network-specific searches
        'reddy anna book telegram channels list india',
        'mahadev book telegram channel india new',
        'fair786 telegram agent channels india',
        'lotusbook telegram channel india new 2026',
        'skyexchange telegram channel india',
    ]

    async with httpx.AsyncClient(timeout=15) as client:
        for query in DISCOVERY_QUERIES:
            results = await serp_search(client, query)
            for item in results:
                url     = item.get('link','')
                title   = item.get('title','')
                snippet = item.get('snippet','')
                combined = (title + ' ' + snippet).lower()

                # Extract Telegram usernames from results
                usernames = re.findall(
                    r't\.me/([A-Za-z0-9_]{5,})',
                    url + ' ' + snippet)
                usernames += re.findall(
                    r'@([A-Za-z0-9_]{5,})',
                    snippet)

                for username in usernames:
                    if username.lower() not in known:
                        # Quick fraud check
                        is_fraud = any(k in combined for k in [
                            'fraud','scam','fake','illegal','betting',
                            'satta','matka','piracy','warned','exposed',
                            'pump','signal','earn','task','loan','crime'
                        ])
                        new_channels.append({
                            'username':      username,
                            'title':         '',
                            'subscribers':   0,
                            'discovered_by': query,
                            'discovered_via':'serpapi_web',
                            'source_url':    url[:100],
                            'fraud_signal':  is_fraud,
                            'discovered_at': datetime.now().isoformat(),
                        })
                        known.add(username.lower())

            await asyncio.sleep(0.5)

    print(f"  New channels discovered: {len(new_channels)}")

    # Add to database
    if new_channels:
        existing.extend(new_channels)
        json.dump(existing,
                  open('reports/all_channels.json','w'),
                  indent=2, default=str)
        print(f"  Total database: {len(existing)}")

    return new_channels


async def enrich_operator_footprints():
    """
    For each known operator phone/network,
    search web for their footprint across platforms.
    Builds richer attribution data.
    """
    print("\n[2/3] Enriching operator footprints...")

    # Known operators from attribution
    OPERATORS = [
        {
            'id':      'BCCI_IMPERSONATOR',
            'phones':  ['8306154335','9216328940'],
            'channels':['BCCI_MATCH_TOSS_FIXER0'],
            'queries': [
                '"8306154335" telegram fraud india',
                '"9216328940" telegram betting india',
                'BCCI_MATCH_TOSS_FIXER telegram',
            ]
        },
        {
            'id':      'MURUGAN_NETWORK',
            'channels':['MURUGAN_FIXER_LONDON1'],
            'queries': [
                'MURUGAN_FIXER_LONDON telegram india',
                'play99 betting telegram india',
                'playgames9999 telegram fraud',
            ]
        },
        {
            'id':      'MAHADEV_NETWORK',
            'channels':['CRYPTO_book_lotus365_nitinnj'],
            'queries': [
                'mahadev book telegram fraud india 2026',
                'mahadev book ed case india',
                'mahadev book operator arrested india',
            ]
        },
        {
            'id':      'REDDY_ANNA_NETWORK',
            'channels':['Anuragt_bookqc_Malikc','News_Crypto5'],
            'queries': [
                'reddy anna book fraud india telegram',
                'reddy anna book arrested india 2026',
                'reddy anna book operator identity',
            ]
        },
    ]

    footprints = {}
    async with httpx.AsyncClient(timeout=15) as client:
        for op in OPERATORS:
            op_footprint = {
                'id':        op['id'],
                'web_mentions': [],
                'news':      [],
                'platforms': [],
            }

            for query in op.get('queries', []):
                results = await serp_search(
                    client, query, num=10)

                for item in results:
                    title   = item.get('title','')
                    url     = item.get('link','')
                    snippet = item.get('snippet','')

                    # Classify result
                    if any(d in url for d in
                           ['ndtv','timesofindia','hindustantimes',
                            'indianexpress','thehindu','livemint',
                            'economictimes','businessstandard']):
                        op_footprint['news'].append({
                            'title':   title,
                            'url':     url,
                            'snippet': snippet[:100],
                        })
                    elif 't.me' in url or 'telegram' in url.lower():
                        op_footprint['platforms'].append({
                            'platform': 'telegram',
                            'url':      url,
                            'title':    title,
                        })
                    else:
                        op_footprint['web_mentions'].append({
                            'title':   title,
                            'url':     url,
                            'snippet': snippet[:100],
                        })

                await asyncio.sleep(0.5)

            footprints[op['id']] = op_footprint

            news_count = len(op_footprint['news'])
            web_count  = len(op_footprint['web_mentions'])
            print(f"  {op['id']:30} "
                  f"news:{news_count:3} web:{web_count:3}")

    json.dump(footprints,
              open('reports/operator_footprints.json','w'),
              indent=2)
    return footprints


async def build_graph_enrichment():
    """
    Use SerpApi to find connections between known entities.
    Discovers edges the Telegram scanner missed.
    """
    print("\n[3/3] Building graph enrichment data...")

    NETWORKS = [
        'Reddy Anna Book', 'Mahadev Book', 'Fair786',
        'Lotus365', 'BigDaddy', 'Yaarwin', 'Play99',
        'Tiger365', 'Betbhai9', 'Laser247',
    ]

    enrichment = defaultdict(list)

    async with httpx.AsyncClient(timeout=15) as client:
        for network in NETWORKS:
            # Find connections between networks
            query = (f'"{network}" india telegram fraud '
                     f'connected affiliate agent 2026')
            results = await serp_search(client, query, num=10)

            connected_networks = []
            for item in results:
                text = (item.get('title','') + ' ' +
                        item.get('snippet','')).lower()

                # Find other network names mentioned
                for other in NETWORKS:
                    if (other.lower() in text and
                            other != network):
                        connected_networks.append(other)

                # Find phone numbers mentioned
                phones = re.findall(
                    r'(?:\+91|91)?([6-9]\d{9})', text)
                for p in phones:
                    if len(p) == 10:
                        enrichment[f'phone_{p}'].append({
                            'found_via':  network,
                            'source':     item.get('link',''),
                        })

                # Find Telegram usernames
                usernames = re.findall(
                    r't\.me/([A-Za-z0-9_]{5,})', text)
                for u in usernames:
                    enrichment[f'channel_{u}'].append({
                        'connected_to': network,
                        'source':       item.get('link',''),
                    })

            if connected_networks:
                unique_conn = list(set(connected_networks))
                print(f"  {network:20} ↔ {unique_conn}")
                enrichment[f'network_{network}'] = unique_conn

            await asyncio.sleep(0.5)

    # Save enrichment
    json.dump(dict(enrichment),
              open('reports/graph_enrichment.json','w'),
              indent=2)

    new_phones = [k for k in enrichment if k.startswith('phone_')]
    new_chans  = [k for k in enrichment if k.startswith('channel_')]
    networks   = [k for k in enrichment if k.startswith('network_')]

    print(f"\n  New phones found:    {len(new_phones)}")
    print(f"  New channels found:  {len(new_chans)}")
    print(f"  Network connections: {len(networks)}")
    return dict(enrichment)


async def main():
    print("="*60)
    print("  CINEOS SERPAPI INTELLIGENCE EXPANDER")
    print("  Building data advantage via web intelligence")
    print("="*60)

    new_channels = await expand_channel_database()
    footprints   = await enrich_operator_footprints()
    enrichment   = await build_graph_enrichment()

    # Update intelligence graph with new data
    print("\n[Updating intelligence graph...]")
    os.system('python3 cineos_intelligence_graph.py 2>/dev/null')

    print(f"\n{'='*60}")
    print(f"  SERPAPI INTELLIGENCE RUN COMPLETE")
    print(f"{'='*60}")
    print(f"  New channels discovered: {len(new_channels)}")
    print(f"  Operators footprinted:   {len(footprints)}")
    print(f"  Graph enrichment items:  {len(enrichment)}")
    print(f"")
    print(f"  DATA ADVANTAGE BUILDING:")
    print(f"  Every SerpApi run adds new channels to database")
    print(f"  Every run enriches operator profiles")
    print(f"  Every run finds new network connections")
    print(f"  Run daily = compound data advantage")
    print(f"")
    print(f"  Added to daily scanner — runs 8am automatically")

asyncio.run(main())
