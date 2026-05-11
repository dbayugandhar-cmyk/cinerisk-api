"""
CINEOS PDF Generator

For each alert generates two PDFs:
  1. PUBLIC  — detection + what we defend (send to companies)
  2. INTERNAL — complete end-to-end (send after payment)
"""
import json, os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

W, H = A4
GREEN  = colors.HexColor('#166534')
GREEN2 = colors.HexColor('#F0FDF4')
GREEN3 = colors.HexColor('#BBF7D0')
RED    = colors.HexColor('#DC2626')
AMBER  = colors.HexColor('#D97706')
AMBER2 = colors.HexColor('#FFFBEB')
GRAY   = colors.HexColor('#F8FAFC')
DARK   = colors.HexColor('#0F172A')
MID    = colors.HexColor('#475569')
LIGHT  = colors.HexColor('#94A3B8')
BORDER = colors.HexColor('#E2E8F0')
WHITE  = colors.white

def styles():
    s = getSampleStyleSheet()
    base = dict(fontName='Helvetica', textColor=DARK)

    def ps(name, **kw):
        return ParagraphStyle(name, **{**base, **kw})

    return {
        'title':    ps('t', fontSize=22, fontName='Helvetica-Bold',
                        textColor=DARK, spaceAfter=4),
        'subtitle': ps('st', fontSize=12, textColor=MID,
                        spaceAfter=16),
        'h1':       ps('h1', fontSize=14, fontName='Helvetica-Bold',
                        textColor=GREEN, spaceBefore=14, spaceAfter=6),
        'h2':       ps('h2', fontSize=11, fontName='Helvetica-Bold',
                        textColor=DARK, spaceBefore=10, spaceAfter=4),
        'body':     ps('b', fontSize=9, textColor=MID,
                        leading=14, spaceAfter=4),
        'mono':     ps('m', fontSize=8, fontName='Courier',
                        textColor=DARK, leading=12,
                        backColor=GRAY, leftIndent=8,
                        rightIndent=8, spaceAfter=6),
        'label':    ps('lb', fontSize=7, fontName='Helvetica-Bold',
                        textColor=LIGHT, spaceBefore=6, spaceAfter=2),
        'value':    ps('v', fontSize=9, textColor=DARK,
                        leading=13, spaceAfter=3),
        'redacted': ps('r', fontSize=9, textColor=LIGHT,
                        leading=13, fontName='Helvetica-Oblique'),
        'footer':   ps('f', fontSize=7, textColor=LIGHT,
                        alignment=TA_CENTER),
        'center':   ps('c', fontSize=9, textColor=MID,
                        alignment=TA_CENTER),
        'green':    ps('g', fontSize=10, fontName='Helvetica-Bold',
                        textColor=GREEN),
    }

def header_table(title, subtitle, badge, badge_color):
    """Green header block."""
    data = [[
        Paragraph(f'<font color="white"><b>CINEOS</b></font>',
                  ParagraphStyle('logo', fontSize=14,
                                 fontName='Helvetica-Bold',
                                 textColor=WHITE)),
        Paragraph(f'<font color="white">{title}</font>',
                  ParagraphStyle('ht', fontSize=13,
                                 fontName='Helvetica-Bold',
                                 textColor=WHITE)),
        Paragraph(f'<font color="white">{subtitle}</font>',
                  ParagraphStyle('hs', fontSize=8,
                                 textColor=colors.HexColor('#DCFCE7'))),
    ]]
    t = Table(data, colWidths=[40*mm, 90*mm, 55*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,-1), GREEN),
        ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1), 10),
        ('BOTTOMPADDING',(0,0),(-1,-1), 10),
        ('LEFTPADDING',(0,0),(0,-1), 14),
        ('RIGHTPADDING',(-1,0),(-1,-1), 14),
    ]))
    return t

def kv_row(label, value, S, redact=False):
    style = S['redacted'] if redact else S['value']
    return [
        Paragraph(label, S['label']),
        Paragraph(str(value) if not redact
                  else '[ Available under signed agreement ]',
                  style),
    ]

def chain_table(steps, S):
    """End-to-end chain visualisation."""
    rows = []
    for i, (icon, label, value, sub) in enumerate(steps):
        connector = '→' if i < len(steps)-1 else ''
        rows.append([
            Paragraph(f'{icon}', ParagraphStyle('ic',fontSize=16,
                      alignment=TA_CENTER)),
            Paragraph(f'<b>{label}</b><br/><font size=8 color="#166534">'
                      f'{value}</font><br/>'
                      f'<font size=7 color="#94A3B8">{sub}</font>', S['body']),
            Paragraph(connector, ParagraphStyle('arr',fontSize=14,
                      alignment=TA_CENTER, textColor=GREEN)),
        ])

    t = Table(rows, colWidths=[14*mm, 50*mm, 12*mm]*3 if len(steps)>3
              else [14*mm, 65*mm, 12*mm]*len(steps))
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), GREEN2),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[GREEN2, GRAY]),
        ('GRID',(0,0),(-1,-1), 0.5, GREEN3),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),8),
        ('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('LEFTPADDING',(0,0),(-1,-1),8),
    ]))
    return t

def generate_public_pdf(alert, output_path):
    """
    PUBLIC PDF — send to companies.
    Shows: detection, scale, evidence standard, what we defend.
    Hides: operator names, phones, UPIs, WHOIS registrant.
    """
    S     = styles()
    chain = alert.get('chain', {})
    doc   = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=14*mm, bottomMargin=20*mm)

    today = datetime.now().strftime('%B %d, %Y')
    story = []

    # Header
    story.append(header_table(
        'Fraud Intelligence Report',
        f'Public brief · {today}',
        'DETECTION SUMMARY', GREEN))
    story.append(Spacer(1, 8))

    # Alert title
    sev   = alert['severity'].upper()
    story.append(Paragraph(
        f'<font color="#DC2626">[{sev}]</font>  {alert["title"]}',
        S['title']))
    story.append(Paragraph(alert['detail'], S['subtitle']))
    story.append(HRFlowable(width='100%', color=BORDER, thickness=1))
    story.append(Spacer(1, 8))

    # Detection summary
    story.append(Paragraph('1. What was detected', S['h1']))
    reach = chain.get('reach', 0)
    reach_str = (f"{reach/1e6:.1f} million subscribers"
                 if reach > 999999 else
                 f"{reach:,} subscribers" if reach else 'Not measured')

    det_data = [
        ['Field', 'Finding'],
        ['Category',    alert['category'].replace('_',' ').title()],
        ['Platform',    alert['platform']],
        ['Channels found', str(len(chain.get('channels_found',[])))],
        ['Keywords matched', str(len(chain.get('keywords_matched',[])))],
        ['Combined reach', reach_str],
        ['Detected at',  alert.get('detected_at','')[:16]],
    ]
    t = Table(det_data, colWidths=[55*mm, 120*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), DARK),
        ('TEXTCOLOR',(0,0),(-1,0), WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,GRAY]),
        ('GRID',(0,0),(-1,-1),0.5,BORDER),
        ('LEFTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),
    ]))
    story.append(t)
    story.append(Spacer(1,10))

    # Evidence standard
    story.append(Paragraph('2. Evidence standard', S['h1']))
    story.append(Paragraph(
        f'Every finding in this report is captured under '
        f'<b>IT Act 2000 Section 65B</b> — the Indian standard for '
        f'court-admissible electronic evidence. Each piece of '
        f'intelligence is SHA-256 hashed at the moment of detection '
        f'with a full timestamp and source record.',
        S['body']))
    story.append(Spacer(1, 4))

    hashes = chain.get('evidence_hashes', [])
    legal  = chain.get('legal_basis', 'IT Act 2000 S.65B')
    ev_data = [
        ['Evidence attribute', 'Value'],
        ['Legal basis',        legal],
        ['Evidence hash',      hashes[0] + '...' if hashes else 'On file'],
        ['Captured at',        chain.get('captured_at','')[:16]],
        ['Chain of custody',   'Maintained — available on request'],
        ['Format',             'IT Act S.65B + STIX 2.1'],
    ]
    t2 = Table(ev_data, colWidths=[55*mm, 120*mm])
    t2.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), GREEN),
        ('TEXTCOLOR',(0,0),(-1,0), WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[GREEN2,WHITE]),
        ('GRID',(0,0),(-1,-1),0.5,GREEN3),
        ('LEFTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),
    ]))
    story.append(t2)
    story.append(Spacer(1,10))

    # What we defend
    story.append(Paragraph('3. What CINEOS can defend', S['h1']))
    action   = chain.get('recommended_action','')
    report_to = chain.get('report_to', [])

    story.append(Paragraph(
        f'Based on this intelligence CINEOS recommends and can support '
        f'the following defensive actions:', S['body']))
    story.append(Spacer(1,4))

    if action:
        story.append(Paragraph(f'<b>Recommended action:</b> {action}',
                                S['body']))
    if report_to:
        story.append(Paragraph(
            f'<b>Report to:</b> {", ".join(report_to)}', S['body']))
    story.append(Spacer(1,6))

    defend_data = [
        ['Defence capability', 'Status'],
        ['IT Act S.65B evidence package', 'Ready'],
        ['IT Rules 2021 takedown notice', 'Ready to generate'],
        ['STIX 2.1 law enforcement format','Ready'],
        ['Operator attribution', 'Under signed agreement'],
        ['Full channel database', 'Under signed agreement'],
        ['Phone + UPI intelligence', 'Under signed agreement'],
    ]
    t3 = Table(defend_data, colWidths=[110*mm, 65*mm])
    t3.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), DARK),
        ('TEXTCOLOR',(0,0),(-1,0), WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,GRAY]),
        ('GRID',(0,0),(-1,-1),0.5,BORDER),
        ('LEFTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('TEXTCOLOR',(1,1),(-1,-1),GREEN),
        ('FONTNAME',(1,1),(-1,-1),'Helvetica-Bold'),
    ]))
    story.append(t3)
    story.append(Spacer(1,10))

    # Attribution note
    story.append(Paragraph('4. Full intelligence available', S['h1']))
    box = Table([[
        Paragraph(
            '<b>Complete attribution intelligence is available under '
            'a signed intelligence agreement.</b> This includes: '
            'operator names, phone numbers, UPI IDs, WHOIS registrant '
            'data, network graph access, fraud family trees and '
            'STIX 2.1 feeds.<br/><br/>'
            'Contact: <b>yugandhar@cineos.in</b> | cineos.in<br/>'
            'US Provisional Patent 64/049,190',
            S['body'])
    ]], colWidths=[175*mm])
    box.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), AMBER2),
        ('GRID',(0,0),(-1,-1),1,AMBER),
        ('LEFTPADDING',(0,0),(-1,-1),12),
        ('TOPPADDING',(0,0),(-1,-1),10),
        ('BOTTOMPADDING',(0,0),(-1,-1),10),
    ]))
    story.append(box)
    story.append(Spacer(1,16))

    # Footer
    story.append(HRFlowable(width='100%',color=BORDER,thickness=0.5))
    story.append(Spacer(1,4))
    story.append(Paragraph(
        'CINEOS — India Trust Intelligence Network · cineos.in · '
        'yugandhar@cineos.in · US Provisional Patent 64/049,190 · '
        f'Generated {today} · IT Act 2000 S.65B compliant · '
        'Public data only · No private messages accessed',
        S['footer']))

    doc.build(story)
    return output_path

def generate_full_pdf(alert, output_path):
    """
    FULL PDF — send after payment/signed agreement.
    Shows everything: operator names, phones, UPIs,
    WHOIS, network graph, fraud family tree, end steps.
    """
    S     = styles()
    chain = alert.get('chain', {})
    doc   = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=14*mm, bottomMargin=20*mm)

    today = datetime.now().strftime('%B %d, %Y')
    story = []

    # Header
    story.append(header_table(
        'Full Intelligence Report',
        f'Confidential · {today} · Signed agreement required',
        'COMPLETE ATTRIBUTION', RED))
    story.append(Spacer(1,6))

    # Confidential banner
    banner = Table([[
        Paragraph(
            '<b>CONFIDENTIAL — SIGNED AGREEMENT REQUIRED</b><br/>'
            'This report contains operator names, phone numbers, UPI IDs, '
            'WHOIS registrant data and network attribution intelligence. '
            'Distribution restricted to authorised recipients only.',
            ParagraphStyle('conf', fontSize=8, textColor=RED,
                           fontName='Helvetica-Bold'))
    ]], colWidths=[175*mm])
    banner.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),
         colors.HexColor('#FEF2F2')),
        ('GRID',(0,0),(-1,-1),1,RED),
        ('LEFTPADDING',(0,0),(-1,-1),10),
        ('TOPPADDING',(0,0),(-1,-1),8),
        ('BOTTOMPADDING',(0,0),(-1,-1),8),
    ]))
    story.append(banner)
    story.append(Spacer(1,8))

    sev = alert['severity'].upper()
    story.append(Paragraph(
        f'<font color="#DC2626">[{sev}]</font>  {alert["title"]}',
        S['title']))
    story.append(Paragraph(alert['detail'], S['subtitle']))
    story.append(HRFlowable(width='100%',color=BORDER,thickness=1))
    story.append(Spacer(1,8))

    # 1. DETECTION
    story.append(Paragraph('1. Detection', S['h1']))
    reach = chain.get('reach',0)
    det_data = [
        ['Field','Finding'],
        ['Category',     alert['category'].replace('_',' ').title()],
        ['Platform',     alert['platform']],
        ['Channels',     ', '.join(chain.get('channels_found',[]))[:80]
                         or 'See channel database'],
        ['Keywords',     ', '.join(chain.get('keywords_matched',[]))[:80]],
        ['Reach',        f"{reach/1e6:.1f}M subscribers"
                         if reach>999999 else f"{reach:,}"],
        ['Detected',     alert.get('detected_at','')[:16]],
    ]
    t = Table(det_data, colWidths=[50*mm, 125*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),DARK),
        ('TEXTCOLOR',(0,0),(-1,0),WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,GRAY]),
        ('GRID',(0,0),(-1,-1),0.5,BORDER),
        ('LEFTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),
    ]))
    story.append(t)
    story.append(Spacer(1,10))

    # 2. ATTRIBUTION — FULL DATA
    story.append(Paragraph('2. Full attribution', S['h1']))

    phones   = chain.get('phones',[])
    upis     = chain.get('upis',[])
    op_name  = chain.get('operator_name','Not yet attributed')
    op_net   = chain.get('operator_network','')
    w_domain = chain.get('whois_domain','')
    w_reg    = chain.get('whois_registrant','')

    attr_data = [['Attribution field','Intelligence']]
    attr_data.append(['Operator name',   op_name or 'Pending deep scan'])
    attr_data.append(['Operator network',op_net  or '—'])
    if phones:
        attr_data.append(['Phone numbers',
                          '\n'.join(phones)])
    if upis:
        attr_data.append(['UPI IDs', '\n'.join(upis)])
    if w_domain:
        attr_data.append(['WHOIS domain',     w_domain])
    if w_reg:
        attr_data.append(['WHOIS registrant', w_reg])

    t2 = Table(attr_data, colWidths=[55*mm, 120*mm])
    t2.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),RED),
        ('TEXTCOLOR',(0,0),(-1,0),WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),
         [colors.HexColor('#FEF2F2'),WHITE]),
        ('GRID',(0,0),(-1,-1),0.5,
         colors.HexColor('#FECACA')),
        ('LEFTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('TEXTCOLOR',(1,1),(-1,-1),
         colors.HexColor('#991B1B')),
        ('FONTNAME',(1,1),(-1,-1),'Helvetica-Bold'),
    ]))
    story.append(t2)
    story.append(Spacer(1,10))

    # 3. END-TO-END CHAIN
    story.append(Paragraph('3. End-to-end attribution chain', S['h1']))
    steps = []
    steps.append(('📡','Detect',
                  f"{len(chain.get('channels_found',[]))} channels",
                  f"{len(chain.get('keywords_matched',[]))} keyword signals"))
    if reach:
        steps.append(('👁','Reach',
                      f"{reach/1e6:.1f}M subs" if reach>999999
                      else f"{reach:,}",
                      'subscriber exposure'))
    if op_name:
        steps.append(('👤','Operator',
                      op_name[:25], op_net[:25] if op_net else 'Network mapped'))
    if phones:
        steps.append(('📱','Phones',
                      phones[0], f'+{len(phones)-1} more' if len(phones)>1 else 'Confirmed'))
    if w_reg:
        steps.append(('🌐','WHOIS',
                      w_domain[:20], w_reg[:30]))
    hashes = chain.get('evidence_hashes',[])
    steps.append(('⚖','Evidence',
                  chain.get('legal_basis','IT Act S.65B').split('+')[0].strip(),
                  hashes[0][:14]+'...' if hashes else 'Hashed'))
    action = chain.get('recommended_action','')
    if action:
        steps.append(('📋','End step',
                      action[:35]+'...' if len(action)>35 else action,
                      ', '.join(chain.get('report_to',[])[:2])))

    # Split into rows of 3
    for i in range(0, len(steps), 3):
        chunk = steps[i:i+3]
        story.append(chain_table(chunk, S))
        story.append(Spacer(1,6))

    story.append(Spacer(1,4))

    # 4. EVIDENCE
    story.append(Paragraph('4. Evidence package', S['h1']))
    legal = chain.get('legal_basis','IT Act 2000 S.65B')
    story.append(Paragraph(
        f'Legal basis: <b>{legal}</b><br/>'
        f'Hash: <b>{", ".join(hashes)}</b><br/>'
        f'Captured: <b>{chain.get("captured_at","")[:16]}</b><br/>'
        f'Standard: IT Act 2000 S.65B — court admissible in India',
        S['body']))
    story.append(Spacer(1,10))

    # 5. RECOMMENDED ACTIONS
    story.append(Paragraph('5. Recommended actions', S['h1']))
    if action:
        story.append(Paragraph(f'<b>Immediate:</b> {action}', S['body']))
    report_to = chain.get('report_to',[])
    if report_to:
        for r in report_to:
            story.append(Paragraph(f'  • Report to: <b>{r}</b>', S['body']))
    story.append(Spacer(1,10))

    # Footer
    story.append(HRFlowable(width='100%',color=BORDER,thickness=0.5))
    story.append(Spacer(1,4))
    story.append(Paragraph(
        'CINEOS — India Trust Intelligence Network · CONFIDENTIAL · '
        'Authorised recipients only · cineos.in · yugandhar@cineos.in · '
        f'US Provisional Patent 64/049,190 · Generated {today} · '
        'IT Act 2000 S.65B · All data from public sources',
        S['footer']))

    doc.build(story)
    return output_path

def generate_both(alert):
    """Generate both PDFs for one alert. Returns (public_path, full_path)."""
    a_id  = alert.get('id','x')[:8]
    title = alert.get('title','alert').replace(' ','_')[:30]
    safe  = ''.join(c if c.isalnum() or c=='_' else '_' for c in title)

    os.makedirs('reports/pdfs', exist_ok=True)
    pub  = f"reports/pdfs/{safe}_{a_id}_PUBLIC.pdf"
    full = f"reports/pdfs/{safe}_{a_id}_FULL.pdf"

    generate_public_pdf(alert, pub)
    generate_full_pdf(alert, full)
    return pub, full

if __name__ == '__main__':
    from cineos_alert_engine import load_alerts, seed

    alerts = load_alerts()
    if not alerts:
        print("Seeding alerts first...")
        seed()
        alerts = load_alerts()

    print(f"Generating PDFs for top 3 alerts...")
    for a in alerts[:3]:
        pub, full = generate_both(a)
        print(f"  PUBLIC: {pub}")
        print(f"  FULL:   {full}")
    print("Done.")
