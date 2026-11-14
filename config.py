"""APEX project configuration.

Central place for constants used across notebooks and src modules.
Keep this file small: paths, the OpenF1 base URL, and the fixed
test-case session/driver used during early development.
"""

from pathlib import Path

# --- Paths -----------------------------------------------------------------
# Project root = the folder this file lives in.
ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"

for _d in (RAW_DIR, PROCESSED_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- OpenF1 API ------------------------------------------------------------
OPENF1_BASE_URL = "https://api.openf1.org/v1"

# Historical data is free and needs no account. During a LIVE F1 session
# the whole API is locked until the session ends (~30 min after). If you
# have a supporter account, set these to raise rate limits / allow live
# access. Leave as None for free historical use.
OPENF1_USERNAME = None
OPENF1_PASSWORD = None

# --- Fixed test case (Phase 1 development shortcut) ------------------------
# One historical session + one driver, so we build against a known target.
TARGET_YEAR = 2024
TARGET_COUNTRY = "United Arab Emirates"   # Abu Dhabi Grand Prix
TARGET_SESSION_NAME = "Race"
TARGET_DRIVER_NUMBER = 1                   # Max Verstappen (Red Bull)
TARGET_DRIVER_NAME = "Max Verstappen"
TARGET_DRIVER_ACRONYM = "VER"
TARGET_TEAM = "Red Bull Racing"
# Driver headshot from OpenF1 /drivers (Phase 1). Hotlinked with a fallback.
TARGET_DRIVER_HEADSHOT = (
    "https://media.formula1.com/d_driver_fallback_image.png/content/dam/"
    "fom-website/drivers/M/MAXVER01_Max_Verstappen/maxver01.png.transform/"
    "1col/image.png"
)

# --- Base design tokens (dark engineering theme, from the roadmap) ---------
# Generic fallback theme (green-tinted) used for any team without a tuned
# variant.
THEME = {
    "background": "#050D0B",
    "panel": "#0B1915",
    "panel_2": "#10231E",
    "border": "#1C3730",
    "text": "#F4F7F5",
    "text_dim": "#8A9C95",
}

# --- Per-team base themes (surfaces, not just accents) ---------------------
# Each team gets a dark surface palette TINTED toward its own livery. Red Bull
# is hand-tuned; every other team is derived from its accent by team_theme(),
# so no team ever falls back to the generic green shell.
TEAM_THEMES = {
    "Red Bull Racing": {
        "background": "#0A1026",   # deep Red Bull navy
        "panel": "#0E1733",
        "panel_2": "#131F45",
        "border": "#27336B",
        "text": "#F3F6FF",
        "text_dim": "#8893BF",
    },
}


def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(c1: str, c2: str, t: float) -> str:
    """Blend two hex colours; t in 0..1 toward c2."""
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return "#%02X%02X%02X" % (round(r1 + (r2 - r1) * t),
                              round(g1 + (g2 - g1) * t),
                              round(b1 + (b2 - b1) * t))


def _derive_theme(accent: str) -> dict:
    """A dark surface palette tinted toward a team's accent colour."""
    black = "#05070C"
    return {
        "background": _mix(black, accent, 0.06),
        "panel": _mix(black, accent, 0.11),
        "panel_2": _mix(black, accent, 0.16),
        "border": _mix(black, accent, 0.34),
        "text": "#F3F6FF",
        "text_dim": _mix("#8A93AF", accent, 0.15),
    }


def team_theme(team_name: str) -> dict:
    """Return the surface palette for a team.

    Hand-tuned entry if present; otherwise derived from the team accent so
    EVERY team gets a themed look, never the generic green fallback.
    """
    if team_name in TEAM_THEMES:
        return TEAM_THEMES[team_name]
    accent = TEAM_COLORS.get(team_name, DEFAULT_ACCENT)["primary"]
    return _derive_theme(accent)

# --- Team accent palette ---------------------------------------------------
# UI starting points, not a guarantee of exact livery colours. Prefer the
# session's team_colour from OpenF1 when available (Phase 4).
TEAM_COLORS = {
    "Mercedes":        {"primary": "#00D2BE", "secondary": "#FFFFFF"},
    "Ferrari":         {"primary": "#E8002D", "secondary": "#FFF200"},
    "McLaren":         {"primary": "#FF8000", "secondary": "#47C7FC"},
    "Red Bull Racing": {"primary": "#3671C6", "secondary": "#E10600"},
    "Williams":        {"primary": "#1868DB", "secondary": "#00A3E0"},
    "Aston Martin":    {"primary": "#229971", "secondary": "#CEDC00"},
    "Alpine":          {"primary": "#FF87BC", "secondary": "#0093CC"},
    "Haas":            {"primary": "#B6BABD", "secondary": "#E10600"},
    "Racing Bulls":    {"primary": "#6692FF", "secondary": "#FFFFFF"},
}

DEFAULT_ACCENT = {"primary": "#3671C6", "secondary": "#E10600"}


def team_accent(team_name: str) -> dict:
    """Return {'primary','secondary'} for a team, with a safe fallback."""
    return TEAM_COLORS.get(team_name, DEFAULT_ACCENT)


# Kept for backwards compatibility with earlier phases.
TEAM_ACCENT_PRIMARY = DEFAULT_ACCENT["primary"]
TEAM_ACCENT_SECONDARY = DEFAULT_ACCENT["secondary"]
