import pytest
from app.schemas import AgendaItem, EventService, EventSummary


def test_event_service_with_person():
    svc = EventService(service_id=1, name="Predigt", person_name="Max Mustermann", is_accepted=True)
    assert svc.name == "Predigt"
    assert svc.person_name == "Max Mustermann"
    assert svc.is_accepted is True


def test_event_service_without_person():
    svc = EventService(service_id=2, name="Worship", person_name=None, is_accepted=False)
    assert svc.person_name is None


def test_event_summary():
    svc = EventService(service_id=1, name="Predigt", person_name="Max", is_accepted=True)
    ev = EventSummary(
        id=42,
        name="Gottesdienst",
        start_date="2026-03-22T09:00:00Z",
        end_date="2026-03-22T11:00:00Z",
        calendar_name="Gottesdienste",
        services=[svc],
    )
    assert ev.id == 42
    assert len(ev.services) == 1


def test_agenda_item_default():
    item = AgendaItem(
        position=1,
        type="default",
        title="Begruessung",
        start="2026-03-22T09:00:00Z",
        duration_seconds=300,
        note="Herzlich willkommen",
        responsible_names=["Max"],
        is_before_event=False,
        song_title=None,
        song_key=None,
        song_arrangement=None,
    )
    assert item.duration_display == "05:00"


def test_agenda_item_song():
    item = AgendaItem(
        position=2,
        type="song",
        title="Amazing Grace",
        start="2026-03-22T09:05:00Z",
        duration_seconds=240,
        note=None,
        responsible_names=["Anna"],
        is_before_event=False,
        song_title="Amazing Grace",
        song_key="G",
        song_arrangement="Band",
    )
    assert item.type == "song"
    assert item.song_key == "G"


def test_agenda_item_header():
    item = AgendaItem(
        position=0,
        type="header",
        title="Vorbereitung",
        start=None,
        duration_seconds=0,
        note=None,
        responsible_names=[],
        is_before_event=True,
        song_title=None,
        song_key=None,
        song_arrangement=None,
    )
    assert item.type == "header"
    assert item.is_before_event is True
    assert item.duration_display == "00:00"
