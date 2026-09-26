from app.config import APP_DIR
from app.schemas import AgendaItem
from app.services.pdf.agenda import create_agenda_pdf


def _make_agenda_items():
    return [
        AgendaItem(
            position=0,
            type="header",
            title="Vorbereitung",
            start=None,
            duration_seconds=0,
            responsible_names=[],
            is_before_event=True,
        ),
        AgendaItem(
            position=1,
            type="default",
            title="Begruessung",
            start="2026-03-22T09:00:00Z",
            duration_seconds=300,
            note="Herzlich willkommen",
            responsible_names=["Max Mustermann"],
            is_before_event=False,
        ),
        AgendaItem(
            position=2,
            type="song",
            title="Amazing Grace",
            start="2026-03-22T09:05:00Z",
            duration_seconds=240,
            responsible_names=["Anna"],
            is_before_event=False,
            song_title="Amazing Grace",
            song_key="G",
            song_arrangement="Band",
        ),
    ]


def test_create_agenda_pdf_returns_bytes():
    items = _make_agenda_items()
    result = create_agenda_pdf("Gottesdienst", "2026-03-22T09:00:00Z", items)
    assert isinstance(result, bytes)
    assert result[:5] == b"%PDF-"


def test_create_agenda_pdf_empty_items():
    result = create_agenda_pdf("Gottesdienst", "2026-03-22T09:00:00Z", [])
    assert isinstance(result, bytes)
    assert result[:5] == b"%PDF-"


def test_create_agenda_pdf_treats_churchtools_text_as_plain_text():
    # ChurchTools texts must not be parsed as ReportLab markup: <img> would embed local files or fetch URLs
    image = APP_DIR.parent / "docs" / "images" / "start.png"
    injected = f'<img src="{image}" width="100" height="60"/>'
    items = [
        AgendaItem(position=0, type="header", title=injected),
        AgendaItem(position=1, title="Lobpreis & Gebet <3", note=injected, responsible_names=[injected]),
    ]

    result = create_agenda_pdf(injected, "2026-03-22T09:00:00Z", items)

    assert result[:5] == b"%PDF-"
    assert b"/Subtype /Image" not in result
