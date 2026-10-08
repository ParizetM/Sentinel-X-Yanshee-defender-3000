"""Modèle SQLAlchemy pour l'archivage des photos d'intrusion capturées par l'IA YOLO."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, LargeBinary
from app.database import Base


class CapturedPhoto(Base):
    __tablename__ = "captured_photos"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    device_id = Column(String(64), default="yanshee-01", nullable=False)
    captured_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    person_count = Column(Integer, default=1)
    image_bytes = Column(LargeBinary(length=16777215), nullable=False)  # MEDIUMBLOB (jusqu'à 16 Mo)
    content_type = Column(String(32), default="image/jpeg")

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "person_count": self.person_count,
            "size_bytes": len(self.image_bytes) if self.image_bytes else 0,
            "url": f"/api/v1/camera/photos/{self.id}"
        }
