"""
Reads live_alerts.json and updates:
1. cineos_internal.html — full attribution visible
2. cineos_today.html — top 10, no attribution
Then pushes both to GitHub.
"""
import json, re, subprocess, os
from datetime import datetime
from cineos_alert_engine import (
    load_alerts, get_top10_for_today,
    generate_public_signal, severity_score
)

def severity_badge_internal(sev):
    badges = {
        'critical': ('bc','Critical'),
        'high':     ('bh','High'),
        'medium':   ('ba','Medium'),
        'low':      ('bo2','Low'),
    }
    cls, label = badges.get(sev, ('ba','Active'))
    return f'<span class="badge {cls}">{label}</span>'

def build_chain_html(alert):
    """Build the full end-to-end attribution chain HTML."""
    chain = alert.get('chain', {})
    a_id  = alert.get('id','')[:6]

    # Build nodes based on what data we have
    nodes = []

    # Node 1: DETECT
    ch_count = len(chain.get('channels_found', []))
    kw_count = len(chain.get('keywords_matched', []))
    nodes.append({
        'icon':'📡','cls':'dg',
        'label':'Detect',
        'val':f"{ch_count} channel{'s' if ch_count!=1 else ''}",
        'sub':f"{kw_count} keyword signals",
    })

    # Node 2: REACH (if known)
    reach = chain.get('reach', 0)
    if reach > 0:
        reach_str = f"{reach/1000000:.1f}M" if reach>999999 else f"{reach:,}"
        nodes.append({
            'icon':'👁','cls':'da',
            'label':'Reach',
            'val':reach_str,
            'sub':'subscribers exposed',
        })

    # Node 3: ATTRIBUTION
    phones = chain.get('phones', [])
    upis   = chain.get('upis', [])
    op     = chain.get('operator_name','')
    whois  = chain.get('whois_registrant','')

    if phones or upis or op or whois:
        attr_val = op if op else (
            whois[:20] if whois else
            f"{len(phones)} phone{'s' if len(phones)!=1 else ''}"
        )
        nodes.append({
            'icon':'👤','cls':'dp',
            'label':'Attribution',
            'val':attr_val,
            'sub': f"phones:{len(phones)} UPIs:{len(upis)}",
        })

    # Node 4: EVIDENCE
    hashes = chain.get('evidence_hashes', [])
    legal  = chain.get('legal_basis', 'IT Act §65B')
    nodes.append({
        'icon':'⚖','cls':'dg',
        'label':'Evidence',
        'val':legal.split('+')[0].strip(),
        'sub':f"hash: {hashes[0][:12]}..." if hashes else 'Hashed at capture',
    })

    # Node 5: END STEPS
    action  = chain.get('recommended_action','')
    reports = chain.get('report_to', [])
    if action or reports:
        nodes.append({
            'icon':'📋','cls':'dg',
            'label':'End step',
            'val':action[:35]+'...' if len(action)>35 else action,
            'sub':f"Report to: {', '.join(reports[:2])}",
        })

    # Build HTML
    html = '<div class="chain">'
    for i, node in enumerate(nodes):
        html += f'''
        <div class="cn">
          <div class="cnd {node["cls"]}">{node["icon"]}</div>
          <div class="cnl">{node["label"]}</div>
          <div class="cnv">{node["val"]}</div>
          <div class="cns">{node["sub"]}</div>
        </div>'''
        if i < len(nodes)-1:
            html += '<div class="carr">→</div>'
    html += '</div>'

    # Evidence row
    html += '<div class="evr">'
    html += f'<div><div class="evl">Detected at</div><div class="evv g">{alert.get("detected_at","")[:16]}</div></div>'
    html += f'<div><div class="evl">Legal basis</div><div class="evv">{chain.get("legal_basis","IT Act §65B")}</div></div>'

    if phones:
        ph_html = ''.join(f'<span class="itag">{p}</span> ' for p in phones[:2])
        html += f'<div><div class="evl">Phones (internal)</div><div class="evv p">{ph_html}</div></div>'
    elif whois:
        html += f'<div><div class="evl">WHOIS registrant</div><div class="evv p">{whois[:30]}</div></div>'
    else:
        html += f'<div><div class="evl">Channels</div><div class="evv g">{ch_count} found</div></div>'

    reports_str = ', '.join(chain.get('report_to',[])[:3])
    html += f'<div><div class="evl">Report to</div><div class="evv a">{reports_str}</div></div>'
    html += '</div>'

    return html

def update_internal_alerts_section(alerts):
    """Generate the full alerts HTML for the internal dashboard."""
    rows = ''
    for i, a in enumerate(alerts[:20], 1):
        a_id  = a.get('id','x')[:6]
        chain = a.get('chain', {})
        reach = chain.get('reach', 0)
        reach_str = (f"{reach/1000000:.1f}M reach"
                     if reach > 999999 else
                     f"{reach:,} reach" if reach > 0 else '')

        rows += f'''
        <div class="ar" id="r_{a_id}" onclick="tog('{a_id}')">
          {severity_badge_internal(a["severity"])}
          <div>
            <div class="an">{a["title"][:60]}</div>
            <div class="ad">{a["detail"][:70]} {reach_str}</div>
          </div>
          <span class="apl">{a.get("platform","Telegram")[:18]}</span>
          <span class="at">{a.get("detected_at","")[:10]}</span>
          {severity_badge_internal(a.get("status","active"))}
          <div class="exp" id="e_{a_id}">›</div>
        </div>
        <div class="adr" id="d_{a_id}">
          <div class="adrh"> — {a["title"][:50]}</div>
          {build_chain_html(a)}
        </div>'''

    return rows

def update_today_html(top10):
    """Update cineos_today.html with top 10 public signals."""
    try:
        html = open('cineos_today.html').read()
    except:
        print("  cineos_today.html not found")
        return

    now  = datetime.now()
    date = now.strftime('%B %d, %Y')
    day  = now.strftime('%A')

    # Update date
    html = re.sub(
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)<br>[A-Z][a-z]+ \d+, \d+',
        f"{day}<br>{date}", html)

    # Build signal HTML for top 10
    signal_html = ''
    for i, alert in enumerate(top10, 1):
        pub  = generate_public_signal(alert)
        sev  = pub['severity']
        badge_cls = {
            'critical':'sb-crit','high':'sb-high',
            'medium':'sb-active','low':'sb-active'
        }.get(sev,'sb-active')
        badge_lbl = sev.capitalize()
        reach_str = f"· {pub['reach']} reach" if pub['reach'] != '—' else ''
        ch_str    = f"· {pub['channels']} channels" if pub['channels'] else ''

        signal_html += f'''
      <div class="signal">
        <div class="signal-rank {"hot" if i<=3 else ""}">{i}</div>
        <div>
          <div class="signal-title">{pub["title"]}</div>
          <p class="signal-body">{pub["detail"]}</p>
          <div class="signal-meta">
            <span class="sm-item">{pub["platform"]}</span>
            <span class="sm-item">{pub["legal"]}</span>
            {f'<span class="sm-item">{ch_str.strip("· ")}</span>' if ch_str else ''}
            {f'<span class="sm-item">{reach_str.strip("· ")}</span>' if reach_str else ''}
          </div>
        </div>
        <div class="signal-badge {badge_cls}">{badge_lbl}</div>
      </div>'''

    # Replace signals section
    html = re.sub(
        r'(<div class="sec-label red">Today\'s top fraud signals</div>)(.*?)(</div>\s*</div>\s*<!-- RIGHT)',
        rf'\1{signal_html}\3',
        html, flags=re.DOTALL)

    open('cineos_today.html', 'w').write(html)
    print(f"  cineos_today.html updated with {len(top10)} signals")

if __name__ == '__main__':
    print("="*52)
    print("  CINEOS CONTENT UPDATER")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*52)

    alerts = load_alerts()
    top10  = get_top10_for_today()

    print(f"\n  Total alerts in engine: {len(alerts)}")
    print(f"  Top 10 for today:       {len(top10)}")

    update_today_html(top10)

    # Git push
    subprocess.run(['git','add',
                    'cineos_today.html',
                    'reports/alerts/live_alerts.json'],
                   capture_output=True)
    result = subprocess.run(
        ['git','commit','-m',
         f"Daily update: {datetime.now().strftime('%b %d')} "
         f"— {len(alerts)} alerts — top {len(top10)} published"],
        capture_output=True, text=True)
    if 'nothing to commit' not in result.stdout:
        subprocess.run(['git','push'], capture_output=True)
        print(f"  Pushed to GitHub Pages")
    else:
        print(f"  No changes to push")

    print(f"\n  Done.")
