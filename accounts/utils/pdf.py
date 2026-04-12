"""
PDF Invoice Generator using ReportLab.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

BRAND_COLOR = colors.HexColor("#1a1a2e")  # dark navy
ACCENT_COLOR = colors.HexColor("#e94560")  # Captain Taxi red


def generate_invoice_pdf(invoice, account) -> bytes:
    """Generate a professional invoice PDF. Returns raw bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    bold = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold")
    right = ParagraphStyle("right", parent=styles["Normal"], alignment=TA_RIGHT)
    center = ParagraphStyle("center", parent=styles["Normal"], alignment=TA_CENTER)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8)

    story = []

    # ── Header ──
    header_data = [
        [
            Paragraph("<b><font size=22 color='#1a1a2e'>Captain Taxi</font></b>", styles["Normal"]),
            Paragraph(f"<b>INVOICE</b><br/><font size=9>#{invoice.invoice_number}</font>", right),
        ]
    ]
    header_table = Table(header_data, colWidths=[4 * inch, 3 * inch])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT_COLOR, spaceAfter=8))

    # ── Company info + Bill To ──
    from_lines = "Captain Taxi Ltd.<br/>Saskatoon & Regina, SK, Canada<br/>accounts@captaintaxi.ca<br/>306-242-0000"
    to_lines = (
        f"<b>Bill To:</b><br/>{account.name}<br/>"
        f"{account.contact_name or ''}<br/>"
        f"{account.billing_email}<br/>"
        f"{account.address or account.city or ''}"
    )
    date_lines = (
        f"<b>Invoice Date:</b> {date.today().strftime('%B %d, %Y')}<br/>"
        f"<b>Period:</b> {invoice.period_start.strftime('%b %d')} – {invoice.period_end.strftime('%b %d, %Y')}<br/>"
        f"<b>Due Date:</b> {invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else 'Net 30'}"
    )
    info_data = [
        [
            Paragraph(from_lines, small),
            Paragraph(to_lines, small),
            Paragraph(date_lines, small),
        ]
    ]
    info_table = Table(info_data, colWidths=[2.3 * inch, 2.3 * inch, 2.4 * inch])
    info_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(Spacer(1, 10))
    story.append(info_table)
    story.append(Spacer(1, 16))

    # ── Line items ──
    col_headers = ["Date", "Description", "Amount"]
    rows = [col_headers]
    for li in invoice.line_items:
        rows.append([
            getattr(li, "trip", None) and li.trip and li.trip.completed_at.strftime("%b %d") or "",
            li.description[:70],
            f"${li.line_total:.2f}",
        ])

    line_table = Table(rows, colWidths=[0.8 * inch, 5.2 * inch, 1 * inch])
    line_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 12))

    # ── Totals ──
    totals_data = [
        ["", "Subtotal:", f"${invoice.subtotal:.2f}"],
        ["", "GST (5%):", f"${invoice.gst_amount:.2f}"],
        ["", "TOTAL DUE:", f"${invoice.total:.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[4.5 * inch, 1.5 * inch, 1 * inch])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (2, -1), "RIGHT"),
        ("FONTNAME", (1, 2), (2, 2), "Helvetica-Bold"),
        ("FONTSIZE", (1, 2), (2, 2), 11),
        ("LINEABOVE", (1, 2), (2, 2), 1, ACCENT_COLOR),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 20))

    # ── Payment instructions ──
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<b>Payment Instructions</b><br/>"
        "e-Transfer: accounts@captaintaxi.ca  |  "
        "Cheque payable to: Captain Taxi Ltd.<br/>"
        "Questions? 306-242-0000 (Saskatoon) · 306-775-2222 (Regina)",
        small,
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"GST # {_get_gst_number()}",
        ParagraphStyle("gst", parent=small, textColor=colors.grey),
    ))

    doc.build(story)
    return buffer.getvalue()


def _get_gst_number() -> str:
    from config import settings
    return settings.company_gst_number
