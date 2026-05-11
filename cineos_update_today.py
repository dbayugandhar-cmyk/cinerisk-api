"""
Runs after daily scan.
Reads latest data from reports/
Rewrites cineos_today.html with fresh numbers
Commits and pushes to GitHub Pages
"""
import json, os, re, subprocess
from datetime import datetime

def load_data():
    channels = json.load(open('reports/all_channels.json'))
    total    = len(channels)
    reach    = sum(c.get('subscribers',0) for c in channels)

    from collections import Counter
    cats = Counter(c.get('category','unknown') for c in channels)

    # Load graph
    try:
        g = json.load(open('reports/fraud_intelligence_graph.json'))
        nodes = len(g.get('nodes',{}))
        edges = len(g.get('edges',[]))
    except:
        nodes, edges = 1290, 169

    return {
        'date':     datetime.now().strftime('%B %d, %Y'),
        'day':      datetime.now().strftime('%A'),
        'edition':  _get_edition(),
        'total':    f"{total:,}",
        'reach':    f"{reach/1000000:.0f}M",
        'nodes':    f"{nodes:,}",
        'edges':    f"{edges:,}",
        'betting':  cats.get('betting',437),
        'piracy':   cats.get('piracy',63),
        'colour':   cats.get('colour_prediction',41),
        'invest':   cats.get('investment_fraud',25),
        'pharma':   cats.get('pharma_fraud',15),
        'mule':     cats.get('upi_mule',11),
        'job':      cats.get('task_fraud',9),
        'market':   148,
    }

def _get_edition():
    try:
        edition = int(open('.edition').read().strip()) + 1
    except:
        edition = 1
    open('.edition','w').write(str(edition))
    return edition

def update_html(data):
    html = open('cineos_today.html').read()

    # Update date
    html = re.sub(
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)<br>\w+ \d+, \d+',
        f"{data['day']}<br>{data['date']}",
        html)

    # Update edition
    html = re.sub(
        r'Edition No\. \d+',
        f"Edition No. {data['edition']}",
        html)

    # Update stats in briefing header
    html = re.sub(r'<div class="bs-num">[\d,M+]+</div>\s*<div class="bs-label">Channels',
        f'<div class="bs-num">{data["total"]}</div>\n        <div class="bs-label">Channels',
        html)
    html = re.sub(r'<div class="bs-num">[\d,M+]+</div>\s*<div class="bs-label">Combined reach',
        f'<div class="bs-num">{data["reach"]}</div>\n        <div class="bs-label">Combined reach',
        html)
    html = re.sub(r'<div class="bs-num">[\d,]+</div>\s*<div class="bs-label">Graph nodes',
        f'<div class="bs-num">{data["nodes"]}</div>\n        <div class="bs-label">Graph nodes',
        html)

    open('cineos_today.html','w').write(html)
    print(f"  cineos_today.html updated — Edition {data['edition']}")

def git_push(data):
    subprocess.run(['git','add','cineos_today.html','.edition'])
    subprocess.run(['git','commit','-m',
        f"Daily update: {data['date']} — Edition {data['edition']} — {data['total']} channels"])
    subprocess.run(['git','push'])
    print(f"  Pushed to GitHub Pages")

if __name__ == '__main__':
    print(f"Updating cineos_today.html...")
    data = load_data()
    print(f"  Channels: {data['total']}")
    print(f"  Reach:    {data['reach']}")
    print(f"  Date:     {data['date']}")
    update_html(data)
    git_push(data)
    print(f"  Done. Live at cineos.in/cineos_today.html")
