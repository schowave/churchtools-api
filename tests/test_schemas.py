import pytest
from pydantic import ValidationError

from app.schemas import (
    AgendaItem,
    AppointmentData,
    ColorSettings,
    ErrorResponse,
    EventService,
    EventSummary,
    GenerateRequest,
)


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
    assert item.duration_display == "5 Min."


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
    assert item.duration_display == ""


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, ""), (30, "1 Min."), (180, "3 Min."), (1200, "20 Min."), (3600, "1 Std."), (3900, "1 Std. 5 Min.")],
)
def test_agenda_duration_reads_as_a_length_not_a_clock_time(seconds, expected):
    # "15:00" for a quarter of an hour looked like a start time
    assert AgendaItem(position=1, title="x", duration_seconds=seconds).duration_display == expected


def test_error_response_model():
    err = ErrorResponse(error="not_found", detail="Resource not found")
    assert err.error == "not_found"
    assert err.detail == "Resource not found"


def test_error_response_without_detail():
    err = ErrorResponse(error="server_error")
    assert err.detail is None


class TestColorSettings:
    def test_valid_colors(self):
        settings = ColorSettings(
            name="test",
            background_color="#d3d3d3",
            date_color="#c1540c",
            description_color="#4e4e4e",
        )
        assert settings.background_color == "#d3d3d3"

    def test_defaults(self):
        settings = ColorSettings(name="test")
        assert settings.background_color == "#d3d3d3"
        assert settings.background_alpha == 128
        assert settings.date_color == "#c1540c"
        assert settings.description_color == "#4e4e4e"

    @pytest.mark.parametrize("color", ["000000", "#fff", "#GGGGGG", "red", "#12345", "#1234567"])
    def test_invalid_hex_color(self, color):
        with pytest.raises(ValidationError):
            ColorSettings(name="test", background_color=color)

    @pytest.mark.parametrize("color", ["#000000", "#FFFFFF", "#c1540c", "#abcdef", "#ABCDEF"])
    def test_valid_hex_color_variants(self, color):
        settings = ColorSettings(name="test", background_color=color)
        assert settings.background_color == color

    def test_alpha_valid_bounds(self):
        assert ColorSettings(name="test", background_alpha=0).background_alpha == 0
        assert ColorSettings(name="test", background_alpha=255).background_alpha == 255
        assert ColorSettings(name="test", background_alpha=128).background_alpha == 128

    def test_alpha_out_of_bounds(self):
        with pytest.raises(ValidationError):
            ColorSettings(name="test", background_alpha=-1)
        with pytest.raises(ValidationError):
            ColorSettings(name="test", background_alpha=256)


class TestAppointmentData:
    def test_computed_fields(self):
        apt = AppointmentData(
            id="1",
            title="Test",
            start_date="2026-03-15T09:00:00Z",
            end_date="2026-03-15T11:00:00Z",
        )
        assert apt.start_date_view == "15.03.2026"
        assert apt.start_time_view == "10:00"  # UTC+1 Berlin
        assert apt.end_time_view == "12:00"

    def test_optional_fields_default_empty(self):
        apt = AppointmentData(
            id="1",
            title="Test",
            start_date="2026-03-15T09:00:00Z",
            end_date="2026-03-15T11:00:00Z",
        )
        assert apt.meeting_at == ""
        assert apt.information == ""
        assert apt.additional_info == ""


def test_generate_request_valid():
    req = GenerateRequest(
        type="pdf",
        start_date="2026-03-14",
        end_date="2026-03-21",
        calendar_ids=["1", "2"],
        appointment_ids=["1_101", "2_102"],
        color_settings={
            "background_color": "#ffffff",
            "background_alpha": 128,
            "date_color": "#c1540c",
            "description_color": "#4e4e4e",
        },
        additional_infos={"1_101": "Some info", "2_102": ""},
    )
    assert req.type == "pdf"
    assert req.appointment_ids == ["1_101", "2_102"]
    assert req.additional_infos["1_101"] == "Some info"
    assert req.color_settings.name == "default"


def test_generate_request_invalid_type():
    import pytest

    with pytest.raises(ValueError):
        GenerateRequest(
            type="png",
            start_date="2026-03-14",
            end_date="2026-03-21",
            calendar_ids=["1"],
            appointment_ids=["1_101"],
            color_settings={
                "background_color": "#ffffff",
                "background_alpha": 128,
                "date_color": "#c1540c",
                "description_color": "#4e4e4e",
            },
            additional_infos={},
        )


def test_generate_request_empty_appointments():
    import pytest

    with pytest.raises(ValueError):
        GenerateRequest(
            type="pdf",
            start_date="2026-03-14",
            end_date="2026-03-21",
            calendar_ids=["1"],
            appointment_ids=[],
            color_settings={
                "background_color": "#ffffff",
                "background_alpha": 128,
                "date_color": "#c1540c",
                "description_color": "#4e4e4e",
            },
            additional_infos={},
        )


def test_generate_request_defaults_additional_infos():
    req = GenerateRequest(
        type="jpeg",
        start_date="2026-03-14",
        end_date="2026-03-21",
        calendar_ids=["1"],
        appointment_ids=["1_101"],
        color_settings={
            "background_color": "#ffffff",
            "background_alpha": 128,
            "date_color": "#c1540c",
            "description_color": "#4e4e4e",
        },
    )
    assert req.additional_infos == {}
