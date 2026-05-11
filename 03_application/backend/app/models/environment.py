from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EnvironmentalDaily(Base):
    __tablename__ = 'environmental_daily'
    __table_args__ = (
        UniqueConstraint('field_id', 'observation_date', name='uq_environmental_field_date'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    field_id: Mapped[str] = mapped_column(ForeignKey('field_maps.id', ondelete='CASCADE'), index=True, nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default='open-meteo')
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    temperature_mean_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_max_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_min_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    shortwave_radiation_sum_mj_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    et0_fao_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_max_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    gdd_base10_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_deficit_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    heat_stress_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    light_accumulation_mj_m2: Mapped[float | None] = mapped_column(Float, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EnvironmentalSourceDaily(Base):
    __tablename__ = 'environmental_source_daily'
    __table_args__ = (
        UniqueConstraint('field_id', 'observation_date', 'provider', name='uq_environmental_source_field_date_provider'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    field_id: Mapped[str] = mapped_column(ForeignKey('field_maps.id', ondelete='CASCADE'), index=True, nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    temperature_mean_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_max_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_min_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    shortwave_radiation_sum_mj_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    et0_fao_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_max_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
