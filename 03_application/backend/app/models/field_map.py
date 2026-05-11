from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FieldMap(Base):
    __tablename__ = 'field_maps'

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    polygon_geojson: Mapped[str] = mapped_column(Text, nullable=False)
    area_m2: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    traps = relationship('TrapPoint', back_populates='field', cascade='all, delete-orphan')


class TrapPoint(Base):
    __tablename__ = 'trap_points'

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    field_id: Mapped[str] = mapped_column(ForeignKey('field_maps.id', ondelete='CASCADE'), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    custom_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    position_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    field = relationship('FieldMap', back_populates='traps')
