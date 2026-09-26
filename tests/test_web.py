import pytest

from app.web import initials


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Erika Muster", "EM"),
        ("erika muster", "EM"),
        ("Madonna", "M"),
        ("Tobias von Hagen", "TH"),
        ("", ""),
        (None, ""),
    ],
)
def test_initials(name, expected):
    assert initials(name) == expected
