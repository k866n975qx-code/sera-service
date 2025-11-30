from datetime import datetime
from sqlalchemy import Column, Integer, Float, Date, DateTime, JSON, UniqueConstraint, String, Boolean
from app.core.db import Base


class WhoopDaily(Base):
    __tablename__ = "whoop_daily"
    __table_args__ = (UniqueConstraint("date", name="uq_whoop_date"),)

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)

    recovery_score = Column(Integer)
    hrv_ms = Column(Float)
    rhr_bpm = Column(Float)
    respiratory_rate = Column(Float)

    sleep_hours = Column(Float)
    sleep_efficiency_pct = Column(Float)
    deep_sleep_min = Column(Float)
    rem_sleep_min = Column(Float)

    strain = Column(Float)
    avg_hr_day = Column(Float)
    avg_hr_sleep = Column(Float)
    spo2_pct = Column(Float)

    raw_payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class WhoopRecoveryDaily(Base):
    __tablename__ = "whoop_recovery_daily"
    __table_args__ = (UniqueConstraint("date", name="uq_whoop_recovery_date"),)

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)

    cycle_id = Column(Integer)
    sleep_id = Column(String)
    user_id = Column(Integer)

    recovery_score = Column(Float)  # 0–100%
    resting_heart_rate = Column(Float)
    hrv_rmssd_milli = Column(Float)
    spo2_percentage = Column(Float)
    skin_temp_celsius = Column(Float)
    user_calibrating = Column(Boolean)

    api_created_at = Column(DateTime)  # WHOOP created_at
    api_updated_at = Column(DateTime)  # WHOOP updated_at

    raw_payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class WhoopCycleDaily(Base):
    __tablename__ = "whoop_cycle_daily"
    __table_args__ = (UniqueConstraint("date", "cycle_id", name="uq_whoop_cycle_date_cycle"),)

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)

    cycle_id = Column(Integer, nullable=False)
    user_id = Column(Integer)

    start = Column(DateTime)
    end = Column(DateTime)
    timezone_offset = Column(String)
    score_state = Column(String)  # SCORED / PENDING_SCORE / UNSCORABLE

    strain = Column(Float)
    kilojoule = Column(Float)
    average_heart_rate = Column(Float)
    max_heart_rate = Column(Float)

    api_created_at = Column(DateTime)
    api_updated_at = Column(DateTime)

    raw_payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class WhoopSleepActivity(Base):
    __tablename__ = "whoop_sleep_activity"
    __table_args__ = (UniqueConstraint("sleep_id", name="uq_whoop_sleep_id"),)

    id = Column(Integer, primary_key=True)

    sleep_id = Column(String, nullable=False)  # UUID from WHOOP
    cycle_id = Column(Integer)
    user_id = Column(Integer)

    date = Column(Date, nullable=False)

    start = Column(DateTime)
    end = Column(DateTime)
    timezone_offset = Column(String)
    nap = Column(Boolean)
    score_state = Column(String)

    # Stage summary
    total_in_bed_time_milli = Column(Integer)
    total_awake_time_milli = Column(Integer)
    total_no_data_time_milli = Column(Integer)
    total_light_sleep_time_milli = Column(Integer)
    total_slow_wave_sleep_time_milli = Column(Integer)
    total_rem_sleep_time_milli = Column(Integer)
    sleep_cycle_count = Column(Integer)
    disturbance_count = Column(Integer)

    # Sleep score metrics
    respiratory_rate = Column(Float)
    sleep_performance_percentage = Column(Float)
    sleep_consistency_percentage = Column(Float)
    sleep_efficiency_percentage = Column(Float)

    api_created_at = Column(DateTime)
    api_updated_at = Column(DateTime)

    raw_payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class WhoopWorkout(Base):
    __tablename__ = "whoop_workout"
    __table_args__ = (UniqueConstraint("workout_id", name="uq_whoop_workout_id"),)

    id = Column(Integer, primary_key=True)

    workout_id = Column(String, nullable=False)  # UUID from WHOOP
    user_id = Column(Integer)

    date = Column(Date, nullable=False)

    sport_name = Column(String)
    score_state = Column(String)

    start = Column(DateTime)
    end = Column(DateTime)
    timezone_offset = Column(String)

    strain = Column(Float)
    average_heart_rate = Column(Float)
    max_heart_rate = Column(Float)
    kilojoule = Column(Float)
    percent_recorded = Column(Float)

    distance_meter = Column(Float)
    altitude_gain_meter = Column(Float)
    altitude_change_meter = Column(Float)

    zone_durations = Column(JSON)  # full ZoneDurations object

    api_created_at = Column(DateTime)
    api_updated_at = Column(DateTime)

    raw_payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class WhoopBodyMeasurement(Base):
    __tablename__ = "whoop_body_measurement"

    id = Column(Integer, primary_key=True)

    as_of_date = Column(Date, nullable=False)
    height_meter = Column(Float)
    weight_kilogram = Column(Float)
    max_heart_rate = Column(Integer)

    raw_payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class WhoopUserProfile(Base):
    __tablename__ = "whoop_user_profile"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, unique=True)
    email = Column(String)
    first_name = Column(String)
    last_name = Column(String)

    raw_payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)