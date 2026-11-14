"""Interactive circuit map for APEX.

Builds a Plotly figure of the track from OpenF1 location (x, y) samples,
coloured by the car's speed at each point, with a highlighted current
position. Hovering shows speed and lap. The map is genuinely interactive
(hover, zoom, pan) - this is the reference screen's mini-map, done for real.

Note (roadmap data rule): OpenF1 location uses an arbitrary coordinate
origin. We only normalise orientation/scale for display; the marker is
approximate, not a precise racing line.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go


def build_circuit_figure(
    location: pd.DataFrame,
    car: pd.DataFrame | None = None,
    marker_index: int | None = None,
    accent: str = "#3671C6",
    accent_2: str = "#E10600",
    text_dim: str = "#8893BF",
    height: int = 230,
) -> go.Figure:
    """Return a Plotly circuit map coloured by speed.

    location: cleaned location frame with x, y (and a 'valid' flag).
    car:      optional cleaned car frame; if given and aligned by nearest
              time, its speed colours the track.
    marker_index: row of `location` to highlight as the current position.
    """
    loc = location.copy()
    if "valid" in loc.columns:
        loc = loc[loc["valid"]]
    loc = loc.dropna(subset=["x", "y"])

    # Downsample for a light, smooth trace (the track shape is preserved).
    if len(loc) > 1500:
        step = len(loc) // 1500
        loc = loc.iloc[::step].reset_index(drop=True)

    x = loc["x"].to_numpy(dtype=float)
    y = loc["y"].to_numpy(dtype=float)

    # Speed per point: nearest car sample by time, if we can.
    speed = None
    if car is not None and "date" in loc.columns and "speed" in car.columns:
        merged = pd.merge_asof(
            loc.sort_values("date")[["date"]],
            car.sort_values("date")[["date", "speed"]],
            on="date", direction="nearest",
        )
        speed = merged["speed"].to_numpy(dtype=float)

    fig = go.Figure()

    if speed is not None and np.isfinite(speed).any():
        # Colour the line by speed using a marker trace along the path.
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="markers",
            marker=dict(size=4, color=speed, colorscale="Turbo",
                        showscale=False, cmin=float(np.nanmin(speed)),
                        cmax=float(np.nanmax(speed))),
            hovertemplate="speed %{marker.color:.0f} km/h<extra></extra>",
            name="track",
        ))
    else:
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines",
            line=dict(color=accent, width=3, shape="spline", smoothing=0.6),
            hoverinfo="skip", name="track",
        ))

    # Current-position marker.
    if marker_index is None:
        marker_index = len(x) // 3
    marker_index = max(0, min(marker_index, len(x) - 1))
    fig.add_trace(go.Scatter(
        x=[x[marker_index]], y=[y[marker_index]], mode="markers",
        marker=dict(size=14, color=accent_2, line=dict(color="#fff", width=2),
                    symbol="circle"),
        hovertemplate="current position<extra></extra>", name="car",
    ))

    fig.update_layout(
        height=height, margin=dict(l=4, r=4, t=4, b=4),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False, font=dict(color=text_dim, size=10),
        xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(visible=False),
        dragmode="pan",
        # Keep the map framed so the marker glides between ticks.
        uirevision="apex-track",
        transition=dict(duration=140, easing="cubic-in-out"),
    )
    return fig
