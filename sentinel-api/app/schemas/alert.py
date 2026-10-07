"""Schémas Pydantic pour la gestion des alertes (POST /api/v1/alerts).

Conforme au Contrat d'Interface §4.5 du projet SENTINEL-X et au cahier des charges national.
Tolère et normalise automatiquement les variantes de nommage (level/severity, ts/created_at, payload/metadata, device/device_id).
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator


class AlertCreate(BaseModel):
    # Identifiant du boîtier
    device_id: Optional[str] = Field(default="esp-01", description="Identifiant du boîtier (ex: esp-01, sentinel-01)")
    # Horodatage
    ts: Optional[Union[datetime, str]] = Field(default=None, description="Horodatage ISO 8601")
    # Origine
    source: Optional[str] = Field(default="sensor", description="Origine : sensor, ia_vision, ia_anomaly, manual")
    # Type d'événement ou capteur
    alert_type: Optional[str] = Field(default="general", description="Type d'alerte : gas_alert, pir_presence, intrusion, temperature_spike")
    # Niveau d'alerte
    level: Optional[str] = Field(default="warning", description="Niveau : info, warning, alert, alerte, critical, high, medium, low")
    # Valeur de mesure éventuelle
    value: Optional[float] = Field(default=None, description="Valeur numérique mesurée")
    # Message descriptif
    message: Optional[str] = Field(default=None, description="Description humaine de l'alerte")
    # Payload ou données brutes
    payload: Optional[Dict[str, Any]] = Field(default=None, description="Données contextuelles ou payload JSON brut")

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        d = dict(data)

        # 1. Normalisation device_id
        if "device_id" not in d and "device" in d:
            d["device_id"] = str(d["device"])

        # 2. Normalisation level / severity / state
        if "level" not in d:
            if "severity" in d:
                d["level"] = str(d["severity"])
            elif "state" in d:
                d["level"] = str(d["state"])

        # Harmonisation du mot "alerte" / "alert"
        if d.get("level") in ["alerte", "high"]:
            d["level"] = "alert"

        # 3. Normalisation alert_type / sensor / event / type
        if "alert_type" not in d:
            if "sensor" in d:
                d["alert_type"] = f"{d['sensor']}_state"
            elif "event" in d:
                d["alert_type"] = str(d["event"])
            elif "type" in d:
                d["alert_type"] = str(d["type"])

        # 4. Normalisation ts / timestamp
        if "ts" not in d and "timestamp" in d:
            d["ts"] = d["timestamp"]

        # 5. Normalisation payload / metadata / extra fields
        if "payload" not in d and "metadata" in d:
            d["payload"] = d["metadata"]

        # 6. Auto-génération du message s'il est manquant
        if not d.get("message"):
            src = d.get("source", "sensor")
            lvl = d.get("level", "warning")
            val = d.get("value")
            typ = d.get("alert_type", "state_change")
            val_str = f" (valeur: {val})" if val is not None else ""
            d["message"] = f"Alerte {src} [{typ}] niveau {lvl}{val_str}"

        return d


class AlertResponse(BaseModel):
    id: int
    device_id: str
    ts: Optional[str] = None
    created_at: Optional[str] = None
    source: str
    alert_type: str
    level: str
    severity: Optional[str] = None
    value: Optional[float] = None
    message: str
    payload: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    acknowledged: bool = False
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class AlertAcknowledgeRequest(BaseModel):
    acknowledged_by: str = Field(
        default="supervisor",
        description="Identité ou rôle de l'opérateur acquittant l'alerte"
    )
