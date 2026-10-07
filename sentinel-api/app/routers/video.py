"""Routeur de flux vidéo et captures pour le Dashboard (Contrat §4.4 & KAN-44 / US-7.3)."""

import httpx
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from app.config import settings

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


@router.get(
    "/api/v1/camera/latest_photo",
    summary="Dernière photo d'intrusion capturée",
    description="Retourne le dernier cliché JPEG reçu par le bus MQTT (detection_robot/photo)."
)
async def get_latest_photo():
    from app.mqtt_client import latest_photo_cache, latest_photo_timestamp
    if not latest_photo_cache:
        raise HTTPException(
            status_code=404,
            detail="Aucune photo de détection disponible pour le moment"
        )

    headers = {}
    if latest_photo_timestamp:
        headers["X-Capture-Timestamp"] = latest_photo_timestamp

    return Response(
        content=latest_photo_cache,
        media_type="image/jpeg",
        headers=headers
    )
