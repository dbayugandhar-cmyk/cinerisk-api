"""
CINEOS Email Alert System
Sends piracy detection alerts via Gmail SMTP
"""
import smtplib, asyncio, os, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Gmail config — use App Password (not regular password)
GMAIL_USER = "yugandhar@cineos.in"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

def send_alert_email(
    to_email: str,
    film_title: str,
    verdict: str,
    hits: list,
    scan_time: str = None
) -> bool:
    """Send piracy alert email to client."""
    
    if not GMAIL_APP_PASSWORD:
        print("WARNING: GMAIL_APP_PASSWORD not set")
        return False

    now = scan_time or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    hit_count = len(hits)
    
    severity_color = "#cc0000" if "CRITICAL" in verdict else "#ff6600"
    
    # Build URL list HTML
    url_rows = ""
    for i, hit in enumerate(hits[:10], 1):
        url = hit.get("url", "") if isinstance(hit, dict) else getattr(hit, "url", "")
        platform = hit.get("platform", "") if isinstance(hit, dict) else getattr(hit, "platform", "")
        url_rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;font-family:monospace;font-size:12px;color:#0066cc;">{url[:80]}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;font-size:12px;">{platform}</td>
        </tr>"""

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f5f5f5;padding:20px;">

  <div style="background:#0a0a14;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
    <h1 style="color:#00ff88;margin:0;font-size:24px;">🛡️ CINEOS</h1>
    <p style="color:#aaaacc;margin:5px 0 0;font-size:13px;">Anti-Piracy Intelligence Alert</p>
  </div>

  <div style="background:#ffffff;padding:25px;border-radius:0 0 8px 8px;">
    
    <div style="background:{severity_color}15;border-left:4px solid {severity_color};padding:15px;margin-bottom:20px;border-radius:4px;">
      <h2 style="color:{severity_color};margin:0 0 5px;font-size:18px;">⚠️ Piracy Detected: {film_title}</h2>
      <p style="margin:0;font-size:13px;color:#555;">Verdict: <strong style="color:{severity_color}">{verdict}</strong></p>
    </div>

    <table style="width:100%;margin-bottom:20px;">
      <tr>
        <td style="padding:8px;background:#f9f9f9;border-radius:4px;width:50%;">
          <div style="font-size:11px;color:#888;text-transform:uppercase;">Film / Content</div>
          <div style="font-size:16px;font-weight:bold;color:#111;">{film_title}</div>
        </td>
        <td style="width:10px;"></td>
        <td style="padding:8px;background:#f9f9f9;border-radius:4px;width:50%;">
          <div style="font-size:11px;color:#888;text-transform:uppercase;">URLs Found</div>
          <div style="font-size:16px;font-weight:bold;color:{severity_color};">{hit_count} platforms</div>
        </td>
      </tr>
    </table>

    <h3 style="color:#333;font-size:14px;border-bottom:1px solid #eee;padding-bottom:8px;">Infringing URLs Detected</h3>
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <th style="text-align:left;padding:8px;background:#f0f0f0;font-size:11px;text-transform:uppercase;">URL</th>
        <th style="text-align:left;padding:8px;background:#f0f0f0;font-size:11px;text-transform:uppercase;">Platform</th>
      </tr>
      {url_rows}
    </table>

    <div style="margin-top:20px;padding:15px;background:#fff5e6;border-radius:4px;border:1px solid #ffcc88;">
      <h3 style="color:#cc6600;margin:0 0 10px;font-size:14px;">Recommended Immediate Actions</h3>
      <ol style="margin:0;padding-left:20px;font-size:13px;color:#555;">
        <li style="margin-bottom:5px;">File DMCA with Google: <a href="https://search.google.com/search-console" style="color:#0066cc;">search.google.com/search-console</a></li>
        <li style="margin-bottom:5px;">Report to MIB: <a href="mailto:nodalofficer@meity.gov.in" style="color:#0066cc;">nodalofficer@meity.gov.in</a></li>
        <li style="margin-bottom:5px;">File with TFCC: <a href="https://tfcc.in" style="color:#0066cc;">tfcc.in</a></li>
      </ol>
    </div>

    <div style="margin-top:20px;text-align:center;">
      <a href="https://cineos.in/cineos_platform.html" 
         style="background:#00aa55;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:14px;">
        View Full Intelligence Report →
      </a>
    </div>

    <p style="margin-top:20px;font-size:11px;color:#aaa;text-align:center;">
      Detected: {now}<br>
      CINEOS Anti-Piracy Intelligence | US Patent 64/049,190<br>
      yugandhar@cineos.in
    </p>

  </div>
</body>
</html>"""

    # Plain text fallback
    text = f"""CINEOS PIRACY ALERT

Film: {film_title}
Verdict: {verdict}
URLs Found: {hit_count}
Detected: {now}

Infringing URLs:
""" + "\n".join([
        (hit.get("url","") if isinstance(hit,dict) else getattr(hit,"url",""))
        for hit in hits[:10]
    ]) + f"""

Recommended Actions:
1. File DMCA: search.google.com/search-console
2. Report to MIB: nodalofficer@meity.gov.in
3. File with TFCC: tfcc.in

View full report: https://cineos.in/cineos_platform.html

CINEOS | Patent 64/049,190 | yugandhar@cineos.in"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🚨 CINEOS Alert: Piracy detected for {film_title} — {hit_count} URLs found"
        msg["From"] = f"CINEOS Intelligence <{GMAIL_USER}>"
        msg["To"] = to_email
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.ehlo()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        
        print(f"Alert sent to {to_email} for {film_title}")
        return True

    except Exception as e:
        print(f"Email failed: {e}")
        return False


def test_alert():
    """Test with fake data."""
    fake_hits = [
        {"url": "https://www.1tamilblasters.luxe/retro-2025-telugu/", "platform": "TamilBlasters"},
        {"url": "https://moviesda28.info/retro-2025-telugu-movie/", "platform": "Moviesda"},
        {"url": "https://www.5movierulz.markets/retro-2025-telugu/", "platform": "Movierulz"},
    ]
    result = send_alert_email(
        to_email=GMAIL_USER,
        film_title="Retro (Test Alert)",
        verdict="HIGH — CAM copy confirmed",
        hits=fake_hits
    )
    print(f"Test result: {'SUCCESS' if result else 'FAILED — set GMAIL_APP_PASSWORD'}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--film", default="")
    ap.add_argument("--email", default=GMAIL_USER)
    args = ap.parse_args()

    if args.test:
        test_alert()
    elif args.film:
        import sys, os
        sys.path.insert(0, ".")
        os.environ.setdefault("SERP_API_KEY",
            "2b37951bf87af21c398c270f8c02db7236c035120cfe4986a39b053f369468e1")
        
        async def run():
            from cineos_india import full_india_scan
            result = await full_india_scan(args.film)
            hits = result.get("hits", [])
            if hits:
                send_alert_email(args.email, args.film,
                    result.get("verdict",""), hits)
            else:
                print(f"No piracy found for {args.film}")
        
        asyncio.run(run())
