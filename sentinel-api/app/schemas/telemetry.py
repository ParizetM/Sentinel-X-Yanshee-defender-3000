"""Schémas Pydantic pour la télémétrie des capteurs."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class GasData(BaseModel):
    raw: Optional[int] = Field(None, description="Valeur analogique brute du capteur MQ-2")
    baseline: Optional[int] = Field(None, description="Valeur de référence / baseline après préchauffage")
    level: Optional[str] = Field("normal", description="Niveau calculé (chauffe, normal, eleve, alerte)")


class ActuatorState(BaseModel):
    buzzer: Optional[str] = Field("off", description="État du buzzer (on/off)")
    led: Optional[str] = Field("off", description="État de la LED (on/off)")


class TelemetryPayload(BaseModel):
    """Payload direct envoyé par l'ESP8266 via MQTT."""
    device: str = Field(..., description="Identifiant du boîtier")
    uptime_s: Optional[int] = Field(None, description="Temps de fonctionnement en secondes")
    temperature: Optional[float] = Field(None, description="Température en °C (DHT22)")
    humidity: Optional[float] = Field(None, description="Humidité relative en % (DHT22)")
    gas: Optional[GasData] = Field(default_factory=GasData)
    presence: bool = Field(False, description="Détection de présence PIR")
    rssi: Optional[int] = Field(None, description="Force du signal Wi-Fi en dBm")
    actuators: Optional[ActuatorState] = Field(default_factory=ActuatorState)


class TelemetryResponse(BaseModel):
    id: int
    device_id: str
    recorded_at: datetime
    uptime_s: Optional[int] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    gas: GasData
    presence: bool
    rssi: Optional[int] = None
    actuators: ActuatorState

    model_config = ConfigDict(from_attributes=True)
