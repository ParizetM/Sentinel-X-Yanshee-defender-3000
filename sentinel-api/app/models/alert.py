"""Modèle SQLAlchemy pour les alertes de sécurité."""

import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, BigInteger, Float, String, Boolean, DateTime, Text
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    device_id = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    source = Column(String(64), nullable=False)
    alert_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(32), nullable=False, index=True)
    value = Column(Float, nullable=True)
    message = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(128), nullable=True)

    def to_dict(self):
        parsed_metadata = {}
        if self.metadata_json:
            try:
                parsed_metadata = json.loads(self.metadata_json)
            except Exception:
                parsed_metadata = {"raw": self.metadata_json}

        return {
            "id": self.id,
            "device_id": self.device_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "source": self.source,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "value": self.value,
            "message": self.message,
            "metadata": parsed_metadata,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
        }
