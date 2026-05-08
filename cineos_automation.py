"""
CINEOS Automation Engine
Legal automated anti-piracy workflows:
- DMCA notices to Google (official Search Console API)
- Cloudflare abuse reports (public abuse form)
- Email alerts (Gmail SMTP)
- Daily digest
- Match-day monitoring cron
"""
import asyncio, httpx, smtplib, json, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

GMAIL_PASS = os.environ.get('GMAIL_APP_PASSWORD','')
GMAIL_FROM = 'dba.yugandhar@gmail.com'
SERP_KEY = os.environ.get('SERP_API_KEY','')

# ── 1. GOOGLE DMCA TAKEDOWN ───────────────────────────────
async def submit_google_dmca(
    infringing_urls: list,
    original_work: str,
    copyright_owner: str = "Yugandhar Mallavarapu / CINEOS"
) -> dict:
    """
    Submit DMCA takedown to Google Search Console.
    Uses Google's official public DMCA submission endpoint.
    Legal: This is the standard process for copyright holders.
    """
    print(f"[DMCA] Preparing Google DMCA for {len(infringing_urls)} URLs")
    
    # Google's official DMCA submission URL
    dmca_url = "https://www.google.com/webmasters/tools/dmca-request"
    
    # Build the DMCA notice
    urls_list = '\n'.join(infringing_urls[:10])
    
    dmca_notice = {
        'copyright_owner': copyright_owner,
        'original_work': original_work,
        'infringing_urls': infringing_urls[:10],
        'legal_basis': 'Copyright Act 1957 (India) + DMCA 17 U.S.C. 512',
        'submission_url': dmca_url,
        'instructions': (
            'Submit manually at: https://reportcontent.google.com/forms/rtbf\n'
            'Or use: https://support.google.com/legal/contact/lr_dmca\n\n'
            f'Infringing URLs:\n{urls_list}'
        ),
        'automated_filing': False,
        'note': 'Google requires manual DMCA submission via their web form'
    }
    
    print(f"[DMCA] DMCA notice prepared for {original_work}")
    print(f"[DMCA] Submit at: https://reportcontent.google.com/forms/rtbf")
    
    return dmca_notice

# ── 2. CLOUDFLARE ABUSE REPORT ───────────────────────────
async def submit_cloudflare_abuse(
    domain: str,
    abuse_type: str = "copyright",
    description: str = ""
) -> dict:
    """
    Submit abuse report to Cloudflare.
    Uses Cloudflare's public abuse reporting API.
    Legal: Standard process for reporting ToS violations.
    """
    print(f"[CF] Preparing Cloudflare abuse report for {domain}")
    
    report = {
        'domain': domain,
        'abuse_type': abuse_type,
        'submission_url': 'https://abuse.cloudflare.com/',
        'api_endpoint': 'https://api.cloudflare.com/client/v4/abuse_reports',
        'instructions': (
            f'Submit at: https://abuse.cloudflare.com/\n'
            f'Domain: {domain}\n'
            f'Type: Copyright Infringement\n'
            f'Description: {description[:200]}'
        ),
        'note': 'Cloudflare abuse reports require submission via web form'
    }
    
    # Try Cloudflare public abuse API
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                'https://abuse.cloudflare.com/api/submit',
                json={
                    'name': copyright_owner if 'copyright_owner' in dir() else 'CINEOS',
                    'email': GMAIL_FROM,
                    'abuse_type': 'copyright',
                    'domain': domain,
                    'description': description[:500],
                }
            )
            if r.status_code in [200, 201]:
                report['submitted'] = True
                print(f"[CF] Abuse report submitted for {domain}")
            else:
                report['submitted'] = False
                report['fallback'] = f"Use: https://abuse.cloudflare.com/"
        except:
            report['submitted'] = False
            report['fallback'] = f"Use: https://abuse.cloudflare.com/"
    
    return report

# ── 3. EMAIL ALERTS ───────────────────────────────────────
def send_alert_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: str = ""
) -> bool:
    """Send email alert via Gmail SMTP."""
    if not GMAIL_PASS:
        print("[EMAIL] No Gmail password set")
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = GMAIL_FROM
        msg['To'] = to_email
        
        if body_text:
            msg.attach(MIMEText(body_text, 'plain'))
        msg.attach(MIMEText(body_html, 'html'))
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_FROM, GMAIL_PASS)
            server.sendmail(GMAIL_FROM, to_email, msg.as_string())
        
        print(f"[EMAIL] Alert sent to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL] Failed: {e}")
        return False

def build_alert_html(title: str, hits: list, verdict: str, scan_time: str) -> str:
    rows = ''.join([
        f'<tr><td style="padding:8px;border:1px solid #ddd;">'
        f'<a href="{h.get("url","")}">{h.get("url","")[:60]}</a></td>'
        f'<td style="padding:8px;border:1px solid #ddd;">{h.get("platform","")}</td>'
        f'<td style="padding:8px;border:1px solid #ddd;">{h.get("quality","")}</td></tr>'
        for h in hits[:10]
    ])
    
    color = '#cc0000' if 'CRITICAL' in verdict or 'CONFIRMED' in verdict else '#007744'
    
    return f'''
<html><body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
<div style="background:#050508;color:#00e87a;padding:20px;text-align:center;">
  <h1 style="margin:0;font-size:24px;">CINEOS Alert</h1>
  <p style="margin:5px 0;font-size:12px;">Anti-Piracy Intelligence | cineos.in</p>
</div>
<div style="padding:20px;background:#f9f9f9;">
  <h2 style="color:{color};">{verdict}</h2>
  <p><strong>Content:</strong> {title}</p>
  <p><strong>Detected:</strong> {scan_time}</p>
  <p><strong>URLs Found:</strong> {len(hits)}</p>
  <table style="width:100%;border-collapse:collapse;margin-top:15px;">
    <tr style="background:#333;color:#fff;">
      <th style="padding:8px;text-align:left;">Infringing URL</th>
      <th style="padding:8px;">Platform</th>
      <th style="padding:8px;">Quality</th>
    </tr>
    {rows}
  </table>
</div>
<div style="padding:15px;background:#050508;color:#888;font-size:11px;text-align:center;">
  CINEOS Anti-Piracy Intelligence | cineos.in | US Patent 64/049,190<br>
  yugandhar@cineos.in
</div>
</body></html>'''

# ── 4. DAILY DIGEST ───────────────────────────────────────
async def run_daily_digest(
    films: list,
    recipient: str
) -> dict:
    """
    Scan multiple films and send daily intelligence digest.
    """
    print(f"[DIGEST] Running daily digest for {len(films)} films...")
    results = []
    
    async with httpx.AsyncClient(timeout=20) as client:
        for film in films:
            try:
                r = await client.post(
                    'https://cinerisk-api-production.up.railway.app/v1/scan',
                    json={'title': film, 'category': 'india'}
                )
                data = r.json().get('data', {})
                results.append({
                    'film': film,
                    'verdict': data.get('verdict', 'UNKNOWN'),
                    'hits': data.get('hits_found', 0),
                    'urls': data.get('hits', [])
                })
                print(f"  {film}: {data.get('verdict')} ({data.get('hits_found')} hits)")
            except Exception as e:
                print(f"  {film}: Error — {e}")
    
    # Build digest email
    total_hits = sum(r['hits'] for r in results)
    critical = [r for r in results if 'CRITICAL' in r['verdict'] or 'CONFIRMED' in r['verdict']]
    
    now = datetime.now().strftime('%B %d, %Y')
    
    rows = ''.join([
        f'<tr style="background:{"#fff5f5" if "CONFIRMED" in r["verdict"] or "CRITICAL" in r["verdict"] else "#f5fff5"};">'
        f'<td style="padding:8px;border:1px solid #ddd;">{r["film"]}</td>'
        f'<td style="padding:8px;border:1px solid #ddd;color:{"#cc0000" if "CONFIRMED" in r["verdict"] else "#007744"};">'
        f'{r["verdict"]}</td>'
        f'<td style="padding:8px;border:1px solid #ddd;text-align:center;">{r["hits"]}</td></tr>'
        for r in results
    ])
    
    html = f'''
<html><body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
<div style="background:#050508;color:#00e87a;padding:20px;text-align:center;">
  <h1 style="margin:0;">CINEOS Daily Intelligence Digest</h1>
  <p style="margin:5px 0;font-size:12px;">{now} | cineos.in</p>
</div>
<div style="padding:20px;">
  <div style="display:flex;gap:20px;margin-bottom:20px;">
    <div style="background:#fff5f5;border:1px solid #ffcccc;padding:15px;border-radius:6px;flex:1;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#cc0000;">{total_hits}</div>
      <div>Total Piracy URLs</div>
    </div>
    <div style="background:#fff5f5;border:1px solid #ffcccc;padding:15px;border-radius:6px;flex:1;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#cc0000;">{len(critical)}</div>
      <div>Films Affected</div>
    </div>
    <div style="background:#f5fff5;border:1px solid #ccffcc;padding:15px;border-radius:6px;flex:1;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#007744;">{len(films)}</div>
      <div>Films Scanned</div>
    </div>
  </div>
  <table style="width:100%;border-collapse:collapse;">
    <tr style="background:#333;color:#fff;">
      <th style="padding:8px;text-align:left;">Film</th>
      <th style="padding:8px;">Verdict</th>
      <th style="padding:8px;">URLs Found</th>
    </tr>
    {rows}
  </table>
</div>
<div style="padding:15px;background:#050508;color:#888;font-size:11px;text-align:center;">
  CINEOS Anti-Piracy Intelligence | cineos.in | US Patent 64/049,190
</div>
</body></html>'''
    
    subject = f"CINEOS Daily Digest — {total_hits} piracy URLs detected — {now}"
    sent = send_alert_email(recipient, subject, html)
    
    return {
        'films_scanned': len(films),
        'total_hits': total_hits,
        'critical_films': len(critical),
        'email_sent': sent,
        'results': results
    }

# ── 5. MATCH-DAY LIVE MONITOR ─────────────────────────────
async def match_day_monitor(
    event: str,
    recipient: str,
    interval_mins: int = 30
) -> None:
    """
    Monitor Telegram channels during a live match.
    Sends alerts when new piracy channels are detected.
    Run this during IPL/cricket matches.
    """
    print(f"[MONITOR] Starting match-day monitor: {event}")
    print(f"[MONITOR] Checking every {interval_mins} minutes")
    print(f"[MONITOR] Alerts to: {recipient}")
    
    previous_channels = set()
    scan_count = 0
    
    while True:
        scan_count += 1
        print(f"\n[MONITOR] Scan #{scan_count} — {datetime.now().strftime('%H:%M:%S')}")
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    'https://cinerisk-api-production.up.railway.app/v1/live_shield',
                    json={'event': event}
                )
                data = r.json().get('data', {})
                streams = data.get('streams', [])
                
                # Find channels with real subscribers
                active = {
                    s['channel'] for s in streams
                    if s.get('subscriber_count', 0) > 0
                }
                betting = {
                    s['channel'] for s in streams
                    if s.get('is_betting')
                }
                
                # Detect new channels since last scan
                new_channels = active - previous_channels
                
                print(f"  Active channels: {len(active)}")
                print(f"  Betting channels: {len(betting)}")
                if new_channels:
                    print(f"  NEW: {new_channels}")
                
                # Send alert if new channels found
                if new_channels or (scan_count == 1 and active):
                    top = sorted(streams, key=lambda x:x.get('subscriber_count',0), reverse=True)
                    alert_rows = ''.join([
                        f'<tr><td style="padding:6px;border:1px solid #ddd;">@{s["channel"]}</td>'
                        f'<td style="padding:6px;border:1px solid #ddd;">{s.get("subscriber_count",0):,}</td>'
                        f'<td style="padding:6px;border:1px solid #ddd;color:{"#b060ff" if s.get("is_betting") else "#cc0000"};">'
                        f'{"BETTING" if s.get("is_betting") else "STREAM"}</td></tr>'
                        for s in top[:10]
                    ])
                    
                    html = f'''<html><body style="font-family:Arial,sans-serif;">
<div style="background:#050508;color:#00e87a;padding:15px;">
  <h2 style="margin:0;">CINEOS LIVE ALERT</h2>
  <p style="margin:5px 0;">{event} — {datetime.now().strftime("%H:%M IST")}</p>
</div>
<div style="padding:15px;">
  <p style="color:#cc0000;font-size:18px;font-weight:bold;">
    {len(active)} illegal streams detected | {len(betting)} betting channels
  </p>
  {f'<p style="color:#cc0000;"><strong>NEW channels: {", ".join("@"+c for c in new_channels)}</strong></p>' if new_channels else ''}
  <table style="width:100%;border-collapse:collapse;margin-top:10px;">
    <tr style="background:#333;color:#fff;">
      <th style="padding:6px;">Channel</th>
      <th style="padding:6px;">Subscribers</th>
      <th style="padding:6px;">Type</th>
    </tr>
    {alert_rows}
  </table>
</div>
</body></html>'''
                    
                    subject = f"CINEOS LIVE: {len(active)} illegal streams — {event}"
                    send_alert_email(recipient, subject, html)
                
                previous_channels = active
                
        except Exception as e:
            print(f"[MONITOR] Error: {e}")
        
        print(f"[MONITOR] Next scan in {interval_mins} minutes...")
        await asyncio.sleep(interval_mins * 60)

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['digest','monitor','dmca','test'],
                    default='test')
    ap.add_argument('--email', default='dba.yugandhar@gmail.com')
    ap.add_argument('--event', default='IPL 2026')
    ap.add_argument('--films', nargs='+',
                    default=['Retro','Devara','Kalki 2898 AD','Lucky Bhaskar'])
    args = ap.parse_args()
    
    if args.mode == 'digest':
        result = asyncio.run(run_daily_digest(args.films, args.email))
        print(f"\nDigest: {result['total_hits']} hits across {result['films_scanned']} films")
        print(f"Email sent: {result['email_sent']}")
    
    elif args.mode == 'monitor':
        print(f"Starting match-day monitor for: {args.event}")
        print("Press Ctrl+C to stop")
        asyncio.run(match_day_monitor(args.event, args.email, interval_mins=5))
    
    elif args.mode == 'dmca':
        notice = asyncio.run(submit_google_dmca(
            ['https://www.5movierulz.markets/retro-2025-tamil/'],
            'Retro (2025 Film)'
        ))
        print(json.dumps(notice, indent=2))
    
    elif args.mode == 'test':
        print("Testing email alert...")
        sent = send_alert_email(
            args.email,
            'CINEOS Test Alert',
            '<h1>CINEOS Automation Working</h1><p>Email alerts are configured.</p>',
        )
        print(f"Email sent: {sent}")
