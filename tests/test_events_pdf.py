import pytest
from app.schemas import AgendaItem
from app.services.pdf_generator import create_agenda_pdf


def _make_agenda_items():
    return [
        AgendaItem(
            position=0, type="header", title="Vorbereitung",
            start=None, duration_seconds=0, responsible_names=[],
            is_before_event=True,
        ),
        AgendaItem(
            position=1, type="default", title="Begruessung",
            start="2026-03-22T09:00:00Z", duration_seconds=300,
            note="Herzlich willkommen", responsible_names=["Max Mustermann"],
            is_before_event=False,
        ),
        AgendaItem(
            position=2, type="song", title="Amazing Grace",
            start="2026-03-22T09:05:00Z", duration_seconds=240,
            responsible_names=["Anna"], is_before_event=False,
            song_title="Amazing Grace", song_key="G", song_arrangement="Band",
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

