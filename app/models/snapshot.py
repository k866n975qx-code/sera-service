from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    Float,
    Date,
    DateTime,
    String,
    JSON,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.db import Base


class SeraDailySnapshot(Base):
    __tablename__ = "sera_daily_snapshot"
    __table_args__ = (UniqueConstraint("date", name="uq_snapshot_date"),)

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)

    # canonical metrics (WHOOP primary; other sources may be added later)
    hrv_ms = Column(Float)
    rhr_bpm = Column(Float)
    sleep_hours = Column(Float)
    sleep_efficiency_pct = Column(Float)
    deep_sleep_pct = Column(Float)
    rem_sleep_pct = Column(Float)
    sleep_consistency_pct = Column(Float)
    sleep_disturbance_count = Column(Integer)
    weight_kg = Column(Float)
    weight_lb = Column(Float)
    bodyfat_pct = Column(Float)
    hydration_pct = Column(Float)
    recovery_score = Column(Integer)
    strain = Column(Float)
    respiratory_rate = Column(Float)
    spo2_pct = Column(Float)

    # readiness (to be filled in later)
    readiness_index = Column(Integer)
    readiness_zone = Column(String(16))
    flags = Column(JSON)
    insight = Column(String(512))

    whoop_id = Column(Integer, ForeignKey("whoop_daily.id"))
    whoop = relationship("WhoopDaily")

    created_at = Column(DateTime, default=datetime.utcnow)