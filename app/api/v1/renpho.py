from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.renpho import RenphoWeightEntry

router = APIRouter(prefix="/renpho", tags=["renpho"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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