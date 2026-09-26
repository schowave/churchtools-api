import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.dates import parse_iso_datetime
from app.schemas import EventSummary
from app.services.pdf.fonts import register_fonts


def create_services_pdf(date_range: str, events: list[EventSummary]) -> bytes:
    """Create a tabular A4 PDF for service assignments across events."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm
    )

    font_name, font_name_bold = register_fonts()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ServicesTitle", parent=styles["Heading1"], fontName=font_name_bold, fontSize=16, spaceAfter=6
    )
    cell_style = ParagraphStyle("ServicesCell", parent=styles["Normal"], fontName=font_name, fontSize=9, leading=12)
    event_header_style = ParagraphStyle(
        "ServicesEventHeader", parent=styles["Normal"], fontName=font_name_bold, fontSize=10, leading=14
    )

    elements = []
    elements.append(Paragraph(f"Dienstplan — {date_range}", title_style))
    elements.append(Spacer(1, 6))

    for event in events:
        start_dt = parse_iso_datetime(event.start_date)
        event_label = f"{start_dt.strftime('%d.%m.%Y %H:%M')} — {event.name}"
        elements.append(Paragraph(event_label, event_header_style))
        elements.append(Spacer(1, 4))

        if not event.services:
            elements.append(Paragraph("Keine Dienste eingetragen", cell_style))
            elements.append(Spacer(1, 10))
            continue

        table_data = [["Dienst", "Person", "Status"]]
        for svc in event.services:
            person = svc.person_name or "-- (offen)"
            status_str = "Ja" if svc.is_accepted else "?"
            table_data.append(
                [
                    Paragraph(svc.name, cell_style),
                    Paragraph(person, cell_style),
                    Paragraph(status_str, cell_style),
                ]
            )

        available = A4[0] - 30 * mm
        col_widths = [available * 0.35, available * 0.45, available * 0.20]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5E8B5A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), font_name_bold),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8DDD0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFBF8")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 14))

    doc.build(elements)
    return buffer.getvalue()
