"""Modèle SQLAlchemy pour l'audit des commandes d'actionneurs."""

import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Text
from app.database import Base


class ActuatorAuditLog(Base):
    __tablename__ = "actuator_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    triggered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    target = Column(String(32), nullable=False)  # "esp8266" | "yanshee"
    device_id = Column(String(64), nullable=False)
    command_payload = Column(Text, nullable=False)
    user_identity = Column(String(128), default="api_user")

    def to_dict(self):
        try:
            payload = json.loads(self.command_payload)
        except Exception:
            payload = {"raw": self.command_payload}

        return {
            "id": self.id,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "target": self.target,
            "device_id": self.device_id,
            "command": payload,
            "user_identity": self.user_identity
        }
