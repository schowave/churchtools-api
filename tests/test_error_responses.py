from app.schemas import ErrorResponse


def test_error_response_model():
    err = ErrorResponse(error="not_found", detail="Resource not found")
    assert err.error == "not_found"
    assert err.detail == "Resource not found"


def test_error_response_without_detail():
    err = ErrorResponse(error="server_error")
    assert err.detail is None
