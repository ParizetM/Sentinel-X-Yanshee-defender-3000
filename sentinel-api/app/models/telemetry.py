"""Modèle SQLAlchemy pour l'historique des mesures (Contrat §4.5 Table measurements)."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime
from app.database import Base


class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    device_id = Column(String(64), default="esp-01", nullable=False, index=True)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    uptime_s = Column(Integer, nullable=True)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    gas_raw = Column(Integer, nullable=True)
    gas_baseline = Column(Integer, nullable=True)
    gas_level = Column(String(32), default="normal", nullable=True)
    presence = Column(Boolean, default=False, nullable=False)
    rssi = Column(Integer, nullable=True)
    buzzer_state = Column(String(16), default="off", nullable=True)
    led_state = Column(String(16), default="off", nullable=True)

    def to_dict(self):
        iso_time = self.recorded_at.isoformat() if self.recorded_at else None
        clock_time = self.recorded_at.strftime("%H:%M:%S") if self.recorded_at else None

        return {
            "id": self.id,
            "device_id": self.device_id,
            "recorded_at": iso_time,
            "ts": iso_time,
            "time": clock_time,  # Pour Recharts React
            "uptime_s": self.uptime_s,
            "temperature": self.temperature,
            "temp": self.temperature,  # Alias pour le Dashboard React
            "humidity": self.humidity,
            "gas": {
                "raw": self.gas_raw,
                "baseline": self.gas_baseline,
                "level": self.gas_level,
            },
            "gas_raw": self.gas_raw,
            "presence": self.presence,
            "pir": self.presence,  # Alias contrat §4.2
            "rssi": self.rssi,
            "actuators": {
                "buzzer": self.buzzer_state,
                "led": self.led_state,
            }
        }
