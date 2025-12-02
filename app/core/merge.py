from datetime import date
from enum import Enum
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.whoop import WhoopDaily
from app.models.snapshot import SeraDailySnapshot
from app.models.renpho import RenphoWeightEntry


class Source(str, Enum):
    WHOOP = "whoop"
    RENPHO = "renpho"


# canonical metrics in SeraDailySnapshot
_METRICS = [
    "hrv_ms",
    "rhr_bpm",
    "sleep_hours",
    "sleep_efficiency_pct",
    "deep_sleep_pct",
    "rem_sleep_pct",
    "weight_kg",
    "bodyfat_pct",
    "hydration_pct",
    "recovery_score",
    "strain",
    "respiratory_rate",
    "spo2_pct",
]

# WHOOP is primary for most metrics.
# Renpho is primary source for scale-related metrics; WHOOP is fallback if present.
METRIC_SOURCE_PRIORITY = {
    "hrv_ms": [Source.WHOOP],
    "rhr_bpm": [Source.WHOOP],
    "sleep_hours": [Source.WHOOP],
    "sleep_efficiency_pct": [Source.WHOOP],
    "deep_sleep_pct": [Source.WHOOP],
    "rem_sleep_pct": [Source.WHOOP],
    "recovery_score": [Source.WHOOP],
    "strain": [Source.WHOOP],
    "respiratory_rate": [Source.WHOOP],
    "spo2_pct": [Source.WHOOP],
    # Scale-related metrics
    "weight_kg": [Source.RENPHO, Source.WHOOP],
    "bodyfat_pct": [Source.RENPHO, Source.WHOOP],
    "hydration_pct": [Source.RENPHO, Source.WHOOP],
}


def _get_value(
    src: Source,
    metric: str,
    renpho: Optional[RenphoWeightEntry],
    whoop: Optional[WhoopDaily],
):
    if src is Source.WHOOP:
        return getattr(whoop, metric, None) if whoop is not None else None

    if src is Source.RENPHO and renpho is not None:
        # Map snapshot metrics to RenphoWeightEntry fields
        if metric == "weight_kg":
            return renpho.weight_kg
        if metric == "bodyfat_pct":
            return renpho.body_fat_pct
        if metric == "hydration_pct":
            return renpho.water_pct

    return None


def choose_metric(
    metric: str,
    renpho: Optional[RenphoWeightEntry],
    whoop: Optional[WhoopDaily],
):
    for src in METRIC_SOURCE_PRIORITY.get(metric, []):
        value = _get_value(src, metric, renpho, whoop)
        if value is not None:
            return value
    return None


def merge_for_date(db: Session, d: date) -> Optional[SeraDailySnapshot]:
    """
    Merge WHOOP + Renpho into SeraDailySnapshot for date d.

    WHOOP is preferred for most metrics, Renpho is preferred for scale metrics.
    """
    # WHOOP daily summary row
    whoop = (
        db.query(WhoopDaily)
        .filter(WhoopDaily.date == d)
        .one_or_none()
    )

    # Renpho: pick the latest measurement on that date, if any
    renpho = (
        db.query(RenphoWeightEntry)
        .filter(func.date(RenphoWeightEntry.timestamp) == d)
        .order_by(RenphoWeightEntry.timestamp.desc())
        .first()
    )

    if renpho is None and whoop is None:
        return None

    values = {metric: choose_metric(metric, renpho, whoop) for metric in _METRICS}

    snapshot = (
        db.query(SeraDailySnapshot)
        .filter(SeraDailySnapshot.date == d)
        .one_or_none()
    )

    if snapshot is None:
        snapshot = SeraDailySnapshot(date=d)
        db.add(snapshot)

    snapshot.hrv_ms = values["hrv_ms"]
    snapshot.rhr_bpm = values["rhr_bpm"]
    snapshot.sleep_hours = values["sleep_hours"]
    snapshot.sleep_efficiency_pct = values["sleep_efficiency_pct"]
    snapshot.deep_sleep_pct = values["deep_sleep_pct"]
    snapshot.rem_sleep_pct = values["rem_sleep_pct"]
    snapshot.weight_kg = values["weight_kg"]
    snapshot.bodyfat_pct = values["bodyfat_pct"]
    snapshot.hydration_pct = values["hydration_pct"]
    snapshot.recovery_score = values["recovery_score"]
    snapshot.strain = values["strain"]  
    snapshot.respiratory_rate = values["respiratory_rate"]
    snapshot.spo2_pct = values["spo2_pct"]

    # We no longer track Apple Health at all; clear any legacy linkage if present.
    if hasattr(snapshot, "apple_health_id"):
        snapshot.apple_health_id = None

    snapshot.whoop_id = whoop.id if whoop else None

    # readiness fields stay None for now
    return snapshot