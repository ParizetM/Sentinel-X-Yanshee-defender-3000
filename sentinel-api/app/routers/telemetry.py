"""Routeur pour la télémétrie des capteurs (KAN-31, KAN-33)."""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryResponse, TelemetryPayload

router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry"])


@router.get(
    "/latest",
    response_model=TelemetryResponse,
    summary="Dernière mesure de télémétrie reçue",
    description="Retourne la plus récente lecture de capteurs pour rafraîchir le dashboard."
)
async def get_latest_telemetry(
    device_id: Optional[str] = Query(None, description="Filtrer par identifiant boîtier"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Telemetry).order_by(desc(Telemetry.recorded_at)).limit(1)
    if device_id:
        query = query.where(Telemetry.device_id == device_id)

    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune mesure de télémétrie disponible pour le moment"
        )

    return record.to_dict()


@router.get(
    "/history",
    response_model=List[TelemetryResponse],
    summary="Historique des mesures pour graphiques",
    description="Retourne les séries temporelles pour tracer les courbes de température, humidité et gaz."
)
async def get_telemetry_history(
    device_id: Optional[str] = Query(None, description="Identifiant du boîtier"),
    limit: int = Query(100, ge=1, le=1000, description="Nombre max de points de mesure"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Telemetry).order_by(desc(Telemetry.recorded_at)).limit(limit)
    if device_id:
        query = query.where(Telemetry.device_id == device_id)

    result = await db.execute(query)
    records = result.scalars().all()
    # Renvoyer par ordre chronologique pour tracer les graphiques
    ordered = sorted(records, key=lambda x: x.recorded_at)
    return [r.to_dict() for r in ordered]


@router.post(
    "",
    response_model=TelemetryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingestion HTTP de télémétrie (secours)",
    description="Permet d'ingérer une trame capteur via HTTP si le broker MQTT est hors-ligne."
)
async def ingest_telemetry_http(
    payload: TelemetryPayload,
    db: AsyncSession = Depends(get_db)
):
    gas_data = payload.gas or None
    actuators_data = payload.actuators or None

    telemetry = Telemetry(
        device_id=payload.device,
        recorded_at=datetime.now(timezone.utc),
        uptime_s=payload.uptime_s,
        temperature=payload.temperature,
        humidity=payload.humidity,
        gas_raw=gas_data.raw if gas_data else None,
        gas_baseline=gas_data.baseline if gas_data else None,
        gas_level=gas_data.level if gas_data else "normal",
        presence=payload.presence,
        rssi=payload.rssi,
        buzzer_state=actuators_data.buzzer if actuators_data else "off",
        led_state=actuators_data.led if actuators_data else "off"
    )

    db.add(telemetry)
    await db.commit()
    await db.refresh(telemetry)

    return telemetry.to_dict()
