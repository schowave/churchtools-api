from collections.abc import Callable
from io import BytesIO

import httpx2
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image
from sqlalchemy.orm import Session

from app.crud import (
    delete_background_image,
    delete_logo,
    load_background_image,
    load_logo,
    save_background_image,
    save_logo,
)
from app.database import DEFAULT_SETTING_NAME, get_db
from app.services.auth import require_auth
from app.web import get_http_client

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_PIXELS = 40_000_000  # guards against decompression bombs
IMAGE_FORMATS = {"PNG", "JPEG"}


async def _read_image_upload(file: UploadFile) -> bytes:
    """Read an uploaded file and reject anything that is not a sane PNG or JPEG."""
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Datei zu groß (max. 10 MB)")
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")
    try:
        with Image.open(BytesIO(content)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Nur PNG- oder JPEG-Bilder erlaubt") from None
    if image_format not in IMAGE_FORMATS:
        raise HTTPException(status_code=400, detail="Nur PNG- oder JPEG-Bilder erlaubt")
    if width * height > MAX_IMAGE_PIXELS:
        raise HTTPException(status_code=413, detail="Bild zu groß (max. 40 Megapixel)")
    return content


def _image_response(data: bytes, not_found_detail: str) -> Response:
    """Serve stored image bytes with a content type derived from the data, never from the filename."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    else:
        # Legacy uploads (e.g. SVG) from before upload validation are not served.
        raise HTTPException(status_code=404, detail=not_found_detail)
    return Response(content=data, media_type=media_type, headers={"Content-Security-Policy": "default-src 'none'"})


router = APIRouter()


async def _upload_image(request, file, client, save: Callable[[bytes, str], None]) -> JSONResponse:
    await require_auth(request, client)
    content = await _read_image_upload(file)
    save(content, file.filename)
    return JSONResponse({"status": "ok", "filename": file.filename})


async def _serve_image(request, client, load: Callable[[], tuple], missing_detail: str) -> Response:
    await require_auth(request, client)
    data, _ = load()
    if not data:
        raise HTTPException(status_code=404, detail=missing_detail)
    return _image_response(data, missing_detail)


async def _remove_image(request, client, delete: Callable[[], None]) -> JSONResponse:
    await require_auth(request, client)
    delete()
    return JSONResponse({"status": "ok"})


@router.post("/logo/upload")
async def upload_logo(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    client: httpx2.AsyncClient = Depends(get_http_client),
) -> JSONResponse:
    """Upload a logo image and store it in the database."""
    return await _upload_image(
        request, file, client, lambda data, name: save_logo(db, DEFAULT_SETTING_NAME, data, name)
    )


@router.get("/logo")
async def get_logo(
    request: Request, db: Session = Depends(get_db), client: httpx2.AsyncClient = Depends(get_http_client)
) -> Response:
    """Serve the stored logo image for preview."""
    return await _serve_image(request, client, lambda: load_logo(db, DEFAULT_SETTING_NAME), "Kein Logo gespeichert")


@router.delete("/logo")
async def remove_logo(
    request: Request, db: Session = Depends(get_db), client: httpx2.AsyncClient = Depends(get_http_client)
) -> JSONResponse:
    """Delete the stored logo."""
    return await _remove_image(request, client, lambda: delete_logo(db, DEFAULT_SETTING_NAME))


@router.post("/background/upload")
async def upload_background(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    client: httpx2.AsyncClient = Depends(get_http_client),
) -> JSONResponse:
    """Upload a background image and store it in the database."""
    return await _upload_image(
        request, file, client, lambda data, name: save_background_image(db, DEFAULT_SETTING_NAME, data, name)
    )


@router.get("/background")
async def get_background(
    request: Request, db: Session = Depends(get_db), client: httpx2.AsyncClient = Depends(get_http_client)
) -> Response:
    """Serve the stored background image for preview."""
    return await _serve_image(
        request, client, lambda: load_background_image(db, DEFAULT_SETTING_NAME), "Kein Hintergrundbild gespeichert"
    )


@router.delete("/background")
async def remove_background(
    request: Request, db: Session = Depends(get_db), client: httpx2.AsyncClient = Depends(get_http_client)
) -> JSONResponse:
    """Delete the stored background image."""
    return await _remove_image(request, client, lambda: delete_background_image(db, DEFAULT_SETTING_NAME))
