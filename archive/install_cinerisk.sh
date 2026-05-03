#!/bin/bash
# CineRisk one-line installer
# Run: bash install_cinerisk.sh

echo "Creating CineRisk folder..."
mkdir -p ~/Desktop/cinerisk
cd ~/Desktop/cinerisk

echo "Installing dependencies..."
python3 -m pip install reportlab requests python-dotenv --quiet

echo "Creating generate_report.py..."
cat > generate_report.py << 'PYEOF'
#!/usr/bin/env python3
import sys, os, requests
from datetime import datetime
try:
    from dotenv import load_dotenv; load_dotenv()
except: pass

TMDB_KEY = os.getenv("TMDB_API_KEY","")
TMDB_BASE = "https://api.themoviedb.org/3"

def search_film(title):
    if not TMDB_KEY: return None
    r = requests.get(f"{TMDB_BASE}/search/movie",params={"api_key":TMDB_KEY,"query":title},timeout=10)
    results = r.json().get("results",[])
    return sorted(results,key=lambda x:x.get("popularity",0),reverse=True)[0] if results else None

def get_details(tmdb_id):
    if not TMDB_KEY: return None
    r = requests.get(f"{TMDB_BASE}/movie/{tmdb_id}",params={"api_key":TMDB_KEY,"append_to_response":"credits,release_dates"},timeout=10)
    return r.json()

def calc_risk(genre,budget,franchise,strategy,gap,buzz):
    r=30
    if genre in ["Action","Science Fiction","Thriller","Adventure","Fantasy"]: r+=15
    if budget>150:r+=18
    elif budget>80:r+=12
    elif budget>30:r+=6
    if franchise:r+=12
    if strategy=="staggered":r+=20
    elif strategy=="global":r-=6
    if gap<4:r+=14
    elif gap<7:r+=8
    elif gap>14:r-=10
    if buzz>80:r+=10
    elif buzz>50:r+=5
    elif buzz<10:r-=6
    return min(96,max(8,round(r)))

def calc_leak(risk,strategy):
    base={"global":22,"staggered":7,"hybrid":14}.get(strategy,14)
    return max(3,round(base-(risk-50)*0.14))

def calc_rev(budget,risk,buzz,genre):
    gm={"Action":2.8,"Science Fiction":2.6,"Adventure":2.7,"Animation":3.2,
        "Thriller":1.9,"Horror":2.1,"Drama":1.5,"Comedy":1.8}.get(genre,2.0)
    return round(budget*max(0.6,gm-(risk/100)*0.9+(buzz/150)*0.4))

def risk_col(s): return '#e05252' if s>=70 else ('#e8a020' if s>=45 else '#3dd68c')
def risk_lbl(s): return 'HIGH' if s>=70 else ('MEDIUM' if s>=45 else 'LOW')

def assemble(title,distributor):
    print(f"\nFetching: {title}")
    film={"title":title,"genre":"Action","genres":["Action"],"budget":150,"franchise":True,
          "strategy":"staggered","strategy_label":"Staggered by region","gap":6,"buzz":60.0,
          "director":"Unknown","cast":[],"release_year":str(datetime.now().year),
          "runtime":120,"rating":"PG-13","overview":"",
          "prepared_for":distributor,"prepared_by":"CineRisk Intelligence",
          "date":datetime.now().strftime("%B %Y")}
    result=search_film(title)
    if result:
        details=get_details(result["id"])
        if details:
            genres=[g["name"] for g in details.get("genres",[])]
            film["genre"]=genres[0] if genres else "Action"
            film["genres"]=genres
            b=details.get("budget",0); rv=details.get("revenue",0)
            film["budget"]=round(b/1e6) if b>0 else (round(rv/3e6) if rv>0 else 80)
            film["franchise"]=details.get("belongs_to_collection") is not None
            film["strategy"]="staggered" if len(details.get("production_countries",[]))>1 else "global"
            film["strategy_label"]="Staggered by region" if film["strategy"]=="staggered" else "Global simultaneous"
            gmap={"Action":6,"Science Fiction":5,"Thriller":7,"Horror":5,"Animation":10,"Drama":14}
            film["gap"]=gmap.get(film["genre"],8)
            film["buzz"]=round(min(150,max(5,details.get("popularity",20)*0.8)),1)
            crew=details.get("credits",{}).get("crew",[])
            dirs=[c["name"] for c in crew if c["job"]=="Director"]
            film["director"]=dirs[0] if dirs else "Unknown"
            cast=details.get("credits",{}).get("cast",[])[:3]
            film["cast"]=[c["name"] for c in cast]
            film["release_year"]=(details.get("release_date","")[:4] or str(datetime.now().year))
            film["runtime"]=details.get("runtime",0)
            film["overview"]=details.get("overview","")
            print(f"  Found: {details.get('title',title)} | Genre: {film['genre']} | Budget: ${film['budget']}M")
    else:
        print("  Using demo data (add TMDB_API_KEY to .env for real data)")

    film["risk"]=calc_risk(film["genre"],film["budget"],film["franchise"],film["strategy"],film["gap"],film["buzz"])
    film["leak_day"]=calc_leak(film["risk"],film["strategy"])
    film["rev"]=calc_rev(film["budget"],film["risk"],film["buzz"],film["genre"])
    film["at_risk"]=round(film["rev"]*(film["risk"]/100)*0.38)
    film["net"]=film["rev"]-film["at_risk"]

    strats=[("Global simultaneous","global",4),("Staggered by region","staggered",film["gap"]),("Hybrid release","hybrid",6)]
    film["scenarios"]=[]
    for nm,st,gp in strats:
        r=calc_risk(film["genre"],film["budget"],film["franchise"],st,gp,film["buzz"])
        rv=calc_rev(film["budget"],r,film["buzz"],film["genre"])
        atr=round(rv*(r/100)*0.38)
        film["scenarios"].append({"name":nm,"strategy":st,"risk":r,"leak":calc_leak(r,st),"rev":rv,"at_risk":atr,"net":rv-atr})
    best=max(film["scenarios"],key=lambda x:x["net"])
    film["recommendation"]=best["name"]

    film["territories"]=[
        {"name":"North America","risk":min(96,22+(20 if film["strategy"]=="staggered" else 0)),"delay":0,"rev":round(film["rev"]*0.30)},
        {"name":"United Kingdom","risk":min(96,31+(6 if film["strategy"]=="staggered" else 0)),"delay":0,"rev":round(film["rev"]*0.09)},
        {"name":"Japan","risk":min(96,41+(12 if film["strategy"]=="staggered" else 0)),"delay":14,"rev":round(film["rev"]*0.11)},
        {"name":"India","risk":min(96,74+(14 if film["strategy"]=="staggered" else 0)),"delay":21,"rev":round(film["rev"]*0.13)},
        {"name":"China","risk":min(96,82+(8 if film["strategy"]=="staggered" else 0)),"delay":28,"rev":round(film["rev"]*0.09)},
        {"name":"Brazil","risk":min(96,68+(10 if film["strategy"]=="staggered" else 0)),"delay":21,"rev":round(film["rev"]*0.09)},
    ]

    cur=next(s for s in film["scenarios"] if s["strategy"]==film["strategy"])
    net_gain=best["net"]-cur["net"]
    film["rec_reason"]=(
        f"Switching to {best['name']} reduces risk from {cur['risk']} to {best['risk']} "
        f"and extends the estimated leak window from Day {cur['leak']} to Day {best['leak']}. "
        f"Net revenue improves by ${abs(net_gain)}M (${cur['net']}M vs ${best['net']}M). "
        f"{'India and China are highest-exposure markets — same-day digital release recommended.' if film['budget']>80 else 'Monitor social buzz in lead-up; high buzz correlates with earlier leak attempts.'}"
        if best["name"]!=film["strategy_label"] else
        f"Current {film['strategy_label']} is the strongest option at ${cur['net']}M net. Focus on closing the streaming gap."
    )
    film["actions"]=[
        f"Switch to {best['name']} — protects ${abs(net_gain)}M additional revenue." if best["name"]!=film["strategy_label"] else f"Maintain {film['strategy_label']} — strongest net position at ${cur['net']}M.",
        f"Close streaming gap from {film['gap']} weeks to 4 — removes primary piracy incentive.",
        "Prioritise India and China for day-and-date digital — both score above 70 risk.",
        "Limit screener distribution to verified press only — implement digital watermarking.",
        f"Set Day {max(3,best['leak']-2)} monitoring trigger — execute PVOD price drop if leak detected early.",
    ]
    print(f"  Risk: {film['risk']}/100 | Leak: Day +{film['leak_day']} | Revenue: ${film['rev']}M | At Risk: ${film['at_risk']}M")
    print(f"  Recommended: {film['recommendation']}")
    return film

def build_pdf(film,out):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,HRFlowable,PageBreak,Flowable
    from reportlab.lib.styles import ParagraphStyle

    BG=colors.HexColor('#090b0f');SU=colors.HexColor('#0f1318');SU2=colors.HexColor('#151a22')
    BO=colors.HexColor('#1c232e');AC=colors.HexColor('#e8a020');RE=colors.HexColor('#e05252')
    GR=colors.HexColor('#3dd68c');TX=colors.HexColor('#e8eaf0');T2=colors.HexColor('#8892a4');T3=colors.HexColor('#4a5568')
    W,H=A4; MG=18*mm

    class Bar(Flowable):
        def __init__(self,s,w=200,h=6): super().__init__(); self._w=w; self._h=h; self.s=s
        def wrap(self,aw,ah): return self._w,self._h+4
        def draw(self):
            c=self.canv; c.setFillColor(BO); c.rect(0,2,self._w,self._h,fill=1,stroke=0)
            c.setFillColor(colors.HexColor(risk_col(self.s))); c.rect(0,2,self._w*(self.s/100),self._h,fill=1,stroke=0)

    def S(n,**k): return ParagraphStyle(n,**k)
    ST={
        'sec':S('sec',fontName='Helvetica-Bold',fontSize=7,textColor=T3,spaceAfter=4,spaceBefore=14,letterSpacing=1.5),
        'h2':S('h2',fontName='Helvetica-Bold',fontSize=16,textColor=TX,spaceAfter=6,leading=20),
        'h3':S('h3',fontName='Helvetica-Bold',fontSize=11,textColor=TX,spaceAfter=4,leading=14),
        'b':S('b',fontName='Helvetica',fontSize=9,textColor=T2,spaceAfter=5,leading=14),
        'bw':S('bw',fontName='Helvetica',fontSize=9,textColor=TX,spaceAfter=5,leading=14),
        'cap':S('cap',fontName='Helvetica',fontSize=7.5,textColor=T3,spaceAfter=3,leading=11),
        'act':S('act',fontName='Helvetica',fontSize=9,textColor=T2,spaceAfter=5,leading=13,leftIndent=10),
        'kl':S('kl',fontName='Helvetica',fontSize=7,textColor=T3,spaceAfter=0,leading=10,letterSpacing=0.8),
    }

    def kpi(items):
        def cell(v,l,c): return [Paragraph(f'<font color="{c}" size="24"><b>{v}</b></font>',ParagraphStyle('big',fontName='Helvetica-Bold',fontSize=26,textColor=TX,spaceAfter=2,leading=30)),Paragraph(l.upper(),ST['kl'])]
        cs=[cell(v,l,c) for v,l,c in items]
        t=Table([cs],colWidths=[(W-2*MG)/len(cs)]*len(cs))
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,-1),SU),('LINEAFTER',(0,0),(-2,-1),0.5,BO),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),('LEFTPADDING',(0,0),(-1,-1),14)]))
        return t

    def cover(c,doc):
        c.setFillColor(BG);c.rect(0,0,W,H,fill=1,stroke=0)
        c.setFillColor(AC);c.rect(0,H-6*mm,W,6*mm,fill=1,stroke=0)
        c.setFillColor(SU);c.rect(0,0,W,38*mm,fill=1,stroke=0)
        c.setFillColor(BO);c.rect(0,38*mm,W,0.5,fill=1,stroke=0)
        c.setStrokeColor(colors.HexColor('#12181f'));c.setLineWidth(0.4)
        for x in range(0,int(W),22):c.line(x,0,x,H)
        for y in range(0,int(H),22):c.line(0,y,W,y)
        c.setFillColor(colors.white);c.setFont("Helvetica-Bold",28);c.drawString(MG,H-32*mm,"CINE")
        c.setFillColor(AC);c.drawString(MG+52,H-32*mm,"RISK")
        c.setFillColor(T3);c.setFont("Helvetica",7);c.drawString(MG,H-36*mm,"RELEASE INTELLIGENCE PLATFORM")
        c.setFillColor(TX);c.setFont("Helvetica-Bold",30);c.drawString(MG,H*0.52+22,film['title'].upper())
        c.setFillColor(T2);c.setFont("Helvetica",9);c.drawString(MG,H*0.52+8,f"{' / '.join(film.get('genres',[''])[:2])}  ·  {film.get('release_year','')}  ·  Dir. {film.get('director','')}")
        c.setFillColor(AC);c.setFont("Helvetica-Bold",11);c.drawString(MG,H*0.52-4,"RELEASE RISK INTELLIGENCE REPORT")
        sc=film['risk'];col=colors.HexColor(risk_col(sc));lbl=risk_lbl(sc)+" RISK"
        c.setFillColor(col);c.setFont("Helvetica-Bold",72);c.drawString(MG,H*0.52-76,str(sc))
        c.setFont("Helvetica-Bold",10);c.drawString(MG,H*0.52-90,lbl)
        c.setFillColor(AC);c.rect(MG,H*0.52-98,38*mm,1.5,fill=1,stroke=0)
        c.setFillColor(T2);c.setFont("Helvetica",8)
        c.drawString(MG,22*mm,f"Prepared for: {film['prepared_for']}")
        c.drawString(MG,16*mm,f"Date: {film['date']}")
        c.setFillColor(T3);c.drawString(MG,10*mm,f"Confidential — {film['prepared_by']}")
        c.drawRightString(W-MG,10*mm,"Page 1")

    def inner(c,doc):
        c.setFillColor(BG);c.rect(0,0,W,H,fill=1,stroke=0)
        c.setFillColor(SU);c.rect(0,H-14*mm,W,14*mm,fill=1,stroke=0)
        c.setFillColor(AC);c.rect(0,H-14*mm,W,1,fill=1,stroke=0)
        c.setFillColor(colors.white);c.setFont("Helvetica-Bold",9);c.drawString(MG,H-9*mm,"CINE")
        c.setFillColor(AC);c.drawString(MG+20,H-9*mm,"RISK")
        c.setFillColor(T2);c.setFont("Helvetica",7);c.drawCentredString(W/2,H-9*mm,film['title'].upper()+" — RELEASE RISK REPORT")
        c.setFillColor(T3);c.drawRightString(W-MG,H-9*mm,f"Page {doc.page}")
        c.setFillColor(SU);c.rect(0,0,W,10*mm,fill=1,stroke=0)
        c.setFillColor(BO);c.rect(0,10*mm,W,0.5,fill=1,stroke=0)
        c.setFillColor(T3);c.setFont("Helvetica",7)
        c.drawString(MG,4*mm,f"Confidential — {film['prepared_by']} — {film['date']}")
        c.drawRightString(W-MG,4*mm,"Not for distribution")

    def pg(c,doc): cover(c,doc) if doc.page==1 else inner(c,doc)

    doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=MG,rightMargin=MG,topMargin=20*mm,bottomMargin=16*mm)
    story=[Spacer(1,1),PageBreak()]
    rc=risk_col(film['risk'])

    story.append(Paragraph("Executive Summary",ST['sec']))
    story.append(Paragraph(f"{film['title']} — Release Risk Assessment",ST['h2']))
    story.append(Spacer(1,4))
    story.append(kpi([(str(film['risk']),"Risk score",rc),(f"Day +{film['leak_day']}","Est. first leak",'#e05252'),(f"${film['rev']}M","Revenue potential",'#3dd68c'),(f"${film['at_risk']}M","Revenue at risk",'#e05252')]))
    story.append(Spacer(1,10))

    rd=[[Paragraph(f'<font color="{rc}"><b>RECOMMENDED: {film["recommendation"].upper()}</b></font>',ST['h3'])],[Paragraph(film['rec_reason'],ST['act'])]]
    rt=Table(rd,colWidths=[W-2*MG])
    rt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),SU2),('LINEBEFORE',(0,0),(-1,-1),3,AC),('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12),('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),12)]))
    story.append(rt);story.append(Spacer(1,12))

    story.append(Paragraph("Film Parameters",ST['sec']))
    cast_str=", ".join(film.get('cast',['N/A'])[:3]) or "N/A"
    params=[["Genre",film['genre'],"Budget",f"${film['budget']}M"],["Director",film.get('director','N/A'),"Runtime",f"{film.get('runtime',0)} min"],["Franchise","Yes" if film['franchise'] else "No","Rating",film.get('rating','N/A')],["Strategy",film['strategy_label'],"Streaming gap",f"{film['gap']} weeks"],["Lead Cast",cast_str,"Trailer buzz",f"{film['buzz']}M views"]]
    pt=Table(params,colWidths=[36*mm,54*mm,36*mm,54*mm])
    pt.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),8.5),('TEXTCOLOR',(0,0),(0,-1),T3),('TEXTCOLOR',(1,0),(1,-1),TX),('TEXTCOLOR',(2,0),(2,-1),T3),('TEXTCOLOR',(3,0),(3,-1),TX),('FONTNAME',(1,0),(1,-1),'Helvetica-Bold'),('FONTNAME',(3,0),(3,-1),'Helvetica-Bold'),('ROWBACKGROUNDS',(0,0),(-1,-1),[SU,SU2]),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),10),('GRID',(0,0),(-1,-1),0.3,BO)]))
    story.append(pt);story.append(PageBreak())

    story.append(Paragraph("Scenario Comparison",ST['sec']))
    story.append(Paragraph("Three Strategies — Net Revenue",ST['h2']))
    story.append(Spacer(1,6))
    sh=[Paragraph(f'<font color="#4a5568"><b>{x}</b></font>',ST['cap']) for x in ["STRATEGY","RISK","LEAK","REVENUE","AT RISK","NET"]]
    srows=[sh]
    for s in film['scenarios']:
        ir=s['name']==film['recommendation']
        nm=f'<b>{s["name"]}</b>'+(f' <font color="#3dd68c" size="7">REC</font>' if ir else "")
        srows.append([Paragraph(nm,ST['bw'] if ir else ST['b']),Paragraph(f'<font color="{risk_col(s["risk"])}"><b>{s["risk"]}</b></font>',ST['b']),Paragraph(f'<font color="#8892a4">D+{s["leak"]}</font>',ST['b']),Paragraph(f'<font color="#3dd68c">${s["rev"]}M</font>',ST['b']),Paragraph(f'<font color="#e05252">-${s["at_risk"]}M</font>',ST['b']),Paragraph(f'<font color="#3dd68c"><b>${s["net"]}M</b></font>',ST['b'])])
    cw=W-2*MG
    sc=Table(srows,colWidths=[cw*.30,cw*.10,cw*.12,cw*.15,cw*.15,cw*.18])
    sc.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),SU2),('ROWBACKGROUNDS',(0,1),(-1,-1),[SU,SU2]),('GRID',(0,0),(-1,-1),0.3,BO),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LEFTPADDING',(0,0),(-1,-1),10),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story.append(sc);story.append(Spacer(1,16))

    bw2=W-2*MG-58*mm;mx=max(s['net'] for s in film['scenarios'])
    story.append(Paragraph("Net Revenue Comparison",ST['sec']))
    brows=[]
    for s in film['scenarios']:
        bc='#3dd68c' if s['name']==film['recommendation'] else '#5b9cf6'
        brows.append([Paragraph(s['name'],ST['cap']),Bar(int(s['net']/mx*100),w=int(bw2),h=14),Paragraph(f'<font color="{bc}"><b>${s["net"]}M</b></font>',ST['b'])])
    bt=Table(brows,colWidths=[55*mm,bw2,25*mm])
    bt.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.append(bt);story.append(PageBreak())

    story.append(Paragraph("Territory Risk",ST['sec']))
    story.append(Paragraph("Region-by-Region Exposure",ST['h2']))
    story.append(Spacer(1,6))
    th=[Paragraph(f'<font color="#4a5568"><b>{x}</b></font>',ST['cap']) for x in ["TERRITORY","RISK","DELAY","REVENUE","EXPOSURE"]]
    trows=[th]
    for t in film['territories']:
        exp=round(t['rev']*(t['risk']/100)*0.38)
        dl="Simultaneous" if t['delay']==0 else f"+{t['delay']} days"
        trows.append([Paragraph(f'<b>{t["name"]}</b>',ST['bw']),Paragraph(f'<font color="{risk_col(t["risk"])}"><b>{t["risk"]}</b></font> <font color="#4a5568" size="7">{risk_lbl(t["risk"])}</font>',ST['b']),Paragraph(f'<font color="#8892a4">{dl}</font>',ST['b']),Paragraph(f'<font color="#3dd68c">${t["rev"]}M</font>',ST['b']),Paragraph(f'<font color="#e05252">-${exp}M</font>',ST['b'])])
    cw3=W-2*MG
    tt=Table(trows,colWidths=[cw3*.26,cw3*.18,cw3*.22,cw3*.17,cw3*.17])
    tt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),SU2),('ROWBACKGROUNDS',(0,1),(-1,-1),[SU,SU2]),('GRID',(0,0),(-1,-1),0.3,BO),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LEFTPADDING',(0,0),(-1,-1),10),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story.append(tt);story.append(Spacer(1,14))
    hr2=[t for t in film['territories'] if t['risk']>=70]
    if hr2:
        hd=[[Paragraph('<font color="#e05252"><b>HIGH-RISK TERRITORIES</b></font>',ST['h3'])],[Paragraph(f"{', '.join(t['name'] for t in hr2)} — score above 70. Same-day digital release strongly recommended in all these markets.",ST['b'])]]
        ht=Table(hd,colWidths=[W-2*MG])
        ht.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#1a0d0d')),('LINEBEFORE',(0,0),(-1,-1),3,RE),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),12),('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#3a1515'))]))
        story.append(ht)
    story.append(PageBreak())

    story.append(Paragraph("Recommended Actions",ST['sec']))
    story.append(Paragraph("Five Actions to Protect Revenue",ST['h2']))
    story.append(Spacer(1,8))
    for i,a in enumerate(film['actions'],1):
        ad=[[Paragraph(f'<font color="#e8a020" size="14"><b>0{i}</b></font>',ST['b']),Paragraph(a,ST['act'])]]
        at=Table(ad,colWidths=[14*mm,W-2*MG-14*mm])
        at.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),SU if i%2==0 else SU2),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),('LEFTPADDING',(0,0),(-1,-1),12),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.3,BO)]))
        story.append(at);story.append(Spacer(1,4))

    doc.build(story,onFirstPage=pg,onLaterPages=pg)
    return out

if __name__=="__main__":
    if len(sys.argv)<2:
        print('Usage: python3 generate_report.py "Film Title" "Distributor Name"')
        sys.exit(1)
    title=sys.argv[1]; dist=sys.argv[2] if len(sys.argv)>2 else "Confidential Client"
    film=assemble(title,dist)
    safe=title.replace(' ','_').replace('/','_')
    out=f"{os.path.expanduser('~/Desktop/cinerisk')}/CineRisk_{safe}_Report.pdf"
    build_pdf(film,out)
    print(f"\n Report saved to: {out}")
    os.system(f"open '{out}'")
PYEOF

echo ""
echo "✓ Done! Now run:"
echo ""
echo "  python3 ~/Desktop/cinerisk/generate_report.py \"Dune Part Two\" \"Your Client\""
echo ""
