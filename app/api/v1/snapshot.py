from datetime import date as DateType, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, engine
from app.core.merge import merge_for_date
from app.models.snapshot import SeraDailySnapshot

router = APIRouter(tags=["snapshot"])


class SnapshotOut(BaseModel):
    date: str
    weight_lb: float | None
    bodyfat_pct: float | None
    hrv_ms: float | None
    rhr_bpm: float | None
    sleep_hours: float | None
    sleep_efficiency_pct: float | None
    deep_sleep_pct: float | None
    rem_sleep_pct: float | None
    sleep_consistency_pct: float | None
    sleep_disturbance_count: int | None
    hydration_pct: float | None
    recovery_score: int | None
    strain: float | None
    respiratory_rate: float | None
    spo2_pct: float | None


def kg_to_lb(kg: float | None) -> float | None:
    if kg is None:
        return None
    return round(kg * 2.20462, 1)


# Prefer the stored weight_lb on the snapshot; fall back to converting from kg if needed.
def _resolve_weight_lb(snap: SeraDailySnapshot) -> float | None:
    """
    Prefer the stored weight_lb on the snapshot; fall back to converting from kg if needed.
    """
    if getattr(snap, "weight_lb", None) is not None:
        return round(snap.weight_lb, 1)
    return kg_to_lb(snap.weight_kg)



@router.get("/snapshot/latest", response_model=SnapshotOut)
def get_latest_snapshot():
    if not engine or not SessionLocal:
        raise HTTPException(503, "DB not configured")

    db: Session = SessionLocal()
    try:
        snap = (
            db.query(SeraDailySnapshot)
            .order_by(SeraDailySnapshot.date.desc())
            .first()
        )
        if not snap:
            raise HTTPException(404, "No snapshot available")

        # Re-run merge_for_date to ensure WHOOP + body metrics are up-to-date for that day
        merged = merge_for_date(db, snap.date) or snap
        db.commit()
        db.refresh(merged)

        return SnapshotOut(
            date=merged.date.isoformat(),
            weight_lb=_resolve_weight_lb(merged),
            bodyfat_pct=merged.bodyfat_pct,
            hrv_ms=merged.hrv_ms,
            rhr_bpm=merged.rhr_bpm,
            sleep_hours=merged.sleep_hours,
            sleep_efficiency_pct=merged.sleep_efficiency_pct,
            deep_sleep_pct=merged.deep_sleep_pct,
            rem_sleep_pct=merged.rem_sleep_pct,
            sleep_consistency_pct=merged.sleep_consistency_pct,
            sleep_disturbance_count=merged.sleep_disturbance_count,
            hydration_pct=merged.hydration_pct,
            recovery_score=merged.recovery_score,
            strain=merged.strain,
            respiratory_rate=merged.respiratory_rate,
            spo2_pct=merged.spo2_pct,
        )
    finally:
        db.close()


# New endpoint: get snapshot by date with merge_for_date
@router.get("/snapshot/daily/{date}", response_model=SnapshotOut)
def get_snapshot_by_date(date: str):
    if not engine or not SessionLocal:
        raise HTTPException(503, "DB not configured")

    try:
        d = DateType.fromisoformat(date)
    except ValueError:
        raise HTTPException(400, f"Invalid date format: {date}, expected YYYY-MM-DD")

    db: Session = SessionLocal()
    try:
        snap = merge_for_date(db, d)
        if not snap:
            raise HTTPException(404, f"No data available to build snapshot for {date}")

        db.commit()
        db.refresh(snap)

        return SnapshotOut(
            date=snap.date.isoformat(),
            weight_lb=_resolve_weight_lb(snap),
            bodyfat_pct=snap.bodyfat_pct,
            hrv_ms=snap.hrv_ms,
            rhr_bpm=snap.rhr_bpm,
            sleep_hours=snap.sleep_hours,
            sleep_efficiency_pct=snap.sleep_efficiency_pct,
            deep_sleep_pct=snap.deep_sleep_pct,
            rem_sleep_pct=snap.rem_sleep_pct,
            sleep_consistency_pct=snap.sleep_consistency_pct,
            sleep_disturbance_count=snap.sleep_disturbance_count,
            hydration_pct=snap.hydration_pct,
            recovery_score=snap.recovery_score,
            strain=snap.strain,
            respiratory_rate=snap.respiratory_rate,
            spo2_pct=snap.spo2_pct,
        )
    finally:
        db.close()


# ----- Readiness computation helpers -----

def _avg(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _format_trend(pct: float | None) -> str:
    if pct is None:
        return "n/a"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{round(pct, 1)}%"


def _build_health_snapshot(
    snap: SeraDailySnapshot,
    hrv_trend_pct: float | None,
    sleep_trend_pct: float | None,
) -> str:
    weight_lb = _resolve_weight_lb(snap)
    bf = snap.bodyfat_pct
    hrv = snap.hrv_ms
    rhr = snap.rhr_bpm
    sleep_h = snap.sleep_hours
    eff = snap.sleep_efficiency_pct
    readiness_index = snap.readiness_index
    readiness_zone = snap.readiness_zone

    hrv_trend_str = _format_trend(hrv_trend_pct)
    sleep_trend_str = _format_trend(sleep_trend_pct)

    return (
        f"HEALTH SNAPSHOT — {snap.date.isoformat()}\n"
        f"• Weight: {weight_lb if weight_lb is not None else 'n/a'} lb"
        f" | BF: {round(bf, 1) if bf is not None else 'n/a'}%\n"
        f"• HRV: {round(hrv, 1) if hrv is not None else 'n/a'} ms"
        f" | RHR: {round(rhr, 1) if rhr is not None else 'n/a'} bpm\n"
        f"• Sleep: {round(sleep_h, 2) if sleep_h is not None else 'n/a'}h"
        f" (Eff {round(eff, 1) if eff is not None else 'n/a'}%)\n"
        f"• Readiness: {readiness_index if readiness_index is not None else 'n/a'}/100"
        f" ({readiness_zone if readiness_zone is not None else 'n/a'})\n"
        f"• Trend: HRV {hrv_trend_str}, Sleep {sleep_trend_str}"
    )


def compute_readiness_for_date(db: Session, d: DateType) -> SeraDailySnapshot | None:
    """
    Compute and persist SERA readiness metrics for a given date based on SeraDailySnapshot
    and previous 7 days' history.

    Rules (v1.3):
    - Flags:
      * hrv_low: today's HRV < 7-day baseline
      * sleep_debt: sleep debt > 1 hour (target 8.0h for v1)
      * recovery_low: recovery_score < 70
    - Zone:
      * 0 flags -> green
      * 1 flag  -> yellow
      * 2+ flags -> red
    - Readiness index:
      * Base on recovery_score (0-100) plus HRV and sleep components.
    """
    snap = (
        db.query(SeraDailySnapshot)
        .filter(SeraDailySnapshot.date == d)
        .one_or_none()
    )
    if not snap:
        return None

    # Look back 7 days for baselines (but not including today)
    start = d - timedelta(days=7)
    history = (
        db.query(SeraDailySnapshot)
        .filter(SeraDailySnapshot.date >= start)
        .filter(SeraDailySnapshot.date < d)
        .order_by(SeraDailySnapshot.date.asc())
        .all()
    )

    hrv_baseline = _avg([s.hrv_ms for s in history])
    sleep_baseline = _avg([s.sleep_hours for s in history])
    strain_baseline = _avg([s.strain for s in history])
    recovery_baseline = _avg(
        [float(s.recovery_score) if s.recovery_score is not None else None for s in history]
    )

    flags: list[str] = []

    # HRV flag
    if snap.hrv_ms is not None and hrv_baseline is not None:
        if snap.hrv_ms < hrv_baseline:
            flags.append("hrv_low")

    # Sleep debt flag (target 8h for v1)
    sleep_target = 8.0
    sleep_debt: float | None = None
    if snap.sleep_hours is not None:
        sleep_debt = max(0.0, sleep_target - snap.sleep_hours)
        if sleep_debt > 1.0:
            flags.append("sleep_debt")

    # Recovery flag
    if snap.recovery_score is not None and snap.recovery_score < 70:
        flags.append("recovery_low")

    # Zone
    if len(flags) >= 2:
        zone = "red"
    elif len(flags) == 1:
        zone = "yellow"
    else:
        zone = "green"

    # Trends (% vs 7-day baseline)
    hrv_trend_pct: float | None = None
    if snap.hrv_ms is not None and hrv_baseline not in (None, 0):
        hrv_trend_pct = ((snap.hrv_ms - hrv_baseline) / hrv_baseline) * 100.0

    sleep_trend_pct: float | None = None
    if snap.sleep_hours is not None and sleep_baseline not in (None, 0):
        sleep_trend_pct = ((snap.sleep_hours - sleep_baseline) / sleep_baseline) * 100.0

    # Components for readiness index
    recovery_component = float(snap.recovery_score or 0.0)

    if snap.hrv_ms is not None and hrv_baseline:
        hrv_ratio = snap.hrv_ms / hrv_baseline
        hrv_component = max(0.0, min(hrv_ratio * 100.0, 120.0))
    else:
        hrv_component = recovery_component

    if snap.sleep_hours is not None:
        sleep_ratio = snap.sleep_hours / sleep_target
        sleep_component = max(0.0, min(sleep_ratio * 100.0, 120.0))
    else:
        sleep_component = recovery_component

    readiness_index = int(
        max(0.0, min(0.6 * recovery_component + 0.2 * hrv_component + 0.2 * sleep_component, 100.0))
    )

    # Signal scores (0-120 scaled then clamped to int)
    hrv_signal_score: int | None = None
    if hrv_component is not None:
        hrv_signal_score = int(round(hrv_component))

    sleep_signal_score: int | None = None
    if sleep_component is not None:
        sleep_signal_score = int(round(sleep_component))

    recovery_signal_score: int | None = None
    if snap.recovery_score is not None:
        recovery_signal_score = int(snap.recovery_score)

    # Insight text
    insight_bits: list[str] = []
    if "hrv_low" in flags:
        insight_bits.append("HRV below 7-day baseline")
    if "sleep_debt" in flags:
        insight_bits.append("sleep debt > 1h (target 8h)")
    if "recovery_low" in flags:
        insight_bits.append("recovery score < 70")

    insight = "; ".join(insight_bits) if insight_bits else "All primary signals within normal range."

    # Persist into snapshot
    snap.readiness_index = readiness_index
    snap.readiness_zone = zone
    snap.flags = {
        "flags": flags,
        "sleep_debt_hours": sleep_debt,
        "hrv_baseline": hrv_baseline,
        "sleep_baseline": sleep_baseline,
        "strain_baseline": strain_baseline,
        "recovery_baseline": recovery_baseline,
        "hrv_trend_pct": hrv_trend_pct,
        "sleep_trend_pct": sleep_trend_pct,
        "signal_scores": {
            "hrv": hrv_signal_score,
            "sleep": sleep_signal_score,
            "recovery": recovery_signal_score,
        },
    }
    snap.insight = insight

    db.commit()
    db.refresh(snap)
    return snap


class ReadinessOut(BaseModel):
    date: str
    readiness_index: int | None
    readiness_zone: str | None
    flags: dict | None
    insight: str | None

    # Raw metrics
    hrv_ms: float | None
    sleep_hours: float | None
    recovery_score: int | None
    strain: float | None

    # Rolling averages (7-day)
    hrv_7d_avg: float | None = None
    sleep_7d_avg: float | None = None
    strain_7d_avg: float | None = None
    recovery_7d_avg: float | None = None

    # Signal scores
    hrv_signal_score: int | None = None
    sleep_signal_score: int | None = None
    recovery_signal_score: int | None = None

    # Derived / presentation
    sleep_debt_hours: float | None = None
    health_snapshot: str | None = None


def _ensure_db():
    if not engine or not SessionLocal:
        raise HTTPException(503, "DB not configured")


@router.get("/readiness/by-date/{date}", response_model=ReadinessOut)
def get_readiness_for_date(date: str):
    _ensure_db()

    try:
        d = DateType.fromisoformat(date)
    except ValueError:
        raise HTTPException(400, f"Invalid date format: {date}, expected YYYY-MM-DD")

    db: Session = SessionLocal()
    try:
        snap = compute_readiness_for_date(db, d)
        if not snap:
            raise HTTPException(404, f"No snapshot for {date}")

        flags = snap.flags or {}
        hrv_baseline = None
        sleep_baseline = None
        strain_baseline = None
        recovery_baseline = None
        hrv_trend_pct = None
        sleep_trend_pct = None
        sleep_debt_hours = None
        hrv_signal_score = None
        sleep_signal_score = None
        recovery_signal_score = None

        if isinstance(flags, dict):
            hrv_baseline = flags.get("hrv_baseline")
            sleep_baseline = flags.get("sleep_baseline")
            strain_baseline = flags.get("strain_baseline")
            recovery_baseline = flags.get("recovery_baseline")
            hrv_trend_pct = flags.get("hrv_trend_pct")
            sleep_trend_pct = flags.get("sleep_trend_pct")
            sleep_debt_hours = flags.get("sleep_debt_hours")
            signal_scores = flags.get("signal_scores") or {}
            if isinstance(signal_scores, dict):
                hrv_signal_score = signal_scores.get("hrv")
                sleep_signal_score = signal_scores.get("sleep")
                recovery_signal_score = signal_scores.get("recovery")

        health_snapshot = _build_health_snapshot(snap, hrv_trend_pct, sleep_trend_pct)

        return ReadinessOut(
            date=snap.date.isoformat(),
            readiness_index=snap.readiness_index,
            readiness_zone=snap.readiness_zone,
            flags=flags,
            insight=snap.insight,
            hrv_ms=snap.hrv_ms,
            sleep_hours=snap.sleep_hours,
            recovery_score=snap.recovery_score,
            strain=snap.strain,
            hrv_7d_avg=hrv_baseline,
            sleep_7d_avg=sleep_baseline,
            strain_7d_avg=strain_baseline,
            recovery_7d_avg=recovery_baseline,
            hrv_signal_score=hrv_signal_score,
            sleep_signal_score=sleep_signal_score,
            recovery_signal_score=recovery_signal_score,
            sleep_debt_hours=sleep_debt_hours,
            health_snapshot=health_snapshot,
        )
    finally:
        db.close()


@router.get("/readiness/latest", response_model=ReadinessOut)
def get_readiness_latest():
    _ensure_db()

    db: Session = SessionLocal()
    try:
        snap = (
            db.query(SeraDailySnapshot)
            .order_by(SeraDailySnapshot.date.desc())
            .first()
        )
        if not snap:
            raise HTTPException(404, "No snapshot available")

        snap = compute_readiness_for_date(db, snap.date)
        if not snap:
            raise HTTPException(404, "No snapshot after readiness compute")

        flags = snap.flags or {}
        hrv_baseline = None
        sleep_baseline = None
        strain_baseline = None
        recovery_baseline = None
        hrv_trend_pct = None
        sleep_trend_pct = None
        sleep_debt_hours = None
        hrv_signal_score = None
        sleep_signal_score = None
        recovery_signal_score = None

        if isinstance(flags, dict):
            hrv_baseline = flags.get("hrv_baseline")
            sleep_baseline = flags.get("sleep_baseline")
            strain_baseline = flags.get("strain_baseline")
            recovery_baseline = flags.get("recovery_baseline")
            hrv_trend_pct = flags.get("hrv_trend_pct")
            sleep_trend_pct = flags.get("sleep_trend_pct")
            sleep_debt_hours = flags.get("sleep_debt_hours")
            signal_scores = flags.get("signal_scores") or {}
            if isinstance(signal_scores, dict):
                hrv_signal_score = signal_scores.get("hrv")
                sleep_signal_score = signal_scores.get("sleep")
                recovery_signal_score = signal_scores.get("recovery")

        health_snapshot = _build_health_snapshot(snap, hrv_trend_pct, sleep_trend_pct)

        return ReadinessOut(
            date=snap.date.isoformat(),
            readiness_index=snap.readiness_index,
            readiness_zone=snap.readiness_zone,
            flags=flags,
            insight=snap.insight,
            hrv_ms=snap.hrv_ms,
            sleep_hours=snap.sleep_hours,
            recovery_score=snap.recovery_score,
            strain=snap.strain,
            hrv_7d_avg=hrv_baseline,
            sleep_7d_avg=sleep_baseline,
            strain_7d_avg=strain_baseline,
            recovery_7d_avg=recovery_baseline,
            hrv_signal_score=hrv_signal_score,
            sleep_signal_score=sleep_signal_score,
            recovery_signal_score=recovery_signal_score,
            sleep_debt_hours=sleep_debt_hours,
            health_snapshot=health_snapshot,
        )
    finally:
        db.close()