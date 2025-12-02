

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import Base
from app.models.renpho import RenphoMeasurement
from datetime import datetime
from typing import List, Optional

router = APIRouter(prefix="/v1/renpho", tags=["Renpho"])

# ---- Helpers ----

def parse_iso(dt_str: str) -> datetime:
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid ISO datetime: {dt_str}")

# ---- Endpoints ----

@router.get("/dates")
def get_renpho_dates(db: Session = Depends(get_db)):
    rows = db.query(RenphoMeasurement.date).distinct().all()
    dates = sorted(list({r[0].strftime("%Y-%m-%d") for r in rows}))
    return {"status": "ok", "dates": dates}

@router.post("/")
def save_renpho_measurements(
    data: List[dict],
    db: Session = Depends(get_db)
):
    """
    Accepts an array of Renpho measurement payloads.
    Each item must contain:
      - date (ISO string)
      - weight_kg
      - bodyfat_pct
      - muscle_mass_kg
      - water_pct
      - bone_mass_kg
    """

    saved = []

    for item in data:
        if "date" not in item:
            raise HTTPException(status_code=400, detail="Missing 'date' in payload")

        dt = parse_iso(item["date"])

        entry = RenphoMeasurement(
            date=dt,
            weight_kg=item.get("weight_kg"),
            bodyfat_pct=item.get("bodyfat_pct"),
            muscle_mass_kg=item.get("muscle_mass_kg"),
            water_pct=item.get("water_pct"),
            bone_mass_kg=item.get("bone_mass_kg"),
        )

        db.add(entry)
        saved.append(item)

    db.commit()

    return {"status": "ok", "count": len(saved)}

@router.get("/daily/{date}")
def get_renpho_daily(date: str, db: Session = Depends(get_db)):
    """
    Returns all Renpho metrics for a given date (YYYY-MM-DD)
    """

    try:
        target = datetime.fromisoformat(date)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    rows = (
        db.query(RenphoMeasurement)
        .filter(RenphoMeasurement.date.like(f"{date}%"))
        .order_by(RenphoMeasurement.date.asc())
        .all()
    )

    if not rows:
        return {"status": "ok", "date": date, "found": False, "raw": []}

    merged = {
        "weight_kg": rows[-1].weight_kg,
        "bodyfat_pct": rows[-1].bodyfat_pct,
        "muscle_mass_kg": rows[-1].muscle_mass_kg,
        "water_pct": rows[-1].water_pct,
        "bone_mass_kg": rows[-1].bone_mass_kg,
    }

    raw = [
        {
            "date": r.date.isoformat(),
            "weight_kg": r.weight_kg,
            "bodyfat_pct": r.bodyfat_pct,
            "muscle_mass_kg": r.muscle_mass_kg,
            "water_pct": r.water_pct,
            "bone_mass_kg": r.bone_mass_kg,
        }
        for r in rows
    ]

    return {
        "status": "ok",
        "date": date,
        "found": True,
        "snapshot": merged,
        "raw": raw,
    }