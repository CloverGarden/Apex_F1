"""Phase 4: the single data source the dashboard reads from.

Loads the processed Parquet files once, and exposes helpers that turn them
into the exact display values each panel needs: header info, race status,
per-lap telemetry series, driver stats, weather, and tire info.

Everything here is derived from REAL data. Where OpenF1 provides nothing
(engine temp, fuel, individual tire temps), there is simply no function -
the dashboard does not invent those.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import config


def _fmt_laptime(seconds: float | None) -> str:
    """Seconds -> M:SS.mmm, or '--' when missing."""
    if seconds is None or pd.isna(seconds):
        return "--"
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"{m}:{s:06.3f}"


@dataclass
class SessionData:
    """Everything the dashboard needs for one driver in one session."""
    laps: pd.DataFrame
    car: pd.DataFrame
    location: pd.DataFrame
    weather: pd.DataFrame
    stints: pd.DataFrame
    tires: pd.DataFrame
    stats: dict
    meta: dict
    position: pd.DataFrame | None = None
    leaderboard: list | None = None
    all_positions: pd.DataFrame | None = None
    all_laps: pd.DataFrame | None = None
    driver_dir: dict | None = None
    race_start: object | None = None

    # --- Lap helpers -------------------------------------------------------
    @property
    def valid_laps(self) -> pd.DataFrame:
        return self.laps[self.laps["is_valid_lap"]]

    @property
    def total_laps(self) -> int:
        if self.laps is None or self.laps.empty or "lap_number" not in self.laps:
            return 0
        return int(self.laps["lap_number"].max())

    def fastest_lap(self) -> tuple[int, float] | tuple[None, None]:
        v = self.valid_laps
        if v.empty:
            return None, None
        row = v.loc[v["lap_duration"].idxmin()]
        return int(row["lap_number"]), float(row["lap_duration"])

    def lap_options(self) -> list[int]:
        if self.laps is None or self.laps.empty or "lap_number" not in self.laps:
            return []
        return sorted(int(x) for x in self.laps["lap_number"].dropna().unique())

    # --- Per-lap telemetry -------------------------------------------------
    def car_for_lap(self, lap_number: int) -> pd.DataFrame:
        df = self.car[self.car["lap_number"] == lap_number].copy()
        if df.empty:
            return df
        # Elapsed seconds within the lap, for a clean x-axis.
        t0 = df["date"].min()
        df["t"] = (df["date"] - t0).dt.total_seconds()
        return df.reset_index(drop=True)

    def sample_at(self, lap_car: pd.DataFrame, frac: float) -> dict:
        """The telemetry sample at a point through the lap (frac 0..1).

        Returns the instantaneous values used to drive the moving car,
        gauges and circuit marker during replay.
        """
        if lap_car.empty:
            return {"speed": 0, "rpm": 0, "throttle": 0, "brake": 0,
                    "gear": 0, "drs": "OFF", "t": 0.0, "date": None, "idx": 0}
        frac = max(0.0, min(1.0, frac))
        i = int(round(frac * (len(lap_car) - 1)))
        row = lap_car.iloc[i]
        return {
            "speed": int(row["speed"]), "rpm": int(row["rpm"]),
            "throttle": int(row["throttle"]), "brake": int(row["brake"]),
            "gear": int(row["n_gear"]),
            "drs": "ON" if bool(row["drs_active"]) else "OFF",
            "t": float(row["t"]), "date": row["date"], "idx": i,
        }

    def location_index_for_time(self, ts) -> int | None:
        """Nearest location row to a timestamp (for the moving circuit dot)."""
        if self.location is None or self.location.empty or ts is None:
            return None
        loc = self.location.sort_values("date").reset_index(drop=True)
        return int((loc["date"] - ts).abs().idxmin())

    def position_at_lap(self, lap_number: int) -> int | None:
        """Real track position at the start of a lap, from /position."""
        from src.processing.cleaning import position_at_time
        if self.position is None or self.position.empty:
            return None
        lap = self.laps[self.laps["lap_number"] == lap_number]
        if lap.empty:
            return None
        return position_at_time(lap["date_start"].iloc[0], self.position)

    def race_status(self, lap_number: int) -> dict:
        fl_num, fl_time = self.fastest_lap()
        last = self.laps[self.laps["lap_number"] == lap_number]
        last_time = float(last["lap_duration"].iloc[0]) if not last.empty and \
            pd.notna(last["lap_duration"].iloc[0]) else None
        pos = self.position_at_lap(lap_number)
        return {
            "lap": lap_number,
            "total_laps": self.total_laps,
            "best_lap": _fmt_laptime(fl_time),
            "best_lap_num": fl_num,
            "last_lap": _fmt_laptime(last_time),
            "top_speed": int(self.stats.get("max_speed_kmh", 0)),
            "position": pos,
        }

    def weather_at_lap(self, lap_number: int) -> dict:
        lap = self.laps[self.laps["lap_number"] == lap_number]
        if lap.empty or self.weather.empty:
            return {}
        ts = lap["date_start"].iloc[0]
        probe = pd.DataFrame({"date": [ts]})
        w = self.weather.sort_values("date")
        m = pd.merge_asof(probe, w, on="date", direction="nearest").iloc[0]
        return {
            "air": m.get("air_temperature"),
            "track": m.get("track_temperature"),
            "humidity": m.get("humidity"),
            "wind": m.get("wind_speed"),
            "rain": bool(m.get("is_raining", False)),
        }

    def tire_at_lap(self, lap_number: int) -> dict:
        row = self.tires[self.tires["lap_number"] == lap_number]
        if row.empty:
            return {}
        r = row.iloc[0]
        return {"compound": r["compound"], "stint": int(r["stint"]),
                "age": int(r["tire_age"])}


def load_session() -> SessionData | None:
    """Load the processed datasets. Returns None if Phase 2 has not run."""
    P = config.PROCESSED_DIR
    required = ["laps_clean", "car_data_clean", "location_clean",
                "weather_clean", "stints_clean", "lap_tire_age", "driver_stats"]
    paths = {n: P / f"{n}.parquet" for n in required}
    if not all(p.exists() for p in paths.values()):
        return None

    laps = pd.read_parquet(paths["laps_clean"])
    car = pd.read_parquet(paths["car_data_clean"])
    location = pd.read_parquet(paths["location_clean"])
    weather = pd.read_parquet(paths["weather_clean"])
    stints = pd.read_parquet(paths["stints_clean"])
    tires = pd.read_parquet(paths["lap_tire_age"])
    stats = pd.read_parquet(paths["driver_stats"]).iloc[0].to_dict()

    # Header meta from the raw session/driver files (small, safe to read).
    meta = {}
    sp = config.RAW_DIR / "sessions.parquet"
    dp = config.RAW_DIR / "drivers.parquet"
    if sp.exists():
        s = pd.read_parquet(sp).iloc[0]
        meta.update({
            "circuit": s.get("circuit_short_name"),
            "country": s.get("country_name"),
            "session_name": s.get("session_name"),
            "date": str(s.get("date_start", ""))[:10],
            "year": int(s.get("year", config.TARGET_YEAR)),
        })
    if dp.exists():
        d = pd.read_parquet(dp)
        row = d[d["driver_number"] == config.TARGET_DRIVER_NUMBER]
        if not row.empty:
            r = row.iloc[0]
            meta.update({
                "driver": r.get("full_name", config.TARGET_DRIVER_NAME),
                "number": int(r.get("driver_number", config.TARGET_DRIVER_NUMBER)),
                "acronym": r.get("name_acronym", config.TARGET_DRIVER_ACRONYM),
                "team": r.get("team_name", config.TARGET_TEAM),
                "team_colour": r.get("team_colour"),
                "headshot": r.get("headshot_url", config.TARGET_DRIVER_HEADSHOT),
            })

    return SessionData(laps, car, location, weather, stints, tires, stats, meta)
