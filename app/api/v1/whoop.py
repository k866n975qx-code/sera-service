from datetime import date as DateType, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, engine
from app.core.merge import merge_for_date
from app.core.config import settings
from app.models.whoop import (
    WhoopDaily,
    WhoopRecoveryDaily,
    WhoopCycleDaily,
    WhoopSleepActivity,
    WhoopWorkout,
    WhoopBodyMeasurement,
    WhoopUserProfile,
)
from pathlib import Path
import json
import httpx



router = APIRouter(tags=["whoop"])

CREDENTIALS_DEFAULT_PATH = "/home/jose/mywhoop/credentials.json"

def _load_access_token_from_credentials() -> str:
    """
    Load the current WHOOP access_token from the MyWhoop credentials.json file.

    MyWhoop runs as a separate Docker service and is responsible for handling
    OAuth and token refresh. SERA just reads the latest access_token from disk.
    """
    # Allow override via environment (through Settings) but fall back to the
    # known Ubuntu path where the mywhoop volume is mounted.
    credentials_path = getattr(
        settings,
        "WHOOP_CREDENTIALS_PATH",
        None,
    ) or CREDENTIALS_DEFAULT_PATH

    p = Path(credentials_path)

    if not p.exists():
        raise HTTPException(
            status_code=500,
            detail=f"WHOOP credentials file not found at {credentials_path}",
        )

    try:
        data = json.loads(p.read_text())
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read WHOOP credentials: {e}",
        )

    token = data.get("access_token")
    if not token:
        raise HTTPException(
            status_code=500,
            detail="WHOOP credentials file is missing 'access_token'",
        )

    return token


class WhoopIn(BaseModel):
    date: str
    recovery_score: int | None = None
    hrv_ms: float | None = None
    rhr_bpm: float | None = None
    respiratory_rate: float | None = None
    sleep_hours: float | None = None
    sleep_efficiency_pct: float | None = None
    deep_sleep_min: float | None = None
    rem_sleep_min: float | None = None
    strain: float | None = None
    avg_hr_day: float | None = None
    avg_hr_sleep: float | None = None
    spo2_pct: float | None = None
    raw_payload: dict | None = None


def _ensure_db():
    if not engine or not SessionLocal:
        raise HTTPException(503, "DB not configured (POSTGRES_DSN missing)")


def _parse_iso8601(dt_str: str | None) -> datetime | None:
    if not dt_str or not isinstance(dt_str, str):
        return None
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


@router.post("/whoop")
def ingest_whoop(payload: WhoopIn):
    """
    Manual ingest endpoint – still writes into the legacy WhoopDaily table
    and triggers merge_for_date. Kept for backwards-compat tooling.
    """
    _ensure_db()
    db: Session = SessionLocal()
    try:
        d = DateType.fromisoformat(payload.date)
        data = payload.dict(exclude={"date"})

        existing = db.query(WhoopDaily).filter(WhoopDaily.date == d).one_or_none()

        if existing:
            for field, value in data.items():
                setattr(existing, field, value)
        else:
            row = WhoopDaily(date=d, **data)
            db.add(row)

        # WHOOP-primary/Apple-fallback merge for this date
        merge_for_date(db, d)

        db.commit()
    finally:
        db.close()

    return {"status": "ok", "date": payload.date}


@router.get("/whoop/import/daily")
def import_whoop_daily(date: str):
    """
    Import WHOOP data for a single calendar date (UTC) into the warehouse-style
    tables (recovery, sleep, cycle, workouts) AND the legacy WhoopDaily summary,
    then trigger SERA merge for that date.
    """
    _ensure_db()

    # parse date string
    try:
        d = DateType.fromisoformat(date)
    except ValueError:
        raise HTTPException(400, f"Invalid date format: {date}, expected YYYY-MM-DD")

    # build WHOOP time window for that date in UTC
    start_dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)
    start_iso = start_dt.isoformat().replace("+00:00", "Z")
    end_iso = end_dt.isoformat().replace("+00:00", "Z")

    db: Session = SessionLocal()
    try:
        # Load WHOOP access token from MyWhoop credentials.json
        access_token = _load_access_token_from_credentials()

        # ---------- RECOVERY ----------
        recovery_url = f"{settings.WHOOP_API_BASE}/developer/v2/recovery"
        with httpx.Client(timeout=10.0) as client:
            recovery_resp = client.get(
                recovery_url,
                params={"start": start_iso, "end": end_iso},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if recovery_resp.status_code != 200:
            raise HTTPException(
                status_code=recovery_resp.status_code,
                detail=f"WHOOP recovery fetch failed: {recovery_resp.text}",
            )

        recovery_data: Any = recovery_resp.json()
        recovery_records = (
            recovery_data
            if isinstance(recovery_data, list)
            else recovery_data.get("records")
            or recovery_data.get("recovery")
            or []
        )

        rec = recovery_records[0] if recovery_records else None

        recovery_score: int | None = None
        hrv_ms: float | None = None
        rhr_bpm: float | None = None
        respiratory_rate: float | None = None
        spo2_pct: float | None = None

        if rec and isinstance(rec, dict):
            score = rec.get("score") or {}
            if isinstance(score, dict):
                rs = score.get("recovery_score")
                recovery_score = int(rs) if isinstance(rs, (int, float)) else None

                hrv_val = score.get("hrv_rmssd_milli")
                hrv_ms = float(hrv_val) if isinstance(hrv_val, (int, float)) else None

                rhr_val = score.get("resting_heart_rate")
                rhr_bpm = float(rhr_val) if isinstance(rhr_val, (int, float)) else None

                spo2_val = score.get("spo2_percentage")
                spo2_pct = float(spo2_val) if isinstance(spo2_val, (int, float)) else None

            # upsert into WhoopRecoveryDaily
            recovery_row = (
                db.query(WhoopRecoveryDaily)
                .filter(WhoopRecoveryDaily.date == d)
                .one_or_none()
            )
            if recovery_row is None:
                recovery_row = WhoopRecoveryDaily(date=d)
                db.add(recovery_row)

            recovery_row.cycle_id = rec.get("cycle_id")
            recovery_row.sleep_id = rec.get("sleep_id")
            recovery_row.user_id = rec.get("user_id")
            recovery_row.recovery_score = recovery_score
            recovery_row.resting_heart_rate = rhr_bpm
            recovery_row.hrv_rmssd_milli = hrv_ms
            recovery_row.spo2_percentage = spo2_pct
            recovery_row.skin_temp_celsius = (
                score.get("skin_temp_celsius") if isinstance(score, dict) else None
            )
            recovery_row.user_calibrating = (
                score.get("user_calibrating") if isinstance(score, dict) else None
            )
            recovery_row.api_created_at = _parse_iso8601(rec.get("created_at"))
            recovery_row.api_updated_at = _parse_iso8601(rec.get("updated_at"))
            recovery_row.raw_payload = rec

        # ---------- SLEEP ----------
        sleep_hours: float | None = None
        sleep_status: int | None = None
        sleep_raw: Any | None = None

        sleep_url = f"{settings.WHOOP_API_BASE}/developer/v2/activity/sleep"
        with httpx.Client(timeout=10.0) as client:
            sleep_resp = client.get(
                sleep_url,
                params={"start": start_iso, "end": end_iso},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        sleep_status = sleep_resp.status_code
        if sleep_resp.status_code == 200:
            try:
                sleep_data: Any = sleep_resp.json()
            except Exception:
                sleep_data = None

            sleep_raw = sleep_data
            sleep_records = (
                sleep_data
                if isinstance(sleep_data, list)
                else sleep_data.get("records")
                or sleep_data.get("sleep")
                if isinstance(sleep_data, dict)
                else []
            )

            total_in_bed_ms = 0.0
            if sleep_records:
                for srec in sleep_records:
                    if not isinstance(srec, dict):
                        continue
                    score_block = srec.get("score") or {}
                    if not isinstance(score_block, dict):
                        continue
                    stage_summary = score_block.get("stage_summary") or {}
                    if not isinstance(stage_summary, dict):
                        continue

                    ms_val = stage_summary.get("total_in_bed_time_milli")
                    if isinstance(ms_val, (int, float)):
                        total_in_bed_ms += ms_val

                    # upsert into WhoopSleepActivity
                    sleep_id = srec.get("id")
                    if not sleep_id:
                        continue

                    sleep_row = (
                        db.query(WhoopSleepActivity)
                        .filter(WhoopSleepActivity.sleep_id == sleep_id)
                        .one_or_none()
                    )
                    if sleep_row is None:
                        sleep_row = WhoopSleepActivity(
                            sleep_id=sleep_id,
                            date=d,
                        )
                        db.add(sleep_row)

                    sleep_row.cycle_id = srec.get("cycle_id")
                    sleep_row.user_id = srec.get("user_id")
                    sleep_row.start = _parse_iso8601(srec.get("start"))
                    sleep_row.end = _parse_iso8601(srec.get("end"))
                    sleep_row.timezone_offset = srec.get("timezone_offset")
                    sleep_row.nap = srec.get("nap")
                    sleep_row.score_state = srec.get("score_state")

                    sleep_row.total_in_bed_time_milli = stage_summary.get(
                        "total_in_bed_time_milli"
                    )
                    sleep_row.total_awake_time_milli = stage_summary.get(
                        "total_awake_time_milli"
                    )
                    sleep_row.total_no_data_time_milli = stage_summary.get(
                        "total_no_data_time_milli"
                    )
                    sleep_row.total_light_sleep_time_milli = stage_summary.get(
                        "total_light_sleep_time_milli"
                    )
                    sleep_row.total_slow_wave_sleep_time_milli = stage_summary.get(
                        "total_slow_wave_sleep_time_milli"
                    )
                    sleep_row.total_rem_sleep_time_milli = stage_summary.get(
                        "total_rem_sleep_time_milli"
                    )
                    sleep_row.sleep_cycle_count = stage_summary.get(
                        "sleep_cycle_count"
                    )
                    sleep_row.disturbance_count = stage_summary.get(
                        "disturbance_count"
                    )

                    sleep_row.respiratory_rate = score_block.get("respiratory_rate")
                    sleep_row.sleep_performance_percentage = score_block.get(
                        "sleep_performance_percentage"
                    )
                    sleep_row.sleep_consistency_percentage = score_block.get(
                        "sleep_consistency_percentage"
                    )
                    sleep_row.sleep_efficiency_percentage = score_block.get(
                        "sleep_efficiency_percentage"
                    )

                    sleep_row.api_created_at = _parse_iso8601(srec.get("created_at"))
                    sleep_row.api_updated_at = _parse_iso8601(srec.get("updated_at"))
                    sleep_row.raw_payload = srec

                if total_in_bed_ms > 0:
                    sleep_hours = round(total_in_bed_ms / 1000.0 / 3600.0, 2)
        else:
            try:
                sleep_raw = sleep_resp.json()
            except Exception:
                sleep_raw = sleep_resp.text

        # ---------- CYCLES / STRAIN ----------
        strain: float | None = None
        cycle_status: int | None = None
        cycle_raw: Any | None = None

        cycle_url = f"{settings.WHOOP_API_BASE}/developer/v2/cycle"
        with httpx.Client(timeout=10.0) as client:
            cycle_resp = client.get(
                cycle_url,
                params={"start": start_iso, "end": end_iso},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        cycle_status = cycle_resp.status_code
        if cycle_resp.status_code == 200:
            try:
                cycle_data: Any = cycle_resp.json()
            except Exception:
                cycle_data = None

            cycle_raw = cycle_data
            cycle_records = (
                cycle_data
                if isinstance(cycle_data, list)
                else cycle_data.get("records")
                or cycle_data.get("cycle")
                if isinstance(cycle_data, dict)
                else []
            )

            max_strain: float | None = None
            if cycle_records:
                for crec in cycle_records:
                    if not isinstance(crec, dict):
                        continue

                    score_block = crec.get("score") or {}
                    if not isinstance(score_block, dict):
                        score_block = {}

                    s_val = score_block.get("strain")
                    if isinstance(s_val, (int, float)):
                        if max_strain is None or s_val > max_strain:
                            max_strain = float(s_val)

                    # upsert into WhoopCycleDaily
                    cycle_id_val = crec.get("id")
                    if not cycle_id_val:
                        continue

                    cycle_row = (
                        db.query(WhoopCycleDaily)
                        .filter(
                            WhoopCycleDaily.date == d,
                            WhoopCycleDaily.cycle_id == cycle_id_val,
                        )
                        .one_or_none()
                    )
                    if cycle_row is None:
                        cycle_row = WhoopCycleDaily(
                            date=d,
                            cycle_id=cycle_id_val,
                        )
                        db.add(cycle_row)

                    cycle_row.user_id = crec.get("user_id")
                    cycle_row.start = _parse_iso8601(crec.get("start"))
                    cycle_row.end = _parse_iso8601(crec.get("end"))
                    cycle_row.timezone_offset = crec.get("timezone_offset")
                    cycle_row.score_state = crec.get("score_state")

                    kj = score_block.get("kilojoule")
                    cycle_row.kilojoule = float(kj) if isinstance(kj, (int, float)) else None

                    ah = score_block.get("average_heart_rate")
                    cycle_row.average_heart_rate = (
                        float(ah) if isinstance(ah, (int, float)) else None
                    )

                    mh = score_block.get("max_heart_rate")
                    cycle_row.max_heart_rate = (
                        float(mh) if isinstance(mh, (int, float)) else None
                    )

                    cycle_row.strain = (
                        float(s_val) if isinstance(s_val, (int, float)) else None
                    )

                    cycle_row.api_created_at = _parse_iso8601(crec.get("created_at"))
                    cycle_row.api_updated_at = _parse_iso8601(crec.get("updated_at"))
                    cycle_row.raw_payload = crec

            if max_strain is not None:
                strain = max_strain
        else:
            try:
                cycle_raw = cycle_resp.json()
            except Exception:
                cycle_raw = cycle_resp.text

        # ---------- WORKOUTS ----------
        workout_url = f"{settings.WHOOP_API_BASE}/developer/v2/activity/workout"
        workout_status: int | None = None
        workout_raw: Any | None = None

        with httpx.Client(timeout=10.0) as client:
            workout_resp = client.get(
                workout_url,
                params={"start": start_iso, "end": end_iso},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        workout_status = workout_resp.status_code
        if workout_resp.status_code == 200:
            try:
                workout_data: Any = workout_resp.json()
            except Exception:
                workout_data = None

            workout_raw = workout_data
            workout_records = (
                workout_data
                if isinstance(workout_data, list)
                else workout_data.get("records")
                or workout_data.get("workout")
                if isinstance(workout_data, dict)
                else []
            )

            if workout_records:
                for wrec in workout_records:
                    if not isinstance(wrec, dict):
                        continue

                    workout_id = wrec.get("id")
                    if not workout_id:
                        continue

                    workout_row = (
                        db.query(WhoopWorkout)
                        .filter(WhoopWorkout.workout_id == workout_id)
                        .one_or_none()
                    )
                    if workout_row is None:
                        workout_row = WhoopWorkout(
                            workout_id=workout_id,
                            date=d,
                        )
                        db.add(workout_row)

                    workout_row.user_id = wrec.get("user_id")
                    workout_row.sport_name = wrec.get("sport_name")
                    workout_row.score_state = wrec.get("score_state")
                    workout_row.start = _parse_iso8601(wrec.get("start"))
                    workout_row.end = _parse_iso8601(wrec.get("end"))
                    workout_row.timezone_offset = wrec.get("timezone_offset")

                    score_block = wrec.get("score") or {}
                    if not isinstance(score_block, dict):
                        score_block = {}

                    s_val = score_block.get("strain")
                    workout_row.strain = float(s_val) if isinstance(s_val, (int, float)) else None

                    ah = score_block.get("average_heart_rate")
                    workout_row.average_heart_rate = (
                        float(ah) if isinstance(ah, (int, float)) else None
                    )

                    mh = score_block.get("max_heart_rate")
                    workout_row.max_heart_rate = (
                        float(mh) if isinstance(mh, (int, float)) else None
                    )

                    kj = score_block.get("kilojoule")
                    workout_row.kilojoule = (
                        float(kj) if isinstance(kj, (int, float)) else None
                    )

                    pr = score_block.get("percent_recorded")
                    workout_row.percent_recorded = (
                        float(pr) if isinstance(pr, (int, float)) else None
                    )

                    workout_row.distance_meter = score_block.get("distance_meter")
                    workout_row.altitude_gain_meter = score_block.get("altitude_gain_meter")
                    workout_row.altitude_change_meter = score_block.get("altitude_change_meter")
                    workout_row.zone_durations = score_block.get("zone_durations")

                    workout_row.api_created_at = _parse_iso8601(wrec.get("created_at"))
                    workout_row.api_updated_at = _parse_iso8601(wrec.get("updated_at"))
                    workout_row.raw_payload = wrec
        else:
            try:
                workout_raw = workout_resp.json()
            except Exception:
                workout_raw = workout_resp.text

        # ---------- BODY MEASUREMENT ----------
        body_url = f"{settings.WHOOP_API_BASE}/developer/v2/user/measurement/body"
        try:
            with httpx.Client(timeout=10.0) as client:
                body_resp = client.get(
                    body_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if body_resp.status_code == 200:
                bm = body_resp.json()
                if isinstance(bm, dict):
                    bm_row = WhoopBodyMeasurement(
                        as_of_date=d,
                        height_meter=bm.get("height_meter"),
                        weight_kilogram=bm.get("weight_kilogram"),
                        max_heart_rate=bm.get("max_heart_rate"),
                        raw_payload=bm,
                    )
                    db.add(bm_row)
        except Exception:
            # ignore body measurement failure for now
            pass

        # ---------- USER PROFILE ----------
        profile_url = f"{settings.WHOOP_API_BASE}/developer/v2/user/profile/basic"
        try:
            with httpx.Client(timeout=10.0) as client:
                profile_resp = client.get(
                    profile_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if profile_resp.status_code == 200:
                prof = profile_resp.json()
                if isinstance(prof, dict):
                    user_id = prof.get("user_id")
                    if user_id is not None:
                        profile_row = (
                            db.query(WhoopUserProfile)
                            .filter(WhoopUserProfile.user_id == user_id)
                            .one_or_none()
                        )
                        if profile_row is None:
                            profile_row = WhoopUserProfile(user_id=user_id)
                            db.add(profile_row)

                        profile_row.email = prof.get("email")
                        profile_row.first_name = prof.get("first_name")
                        profile_row.last_name = prof.get("last_name")
                        profile_row.raw_payload = prof
        except Exception:
            # ignore profile failure for now
            pass

        # ---------- LEGACY SUMMARY (WhoopDaily) ----------
        existing = db.query(WhoopDaily).filter(WhoopDaily.date == d).one_or_none()

        if existing:
            if recovery_score is not None:
                existing.recovery_score = recovery_score
            if hrv_ms is not None:
                existing.hrv_ms = hrv_ms
            if rhr_bpm is not None:
                existing.rhr_bpm = rhr_bpm
            if respiratory_rate is not None:
                existing.respiratory_rate = respiratory_rate
            if spo2_pct is not None:
                existing.spo2_pct = spo2_pct
            if sleep_hours is not None:
                existing.sleep_hours = sleep_hours
            if strain is not None:
                existing.strain = strain
        else:
            row = WhoopDaily(
                date=d,
                recovery_score=recovery_score,
                hrv_ms=hrv_ms,
                rhr_bpm=rhr_bpm,
                respiratory_rate=respiratory_rate,
                spo2_pct=spo2_pct,
                sleep_hours=sleep_hours,
                strain=strain,
            )
            db.add(row)

        # run WHOOP-primary/Apple-fallback merge for that date
        merge_for_date(db, d)
        db.commit()

        return {
            "status": "ok",
            "date": date,
            "recovery_score": recovery_score,
            "hrv_ms": hrv_ms,
            "rhr_bpm": rhr_bpm,
            "respiratory_rate": respiratory_rate,
            "spo2_pct": spo2_pct,
            "sleep_hours": sleep_hours,
            "sleep_status": sleep_status,
            "sleep_raw": sleep_raw,
            "strain": strain,
            "cycle_status": cycle_status,
            "cycle_raw": cycle_raw,
            "workout_status": workout_status,
            "workout_raw": workout_raw,
        }
    finally:
        db.close()