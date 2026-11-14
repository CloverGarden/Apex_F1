"""APEX - Formula 1 Telemetry & Performance Analytics.

Phase 5 (final): true 60fps replay. The lap's whole dataset is handed to a
browser-side canvas component that animates with requestAnimationFrame, so
the circuit dot, gauges and telemetry cursor glide smoothly with no Python
reruns and no ticking. Streamlit still drives the sidebar selectors, the
header, race status, weather, tires and session stats. Metrics OpenF1 does
not provide (engine temp, fuel) are never shown.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import config
from src.dashboard import theme as T
from src.dashboard.replay_payload import build_payload
from src.dashboard.replay_component import replay_html
from src.data.api_client import OpenF1Client, LiveSessionLockError
from src.data import session_loader as SL

st.set_page_config(page_title="APEX · F1 Telemetry", page_icon="🏎️", layout="wide")


@st.cache_resource(show_spinner=False)
def client() -> OpenF1Client:
    return OpenF1Client()


@st.cache_data(show_spinner=False)
def _meetings(year):
    return SL.list_meetings(client(), year)


@st.cache_data(show_spinner=False)
def _sessions(meeting_key):
    return SL.list_sessions(client(), meeting_key)


@st.cache_data(show_spinner=False)
def _drivers(session_key):
    return SL.list_drivers(client(), session_key)


@st.cache_resource(show_spinner=True)
def _session(session_key, driver_number, meta):
    return SL.build_session(client(), session_key, driver_number, meta)


# --- Sidebar selectors -----------------------------------------------------
st.sidebar.markdown("### APEX · Session")
try:
    year = st.sidebar.selectbox("Season", SL.list_years(),
                                index=SL.list_years().index(config.TARGET_YEAR))
    meetings = _meetings(year)
    mnames = meetings["meeting_name"].tolist()
    default_m = next((i for i, n in enumerate(mnames) if "Abu Dhabi" in n), 0)
    mi = st.sidebar.selectbox("Grand Prix", range(len(mnames)),
                              format_func=lambda i: mnames[i], index=default_m)
    meeting_key = int(meetings.iloc[mi]["meeting_key"])

    sessions = _sessions(meeting_key)
    snames = sessions["session_name"].tolist()
    default_s = next((i for i, n in enumerate(snames) if n == "Race"), len(snames) - 1)
    si = st.sidebar.selectbox("Session", range(len(snames)),
                              format_func=lambda i: snames[i], index=default_s)
    session_key = int(sessions.iloc[si]["session_key"])

    drivers = _drivers(session_key).sort_values("driver_number")
    dnames = [f"#{int(r.driver_number)} {r.full_name} · {r.team_name}"
              for r in drivers.itertuples()]
    default_d = next((i for i, r in enumerate(drivers.itertuples())
                      if int(r.driver_number) == config.TARGET_DRIVER_NUMBER), 0)
    di = st.sidebar.selectbox("Driver", range(len(dnames)),
                              format_func=lambda i: dnames[i], index=default_d)
    drow = drivers.iloc[di]
except LiveSessionLockError:
    st.sidebar.warning("OpenF1 is live-locked right now (a live F1 session is "
                       "running). The selectors return when it ends — showing the "
                       "last downloaded session if one is cached.")
    LIVE_LOCKED = True
except Exception as e:
    st.error(f"Could not load session options: {e}")
    st.stop()
else:
    LIVE_LOCKED = False

if LIVE_LOCKED:
    # API is live-locked: use the last session processed to disk, if any.
    from src.dashboard.session_data import load_session as _load_cached
    sess = _load_cached()
    if sess is None:
        st.error("OpenF1 is live-locked and no session is cached yet. "
                 "Try again once the live session ends.")
        st.stop()
    meta = dict(sess.meta)
    meta.setdefault("team", config.TARGET_TEAM)
else:
    meta = {
        "driver": drow.get("full_name"), "number": int(drow.get("driver_number")),
        "acronym": drow.get("name_acronym"), "team": drow.get("team_name"),
        "team_colour": drow.get("team_colour"), "headshot": drow.get("headshot_url"),
        "circuit": sessions.iloc[si].get("circuit_short_name"),
        "country": meetings.iloc[mi].get("country_name"),
        "session_name": snames[si], "date": str(sessions.iloc[si].get("date_start", ""))[:10],
        "year": year,
    }
    try:
        sess = _session(session_key, int(drow["driver_number"]), meta)
    except LiveSessionLockError:
        st.error("OpenF1 locked mid-load (live session). Try again shortly.")
        st.stop()

# --- Theme -----------------------------------------------------------------
TEAM = meta["team"]
accent = config.team_accent(TEAM)
if meta.get("team_colour"):
    accent = {"primary": "#" + str(meta["team_colour"]).lstrip("#"),
              "secondary": accent["secondary"]}
surfaces = config.team_theme(TEAM)
watermark = T.data_uri("logos/redbull_bulls.jpg") if TEAM == "Red Bull Racing" else ""
T.inject_theme(accent, surfaces, f"url('{watermark}')" if watermark else "none")

DRIVER = meta["driver"]; NUMBER = meta["number"]

# --- Header ----------------------------------------------------------------
logo = T.data_uri("logos/redbull_oracle.jpg") if TEAM == "Red Bull Racing" else ""
logo_html = f'<img class="apex-logo-img" src="{logo}" alt="{TEAM}"/>' if logo else \
            f'<div class="apex-sub" style="font-size:1rem;font-weight:800">{TEAM}</div>'
headshot = meta.get("headshot") or config.TARGET_DRIVER_HEADSHOT

st.markdown(
    f"""
    <div class="apex-header">
      <div style="display:flex; align-items:center; gap:18px">
        <div class="apex-brand">▲ APEX</div>{logo_html}
      </div>
      <div style="display:flex; align-items:center; gap:16px">
        <div style="text-align:right">
          <span class="apex-driver-name">{DRIVER}</span>
          <span class="apex-driver-num">{NUMBER}</span>
          <div class="apex-sub">{meta['year']} · {meta['country']}
               · {meta['session_name']} · {meta['date']}</div>
        </div>
        <img class="apex-headshot" src="{headshot}" alt="{DRIVER}"
             onerror="this.style.display='none'"/>
      </div>
    </div>
    <div class="apex-accent-bar"></div>
    """,
    unsafe_allow_html=True,
)

laps = sess.lap_options()
if not laps:
    st.warning("This driver/session has no lap data. Try another selection.")
    st.stop()


def _n(v, d=1):
    return f"{v:.{d}f}" if v is not None and not pd.isna(v) else "--"


# Session-level summary (not tied to one lap; the replay covers the whole race).
fl_num, fl_time = sess.fastest_lap()
final = sess.race_status(sess.total_laps)
start = sess.race_status(1)
w0 = sess.weather_at_lap(1)

reveal = st.sidebar.checkbox("Reveal finishing result", value=False,
                             help="Off by default so the replay isn't spoiled.")

s1, s2, s3 = st.columns(3)
with s1:
    finish_cell = (f"P{final['position']}" if final.get("position") else "--") \
        if reveal else "hidden"
    st.markdown(T.panel("Race", T.metric_grid([
        ("Finish", finish_cell, ""),
        ("Start", f"P{start['position']}" if start.get("position") else "--", ""),
        ("Laps", str(sess.total_laps), ""),
        ("Fastest", final["best_lap"], f"L{fl_num}" if fl_num else ""),
    ])), unsafe_allow_html=True)
with s2:
    rain = " · raining" if w0.get("rain") else ""
    st.markdown(T.panel(f"Weather (start){rain}", T.metric_grid([
        ("Air", _n(w0.get("air")), "°C"),
        ("Track", _n(w0.get("track")), "°C"),
        ("Humidity", _n(w0.get("humidity"), 0), "%"),
        ("Wind", _n(w0.get("wind")), "m/s"),
    ])), unsafe_allow_html=True)
with s3:
    st.markdown(T.panel("Performance", T.metric_grid([
        ("Top Speed", f"{sess.stats['max_speed_kmh']:.0f}", "km/h"),
        ("Avg Speed", f"{sess.stats['avg_speed_kmh']:.0f}", "km/h"),
        ("Max RPM", f"{sess.stats['max_rpm']:,.0f}", ""),
        ("Braking", f"{sess.stats['braking_pct']:.1f}", "%"),
    ])), unsafe_allow_html=True)

st.caption("Press ▶ Play to replay the entire race. Hover the telemetry charts for values.")

# --- The 60fps whole-race replay component ---------------------------------
payload = build_payload(sess, accent["primary"], accent["secondary"],
                        surfaces["text_dim"], surfaces["panel"], surfaces["border"])
theme = {"accent": accent["primary"], "accent2": accent["secondary"],
         "dim": surfaces["text_dim"], "panel": surfaces["panel"],
         "border": surfaces["border"]}
components.html(replay_html(payload, theme, height=900), height=900, scrolling=False)

st.markdown(
    f'<div class="apex-sub" style="text-align:center;margin-top:6px">'
    f'APEX · live leaderboard + whole-race replay at 60fps · {meta.get("circuit","")} · OpenF1</div>',
    unsafe_allow_html=True,
)
