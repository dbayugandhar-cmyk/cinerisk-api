"""
CINEOS Weekly Piracy Intelligence Report
Runs every Monday — scans top films and sends report to subscribers
"""
import asyncio, os, datetime, sys
sys.path.insert(0, '.')

GMAIL_USER = "yugandhar@cineos.in"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
SERP_API_KEY = os.environ.get("SERP_API_KEY", "")

# Films to scan every week
WEEKLY_WATCHLIST = [
    "Retro", "Devara", "Lucky Bhaskar",
    "Kalki 2898 AD", "RRR", "KGF Chapter 2",
]

# Subscribers list — add clients here
SUBSCRIBERS = [
    "yugandhar@cineos.in",  # yourself — always gets report
]

async def run_weekly_report():
    from cineos_india import full_india_scan
    from cineos_alerts import send_alert_email
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    now = datetime.datetime.now(datetime.timezone.utc)
    week_str = now.strftime("Week of %B %d, %Y")
    print(f"CINEOS Weekly Report — {week_str}")
    print(f"Scanning {len(WEEKLY_WATCHLIST)} films...")

    results = []
    total_hits = 0

    for film in WEEKLY_WATCHLIST:
        print(f"  Scanning: {film}...")
        try:
            result = await full_india_scan(film)
            hits = result.get("hits", [])
            verdict = result.get("verdict", "CLEAN")
            results.append({
                "film": film,
                "verdict": verdict,
                "hits": len(hits),
                "urls": [getattr(h,"url","") if hasattr(h,"url") else h.get("url","")
                         for h in hits[:3]],
                "cam": result.get("cam_hits", 0)
            })
            total_hits += len(hits)
            print(f"    {verdict} — {len(hits)} hits")
        except Exception as e:
            print(f"    Error: {e}")
            results.append({"film": film, "verdict": "ERROR", "hits": 0, "urls": [], "cam": 0})

    # Build HTML report
    rows = ""
    for r in results:
        color = "#cc0000" if r["hits"] > 0 else "#007700"
        verdict_bg = "#fff0f0" if r["hits"] > 0 else "#f0fff0"
        url_list = "".join([f'<div style="font-size:11px;font-family:monospace;color:#0066cc;margin:2px 0;">{u[:70]}</div>' for u in r["urls"]])
        rows += f"""
        <tr style="background:{verdict_bg}">
          <td style="padding:10px;border-bottom:1px solid #eee;font-weight:bold">{r['film']}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;color:{color};font-weight:bold">{r['verdict']}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;color:{color};font-weight:bold;text-align:center">{r['hits']}</td>
          <td style="padding:10px;border-bottom:1px solid #eee">{url_list if r['urls'] else '<span style="color:#aaa">None detected</span>'}</td>
        </tr>"""

    confirmed = sum(1 for r in results if r["hits"] > 0)
    cam_total = sum(r["cam"] for r in results)

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;background:#f5f5f5;padding:20px;">

  <div style="background:#0a0a14;padding:25px;border-radius:8px 8px 0 0;text-align:center;">
    <h1 style="color:#00ff88;margin:0;font-size:28px;">🛡️ CINEOS</h1>
    <p style="color:#aaaacc;margin:8px 0 0;font-size:15px;">Weekly Piracy Intelligence Report</p>
    <p style="color:#666688;margin:4px 0 0;font-size:13px;">{week_str}</p>
  </div>

  <div style="background:white;padding:25px;border-radius:0 0 8px 8px;">

    <div style="display:flex;gap:10px;margin-bottom:25px;">
      <div style="flex:1;background:#fff0f0;border:1px solid #ffcccc;padding:15px;border-radius:6px;text-align:center;">
        <div style="font-size:28px;font-weight:bold;color:#cc0000">{confirmed}</div>
        <div style="font-size:12px;color:#888;text-transform:uppercase">Films Pirated</div>
      </div>
      <div style="flex:1;background:#fff5e6;border:1px solid #ffcc88;padding:15px;border-radius:6px;text-align:center;">
        <div style="font-size:28px;font-weight:bold;color:#cc6600">{total_hits}</div>
        <div style="font-size:12px;color:#888;text-transform:uppercase">Total URLs Found</div>
      </div>
      <div style="flex:1;background:#f0fff0;border:1px solid #88cc88;padding:15px;border-radius:6px;text-align:center;">
        <div style="font-size:28px;font-weight:bold;color:#007700">{len(WEEKLY_WATCHLIST) - confirmed}</div>
        <div style="font-size:12px;color:#888;text-transform:uppercase">Films Clean</div>
      </div>
      <div style="flex:1;background:#f5f0ff;border:1px solid #cc99ff;padding:15px;border-radius:6px;text-align:center;">
        <div style="font-size:28px;font-weight:bold;color:#6600cc">{cam_total}</div>
        <div style="font-size:12px;color:#888;text-transform:uppercase">CAM Copies</div>
      </div>
    </div>

    <h3 style="color:#333;border-bottom:2px solid #00aa55;padding-bottom:8px;">Film-wise Piracy Report</h3>
    <table style="width:100%;border-collapse:collapse;">
      <tr style="background:#f0f0f0;">
        <th style="padding:10px;text-align:left;font-size:12px;text-transform:uppercase">Film</th>
        <th style="padding:10px;text-align:left;font-size:12px;text-transform:uppercase">Verdict</th>
        <th style="padding:10px;text-align:center;font-size:12px;text-transform:uppercase">URLs</th>
        <th style="padding:10px;text-align:left;font-size:12px;text-transform:uppercase">Sample URLs</th>
      </tr>
      {rows}
    </table>

    <div style="margin-top:25px;padding:15px;background:#f0f8ff;border-radius:6px;border:1px solid #99ccff;">
      <h3 style="color:#0066cc;margin:0 0 10px;font-size:14px;">Recommended Actions This Week</h3>
      <ol style="margin:0;padding-left:20px;font-size:13px;color:#555;">
        <li style="margin-bottom:6px;">File DMCA takedowns for all confirmed URLs via Google Search Console</li>
        <li style="margin-bottom:6px;">Report to MIB: <a href="mailto:nodalofficer@meity.gov.in">nodalofficer@meity.gov.in</a></li>
        <li style="margin-bottom:6px;">Contact TFCC for Telugu/Tamil films: <a href="https://tfcc.in">tfcc.in</a></li>
        {'<li style="margin-bottom:6px;color:#cc0000"><strong>URGENT: CAM copies found — file FIR immediately at cybercrime.gov.in</strong></li>' if cam_total > 0 else ''}
      </ol>
    </div>

    <div style="margin-top:20px;text-align:center;">
      <a href="https://cineos.in/cineos_platform.html"
         style="background:#00aa55;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">
        View Live Dashboard →
      </a>
    </div>

    <p style="margin-top:20px;font-size:11px;color:#aaa;text-align:center;border-top:1px solid #eee;padding-top:15px;">
      CINEOS Weekly Intelligence | US Patent 64/049,190<br>
      To add films to watchlist or unsubscribe: yugandhar@cineos.in<br>
      Platform: cineos_platform.html | Dashboard: cineos_dashboard.html
    </p>
  </div>
</body></html>"""

    # Send to all subscribers
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    for subscriber in SUBSCRIBERS:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"CINEOS Weekly: {confirmed}/{len(WEEKLY_WATCHLIST)} films pirated — {total_hits} URLs | {week_str}"
            msg["From"] = f"CINEOS Intelligence <{GMAIL_USER}>"
            msg["To"] = subscriber
            msg.attach(MIMEText(html, "html", "utf-8"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.ehlo()
                server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                server.sendmail(GMAIL_USER, subscriber, msg.as_string())
            print(f"Weekly report sent to {subscriber}")
        except Exception as e:
            print(f"Failed to send to {subscriber}: {e}")

    print(f"\nWeekly report complete: {confirmed}/{len(WEEKLY_WATCHLIST)} films pirated, {total_hits} total URLs")
    return results

if __name__ == "__main__":
    asyncio.run(run_weekly_report())
