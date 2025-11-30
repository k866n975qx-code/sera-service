from datetime import date
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from app.models.apple import AppleHealthDaily
from app.models.whoop import WhoopDaily
from app.models.snapshot import SeraDailySnapshot


class Source(str, Enum):
    WHOOP = "whoop"
    APPLE = "apple"


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

# WHOOP is primary source for ALL metrics, Apple is fallback
METRIC_SOURCE_PRIORITY = {
    metric: [Source.WHOOP, Source.APPLE] for metric in _METRICS
}


def _get_value(
    src: Source,
    metric: str,
    apple: Optional[AppleHealthDaily],
    whoop: Optional[WhoopDaily],
):
    if src is Source.WHOOP:
        return getattr(whoop, metric, None) if whoop is not None else None
    else:
        return getattr(apple, metric, None) if apple is not None else None


def choose_metric(
    metric: str,
    apple: Optional[AppleHealthDaily],
    whoop: Optional[WhoopDaily],
):
    for src in METRIC_SOURCE_PRIORITY.get(metric, []):
        value = _get_value(src, metric, apple, whoop)
        if value is not None:
            return value
    return None


def merge_for_date(db: Session, d: date) -> Optional[SeraDailySnapshot]:
    """
    Merge Apple + WHOOP into SeraDailySnapshot for date d.

    WHOOP is always preferred when it has a value; Apple is fallback.
    """
    apple = (
        db.query(AppleHealthDaily)
        .filter(AppleHealthDaily.date == d)
        .one_or_none()
    )
    whoop = (
        db.query(WhoopDaily)
        .filter(WhoopDaily.date == d)
        .one_or_none()
    )

    if apple is None and whoop is None:
        return None

    values = {metric: choose_metric(metric, apple, whoop) for metric in _METRICS}

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

    snapshot.apple_health_id = apple.id if apple else None
    snapshot.whoop_id = whoop.id if whoop else None

    # readiness fields stay None for now
    return snapshot