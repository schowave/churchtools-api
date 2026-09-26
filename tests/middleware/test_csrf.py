from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.testclient import TestClient


def test_csrf_blocks_post_without_token():
    from app.middleware.csrf import CSRFMiddleware

    test_app = FastAPI()
    test_app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])

    @test_app.post("/test")
    async def test_post():
        return JSONResponse({"ok": True})

    client = TestClient(test_app)
    response = client.post("/test")
    assert response.status_code == 403


def test_csrf_allows_post_with_matching_token():
    from app.middleware.csrf import CSRFMiddleware

    test_app = FastAPI()
    test_app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])

    @test_app.get("/get-token")
    async def get_token(request: Request):
        return HTMLResponse("<html></html>")

    @test_app.post("/test")
    async def test_post():
        return JSONResponse({"ok": True})

    client = TestClient(test_app)
    get_resp = client.get("/get-token")
    csrf_token = get_resp.cookies.get("csrf_token")
    assert csrf_token is not None

    response = client.post("/test", headers={"X-CSRF-Token": csrf_token})
    assert response.status_code == 200


def test_csrf_allows_get_without_token():
    from app.middleware.csrf import CSRFMiddleware

    test_app = FastAPI()
    test_app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])

    @test_app.get("/test")
    async def test_get():
        return JSONResponse({"ok": True})

    client = TestClient(test_app)
    response = client.get("/test")
    assert response.status_code == 200


def test_csrf_exempt_path_allows_post_without_token():
    from app.middleware.csrf import CSRFMiddleware

    test_app = FastAPI()
    test_app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])

    @test_app.post("/health")
    async def health_post():
        return JSONResponse({"ok": True})

    client = TestClient(test_app)
    response = client.post("/health")
    assert response.status_code == 200


def test_csrf_blocks_post_with_mismatched_token():
    from app.middleware.csrf import CSRFMiddleware

    test_app = FastAPI()
    test_app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])

    @test_app.get("/get-token")
    async def get_token(request: Request):
        return HTMLResponse("<html></html>")

    @test_app.post("/test")
    async def test_post():
        return JSONResponse({"ok": True})

    client = TestClient(test_app)
    # Get a valid cookie
    client.get("/get-token")
    # Send with wrong header token
    response = client.post("/test", headers={"X-CSRF-Token": "wrong-token"})
    assert response.status_code == 403


def test_csrf_allows_post_with_form_token():
    from app.middleware.csrf import CSRFMiddleware

    test_app = FastAPI()
    test_app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])

    @test_app.get("/get-token")
    async def get_token(request: Request):
        return HTMLResponse("<html></html>")

    @test_app.post("/test")
    async def test_post():
        return JSONResponse({"ok": True})

    client = TestClient(test_app)
    get_resp = client.get("/get-token")
    csrf_token = get_resp.cookies.get("csrf_token")
    assert csrf_token is not None

    response = client.post("/test", data={"_csrf_token": csrf_token})
    assert response.status_code == 200
