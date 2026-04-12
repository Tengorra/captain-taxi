"""Generate PDF reports using ReportLab."""
import io
from datetime import datetime, date
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT


BRAND_DARK = colors.HexColor("#1a1a2e")
BRAND_ACCENT = colors.HexColor("#f59e0b")
BRAND_GREEN = colors.HexColor("#10b981")
BRAND_RED = colors.HexColor("#ef4444")
BRAND_GRAY = colors.HexColor("#6b7280")


def _header_style():
    s = getSampleStyleSheet()
    return ParagraphStyle("CaptainHeader", parent=s["Heading1"],
                          textColor=BRAND_DARK, fontSize=20, spaceAfter=4)


def _sub_style():
    s = getSampleStyleSheet()
    return ParagraphStyle("CaptainSub", parent=s["Normal"],
                          textColor=BRAND_GRAY, fontSize=10, spaceAfter=12)


def _section_style():
    s = getSampleStyleSheet()
    return ParagraphStyle("CaptainSection", parent=s["Heading2"],
                          textColor=BRAND_DARK, fontSize=13, spaceBefore=16, spaceAfter=6)


def _normal():
    return getSampleStyleSheet()["Normal"]


def generate_weekly_report(data: dict) -> bytes:
    """
    Generate weekly PDF report.
    data keys: week_label, saskatoon, regina, drivers, compliance_issues
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    story = []
    styles = getSampleStyleSheet()

    # Title
    story.append(Paragraph("Captain Taxi", _header_style()))
    story.append(Paragraph(f"Weekly Operations Report — {data.get('week_label', '')}", _sub_style()))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", _sub_style()))
    story.append(HRFlowable(width="100%", thickness=2, color=BRAND_ACCENT))
    story.append(Spacer(1, 12))

    # Revenue Summary
    story.append(Paragraph("Revenue Summary", _section_style()))
    rev_data = [
        ["City", "Total Trips", "Gross Revenue", "Driver Pay", "Company Revenue"],
        ["Saskatoon",
         str(data.get("saskatoon", {}).get("trips", 0)),
         f"${data.get('saskatoon', {}).get('gross', 0):,.2f}",
         f"${data.get('saskatoon', {}).get('driver_pay', 0):,.2f}",
         f"${data.get('saskatoon', {}).get('company', 0):,.2f}"],
        ["Regina",
         str(data.get("regina", {}).get("trips", 0)),
         f"${data.get('regina', {}).get('gross', 0):,.2f}",
         f"${data.get('regina', {}).get('driver_pay', 0):,.2f}",
         f"${data.get('regina', {}).get('company', 0):,.2f}"],
        ["TOTAL",
         str(data.get("total_trips", 0)),
         f"${data.get('total_gross', 0):,.2f}",
         f"${data.get('total_driver_pay', 0):,.2f}",
         f"${data.get('total_company', 0):,.2f}"],
    ]
    t = Table(rev_data, colWidths=[1.2*inch, 1*inch, 1.4*inch, 1.2*inch, 1.4*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, -1), (-1, -1), BRAND_ACCENT),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f9fafb")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Driver Performance
    story.append(Paragraph("Driver Performance", _section_style()))
    drivers = data.get("drivers", [])
    if drivers:
        drv_data = [["Driver", "City", "Trips", "Earnings", "Score", "Status"]]
        for d in drivers[:20]:
            drv_data.append([
                d.get("name", ""),
                d.get("city", "").title(),
                str(d.get("trips", 0)),
                f"${d.get('earnings', 0):,.2f}",
                f"{d.get('score', 100):.0f}",
                d.get("status", "").title(),
            ])
        dt = Table(drv_data, colWidths=[1.6*inch, 1*inch, 0.7*inch, 1*inch, 0.7*inch, 1.2*inch])
        dt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(dt)
    else:
        story.append(Paragraph("No driver data available.", _normal()))
    story.append(Spacer(1, 12))

    # Compliance Issues
    issues = data.get("compliance_issues", [])
    story.append(Paragraph(f"Compliance Alerts ({len(issues)})", _section_style()))
    if issues:
        ci_data = [["Driver", "Document", "Status", "Expiry"]]
        for i in issues:
            ci_data.append([
                i.get("driver_name", ""),
                i.get("doc_type", "").replace("_", " ").title(),
                i.get("status", "").upper(),
                i.get("expiry", "N/A"),
            ])
        ct = Table(ci_data, colWidths=[1.8*inch, 1.5*inch, 1*inch, 1.4*inch])
        ct.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff7ed")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(ct)
    else:
        story.append(Paragraph("No compliance issues this week.", _normal()))

    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_GRAY))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Captain Taxi Admin System — Auto-generated report. For questions contact your admin agent.",
        ParagraphStyle("footer", parent=getSampleStyleSheet()["Normal"],
                       textColor=BRAND_GRAY, fontSize=8, alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
