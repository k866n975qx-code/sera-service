# app/models/body_metrics.py

from datetime import datetime, date

from sqlalchemy import Column, Date, DateTime, Float, Integer, String

from app.core.db import Base


class BodyMetricsEntry(Base):
    """
    Generic body-composition measurement for a single timestamp.
    Not tied to any specific device brand.
    """

    __tablename__ = "body_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # When the measurement happened
    timestamp = Column(DateTime, nullable=False, index=True)
    # Cached calendar date (for easy daily queries, in your local-day semantics)
    date = Column(Date, nullable=False, index=True)

    # Weight
    weight_kg = Column(Float)          # from device or converted
    weight_lb = Column(Float)          # optional, as reported

    # Core composition
    bmi = Column(Float)
    body_fat_pct = Column(Float)
    body_fat_mass_kg = Column(Float)
    body_fat_mass_lb = Column(Float)

    subcutaneous_fat_pct = Column(Float)
    visceral_fat = Column(Float)       # Renpho "score" (e.g. 17)

    body_water_pct = Column(Float)

    # Muscle & bone
    muscle_mass_kg = Column(Float)
    muscle_mass_lb = Column(Float)

    skeletal_muscle_kg = Column(Float)
    skeletal_muscle_lb = Column(Float)

    bone_mass_kg = Column(Float)
    bone_mass_lb = Column(Float)

    fat_free_mass_kg = Column(Float)
    fat_free_mass_lb = Column(Float)

    # Protein
    protein_pct = Column(Float)
    protein_kg = Column(Float)

    # Other derived metrics
    bmr_kcal = Column(Float)
    metabolic_age = Column(Integer)

    # Optional text / classification from device (if you ever want it)
    body_type = Column(String(64))     # e.g. "Obese", "Standard", etc.

    # Where this came from (screenshot, script, integration, etc.)
    source = Column(String(64), default="manual")