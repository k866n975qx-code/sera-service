from sqlalchemy import Column, Integer, Float, String, DateTime
from app.db.base import Base

class RenphoWeightEntry(Base):
    __tablename__ = "renpho_weight_entries"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True, nullable=False)
    weight_kg = Column(Float, nullable=False)
    bmi = Column(Float, nullable=True)
    body_fat_pct = Column(Float, nullable=True)
    muscle_mass_kg = Column(Float, nullable=True)
    bone_mass_kg = Column(Float, nullable=True)
    water_pct = Column(Float, nullable=True)
    bmr_kcal = Column(Float, nullable=True)
    metabolic_age = Column(Integer, nullable=True)
    visceral_fat = Column(Float, nullable=True)
    impedance = Column(Float, nullable=True)
    source = Column(String, default="renpho")
