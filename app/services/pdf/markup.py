from xml.sax.saxutils import escape

from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph


def text_paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    """Paragraph for plain text, e.g. from ChurchTools.

    Paragraph parses its input as markup: an unescaped <img src="..."> would embed local files
    or fetch URLs from the server, and a stray "<" breaks the PDF. Line breaks become <br/>.
    """
    return Paragraph(escape(text).replace("\n", "<br/>"), style)
