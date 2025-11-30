from __future__ import annotations

from collections import defaultdict
from datetime import datetime, date as DateType
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.apple import AppleHealthDaily

router = APIRouter(tags=["apple-health"])


def _parse_dt(dt_str: str | None) -> datetime | None:
    if not dt_str or not isinstance(dt_str, str):
        return None
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def _to_kg(value: float | int | None, unit: str | None) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        return None
    if unit and unit.lower() in ("kg", "kilogram", "kilograms"):
        return float(value)
    if unit and unit.lower() in ("lb", "lbs", "pound", "pounds"):
        return float(value) * 0.45359237
    return float(value)


@router.post("/apple-health")
async def apple_health(payload: Dict[str, Any]):
    """
    Ingest Health Auto Export JSON payload and upsert into apple_health_daily.
    """
    db: Session = SessionLocal()

    # { date: {"weight_kg": ..., "bodyfat_pct": ..., "rhr_bpm": ..., "hrv_ms": ..., "raw": [...] } }
    per_date: Dict[DateType, Dict[str, Any]] = defaultdict(
        lambda: {
            "weight_kg": None,
            "bodyfat_pct": None,
            "rhr_bpm": None,
            "hrv_ms": None,
            "raw": [],
        }
    )

    try:
        for data_type, records in payload.items():
            if not isinstance(records, list):
                continue

            for rec in records:
                if not isinstance(rec, dict):
                    continue

                dt = _parse_dt(rec.get("date"))
                if not dt:
                    continue

                d = dt.date()
                bucket = per_date[d]
                bucket["raw"].append({"type": data_type, **rec})

                value = rec.get("value")
                unit = rec.get("unit")
                t = data_type

                if t in ("BodyMass", "BodyMassIndex"):
                    kg = _to_kg(value, unit)
                    if kg is not None:
                        bucket["weight_kg"] = kg

                elif t in ("BodyFatPercentage",):
                    if isinstance(value, (int, float)):
                        bucket["bodyfat_pct"] = float(value)

                elif t in ("RestingHeartRate",):
                    if isinstance(value, (int, float)):
                        bucket["rhr_bpm"] = float(value)

                elif t in ("HeartRateVariabilitySDNN", "HeartRateVariabilityRMSSD"):
                    if isinstance(value, (int, float)):
                        bucket["hrv_ms"] = float(value)

        for d, data in per_date.items():
            row = (
                db.query(AppleHealthDaily)
                .filter(AppleHealthDaily.date == d)
                .one_or_none()
            )

            if row is None:
                row = AppleHealthDaily(date=d)
                db.add(row)

            if data["weight_kg"] is not None:
                row.weight_kg = data["weight_kg"]
            if data["bodyfat_pct"] is not None:
                row.bodyfat_pct = data["bodyfat_pct"]
            if data["rhr_bpm"] is not None:
                row.rhr_bpm = data["rhr_bpm"]
            if data["hrv_ms"] is not None:
                row.hrv_ms = data["hrv_ms"]

            row.raw_payload = data["raw"]

        db.commit()
        return {"status": "ok", "dates": [str(d) for d in per_date.keys()]}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Apple ingest failed: {e}")

    finally:
        db.close()