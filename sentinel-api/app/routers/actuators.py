"""Routeur de commande des actionneurs (KAN-35)."""

import json
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.audit import ActuatorAuditLog
from app.schemas.actuator import ActuatorCommandRequest, ActuatorAuditResponse
from app.security.auth import verify_api_key
from app.mqtt_client import mqtt_manager

router = APIRouter(prefix="/api/v1/actuators", tags=["Actuators"])


@router.post(
    "/command",
    summary="Envoyer une commande d'actionneur (Buzzer, LED, Robot)",
    description="Relaye la commande via le topic MQTT approprié et enregistre un journal d'audit."
)
async def send_actuator_command(
    request: ActuatorCommandRequest,
    db: AsyncSession = Depends(get_db),
    api_token: str = Depends(verify_api_key)
):
    target = request.target
    payload_to_mqtt = {}
    topic = ""

    if target == "esp8266":
        topic = f"{settings.MQTT_CMD_TOPIC_PREFIX}/{request.device_id}/cmd"
        # Format attendu par le firmware esp8266 : {"buzzer": "on|off", "led": "on|off"}
        payload_to_mqtt = request.command
    elif target == "yanshee":
        topic = settings.MQTT_ROBOT_CMD_TOPIC
        # Format attendu par yanshee_mqtt_listener.py : {"cmd": "punch", "dry_run": false}
        action = request.command.get("action", "punch")
        dry_run = request.command.get("dry_run", False)
        payload_to_mqtt = {"cmd": action, "dry_run": dry_run}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cible inconnue : {target}. Valeurs permises : 'esp8266', 'yanshee'."
        )

    # Publication MQTT
    published = mqtt_manager.publish_command(topic, payload_to_mqtt)

    # Journalisation dans la table d'audit
    audit = ActuatorAuditLog(
        triggered_at=datetime.now(timezone.utc),
        target=target,
        device_id=request.device_id,
        command_payload=json.dumps(payload_to_mqtt),
        user_identity="authenticated_client"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    return {
        "status": "published" if published else "queued_offline",
        "topic": topic,
        "command_sent": payload_to_mqtt,
        "audit_id": audit.id,
        "mqtt_connected": mqtt_manager.is_connected
    }


@router.get(
    "/audit",
    response_model=List[ActuatorAuditResponse],
    summary="Consulter l'historique d'audit des actionneurs",
    description="Retourne les dernières actions physiques déclenchées pour traçabilité."
)
async def get_audit_logs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    query = select(ActuatorAuditLog).order_by(desc(ActuatorAuditLog.triggered_at)).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()
    return [l.to_dict() for l in logs]


# ============================================================
# Aliases pour le Dashboard Web (/api/v1/control/alarm & led)
# ============================================================

control_router = APIRouter(prefix="/api/v1/control", tags=["Dashboard Control"])


@control_router.post("/alarm", summary="Déclencher l'alarme buzzer")
async def trigger_alarm(db: AsyncSession = Depends(get_db)):
    topic = f"{settings.MQTT_CMD_TOPIC_PREFIX}/sentinel-01/cmd"
    payload = {"buzzer": "on"}
    published = mqtt_manager.publish_command(topic, payload)

    audit = ActuatorAuditLog(
        triggered_at=datetime.now(timezone.utc),
        target="esp8266",
        device_id="sentinel-01",
        command_payload=json.dumps(payload),
        user_identity="dashboard_operator"
    )
    db.add(audit)
    await db.commit()

    return {"status": "alarm_triggered", "published": published}


@control_router.post("/led", summary="Toggle statut LED")
async def toggle_led(db: AsyncSession = Depends(get_db)):
    topic = f"{settings.MQTT_CMD_TOPIC_PREFIX}/sentinel-01/cmd"
    payload = {"led": "on"}
    published = mqtt_manager.publish_command(topic, payload)

    audit = ActuatorAuditLog(
        triggered_at=datetime.now(timezone.utc),
        target="esp8266",
        device_id="sentinel-01",
        command_payload=json.dumps(payload),
        user_identity="dashboard_operator"
    )
    db.add(audit)
    await db.commit()

    return {"status": "led_triggered", "published": published}

