"""Fetch + clean any session/driver on demand, for the dashboard selectors.

Given a season, meeting and session, this fetches every endpoint through the
cached OpenF1 client, cleans and aligns it with the Phase 2 logic, and
returns a ready SessionData. Caching means each session/driver is downloaded
only once; later selections load from Parquet.

This is what lets the dashboard change race, session and driver at runtime
instead of being pinned to the single Phase 1 test case.
"""

from __future__ import annotations

import pandas as pd

import config
from src.data.api_client import OpenF1Client, LiveSessionLockError
from src.processing import cleaning as cl
from src.dashboard.session_data import SessionData


# --- Selector option lists -------------------------------------------------
def list_years() -> list[int]:
    """Seasons with free historical data (2023 onward)."""
    return [2023, 2024, 2025]


def list_meetings(client: OpenF1Client, year: int) -> pd.DataFrame:
    return client.get("meetings", {"year": year})


def list_sessions(client: OpenF1Client, meeting_key: int) -> pd.DataFrame:
    return client.get("sessions", {"meeting_key": meeting_key})


def list_drivers(client: OpenF1Client, session_key: int) -> pd.DataFrame:
    return client.get("drivers", {"session_key": session_key})


# --- Build a full SessionData ----------------------------------------------
def build_session(client: OpenF1Client, session_key: int, driver_number: int,
                  meta_overrides: dict | None = None) -> SessionData:
    """Fetch, clean and align everything for one driver in one session."""
    skq = {"session_key": session_key}
    skd = {"session_key": session_key, "driver_number": driver_number}

    raw_laps = client.get("laps", skd)
    if raw_laps.empty:
        # No laps for this driver/session (e.g. a practice they sat out, or an
        # endpoint with no data). Return an empty-but-valid SessionData so the
        # dashboard can show a friendly "no data" message instead of crashing.
        empty = pd.DataFrame()
        sd = SessionData(empty, empty, empty, empty, empty,
                         pd.DataFrame(columns=["lap_number", "compound", "stint", "tire_age"]),
                         {}, dict(meta_overrides or {}))
        sd.leaderboard = []
        return sd

    raw_car = client.get("car_data", skd)
    raw_loc = client.get("location", skd)
    raw_weather = client.get("weather", skq)
    raw_stints = client.get("stints", skd)
    raw_pos = client.get("position", skd)
    raw_result = client.get("session_result", skq)   # full classification
    raw_drivers = client.get("drivers", skq)          # names for the board
    raw_all_pos = client.get("position", skq)         # every driver's position over time
    raw_all_laps = client.get("laps", skq)            # every driver's laps (for fastest)

    laps = cl.clean_laps(raw_laps)
    car = cl.clean_car_data(raw_car)
    car["lap_number"] = cl.assign_lap_to_timestamps(car["date"], laps).values
    location = cl.clean_location(raw_loc)
    weather = cl.clean_weather(raw_weather)
    stints = cl.clean_stints(raw_stints)
    position = cl.clean_position(raw_pos) if not raw_pos.empty else raw_pos

    # Per-lap tire age.
    rows = []
    for lap in laps["lap_number"]:
        info = cl.tire_age_at_lap(int(lap), stints)
        if info:
            rows.append({"lap_number": int(lap), "compound": info["compound"],
                         "stint": info["stint_number"],
                         "tire_age": info["estimated_tire_age"]})
    tires = pd.DataFrame(rows, columns=["lap_number", "compound", "stint", "tire_age"])

    stats = cl.telemetry_stats(car)

    # Leaderboard: join the classification to driver names/teams.
    leaderboard = []
    if not raw_result.empty:
        res = raw_result.sort_values("position")
        dmap = {}
        if not raw_drivers.empty:
            for r in raw_drivers.itertuples():
                dmap[int(r.driver_number)] = {
                    "name": getattr(r, "full_name", ""),
                    "acronym": getattr(r, "name_acronym", ""),
                    "team": getattr(r, "team_name", ""),
                    "colour": getattr(r, "team_colour", None),
                }
        for r in res.itertuples():
            num = int(r.driver_number)
            info = dmap.get(num, {})
            pos = getattr(r, "position", None)
            leaderboard.append({
                "position": int(pos) if pos == pos else None,  # NaN guard
                "number": num,
                "name": info.get("name", f"#{num}"),
                "acronym": info.get("acronym", str(num)),
                "team": info.get("team", ""),
                "colour": info.get("colour"),
                "laps": int(getattr(r, "number_of_laps", 0) or 0),
                "points": float(getattr(r, "points", 0) or 0),
                "gap": getattr(r, "gap_to_leader", None),
                "dnf": bool(getattr(r, "dnf", False)),
                "dsq": bool(getattr(r, "dsq", False)),
            })

    # Driver directory for the live board (names, teams, colours).
    ddir = {}
    if not raw_drivers.empty:
        for r in raw_drivers.itertuples():
            ddir[int(r.driver_number)] = {
                "acronym": getattr(r, "name_acronym", str(int(r.driver_number))),
                "team": getattr(r, "team_name", ""),
                "colour": getattr(r, "team_colour", None),
            }

    meta = dict(meta_overrides or {})
    sd = SessionData(laps, car, location, weather, stints, tires, stats, meta,
                     position=position)
    sd.leaderboard = leaderboard
    sd.all_positions = raw_all_pos      # time-series positions, all drivers
    sd.all_laps = raw_all_laps          # all drivers' laps (fastest per lap)
    sd.driver_dir = ddir
    sd.race_start = car["date"].min() if not car.empty else None
    return sd
