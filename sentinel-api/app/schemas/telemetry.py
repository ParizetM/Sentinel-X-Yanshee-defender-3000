"""Schémas Pydantic pour la télémétrie des capteurs (Contrat §4.2)."""

from datetime import datetime
from typing import Optional, Union, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class GasData(BaseModel):
    raw: Optional[int] = Field(None, description="Valeur analogique brute du capteur MQ-2")
    baseline: Optional[int] = Field(None, description="Valeur de référence / baseline après préchauffage")
    level: Optional[str] = Field("normal", description="Niveau calculé (chauffe, normal, eleve, alerte)")

    model_config = ConfigDict(extra="allow")


class ActuatorState(BaseModel):
    buzzer: Optional[str] = Field("off", description="État du buzzer (alert/off)")
    led: Optional[str] = Field("off", description="État de la LED (alert/off)")

    model_config = ConfigDict(extra="allow")


class TelemetryPayload(BaseModel):
    """Payload direct envoyé par l'ESP8266 via MQTT."""
    device: Optional[str] = Field("esp-01", description="Identifiant du boîtier")
    device_id: Optional[str] = Field(None, description="Alias identifiant boîtier")
    uptime_s: Optional[int] = Field(None, description="Temps de fonctionnement en secondes")
    temperature: Optional[float] = Field(None, description="Température en °C (DHT22)")
    humidity: Optional[float] = Field(None, description="Humidité relative en % (DHT22)")
    gas: Optional[Union[GasData, Dict[str, Any], int]] = Field(default_factory=GasData)
    presence: Optional[bool] = Field(False, description="Détection de présence PIR")
    pir: Optional[bool] = Field(None, description="Alias PIR")
    rssi: Optional[int] = Field(None, description="Force du signal Wi-Fi en dBm")
    actuators: Optional[ActuatorState] = Field(default_factory=ActuatorState)

    model_config = ConfigDict(extra="allow")


class TelemetryResponse(BaseModel):
    id: int
    device_id: str
    recorded_at: datetime
    ts: Optional[str] = None
    time: Optional[str] = None
    uptime_s: Optional[int] = None
    temperature: Optional[float] = None
    temp: Optional[float] = None
    humidity: Optional[float] = None
    gas: Optional[Union[GasData, Dict[str, Any]]] = None
    gas_raw: Optional[int] = None
    presence: bool = False
    pir: Optional[bool] = None
    rssi: Optional[int] = None
    actuators: Optional[Union[ActuatorState, Dict[str, Any]]] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")
