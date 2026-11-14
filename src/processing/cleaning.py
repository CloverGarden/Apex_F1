"""Phase 2: data cleaning and alignment for APEX.

Turns the raw OpenF1 datasets saved in data/raw/ into clean, reliable,
time-aligned DataFrames saved in data/processed/.

Design choices (documented for the portfolio):
- All timestamps are parsed to timezone-aware UTC datetimes.
- `brake` from OpenF1 is 0 or 100 (percent-ish on/off); we keep the raw
  value and add a boolean `brake_on`.
- `drs` is a status code, not a percentage; we keep the code and add a
  readable `drs_active` flag using the known "DRS on" codes (10, 12, 14).
- `n_gear` == 0 means neutral/coasting; kept as-is.
- Telemetry is joined to laps by time windows (each lap spans from its
  `date_start` to the next lap's `date_start`).
- car_data and location are aligned with a nearest-timestamp merge, since
  they are sampled on slightly different clocks.
- Weather is attached to any timestamp via nearest-reading lookup.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

# OpenF1 DRS status codes that mean DRS is active/available-and-open.
# 0/1 = off, 8 = eligible, 10/12/14 = on. We treat 10,12,14 as "active".
DRS_ACTIVE_CODES = {10, 12, 14}


# --- Timestamp parsing -----------------------------------------------------
def to_utc(series: pd.Series) -> pd.Series:
    """Parse an OpenF1 date string column to timezone-aware UTC datetimes.

    OpenF1 mixes formats (some timestamps carry microseconds, some don't), so
    we use ISO8601 inference to handle both.
    """
    return pd.to_datetime(series, utc=True, errors="coerce", format="ISO8601")


# --- Per-dataset cleaners --------------------------------------------------
def clean_car_data(car: pd.DataFrame) -> pd.DataFrame:
    df = car.copy()
    df["date"] = to_utc(df["date"])
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    df = df.drop_duplicates(subset=["date"])  # one sample per timestamp

    # Readable derived flags (raw columns kept).
    df["brake_on"] = df["brake"].fillna(0).astype(int) > 0
    df["drs_active"] = df["drs"].isin(DRS_ACTIVE_CODES)

    # Validity: speed/rpm cannot be negative; clip obvious bad samples.
    df["valid"] = (
        df["speed"].between(0, 400)
        & df["rpm"].between(0, 20000)
        & df["throttle"].between(0, 100)
        & df["n_gear"].between(0, 8)
    )
    return df


def clean_location(loc: pd.DataFrame) -> pd.DataFrame:
    df = loc.copy()
    df["date"] = to_utc(df["date"])
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    df = df.drop_duplicates(subset=["date"])

    # OpenF1 uses (0,0,0) as a "no fix" placeholder; mark those invalid.
    df["valid"] = ~((df["x"] == 0) & (df["y"] == 0))
    return df


def clean_laps(laps: pd.DataFrame) -> pd.DataFrame:
    df = laps.copy()
    df["date_start"] = to_utc(df["date_start"])
    df = df.sort_values("lap_number").reset_index(drop=True)

    # A lap is "complete/valid" for comparison if it has a real duration
    # and is not an out-lap (pit exit laps are not representative).
    df["is_valid_lap"] = df["lap_duration"].notna() & (~df["is_pit_out_lap"].fillna(False))

    # End of each lap = start of the next lap (last lap has no next start).
    df["date_end"] = df["date_start"].shift(-1)
    return df


def clean_weather(weather: pd.DataFrame) -> pd.DataFrame:
    df = weather.copy()
    df["date"] = to_utc(df["date"])
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    df["is_raining"] = df["rainfall"].fillna(0).astype(int) > 0
    return df


def clean_stints(stints: pd.DataFrame) -> pd.DataFrame:
    df = stints.copy()
    return df.sort_values("stint_number").reset_index(drop=True)


def clean_position(position: pd.DataFrame) -> pd.DataFrame:
    """Clean the /position feed: parse dates, sort, drop dup timestamps."""
    df = position.copy()
    df["date"] = to_utc(df["date"])
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    df = df.drop_duplicates(subset=["date"])
    return df


def position_at_time(ts, position: pd.DataFrame) -> int | None:
    """Most recent reported track position at a given timestamp."""
    if position is None or position.empty:
        return None
    p = position.sort_values("date")
    probe = pd.DataFrame({"date": [pd.to_datetime(ts, utc=True)]})
    m = pd.merge_asof(probe, p[["date", "position"]], on="date", direction="backward")
    val = m["position"].iloc[0]
    return int(val) if pd.notna(val) else None


# --- Alignment / joins -----------------------------------------------------
def assign_lap_to_timestamps(ts: pd.Series, laps: pd.DataFrame) -> pd.Series:
    """Return the lap_number active at each timestamp.

    Each lap covers [date_start, date_end). Uses a sorted merge_asof so a
    timestamp gets the most recent lap that had already started.
    """
    laps_sorted = laps.dropna(subset=["date_start"]).sort_values("date_start")
    probe = pd.DataFrame({"date": pd.to_datetime(ts, utc=True)}).sort_values("date")
    merged = pd.merge_asof(
        probe, laps_sorted[["date_start", "lap_number"]],
        left_on="date", right_on="date_start", direction="backward",
    )
    # Restore original order.
    return merged.set_index(probe.index)["lap_number"].reindex(ts.index)


def align_car_location(car: pd.DataFrame, location: pd.DataFrame,
                       tolerance_ms: int = 500) -> pd.DataFrame:
    """Nearest-timestamp merge of car telemetry with x/y/z location.

    Both are sampled near 3.7 Hz but on different clocks, so we match each
    car sample to the closest location sample within `tolerance_ms`.
    """
    left = car.sort_values("date")
    right = location.sort_values("date")[["date", "x", "y", "z"]].rename(
        columns={"valid": "loc_valid"} if "valid" in location.columns else {}
    )
    merged = pd.merge_asof(
        left, right, on="date", direction="nearest",
        tolerance=pd.Timedelta(milliseconds=tolerance_ms),
    )
    return merged


def attach_weather(ts: pd.Series, weather: pd.DataFrame) -> pd.DataFrame:
    """For each timestamp, return the nearest weather reading (as rows)."""
    probe = pd.DataFrame({"date": pd.to_datetime(ts, utc=True)}).sort_values("date")
    w = weather.sort_values("date")
    merged = pd.merge_asof(probe, w, on="date", direction="nearest")
    return merged.set_index(probe.index).reindex(ts.index)


def tire_age_at_lap(lap_number: int, stints: pd.DataFrame) -> dict | None:
    """Estimated tire info at a given lap, from stint data.

    tire_age = selected_lap - stint_start_lap + age_at_stint_start
    """
    row = stints[(stints["lap_start"] <= lap_number) & (stints["lap_end"] >= lap_number)]
    if row.empty:
        return None
    r = row.iloc[0]
    age = int(lap_number) - int(r["lap_start"]) + int(r["tyre_age_at_start"])
    return {
        "stint_number": int(r["stint_number"]),
        "compound": r["compound"],
        "stint_start_lap": int(r["lap_start"]),
        "stint_end_lap": int(r["lap_end"]),
        "age_at_stint_start": int(r["tyre_age_at_start"]),
        "estimated_tire_age": age,
    }


# --- Telemetry statistics --------------------------------------------------
def telemetry_stats(car_valid: pd.DataFrame) -> dict:
    """Driver performance statistics from valid telemetry samples."""
    v = car_valid[car_valid.get("valid", True)] if "valid" in car_valid else car_valid
    speed = v["speed"]
    return {
        "avg_speed_kmh": round(float(speed.mean()), 1),
        "max_speed_kmh": int(speed.max()),
        "min_speed_kmh": int(speed.min()),
        "avg_throttle_pct": round(float(v["throttle"].mean()), 1),
        "braking_pct": round(float((v["brake"].fillna(0) > 0).mean()) * 100, 1),
        "max_rpm": int(v["rpm"].max()),
        "n_samples": int(len(v)),
    }
