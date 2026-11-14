"""Theme + small HTML helpers for the APEX Streamlit shell.

Loads styles/main.css, injects the dark design tokens and the selected
team accent as CSS variables, and provides tiny helpers to render panels
and metric blocks consistently.
"""

from __future__ import annotations

from pathlib import Path
import streamlit as st

import config

CSS_PATH = config.ROOT / "styles" / "main.css"


def inject_theme(accent: dict, surfaces: dict | None = None,
                 watermark: str = "none") -> None:
    """Load the stylesheet and override CSS variables for the chosen team.

    `accent` is {'primary','secondary'}; `surfaces` is the per-team base
    palette (background/panel/border/text). `watermark` is a CSS value for
    the faint background mark (e.g. url(data:...) or 'none').
    """
    t = surfaces or config.THEME
    css = CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.exists() else ""
    variables = f"""
    <style>
    :root {{
      --apex-bg: {t['background']};
      --apex-panel: {t['panel']};
      --apex-panel-2: {t['panel_2']};
      --apex-border: {t['border']};
      --apex-text: {t['text']};
      --apex-text-dim: {t['text_dim']};
      --apex-accent: {accent['primary']};
      --apex-accent-2: {accent['secondary']};
      --apex-watermark: {watermark};
    }}
    {css}
    </style>
    """
    st.markdown(variables, unsafe_allow_html=True)


def panel(title: str, body_html: str) -> str:
    """Return an HTML string for a titled panel card."""
    return (
        f'<div class="apex-panel">'
        f'<div class="apex-panel-title">{title}</div>'
        f'{body_html}</div>'
    )


def metric(label: str, value: str, unit: str = "") -> str:
    unit_html = f'<span class="unit">{unit}</span>' if unit else ""
    return (
        f'<div class="apex-metric"><div class="label">{label}</div>'
        f'<div class="value">{value}{unit_html}</div></div>'
    )


def metric_grid(metrics: list[tuple[str, str, str]]) -> str:
    cells = "".join(metric(l, v, u) for l, v, u in metrics)
    return f'<div class="apex-metric-grid">{cells}</div>'


def placeholder(text: str) -> str:
    return f'<div class="apex-placeholder">{text}</div>'


def leaderboard_table(rows: list, highlight_number: int | None = None) -> str:
    """Render the race classification as a styled leaderboard, highlighting
    the selected driver's row."""
    if not rows:
        return placeholder("No classification data for this session")
    out = ['<table class="apex-lb"><thead><tr>'
           '<th>Pos</th><th>Driver</th><th>Team</th><th>Laps</th>'
           '<th>Gap</th><th>Pts</th></tr></thead><tbody>']
    for r in rows:
        hl = ' class="hl"' if highlight_number == r.get("number") else ""
        pos = r.get("position")
        pos_txt = "DNF" if r.get("dnf") else ("DSQ" if r.get("dsq") else (str(pos) if pos else "--"))
        gap = r.get("gap")
        if r.get("position") == 1:
            gap_txt = "leader"
        elif gap in (None, "", "nan"):
            gap_txt = "--"
        else:
            try:
                gap_txt = f"+{float(gap):.3f}s"      # numeric gap (or numeric string)
            except (TypeError, ValueError):
                gap_txt = str(gap)                    # e.g. "+1 LAP"
        colour = r.get("colour")
        dot = (f'<span class="lb-dot" style="background:#{str(colour).lstrip("#")}"></span>'
               if colour else '<span class="lb-dot"></span>')
        out.append(
            f'<tr{hl}><td class="pos">{pos_txt}</td>'
            f'<td>{dot}{r.get("acronym","")} <span class="lb-name">{r.get("name","")}</span></td>'
            f'<td class="lb-team">{r.get("team","")}</td>'
            f'<td>{r.get("laps","")}</td><td>{gap_txt}</td>'
            f'<td class="lb-pts">{r.get("points",0):.0f}</td></tr>'
        )
    out.append("</tbody></table>")
    return "".join(out)


ASSETS = config.ROOT / "assets"


def svg(rel_path: str) -> str:
    """Return the inline SVG markup for an asset, or '' if missing."""
    p = ASSETS / rel_path
    return p.read_text(encoding="utf-8") if p.exists() else ""


import base64
import functools


@functools.lru_cache(maxsize=32)
def data_uri(rel_path: str) -> str:
    """Return a base64 data: URI for an image asset (so Streamlit can show it).

    Cached so each image is read and encoded only once per run.
    """
    p = ASSETS / rel_path
    if not p.exists():
        return ""
    mime = "image/svg+xml" if p.suffix == ".svg" else f"image/{p.suffix.lstrip('.')}"
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def gauge_bar(label: str, value: float, vmin: float, vmax: float,
              unit: str = "", redline: float | None = None,
              fmt: str = "{:.0f}") -> str:
    """A horizontal progress-bar gauge, styled like the reference screen.

    `redline` (0-1 fraction of the track) draws a red zone at the high end.
    """
    span = max(vmax - vmin, 1e-9)
    pct = max(0.0, min(1.0, (value - vmin) / span)) * 100
    red_html = ""
    if redline is not None:
        red_html = (f'<span class="apex-gauge-red" '
                    f'style="left:{redline*100:.0f}%"></span>')
    return (
        f'<div class="apex-gauge">'
        f'<div class="apex-gauge-head"><span>{label}</span>'
        f'<span class="apex-gauge-val">{fmt.format(value)}'
        f'<em>{unit}</em></span></div>'
        f'<div class="apex-gauge-track">{red_html}'
        f'<span class="apex-gauge-fill" style="width:{pct:.1f}%"></span></div>'
        f'<div class="apex-gauge-scale"><span>{fmt.format(vmin)}</span>'
        f'<span>{fmt.format(vmax)}</span></div>'
        f'</div>'
    )
