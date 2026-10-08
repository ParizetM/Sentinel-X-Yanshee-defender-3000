"""Modèle SQLAlchemy pour l'archivage des photos d'intrusion capturées par l'IA YOLO."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from app.database import Base


class CapturedPhoto(Base):
    __tablename__ = "captured_photos"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    device_id = Column(String(64), default="yanshee-01", nullable=False)
    captured_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    person_count = Column(Integer, default=1)
    image_base64 = Column(Text().with_variant(LONGTEXT, "mysql"), nullable=False)  # Encodage base64 pour compatibilité BDD et réseau
    content_type = Column(String(32), default="image/jpeg")

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "person_count": self.person_count,
            "size_bytes": len(self.image_base64) * 3 // 4 if self.image_base64 else 0,
            "url": f"/api/v1/camera/photos/{self.id}"
        }
