"""
CINEOS Payment Platform Pitch
PhonePe: 700M users, IPO coming, fraud prevention priority.
Paytm: 540M users, AI fraud detection already running.
CINEOS adds the Telegram/social intelligence they don't have.
"""
import smtplib, os, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

GMAIL_FROM = 'yugandhar@cineos.in'
GMAIL_SMTP = 'dba.yugandhar@gmail.com'
GMAIL_PASS = os.environ.get('GMAIL_APP_PASSWORD','')
now = datetime.datetime.now().strftime('%B %d, %Y')

contacts = [
    {
        'to': 'business@phonepe.com',
        'company': 'PhonePe',
        'subject': 'CINEOS fraud intelligence — fake PhonePe screenshots in Telegram channels detected',
        'body': f'''Dear PhonePe Security Team,

CINEOS detected Telegram channels distributing tools
to create fake PhonePe payment screenshots — used to
defraud merchants across India.

With 700M users and your IPO approaching, merchant fraud
directly impacts PhonePe's reliability reputation.

CINEOS monitors 13 platforms, 354 fraud channels,
11 million subscribers daily in 6 Indian languages.

What CINEOS provides PhonePe:
  • Real-time alerts when new fake payment tools appear
  • Telegram channel names distributing PhonePe fakes
  • Fake screenshot app listings on Play Store
  • Phone numbers linked to payment fraud channels

PhonePe + DoT already blocked Rs 200 Cr in fraud via FRI.
CINEOS adds the Telegram intelligence layer DoT cannot see.

Intelligence report attached.

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in
cineos.in
US Provisional Patent 64/049,190''',
    },
    {
        'to': 'grievance@paytm.com',
        'company': 'Paytm',
        'subject': 'CINEOS: Fake Paytm payment screenshots in Telegram — fraud intelligence report',
        'body': f'''Dear Paytm Security Team,

CINEOS detected Telegram channels distributing fake Paytm
payment screenshot tools used to defraud merchants.

Also detected: 10+ Paytm-branded fraud channels on Telegram
with fake investment and crypto schemes.

CINEOS monitors 354 fraud channels, 11M subscribers daily.
We detected fake PhonePe/Paytm screenshots being shared
in 23+ fraud contexts this week.

Intelligence report attached. API integration available.

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in
cineos.in
US Provisional Patent 64/049,190''',
    },
    {
        'to': 'rahul.chari@phonepe.com',
        'company': 'PhonePe (Rahul Chari)',
        'subject': 'CINEOS fraud intelligence for PhonePe — Telegram social layer for FRI platform',
        'body': f'''Hi Rahul,

Congratulations on presenting PhonePe's fraud work
to PM Modi at India Mobile Congress 2025.

PhonePe + Paytm + DoT stopped Rs 200 Cr via FRI.
CINEOS adds the missing piece — Telegram intelligence.

FRI checks mobile numbers against bank data.
CINEOS maps those same numbers to Telegram fraud channels.

Example: +91-8441916068 appears in 2 IPL betting channels
with 19,220 subscribers. FRI would flag transactions.
CINEOS shows WHY — the operator, the channels, the fraud.

This is the social intelligence layer FRI needs.

Can we talk this week?

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in
cineos.in
US Provisional Patent 64/049,190''',
    },
]

print("=== Sending PhonePe/Paytm pitches ===\n")
for c in contacts:
    msg = MIMEMultipart()
    msg['Subject'] = c['subject']
    msg['From'] = GMAIL_FROM
    msg['To'] = c['to']
    msg['Bcc'] = GMAIL_FROM
    msg.attach(MIMEText(c['body'], 'plain'))

    # Attach relevant PDF
    pdf_path = 'reports/CINEOS_DigitalArrest_Intelligence.pdf'
    if os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            pdf = MIMEApplication(f.read(), _subtype='pdf')
            pdf.add_header('Content-Disposition', 'attachment',
                          filename='CINEOS_PaymentFraud_Intelligence.pdf')
            msg.attach(pdf)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(GMAIL_SMTP, GMAIL_PASS)
            s.sendmail(GMAIL_FROM, [c['to'], GMAIL_FROM], msg.as_string())
        print(f"✓ {c['company']:25} → {c['to']}")
    except Exception as e:
        print(f"✗ {c['company']} → {e}")
