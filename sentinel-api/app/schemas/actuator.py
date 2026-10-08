"""Schémas Pydantic pour les commandes d'actionneurs (Contrat d'interface §4.3 & §4.4)."""

from datetime import datetime
from typing import Optional, Literal, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict


class CommandRequest(BaseModel):
    """Payload officiel du contrat §4.3 : { "target": "buzzer", "state": "toggle", "duration_ms": 3000 }."""
    target: str = Field(
        default="all",
        description="Actionneur(s) visé(s) : buzzer, led, all, yanshee",
        examples=["buzzer"]
    )
    state: Optional[str] = Field(
        default="toggle",
        description="Mode : toggle (défaut), on, off",
        examples=["toggle"]
    )
    duration_ms: Optional[int] = Field(
        default=None,
        description="Durée d'activation temporisée en millisecondes",
        examples=[5000]
    )
    device_id: Optional[str] = Field(
        default="esp-01",
        description="Identifiant du boîtier ESP8266 cible (défaut: esp-01)"
    )
    action: Optional[str] = Field(
        default=None,
        description="Action spécifique pour le robot Yanshee (punch, victory, patrol)"
    )
    dry_run: Optional[bool] = Field(
        default=False,
        description="Mode simulation sans sollicitation des servomoteurs"
    )

    model_config = ConfigDict(extra="allow")


class ActuatorAuditResponse(BaseModel):
    id: int
    triggered_at: datetime
    target: str
    device_id: str
    command: Dict[str, Any]
    user_identity: str


# Alias de compatibilité
ActuatorCommandRequest = CommandRequest
ESP8266ActuatorCommand = CommandRequest
RobotCommand = CommandRequest

