# APEX - Formula 1 Telemetry & Performance Analytics

> **Project roadmap and incremental implementation plan**\
> Historical replay first · Streamlit · Python · OpenF1 · Plotly

**Tagline:** Explore every lap. Understand every detail.

------------------------------------------------------------------------

## 0. Progress Tracker

_Last updated: 2026-11-09. Test case: 2024 season, Red Bull · Max Verstappen (#1),
default Abu Dhabi (Yas Marina) Race. Driver/GP/session selectable in the sidebar._

| Phase | Status | Notes |
|-------|--------|-------|
| 1 · Data Exploration & Collection | ✅ Done | `notebooks/01_data_collection.ipynb`, all 8 datasets fetched + saved |
| 2 · Data Cleaning & Processing | ✅ Done | `notebooks/02_data_cleaning.ipynb`, `src/processing/cleaning.py` |
| 3 · Static Dashboard UI | ✅ Done | 3-column layout, dark Red Bull theme, CSS variables |
| 4 · Data & Visualization Integration | ✅ Done | every panel reads real data; real `/position` |
| 5 · Historical Replay | ✅ Done (exceeded) | 60fps browser component, see "beyond spec" below |
| 6 · Testing, Polish & Deployment | 🟡 In progress | README written; multi-session testing + deploy pending |

### Done beyond the original spec

- **60fps replay** via a custom HTML/JS canvas component (not Streamlit reruns),
  with offscreen-cached static layers for smooth motion.
- **Live leaderboard** that re-orders in real time as the race plays, with the
  selected driver highlighted and a ⚡ on the fastest-lap driver.
- **Official circuit geometry** for every track (open-licensed `bacinger/f1-circuits`,
  OpenStreetMap-derived), splined for a clean drawn look; falls back to the
  GPS-derived line if a circuit is unknown or offline.
- **Dot placed by lap progress** (not raw GPS), so it always rides the drawn track.
- Sector colours (S1/S2/S3), start/finish marker, circuit name, fading comet trail.
- Season / Grand Prix / Session / Driver selectors; dynamic team accent colour.

### Phase 6 — remaining work

- [ ] Test multiple drivers, constructors, session types, and weekends end to end.
- [ ] Verify behaviour on sessions with incomplete data (wet races, retirements).
- [ ] Tidy loading / error states and finalise the README.
- [ ] Deploy the application (e.g. Streamlit Community Cloud).
- [ ] Add screenshots / a short demo clip.

### Known limitations (by design)

- The car marker is positioned by **lap progress** mapped onto the official track,
  so it shows where in the lap the car is, not its exact GPS metre (pit detours
  are not drawn). Telemetry values and the leaderboard remain exact.
- Sector splits are three equal arc-length thirds (OpenF1 gives sector *times*,
  not on-track boundaries).
- No engine temp / fuel / individual tyre temps — OpenF1 does not provide them,
  so they are never shown (not faked).

------------------------------------------------------------------------

## 1. Project Overview

APEX is a driver-focused Formula 1 analytics dashboard. Users will
select a historical Grand Prix session, constructor, and driver, then
explore race information and car telemetry through an interactive
engineering-style interface.

The dashboard takes inspiration from an F1 engineering telemetry screen:

-   **Left column:** race status, circuit map, and weather.
-   **Center column:** top-down car visualization and current telemetry
    values.
-   **Right column:** driver telemetry charts and performance
    statistics.

### Core principles

1.  Use real session data wherever possible.
2.  Clearly distinguish raw data from calculated metrics.
3.  Prioritize useful visualizations over decorative widgets.
4.  Adapt the dashboard accent colors to the selected constructor and
    season.
5.  Keep the code modular, but appropriate for an undergraduate
    portfolio project.
6.  Build a working minimum viable product (MVP) before adding advanced
    features.

### Initial project scope

  Item                  Initial decision
  --------------------- ---------------------------------------------------------
  Data experience       Historical sessions first
  Future extension      Live session mode
  Layout                Three-column layout inspired by the reference dashboard
  Main visuals          Circuit map and top-down car illustration
  Framework             Streamlit with custom CSS
  Driver display        One driver at a time
  Data source           OpenF1 API
  Data processing       Python, Pandas, NumPy
  Charts                Plotly
  Local storage/cache   Parquet and Streamlit caching

------------------------------------------------------------------------

## 2. User Journey

The intended full application flow is:

1.  Select a season.
2.  Select a Grand Prix.
3.  Select a session (Practice, Qualifying, Sprint, or Race).
4.  Select a constructor.
5.  Select a driver.
6.  Open the APEX telemetry dashboard.

**Development shortcut:** During the first dashboard milestone, use one
fixed historical session and driver. Build the selection homepage after
the main dashboard works.

------------------------------------------------------------------------

## 3. Dashboard Specification

### 3.1 Header and driver information

Display:

-   APEX application identity.
-   Constructor logo and name.
-   Driver name and number.
-   Driver portrait, when available.
-   Season, Grand Prix, session type, and session date.

The header must update when the selected driver or constructor changes.

### 3.2 Left column: race status

Display:

  Metric             Meaning / source
  ------------------ ---------------------------------------------
  Current position   Driver position during the selected session
  Current lap        Current or selected lap
  Best lap           Fastest valid lap
  Last lap           Most recently completed valid lap
  Gap to leader      Interval to the race leader, when available
  Circuit name       Selected meeting

Recommended prominent metrics:

-   Position
-   Lap number
-   Best lap time
-   Last lap time

Do not label a historical final position as a live or current position.
Make the selected timestamp or session context clear.

### 3.3 Left column: circuit map

The circuit map should be one of the dashboard's main visual features.

Planned features:

-   Circuit outline.
-   Selected driver's approximate location.
-   Track segments colored by speed.
-   Highlighted current position.
-   Hover information such as speed, lap, and timestamp.

**Data consideration:** OpenF1 location coordinates use an arbitrary
coordinate origin. They are not automatically aligned to a circuit map
and do not provide a precise lateral racing line. The project will need
to normalize and orient the coordinates. Treat the displayed marker as
approximate.

### 3.4 Left column: weather

Display, when supplied by the selected session:

  Metric              Unit
  ------------------- ----------
  Air temperature     °C
  Track temperature   °C
  Humidity            \%
  Wind speed          m/s
  Wind direction      Degrees
  Rainfall            Yes / No

Use the nearest available weather observation to the selected replay
timestamp. Do not imply that a less frequently sampled weather reading
is an exact instantaneous measurement.

### 3.5 Center column: car visualization

Use a top-down generic Formula 1 car illustration. Team-specific styling
can be applied where practical.

Place telemetry indicators around or below the illustration:

-   Speed (km/h)
-   Throttle input (%)
-   Brake input (%)
-   RPM
-   Gear
-   DRS status

The values should correspond to the selected driver and timestamp.

The illustration is a visual representation, not a mechanical diagram.
Do not display unsupported values such as individual tire temperatures,
brake temperatures, fuel level, or engine temperature as if OpenF1
supplied them.

### 3.6 Right column: telemetry charts

Start with three main charts.

#### Chart A - Speed

-   X-axis: lap distance or elapsed time.
-   Y-axis: speed in km/h.
-   Purpose: show acceleration, braking, and speed changes around a lap.

#### Chart B - Throttle and brake

-   X-axis: lap distance or elapsed time.
-   Y-axis: input percentage.
-   Series: throttle and brake.
-   Purpose: show how the driver applies throttle and braking.

#### Chart C - RPM and gear

-   X-axis: lap distance or elapsed time.
-   Y-axis: RPM.
-   Optional companion display: gear selection.
-   Purpose: show engine-speed patterns and gear changes.

All charts should support hover tooltips. Where practical, synchronize a
vertical cursor across charts during replay.

### 3.7 Driver performance statistics

Calculate these from the available telemetry samples:

  Statistic            Calculation
  -------------------- ----------------------------------------
  Average speed        Mean of valid speed samples
  Maximum speed        Maximum valid speed
  Minimum speed        Minimum valid speed
  Average throttle     Mean throttle input
  Braking percentage   Share of samples where brake is active
  Maximum RPM          Maximum valid RPM

Document how missing values and invalid samples are handled.

### 3.8 Tire information

Display:

-   Tire compound.
-   Stint number.
-   Stint starting lap.
-   Stint ending lap, when known.
-   Tire age at stint start.
-   Estimated tire age at the selected lap.

Estimated tire age:

`Tire age = selected lap - stint start lap + age at stint start`

Example: if a stint begins on lap 20 with tires already two laps old,
the estimated tire age on lap 25 is seven laps.

Clearly label this as an estimate derived from stint data.

### 3.9 Race events

Add a compact event timeline after the core dashboard is working.

Potential events:

-   Yellow flags.
-   Safety car.
-   Virtual safety car.
-   Red flags.
-   Pit stops.
-   Other race-control messages.

Use this information to help explain unusual changes in lap times or
telemetry.

------------------------------------------------------------------------

## 4. Dynamic Team Theme

Keep the base interface consistent and change the accent color based on
the selected constructor and season.

### Base design tokens

  Element            Suggested value
  ------------------ --------------------
  Background         `#050D0B`
  Panel background   `#0B1915`
  Secondary panel    `#10231E`
  Border             `#1C3730`
  Primary text       `#F4F7F5`
  Secondary text     `#8A9C95`
  Accent             Dynamic team color

### Suggested starting accent colors

These are UI starting points, not a guarantee of exact official livery
colors for every season.

  Constructor       Primary accent   Secondary accent
  ----------------- ---------------- ------------------
  Mercedes          `#00D2BE`        `#FFFFFF`
  Ferrari           `#E8002D`        `#FFF200`
  McLaren           `#FF8000`        `#47C7FC`
  Red Bull Racing   `#3671C6`        `#E10600`
  Williams          `#1868DB`        `#00A3E0`
  Aston Martin      `#229971`        `#CEDC00`
  Alpine            `#FF87BC`        `#0093CC`
  Haas              `#B6BABD`        `#E10600`
  Racing Bulls      `#6692FF`        `#FFFFFF`

Prefer the selected season's `team_colour` from OpenF1 when available.
Use a fallback palette if the API value is missing.

Implement the theme with CSS variables so all relevant panels, chart
accents, gauges, and highlights update together.

------------------------------------------------------------------------

## 5. OpenF1 Data Requirements

Official documentation: <https://openf1.org/docs/>

### Endpoint mapping

  -----------------------------------------------------------------------
  Endpoint                Purpose                 Priority
  ----------------------- ----------------------- -----------------------
  `/meetings`             Grand Prix weekend      Essential
                          information             

  `/sessions`             Practice, qualifying,   Essential
                          sprint, and race        
                          sessions                

  `/drivers`              Driver names, numbers,  Essential
                          team colors, and        
                          available images        

  `/car_data`             Speed, throttle, brake, Essential
                          RPM, gear, and DRS      

  `/location`             Approximate driver      Essential
                          position on the circuit 

  `/laps`                 Lap and sector times    Essential

  `/weather`              Weather observations    High

  `/stints`               Tire compound and stint High
                          information             

  `/position`             Driver position during  High
                          a session               

  `/intervals`            Gap to leader and car   Medium
                          ahead                   

  `/race_control`         Flags, safety cars, and Medium
                          race events             

  `/pit`                  Pit stop information    Medium

  `/session_result`       Final session           Medium
                          classification          
  -----------------------------------------------------------------------

Historical data is available from 2023 onwards under OpenF1's free
historical-data access. Check the current API documentation for endpoint
coverage, access conditions, and rate limits before implementation.

### Data acquisition sequence

For a selected session:

1.  Retrieve meeting information.
2.  Retrieve session information.
3.  Retrieve participating drivers.
4.  Retrieve the selected driver's laps.
5.  Retrieve car telemetry.
6.  Retrieve location data.
7.  Retrieve weather observations.
8.  Retrieve tire stints.
9.  Retrieve position, intervals, and race events as needed.
10. Clean, synchronize, and cache the data.

Do not retrieve all endpoints again whenever a chart control changes.
Cache session-level data and filter it locally.

### Data limitations and handling

  -----------------------------------------------------------------------
  Challenge                           Handling
  ----------------------------------- -----------------------------------
  Different endpoint sampling         Align using timestamps and
  frequencies                         appropriate resampling

  Telemetry and lap timestamps do not Join using time boundaries and
  match exactly                       nearest-time logic where
                                      appropriate

  Arbitrary location coordinate       Normalize and orient coordinates
  origin                              against circuit geometry

  Missing telemetry                   Display unavailable values or gaps

  Weather updates less frequently     Use nearest available observation
                                      and disclose the limitation

  Incomplete or invalid laps          Identify and exclude from
                                      comparisons where appropriate

  Approximate location data           Do not claim precise racing-line
                                      accuracy
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 6. Historical Replay Specification

Historical replay is a planned feature, but it should be implemented
after the static data-connected dashboard.

### Replay controls

-   Lap selector.
-   Timestamp slider.
-   Play and pause.
-   Previous lap and next lap.
-   Playback speed options (for example 0.5×, 1×, and 2×).

### Expected behavior

When the selected timestamp changes:

-   Update the car's approximate circuit marker.
-   Update speed, throttle, brake, RPM, gear, and DRS.
-   Move the cursor on the telemetry charts.
-   Update the selected lap and session time.
-   Update weather using the nearest available observation.

### Implementation note

Start with a timestamp-controlled historical view, not a fully
continuous animation. Streamlit reruns the application when controls
change, so data should be loaded and cached before replay interaction.

A lightweight client-side component or controlled refresh can be
considered later if smoother playback is needed. Streamlit is suitable
for the analytics dashboard, but high-frequency animation may eventually
need a more specialized frontend.

------------------------------------------------------------------------

## 7. Technical Architecture

``` text
OpenF1 API
    |
    v
Data Collection Layer
(API requests, filtering, caching, error handling)
    |
    v
Data Processing Layer
(cleaning, timestamp alignment, feature engineering)
    |
    v
Data Storage and Cache
(Parquet, Streamlit cache, session datasets)
    |
    v
Streamlit Application
(custom CSS, controls, Plotly charts)
    |
    v
APEX Dashboard
(circuit, car, telemetry, race analytics)
```

### Suggested repository structure

``` text
apex-f1/
|
|-- app.py
|-- config.py
|-- requirements.txt
|-- README.md
|
|-- data/
|   |-- raw/
|   |-- processed/
|   |-- cache/
|
|-- notebooks/
|   |-- 01_data_collection.ipynb
|   |-- 02_data_exploration.ipynb
|   |-- 03_telemetry_analysis.ipynb
|   |-- 04_circuit_visualization.ipynb
|
|-- src/
|   |-- data/
|   |   |-- api_client.py
|   |   |-- fetch_data.py
|   |   |-- cache_manager.py
|   |
|   |-- processing/
|   |   |-- cleaning.py
|   |   |-- telemetry.py
|   |   |-- lap_analysis.py
|   |   |-- feature_engineering.py
|   |
|   |-- visualization/
|   |   |-- circuit_map.py
|   |   |-- telemetry_charts.py
|   |   |-- car_visualization.py
|   |
|   |-- dashboard/
|       |-- header.py
|       |-- race_status.py
|       |-- weather.py
|       |-- car_panel.py
|       |-- performance.py
|
|-- assets/
|   |-- logos/
|   |-- drivers/
|   |-- cars/
|   |-- fonts/
|
|-- styles/
    |-- main.css
```

This structure is a guide. Create modules when they are needed rather
than building every empty file at the beginning.

------------------------------------------------------------------------

# 8. Incremental Implementation Roadmap

The project should be developed in small, testable milestones. Each
milestone has a concrete deliverable and a completion check.

## Phase 1 - Data Exploration and Collection

**Goal:** Understand the OpenF1 data before designing the dashboard
around it.

### Tasks

-   [ ] Create the project repository and Python environment.
-   [ ] Install the required libraries.
-   [ ] Read the OpenF1 API documentation.
-   [ ] Choose one historical Grand Prix session.
-   [ ] Choose one driver who participated in that session.
-   [ ] Retrieve meeting information.
-   [ ] Retrieve session information.
-   [ ] Retrieve driver information.
-   [ ] Retrieve lap data.
-   [ ] Retrieve car telemetry.
-   [ ] Retrieve location data.
-   [ ] Retrieve weather data.
-   [ ] Retrieve tire stint data.
-   [ ] Inspect the shape, columns, data types, and missing values of
    each dataset.
-   [ ] Save the raw datasets locally.

### Suggested first test case

Use the 2025 Abu Dhabi Grand Prix Race session and Lewis Hamilton as an
initial test case, provided the selected driver and requested data are
available for that session. If not, select another valid driver/session
combination.

### Deliverable

`notebooks/01_data_collection.ipynb`

### Completion criteria

-   [ ] API requests work for the selected session.
-   [ ] The selected driver is correctly identified.
-   [ ] The expected datasets are retrieved.
-   [ ] Raw data is saved and can be loaded again without repeating API
    requests.
-   [ ] Data availability and limitations are documented.

------------------------------------------------------------------------

## Phase 2 - Data Cleaning and Processing

**Goal:** Convert raw API responses into reliable datasets for analysis.

### Tasks

-   [ ] Standardize column names and data types.
-   [ ] Parse timestamps consistently.
-   [ ] Check for duplicated records.
-   [ ] Inspect missing values and invalid measurements.
-   [ ] Identify valid lap boundaries.
-   [ ] Associate telemetry records with the correct lap.
-   [ ] Align car telemetry with location data.
-   [ ] Connect weather observations to session timestamps.
-   [ ] Connect tire stints to lap information.
-   [ ] Calculate basic telemetry statistics.
-   [ ] Save processed datasets in Parquet format.

### Deliverable

Clean, reusable DataFrames and processed files.

### Completion criteria

-   [ ] Timestamps use a consistent format.
-   [ ] Telemetry records can be associated with laps.
-   [ ] Missing and invalid values are handled consistently.
-   [ ] Calculated metrics can be reproduced from the processed data.

------------------------------------------------------------------------

## Phase 3 - Static Dashboard UI

**Goal:** Recreate the reference dashboard layout using placeholder
data.

### Tasks

-   [ ] Create the Streamlit entry point.
-   [ ] Set up the wide-page layout.
-   [ ] Add the custom dark theme.
-   [ ] Implement CSS variables for team colors.
-   [ ] Create the header and driver information panel.
-   [ ] Create the left-column race status panel.
-   [ ] Create the circuit map placeholder.
-   [ ] Create the weather panel.
-   [ ] Create the center car visualization.
-   [ ] Create the right-column chart panels.
-   [ ] Add responsive spacing and typography.
-   [ ] Test the layout at desktop screen sizes.

### Deliverable

A complete static dashboard with placeholder values.

### Completion criteria

-   [ ] The three-column layout resembles the design reference.
-   [ ] Panels are readable and consistently spaced.
-   [ ] Changing the theme accent updates the interface.
-   [ ] The dashboard does not depend on live API requests yet.

------------------------------------------------------------------------

## Phase 4 - Data and Visualization Integration

**Goal:** Replace placeholder content with actual historical session
data.

### Tasks

-   [ ] Connect driver and session information to the header.
-   [ ] Connect position and lap information to race status.
-   [ ] Build the circuit visualization.
-   [ ] Plot the approximate driver location.
-   [ ] Color circuit segments using speed.
-   [ ] Connect speed telemetry to Plotly.
-   [ ] Connect throttle and brake telemetry.
-   [ ] Connect RPM and gear information.
-   [ ] Add DRS status.
-   [ ] Calculate and display driver statistics.
-   [ ] Connect weather information.
-   [ ] Connect tire stint information.
-   [ ] Add loading, missing-data, and error states.

### Deliverable

A fully data-connected historical telemetry dashboard.

### Completion criteria

-   [ ] Displayed metrics match the selected session and driver.
-   [ ] Charts use actual telemetry.
-   [ ] The circuit map uses actual location data.
-   [ ] Missing values do not crash the application.
-   [ ] Unsupported measurements are not presented as real data.

------------------------------------------------------------------------

## Phase 5 - Historical Replay

**Goal:** Allow users to explore a driver's telemetry at different
points in a session.

### Tasks

-   [ ] Add a lap selector.
-   [ ] Add a timestamp slider.
-   [ ] Add previous-lap and next-lap controls.
-   [ ] Add play and pause controls.
-   [ ] Add playback speed options.
-   [ ] Synchronize the circuit marker with the selected timestamp.
-   [ ] Synchronize telemetry values with the selected timestamp.
-   [ ] Add a moving cursor to the telemetry charts.
-   [ ] Update weather and race status where applicable.
-   [ ] Optimize replay performance using cached data.

### Deliverable

An interactive historical session replay.

### Completion criteria

-   [ ] Selecting a lap loads the correct lap data.
-   [ ] Changing the timestamp updates the displayed telemetry.
-   [ ] Circuit and chart indicators refer to the same point in time.
-   [ ] Replay controls do not trigger unnecessary API requests.

------------------------------------------------------------------------

## Phase 6 - Testing, Polish, and Deployment

**Goal:** Make APEX reliable and ready to demonstrate in a portfolio.

### Tasks

-   [ ] Test multiple drivers.
-   [ ] Test multiple constructors.
-   [ ] Test different session types.
-   [ ] Test different Grand Prix weekends.
-   [ ] Verify dynamic team colors.
-   [ ] Test sessions with incomplete data.
-   [ ] Improve loading and error messages.
-   [ ] Improve desktop and smaller-screen layouts.
-   [ ] Optimize API calls and caching.
-   [ ] Write the project README.
-   [ ] Document data sources and limitations.
-   [ ] Add screenshots and a demo.
-   [ ] Deploy the application.

### Deliverable

A portfolio-ready APEX application.

### Completion criteria

-   [ ] The app can load more than one supported historical session.
-   [ ] Driver and constructor selections work correctly.
-   [ ] Errors and missing data are handled gracefully.
-   [ ] The README explains the project, setup, data, and limitations.
-   [ ] The deployed application can be accessed and demonstrated.

------------------------------------------------------------------------

# 9. MVP vs. Later Features

Keep the first release focused.

  Feature                              MVP   Later
  ----------------------------------- ----- -------
  Historical session data              Yes  
  Driver selection                     Yes  
  Dynamic team theme                   Yes  
  Driver information                   Yes  
  Race status                          Yes  
  Circuit visualization                Yes  
  Top-down car illustration            Yes  
  Speed, throttle, and brake charts    Yes  
  RPM, gear, and DRS                   Yes  
  Weather information                  Yes  
  Tire information                     Yes  
  Historical replay controls                  Yes
  Animated circuit marker                     Yes
  Live telemetry                              Yes
  Multiple-driver comparison                  Yes
  Advanced performance analytics              Yes

------------------------------------------------------------------------

# 10. Data Science Portfolio Value

APEX should demonstrate more than frontend development.

  -----------------------------------------------------------------------
  Skill                               How APEX demonstrates it
  ----------------------------------- -----------------------------------
  Exploratory Data Analysis           Explore telemetry distributions and
                                      racing patterns

  Data Cleaning                       Handle missing, duplicated, and
                                      inconsistent records

  Time-series Processing              Synchronize telemetry and session
                                      timestamps

  Feature Engineering                 Calculate lap and driver
                                      performance statistics

  Data Visualization                  Communicate complex racing data
                                      through interactive charts

  API Integration                     Retrieve and process data from
                                      OpenF1

  Application Development             Turn processed data into an
                                      interactive Streamlit application
  -----------------------------------------------------------------------

### Suggested analytical questions

These can become small insights or analysis sections in the application:

-   Which lap had the highest average speed?
-   What was the driver's maximum speed?
-   How much of a lap was spent braking?
-   How did the driver's speed distribution change across laps?
-   Which sector had the highest speed?
-   How did lap times change throughout the session?
-   How did tire age relate to lap-time changes?

Avoid adding machine learning just to make the project look more
advanced. Meaningful descriptive and exploratory analytics are a better
fit for the initial scope.

------------------------------------------------------------------------

# 11. First Development Sprint

The first sprint should focus only on Phase 1.

### Notebook: `01_data_collection.ipynb`

Recommended notebook structure:

1.  Project Introduction
2.  Import Libraries
3.  Connect to OpenF1 API
4.  Retrieve Meeting Information
5.  Retrieve Session Information
6.  Retrieve Driver Information
7.  Retrieve Lap Data
8.  Retrieve Car Telemetry
9.  Retrieve Circuit Location
10. Retrieve Weather Data
11. Retrieve Tire Stints
12. Initial Data Inspection
13. Save Raw Datasets

### Suggested initial libraries

``` text
pandas
numpy
requests
matplotlib
seaborn
plotly
streamlit
pyarrow
```

Install only what the notebook or application currently needs.
Additional libraries can be introduced when their purpose is clear.

### First sprint success checklist

-   [ ] A historical session has been selected.
-   [ ] A participating driver has been selected.
-   [ ] OpenF1 requests return usable data.
-   [ ] The returned datasets have been inspected.
-   [ ] Important data limitations are recorded.
-   [ ] Raw datasets have been saved locally.

------------------------------------------------------------------------

# 12. Project Development Rules

Use these rules throughout development:

1.  **Data first:** Confirm that a metric is available before designing
    a panel for it.
2.  **No fabricated telemetry:** Use calculated metrics only when their
    formulas and assumptions are clear.
3.  **One milestone at a time:** Finish and validate the current
    milestone before adding the next major feature.
4.  **Keep notebooks understandable:** Explain what each step does and
    why it is necessary.
5.  **Avoid premature complexity:** Do not introduce a database, backend
    service, or advanced frontend framework unless the project needs it.
6.  **Cache responsibly:** Avoid repeatedly requesting the same
    historical data.
7.  **Document assumptions:** Especially for timestamp matching, circuit
    coordinates, and calculated statistics.
8.  **Test across sessions:** Do not assume every endpoint has complete
    data for every driver or session.

------------------------------------------------------------------------

## Final Project Definition

**APEX - Formula 1 Telemetry & Performance Analytics**

A historical Formula 1 telemetry dashboard that lets users explore an
individual driver's race performance through an engineering-inspired
interface. The application combines OpenF1 data, Python-based
processing, interactive Plotly visualizations, circuit tracking, and
dynamic constructor themes.

**Immediate next step:** Complete Phase 1, Data Exploration and
Collection. Do not begin the full dashboard implementation until the
selected session's data has been retrieved and understood.
