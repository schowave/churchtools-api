from app.schemas import AgendaItem, EventService, EventSummary
from app.services.pdf_generator import create_agenda_pdf, create_services_pdf


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
