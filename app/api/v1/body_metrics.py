# app/api/v1/body_metrics.py

from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.body_metrics import BodyMetricsEntry

router = APIRouter(prefix="/body-metrics", tags=["body-metrics"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Pydantic schemas ----------

class BodyMetricsIn(BaseModel):
    timestamp: datetime = Field(..., description="ISO8601 timestamp of measurement")
    weight_kg: float | None = None
    bmi: float | None = None
    body_fat_pct: float | None = None
    water_pct: float | None = None
    muscle_mass_kg: float | None = None
    bone_mass_kg: float | None = None
    fat_free_mass_kg: float | None = None
    skeletal_muscle_kg: float | None = None
    protein_kg: float | None = None
    visceral_fat: float | None = None
    subcutaneous_fat_pct: float | None = None
    bmr_kcal: float | None = None
    metabolic_age: int | None = None
    source: str | None = "manual"


class BodyMetricsBatchIn(BaseModel):
    measurements: list[BodyMetricsIn]


# ---------- Endpoints ----------

@router.post("/ingest")
def ingest_body_metrics(payload: BodyMetricsBatchIn, db: Session = Depends(get_db)):
    """
    Insert one or more body-metric measurements into the DB.
    """
    created = 0
    for m in payload.measurements:
        dt = m.timestamp
        entry = BodyMetricsEntry(
            timestamp=dt,
            date=dt.date(),
            weight_kg=m.weight_kg,
            bmi=m.bmi,
            body_fat_pct=m.body_fat_pct,
            water_pct=m.water_pct,
            muscle_mass_kg=m.muscle_mass_kg,
            bone_mass_kg=m.bone_mass_kg,
            fat_free_mass_kg=m.fat_free_mass_kg,
            skeletal_muscle_kg=m.skeletal_muscle_kg,
            protein_kg=m.protein_kg,
            visceral_fat=m.visceral_fat,
            subcutaneous_fat_pct=m.subcutaneous_fat_pct,
            bmr_kcal=m.bmr_kcal,
            metabolic_age=m.metabolic_age,
            source=m.source or "manual",
        )
        db.add(entry)
        created += 1

    db.commit()
    return {"status": "ok", "created": created}


@router.get("/dates")
def list_body_metric_dates(db: Session = Depends(get_db)):
    """
    Return all dates (YYYY-MM-DD) where we have at least one body-metrics entry.
    """
    rows = db.query(func.date(BodyMetricsEntry.date)).distinct().order_by(
        BodyMetricsEntry.date
    )
    dates = [r[0].isoformat() for r in rows]
    return {"status": "ok", "dates": dates}


@router.get("/daily/{date_str}")
def get_body_metrics_for_date(date_str: str, db: Session = Depends(get_db)):
    """
    Return the latest body-metrics entry for a given date (YYYY-MM-DD).
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    entry: BodyMetricsEntry | None = (
        db.query(BodyMetricsEntry)
        .filter(BodyMetricsEntry.date == target_date)
        .order_by(BodyMetricsEntry.timestamp.desc())
        .first()
    )

    if not entry:
        return {"status": "ok", "date": date_str, "found": False}

    return {
        "status": "ok",
        "date": date_str,
        "found": True,
        "weight_kg": entry.weight_kg,
        "bmi": entry.bmi,
        "body_fat_pct": entry.body_fat_pct,
        "water_pct": entry.water_pct,
        "muscle_mass_kg": entry.muscle_mass_kg,
        "bone_mass_kg": entry.bone_mass_kg,
        "fat_free_mass_kg": entry.fat_free_mass_kg,
        "skeletal_muscle_kg": entry.skeletal_muscle_kg,
        "protein_kg": entry.protein_kg,
        "visceral_fat": entry.visceral_fat,
        "subcutaneous_fat_pct": entry.subcutaneous_fat_pct,
        "bmr_kcal": entry.bmr_kcal,
        "metabolic_age": entry.metabolic_age,
        "source": entry.source,
        "raw": {
            "timestamp": entry.timestamp.isoformat(),
        },
    }