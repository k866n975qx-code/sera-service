from __future__ import annotations

from datetime import datetime, date as DateType

from sqlalchemy import Column, Integer, Date, Float, JSON, DateTime, UniqueConstraint
from app.core.db import Base


class AppleHealthDaily(Base):
    __tablename__ = "apple_health_daily"
    __table_args__ = (UniqueConstraint("date", name="uq_apple_health_date"),)

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)

    # Core metrics we care about from Apple Health
    weight_kg = Column(Float)
    bodyfat_pct = Column(Float)
    rhr_bpm = Column(Float)
    hrv_ms = Column(Float)

    # Extra fields you may use later (sleep, hydration, etc.)
    sleep_hours = Column(Float)
    sleep_efficiency_pct = Column(Float)
    deep_sleep_pct = Column(Float)
    rem_sleep_pct = Column(Float)
    hydration_pct = Column(Float)

    # Raw JSON records from Health Auto Export for this date
    raw_payload = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)