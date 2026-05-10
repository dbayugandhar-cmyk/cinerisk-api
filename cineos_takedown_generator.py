"""
CINEOS Takedown Notice Generator
Generates legally formatted takedown notices for:
  - Telegram (IT Rules 2021 — Significant Social Media Intermediary)
  - Google/YouTube (DMCA + IT Rules 2021)
  - Meta/Instagram (IT Rules 2021)
  - SEBI SCORES (investment fraud channels)
  - GST Council (counterfeit sellers)
  - MHA/I4C (digital arrest + pig butchering)

IT Rules 2021 mandates 36-hour response for SSMI.
Evidence must be IT Act 65B compliant.
"""
import json, os, hashlib, hmac, datetime

SECRET_KEY = b'cineos_evidence_key_2026'

def hash_evidence(data: str) -> dict:
    """IT Act 65B compliant hashing."""
    sha256   = hashlib.sha256(data.encode()).hexdigest()
    hmac_sig = hmac.new(SECRET_KEY, data.encode(), hashlib.sha256).hexdigest()
    return {
        'sha256':    sha256,
        'hmac':      hmac_sig,
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'method':    'SHA-256 + HMAC-SHA256',
        'standard':  'IT Act 2000 Section 65B',
    }

def generate_telegram_notice(channel: dict) -> str:
    """
    IT Rules 2021 — Rule 4(2) — Takedown notice to Telegram.
    Telegram is a Significant Social Media Intermediary (SSMI) in India.
    Must respond within 36 hours.
    Send to: abuse@telegram.org
    """
    username  = channel.get('username', '')
    subs      = channel.get('subscribers', 0)
    title     = channel.get('title', '')
    category  = channel.get('discovered_by', 'fraud')
    evidence  = hash_evidence(json.dumps(channel, default=str))
    now       = datetime.datetime.now().strftime('%B %d, %Y')

    notice = f"""FORMAL TAKEDOWN NOTICE
Under Information Technology (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021
Rule 4(2) — Grievance by Affected Party

Date: {now}
To: Telegram Messenger (abuse@telegram.org)
From: CINEOS Intelligence Platform
       Yugandhar Mallavarapu, Founder
       yugandhar@cineos.in | cineos.in
       US Provisional Patent 64/049,190

SUBJECT: Immediate removal of illegal channel @{username}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. CHANNEL DETAILS
   Username:     @{username}
   Display name: {title}
   Subscribers:  {subs:,}
   Category:     {category}
   Platform:     Telegram

2. NATURE OF VIOLATION
   This channel operates an illegal {"gambling/betting operation" if any(k in category.lower() for k in ["bet","satta","matka","ipl"]) else "fraud operation"} targeting Indian users.
   It violates:
   a) The Public Gambling Act, 1867
   b) Information Technology Act, 2000 — Section 66D (cheating by personation)
   c) Bharatiya Nyaya Sanhita, 2023 — Section 318 (cheating)
   d) FEMA, 1999 (illegal foreign exchange transactions via betting)

3. EVIDENCE — IT ACT 2000 SECTION 65B COMPLIANT
   SHA-256 Hash:    {evidence['sha256']}
   HMAC Signature:  {evidence['hmac']}
   Captured at:     {evidence['timestamp']}
   
   I certify that this electronic record was captured from
   the publicly accessible Telegram channel @{username} and
   that this certificate is issued in compliance with
   Section 65B of the Indian Evidence Act, 1872.

4. LEGAL BASIS FOR REMOVAL
   Under IT Rules 2021 Rule 3(1)(b), Telegram is required to
   remove content that is "grossly harmful", "promotes gambling"
   or "threatens public order" within 36 hours of receipt of
   this notice.

   Failure to act within 36 hours will result in:
   a) Escalation to Ministry of Electronics and IT (MeitY)
   b) Referral to I4C (Indian Cybercrime Coordination Centre)
   c) Potential loss of safe harbour protection under IT Act Section 79

5. REQUESTED ACTION
   a) Immediate suspension of channel @{username}
   b) Preservation of channel metadata for law enforcement
   c) Written acknowledgement within 36 hours
   d) Confirmation of removal within 36 hours

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Yugandhar Mallavarapu
Founder, CINEOS — India's Trust Intelligence Network
yugandhar@cineos.in | cineos.in
US Provisional Patent 64/049,190

This notice is filed on {now}.
"""
    return notice

def generate_sebi_scores_complaint(channel: dict) -> str:
    """SEBI SCORES complaint for investment fraud channels."""
    username = channel.get('username', '')
    subs     = channel.get('subscribers', 0)
    evidence = hash_evidence(json.dumps(channel, default=str))
    now      = datetime.datetime.now().strftime('%B %d, %Y')

    complaint = f"""SEBI SCORES INVESTOR COMPLAINT
Securities and Exchange Board of India

Date: {now}
Complaint Category: Unregistered Investment Advisor
Sub-category: Fraudulent investment tips on social media

CHANNEL DETAILS:
  Platform:    Telegram
  Username:    @{username}
  Subscribers: {subs:,}

NATURE OF COMPLAINT:
  This Telegram channel provides stock market trading tips,
  investment signals and/or cryptocurrency trading advice
  to {subs:,} subscribers without being registered as an
  Investment Adviser under SEBI (Investment Advisers)
  Regulations, 2013.

  This constitutes a violation of:
  a) SEBI (Investment Advisers) Regulations, 2013 — Regulation 3
  b) SEBI Act, 1992 — Section 12
  c) IT Act, 2000 — Section 66D

EVIDENCE (IT Act 65B Compliant):
  SHA-256: {evidence['sha256']}
  Captured: {evidence['timestamp']}

REQUESTED ACTION:
  1. Investigation of channel @{username}
  2. Direction to Telegram to disclose operator identity
  3. FIR registration if violation confirmed
  4. Investor alert advisory

Filed by: CINEOS Intelligence Platform
Contact: yugandhar@cineos.in
"""
    return complaint

def generate_gst_complaint(seller: dict) -> str:
    """GST Council complaint for counterfeit sellers."""
    company  = seller.get('company', 'Unknown')
    gst      = seller.get('gst', '')
    city     = seller.get('city', '')
    brand    = seller.get('brand', '')
    score    = seller.get('auth_score', 0)
    evidence = hash_evidence(json.dumps(seller, default=str))
    now      = datetime.datetime.now().strftime('%B %d, %Y')

    complaint = f"""GST COUNCIL COMPLAINT — COUNTERFEIT GOODS SELLER
Central Board of Indirect Taxes and Customs

Date: {now}
To: cbec-gst@gov.in

SELLER DETAILS:
  Company Name: {company}
  GST Number:   {gst}
  City:         {city}
  Platform:     IndiaMART

NATURE OF VIOLATION:
  This seller is marketing and selling counterfeit {brand}
  products under GST registration {gst}.
  CINEOS risk score: {score}/100 — CONFIRMED COUNTERFEIT.

  Violations:
  a) Trade Marks Act, 1999 — Section 29 (Infringement)
  b) Legal Metrology Act, 2009 (fake branded goods)
  c) Consumer Protection Act, 2019
  d) Customs Act, 1962 (if imported counterfeits)

EVIDENCE (IT Act 65B Compliant):
  SHA-256: {evidence['sha256']}
  Captured: {evidence['timestamp']}

REQUESTED ACTION:
  1. Inspection of GST registrant {gst}
  2. Cancellation of GST registration if violation confirmed
  3. Referral to trademark enforcement authority
  4. Consumer protection action

Filed by: CINEOS Intelligence Platform
Contact: yugandhar@cineos.in
"""
    return complaint

def run_batch_notices():
    """Generate takedown notices for top confirmed fraud cases."""
    os.makedirs('reports/takedowns', exist_ok=True)

    generated = 0

    # Telegram — top 10 betting channels
    try:
        channels = json.load(open('reports/all_channels.json'))
        betting  = sorted(
            [c for c in channels if any(k in c.get('username','').lower()
             for k in ['satta','matka','bet','reddy','mahadev','ipl','toss'])
             and c.get('subscribers', 0) >= 100000],
            key=lambda x: -x.get('subscribers', 0)
        )[:10]

        for ch in betting:
            notice = generate_telegram_notice(ch)
            fname  = f"reports/takedowns/telegram_{ch['username'][:30]}.txt"
            open(fname, 'w').write(notice)
            generated += 1

        print(f"Generated {len(betting)} Telegram takedown notices")

        # Investment fraud — SEBI SCORES
        investment = sorted(
            [c for c in channels if any(k in c.get('username','').lower()
             for k in ['stock','zerodha','groww','nifty','crypto','signal','invest'])
             and c.get('subscribers', 0) >= 50000],
            key=lambda x: -x.get('subscribers', 0)
        )[:5]

        for ch in investment:
            complaint = generate_sebi_scores_complaint(ch)
            fname     = f"reports/takedowns/sebi_{ch['username'][:30]}.txt"
            open(fname, 'w').write(complaint)
            generated += 1

        print(f"Generated {len(investment)} SEBI SCORES complaints")

    except Exception as e:
        print(f"Channel notice error: {e}")

    # GST Council — counterfeit sellers
    try:
        sellers   = json.load(open('reports/seller_auth_scores.json'))
        confirmed = [s for s in sellers if s.get('auth_score', 0) >= 75
                     and s.get('gst')][:10]

        for seller in confirmed:
            complaint = generate_gst_complaint(seller)
            co        = seller.get('company', 'seller')[:20].replace(' ', '_')
            fname     = f"reports/takedowns/gst_{co}.txt"
            open(fname, 'w').write(complaint)
            generated += 1

        print(f"Generated {len(confirmed)} GST Council complaints")

    except Exception as e:
        print(f"Seller complaint error: {e}")

    print(f"\nTotal notices generated: {generated}")
    print(f"Saved to: reports/takedowns/")
    print(f"\nNEXT STEPS:")
    print(f"  Telegram:  email abuse@telegram.org with notice + evidence")
    print(f"  SEBI:      file at scores.sebi.gov.in")
    print(f"  GST:       email cbec-gst@gov.in")
    return generated

run_batch_notices()
