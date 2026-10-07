"""Routeur pour la gestion des alertes (KAN-32 - POST /api/v1/alerts imposé par le sujet)."""

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
    summary="Point d'entrée obligatoire de réception des alertes",
    description="Réceptionne les alertes des capteurs ESP8266, de l'IA (YOLO intrusion, anomalies cinétiques) ou manuelles."
)
async def create_alert(
    payload: AlertCreate,
    db: AsyncSession = Depends(get_db)
):
    """Enregistre une alerte et retourne l'objet créé avec code HTTP 201."""
    metadata_str = json.dumps(payload.metadata) if payload.metadata else None

    alert = Alert(
        device_id=payload.device_id,
        created_at=datetime.now(timezone.utc),
        source=payload.source,
        alert_type=payload.alert_type,
        severity=payload.severity,
        value=payload.value,
        message=payload.message,
        metadata_json=metadata_str,
        acknowledged=False
    )

    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    alert_dict = alert.to_dict()
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
    severity: Optional[str] = Query(None, description="Filtrer par sévérité (low, medium, high, critical)"),
    acknowledged: Optional[bool] = Query(None, description="Filtrer par statut d'acquittement"),
    limit: int = Query(50, ge=1, le=500, description="Nombre maximum de résultats"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Alert).order_by(desc(Alert.created_at)).limit(limit)

    if severity:
        query = query.where(Alert.severity == severity)
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
            detail=f"Alerte avec l'id {alert_id} non trouvée"
        )

    alert.acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = payload.acknowledged_by

    await db.commit()
    await db.refresh(alert)
    return alert.to_dict()
