"""Routeur de statut et santé de l'API (KAN-33)."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.mqtt_client import mqtt_manager, device_status_cache
from app.config import settings

router = APIRouter(tags=["Status"])


@router.get(
    "/health",
    summary="Probe de santé applicative",
    description="Endpoint ultra-léger pour Docker et monitoring."
)
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get(
    "/api/v1/status",
    summary="Statut global du système Sentinel-X",
    description="Retourne l'état de connectivité du broker MQTT, de la base de données et des boîtiers surveillés."
)
async def system_status(db: AsyncSession = Depends(get_db)):
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "api": {
            "status": "online",
            "environment": settings.API_ENV,
            "version": "1.0.0"
        },
        "database": {
            "status": "connected" if db_ok else "disconnected",
            "type": "MariaDB Galera" if "mysql" in settings.DATABASE_URL else "SQLite"
        },
        "mqtt_broker": {
            "host": f"{settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}",
            "connected": mqtt_manager.is_connected,
            "tls": settings.MQTT_USE_TLS
        },
        "devices": device_status_cache,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
