from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.db import SessionLocal
from app.models.renpho import RenphoWeightEntry

router = APIRouter(prefix="/renpho", tags=["renpho"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class RenphoMeasurementIn(BaseModel):
    timestamp: datetime
    weight_kg: float
    bmi: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    bone_mass_kg: Optional[float] = None
    water_pct: Optional[float] = None
    bmr_kcal: Optional[float] = None
    metabolic_age: Optional[int] = None
    visceral_fat: Optional[float] = None
    impedance: Optional[float] = None
    source: Optional[str] = "renpho"


class RenphoIngestPayload(BaseModel):
    measurements: List[RenphoMeasurementIn]


@router.post("/ingest")
def ingest_renpho(payload: RenphoIngestPayload, db: Session = Depends(get_db)):
    """Ingest one or more Renpho scale measurements."""
    created = 0
    for m in payload.measurements:
        entry = RenphoWeightEntry(
            timestamp=m.timestamp,
            weight_kg=m.weight_kg,
            bmi=m.bmi,
            body_fat_pct=m.body_fat_pct,
            muscle_mass_kg=m.muscle_mass_kg,
            bone_mass_kg=m.bone_mass_kg,
            water_pct=m.water_pct,
            bmr_kcal=m.bmr_kcal,
            metabolic_age=m.metabolic_age,
            visceral_fat=m.visceral_fat,
            impedance=m.impedance,
            source=m.source or "renpho",
        )
        db.add(entry)
        created += 1

    db.commit()
    return {"status": "ok", "created": created}


@router.get("/dates")
def get_renpho_dates(db: Session = Depends(get_db)):
    """
    Return all dates (YYYY-MM-DD) where we have at least one Renpho measurement.
    """
    rows = (
        db.query(func.date(RenphoWeightEntry.timestamp))
        .distinct()
        .order_by(func.date(RenphoWeightEntry.timestamp))
        .all()
    )
    dates = [r[0].isoformat() for r in rows]
    return {"status": "ok", "dates": dates}


@router.get("/daily/{date_str}")
def get_renpho_daily(date_str: str, db: Session = Depends(get_db)):
    """
    Return the latest Renpho measurement for a given date (YYYY-MM-DD).
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    entry: Optional[RenphoWeightEntry] = (
        db.query(RenphoWeightEntry)
        .filter(func.date(RenphoWeightEntry.timestamp) == target_date)
        .order_by(RenphoWeightEntry.timestamp.desc())
        .first()
    )

    if not entry:
        return {"status": "ok", "date": date_str, "found": False}

    return {
        "status": "ok",
        "date": date_str,
        "found": True,
        "weight_kg": entry.weight_kg,
        "bodyfat_pct": entry.body_fat_pct,
        "bmi": entry.bmi,
        "muscle_mass_kg": entry.muscle_mass_kg,
        "bone_mass_kg": entry.bone_mass_kg,
        "water_pct": entry.water_pct,
        "bmr_kcal": entry.bmr_kcal,
        "metabolic_age": entry.metabolic_age,
        "visceral_fat": entry.visceral_fat,
        "impedance": entry.impedance,
        "source": entry.source,
        "raw": {
            "timestamp": entry.timestamp.isoformat(),
        },
    }