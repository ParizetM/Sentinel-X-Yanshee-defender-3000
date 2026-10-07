"""Routeur de flux vidéo pour le Dashboard (KAN-44 / US-7.3)."""

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse, Response
from app.config import settings

router = APIRouter(prefix="/api/v1/video", tags=["Video Stream"])

# URL par défaut du flux matériel Yanshee (GPU VideoCore IV)
ROBOT_STREAM_URL = "http://10.0.3.234:8000/stream.mjpg?key=sentinel-x-secret-key-2026"


@router.get(
    "/stream",
    summary="Relais proxy du flux vidéo caméra (MJPEG)",
    description="Permet au Dashboard d'afficher le flux vidéo temps réel sans problème de CORS ou d'IP directe."
)
async def video_stream():
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
