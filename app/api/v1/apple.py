from datetime import date as DateType

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, engine
from app.models.apple import AppleHealthDaily
from app.core.merge import merge_for_date


router = APIRouter(tags=["apple"])


class AppleIn(BaseModel):
    date: str
    hrv_ms: float | None = None
    rhr_bpm: float | None = None
    sleep_hours: float | None = None
    sleep_efficiency_pct: float | None = None
    deep_sleep_pct: float | None = None
    rem_sleep_pct: float | None = None
    weight_kg: float | None = None
    bodyfat_pct: float | None = None
    hydration_pct: float | None = None
    raw_payload: dict | None = None


@router.post("/apple-health")
def ingest_apple(payload: AppleIn):
    if not engine or not SessionLocal:
        raise HTTPException(503, "DB not configured (POSTGRES_DSN missing)")

    db: Session = SessionLocal()
    try:
        d = DateType.fromisoformat(payload.date)
        data = payload.dict(exclude={"date"})

        existing = (
            db.query(AppleHealthDaily)
            .filter(AppleHealthDaily.date == d)
            .one_or_none()
        )

        if existing:
            for field, value in data.items():
                setattr(existing, field, value)
        else:
            row = AppleHealthDaily(date=d, **data)
            db.add(row)

        # WHOOP-primary/Apple-fallback merge for this date
        merge_for_date(db, d)

        db.commit()
    finally:
        db.close()

    return {"status": "ok", "date": payload.date}