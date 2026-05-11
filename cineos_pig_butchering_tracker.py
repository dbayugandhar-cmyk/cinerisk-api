"""
CINEOS Pig Butchering End-to-End Tracker

THE BREAKTHROUGH NOBODY HAS BUILT FOR INDIA:

Step 1: Scan Telegram investment fraud channels
Step 2: Extract every URL/domain posted in messages
Step 3: Run WHOIS on each domain
Step 4: Cross-reference: same registrant = same operator
Step 5: Build: Channel → Fake Platform → Registrant → Network

This maps the ENTIRE pig butchering operation:
  Who recruited (Telegram channel)
  Where they sent victims (fake trading platform)
  Who registered the platform (WHOIS)
  What other platforms they run (same registrant)

Nobody has this end-to-end chain for India.
Not CloudSEK. Not Cyble. Not Group-IB India.
"""
import asyncio, json, os, re, hashlib, subprocess
from datetime import datetime
from collections import defaultdict
from telethon import TelegramClient
from telethon.errors import FloodWaitError

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

# Known pig butchering entry patterns
PIG_BUTCHERING_SIGNALS = [
    # Investment promises
    'guaranteed return', 'daily profit', 'sure profit',
    'trading profit', 'investment profit', 'earn daily',
    '100% profit', 'guaranteed income', 'passive income',
    # Platform promotion
    'join our platform', 'trading platform', 'investment app',
    'download app', 'register now', 'sign up now',
    # Trust building
    'my mentor', 'expert trader', 'successful trader',
    'i made profit', 'withdrawal proof', 'payment proof',
    # Crypto signals
    'usdt', 'crypto profit', 'bitcoin earn',
    'crypto investment', 'defi earn', 'yield farming',
    # Hindi signals
    'paisa kamao', 'daily earning', 'ghar baithe earn',
    'investment se kamao', 'trading se profit',
]

# Fake platform domain patterns
FAKE_PLATFORM_PATTERNS = [
    # Trading platform keywords
    r'https?://[^\s]+(?:trade|trading|invest|profit|earn|capital|fund|wealth|finance|forex|crypto|bitcoin|usdt)[^\s]*',
    # Short domains with trade-like names
    r'https?://(?:www\.)?[a-z]{4,15}(?:trade|fx|pro|cap|inv|earn)[^\s/]*\.[a-z]{2,6}',
    # App download links (not Play Store/App Store)
    r'https?://[^\s]+\.apk',
    r'https?://[^\s]+/download[^\s]*',
]

def extract_domains(text):
    """Extract all domains from text."""
    domains = set()

    # Standard URLs
    urls = re.findall(
        r'https?://([A-Za-z0-9.\-]+)', text)
    for url in urls:
        domain = url.lower().strip('.')
        # Skip known legitimate platforms
        skip = ['telegram', 't.me', 'whatsapp', 'youtube',
                'google', 'instagram', 'facebook', 'twitter',
                'sebi.gov', 'rbi.org', 'wikipedia', 'amazon',
                'flipkart', 'zerodha', 'groww', 'nseindia']
        if not any(s in domain for s in skip):
            domains.add(domain)

    # Domains without https
    bare = re.findall(
        r'\b([a-z]{3,20}(?:trade|fx|pro|capital|invest|earn|profit)'
        r'[a-z]{0,10}\.[a-z]{2,6})\b',
        text.lower())
    domains.update(bare)

    return domains

async def scan_investment_channels():
    """
    Scan investment fraud channels for fake platform URLs.
    """
    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()

    # Load our investment fraud channels
    all_channels = json.load(open('reports/all_channels.json'))
    investment_channels = [
        c for c in all_channels
        if c.get('category') in
        ['investment_fraud', 'crypto', 'task_fraud']
        or any(k in str(c).lower() for k in
               ['sebi', 'tip', 'invest', 'profit', 'crypto',
                'signal', 'trading', 'earn', 'stock', 'option'])
    ]

    print(f"  Investment fraud channels to scan: "
          f"{len(investment_channels)}")

    all_domains   = defaultdict(list)  # domain → channels
    channel_data  = {}
    total_messages = 0

    for ch in investment_channels[:30]:  # rate limit safe
        username = ch.get('username','')
        if not username:
            continue

        try:
            entity   = await client.get_entity(username)
            messages = await client.get_messages(entity, limit=200)
            all_text = '\n'.join(
                m.text for m in messages if m.text)
            total_messages += len(messages)

            # Extract domains
            domains = extract_domains(all_text)

            # Extract pig butchering signals
            signals = [s for s in PIG_BUTCHERING_SIGNALS
                      if s in all_text.lower()]

            # Extract phones and UPIs
            phones = list(set(
                p[-10:] for p in
                re.findall(r'(?:\+91|91)?([6-9]\d{9})',
                           all_text)))
            upis = list(set(re.findall(
                r'[\w.\-+]{3,}@(?:okaxis|okicici|paytm|gpay|'
                r'phonepe|ybl|upi|sbi|hdfc|icici|kotak)',
                all_text, re.I)))

            channel_data[username] = {
                'username':  username,
                'title':     ch.get('title',''),
                'subs':      ch.get('subscribers',0),
                'domains':   list(domains),
                'signals':   signals[:5],
                'phones':    phones,
                'upis':      upis,
                'msg_count': len(messages),
            }

            # Map domains to channels
            for domain in domains:
                all_domains[domain].append(username)

            if domains or signals:
                subs = ch.get('subscribers',0)
                print(f"  @{username[:30]:30} "
                      f"subs:{subs:6,} | "
                      f"domains:{len(domains):3} | "
                      f"signals:{len(signals)}")

            await asyncio.sleep(5)

        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds, 60))
        except Exception:
            await asyncio.sleep(3)

    await client.disconnect()
    return all_domains, channel_data, total_messages

def run_whois_on_domains(domains):
    """
    Run WHOIS on every extracted domain.
    Build registrant → multiple domains map.
    Same registrant = same operator.
    """
    print(f"\n  Running WHOIS on {len(domains)} domains...")

    whois_results  = {}
    registrant_map = defaultdict(list)  # registrant → domains
    email_map      = defaultdict(list)  # email → domains

    for domain in list(domains)[:50]:  # top 50
        try:
            result = subprocess.run(
                ['whois', domain],
                capture_output=True, text=True, timeout=10)
            raw = result.stdout

            is_live = any(x in raw.lower() for x in
                         ['registrar:','creation date:',
                          'domain status:'])

            if not is_live:
                continue

            # Extract fields
            def extract(pattern):
                m = re.search(pattern, raw, re.I | re.M)
                return m.group(1).strip() if m else ''

            registrant = extract(r'Registrant Name:\s*(.+)')
            reg_email  = extract(r'Registrant Email:\s*(.+)')
            reg_country= extract(r'Registrant Country:\s*(.+)')
            created    = extract(r'Creation Date:\s*(.+)')
            registrar  = extract(r'Registrar:\s*(.+)')

            # Privacy check
            is_hidden = any(k in registrant.lower() for k in
                           ['privacy','redacted','protected',
                            'whoisguard','proxy'])

            # Recent registration check
            is_recent = any(yr in str(created) for yr in
                           ['2024','2025','2026'])

            whois_results[domain] = {
                'domain':      domain,
                'live':        True,
                'registrant':  registrant,
                'email':       reg_email,
                'country':     reg_country,
                'created':     created[:20],
                'registrar':   registrar,
                'is_hidden':   is_hidden,
                'is_recent':   is_recent,
                'risk':       ('CRITICAL' if is_recent
                               and not is_hidden
                               else 'HIGH' if is_recent
                               else 'MEDIUM'),
            }

            # Map registrant to domains
            if registrant and not is_hidden:
                registrant_map[registrant].append(domain)
            if reg_email and 'privacy' not in reg_email.lower():
                email_map[reg_email].append(domain)

            status = ('NAMED' if not is_hidden
                     else 'HIDDEN')
            recent = '← RECENT' if is_recent else ''
            print(f"  ✓ {domain[:35]:35} "
                  f"{status:6} {reg_country:5} "
                  f"{recent}")

        except Exception:
            pass

    # Find operators running multiple platforms
    # Same registrant + multiple fake trading domains = syndicate
    syndicates = {
        r: domains for r, domains in registrant_map.items()
        if len(domains) >= 2
    }
    email_syndicates = {
        e: domains for e, domains in email_map.items()
        if len(domains) >= 2
    }

    if syndicates:
        print(f"\n  SYNDICATES — same registrant, multiple platforms:")
        for registrant, domains in syndicates.items():
            print(f"  → {registrant}")
            for d in domains:
                print(f"    • {d}")

    if email_syndicates:
        print(f"\n  EMAIL SYNDICATES:")
        for email, domains in email_syndicates.items():
            print(f"  → {email}")
            for d in domains:
                print(f"    • {d}")

    return whois_results, syndicates, email_syndicates

async def main():
    print("="*60)
    print("  CINEOS PIG BUTCHERING END-TO-END TRACKER")
    print("  Channel → Platform → Registrant → Network")
    print("  What nobody has built for India")
    print("="*60)

    # Step 1: Scan channels for fake platform URLs
    print("\n[STEP 1] Scanning investment fraud channels...")
    all_domains, channel_data, total_msg = \
        await scan_investment_channels()

    print(f"\n  Messages scanned:  {total_msg}")
    print(f"  Unique domains:    {len(all_domains)}")
    print(f"  Channels with URLs:{len([c for c in channel_data.values() if c['domains']])}")

    # Step 2: WHOIS on every domain
    print(f"\n[STEP 2] WHOIS attribution on extracted domains...")
    whois_data, syndicates, email_syndicates = \
        run_whois_on_domains(set(all_domains.keys()))

    live_domains = [d for d,v in whois_data.items()
                    if v.get('live')]
    named        = [d for d,v in whois_data.items()
                    if not v.get('is_hidden') and v.get('live')]
    recent       = [d for d,v in whois_data.items()
                    if v.get('is_recent') and v.get('live')]

    # Step 3: Build end-to-end chain
    print(f"\n[STEP 3] Building end-to-end attribution chain...")

    chains = []
    for domain, channels in all_domains.items():
        whois = whois_data.get(domain, {})
        if not whois.get('live'):
            continue

        chain = {
            'fake_platform':    domain,
            'promoted_in':      channels,
            'registrant':       whois.get('registrant',''),
            'email':            whois.get('email',''),
            'country':          whois.get('country',''),
            'registered':       whois.get('created',''),
            'registrar':        whois.get('registrar',''),
            'is_named':         not whois.get('is_hidden'),
            'is_recent':        whois.get('is_recent'),
            'other_platforms':  syndicates.get(
                                whois.get('registrant',''), []),
            'evidence_hash':    hashlib.sha256(
                                domain.encode()).hexdigest(),
        }
        chains.append(chain)

    # Step 4: Save complete intelligence
    os.makedirs('reports', exist_ok=True)
    report = {
        'generated_at':    datetime.now().isoformat(),
        'classification':  'INTERNAL — End-to-end pig butchering intelligence',
        'methodology':     (
            'Telegram channel scan → URL extraction → '
            'WHOIS attribution → Registrant network mapping. '
            'All public data. IT Act 65B compliant.'
        ),
        'what_this_is': (
            'India\'s first end-to-end pig butchering '
            'intelligence chain. Maps from Telegram recruitment '
            'channel to fake trading platform to operator identity. '
            'Nobody has built this for India.'
        ),
        'stats': {
            'channels_scanned':      len(channel_data),
            'messages_read':         total_msg,
            'domains_extracted':     len(all_domains),
            'domains_whois_checked': len(whois_data),
            'domains_live':          len(live_domains),
            'domains_named':         len(named),
            'domains_recent':        len(recent),
            'syndicates_found':      len(syndicates),
            'complete_chains':       len(chains),
        },
        'channel_data':      channel_data,
        'domain_map':        dict(all_domains),
        'whois_results':     whois_data,
        'syndicates':        dict(syndicates),
        'email_syndicates':  dict(email_syndicates),
        'complete_chains':   chains,
    }

    json.dump(report,
              open('reports/pig_butchering_intelligence.json','w'),
              indent=2, default=str)

    # Final summary
    print(f"\n{'='*60}")
    print(f"  PIG BUTCHERING TRACKER — RESULTS")
    print(f"{'='*60}")
    print(f"""
  WHAT WAS BUILT:
  Channels scanned:      {len(channel_data)}
  Messages read:         {total_msg}
  Fake platform domains: {len(all_domains)}
  WHOIS checked:         {len(whois_data)}
  Live domains:          {len(live_domains)}
  Named registrants:     {len(named)}
  Recent registrations:  {len(recent)}
  Operator syndicates:   {len(syndicates)}
  Complete chains:       {len(chains)}

  WHAT THIS PROVES:
  For every named registrant with multiple domains:
  → One person/entity running multiple fake platforms
  → All promoted through specific Telegram channels
  → End-to-end chain: recruiter → platform → operator

  WHAT NOBODY ELSE HAS FOR INDIA:
  Global firms find fake platforms after deployment.
  CINEOS finds the Telegram channel that promotes it
  AND the domain AND the registrant AND the network.
  That is source-to-operator. End to end.

  WHO PAYS FOR THIS:
  SEBI:   Every fake trading platform is SEBI violation
  I4C:    Operator attribution for FIR filing
  Banks:  UPI drain chains for account flagging
  MHA:    Complete pig butchering network map

  INTERNAL ONLY — share under signed agreement.
  Saved: reports/pig_butchering_intelligence.json
""")

asyncio.run(main())
