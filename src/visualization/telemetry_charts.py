"""Phase 5: real, butter-smooth telemetry charts for a selected lap.

Each chart plots actual car_data samples against elapsed time within the
lap. Lines are spline-smoothed, the figure keeps its state across replay
ticks (uirevision) so Plotly tweens instead of hard-redrawing, and a
vertical cursor (cursor_t) marks the current replay moment, synchronised
across all three charts. Hover tooltips are enabled.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# A short layout transition makes value/cursor changes glide between ticks.
_TRANSITION = dict(duration=140, easing="cubic-in-out")


def _base(height: int, text_dim: str, border: str) -> dict:
    return dict(
        height=height, margin=dict(l=10, r=10, t=6, b=24),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=text_dim, size=10), showlegend=False,
        xaxis=dict(gridcolor=border, zeroline=False, title="lap time (s)"),
        yaxis=dict(gridcolor=border, zeroline=False),
        hovermode="x unified",
        # Keep the view stable so Plotly animates instead of redrawing.
        uirevision="apex-lap",
        transition=_TRANSITION,
    )


def _cursor(fig: go.Figure, cursor_t: float | None, accent_2: str) -> None:
    """A vertical replay cursor plus a glowing dot where it meets the line."""
    if cursor_t is None:
        return
    fig.add_vline(x=cursor_t, line_width=2, line_color=accent_2, opacity=0.9)


def _dot(fig: go.Figure, x: float | None, y: float | None, color: str) -> None:
    """A moving marker that rides the line at the cursor (the 'playhead')."""
    if x is None or y is None:
        return
    fig.add_trace(go.Scatter(
        x=[x], y=[y], mode="markers",
        marker=dict(size=10, color=color, line=dict(color="#fff", width=2)),
        hoverinfo="skip", showlegend=False))


def _val_at(lap: pd.DataFrame, cursor_t: float | None, col: str):
    if cursor_t is None or lap.empty:
        return None, None
    i = int((lap["t"] - cursor_t).abs().idxmin())
    return float(lap["t"].iloc[i]), float(lap[col].iloc[i])


def speed_chart(lap, accent, text_dim, border, height=150,
                cursor_t=None, accent_2="#E10600") -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=lap["t"], y=lap["speed"], mode="lines",
        line=dict(color=accent, width=2.5, shape="spline", smoothing=1.0),
        hovertemplate="%{y:.0f} km/h<extra></extra>"))
    fig.update_layout(**_base(height, text_dim, border))
    fig.update_yaxes(title="km/h")
    _cursor(fig, cursor_t, accent_2)
    cx, cy = _val_at(lap, cursor_t, "speed"); _dot(fig, cx, cy, accent_2)
    return fig


def throttle_brake_chart(lap, accent, accent_2, text_dim, border, height=150,
                         cursor_t=None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=lap["t"], y=lap["throttle"], mode="lines",
                             line=dict(color=accent, width=2.5, shape="spline", smoothing=1.0),
                             name="Throttle",
                             hovertemplate="throttle %{y:.0f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=lap["t"], y=lap["brake"], mode="lines",
                             line=dict(color=accent_2, width=2.5, shape="spline", smoothing=1.0),
                             name="Brake", fill="tozeroy",
                             fillcolor="rgba(225,6,0,0.12)",
                             hovertemplate="brake %{y:.0f}%<extra></extra>"))
    fig.update_layout(**_base(height, text_dim, border))
    fig.update_yaxes(title="%", range=[0, 105])
    _cursor(fig, cursor_t, accent_2)
    cx, cy = _val_at(lap, cursor_t, "throttle"); _dot(fig, cx, cy, accent)
    return fig


def rpm_gear_chart(lap, accent, text_dim, border, height=150,
                   cursor_t=None, accent_2="#E10600") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=lap["t"], y=lap["rpm"], mode="lines",
                             line=dict(color=accent, width=2.5, shape="spline", smoothing=1.0),
                             name="RPM",
                             hovertemplate="%{y:,.0f} rpm<extra></extra>"))
    fig.add_trace(go.Scatter(x=lap["t"], y=lap["n_gear"], mode="lines",
                             line=dict(color=text_dim, width=1.5, shape="hv"),
                             name="Gear", yaxis="y2",
                             hovertemplate="gear %{y:.0f}<extra></extra>"))
    layout = _base(height, text_dim, border)
    layout["yaxis2"] = dict(overlaying="y", side="right", range=[0, 9],
                            showgrid=False, title="gear")
    fig.update_layout(**layout)
    fig.update_yaxes(title="rpm")
    _cursor(fig, cursor_t, accent_2)
    cx, cy = _val_at(lap, cursor_t, "rpm"); _dot(fig, cx, cy, accent_2)
    return fig
