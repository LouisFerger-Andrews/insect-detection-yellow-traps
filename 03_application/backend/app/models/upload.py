from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TrapUpload(Base):
    __tablename__ = 'trap_uploads'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    field_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trap_code: Mapped[str] = mapped_column(String(100), nullable=False)
    trap_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    capture_date: Mapped[date] = mapped_column(Date, nullable=False)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    detection_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence_avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    detections = relationship('Detection', back_populates='upload', cascade='all, delete-orphan')


class Detection(Base):
    __tablename__ = 'detections'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey('trap_uploads.id', ondelete='CASCADE'), nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    x2: Mapped[float] = mapped_column(Float, nullable=False)
    y2: Mapped[float] = mapped_column(Float, nullable=False)

    upload = relationship('TrapUpload', back_populates='detections')
