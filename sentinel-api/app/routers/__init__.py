"""Export des routeurs de l'API."""

from app.routers.alerts import router as alerts_router
from app.routers.telemetry import router as telemetry_router
from app.routers.actuators import router as actuators_router
from app.routers.status import router as status_router

__all__ = ["alerts_router", "telemetry_router", "actuators_router", "status_router"]
