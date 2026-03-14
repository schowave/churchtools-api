import pytest
from pydantic import ValidationError

from app.schemas import AppointmentData, ColorSettings, GenerateRequest


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
