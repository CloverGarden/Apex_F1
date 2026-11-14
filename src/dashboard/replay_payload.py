"""Build the JSON payload the JS replay component animates in the browser.

Sends the WHOLE RACE for one driver to the browser once, so the client can
animate at 60fps with requestAnimationFrame and never round-trip to Python.

Payload shape:
{
  "track":   {"x":[...], "y":[...]},     # full circuit outline (one lap shape)
  "path":    {"x":[...], "y":[...]},     # driver position over the whole race
  "t":       [...],                       # elapsed seconds from race start
  "lap":     [...],                       # lap number per sample
  "speed","rpm","throttle","brake","gear","drs": [...],
  "duration": float,                      # race length in seconds (telemetry span)
  "laps":    [{"n":1,"t0":..,"t1":..}],   # lap boundaries in seconds
  "theme":   {...}
}
"""

from __future__ import annotations

import json
import math
import numpy as np
import pandas as pd


def _ds_idx(n: int, n_max: int) -> np.ndarray:
    if n <= n_max:
        return np.arange(n)
    return np.linspace(0, n - 1, n_max).astype(int)


def _circ_ma(a: np.ndarray, window: int) -> np.ndarray:
    """Circular moving average (wraps, because a lap is a loop)."""
    k = np.ones(window) / window
    pad = np.concatenate([a[-window:], a, a[:window]])
    return np.convolve(pad, k, mode="same")[window:-window]


def _resample_even(x: np.ndarray, y: np.ndarray, n_out: int):
    """Resample a closed path to n_out points evenly spaced by arc length.

    This is the key to a crisp map: raw GPS points bunch up in slow corners
    and spread out on straights, which makes the smoothed line look lumpy.
    Spacing points evenly along the track distance gives a uniform, clean curve.
    """
    # close the loop
    x = np.append(x, x[0]); y = np.append(y, y[0])
    d = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0], np.cumsum(d)])
    total = s[-1]
    if total <= 0:
        return x[:-1], y[:-1]
    targets = np.linspace(0, total, n_out, endpoint=False)
    xs = np.interp(targets, s, x)
    ys = np.interp(targets, s, y)
    return xs, ys


def _catmull_rom(cx: np.ndarray, cy: np.ndarray, samples_per_seg: int = 12):
    """Closed Catmull-Rom spline through control points (cx, cy).

    The spline passes THROUGH every control point with a smooth tangent, so
    corners are preserved while the line between points is silky — exactly
    the clean 'drawn circuit' look, from real data.
    """
    n = len(cx)
    out_x, out_y = [], []
    for i in range(n):
        p0 = (cx[(i - 1) % n], cy[(i - 1) % n])
        p1 = (cx[i % n],       cy[i % n])
        p2 = (cx[(i + 1) % n], cy[(i + 1) % n])
        p3 = (cx[(i + 2) % n], cy[(i + 2) % n])
        for s in range(samples_per_seg):
            t = s / samples_per_seg
            t2, t3 = t * t, t * t * t
            # Catmull-Rom basis (tension 0.5)
            bx = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                        + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                        + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            by = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                        + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                        + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out_x.append(bx)
            out_y.append(by)
    return np.array(out_x), np.array(out_y)


def _smooth_track(x: np.ndarray, y: np.ndarray, control_points: int = 60):
    """Produce a clean 'drawn' racing line from noisy GPS, via a spline.

    Recipe that finally works for detailed circuits (Suzuka, etc.):
      1. Drop (0,0) no-fix points.
      2. Light pre-smooth to kill single-point GPS spikes.
      3. Reduce to a modest set of EVENLY-SPACED control points. Fewer,
         even points average out jitter without erasing corners.
      4. Fit a closed Catmull-Rom spline through those control points. The
         spline is smooth between points but passes through each, so the
         real corner shape is kept and the line looks hand-drawn.
    """
    mask = ~((x == 0) & (y == 0))
    x, y = x[mask], y[mask]
    if len(x) < 20:
        return x, y
    x = _circ_ma(x, 7)
    y = _circ_ma(y, 7)
    # Even control points. FEWER points (one every ~1.5% of the lap) average
    # out jitter; the spline fills the smooth curve back in between them.
    cx, cy = _resample_even(x, y, control_points)
    # Smooth the control points themselves so the spline rides a clean path.
    cx = _circ_ma(cx, 5)
    cy = _circ_ma(cy, 5)
    # Spline through them -> clean, corner-preserving curve.
    return _catmull_rom(cx, cy, samples_per_seg=14)


def build_payload(sess, accent: str, accent_2: str, text_dim: str,
                  panel: str, border: str, max_samples: int = 9000,
                  track_points: int = 1000) -> str:
    """Serialize the whole race for one driver into a compact JSON string."""
    car = sess.car.copy()
    car = car.dropna(subset=["lap_number"]).sort_values("date").reset_index(drop=True)

    # Elapsed seconds from the first telemetry sample.
    t0 = car["date"].min()
    car["t"] = (car["date"] - t0).dt.total_seconds()

    # Downsample telemetry for the whole race (keeps it light but smooth).
    idx = _ds_idx(len(car), max_samples)
    cs = car.iloc[idx].reset_index(drop=True)

    # Track outline: ONE clean lap's location (not the whole race, which
    # overlaps 58 times and looks thick/wobbly). Use the fastest lap window.
    loc = sess.location.copy()
    if "valid" in loc.columns:
        loc = loc[loc["valid"]]
    loc = loc.sort_values("date").reset_index(drop=True)

    fl_num, _ = sess.fastest_lap()
    track_x = track_y = None

    # 1. OFFICIAL outline (clean, accurate, every corner) when we know the
    #    circuit. This is the preferred source for the drawn track.
    try:
        from src.data.official_circuits import official_outline
        ox, oy = official_outline(sess.meta.get("circuit", ""),
                                  sess.meta.get("country", "")) or (None, None)
    except Exception:
        ox = oy = None
    if ox is not None and len(ox) > 20:
        # The official outline is already clean; just resample to even spacing
        # at a sensible density and spline it for a silky draw. No heavy
        # smoothing (that would distort the real corners).
        oxa, oya = np.asarray(ox, float), np.asarray(oy, float)
        cx, cy = _resample_even(oxa, oya, 150)     # even control points
        sx, sy = _catmull_rom(cx, cy, samples_per_seg=10)
        track_x, track_y = sx.tolist(), sy.tolist()

    # 2. Fallback: GPS-derived spline (offline, or unknown circuit).
    if track_x is None:
        lap_rows = sess.laps[sess.laps["lap_number"] == fl_num]
        if not lap_rows.empty and pd.notna(lap_rows["date_start"].iloc[0]) and \
                pd.notna(lap_rows["date_end"].iloc[0]):
            t0, t1 = lap_rows["date_start"].iloc[0], lap_rows["date_end"].iloc[0]
            one = loc[(loc["date"] >= t0) & (loc["date"] <= t1)]
            if len(one) > 50:
                sx, sy = _smooth_track(one["x"].to_numpy(float), one["y"].to_numpy(float))
                track_x, track_y = sx.tolist(), sy.tolist()
    if track_x is None:
        sx, sy = _smooth_track(loc["x"].to_numpy(float), loc["y"].to_numpy(float))
        track_x, track_y = sx.tolist(), sy.tolist()

    # --- Dot position by LAP PROGRESS (Option A) --------------------------
    # The dot is placed by HOW FAR THROUGH THE LAP the car is, mapped to a
    # distance along the drawn track. This sidesteps GPS<->official coordinate
    # mismatch entirely: the dot always rides the drawn line, at the right
    # point of the lap, whatever track shape or source we drew.
    tx_arr = np.asarray(track_x, dtype=float)
    ty_arr = np.asarray(track_y, dtype=float)
    n_tr = len(tx_arr)

    # Cumulative arc length along the drawn track (fraction 0..1 per point).
    seg = np.hypot(np.diff(tx_arr, append=tx_arr[0]),
                   np.diff(ty_arr, append=ty_arr[0]))
    arc = np.concatenate([[0.0], np.cumsum(seg)[:-1]])
    arc_frac = arc / (arc[-1] if arc[-1] > 0 else 1.0)   # 0..1 around the lap

    # The start/finish line's track index -> lap progress starts there.
    sf_idx = 0
    # Lap start times (seconds) for each lap, to compute progress within a lap.
    lap_t0 = {int(r["lap_number"]): float((r["date_start"] - t0).total_seconds())
              for _, r in sess.laps.iterrows() if pd.notna(r["date_start"])}
    lap_t1 = {int(r["lap_number"]): float((r["date_end"] - t0).total_seconds())
              for _, r in sess.laps.iterrows() if pd.notna(r["date_end"])}

    snap_x = np.empty(len(cs)); snap_y = np.empty(len(cs))
    for i in range(len(cs)):
        lp = int(cs["lap_number"].iloc[i]); tt = float(cs["t"].iloc[i])
        a = lap_t0.get(lp); b = lap_t1.get(lp)
        if a is not None and b is not None and b > a:
            prog = max(0.0, min(1.0, (tt - a) / (b - a)))   # 0..1 through lap
        else:
            prog = 0.0
        # map progress -> nearest track index by arc fraction
        j = int(np.argmin(np.abs(arc_frac - prog)))
        snap_x[i] = tx_arr[j]; snap_y[i] = ty_arr[j]
    path = pd.DataFrame({"x": snap_x, "y": snap_y})

    # Lap boundaries in seconds (for lap ticks on the timeline).
    lap_bounds = []
    for lap_n, grp in car.groupby("lap_number"):
        lap_bounds.append({"n": int(lap_n),
                           "t0": float(grp["t"].min()),
                           "t1": float(grp["t"].max())})

    def col(frame, c):
        return [None if pd.isna(v) else float(v) for v in frame[c].to_numpy()]

    # Start/finish marker: the track point nearest where a lap begins.
    # Use the start of the fastest lap (its first location fix), snapped to
    # the track line so the marker sits exactly on the drawn circuit.
    sf = None
    try:
        lap_rows_sf = sess.laps[sess.laps["lap_number"] == fl_num]
        if not lap_rows_sf.empty and pd.notna(lap_rows_sf["date_start"].iloc[0]):
            ts_sf = lap_rows_sf["date_start"].iloc[0]
            near = loc.iloc[(loc["date"] - ts_sf).abs().to_numpy().argmin()]
            d2 = (tx_arr - float(near["x"])) ** 2 + (ty_arr - float(near["y"])) ** 2
            j = int(np.argmin(d2))
            sf = {"x": float(tx_arr[j]), "y": float(ty_arr[j]), "i": j}
    except Exception:
        sf = None

    # --- Live leaderboard timeline ----------------------------------------
    # Position-change events for every driver, in race seconds, so the board
    # updates as the replay plays. Light (a few hundred rows).
    race_start = getattr(sess, "race_start", None)
    pos_events = []
    ap = getattr(sess, "all_positions", None)
    if ap is not None and not ap.empty and race_start is not None:
        apx = ap.copy()
        apx["date"] = pd.to_datetime(apx["date"], utc=True, format="ISO8601")
        apx = apx.sort_values("date")
        for r in apx.itertuples():
            ts = (r.date - race_start).total_seconds()
            pos_events.append({"t": round(float(ts), 1),
                               "n": int(r.driver_number),
                               "p": int(r.position)})

    ddir = getattr(sess, "driver_dir", None) or {}
    drivers_meta = {str(k): v for k, v in ddir.items()}

    # Fastest lap per driver, and overall fastest (for the highlight).
    fastest = {}
    al = getattr(sess, "all_laps", None)
    overall_fl = None
    if al is not None and not al.empty:
        for num, grp in al.groupby("driver_number"):
            valid = grp["lap_duration"].dropna()
            if len(valid):
                fastest[str(int(num))] = round(float(valid.min()), 3)
        if fastest:
            fn = min(fastest, key=fastest.get)
            overall_fl = {"n": int(fn), "t": fastest[fn]}

    # Sector split: three ~equal arc-length thirds of the lap (OpenF1 gives
    # sector TIMES but not on-track boundaries, so thirds are a clean proxy).
    n_tr2 = len(track_x)
    sectors = [0, n_tr2 // 3, (2 * n_tr2) // 3] if n_tr2 else [0, 0, 0]

    circuit_name = (sess.meta.get("circuit") or sess.meta.get("country")
                    or sess.meta.get("session_name") or "Circuit")

    payload = {
        "duration": float(cs["t"].max()) if len(cs) else 0.0,
        "track": {"x": track_x, "y": track_y},
        "sectors": sectors,
        "circuit": circuit_name,
        "start_finish": sf,
        "pos_events": pos_events,
        "drivers_meta": drivers_meta,
        "fastest_laps": fastest,
        "overall_fastest": overall_fl,
        "selected": int(sess.meta.get("number")) if sess.meta.get("number") else None,
        "path": {"x": col(path, "x"), "y": col(path, "y")},
        "t": col(cs, "t"),
        "lap": [int(v) for v in cs["lap_number"].to_numpy()],
        "speed": col(cs, "speed"),
        "rpm": col(cs, "rpm"),
        "throttle": col(cs, "throttle"),
        "brake": col(cs, "brake"),
        "gear": [int(v) for v in cs["n_gear"].to_numpy()],
        "drs": [int(v) for v in cs["drs_active"].astype(int).to_numpy()],
        "laps": lap_bounds,
        "theme": {"accent": accent, "accent2": accent_2,
                  "dim": text_dim, "panel": panel, "border": border},
    }
    return json.dumps(payload)
