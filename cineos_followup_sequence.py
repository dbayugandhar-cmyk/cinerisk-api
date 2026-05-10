"""
CINEOS Follow-up Email Sequence
Day 3, Day 7, Day 14 follow-ups to all contacts.
Run: python3 cineos_followup_sequence.py 3
"""
import sys, smtplib, os, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_FROM = 'yugandhar@cineos.in'
GMAIL_SMTP = 'dba.yugandhar@gmail.com'
GMAIL_PASS = os.environ.get('GMAIL_APP_PASSWORD', '')

day = int(sys.argv[1]) if len(sys.argv) > 1 else 3

FOLLOWUPS = {
    3: [
        {
            'to': 'sanjayg@sebi.gov.in',
            'subject': 'CINEOS follow-up: 1,077 fraud channels — SEBI intelligence update',
            'body': """Dear Shri Sanjay G,

Following up on my email from 3 days ago.

Quick update since my last report:
  - New fraud category detected: Colour prediction apps
    41 channels, 5M+ subscribers, no SEBI/RBI registration
  - BigDaddy, Yaarwin, Daman, Tiranga, 91Club
  - Illegal lottery disguised as colour prediction games

This is a new alert we have not seen any regulator flag yet.
Full intelligence report attached if helpful.

Happy to present our full database to SEBI this week.

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in · cineos.in""",
        },
        {
            'to': 'cybercrime@mha.gov.in',
            'subject': 'CINEOS follow-up: Digital arrest fraud — 67 cases, Rs 22.92 Cr victim',
            'body': """Dear MHA Cyber Crime Division,

Following up on my digital arrest fraud intelligence report.

Since that email we have also detected:
  - Colour prediction gambling apps (BigDaddy, Yaarwin)
    41 channels, 5M+ subscribers — new fraud category
  - QR code fraud on merchant payment terminals
  - 4 phone numbers attributed to IPL betting operators

CINEOS is ready to provide daily intelligence feeds to I4C.
Our data is formatted for I4C Suspect Registry integration.

I4C phone: 011-2343 8207 — happy to brief your team.

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in · cineos.in""",
        },
        {
            'to': 'nithin@zerodha.com',
            'subject': 'CINEOS follow-up: 540K subscribers on fake Zerodha channel',
            'body': """Hi Nithin,

Following up from 3 days ago.

Your name appeared in 113 fraud mentions in our weekly scan.
The single largest fake channel using your brand:

  @Groww_Tips_Zerodha_Upstox — 540,284 subscribers
  Active as of today. Posting fake trading signals daily.

CINEOS can alert your team within minutes of any new
channel appearing — anywhere, in any language.

15-minute call this week?

Yugandhar
yugandhar@cineos.in""",
        },
        {
            'to': 'integrity@bcci.tv',
            'subject': 'CINEOS follow-up: IPL 2026 — 371 illegal betting channels active',
            'body': """Dear BCCI Integrity Team,

Following up on my intelligence report.

During IPL 2026 matches, CINEOS is detecting active betting
channels with combined reach of 35M+ subscribers.

Top channels active during match days:
  @Anuragt_bookqc_Malikc    — 1.7M subscribers
  @News_Crypto5             — 1.7M subscribers  
  @CRYPTO_book_lotus365     — 1.1M subscribers

Each publishes live odds during BCCI matches.
CINEOS can provide match-day monitoring as a service.

Available to present this week.

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in · cineos.in""",
        },
    ],
    7: [
        {
            'to': 'partners@zerofox.com',
            'subject': 'CINEOS × ZeroFox: India intelligence partnership — following up',
            'body': """Dear ZeroFox Partnerships Team,

Following up on my email from last week.

We have added new capabilities since then:
  ✓ Privacy policy and terms of service live (cineos.in/privacy.html)
  ✓ Full API documentation published (cineos.in/api.html)
  ✓ Daily automated scans operational
  ✓ Webhook system live for real-time alerts

CINEOS is now fully ready for a technical partnership evaluation.

Key differentiator for ZeroFox India clients:
  - 1,077 Telegram channels (vs zero coverage today)
  - IndiaMART counterfeit sellers (GST validated)
  - 6 Indian language detection
  - IT Act 65B court-grade evidence

15-minute call this week?

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in · cineos.in
US Provisional Patent 64/049,190""",
        },
        {
            'to': 'partnerships@marqvision.com',
            'subject': 'CINEOS × MarqVision: India follow-up — API docs now live',
            'body': """Dear MarqVision Partnerships Team,

Following up from last week.

Since my email we have published full API documentation
at cineos.in/api.html — 18 endpoints including:

  POST /v1/scan        — brand counterfeit scan
  POST /v1/risk/seller — IndiaMART seller scoring
  POST /v1/risk/batch  — batch 50 sellers at once
  POST /v1/webhooks    — real-time alert webhooks

Integration with MarqVision would take 1-2 days.
Your Asia coverage gains genuine India depth immediately.

Happy to do a 15-minute technical call this week.

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in · cineos.in""",
        },
    ],
}

contacts = FOLLOWUPS.get(day, [])
if not contacts:
    print(f"No follow-ups configured for day {day}")
    sys.exit(0)

print(f"=== Day {day} follow-up sequence ===\n")
sent = 0
for contact in contacts:
    msg = MIMEMultipart()
    msg['Subject'] = contact['subject']
    msg['From']    = GMAIL_FROM
    msg['To']      = contact['to']
    msg['Bcc']     = GMAIL_FROM
    msg.attach(MIMEText(contact['body'], 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(GMAIL_SMTP, GMAIL_PASS)
            s.sendmail(GMAIL_FROM, [contact['to'], GMAIL_FROM], msg.as_string())
        print(f"  ✓ {contact['to']}")
        sent += 1
    except Exception as e:
        print(f"  ✗ {contact['to']} — {e}")

print(f"\nDay {day} follow-ups sent: {sent}/{len(contacts)}")
