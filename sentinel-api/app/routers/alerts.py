"""Routeur pour la gestion des alertes (Contrat d'interface §4.4 & KAN-32 : POST /api/v1/alerts)."""

import json
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertCreate, AlertResponse, AlertAcknowledgeRequest
from app.security.auth import verify_api_key
from app.websocket_manager import ws_manager

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


@router.post(
    "",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Point d'entrée obligatoire de réception des alertes (Sujet Sentinel-X)",
    description="Réceptionne les changements d'état des capteurs (ESP8266) et les alertes d'intrusion (IA)."
)
async def create_alert(
    payload: AlertCreate,
    db: AsyncSession = Depends(get_db)
):
    """Enregistre une alerte ou changement d'état et diffuse l'événement en direct."""
    # Gestion de l'horodatage
    recorded_at = datetime.now(timezone.utc)
    if payload.ts:
        if isinstance(payload.ts, datetime):
            recorded_at = payload.ts
        elif isinstance(payload.ts, str):
            try:
                recorded_at = datetime.fromisoformat(payload.ts.replace("Z", "+00:00"))
            except Exception:
                pass

    # Collecte du payload complet (incluant les champs supplémentaires)
    full_payload = {}
    if payload.payload:
        full_payload.update(payload.payload)
    # Récupérer les attributs extras si existants
    extra_fields = getattr(payload, "__pydantic_extra__", None)
    if extra_fields:
        full_payload.update(extra_fields)

    payload_str = json.dumps(full_payload) if full_payload else None

    alert = Alert(
        device_id=payload.device_id or "esp-01",
        created_at=recorded_at,
        source=payload.source or "sensor",
        alert_type=payload.alert_type or "general",
        level=payload.level or "warning",
        value=payload.value,
        message=payload.message or "Alerte générée",
        payload_json=payload_str,
        acknowledged=False
    )

    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    alert_dict = alert.to_dict()

    # Diffusion immédiate aux dashboards connectés via WebSocket
    await ws_manager.broadcast({
        "type": "alert",
        "data": alert_dict
    })

    return alert_dict


@router.get(
    "",
    response_model=List[AlertResponse],
    summary="Consulter l'historique des alertes",
    description="Permet au dashboard de lister les alertes récentes avec filtres optionnels."
)
async def get_alerts(
    level: Optional[str] = Query(None, description="Filtrer par niveau (info, warning, alert, critical)"),
    severity: Optional[str] = Query(None, description="Alias pour level"),
    source: Optional[str] = Query(None, description="Filtrer par source (sensor, ia_vision, etc.)"),
    acknowledged: Optional[bool] = Query(None, description="Filtrer par statut d'acquittement"),
    limit: int = Query(50, ge=1, le=500, description="Nombre maximum de résultats"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Alert).order_by(desc(Alert.created_at)).limit(limit)

    target_level = level or severity
    if target_level:
        query = query.where(Alert.level == target_level)
    if source:
        query = query.where(Alert.source == source)
    if acknowledged is not None:
        query = query.where(Alert.acknowledged == acknowledged)

    result = await db.execute(query)
    alerts = result.scalars().all()
    return [a.to_dict() for a in alerts]


@router.put(
    "/{alert_id}/acknowledge",
    response_model=AlertResponse,
    summary="Acquitter une alerte",
    description="Marque une alerte comme prise en compte par le superviseur."
)
async def acknowledge_alert(
    alert_id: int,
    payload: AlertAcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key)
):
    query = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alerte #{alert_id} introuvable"
        )

    alert.acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = payload.acknowledged_by

    await db.commit()
    await db.refresh(alert)
    return alert.to_dict()
