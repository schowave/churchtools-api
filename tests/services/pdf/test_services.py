from app.config import APP_DIR
from app.schemas import EventService, EventSummary
from app.services.pdf.services import create_services_pdf


def _make_events():
    return [
        EventSummary(
            id=1,
            name="Gottesdienst",
            start_date="2026-03-22T09:00:00Z",
            end_date="2026-03-22T11:00:00Z",
            calendar_name="GD",
            services=[
                EventService(service_id=1, name="Predigt", person_name="Max Mustermann", is_accepted=True),
                EventService(service_id=2, name="Worship", person_name=None, is_accepted=False),
            ],
        ),
        EventSummary(
            id=2,
            name="Abendgottesdienst",
            start_date="2026-03-22T18:00:00Z",
            end_date="2026-03-22T19:30:00Z",
            calendar_name="GD",
            services=[
                EventService(service_id=1, name="Predigt", person_name="Anna Schmidt", is_accepted=True),
            ],
        ),
    ]


def test_create_services_pdf_returns_bytes():
    events = _make_events()
    result = create_services_pdf("22.03. \u2013 29.03.2026", events)
    assert isinstance(result, bytes)
    assert result[:5] == b"%PDF-"


def test_create_services_pdf_empty_events():
    result = create_services_pdf("22.03. \u2013 29.03.2026", [])
    assert isinstance(result, bytes)
    assert result[:5] == b"%PDF-"


def test_create_services_pdf_treats_churchtools_text_as_plain_text():
    # ChurchTools texts must not be parsed as ReportLab markup: <img> would embed local files or fetch URLs
    image = APP_DIR.parent / "docs" / "images" / "start.png"
    injected = f'<img src="{image}" width="100" height="60"/>'
    event = EventSummary(
        id=1,
        name=injected,
        start_date="2026-03-22T09:00:00Z",
        end_date="2026-03-22T11:00:00Z",
        services=[EventService(service_id=1, name="Ton & Licht <Technik>", person_name=injected)],
    )

    result = create_services_pdf("22.03.2026", [event])

    assert result[:5] == b"%PDF-"
    assert b"/Subtype /Image" not in result
