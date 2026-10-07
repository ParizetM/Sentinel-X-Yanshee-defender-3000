"""Schémas Pydantic pour les commandes d'actionneurs."""

from datetime import datetime
from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class ESP8266ActuatorCommand(BaseModel):
    buzzer: Optional[Literal["on", "off"]] = Field(None, description="Commande buzzer (on/off)")
    led: Optional[Literal["on", "off"]] = Field(None, description="Commande LED (on/off)")


class RobotCommand(BaseModel):
    action: Literal["punch", "victory", "patrol", "standby"] = Field(
        ...,
        description="Action demandée au robot Yanshee"
    )
    dry_run: bool = Field(
        False,
        description="Si vrai, simule sans solliciter les moteurs"
    )


class ActuatorCommandRequest(BaseModel):
    target: Literal["esp8266", "yanshee"] = Field(
        ...,
        description="Cible matérielle de la commande",
        examples=["esp8266"]
    )
    device_id: str = Field(
        default="sentinel-01",
        description="Identifiant de l'appareil (pour esp8266)",
        examples=["sentinel-01"]
    )
    command: Dict[str, Any] = Field(
        ...,
        description="Détail de la commande (ex: {'buzzer': 'on'} ou {'action': 'punch', 'dry_run': false})",
        examples=[{"buzzer": "on", "led": "on"}]
    )


class ActuatorAuditResponse(BaseModel):
    id: int
    triggered_at: datetime
    target: str
    device_id: str
    command: Dict[str, Any]
    user_identity: str
