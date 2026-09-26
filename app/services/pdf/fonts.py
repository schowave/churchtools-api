import structlog
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.config import APP_DIR

logger = structlog.get_logger()

# Preferred font (Bahnschrift for church display, Helvetica as fallback)
PREFERRED_FONT = "Bahnschrift"
FALLBACK_FONT = "Helvetica"
FALLBACK_FONT_BOLD = "Helvetica-Bold"

_FONTS_DIR = APP_DIR / "resources" / "fonts"

_cached_fonts = None


def register_fonts():
    """Register preferred fonts with fallback to Helvetica.

    Returns (font_name, bold_font_name). Results are cached after first call.
    """
    global _cached_fonts
    if _cached_fonts is not None:
        return _cached_fonts

    font_name = PREFERRED_FONT
    try:
        if font_name not in pdfmetrics.getRegisteredFontNames():
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(_FONTS_DIR / f"{font_name}.ttf")))
            except Exception as e:
                logger.error("font_registration_failed", font=font_name, error=str(e))
                font_name = FALLBACK_FONT

        bold_font_name = font_name + "-Bold"
        if bold_font_name not in pdfmetrics.getRegisteredFontNames():
            try:
                if font_name == PREFERRED_FONT:
                    # Bahnschrift uses the same file for bold
                    pdfmetrics.registerFont(TTFont(bold_font_name, str(_FONTS_DIR / f"{font_name}.ttf")))
                else:
                    pdfmetrics.registerFont(TTFont(bold_font_name, str(_FONTS_DIR / f"{font_name}-Bold.ttf")))
            except Exception as e:
                logger.error("font_registration_failed", font=bold_font_name, error=str(e))
                bold_font_name = FALLBACK_FONT_BOLD
                if FALLBACK_FONT_BOLD not in pdfmetrics.getRegisteredFontNames():
                    try:
                        pdfmetrics.registerFont(TTFont(FALLBACK_FONT_BOLD, str(_FONTS_DIR / "helvetica-bold.ttf")))
                    except Exception as e2:
                        logger.error("font_registration_failed", font=FALLBACK_FONT_BOLD, error=str(e2))
                        bold_font_name = FALLBACK_FONT
    except Exception as e:
        logger.error("font_registration_failed", error=str(e))
        font_name = FALLBACK_FONT
        bold_font_name = FALLBACK_FONT_BOLD

    _cached_fonts = (font_name, bold_font_name)
    return _cached_fonts
