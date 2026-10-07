"""Modèle SQLAlchemy pour l'historique des mesures de télémétrie capteurs."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, BigInteger, Float, String, Boolean, DateTime
from app.database import Base


class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    device_id = Column(String(64), nullable=False, index=True)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    uptime_s = Column(Integer, nullable=True)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    gas_raw = Column(Integer, nullable=True)
    gas_baseline = Column(Integer, nullable=True)
    gas_level = Column(String(32), nullable=True)
    presence = Column(Boolean, default=False, nullable=False)
    rssi = Column(Integer, nullable=True)
    buzzer_state = Column(String(8), default="off", nullable=True)
    led_state = Column(String(8), default="off", nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "uptime_s": self.uptime_s,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "gas": {
                "raw": self.gas_raw,
                "baseline": self.gas_baseline,
                "level": self.gas_level,
            },
            "presence": self.presence,
            "rssi": self.rssi,
            "actuators": {
                "buzzer": self.buzzer_state,
                "led": self.led_state,
            }
        }
