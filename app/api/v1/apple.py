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


@router.post("/v1/apple-health")
async def apple_health(payload: Dict[str, Any]):
    return {"status": "ok"}