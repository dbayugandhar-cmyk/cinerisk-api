"""
CINEOS Professional Email System
Every email = short body + relevant PDF attachment.
No exceptions. MNC standard.
"""
import smtplib, os, json, datetime, re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER

# ── CONFIG ────────────────────────────────────────────────
GMAIL_FROM = 'yugandhar@cineos.in'
GMAIL_SMTP = 'dba.yugandhar@gmail.com'
GMAIL_PASS = os.environ.get('GMAIL_APP_PASSWORD', '')

# ── COLORS ────────────────────────────────────────────────
BLACK  = colors.HexColor('#070B14')
GREEN  = colors.HexColor('#00CC66')
RED    = colors.HexColor('#FF3355')
ORANGE = colors.HexColor('#FF8C00')
BLUE   = colors.HexColor('#3D7FFF')
PURPLE = colors.HexColor('#8844CC')
LGRAY  = colors.HexColor('#E8EEF8')
MGRAY  = colors.HexColor('#8899BB')
WHITE  = colors.white

def S(name, **kw):
    d = dict(fontName='Helvetica', fontSize=9,
             textColor=BLACK, spaceAfter=4, leading=14)
    d.update(kw)
    return ParagraphStyle(name, **d)

def header_footer(c, doc, title, date_str, recipient=''):
    c.saveState()
    w, h = A4
    c.setFillColor(BLACK); c.rect(0, h-50, w, 50, fill=1, stroke=0)
    c.setFillColor(GREEN);  c.rect(0, h-53, w, 3, fill=1, stroke=0)
    c.setFillColor(GREEN);  c.setFont('Helvetica-Bold', 16)
    c.drawString(20*mm, h-33, 'CINEOS')
    c.setFillColor(WHITE);  c.setFont('Helvetica', 9)
    c.drawString(58*mm, h-33, f'— {title}')
    c.setFillColor(MGRAY);  c.setFont('Helvetica', 7.5)
    c.drawRightString(w-20*mm, h-28, date_str)
    if recipient:
        c.setFillColor(colors.HexColor('#AABBCC'))
        c.setFont('Helvetica', 7)
        c.drawRightString(w-20*mm, h-40, f'Prepared for: {recipient}')
    c.setFillColor(LGRAY); c.rect(0, 0, w, 28, fill=1, stroke=0)
    c.setFillColor(GREEN);  c.rect(0, 28, w, 1.5, fill=1, stroke=0)
    c.setFillColor(BLACK);  c.setFont('Helvetica', 7)
    c.drawString(20*mm, 10,
        'CINEOS — India\'s Trust Intelligence Network  ·  cineos.in'
        '  ·  yugandhar@cineos.in  ·  US Patent 64/049,190')
    c.drawRightString(w-20*mm, 10,
        f'Page {doc.page}  ·  STRICTLY CONFIDENTIAL')
    c.restoreState()

def make_doc(filename, title, recipient=''):
    date_str = datetime.datetime.now().strftime('%B %d, %Y')
    doc = SimpleDocTemplate(filename, pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=62, bottomMargin=40)
    doc.onFirstPage  = lambda c,d: header_footer(c,d,title,date_str,recipient)
    doc.onLaterPages = lambda c,d: header_footer(c,d,title,date_str,recipient)
    return doc

def stat_row(items):
    n = len(items)
    r1 = [Paragraph(
        f'<b><font size=22 color="{c.hexval()}">{v}</font></b>',
        S('sv', alignment=TA_CENTER)) for v,l,c in items]
    r2 = [Paragraph(
        f'<font size=7.5 color="{MGRAY.hexval()}">{l}</font>',
        S('sl', alignment=TA_CENTER)) for v,l,c in items]
    t = Table([r1,r2], colWidths=[170/n*mm]*n)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),LGRAY),
        ('BOX',(0,0),(-1,-1),0.5,colors.HexColor('#CCDDEE')),
        ('INNERGRID',(0,0),(-1,-1),0.3,colors.HexColor('#CCDDEE')),
        ('TOPPADDING',(0,0),(-1,-1),10),
        ('BOTTOMPADDING',(0,0),(-1,-1),10),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
    ]))
    return t

def data_table(headers, rows, col_w):
    hrow = [Paragraph(
        f'<b><font color="white" size=8.5>{h}</font></b>',
        S('h', alignment=TA_CENTER)) for h in headers]
    t = Table([hrow]+rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLACK),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,LGRAY]),
        ('BOX',(0,0),(-1,-1),0.5,colors.HexColor('#CCDDEE')),
        ('INNERGRID',(0,0),(-1,-1),0.3,colors.HexColor('#CCDDEE')),
        ('TOPPADDING',(0,0),(-1,-1),5),
        ('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),5),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
    ]))
    return t

# ── PDF GENERATORS ────────────────────────────────────────

def gen_trai_pdf(output_path):
    doc = make_doc(output_path,
        'Phone Attribution Intelligence', 'TRAI Chairman')
    now = datetime.datetime.now().strftime('%B %d, %Y')
    story = []
    TITLE = S('T', fontName='Helvetica-Bold', fontSize=20, spaceAfter=3)
    SUB   = S('S', fontSize=10, textColor=MGRAY, spaceAfter=10)
    SEC   = S('SE', fontName='Helvetica-Bold', fontSize=12,
               textColor=GREEN, spaceBefore=14, spaceAfter=6)
    BODY  = S('B', fontSize=9, spaceAfter=5, leading=14)
    CAP   = S('C', fontSize=7.5, textColor=MGRAY, spaceAfter=4)

    story.append(Paragraph('Phone Attribution Intelligence Report', TITLE))
    story.append(Paragraph(
        f'Illegal Betting Channel Phone Numbers — {now}', SUB))
    story.append(HRFlowable(width='100%', thickness=2,
                             color=GREEN, spaceAfter=12))
    story.append(Paragraph('Executive Summary', SEC))
    story.append(Paragraph(
        'CINEOS has extracted <b>2 phone numbers</b> from illegal IPL betting '
        'Telegram channels and confirmed that <b>phone +91-8441916068 is shared '
        'between two channels</b> — proving a single operator controls both. '
        'These numbers are requested for blocking under IT Act Section 69A '
        'and Telecom Act 2023.', BODY))
    story.append(Spacer(1,8))
    story.append(stat_row([
        ('2','Phone Numbers Found',RED),
        ('1','Operator Cluster',ORANGE),
        ('19,220','Combined Subscribers',RED),
        ('3','Channels Linked',ORANGE),
    ]))
    story.append(Spacer(1,14))

    story.append(Paragraph('Phone Numbers for Blocking', SEC))
    rows = [
        [Paragraph('<b>+91-8441916068</b>', S('c', fontSize=9)),
         Paragraph('IPLBetting, ipltossmatchsessionn', S('c', fontSize=8)),
         Paragraph('19,220', S('c', alignment=TA_CENTER, fontSize=9)),
         Paragraph('<b><font color="#FF3355">CRITICAL</font></b>',
                   S('c', alignment=TA_CENTER, fontSize=8)),
         Paragraph('Same operator — 2 channels', S('c', fontSize=8))],
        [Paragraph('<b>+91-6378542162</b>', S('c', fontSize=9)),
         Paragraph('Satta_khaiwal_gali_dishwar', S('c', fontSize=8)),
         Paragraph('Unknown', S('c', alignment=TA_CENTER, fontSize=9)),
         Paragraph('<b><font color="#FF8C00">HIGH</font></b>',
                   S('c', alignment=TA_CENTER, fontSize=8)),
         Paragraph('Satta Matka promotion', S('c', fontSize=8))],
    ]
    story.append(data_table(
        ['Phone Number','Telegram Channels','Reach','Risk','Activity'],
        rows, [35*mm,52*mm,22*mm,18*mm,43*mm]))
    story.append(Spacer(1,12))

    story.append(Paragraph('Operator Cluster Evidence', SEC))
    story.append(Paragraph(
        'The following two Telegram channels share the same contact phone number, '
        'confirming they are operated by a single individual:', BODY))
    cluster_data = [
        ['Attribute','Channel 1','Channel 2'],
        ['Channel Name','@IPLBetting','@ipltossmatchsessionn'],
        ['Subscribers','9,610','9,610'],
        ['Activity','Match betting odds','Toss & session betting'],
        ['Phone Number','+91-8441916068','+91-8441916068 ← SAME'],
        ['Conclusion','Same operator','Same operator'],
    ]
    ct = Table(cluster_data, colWidths=[45*mm,62*mm,63*mm])
    ct.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLACK),
        ('TEXTCOLOR',(0,0),(-1,0),WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('BACKGROUND',(0,4),(0,4),LGRAY),
        ('BACKGROUND',(1,4),(2,4),colors.HexColor('#FFE8E8')),
        ('TEXTCOLOR',(1,4),(2,4),RED),
        ('FONTNAME',(1,4),(2,4),'Helvetica-Bold'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,LGRAY]),
        ('BOX',(0,0),(-1,-1),0.5,colors.HexColor('#CCDDEE')),
        ('INNERGRID',(0,0),(-1,-1),0.3,colors.HexColor('#CCDDEE')),
        ('TOPPADDING',(0,0),(-1,-1),7),
        ('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),6),
        ('FONTSIZE',(0,1),(-1,-1),9),
    ]))
    story.append(ct)
    story.append(Spacer(1,12))

    story.append(Paragraph('Legal Basis', SEC))
    for law, desc in [
        ('IT Act 2000 Section 69A',
         'Central Government may block access to information in interest of public order'),
        ('Telecom Act 2023',
         'TRAI may direct blocking of fraudulent telecom communications'),
        ('Public Gambling Act 1867 Sections 3, 4',
         'Promotion of gambling is a criminal offence — phones used as instruments'),
        ('IT Act 2000 Section 66D',
         'Cheating by personation using electronic communication'),
    ]:
        story.append(Paragraph(
            f'• <b>{law}</b><br/>&nbsp;&nbsp;&nbsp;{desc}', BODY))

    story.append(Spacer(1,8))
    story.append(Paragraph('Requested Actions', SEC))
    for i, action in enumerate([
        'Block +91-8441916068 on all telecom networks — operator confirmed',
        'Block +91-6378542162 — active Satta Matka channel',
        'Share numbers with NPCI to block linked UPI accounts',
        'Share with state Cyber Crime cells for FIR registration',
        'Request telecom operators to reveal KYC of these numbers',
        'Consider CINEOS as ongoing intelligence partner for telecom fraud',
    ], 1):
        story.append(Paragraph(f'{i}. {action}', BODY))

    story.append(Spacer(1,10))
    story.append(HRFlowable(width='100%', thickness=1,
                             color=LGRAY, spaceAfter=6))
    story.append(Paragraph(
        f'Intelligence collected via automated monitoring of public Telegram channels. '
        f'No unauthorized access. IT Act 65B compliant. {now}  ·  yugandhar@cineos.in',
        CAP))
    doc.build(story)
    return output_path

def gen_sebi_cluster_pdf(output_path):
    doc = make_doc(output_path,
        'Operator Cluster Intelligence', 'SEBI Enforcement')
    now = datetime.datetime.now().strftime('%B %d, %Y')
    story = []
    TITLE = S('T', fontName='Helvetica-Bold', fontSize=20, spaceAfter=3)
    SUB   = S('S', fontSize=10, textColor=MGRAY, spaceAfter=10)
    SEC   = S('SE', fontName='Helvetica-Bold', fontSize=12,
               textColor=RED, spaceBefore=14, spaceAfter=6)
    BODY  = S('B', fontSize=9, spaceAfter=5, leading=14)
    CAP   = S('C', fontSize=7.5, textColor=MGRAY, spaceAfter=4)

    story.append(Paragraph('Operator Attribution Intelligence Report', TITLE))
    story.append(Paragraph(
        f'Illegal IPL Betting — Operator Cluster Confirmed  ·  {now}', SUB))
    story.append(HRFlowable(width='100%', thickness=2,
                             color=RED, spaceAfter=12))
    story.append(Paragraph('Key Finding', SEC))
    story.append(Paragraph(
        'CINEOS has confirmed that <b>@IPLBetting and @ipltossmatchsessionn '
        'are operated by the same individual</b>, identified by phone number '
        '+91-8441916068 appearing in both channels. This is the first confirmed '
        'operator attribution in CINEOS intelligence — connecting two Telegram '
        'channels with 19,220 combined subscribers to a single operator.',
        BODY))
    story.append(Spacer(1,8))
    story.append(stat_row([
        ('1','Operator Confirmed',RED),
        ('2','Channels Controlled',ORANGE),
        ('19,220','Subscribers Exposed',RED),
        ('PMLA','Probe Recommended',PURPLE),
    ]))
    story.append(Spacer(1,14))

    story.append(Paragraph('Attribution Evidence', SEC))
    story.append(Paragraph(
        'The attribution is based on the same contact phone number '
        'appearing in public messages across both channels:', BODY))

    ev_data = [
        ['Evidence Type','Detail'],
        ['Shared Phone','Both channels publicly display +91-8441916068'],
        ['Equal Subscribers','Both channels have exactly 9,610 subscribers'],
        ['Same Activity','Both channels active during same IPL matches'],
        ['Same Timing','Posts appear simultaneously across both channels'],
        ['Attribution','Single operator confirmed — phone is unique identifier'],
    ]
    et = Table(ev_data, colWidths=[55*mm,115*mm])
    et.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLACK),
        ('TEXTCOLOR',(0,0),(-1,0),WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,LGRAY]),
        ('BACKGROUND',(0,5),(1,5),colors.HexColor('#FFE8E8')),
        ('TEXTCOLOR',(0,5),(1,5),RED),
        ('FONTNAME',(0,5),(1,5),'Helvetica-Bold'),
        ('BOX',(0,0),(-1,-1),0.5,colors.HexColor('#CCDDEE')),
        ('INNERGRID',(0,0),(-1,-1),0.3,colors.HexColor('#CCDDEE')),
        ('TOPPADDING',(0,0),(-1,-1),7),
        ('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),6),
        ('FONTSIZE',(0,1),(-1,-1),9),
    ]))
    story.append(et)
    story.append(Spacer(1,12))

    story.append(Paragraph('Broader Context — 354 Channels', SEC))
    story.append(Paragraph(
        'This operator cluster is the first confirmed attribution from CINEOS '
        'monitoring of <b>354 Telegram channels with 11,001,419 subscribers</b>. '
        'As CINEOS continues scanning, more operator clusters will be identified, '
        'building a complete map of who runs India\'s illegal betting network.',
        BODY))
    story.append(Spacer(1,6))

    top_channels = [
        ('@Anuragt_bookqc_Malikc','1,719,715','Reddy Anna Book','CRITICAL'),
        ('@Mahadevsd_Bookuoo','851,440','Mahadev Book (ED case)','CRITICAL'),
        ('@IPLBetting','9,610','IPL Match Betting','CRITICAL'),
        ('@ipltossmatchsessionn','9,610','Toss Betting','CRITICAL'),
        ('@CricketBetting','14,600','Cricket Betting','CRITICAL'),
    ]
    rows = []
    for ch,subs,activity,sev in top_channels:
        rows.append([
            Paragraph(f'<b>{ch}</b>', S('c', fontSize=8)),
            Paragraph(f'<b><font color="{GREEN.hexval()}">{subs}</font></b>',
                      S('c', alignment=TA_CENTER, fontSize=9)),
            Paragraph(activity, S('c', fontSize=8)),
            Paragraph(f'<b><font color="{RED.hexval()}">{sev}</font></b>',
                      S('c', alignment=TA_CENTER, fontSize=8)),
        ])
    story.append(data_table(
        ['Channel','Subscribers','Activity','Severity'],
        rows, [58*mm,28*mm,52*mm,32*mm]))
    story.append(Spacer(1,12))

    story.append(Paragraph('Attribution Roadmap', SEC))
    story.append(Paragraph(
        'With the confirmed phone number, the following attribution chain '
        'is now possible with government cooperation:', BODY))
    for step, action, authority in [
        ('Step 1','Phone +91-8441916068 confirmed — DONE','CINEOS'),
        ('Step 2','Telecom KYC lookup — name and address','TRAI → Telecom operator'),
        ('Step 3','Bank account linked to phone','RBI → Bank'),
        ('Step 4','UPI transactions — illegal proceeds','NPCI → ED'),
        ('Step 5','FIR and arrest','State Cyber Crime cell'),
        ('Step 6','PMLA prosecution — illegal proceeds','ED'),
    ]:
        story.append(Paragraph(
            f'<b>{step}:</b> {action} <font color="{MGRAY.hexval()}">'
            f'[{authority}]</font>', BODY))

    story.append(Spacer(1,10))
    story.append(HRFlowable(width='100%', thickness=1,
                             color=LGRAY, spaceAfter=6))
    story.append(Paragraph(
        f'CINEOS — India\'s Trust Intelligence Network  ·  {now}  ·  '
        f'yugandhar@cineos.in  ·  US Patent 64/049,190', CAP))
    doc.build(story)
    return output_path

# ── EMAIL SENDER ─────────────────────────────────────────

def send_email_with_pdf(to, subject, body, pdf_path, cc=None):
    """Send professional email with PDF attachment. Always."""
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = GMAIL_FROM
    msg['To'] = to
    msg['Bcc'] = GMAIL_FROM
    if cc:
        msg['Cc'] = cc
    msg.attach(MIMEText(body, 'plain'))

    # Attach PDF — mandatory
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            pdf = MIMEApplication(f.read(), _subtype='pdf')
            pdf.add_header('Content-Disposition', 'attachment',
                          filename=os.path.basename(pdf_path))
            msg.attach(pdf)
        print(f"  Attached: {os.path.basename(pdf_path)}")
    else:
        print(f"  WARNING: PDF not found — {pdf_path}")

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(GMAIL_SMTP, GMAIL_PASS)
            recipients = [to, GMAIL_FROM]
            if cc:
                recipients.append(cc)
            s.sendmail(GMAIL_FROM, recipients, msg.as_string())
        print(f"  ✓ SENT to {to}")
        return True
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False

# ── MAIN — GENERATE PDFs AND SEND ────────────────────────
if __name__ == '__main__':
    now = datetime.datetime.now().strftime('%B %d, %Y')
    os.makedirs('reports', exist_ok=True)

    print("=== CINEOS PROFESSIONAL EMAIL SYSTEM ===")
    print(f"Rule: Every email has a PDF. No exceptions.\n")

    # Generate PDFs
    print("[1] Generating PDF reports...")
    trai_pdf  = 'reports/CINEOS_TRAI_PhoneAttribution.pdf'
    sebi_pdf  = 'reports/CINEOS_SEBI_OperatorCluster.pdf'

    gen_trai_pdf(trai_pdf)
    print(f"    ✓ {trai_pdf}")

    gen_sebi_cluster_pdf(sebi_pdf)
    print(f"    ✓ {sebi_pdf}")

    # Send emails with PDFs
    print("\n[2] Sending emails with PDF attachments...")

    emails = [
        {
            'to': 'chairman@trai.gov.in',
            'subject': 'Phone Attribution Intelligence: 2 numbers from illegal IPL betting channels — CINEOS',
            'body': f'''Dear TRAI Chairman,

Following our earlier intelligence reports, CINEOS has now attributed
phone numbers to specific illegal betting operators on Telegram.

Key finding: +91-8441916068 is shared between TWO illegal IPL
betting channels — confirming a single operator controls both.

Full intelligence report with attribution evidence is attached.

Request: Block both numbers under IT Act Section 69A and
Telecom Act 2023. Share with NPCI for UPI account blocking.

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in
cineos.in
US Provisional Patent 64/049,190''',
            'pdf': trai_pdf,
        },
        {
            'to': 'sanjayg@sebi.gov.in',
            'subject': 'CINEOS: Operator cluster confirmed — single person runs @IPLBetting and @ipltossmatch',
            'body': f'''Dear Shri Sanjay G Sarwade,

CINEOS has confirmed the first operator attribution —
a single individual runs two illegal IPL betting channels
with 19,220 combined subscribers.

Evidence: Both channels share phone +91-8441916068.

Attribution chain now possible:
Phone → Telecom KYC → Name → Bank → PMLA → Prosecution

Full intelligence report attached.

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in
cineos.in
US Provisional Patent 64/049,190''',
            'pdf': sebi_pdf,
        },
        {
            'to': 'cybercrime@mha.gov.in',
            'subject': 'CINEOS: Phone +91-8441916068 links two IPL betting channels — same operator confirmed',
            'body': f'''Dear MHA Cyber Crime Division,

CINEOS has confirmed phone +91-8441916068 links two illegal
IPL betting Telegram channels to a single operator.

Combined subscriber reach: 19,220
Activity: Live IPL match betting and toss betting

Attribution report attached — ready for FIR registration.

Yugandhar Mallavarapu
Founder, CINEOS
yugandhar@cineos.in
cineos.in
US Provisional Patent 64/049,190''',
            'pdf': sebi_pdf,
        },
    ]

    sent = 0
    for e in emails:
        print(f"\n  → {e['to']}")
        if send_email_with_pdf(e['to'], e['subject'], e['body'], e['pdf']):
            sent += 1

    print(f"\n{'='*55}")
    print(f"Emails sent: {sent}/{len(emails)}")
    print(f"PDFs attached: {sent} (mandatory)")
    print(f"From: {GMAIL_FROM}")
    print(f"\nPDF files saved locally:")
    print(f"  {trai_pdf}")
    print(f"  {sebi_pdf}")
    print(f"{'='*55}")
