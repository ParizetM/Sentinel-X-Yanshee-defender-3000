"""Schémas Pydantic pour la gestion des alertes (POST /api/v1/alerts)."""

from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class AlertCreate(BaseModel):
    source: str = Field(
        ...,
        description="Origine de l'alerte (ex: sensor_esp8266, ia_vision, ia_anomaly, manual)",
        examples=["sensor_esp8266"]
    )
    device_id: str = Field(
        default="sentinel-01",
        description="Identifiant unique du boîtier émetteur",
        examples=["sentinel-01"]
    )
    alert_type: str = Field(
        ...,
        description="Type d'alerte (ex: gas_alert, temperature_spike, human_intrusion, offline)",
        examples=["gas_alert"]
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Niveau de criticité de l'alerte",
        examples=["critical"]
    )
    value: Optional[float] = Field(
        default=None,
        description="Valeur numérique associée au dépassement de seuil",
        examples=[450.0]
    )
    message: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Description humaine explicite de l'alerte",
        examples=["Seuil critique de gaz atteint (MQ-2 : 450)"]
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Données contextuelles optionnelles (ex: confiance IA, snapshot, coordonnées)",
        examples=[{"confidence": 0.94, "snapshot_url": "/snapshots/alert_123.jpg"}]
    )

    model_config = ConfigDict(extra="forbid")


class AlertResponse(BaseModel):
    id: int
    device_id: str
    created_at: datetime
    source: str
    alert_type: str
    severity: str
    value: Optional[float] = None
    message: str
    metadata: Optional[Dict[str, Any]] = None
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AlertAcknowledgeRequest(BaseModel):
    acknowledged_by: str = Field(
        default="supervisor",
        description="Identité ou rôle de l'opérateur acquittant l'alerte",
        examples=["supervisor"]
    )
