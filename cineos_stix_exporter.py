"""
CINEOS STIX 2.1 Threat Intelligence Exporter
STIX = Structured Threat Intelligence eXpression
Global standard used by Group-IB, ZeroFox, Recorded Future.
When they ask 'do you support STIX?' — the answer is YES.

Run: python3 cineos_stix_exporter.py
Output: reports/cineos_stix_bundle.json
"""
import json, uuid, os
from datetime import datetime, timezone

def now_stix():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')

def make_id(obj_type):
    return f"{obj_type}--{str(uuid.uuid4())}"

def build_stix_bundle():
    objects = []
    created = now_stix()

    # ── Identity object (CINEOS as the producer) ──────────
    cineos_id = make_id('identity')
    objects.append({
        'type':             'identity',
        'spec_version':     '2.1',
        'id':               cineos_id,
        'created':          created,
        'modified':         created,
        'name':             'CINEOS',
        'description':      "India's Trust Intelligence Network. US Provisional Patent 64/049,190.",
        'identity_class':   'organization',
        'sectors':          ['technology', 'financial-services'],
        'contact_information': 'yugandhar@cineos.in',
        'object_marking_refs': ['marking-definition--613f2e26-407d-48c7-9eca-b8e91ba4c5e5'],  # TLP:WHITE
    })

    # ── TLP:WHITE marking ─────────────────────────────────
    objects.append({
        'type':         'marking-definition',
        'spec_version': '2.1',
        'id':           'marking-definition--613f2e26-407d-48c7-9eca-b8e91ba4c5e5',
        'created':      '2017-01-20T00:00:00.000Z',
        'definition_type': 'tlp',
        'definition':   {'tlp': 'white'},
    })

    # ── Load CINEOS channel data ──────────────────────────
    try:
        channels = json.load(open('reports/all_channels.json'))
    except:
        channels = []

    # ── Load seller data ──────────────────────────────────
    try:
        sellers = json.load(open('reports/seller_auth_scores.json'))
        confirmed = [s for s in sellers if s.get('auth_score', 0) >= 75]
    except:
        confirmed = []

    # ── Convert top betting channels → Threat Actor objects ──
    betting = sorted(
        [c for c in channels if any(k in c.get('username','').lower()
          for k in ['satta','matka','bet','reddy','mahadev','ipl'])],
        key=lambda x: -x.get('subscribers', 0)
    )[:20]

    for ch in betting:
        actor_id = make_id('threat-actor')
        subs     = ch.get('subscribers', 0)
        subs_str = f"{subs/1000000:.1f}M" if subs >= 1000000 else f"{subs/1000:.0f}K"

        objects.append({
            'type':         'threat-actor',
            'spec_version': '2.1',
            'id':           actor_id,
            'created':      created,
            'modified':     created,
            'name':         f"@{ch['username']}",
            'description':  (f"India illegal betting/gambling channel. "
                             f"Subscribers: {subs_str}. "
                             f"Platform: Telegram. "
                             f"Discovered: {ch.get('discovered_at','')[:10]}"),
            'threat_actor_types': ['criminal'],
            'sophistication':     'minimal',
            'resource_level':     'individual',
            'primary_motivation': 'financial-gain',
            'aliases':            [ch.get('title', '')[:64]],
            'labels':             ['illegal-gambling', 'india', 'telegram'],
            'external_references': [{
                'source_name': 'CINEOS',
                'url':         f"https://t.me/{ch['username']}",
                'description': 'CINEOS India Intelligence — cineos.in',
            }],
            'created_by_ref': cineos_id,
            'object_marking_refs': ['marking-definition--613f2e26-407d-48c7-9eca-b8e91ba4c5e5'],
        })

    # ── Convert counterfeit sellers → Threat Actor objects ──
    for seller in confirmed[:10]:
        actor_id = make_id('threat-actor')
        objects.append({
            'type':         'threat-actor',
            'spec_version': '2.1',
            'id':           actor_id,
            'created':      created,
            'modified':     created,
            'name':         seller.get('company', 'Unknown Seller'),
            'description':  (f"Confirmed counterfeit seller on IndiaMART. "
                             f"Brand: {seller.get('brand','')}. "
                             f"City: {seller.get('city','')}. "
                             f"Risk score: {seller.get('auth_score',0)}/100. "
                             f"Verdict: {seller.get('verdict','')}"),
            'threat_actor_types': ['criminal'],
            'sophistication':     'minimal',
            'resource_level':     'individual',
            'primary_motivation': 'financial-gain',
            'labels':             ['counterfeit', 'indiamart', 'india', seller.get('brand','').lower()],
            'external_references': [{
                'source_name': 'CINEOS',
                'url':         seller.get('url', ''),
                'description': 'IndiaMART counterfeit listing — IT Act 65B compliant evidence',
            }],
            'created_by_ref': cineos_id,
            'object_marking_refs': ['marking-definition--613f2e26-407d-48c7-9eca-b8e91ba4c5e5'],
        })

    # ── Phone numbers → Indicator objects ─────────────────
    phones = ['+91-8441916068', '+91-6378542162', '+91-8696206466', '+91-9911919102']
    phone_channels = {
        '+91-8441916068': ['@IPLBetting', '@ipltossmatchsessionn'],
        '+91-6378542162': ['@Satta_khaiwal_gali_dishwar'],
        '+91-8696206466': ['Deep scan attribution'],
        '+91-9911919102': ['Deep scan attribution'],
    }

    for phone in phones:
        indicator_id = make_id('indicator')
        objects.append({
            'type':             'indicator',
            'spec_version':     '2.1',
            'id':               indicator_id,
            'created':          created,
            'modified':         created,
            'name':             f"India fraud operator phone: {phone}",
            'description':      (f"Phone number attributed to India fraud channels: "
                                 f"{', '.join(phone_channels.get(phone, []))}"),
            'indicator_types':  ['malicious-activity'],
            'pattern':          f"[phone-number:value = '{phone}']",
            'pattern_type':     'stix',
            'valid_from':       created,
            'labels':           ['fraud', 'india', 'telegram', 'phone-attribution'],
            'created_by_ref':   cineos_id,
            'object_marking_refs': ['marking-definition--613f2e26-407d-48c7-9eca-b8e91ba4c5e5'],
        })

    # ── Digital arrest fraud → Campaign object ─────────────
    campaign_id = make_id('campaign')
    objects.append({
        'type':         'campaign',
        'spec_version': '2.1',
        'id':           campaign_id,
        'created':      created,
        'modified':     created,
        'name':         'India Digital Arrest Fraud Campaign 2025-26',
        'description':  ('Coordinated campaign impersonating CBI, ED, TRAI and Customs officers '
                         'via video call. Victims told they are "digitally arrested" and coerced '
                         'into payments. Rs 2,000+ Cr India loss 2024. Single victim: Rs 22.92 Cr. '
                         'PM Modi warned in Mann Ki Baat. Chief Justice of India expressed concern. '
                         '67 cases detected by CINEOS.'),
        'aliases':      ['Digital Arrest', 'Cyber Arrest', 'डिजिटल अरेस्ट'],
        'objective':    'Financial extortion through fake law enforcement impersonation',
        'first_seen':   '2024-01-01T00:00:00.000Z',
        'last_seen':    created,
        'labels':       ['social-engineering', 'india', 'financial-fraud'],
        'created_by_ref': cineos_id,
        'object_marking_refs': ['marking-definition--613f2e26-407d-48c7-9eca-b8e91ba4c5e5'],
    })

    # ── Pig butchering → Campaign object ──────────────────
    pig_id = make_id('campaign')
    objects.append({
        'type':         'campaign',
        'spec_version': '2.1',
        'id':           pig_id,
        'created':      created,
        'modified':     created,
        'name':         'India Pig Butchering Campaign (Sha Zhu Pan) 2024-26',
        'description':  ('Mass-scale investment fraud targeting India. Task fraud → investment '
                         'trust → fake crypto platform → UPI transfer → operator disappears. '
                         'Rs 6,000 Cr India loss 2024 per MHA/I4C. 105 CINEOS detection patterns '
                         'in 6 Indian languages. Platforms: WhatsApp, Telegram, Instagram, Facebook.'),
        'aliases':      ['Sha Zhu Pan', 'Task Fraud', 'Investment Scam India'],
        'objective':    'Financial fraud through relationship manipulation and fake investment platforms',
        'first_seen':   '2023-01-01T00:00:00.000Z',
        'last_seen':    created,
        'labels':       ['pig-butchering', 'social-engineering', 'india', 'financial-fraud'],
        'created_by_ref': cineos_id,
        'object_marking_refs': ['marking-definition--613f2e26-407d-48c7-9eca-b8e91ba4c5e5'],
    })

    # ── Build bundle ──────────────────────────────────────
    bundle = {
        'type':         'bundle',
        'id':           make_id('bundle'),
        'spec_version': '2.1',
        'created':      created,
        'objects':      objects,
    }

    os.makedirs('reports', exist_ok=True)
    path = 'reports/cineos_stix_bundle.json'
    json.dump(bundle, open(path, 'w'), indent=2)

    print(f"\n{'='*55}")
    print(f"  CINEOS STIX 2.1 BUNDLE")
    print(f"{'='*55}")
    print(f"  Bundle ID:       {bundle['id']}")
    print(f"  Total objects:   {len(objects)}")
    print(f"  Threat actors:   {sum(1 for o in objects if o['type']=='threat-actor')}")
    print(f"  Indicators:      {sum(1 for o in objects if o['type']=='indicator')}")
    print(f"  Campaigns:       {sum(1 for o in objects if o['type']=='campaign')}")
    print(f"  Spec version:    STIX 2.1")
    print(f"  TLP marking:     TLP:WHITE")
    print(f"  Producer:        CINEOS (yugandhar@cineos.in)")
    print(f"  Saved:           {path}")
    print(f"\n  Group-IB, ZeroFox, Recorded Future all consume STIX 2.1.")
    print(f"  CINEOS now speaks their language.")
    return bundle

build_stix_bundle()
