from datetime import date
from enum import Enum
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.whoop import WhoopDaily
from app.models.snapshot import SeraDailySnapshot
from app.models.body_metrics import BodyMetricsEntry


class Source(str, Enum):
    WHOOP = "whoop"
    BODY = "body"


# canonical metrics in SeraDailySnapshot
_METRICS = [
    "hrv_ms",
    "rhr_bpm",
    "sleep_hours",
    "sleep_efficiency_pct",
    "deep_sleep_pct",
    "rem_sleep_pct",
    "sleep_consistency_pct",
    "sleep_disturbance_count",
    "weight_kg",
    "weight_lb",
    "bodyfat_pct",
    "hydration_pct",
    "recovery_score",
    "strain",
    "respiratory_rate",
    "spo2_pct",
]

# WHOOP is primary for most metrics.
# Body metrics (scale) are primary for weight/bodyfat/hydration; WHOOP is fallback if present.
METRIC_SOURCE_PRIORITY = {
    "hrv_ms": [Source.WHOOP],
    "rhr_bpm": [Source.WHOOP],
    "sleep_hours": [Source.WHOOP],
    "sleep_efficiency_pct": [Source.WHOOP],
    "deep_sleep_pct": [Source.WHOOP],
    "rem_sleep_pct": [Source.WHOOP],
    "sleep_consistency_pct": [Source.WHOOP],
    "sleep_disturbance_count": [Source.WHOOP],
    "recovery_score": [Source.WHOOP],
    "strain": [Source.WHOOP],
    "respiratory_rate": [Source.WHOOP],
    "spo2_pct": [Source.WHOOP],
    # Scale-related metrics
    "weight_kg": [Source.BODY, Source.WHOOP],
    "weight_lb": [Source.BODY, Source.WHOOP],
    "bodyfat_pct": [Source.BODY, Source.WHOOP],
    "hydration_pct": [Source.BODY, Source.WHOOP],
}


def _get_value(
    src: Source,
    metric: str,
    body: Optional[BodyMetricsEntry],
    whoop: Optional[WhoopDaily],
):
    if src is Source.WHOOP:
        if whoop is None:
            return None

        # derive percentages from minutes + total sleep hours
        if metric in ("deep_sleep_pct", "rem_sleep_pct"):
            if whoop.sleep_hours and whoop.sleep_hours > 0:
                total_min = whoop.sleep_hours * 60.0
                if metric == "deep_sleep_pct" and getattr(whoop, "deep_sleep_min", None) is not None:
                    return (whoop.deep_sleep_min / total_min) * 100.0
                if metric == "rem_sleep_pct" and getattr(whoop, "rem_sleep_min", None) is not None:
                    return (whoop.rem_sleep_min / total_min) * 100.0
                return None

        # derive weight_lb from any WHOOP-side weight_kg if present
        if metric == "weight_lb":
            kg = getattr(whoop, "weight_kg", None)
            if kg is not None:
                return kg * 2.20462

        return getattr(whoop, metric, None)

    if src is Source.BODY and body is not None:
        # Map snapshot metrics to BodyMetricsEntry fields
        if metric == "weight_kg":
            return body.weight_kg
        if metric == "weight_lb":
            if getattr(body, "weight_lb", None) is not None:
                return body.weight_lb
            if body.weight_kg is not None:
                return body.weight_kg * 2.20462
            return None
        if metric == "bodyfat_pct":
            return body.body_fat_pct
        if metric == "hydration_pct":
            return body.body_water_pct

    return None


def choose_metric(
    metric: str,
    body: Optional[BodyMetricsEntry],
    whoop: Optional[WhoopDaily],
):
    for src in METRIC_SOURCE_PRIORITY.get(metric, []):
        value = _get_value(src, metric, body, whoop)
        if value is not None:
            return value
    return None


def merge_for_date(db: Session, d: date) -> Optional[SeraDailySnapshot]:
    """
    Merge WHOOP + body metrics into SeraDailySnapshot for date d.

    WHOOP is preferred for readiness/sleep/strain metrics.
    Body metrics are preferred for scale-related metrics (weight, fat %, hydration).
    """
    # WHOOP daily summary row
    whoop = (
        db.query(WhoopDaily)
        .filter(WhoopDaily.date == d)
        .one_or_none()
    )

    # Body metrics: pick the latest measurement on that date, if any
    body = (
        db.query(BodyMetricsEntry)
        .filter(BodyMetricsEntry.date == d)
        .order_by(BodyMetricsEntry.timestamp.desc())
        .first()
    )

    if body is None and whoop is None:
        return None

    values = {metric: choose_metric(metric, body, whoop) for metric in _METRICS}

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
    snapshot.sleep_consistency_pct = values["sleep_consistency_pct"]
    snapshot.sleep_disturbance_count = values["sleep_disturbance_count"]
    snapshot.weight_kg = values["weight_kg"]
    snapshot.weight_lb = values["weight_lb"]
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