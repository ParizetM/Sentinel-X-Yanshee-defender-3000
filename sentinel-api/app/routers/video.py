"""Routeur de flux vidéo et captures pour le Dashboard (Contrat §4.4 & KAN-44 / US-7.3)."""

import httpx
from fastapi import APIRouter, HTTPException, Response, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db

router = APIRouter(tags=["Camera & Video (Contrat §4.4)"])

# URL par défaut du flux matériel Yanshee (GPU VideoCore IV)
ROBOT_STREAM_URL = "http://10.0.3.234:8000/stream.mjpg?key=sentinel-x-secret-key-2026"


@router.get(
    "/api/v1/camera/stream",
    summary="Flux vidéo caméra annoté / brut (Contrat §4.4)",
    description="Relaye le flux vidéo MJPEG en direct pour le Dashboard."
)
@router.get(
    "/api/v1/video/stream",
    include_in_schema=False
)
async def camera_stream():
    """Relaye le flux multipart/x-mixed-replace depuis le robot ou la VM IA."""
    async def proxy_mjpeg():
        try:
            timeout = httpx.Timeout(5.0, connect=1.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("GET", ROBOT_STREAM_URL) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except Exception:
            # Fallback JPEG frame si le robot est éteint / hors-ligne
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\r\n"

    return StreamingResponse(
        proxy_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


PHOTO_CACHE_PATH = "/var/tmp/sentinel_latest_photo.jpg"
PHOTO_TS_PATH = "/var/tmp/sentinel_latest_photo.txt"


@router.get(
    "/api/v1/camera/latest_photo",
    summary="Dernière photo d'intrusion capturée",
    description="Retourne le dernier cliché JPEG reçu par le bus MQTT (detection_robot/photo)."
)
async def get_latest_photo():
    import os
    import app.mqtt_client as mqtt_mod

    content = mqtt_mod.latest_photo_cache
    ts = mqtt_mod.latest_photo_timestamp

    if not content and os.path.exists(PHOTO_CACHE_PATH):
        try:
            with open(PHOTO_CACHE_PATH, "rb") as f:
                content = f.read()
                mqtt_mod.latest_photo_cache = content
            if os.path.exists(PHOTO_TS_PATH):
                with open(PHOTO_TS_PATH, "r") as f:
                    ts = f.read().strip()
                    mqtt_mod.latest_photo_timestamp = ts
        except Exception:
            pass

    if not content:
        raise HTTPException(
            status_code=404,
            detail="Aucune photo de détection disponible pour le moment"
        )

    headers = {}
    if ts:
        headers["X-Capture-Timestamp"] = ts

    return Response(
        content=content,
        media_type="image/jpeg",
        headers=headers
    )


@router.get(
    "/api/v1/camera/photos",
    summary="Historique des photos d'intrusion enregistrées en BDD",
    description="Retourne la liste paginée des clichés capturés avec métadonnées."
)
async def list_captured_photos(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    from app.models.photo import CapturedPhoto
    from sqlalchemy import select, desc

    query = select(CapturedPhoto).order_by(desc(CapturedPhoto.captured_at)).limit(limit)
    result = await db.execute(query)
    photos = result.scalars().all()
    return [p.to_dict() for p in photos]


@router.get(
    "/api/v1/camera/photos/{photo_id}",
    summary="Télécharger / afficher une photo d'intrusion par son ID",
    description="Retourne le binaire JPEG stocké dans le cluster MariaDB Galera."
)
async def get_photo_by_id(
    photo_id: int,
    db: AsyncSession = Depends(get_db)
):
    from app.models.photo import CapturedPhoto
    from sqlalchemy import select

    query = select(CapturedPhoto).where(CapturedPhoto.id == photo_id)
    result = await db.execute(query)
    photo = result.scalar_one_or_none()

    if not photo or not photo.image_base64:
        raise HTTPException(
            status_code=404,
            detail=f"Photo #{photo_id} introuvable en base de données"
        )

    headers = {}
    if photo.captured_at:
        headers["X-Capture-Timestamp"] = photo.captured_at.isoformat()

    import base64
    raw_bytes = base64.b64decode(photo.image_base64)

    return Response(
        content=raw_bytes,
        media_type=photo.content_type or "image/jpeg",
        headers=headers
    )
