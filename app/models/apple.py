from datetime import datetime
from sqlalchemy import Column, Integer, Float, Date, DateTime, JSON, UniqueConstraint
from app.core.db import Base


class AppleHealthDaily(Base):
    __tablename__ = "apple_health_daily"
    __table_args__ = (UniqueConstraint("date", name="uq_apple_date"),)

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)

    hrv_ms = Column(Float)
    rhr_bpm = Column(Float)
    sleep_hours = Column(Float)
    sleep_efficiency_pct = Column(Float)
    deep_sleep_pct = Column(Float)
    rem_sleep_pct = Column(Float)
    weight_kg = Column(Float)
    bodyfat_pct = Column(Float)
    hydration_pct = Column(Float)

    raw_payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)