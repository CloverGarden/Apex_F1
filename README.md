# APEX - Formula 1 Telemetry & Performance Analytics

> Explore every lap. Understand every detail.

A historical F1 telemetry dashboard. Pick a session and a driver, then explore race
status, circuit position, and car telemetry through an engineering-style interface.
Data from the [OpenF1 API](https://openf1.org/); built with Python, Pandas, Plotly,
and Streamlit.

## Status

**Phase 1 complete — Data Collection.**
**Phase 2 complete — Data Cleaning and Processing.**
**Phase 3 complete — Static Dashboard UI** (three-column Red Bull theme, logo, circuit map, gauges).
**Phase 4 complete — Data & Visualization Integration** (lap selector drives real values across every panel).
Test case: 2024 Abu Dhabi Grand Prix (Race), Max Verstappen (Red Bull, #1).

Run the app: `streamlit run app.py`

## Setup

```bash
py -3.10 -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Open `notebooks/01_data_collection.ipynb` and run all cells. Data is cached, so it only
downloads once.

## Project layout

```
config.py                     # paths, API base URL, fixed test case, team theme
requirements.txt
notebooks/
  01_data_collection.ipynb    # Phase 1 deliverable
  02_data_cleaning.ipynb      # Phase 2 deliverable
src/data/
  api_client.py               # OpenF1 client: requests, caching, live-lock handling
src/processing/
  cleaning.py                 # Phase 2: parse, dedupe, align, stats
data/raw/                     # saved datasets (Parquet) — not tracked in git
data/processed/               # cleaned, aligned datasets (Parquet) — not tracked in git
data/cache/                   # raw API response cache — not tracked in git
```

## OpenF1 access notes

- Historical data is **free** and needs no account.
- During a **live session** (30 min before to 30 min after), the whole API is locked
  for unauthenticated users. It opens again when the session ends. The client raises a
  clear `LiveSessionLockError` and the notebook handles it gracefully — just re-run later.
- Free tier: 3 requests/second, 30/minute. The client throttles itself to stay under this.

## Data limitations (recorded in Phase 1)

- **Location coordinates** use an arbitrary origin — they must be normalised before
  drawing a circuit map, and the marker is approximate, not a precise racing line.
- **Weather** is sampled roughly once a minute — always match to the nearest reading;
  do not present it as an exact instantaneous value.
- **Sampling rates differ** across endpoints — align by timestamp when joining.
- OpenF1 provides **no** individual tire temperatures, brake temperatures, fuel level,
  or engine temperature. The reference screen shows these; APEX must not fabricate them.

## Data source

OpenF1 is an independent, community project, not affiliated with Formula 1 or the FIA.
Used here for a non-commercial educational portfolio project.
