"""
CINEOS Media Pitch Generator
One article in ET/Mint/YourStory = 100 inbound calls.
This builds the pitch for major Indian media.
"""
import smtplib, os, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_FROM = 'yugandhar@cineos.in'
GMAIL_SMTP = 'dba.yugandhar@gmail.com'
GMAIL_PASS = os.environ.get('GMAIL_APP_PASSWORD','')

now = datetime.datetime.now().strftime('%B %d, %Y')

MEDIA_CONTACTS = [
    {
        'publication': 'Economic Times',
        'journalist': 'Tech/Startup Desk',
        'email': 'etdesk@indiatimes.com',
        'angle': 'startup',
    },
    {
        'publication': 'Mint',
        'journalist': 'Technology Desk',
        'email': 'letters@livemint.com',
        'angle': 'fintech',
    },
    {
        'publication': 'YourStory',
        'journalist': 'Editor',
        'email': 'editor@yourstory.com',
        'angle': 'startup',
    },
    {
        'publication': 'Inc42',
        'journalist': 'News Desk',
        'email': 'news@inc42.com',
        'angle': 'startup',
    },
    {
        'publication': 'The420.in',
        'journalist': 'Cybercrime Desk',
        'email': 'editor@the420.in',
        'angle': 'cybercrime',
    },
    {
        'publication': 'NDTV Tech',
        'journalist': 'Tech Desk',
        'email': 'ndtvtech@ndtv.com',
        'angle': 'tech',
    },
    {
        'publication': 'Moneycontrol',
        'journalist': 'Fintech Desk',
        'email': 'feedback@moneycontrol.com',
        'angle': 'fintech',
    },
]

PITCH_TEMPLATES = {
    'startup': {
        'subject': 'Story: India startup detects Rs 8,000 Cr fraud network — 11M Telegram subscribers',
        'body': f'''Dear Editor,

I am Yugandhar Mallavarapu, founder of CINEOS — India's Trust Intelligence Network.

STORY PITCH — Ready to publish immediately.

HEADLINE:
"Hyderabad startup maps India's Rs 8,000 crore fraud network —
 found on 13 platforms, 6 languages, in 4 months"

KEY FACTS (all verified):
- 354 Telegram fraud channels — 11 million subscribers
- Rs 6,000 Cr lost to pig butchering scams (MHA data)
- Rs 2,000 Cr lost to digital arrest fraud in 2024
- 2,300 voice clone cases in Q4 2025 — 450% YoY increase
- 79 counterfeit sellers found — Nike, Samsung, Dove, boAt
- Single platform monitoring 13 channels in 6 Indian languages
- No US competitor (Doppel $129M, ZeroFox $350M) has this
- Bootstrapped by 1 founder — US Provisional Patent filed

THE STORY:
While US companies raised $129M to fight counterfeit goods,
a solo founder in Hyderabad built the same thing for India —
covering platforms they've never heard of, in languages
they've never detected, finding fraud types that don't
even exist in the US.

AVAILABLE:
- Demo of the live platform (cineos.in)
- Raw data on 354 fraud channels
- Names of confirmed counterfeit sellers
- Voice clone fraud examples using Nithin Kamath's name
- Digital arrest victim loss data

I can do an interview today. Full platform demo available.

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in
cineos.in
+91 [available on request]
US Provisional Patent 64/049,190''',
    },
    'fintech': {
        'subject': 'Story Pitch: Rs 6,000 Cr pig butchering fraud — India startup built the first detector',
        'body': f'''Dear Editor,

STORY PITCH — Exclusive data available.

HEADLINE:
"India's Rs 6,000 crore pig butchering problem —
 one startup built what the RBI couldn't"

KEY DATA:
- Rs 6,000 Cr lost to Telegram investment fraud 2024 (MHA)
- Rs 19.8 Cr — single pig butchering victim, Ludhiana 2026
- CINEOS built 105-pattern detection in 6 Indian languages
- 354 fraud channels monitored daily
- Fake Zerodha channels: 18 found, 747K subscribers exposed
- PhonePe fake screenshots — new Telegram tool channels found
- Digital arrest: Rs 22.92 Cr single victim case confirmed

CINEOS is the only platform in India scanning for all of this
simultaneously. Built by 1 founder. Bootstrapped. Patent filed.

Available for interview immediately.

Yugandhar Mallavarapu
yugandhar@cineos.in
cineos.in
US Provisional Patent 64/049,190''',
    },
    'cybercrime': {
        'subject': 'Exclusive: India cybercrime mapped — digital arrest, pig butchering, voice clone data',
        'body': f'''Dear Editor,

EXCLUSIVE DATA AVAILABLE — Cybercrime Intelligence Story.

CINEOS has mapped India's cybercrime landscape:

DIGITAL ARREST FRAUD:
- 67 confirmed cases detected this week
- Single victim loss: Rs 22.92 Crore
- Delhi couple: Rs 14 Crore
- Chief Justice of India expressed concern
- PM Modi warned in Mann Ki Baat

VOICE CLONE FRAUD:
- 2,300 cases in India Q4 2025 — 450% YoY increase
- Nithin Kamath (Zerodha CEO) name used in 113 fraud mentions
- Only 3 seconds of audio needed in 2026

PIG BUTCHERING:
- Rs 6,000 Cr India loss 2024 (MHA estimates)
- 105 fraud patterns detected in 6 Indian languages
- 1,191 Telegram messages analyzed

All data verified. Available for immediate interview.
Full platform demo: cineos.in

Yugandhar Mallavarapu
yugandhar@cineos.in
US Provisional Patent 64/049,190''',
    },
}

print("=== Sending media pitches ===\n")
sent = 0
for contact in MEDIA_CONTACTS:
    template = PITCH_TEMPLATES.get(contact['angle'],
                                    PITCH_TEMPLATES['startup'])
    msg = MIMEMultipart()
    msg['Subject'] = template['subject']
    msg['From'] = GMAIL_FROM
    msg['To'] = contact['email']
    msg['Bcc'] = GMAIL_FROM
    msg.attach(MIMEText(template['body'], 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(GMAIL_SMTP, GMAIL_PASS)
            s.sendmail(GMAIL_FROM,
                      [contact['email'], GMAIL_FROM],
                      msg.as_string())
        print(f"✓ {contact['publication']:20} → {contact['email']}")
        sent += 1
    except Exception as e:
        print(f"✗ {contact['publication']} → {e}")

print(f"\nMedia pitches sent: {sent}/{len(MEDIA_CONTACTS)}")
print("\nIf ONE journalist replies — CINEOS gets national coverage.")
print("National coverage = 100 inbound enterprise calls.")
print("That is the contract. One article changes everything.")
