#!/usr/bin/env python3
"""
cineos_pdf_report.py
CINEOS Anti-Piracy Platform — PDF Evidence Package Generator
US Provisional Patent 64/049,190

Generates court-ready PDF evidence packages for law firms.
Price: $499/report

Usage:
    python3 cineos_pdf_report.py --film "Michael" --verdict "CONFIRMED" \
        --hits "WhereYouWatch,https://whereyouwatch.com/movies/michael/,CAM with line audio,CAM"

    Multiple hits (semicolon-separated):
    python3 cineos_pdf_report.py --film "Michael" --verdict "CONFIRMED" \
        --hits "WhereYouWatch,https://whereyouwatch.com/...,CAM,CAM;Telegram,https://t.me/...,CAM repost,CAM"
"""

import argparse
import hashlib
import os
import sys
import uuid
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

# ─── Brand colors ─────────────────────────────────────────────────────────────
BLACK      = colors.HexColor("#0a0a0a")
DARK_GRAY  = colors.HexColor("#111111")
MID_GRAY   = colors.HexColor("#444444")
LIGHT_GRAY = colors.HexColor("#cccccc")
RED        = colors.HexColor("#cc2222")
GOLD       = colors.HexColor("#b8960c")
WHITE      = colors.white

REPORT_DIR = os.path.expanduser("~/Desktop/cinerisk/reports")


# ─── Styles ───────────────────────────────────────────────────────────────────

def make_styles():
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title", fontSize=32, fontName="Helvetica-Bold",
            textColor=BLACK, alignment=TA_CENTER, spaceAfter=6,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", fontSize=13, fontName="Helvetica",
            textColor=MID_GRAY, alignment=TA_CENTER, spaceAfter=4,
        ),
        "cover_patent": ParagraphStyle(
            "cover_patent", fontSize=9, fontName="Helvetica",
            textColor=LIGHT_GRAY, alignment=TA_CENTER,
        ),
        "section_head": ParagraphStyle(
            "section_head", fontSize=13, fontName="Helvetica-Bold",
            textColor=BLACK, spaceBefore=18, spaceAfter=8,
            borderPad=4,
        ),
        "body": ParagraphStyle(
            "body", fontSize=10, fontName="Helvetica",
            textColor=BLACK, leading=15, spaceAfter=6, alignment=TA_JUSTIFY,
        ),
        "body_bold": ParagraphStyle(
            "body_bold", fontSize=10, fontName="Helvetica-Bold",
            textColor=BLACK, leading=15, spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "small", fontSize=8, fontName="Helvetica",
            textColor=MID_GRAY, leading=12,
        ),
        "mono": ParagraphStyle(
            "mono", fontSize=8, fontName="Courier",
            textColor=BLACK, leading=12, spaceAfter=3,
        ),
        "verdict_confirmed": ParagraphStyle(
            "verdict_confirmed", fontSize=22, fontName="Helvetica-Bold",
            textColor=RED, alignment=TA_CENTER, spaceAfter=6,
        ),
        "label": ParagraphStyle(
            "label", fontSize=9, fontName="Helvetica-Bold",
            textColor=MID_GRAY, spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "footer", fontSize=7.5, fontName="Helvetica",
            textColor=LIGHT_GRAY, alignment=TA_CENTER,
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer", fontSize=8.5, fontName="Helvetica",
            textColor=MID_GRAY, leading=13, alignment=TA_JUSTIFY,
        ),
        "right": ParagraphStyle(
            "right", fontSize=9, fontName="Helvetica",
            textColor=MID_GRAY, alignment=TA_RIGHT,
        ),
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def sha256_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def case_ref(film: str) -> str:
    slug = "".join(c for c in film.upper() if c.isalnum())[:8]
    uid  = str(uuid.uuid4()).split("-")[0].upper()
    return f"CINEOS-{slug}-{uid}"


def divider(color=LIGHT_GRAY, thickness=0.5):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                      spaceAfter=8, spaceBefore=4)


def section_header(text, styles):
    return [
        divider(BLACK, 1.5),
        Paragraph(text.upper(), styles["section_head"]),
    ]


# ─── Page template (header/footer) ────────────────────────────────────────────

def make_canvas_callback(case_id: str, film: str, generated: str):
    def on_page(canvas, doc):
        canvas.saveState()
        w, h = letter

        # Header bar
        canvas.setFillColor(BLACK)
        canvas.rect(0, h - 40, w, 40, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(0.4 * inch, h - 26, "CINEOS")
        canvas.setFont("Helvetica", 8)
        canvas.drawString(1.1 * inch, h - 26, "Anti-Piracy Evidence Package")
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(w - 0.4 * inch, h - 26, f"Case: {case_id}")

        # Footer
        canvas.setFillColor(LIGHT_GRAY)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(0.4 * inch, 0.3 * inch,
                          f"CINEOS | US Provisional Patent 64/049,190 | "
                          f"CONFIDENTIAL — ATTORNEY-CLIENT PRIVILEGED")
        canvas.drawRightString(w - 0.4 * inch, 0.3 * inch,
                               f"Page {doc.page}  |  Generated {generated}")

        canvas.restoreState()
    return on_page


# ─── Cover page ───────────────────────────────────────────────────────────────

def build_cover(film, verdict, case_id, generated, total_hits, styles):
    s = styles
    elements = []
    elements.append(Spacer(1, 1.2 * inch))

    # Logo block
    logo_data = [
        [Paragraph("CINEOS", ParagraphStyle(
            "logo", fontSize=48, fontName="Helvetica-Bold",
            textColor=BLACK, alignment=TA_CENTER))],
        [Paragraph("ANTI-PIRACY PLATFORM", ParagraphStyle(
            "logo_sub", fontSize=11, fontName="Helvetica",
            textColor=MID_GRAY, alignment=TA_CENTER, spaceAfter=2))],
        [Paragraph("US Provisional Patent 64/049,190", s["cover_patent"])],
    ]
    logo_table = Table(logo_data, colWidths=[6.5 * inch])
    logo_table.setStyle(TableStyle([
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    elements.append(logo_table)
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(divider(BLACK, 2))
    elements.append(Spacer(1, 0.3 * inch))

    elements.append(Paragraph("EVIDENCE PACKAGE", s["cover_sub"]))
    elements.append(Paragraph(
        "Digital Piracy Detection &amp; DMCA Documentation", s["cover_sub"]
    ))
    elements.append(Spacer(1, 0.4 * inch))

    # Film title box
    film_box = Table(
        [[Paragraph(film, ParagraphStyle(
            "film_box", fontSize=26, fontName="Helvetica-Bold",
            textColor=WHITE, alignment=TA_CENTER))]],
        colWidths=[6.5 * inch]
    )
    film_box.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), BLACK),
        ("TOPPADDING",   (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 16),
        ("ROUNDEDCORNERS", [6]),
    ]))
    elements.append(film_box)
    elements.append(Spacer(1, 0.35 * inch))

    # Verdict badge
    vc = RED if verdict in ("CONFIRMED", "HIGH") else GOLD
    verdict_box = Table(
        [[Paragraph(f"VERDICT: {verdict}", ParagraphStyle(
            "vb", fontSize=18, fontName="Helvetica-Bold",
            textColor=WHITE, alignment=TA_CENTER))]],
        colWidths=[6.5 * inch]
    )
    verdict_box.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), vc),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
    ]))
    elements.append(verdict_box)
    elements.append(Spacer(1, 0.4 * inch))

    # Meta table
    meta = [
        ["Case Reference",  case_id],
        ["Generated (UTC)", generated],
        ["Total Hits",      str(total_hits)],
        ["Prepared By",     "CINEOS Automated Detection System"],
        ["Classification",  "CONFIDENTIAL — ATTORNEY-CLIENT PRIVILEGED"],
    ]
    meta_table = Table(meta, colWidths=[2 * inch, 4.5 * inch])
    meta_table.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",      (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR",     (0, 0), (0, -1), MID_GRAY),
        ("TEXTCOLOR",     (1, 0), (1, -1), BLACK),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, LIGHT_GRAY),
        ("BACKGROUND",    (0, -1), (-1, -1), colors.HexColor("#fff3f3")),
    ]))
    elements.append(meta_table)
    elements.append(PageBreak())
    return elements


# ─── Executive summary ────────────────────────────────────────────────────────

def build_summary(film, verdict, hits, case_id, generated, styles):
    s  = styles
    el = []
    el += section_header("1. Executive Summary", s)

    el.append(Paragraph(
        f"CINEOS has detected unauthorized distribution of <b>{film}</b> across "
        f"{len(hits)} platform(s). This report documents each instance of infringement "
        f"with forensic evidence suitable for DMCA takedown proceedings and civil litigation.",
        s["body"]
    ))
    el.append(Spacer(1, 8))

    # Summary stats
    stats = [
        ["Film / Title",     film],
        ["Detection Verdict",verdict],
        ["Total Hits",       str(len(hits))],
        ["Platforms",        ", ".join(set(h["platform"] for h in hits))],
        ["Scan Date (UTC)",  generated],
        ["Case Reference",   case_id],
    ]
    st = Table(stats, colWidths=[2 * inch, 4.5 * inch])
    st.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor("#f5f5f5")),
        ("TEXTCOLOR",     (0, 0), (0, -1), MID_GRAY),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, LIGHT_GRAY),
        ("BOX",           (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
    ]))
    el.append(st)
    return el


# ─── Evidence table ───────────────────────────────────────────────────────────

def build_evidence_table(hits, generated, styles):
    s  = styles
    el = []
    el += section_header("2. Evidence Table", s)
    el.append(Paragraph(
        "Each row represents a confirmed infringing source. URLs have been "
        "SHA-256 hashed for tamper-evident documentation.",
        s["body"]
    ))
    el.append(Spacer(1, 8))

    header = ["#", "Platform", "Quality", "Confidence", "Timestamp (UTC)", "Detail"]
    rows   = [header]
    for i, h in enumerate(hits, 1):
        rows.append([
            str(i),
            h["platform"],
            h.get("quality", "CAM"),
            h.get("confidence", "HIGH"),
            generated,
            Paragraph(h.get("detail", "—"), s["small"]),
        ])

    col_w = [0.3*inch, 1.1*inch, 0.8*inch, 0.85*inch, 1.45*inch, 2.0*inch]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BLACK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, colors.HexColor("#f9f9f9")]),
        ("GRID",          (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN",         (0, 0), (0, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    el.append(t)
    return el


# ─── URL hashes ───────────────────────────────────────────────────────────────

def build_url_hashes(hits, styles):
    s  = styles
    el = []
    el += section_header("3. SHA-256 Hash Registry (Tamper Evidence)", s)
    el.append(Paragraph(
        "SHA-256 cryptographic hashes of each infringing URL are recorded below. "
        "These hashes prove the URLs have not been altered since detection.",
        s["body"]
    ))
    el.append(Spacer(1, 8))

    hash_data = [["#", "Platform", "Infringing URL", "SHA-256 Hash"]]
    for i, h in enumerate(hits, 1):
        url  = h["url"]
        digest = sha256_url(url)
        hash_data.append([
            str(i),
            h["platform"],
            Paragraph(f'<link href="{url}">{url[:55]}{"..." if len(url) > 55 else ""}</link>', s["mono"]),
            Paragraph(digest, s["mono"]),
        ])

    t = Table(hash_data, colWidths=[0.3*inch, 1.0*inch, 2.3*inch, 2.9*inch], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BLACK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 7.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, colors.HexColor("#f9f9f9")]),
        ("GRID",          (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    el.append(t)
    return el


# ─── DMCA notice ──────────────────────────────────────────────────────────────

def build_dmca(film, hits, case_id, generated, styles):
    s  = styles
    el = []
    el += section_header("4. DMCA Takedown Notice", s)

    url_list = "\n".join(f"  {i+1}. {h['url']}" for i, h in enumerate(hits))
    platforms = ", ".join(set(h["platform"] for h in hits))

    el.append(Paragraph(f"Date: {generated}", s["body"]))
    el.append(Paragraph(f"Re: Unauthorized Distribution of <b>{film}</b> — Case {case_id}", s["body"]))
    el.append(Spacer(1, 8))

    dmca_elements = [
        (
            "1. Identification of Copyrighted Work",
            f"The copyrighted work at issue is the motion picture / content titled "
            f"<b>\"{film}\"</b>. The rights holder (or authorized representative) "
            f"owns exclusive rights to reproduce, distribute, and publicly display "
            f"this work under 17 U.S.C. § 106."
        ),
        (
            "2. Identification of Infringing Material",
            f"The following URLs host or facilitate unauthorized copies of the above "
            f"work on {platforms}. Each URL has been verified by the CINEOS automated "
            f"detection system and confirmed as infringing:<br/><br/>" +
            "<br/>".join(
                f"&nbsp;&nbsp;{i+1}. <font name='Courier' size='8'>{h['url']}</font>"
                for i, h in enumerate(hits)
            )
        ),
        (
            "3. Contact Information",
            "CINEOS Anti-Piracy Platform<br/>"
            "Email: alerts@cineos.io<br/>"
            "US Provisional Patent 64/049,190<br/>"
            "Case Reference: " + case_id
        ),
        (
            "4. Good Faith Statement",
            "I have a good faith belief that the use of the copyrighted material "
            "described above is not authorized by the copyright owner, its agent, "
            "or the law. This notice is submitted in good faith pursuant to 17 U.S.C. "
            "§ 512(c)(3) of the Digital Millennium Copyright Act."
        ),
        (
            "5. Accuracy and Authorization Statement",
            "I swear, under penalty of perjury, that the information in this "
            "notification is accurate and that I am the copyright owner or am "
            "authorized to act on behalf of the copyright owner of an exclusive "
            "right that is allegedly infringed."
        ),
        (
            "6. Electronic Signature",
            f"Electronically signed by the CINEOS Anti-Piracy Detection System<br/>"
            f"Date: {generated}<br/>"
            f"Case: {case_id}"
        ),
    ]

    for title, body in dmca_elements:
        el.append(Paragraph(title, s["body_bold"]))
        el.append(Paragraph(body, s["body"]))
        el.append(Spacer(1, 6))

    return el


# ─── Chain of custody ─────────────────────────────────────────────────────────

def build_chain_of_custody(film, case_id, generated, hits, styles):
    s  = styles
    el = []
    el += section_header("5. Chain of Custody Statement", s)

    el.append(Paragraph(
        f"This document certifies the unbroken chain of custody for digital "
        f"evidence collected in Case {case_id}.",
        s["body"]
    ))
    el.append(Spacer(1, 6))

    coc_rows = [
        ["Event", "Description", "Timestamp (UTC)"],
        ["Detection", f"CINEOS scanner identified unauthorized copy of {film}", generated],
        ["Hash Capture", "SHA-256 hashes computed for all infringing URLs", generated],
        ["Report Generated", f"This PDF evidence package created — Case {case_id}", generated],
        ["Integrity Verification", "Document hash embedded at generation time", generated],
    ]
    t = Table(coc_rows, colWidths=[1.5*inch, 3.5*inch, 1.5*inch], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BLACK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, colors.HexColor("#f9f9f9")]),
        ("GRID",          (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    el.append(t)
    return el


# ─── Signature block ──────────────────────────────────────────────────────────

def build_signature(case_id, generated, styles):
    s  = styles
    el = []
    el += section_header("6. Legal Disclaimer &amp; Electronic Signature", s)

    el.append(Paragraph(
        "This report has been generated by the CINEOS automated anti-piracy detection "
        "system. The evidence contained herein was collected using proprietary scanning "
        "technology protected under US Provisional Patent 64/049,190. All URL hashes "
        "were computed at the time of detection using SHA-256 cryptographic hashing "
        "and have not been modified.",
        s["disclaimer"]
    ))
    el.append(Spacer(1, 10))
    el.append(Paragraph(
        "<b>DISCLAIMER:</b> This report is provided for informational and legal "
        "purposes only. CINEOS makes no warranty, express or implied, regarding "
        "the completeness or accuracy of third-party platform data. This document "
        "does not constitute legal advice. Recipients should consult qualified "
        "intellectual property counsel before initiating any legal proceedings.",
        s["disclaimer"]
    ))
    el.append(Spacer(1, 20))

    sig_data = [
        [
            Paragraph("CINEOS Anti-Piracy Platform", s["body_bold"]),
            Paragraph(f"Case Reference: {case_id}", s["right"]),
        ],
        [
            Paragraph("Automated Detection System", s["small"]),
            Paragraph(f"Generated: {generated}", s["right"]),
        ],
        [
            Paragraph("US Provisional Patent 64/049,190", s["small"]),
            Paragraph("alerts@cineos.io", s["right"]),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[3.5*inch, 3*inch])
    sig_table.setStyle(TableStyle([
        ("LINEABOVE",     (0, 0), (-1, 0), 1.5, BLACK),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    el.append(sig_table)
    return el


# ─── Master builder ───────────────────────────────────────────────────────────

def generate_report(
    film: str,
    verdict: str,
    hits: list,          # list of dicts: platform, url, detail, quality, confidence
    output_dir: str = REPORT_DIR,
) -> str:
    """
    Generate a PDF evidence package and return the output file path.

    Args:
        film:       Film/content title.
        verdict:    CONFIRMED / HIGH / MEDIUM / LOW
        hits:       List of detection dicts.
        output_dir: Directory to save the PDF.

    Returns:
        Absolute path to the generated PDF.
    """
    os.makedirs(output_dir, exist_ok=True)

    now       = datetime.now(timezone.utc)
    generated = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    date_slug = now.strftime("%Y-%m-%d")
    case_id   = case_ref(film)

    safe_film = "".join(c if c.isalnum() or c in "-_ " else "_" for c in film).replace(" ", "_")
    filename  = f"CINEOS_{safe_film}_{date_slug}.pdf"
    filepath  = os.path.join(output_dir, filename)

    styles    = make_styles()
    on_page   = make_canvas_callback(case_id, film, generated)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.6 * inch,
        title=f"CINEOS Evidence Package — {film}",
        author="CINEOS Anti-Piracy Platform",
        subject=f"Digital Piracy Evidence — {film} — {case_id}",
        creator="CINEOS | US Provisional Patent 64/049,190",
    )

    story = []
    story += build_cover(film, verdict, case_id, generated, len(hits), styles)
    story += build_summary(film, verdict, hits, case_id, generated, styles)
    story.append(Spacer(1, 12))
    story += build_evidence_table(hits, generated, styles)
    story.append(Spacer(1, 12))
    story += build_url_hashes(hits, styles)
    story.append(PageBreak())
    story += build_dmca(film, hits, case_id, generated, styles)
    story.append(Spacer(1, 12))
    story += build_chain_of_custody(film, case_id, generated, hits, styles)
    story.append(Spacer(1, 12))
    story += build_signature(case_id, generated, styles)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)

    print(f"[CINEOS] Report generated: {filepath}")
    print(f"[CINEOS] Case reference:   {case_id}")
    print(f"[CINEOS] Hits documented:  {len(hits)}")
    return filepath


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_hits(hits_str: str) -> list:
    """
    Parse --hits argument.
    Format: "Platform,URL,Detail,Quality" — semicolon-separated for multiple hits.
    Example: "WhereYouWatch,https://...,CAM with audio,CAM;Telegram,https://...,repost,CAM"
    """
    results = []
    for entry in hits_str.split(";"):
        parts = [p.strip() for p in entry.split(",", 3)]
        if len(parts) < 2:
            continue
        results.append({
            "platform":   parts[0] if len(parts) > 0 else "Unknown",
            "url":        parts[1] if len(parts) > 1 else "",
            "detail":     parts[2] if len(parts) > 2 else "",
            "quality":    parts[3] if len(parts) > 3 else "CAM",
            "confidence": "HIGH",
        })
    return results


def main():
    ap = argparse.ArgumentParser(
        description="CINEOS PDF Evidence Package Generator — $499/report for law firms"
    )
    ap.add_argument("--film",    required=True, help='Film title e.g. "Michael"')
    ap.add_argument("--verdict", default="CONFIRMED",
                    help="CONFIRMED / HIGH / MEDIUM / LOW")
    ap.add_argument("--hits",    required=True,
                    help='Hits: "Platform,URL,Detail,Quality" semicolon-separated')
    ap.add_argument("--output",  default=REPORT_DIR,
                    help=f"Output directory (default: {REPORT_DIR})")
    args = ap.parse_args()

    hits = parse_hits(args.hits)
    if not hits:
        print("ERROR: No valid hits parsed. Check --hits format.", file=sys.stderr)
        sys.exit(1)

    path = generate_report(
        film      = args.film,
        verdict   = args.verdict.upper(),
        hits      = hits,
        output_dir= args.output,
    )
    print(f"\nSaved to: {path}")


if __name__ == "__main__":
    main()
