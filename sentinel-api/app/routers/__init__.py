"""Export des routeurs de l'API."""

from app.routers.alerts import router as alerts_router
from app.routers.telemetry import router as telemetry_router, measurements_router
from app.routers.actuators import router as actuators_router, control_router
from app.routers.status import router as status_router
from app.routers.websocket import router as websocket_router
from app.routers.video import router as video_router
from app.routers.auth import router as auth_router

__all__ = [
    "alerts_router",
    "telemetry_router",
    "measurements_router",
    "actuators_router",
    "control_router",
    "status_router",
    "websocket_router",
    "video_router",
    "auth_router"
]
