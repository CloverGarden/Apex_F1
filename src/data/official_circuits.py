"""Official circuit geometry from the open bacinger/f1-circuits dataset.

That project publishes real F1 track outlines as GeoJSON LineStrings, derived
from OpenStreetMap, under an open licence (MIT / ODbL). We use it to draw a
clean, accurate circuit instead of a noisy GPS line.

We map an OpenF1 circuit (by its short name / location) to a bacinger circuit
id, download the GeoJSON once, cache it under data/cache/circuits/, and return
the outline as x/y metres (local equirectangular projection).

If a circuit is unknown or the download fails, the caller falls back to the
GPS-derived track, so the app always works offline too.
"""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

import numpy as np

import config

BASE = "https://raw.githubusercontent.com/bacinger/f1-circuits/master/circuits"
CACHE = config.CACHE_DIR / "circuits"
CACHE.mkdir(parents=True, exist_ok=True)

# Map OpenF1 circuit_short_name / location (lowercased) -> bacinger id.
# Keys are matched loosely (substring), so small naming differences still hit.
CIRCUIT_IDS = {
    "sakhir": "bh-2002", "bahrain": "bh-2002",
    "jeddah": "sa-2021",
    "melbourne": "au-1953", "albert park": "au-1953",
    "suzuka": "jp-1962",
    "shanghai": "cn-2004",
    "miami": "us-2022",
    "imola": "it-1953",
    "monaco": "mc-1929", "monte carlo": "mc-1929",
    "catalunya": "es-1991", "barcelona": "es-1991",
    "montreal": "ca-1978", "gilles villeneuve": "ca-1978",
    "spielberg": "at-1969", "red bull ring": "at-1969",
    "silverstone": "gb-1948",
    "hungaroring": "hu-1986", "budapest": "hu-1986",
    "spa": "be-1925", "spa-francorchamps": "be-1925",
    "zandvoort": "nl-1948",
    "monza": "it-1922",
    "baku": "az-2016",
    "singapore": "sg-2008", "marina bay": "sg-2008",
    "austin": "us-2012", "americas": "us-2012", "cota": "us-2012",
    "mexico": "mx-1962", "hermanos rodriguez": "mx-1962",
    "interlagos": "br-1940", "sao paulo": "br-1940",
    "las vegas": "us-2023",
    "lusail": "qa-2004", "losail": "qa-2004",
    "yas marina": "ae-2009", "yas_marina": "ae-2009", "abu dhabi": "ae-2009",
}


def _match_id(circuit_name: str, country: str = "") -> str | None:
    hay = f"{circuit_name} {country}".lower()
    for key, cid in CIRCUIT_IDS.items():
        if key in hay:
            return cid
    return None


def _project(coords):
    """lon/lat degrees -> local x/y metres (equirectangular about the mean)."""
    lon = np.array([c[0] for c in coords], dtype=float)
    lat = np.array([c[1] for c in coords], dtype=float)
    lat0 = math.radians(float(lat.mean()))
    R = 6371000.0
    x = np.radians(lon) * math.cos(lat0) * R
    y = np.radians(lat) * R
    x -= x.mean()
    y -= y.mean()
    return x, y


def official_outline(circuit_name: str, country: str = ""):
    """Return (x, y) arrays for the official circuit outline, or None.

    Cached on disk; downloads once. Never raises — returns None on any
    problem so the caller can fall back to GPS.
    """
    cid = _match_id(circuit_name or "", country or "")
    if not cid:
        return None
    path = CACHE / f"{cid}.geojson"
    try:
        if not path.exists():
            req = urllib.request.Request(f"{BASE}/{cid}.geojson",
                                         headers={"User-Agent": "APEX-F1/0.1"})
            data = urllib.request.urlopen(req, timeout=20).read()
            path.write_bytes(data)
        gj = json.loads(path.read_text(encoding="utf-8"))
        coords = gj["features"][0]["geometry"]["coordinates"]
        x, y = _project(coords)
        return x, y
    except Exception:
        return None
