"""Routeur des commandes d'actionneurs (Contrat §4.3 & §4.4, KAN-35)."""

import json
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.audit import ActuatorAuditLog
from app.schemas.actuator import CommandRequest, ActuatorAuditResponse
from app.mqtt_client import mqtt_manager

router = APIRouter(tags=["Commands & Actuators"])


@router.post(
    "/api/v1/commands",
    summary="Envoyer une commande d'actionneur (Contrat d'interface §4.4)",
    description="Relaye une commande vers l'ESP8266 (buzzer/led/all) ou le robot Yanshee."
)
@router.post(
    "/api/v1/actuators/command",
    summary="Alias commande actionneurs",
    include_in_schema=False
)
async def send_command(
    request: CommandRequest,
    db: AsyncSession = Depends(get_db)
):
    target = request.target.lower()
    device_id = request.device_id or "esp-01"

    # 1. Commande destinée à l'ESP8266 (buzzer, led, all)
    if target in ["buzzer", "led", "all", "esp8266"]:
        esp_target = "all" if target == "esp8266" else target
        topic = f"{settings.MQTT_CMD_TOPIC_PREFIX}/{device_id}/cmd"

        state_val = (request.state or "toggle").lower()
        payload_to_mqtt = {
            "target": esp_target,
            "state": state_val
        }
        # Clés directes pour compatibilité universelle firmware ({"buzzer": "on"}, {"led": "on"})
        if esp_target in ("buzzer", "all"):
            payload_to_mqtt["buzzer"] = state_val
        if esp_target in ("led", "all"):
            payload_to_mqtt["led"] = state_val

        if request.duration_ms:
            payload_to_mqtt["duration_ms"] = request.duration_ms

    # 2. Commande destinée au Robot Yanshee
    elif target in ["yanshee", "robot"]:
        topic = settings.MQTT_ROBOT_CMD_TOPIC
        action = request.action or "punch"
        payload_to_mqtt = {
            "cmd": action,
            "dry_run": bool(request.dry_run)
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cible '{target}' inconnue. Valeurs attendues : 'buzzer', 'led', 'all', 'yanshee'."
        )

    # Publication vers le broker MQTT
    published = mqtt_manager.publish_command(topic, payload_to_mqtt)

    # Journalisation d'audit
    audit = ActuatorAuditLog(
        triggered_at=datetime.now(timezone.utc),
        target=target,
        device_id=device_id,
        command_payload=json.dumps(payload_to_mqtt),
        user_identity="supervisor"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    return {
        "status": "published" if published else "sent_offline",
        "target": target,
        "topic": topic,
        "command": payload_to_mqtt,
        "audit_id": audit.id,
        "mqtt_connected": mqtt_manager.is_connected
    }


@router.get(
    "/api/v1/commands",
    response_model=List[ActuatorAuditResponse],
    summary="Historique des commandes envoyées",
    description="Retourne les dernières actions physiques déclenchées pour traçabilité."
)
@router.get(
    "/api/v1/actuators/audit",
    response_model=List[ActuatorAuditResponse],
    include_in_schema=False
)
async def get_commands_audit(
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


@control_router.post("/alarm", summary="Déclencher l'alarme buzzer (ESP8266)")
async def trigger_alarm(db: AsyncSession = Depends(get_db)):
    topic = f"{settings.MQTT_CMD_TOPIC_PREFIX}/esp-01/cmd"
    payload = {"target": "buzzer", "state": "toggle"}
    published = mqtt_manager.publish_command(topic, payload)

    audit = ActuatorAuditLog(
        triggered_at=datetime.now(timezone.utc),
        target="buzzer",
        device_id="esp-01",
        command_payload=json.dumps(payload),
        user_identity="dashboard_operator"
    )
    db.add(audit)
    await db.commit()

    return {"status": "alarm_triggered", "published": published, "payload": payload}


@control_router.post("/led", summary="Toggle statut LED (ESP8266)")
async def toggle_led(db: AsyncSession = Depends(get_db)):
    topic = f"{settings.MQTT_CMD_TOPIC_PREFIX}/esp-01/cmd"
    payload = {"target": "led", "state": "toggle"}
    published = mqtt_manager.publish_command(topic, payload)

    audit = ActuatorAuditLog(
        triggered_at=datetime.now(timezone.utc),
        target="led",
        device_id="esp-01",
        command_payload=json.dumps(payload),
        user_identity="dashboard_operator"
    )
    db.add(audit)
    await db.commit()

    return {"status": "led_triggered", "published": published, "payload": payload}
