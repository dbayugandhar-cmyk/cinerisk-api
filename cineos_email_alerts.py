"""
cineos_email_alerts.py
CINEOS Anti-Piracy Platform — SendGrid Email Alert System
US Provisional Patent 64/049,190
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional
import urllib.parse

logger = logging.getLogger(__name__)

SENDGRID_API_KEY  = os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL        = "alerts@cineos.io"
FROM_NAME         = "CINEOS Anti-Piracy"
TO_EMAIL          = "dba.yugandhar@gmail.com"
DASHBOARD_URL     = "https://dbayugandhar-cmyk.github.io/cinerisk-api/cineos_platform.html"
API_BASE_URL      = "https://cinerisk-api-production.up.railway.app"


# ─── Public API ───────────────────────────────────────────────────────────────

def send_piracy_alert(
    film: str,
    platform: str,
    url: str,
    verdict: str,
    quality: str = "UNKNOWN",
    detected_at: Optional[datetime] = None,
) -> bool:
    """
    Send an immediate piracy detection alert.

    Args:
        film:        Title of the detected content.
        platform:    Platform where piracy was found (e.g. "Telegram").
        url:         Infringing URL.
        verdict:     CONFIRMED / HIGH / MEDIUM / LOW
        quality:     CAM / HDRip / WEB-DL / UNKNOWN
        detected_at: UTC datetime. Defaults to now.

    Returns:
        True if sent successfully, False otherwise (never raises).
    """
    try:
        _check_sendgrid()
        detected_at = detected_at or datetime.now(timezone.utc)
        timestamp   = detected_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        dmca_link   = _dmca_link(film, url)
        verdict_uc  = verdict.upper()

        subject  = f"CINEOS ALERT — {film} {verdict_uc} copy detected on {platform}"
        html     = _alert_html(film, platform, url, verdict_uc, quality, timestamp, dmca_link)
        text     = _alert_text(film, platform, url, verdict_uc, quality, timestamp, dmca_link)

        return _send(TO_EMAIL, subject, html, text)

    except Exception as e:
        logger.error(f"[CINEOS Alerts] send_piracy_alert failed: {e}")
        return False


def send_daily_summary(scan_results_list: list) -> bool:
    """
    Send a daily summary of all detections.

    Args:
        scan_results_list: List of dicts, each with keys:
            film, platform, url, verdict, quality, detected_at (optional)

    Returns:
        True if sent successfully, False otherwise (never raises).
    """
    try:
        _check_sendgrid()
        if not scan_results_list:
            logger.info("[CINEOS Alerts] No detections to summarise — skipping daily email.")
            return True

        now       = datetime.now(timezone.utc)
        date_str  = now.strftime("%Y-%m-%d")
        confirmed = [r for r in scan_results_list if r.get("verdict", "").upper() in ("CONFIRMED", "HIGH")]
        subject   = f"CINEOS Daily Summary — {len(confirmed)} confirmed detections on {date_str}"
        html      = _summary_html(scan_results_list, confirmed, date_str)
        text      = _summary_text(scan_results_list, confirmed, date_str)

        return _send(TO_EMAIL, subject, html, text)

    except Exception as e:
        logger.error(f"[CINEOS Alerts] send_daily_summary failed: {e}")
        return False


# ─── SendGrid send ────────────────────────────────────────────────────────────

def _check_sendgrid():
    if not SENDGRID_API_KEY:
        raise EnvironmentError("SENDGRID_API_KEY is not set in environment.")


def _send(to_email: str, subject: str, html: str, text: str) -> bool:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=(FROM_EMAIL, FROM_NAME),
            to_emails=to_email,
            subject=subject,
            html_content=html,
            plain_text_content=text,
        )
        sg       = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        if response.status_code in (200, 202):
            logger.info(f"[CINEOS Alerts] Email sent to {to_email} (HTTP {response.status_code})")
            return True
        else:
            logger.error(f"[CINEOS Alerts] SendGrid returned HTTP {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"[CINEOS Alerts] SendGrid send error: {e}")
        return False


# ─── URL helpers ──────────────────────────────────────────────────────────────

def _dmca_link(film: str, url: str) -> str:
    params = urllib.parse.urlencode({"title": film, "url": url})
    return f"{API_BASE_URL}/dmca/generate?{params}"


# ─── HTML / text builders ─────────────────────────────────────────────────────

def _verdict_color(verdict: str) -> str:
    return {"CONFIRMED": "#e63333", "HIGH": "#e67e00", "MEDIUM": "#ccaa00", "LOW": "#4da6ff"}.get(verdict, "#888")


def _alert_html(film, platform, url, verdict, quality, timestamp, dmca_link) -> str:
    vc = _verdict_color(verdict)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<style>
  body      {{margin:0;padding:0;background:#0a0a0a;font-family:Arial,sans-serif;color:#f0f0f0}}
  .wrap     {{max-width:600px;margin:40px auto;background:#111;border:1px solid #222;border-radius:8px;overflow:hidden}}
  .hdr      {{background:#0d0d0d;padding:24px 32px;border-bottom:3px solid {vc}}}
  .logo     {{font-size:24px;font-weight:700;letter-spacing:3px;color:#fff}}
  .logo span{{color:{vc}}}
  .badge    {{display:inline-block;background:{vc};color:#fff;font-size:11px;font-weight:700;
              padding:4px 14px;border-radius:20px;letter-spacing:1px;margin-top:10px}}
  .body     {{padding:32px}}
  .headline {{font-size:18px;font-weight:700;margin-bottom:24px;color:#fff}}
  table     {{width:100%;border-collapse:collapse;margin-bottom:28px}}
  td        {{padding:11px 14px;border-bottom:1px solid #1e1e1e;font-size:14px}}
  td:first-child{{color:#888;width:130px;white-space:nowrap}}
  td:last-child {{color:#eee;word-break:break-all}}
  .btn      {{display:inline-block;background:{vc};color:#fff;padding:13px 26px;border-radius:6px;
              text-decoration:none;font-weight:700;font-size:14px;margin-right:10px;margin-bottom:10px}}
  .btn2     {{display:inline-block;background:#1a1a1a;color:#bbb;padding:13px 26px;border-radius:6px;
              text-decoration:none;font-weight:600;font-size:14px;border:1px solid #2e2e2e;margin-bottom:10px}}
  .foot     {{background:#080808;padding:18px 32px;font-size:11px;color:#444;border-top:1px solid #1a1a1a}}
  a.url     {{color:#4da6ff;word-break:break-all}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <div class="logo">CINE<span>OS</span></div>
    <div class="badge">⚠&nbsp; {verdict} DETECTION</div>
  </div>
  <div class="body">
    <div class="headline">Piracy detected: {film}</div>
    <table>
      <tr><td>Content</td>       <td>{film}</td></tr>
      <tr><td>Platform</td>      <td>{platform}</td></tr>
      <tr><td>Quality</td>       <td>{quality}</td></tr>
      <tr><td>Verdict</td>       <td><strong style="color:{vc}">{verdict}</strong></td></tr>
      <tr><td>Detected (UTC)</td><td>{timestamp}</td></tr>
      <tr><td>Infringing URL</td><td><a class="url" href="{url}">{url}</a></td></tr>
    </table>
    <a href="{dmca_link}" class="btn">📄 View DMCA Report</a>
    <a href="{DASHBOARD_URL}" class="btn2">🔍 Open Dashboard</a>
  </div>
  <div class="foot">
    CINEOS Anti-Piracy Platform &nbsp;·&nbsp; US Provisional Patent 64/049,190<br>
    Automated alert — do not reply to this email.
  </div>
</div>
</body>
</html>"""


def _alert_text(film, platform, url, verdict, quality, timestamp, dmca_link) -> str:
    return f"""CINEOS ANTI-PIRACY ALERT
========================
Content:        {film}
Platform:       {platform}
Quality:        {quality}
Verdict:        {verdict}
Detected (UTC): {timestamp}
Infringing URL: {url}

View DMCA Report:  {dmca_link}
Open Dashboard:    {DASHBOARD_URL}

--
CINEOS Anti-Piracy Platform | US Provisional Patent 64/049,190
Automated alert — do not reply.
"""


def _summary_html(results: list, confirmed: list, date_str: str) -> str:
    rows = ""
    for r in sorted(results, key=lambda x: x.get("verdict", ""), reverse=True):
        vc    = _verdict_color(r.get("verdict", "").upper())
        film  = r.get("film", "—")
        plat  = r.get("platform", "—")
        qual  = r.get("quality", "—")
        verd  = r.get("verdict", "—").upper()
        url   = r.get("url", "")
        dmca  = _dmca_link(film, url)
        rows += f"""
        <tr>
          <td>{film}</td>
          <td>{plat}</td>
          <td>{qual}</td>
          <td><strong style="color:{vc}">{verd}</strong></td>
          <td><a href="{dmca}" style="color:#4da6ff;font-size:12px">DMCA</a></td>
        </tr>"""

    total     = len(results)
    confirmed_count = len(confirmed)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<style>
  body  {{margin:0;padding:0;background:#0a0a0a;font-family:Arial,sans-serif;color:#f0f0f0}}
  .wrap {{max-width:680px;margin:40px auto;background:#111;border:1px solid #222;border-radius:8px;overflow:hidden}}
  .hdr  {{background:#0d0d0d;padding:24px 32px;border-bottom:3px solid #e63333}}
  .logo {{font-size:24px;font-weight:700;letter-spacing:3px;color:#fff}}
  .logo span{{color:#e63333}}
  .sub  {{color:#888;font-size:13px;margin-top:6px}}
  .body {{padding:32px}}
  .stats{{display:flex;gap:20px;margin-bottom:28px}}
  .stat {{flex:1;background:#0d0d0d;border:1px solid #222;border-radius:6px;padding:16px;text-align:center}}
  .stat .n{{font-size:32px;font-weight:700;color:#e63333}}
  .stat .l{{font-size:12px;color:#666;margin-top:4px}}
  table {{width:100%;border-collapse:collapse;font-size:13px}}
  th    {{background:#0d0d0d;color:#666;padding:10px 12px;text-align:left;font-weight:600;
          border-bottom:1px solid #222;font-size:11px;letter-spacing:0.5px;text-transform:uppercase}}
  td    {{padding:10px 12px;border-bottom:1px solid #1a1a1a;color:#ddd}}
  .btn  {{display:inline-block;background:#e63333;color:#fff;padding:13px 26px;border-radius:6px;
          text-decoration:none;font-weight:700;font-size:14px;margin-top:24px}}
  .foot {{background:#080808;padding:18px 32px;font-size:11px;color:#444;border-top:1px solid #1a1a1a}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <div class="logo">CINE<span>OS</span></div>
    <div class="sub">Daily Detection Summary — {date_str}</div>
  </div>
  <div class="body">
    <div class="stats">
      <div class="stat"><div class="n">{total}</div><div class="l">Total Detections</div></div>
      <div class="stat"><div class="n">{confirmed_count}</div><div class="l">Confirmed / High</div></div>
      <div class="stat"><div class="n">{total - confirmed_count}</div><div class="l">Medium / Low</div></div>
    </div>
    <table>
      <tr><th>Content</th><th>Platform</th><th>Quality</th><th>Verdict</th><th>Action</th></tr>
      {rows}
    </table>
    <a href="{DASHBOARD_URL}" class="btn">🔍 Open Dashboard</a>
  </div>
  <div class="foot">
    CINEOS Anti-Piracy Platform &nbsp;·&nbsp; US Provisional Patent 64/049,190<br>
    Automated daily summary — do not reply.
  </div>
</div>
</body>
</html>"""


def _summary_text(results: list, confirmed: list, date_str: str) -> str:
    lines = [
        f"CINEOS DAILY SUMMARY — {date_str}",
        "=" * 40,
        f"Total detections:    {len(results)}",
        f"Confirmed / High:    {len(confirmed)}",
        f"Medium / Low:        {len(results) - len(confirmed)}",
        "",
        f"{'Content':<30} {'Platform':<20} {'Quality':<10} {'Verdict'}",
        "-" * 80,
    ]
    for r in sorted(results, key=lambda x: x.get("verdict", ""), reverse=True):
        lines.append(
            f"{r.get('film','—'):<30} {r.get('platform','—'):<20} "
            f"{r.get('quality','—'):<10} {r.get('verdict','—').upper()}"
        )
    lines += ["", f"Dashboard: {DASHBOARD_URL}", "", "--",
              "CINEOS Anti-Piracy Platform | US Provisional Patent 64/049,190"]
    return "\n".join(lines)


# ─── Quick smoke test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Testing send_piracy_alert...")
    ok = send_piracy_alert(
        film="Michael 2026",
        platform="Telegram",
        url="https://t.me/example_piracy_channel",
        verdict="CONFIRMED",
        quality="CAM",
    )
    print("✅ Alert sent" if ok else "❌ Alert failed — check SENDGRID_API_KEY & sender verification")

    print("\nTesting send_daily_summary...")
    ok2 = send_daily_summary([
        {"film": "Michael 2026",   "platform": "Telegram",    "url": "https://t.me/x", "verdict": "CONFIRMED", "quality": "CAM"},
        {"film": "Retro 2025",     "platform": "Movierulz",   "url": "https://mvrz.io/retro", "verdict": "HIGH",      "quality": "HDRip"},
        {"film": "Baldur's Gate 3","platform": "FitGirl",     "url": "https://fitgirl-repacks.site/bg3", "verdict": "CONFIRMED", "quality": "FULL"},
    ])
    print("✅ Summary sent" if ok2 else "❌ Summary failed")
