"""Modèle SQLAlchemy pour les alertes de sécurité (Contrat d'interface §4.5)."""

import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, Text
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    device_id = Column(String(64), default="esp-01", nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    source = Column(String(64), default="sensor", nullable=False, index=True)  # sensor | ia_vision | ia_anomaly | manual
    alert_type = Column(String(64), default="general", nullable=False, index=True)
    level = Column(String(32), default="warning", nullable=False, index=True)  # info | warning | alert | critical
    value = Column(Float, nullable=True)
    message = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=True)  # Contenu brut ou métadonnées JSON
    acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(128), nullable=True)

    def to_dict(self):
        parsed_payload = {}
        if self.payload_json:
            try:
                parsed_payload = json.loads(self.payload_json)
            except Exception:
                parsed_payload = {"raw": self.payload_json}

        dt = self.created_at
        if dt:
            dt_utc = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
            ts_iso = dt_utc.isoformat()
        else:
            ts_iso = None

        return {
            "id": self.id,
            "device_id": self.device_id,
            "ts": ts_iso,
            "created_at": ts_iso,
            "source": self.source,
            "alert_type": self.alert_type,
            "level": self.level,
            "severity": self.level,  # compatibilité ascendante
            "value": self.value,
            "message": self.message,
            "payload": parsed_payload,
            "metadata": parsed_payload,  # alias
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
        }
