# app/models/body_metrics.py

from datetime import datetime, date

from sqlalchemy import Column, Date, DateTime, Float, Integer, String

from app.core.db import Base


class BodyMetricsEntry(Base):
    """
    Generic body-composition measurement for a single timestamp.
    This is NOT tied to Renpho anymore – just 'body metrics'.
    """

    __tablename__ = "body_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # when the measurement actually happened
    timestamp = Column(DateTime, nullable=False, index=True)
    # cached date for easier querying
    date = Column(Date, nullable=False, index=True)

    # core stuff
    weight_kg = Column(Float)
    bmi = Column(Float)
    body_fat_pct = Column(Float)
    water_pct = Column(Float)

    # composition
    muscle_mass_kg = Column(Float)
    bone_mass_kg = Column(Float)
    fat_free_mass_kg = Column(Float)
    skeletal_muscle_kg = Column(Float)
    protein_kg = Column(Float)

    # other metrics
    visceral_fat = Column(Float)
    subcutaneous_fat_pct = Column(Float)
    bmr_kcal = Column(Float)
    metabolic_age = Column(Integer)

    # where this came from (screenshot, script, whatever)
    source = Column(String(64), default="manual")