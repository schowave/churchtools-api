import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from app.dates import parse_iso_datetime
from app.schemas import AgendaItem
from app.services.pdf.fonts import register_fonts
from app.services.pdf.markup import text_paragraph


def create_agenda_pdf(event_name: str, event_start: str, agenda_items: list[AgendaItem]) -> bytes:
    """Create a tabular A4 PDF for a worship service agenda."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm
    )

    font_name, font_name_bold = register_fonts()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "AgendaTitle", parent=styles["Heading1"], fontName=font_name_bold, fontSize=16, spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        "AgendaSubtitle", parent=styles["Normal"], fontName=font_name, fontSize=10, textColor=colors.grey, spaceAfter=12
    )
    cell_style = ParagraphStyle("AgendaCell", parent=styles["Normal"], fontName=font_name, fontSize=9, leading=12)
    section_style = ParagraphStyle(
        "AgendaSection",
        parent=styles["Normal"],
        fontName=font_name_bold,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#5E8B5A"),
    )

    start_dt = parse_iso_datetime(event_start)
    date_str = start_dt.strftime("%d.%m.%Y")

    elements = []
    elements.append(text_paragraph(f"Agenda — {event_name}", title_style))
    elements.append(text_paragraph(date_str, subtitle_style))

    table_data = [["Zeit", "Titel", "Dauer", "Verantwortlich", "Notiz"]]
    row_styles = []

    for item in agenda_items:
        if item.type == "header":
            table_data.append([text_paragraph(item.title, section_style), "", "", "", ""])
            row_idx = len(table_data) - 1
            row_styles.append(("SPAN", (0, row_idx), (4, row_idx)))
            row_styles.append(("BACKGROUND", (0, row_idx), (4, row_idx), colors.HexColor("#F0F3ED")))
            continue

        time_str = ""
        if item.start:
            dt = parse_iso_datetime(item.start)
            time_str = dt.strftime("%H:%M")

        title = item.title
        if item.type == "song" and item.song_key:
            title += f" ({item.song_key})"
            if item.song_arrangement:
                title += f"\n{item.song_arrangement}"

        table_data.append(
            [
                text_paragraph(time_str, cell_style),
                text_paragraph(title, cell_style),
                text_paragraph(item.duration_display, cell_style),
                text_paragraph(", ".join(item.responsible_names) if item.responsible_names else "", cell_style),
                text_paragraph(item.note or "", cell_style),
            ]
        )

    if len(table_data) > 1:
        col_widths = [45, 150, 40, 100, None]
        available = A4[0] - 30 * mm
        fixed = sum(w for w in col_widths if w is not None)
        col_widths[-1] = available - fixed

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        base_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5E8B5A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), font_name_bold),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8DDD0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFBF8")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        base_style.extend(row_styles)
        table.setStyle(TableStyle(base_style))
        elements.append(table)

    doc.build(elements)
    return buffer.getvalue()
