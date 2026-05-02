# Run on your Mac: python3 create_report_v2.py
# Creates report_v2.py in ~/Desktop/cinerisk/
# report_v2.py calls the API instead of its own logic
import os

code = r'''#!/usr/bin/env python3
"""
CineRisk Report Generator v2
=============================
Calls the API (engine.py via api.py) for all data.
No calculation logic here — pure PDF rendering.

Usage:
  # API must be running: python3 -m uvicorn api:app --reload --port 8000
  python3 report_v2.py --genre action --hype high --strategy staggered --budget 180 --title "Nova Station" --client "Meridian Pictures"
  python3 report_v2.py --genre thriller --hype medium --strategy staggered --budget 65 --title "Deep Water"
"""

import sys, os, json, argparse, requests
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, PageBreak, Flowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

API = os.getenv("CINERISK_API", "http://localhost:8000")

# ── Colours ───────────────────────────────────────────────────────────
BG=colors.HexColor("#07090c"); SU=colors.HexColor("#0c0f14")
SU2=colors.HexColor("#111620"); BO=colors.HexColor("#1c232e")
GOLD=colors.HexColor("#c9a84c"); RED=colors.HexColor("#d94f4f")
GREEN=colors.HexColor("#3db87a"); TX=colors.HexColor("#dde1e8")
T2=colors.HexColor("#7a8494"); T3=colors.HexColor("#3a4150")
W,H=A4; MG=18*mm; CW=W-22*mm-MG

# ── Styles ────────────────────────────────────────────────────────────
def S(n,**k): return ParagraphStyle(n,**k)
ST={
    "tag":   S("tag",  fontName="Helvetica-Bold", fontSize=7,  textColor=T3,   spaceAfter=4, spaceBefore=12, letterSpacing=1.8),
    "h1":    S("h1",   fontName="Helvetica-Bold", fontSize=20, textColor=TX,   spaceAfter=6, leading=24),
    "h2":    S("h2",   fontName="Helvetica-Bold", fontSize=14, textColor=TX,   spaceAfter=5, spaceBefore=4, leading=18),
    "h3":    S("h3",   fontName="Helvetica-Bold", fontSize=10, textColor=TX,   spaceAfter=3, leading=13),
    "body":  S("body", fontName="Helvetica",      fontSize=9,  textColor=T2,   spaceAfter=5, leading=14),
    "bodyw": S("bodyw",fontName="Helvetica",       fontSize=9,  textColor=TX,   spaceAfter=5, leading=14),
    "small": S("small",fontName="Helvetica",       fontSize=8,  textColor=T3,   spaceAfter=3, leading=11),
    "mono":  S("mono", fontName="Courier",         fontSize=8,  textColor=GOLD, spaceAfter=3, leading=11),
    "clause":S("clause",fontName="Helvetica",      fontSize=8.5,textColor=T2,   spaceAfter=5, leading=13),
    "kl":    S("kl",   fontName="Helvetica",       fontSize=7,  textColor=T3,   spaceAfter=0, leading=10, letterSpacing=0.8),
}

def rc(s):
    return "#d94f4f" if s>=0.70 else ("#c9a84c" if s>=0.45 else "#3db87a")

def rl(s):
    return "HIGH" if s>=0.70 else ("MEDIUM" if s>=0.45 else "LOW")

def strat_label(s):
    return {"global_day1":"Global Day-One","staggered":"Staggered","streaming_delay":"Streaming Delay"}.get(s,s)

class Bar(Flowable):
    def __init__(self,score,w=200,h=6): super().__init__(); self._w=w; self._h=h; self.score=score
    def wrap(self,aw,ah): return self._w,self._h+4
    def draw(self):
        c=self.canv; c.setFillColor(BO); c.rect(0,2,self._w,self._h,fill=1,stroke=0)
        c.setFillColor(colors.HexColor(rc(self.score))); c.rect(0,2,self._w*(self.score),self._h,fill=1,stroke=0)

# ── Page templates ────────────────────────────────────────────────────
def make_pages(film_title, client, date, risk_score, expiry=""):
    def cover(c,doc):
        c.setFillColor(BG);    c.rect(0,0,W,H,fill=1,stroke=0)
        c.setFillColor(GOLD);  c.rect(0,H-8*mm,W,8*mm,fill=1,stroke=0)
        c.setFillColor(SU2);   c.rect(0,0,14*mm,H-8*mm,fill=1,stroke=0)
        c.setFillColor(BO);    c.rect(14*mm,0,0.5,H-8*mm,fill=1,stroke=0)
        c.setFillColor(SU);    c.rect(0,0,W,42*mm,fill=1,stroke=0)
        c.setFillColor(BO);    c.rect(0,42*mm,W,0.5,fill=1,stroke=0)
        c.saveState(); c.setFillColor(T3); c.setFont("Helvetica",7)
        c.translate(9*mm,H/2); c.rotate(90); c.drawCentredString(0,0,"CINERISK — ENGINE v1 — SINGLE SOURCE OF TRUTH"); c.restoreState()
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold",24); c.drawString(22*mm,H-30*mm,"CINE")
        c.setFillColor(GOLD); c.drawString(22*mm+45,H-30*mm,"RISK")
        c.setFillColor(T3); c.setFont("Helvetica",7); c.drawString(22*mm,H-35*mm,"RELEASE INTELLIGENCE PLATFORM  ·  ENGINE v1")
        c.setFillColor(GOLD); c.setFont("Helvetica-Bold",9); c.drawString(22*mm,H*0.60+10,"RELEASE RISK INTELLIGENCE REPORT")
        c.setFillColor(TX); c.setFont("Helvetica-Bold",32); c.drawString(22*mm,H*0.60-22,film_title.upper() if film_title else "UNTITLED")
        rco=colors.HexColor(rc(risk_score)); lbl=rl(risk_score)+" RISK"
        c.setFillColor(rco); c.setFont("Helvetica-Bold",72); c.drawString(22*mm,H*0.60-96,f"{risk_score:.2f}")
        c.setFont("Helvetica-Bold",10); c.drawString(22*mm,H*0.60-110,lbl)
        c.setFillColor(GOLD); c.rect(22*mm,H*0.60-118,38*mm,1.5,fill=1,stroke=0)
        c.setFillColor(T2); c.setFont("Helvetica",8)
        c.drawString(22*mm,26*mm,f"Prepared for: {client}")
        c.drawString(22*mm,19*mm,f"Date: {date}")
        c.setFillColor(T3); c.setFont("Helvetica",7)
        c.drawString(22*mm,12*mm,"Confidential — CineRisk Intelligence  ·  All figures from Engine v1")
        c.drawRightString(W-MG,12*mm,"Page 1 of 4")

    def inner(c,doc):
        c.setFillColor(BG);   c.rect(0,0,W,H,fill=1,stroke=0)
        c.setFillColor(SU2);  c.rect(0,0,14*mm,H,fill=1,stroke=0)
        c.setFillColor(BO);   c.rect(14*mm,0,0.5,H,fill=1,stroke=0)
        c.setFillColor(SU);   c.rect(14*mm,H-14*mm,W-14*mm,14*mm,fill=1,stroke=0)
        c.setFillColor(GOLD); c.rect(14*mm,H-14*mm,W-14*mm,1,fill=1,stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold",8); c.drawString(22*mm,H-9*mm,"CINE")
        c.setFillColor(GOLD); c.drawString(22*mm+18,H-9*mm,"RISK")
        c.setFillColor(T2); c.setFont("Helvetica",7)
        title_str = (film_title.upper()+" — " if film_title else "")+"RELEASE RISK REPORT"
        c.drawCentredString(W/2+7*mm,H-9*mm,title_str)
        c.setFillColor(T3); c.drawRightString(W-MG,H-9*mm,f"Page {doc.page} of 4")
        c.setFillColor(SU);  c.rect(14*mm,0,W-14*mm,10*mm,fill=1,stroke=0)
        c.setFillColor(BO);  c.rect(14*mm,10*mm,W-14*mm,0.5,fill=1,stroke=0)
        c.setFillColor(T3); c.setFont("Helvetica",7)
        c.drawString(22*mm,4*mm,f"Engine v1 output — {date}  ·  CineRisk Intelligence")
        c.drawRightString(W-MG,4*mm,"Confidential")
        c.saveState(); c.setFillColor(T3); c.setFont("Helvetica",7)
        c.translate(9*mm,H/2); c.rotate(90); c.drawCentredString(0,0,"CINERISK ENGINE v1"); c.restoreState()

    def on_page(c,doc): cover(c,doc) if doc.page==1 else inner(c,doc)
    return on_page

# ── Fetch from API ────────────────────────────────────────────────────
def fetch_simulation(genre, hype, strategy, budget, title=None):
    print(f"  Calling API: POST {API}/simulate")
    r = requests.post(f"{API}/simulate", json={
        "genre": genre, "hype": hype, "strategy": strategy,
        "budget_m": budget, "film_title": title
    }, timeout=10)
    r.raise_for_status()
    data = r.json()
    print(f"  Engine returned: recommended={data['recommended']}")
    return data

# ── Build PDF from API data ───────────────────────────────────────────
def build_pdf(data, client, output_path):
    film_title = data.get("film_title") or "Untitled"
    date_str   = datetime.now().strftime("%B %d, %Y")
    current    = next(s for s in data["strategies"] if s["strategy"]==data["current_strategy"])
    recommended= next(s for s in data["strategies"] if s["strategy"]==data["recommended"])
    risk_score = current["risk_score"]

    on_page = make_pages(film_title, client, date_str, risk_score)

    doc = SimpleDocTemplate(output_path, pagesize=A4,
        leftMargin=22*mm, rightMargin=MG, topMargin=20*mm, bottomMargin=16*mm)
    story = [Spacer(1,1), PageBreak()]

    # ── PAGE 2: Summary ──────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", ST["tag"]))
    story.append(Paragraph(f"{film_title} — Engine v1 Risk Assessment", ST["h1"]))
    story.append(Spacer(1,4))

    # KPI row
    def kpi_cell(val,lbl,col):
        return [
            Paragraph(f'<font color="{col}" size="22"><b>{val}</b></font>',
                      ParagraphStyle("kv",fontName="Helvetica-Bold",fontSize=22,textColor=TX,leading=26,spaceAfter=2)),
            Paragraph(lbl.upper(), ST["kl"])
        ]
    kpi_data = [[
        kpi_cell(f"{current['risk_score']:.2f}", "Risk Score", rc(current["risk_score"])),
        kpi_cell(f"D+{current['leak_day_low']}–{current['leak_day_high']}", "Leak Window", "#d94f4f"),
        kpi_cell(f"${current['revenue_low']}M–${current['revenue_high']}M", "Revenue Range", "#3db87a"),
        kpi_cell(f"{current['confidence']*100:.0f}%", "Confidence", "#c9a84c"),
    ]]
    kt = Table(kpi_data, colWidths=[CW/4]*4)
    kt.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),("BACKGROUND",(0,0),(-1,-1),SU),
        ("LINEAFTER",(0,0),(-2,-1),0.5,BO),
        ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
        ("LEFTPADDING",(0,0),(-1,-1),14),
    ]))
    story.append(kt); story.append(Spacer(1,12))

    # Recommendation box
    rec_data=[[Paragraph(f'<font color="{rc(recommended["risk_score"])}"><b>RECOMMENDED: {strat_label(data["recommended"]).upper()}</b></font>',ST["h3"])],
              [Paragraph(data["recommendation_text"], ST["body"])]]
    rt=Table(rec_data,colWidths=[CW])
    rt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),SU2),("LINEBEFORE",(0,0),(-1,-1),3,GOLD),
        ("TOPPADDING",(0,0),(-1,-1),12),("BOTTOMPADDING",(0,0),(-1,-1),12),
        ("LEFTPADDING",(0,0),(-1,-1),14),("RIGHTPADDING",(0,0),(-1,-1),12)]))
    story.append(rt); story.append(Spacer(1,12))

    # Input params
    story.append(Paragraph("Simulation Inputs", ST["tag"]))
    params=[
        ["Genre", data["genre"].title(), "Hype Level", data["hype"].title()],
        ["Current Strategy", strat_label(data["current_strategy"]), "Budget", f"${data['budget_m']}M"],
        ["Engine Version", "v1 — single source of truth", "Confidence", f"{current['confidence']*100:.0f}%"],
    ]
    pt=Table(params,colWidths=[36*mm,54*mm,36*mm,54*mm])
    pt.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),8.5),
        ("TEXTCOLOR",(0,0),(0,-1),T3),("TEXTCOLOR",(1,0),(1,-1),TX),
        ("TEXTCOLOR",(2,0),(2,-1),T3),("TEXTCOLOR",(3,0),(3,-1),TX),
        ("FONTNAME",(1,0),(1,-1),"Helvetica-Bold"),("FONTNAME",(3,0),(3,-1),"Helvetica-Bold"),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[SU,SU2]),
        ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
        ("LEFTPADDING",(0,0),(-1,-1),10),("GRID",(0,0),(-1,-1),0.3,BO),
    ]))
    story.append(pt); story.append(PageBreak())

    # ── PAGE 3: Strategy comparison ──────────────────────────────────
    story.append(Paragraph("Strategy Comparison", ST["tag"]))
    story.append(Paragraph("All 3 Strategies — Engine Output", ST["h1"]))
    story.append(Spacer(1,6))

    sh=[Paragraph(f'<font color="#3a4150"><b>{x}</b></font>',ST["small"])
        for x in ["STRATEGY","RISK","RISK LEVEL","REVENUE RANGE","LEAK WINDOW","CONFIDENCE"]]
    srows=[sh]
    for s in data["strategies"]:
        is_rec = s["strategy"]==data["recommended"]
        is_cur = s["strategy"]==data["current_strategy"]
        nm = f'<b>{strat_label(s["strategy"])}</b>'
        if is_rec: nm += ' <font color="#3db87a" size="7"> REC</font>'
        if is_cur and not is_rec: nm += ' <font color="#c9a84c" size="7"> CURRENT</font>'
        srows.append([
            Paragraph(nm, ST["bodyw"] if is_rec or is_cur else ST["body"]),
            Paragraph(f'<font color="{rc(s["risk_score"])}"><b>{s["risk_score"]:.2f}</b></font>',ST["body"]),
            Paragraph(f'<font color="{rc(s["risk_score"])}">{rl(s["risk_score"])}</font>',ST["body"]),
            Paragraph(f'<font color="#3db87a">${s["revenue_low"]}M–${s["revenue_high"]}M</font>',ST["body"]),
            Paragraph(f'<font color="#d94f4f">Day {s["leak_day_low"]}–{s["leak_day_high"]}</font>',ST["body"]),
            Paragraph(f'<font color="#7a8494">{s["confidence"]*100:.0f}%</font>',ST["body"]),
        ])
    sc=Table(srows,colWidths=[CW*.29,CW*.09,CW*.12,CW*.22,CW*.16,CW*.12])
    sc.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),SU2),("ROWBACKGROUNDS",(0,1),(-1,-1),[SU,SU2]),
        ("GRID",(0,0),(-1,-1),0.3,BO),
        ("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9),
        ("LEFTPADDING",(0,0),(-1,-1),10),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    story.append(sc); story.append(Spacer(1,16))

    # Revenue bar chart
    story.append(Paragraph("Revenue Range Comparison", ST["tag"]))
    bw = CW-56*mm; mx=max(s["revenue_high"] for s in data["strategies"])
    brows=[]
    for s in data["strategies"]:
        pct = s["revenue_high"]/mx if mx>0 else 0
        bc="#3db87a" if s["strategy"]==data["recommended"] else "#5b9cf6"
        brows.append([
            Paragraph(strat_label(s["strategy"]),ST["small"]),
            Bar(pct,w=int(bw),h=14),
            Paragraph(f'<font color="{bc}"><b>${s["revenue_low"]}M–${s["revenue_high"]}M</b></font>',ST["body"]),
        ])
    bt=Table(brows,colWidths=[54*mm,bw,CW-54*mm-bw])
    bt.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story.append(bt); story.append(PageBreak())

    # ── PAGE 4: Explanation + Actions ────────────────────────────────
    story.append(Paragraph("Engine Explanation", ST["tag"]))
    story.append(Paragraph(f"Why This Result — {strat_label(data['current_strategy'])}", ST["h1"]))
    story.append(Spacer(1,8))
    story.append(Paragraph(
        "The following explanation is generated directly by the engine's logic layer, "
        "not post-hoc rationalisation. Every factor below contributed to the risk score above.",
        ST["body"]
    ))
    story.append(Spacer(1,10))

    for i,line in enumerate(current["explanation"],1):
        erow=Table([[
            Paragraph(f'<font color="#c9a84c"><b>0{i}</b></font>',ST["h3"]),
            Paragraph(line, ST["body"])
        ]],colWidths=[14*mm,CW-14*mm])
        erow.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),SU if i%2==1 else SU2),
            ("GRID",(0,0),(-1,-1),0.3,BO),
            ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
            ("LEFTPADDING",(0,0),(-1,-1),12),("VALIGN",(0,0),(-1,-1),"TOP"),
        ]))
        story.append(erow); story.append(Spacer(1,3))

    story.append(Spacer(1,14))
    story.append(HRFlowable(width="100%",thickness=0.5,color=BO,spaceAfter=12,spaceBefore=4))

    # Confidence note
    conf_data=[[Paragraph(
        f"<b>Model Confidence: {current['confidence']*100:.0f}%</b> — "
        "This score reflects the reliability of the engine's prediction for this specific "
        "genre/hype/strategy combination based on the confidence table calibrated against "
        "historical comparable title data. Revenue figures are ranges, not point estimates. "
        "All outputs are from Engine v1 — identical to dashboard figures.",
        ST["clause"]
    )]]
    ct=Table(conf_data,colWidths=[CW])
    ct.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),SU2),("TOPPADDING",(0,0),(-1,-1),10),
        ("BOTTOMPADDING",(0,0),(-1,-1),10),("LEFTPADDING",(0,0),(-1,-1),12),
        ("LINEBEFORE",(0,0),(-1,-1),3,GOLD),("GRID",(0,0),(-1,-1),0.3,BO),
    ]))
    story.append(ct)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"  Report saved: {output_path}")
    return output_path

# ── CLI ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="CineRisk Report Generator v2 — API-powered")
    p.add_argument("--genre",    required=True, choices=["action","scifi","thriller","horror","drama","animation"])
    p.add_argument("--hype",     required=True, choices=["low","medium","high"])
    p.add_argument("--strategy", required=True, choices=["global_day1","staggered","streaming_delay"])
    p.add_argument("--budget",   type=float, default=100.0)
    p.add_argument("--title",    default=None)
    p.add_argument("--client",   default="Confidential Client")
    p.add_argument("--output",   default=None)
    args = p.parse_args()

    print(f"\nCineRisk Report Generator v2")
    print(f"  Film:     {args.title or 'Untitled'}")
    print(f"  Inputs:   {args.genre} / {args.hype} / {args.strategy} / ${args.budget}M")
    print(f"  Client:   {args.client}")
    print(f"  API:      {API}")

    try:
        data = fetch_simulation(args.genre, args.hype, args.strategy, args.budget, args.title)
    except requests.exceptions.ConnectionError:
        print(f"\n  ERROR: Cannot connect to API at {API}")
        print("  Make sure the API is running:")
        print("    python3 -m uvicorn api:app --reload --port 8000\n")
        sys.exit(1)

    safe = (args.title or "report").replace(" ","_").replace("/","_")
    out  = args.output or os.path.expanduser(f"~/Desktop/cinerisk/CineRisk_{safe}_Report.pdf")
    build_pdf(data, args.client, out)
    print(f"\n  Opening report...")
    os.system(f"open '{out}'")
    print(f"  Done.\n")
'''

path = os.path.expanduser("~/Desktop/cinerisk/report_v2.py")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    f.write(code.strip())
print(f"Created: {path}")
print("\nUsage (API must be running first):")
print('  python3 report_v2.py --genre action --hype high --strategy staggered --budget 180 --title "Nova Station" --client "Meridian Pictures"')
