# EGTS RTLS Sandbox — Prototypes from Discussions

This `sandbox/` folder contains **runnable, isolated prototypes** extracted and cleaned from the technical discussions in `DOCS/discussions/`.

**Purpose**: Experiment with the proposed RTLS v2 extensions (SRT 204 + IMU + Sensor Fusion + Map Matching) **without touching** the main SERVICE/PARSER/MOBILE_APP code.

**Date created**: 2026-06-12 (based on discussions dated 2026-06-11/12)
**Authors of ideas**: Anton Tenyakov / Grok / Claude (see individual .md files)

**Original source chat**:
https://grok.com/project/141c898d-eabd-44f4-bd3c-14ff027bc028?chat=40590679-37f2-48f0-b26a-50f69a97e272&rid=096e52bb-7c58-4b50-afa7-39bbddc23b5d

(Private Grok project/chat. The local DOCS/discussions/*.md files are the structured exports/summaries from that thread.)

## How to use

```powershell
# 1. (Recommended) Create venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt

# 2. Run the main demo (synthetic + real GPS seeds from egts_20260607.json)
python demo.py

# 3. Run individual components
python madgwick.py          # standalone Madgwick test
python ekf.py               # EKF with synthetic data
python fusion_pipeline.py   # full Madgwick + EKF pipeline
python map_matcher.py       # geometric snap + example track
python lbs_map_matcher.py   # LBS (base stations) + road graph snap (new)
python srt204.py            # SRT 204 model encode/decode roundtrip
python srt205_lbs.py        # SRT 205 LBS data model (new)
```

## Mapping to Discussions (все дискурсии)

| Discussion File                        | What is prototyped here                          | Key files in sandbox                  |
|----------------------------------------|--------------------------------------------------|---------------------------------------|
| 01-project-analysis.md                 | Overall project context                          | (this README)                         |
| 02-recommendations-improvements.md     | Testability, future extensions                   | demo.py, generate_data.py             |
| 03-rtls-extensions.md                  | SRT 200-203 baseline (already in main)           | srt204.py (extension pattern)         |
| 04-rtls-iso-standard.md + 06-...       | Standards context, quality fields                | srt204.py (added quality/confidence)  |
| 05-excel-parser.md                     | Future: new INERTIAL / MAP_MATCH sheets          | (commented in srt204.py)              |
| 07-egts-rnis-integration.md            | Ingestion + PostGIS                              | map_matcher.py (PostGIS comments)     |
| **08-road-graph-map-matching.md**      | Why + high-level integration                     | map_matcher.py, fusion_pipeline.py    |
| **09-inertial-sensors-egts.md**        | **SRT 204 proposal** (heading, accel, gyro...)   | **srt204.py** (full dataclass + bytes)|
| **10-vibration-filtering-algorithms.md**| LPF, median, metrics for SRT 204                | **vibration.py** + integration notes  |
| **11-postgis-map-matching.md**         | SQL snap + integration example                   | map_matcher.py (PostGIS section)      |
| **12-flutter-imu-integration.md**      | Dart IMU collection + SRT 204 payload            | (Python equivalent in fusion + notes) |
| **13-sensor-fusion-architecture.md**   | **Madgwick → EKF → Map Matching** 3-layer arch   | **fusion_pipeline.py** (core)         |
| **14-ekf-implementation.md**           | **Full EGTS_EKF** (predict + GPS + heading updates) | **ekf.py**                         |
| **15-map-matching-algorithms.md**      | HMM/Viterbi vs geometric vs Particle, libraries  | map_matcher.py (simple + stubs)       |
| **16-madgwick-filter-implementation.md**| **Full MadgwickFilter** (MARG + IMU-only, β, Euler) | **madgwick.py**                   |
| **17-geopandas-map-matching.md**       | Prototyping with GeoPandas + OSMnx + leuven      | map_matcher.py (GeoPandas stub section)|
| **18-lbs-road-graph-positioning.md**   | LBS (cellular base stations) + road graph for precise on-road location | **lbs_map_matcher.py** (LBS likelihood + lbs_aware_snap_to_road) |
|                                        | Synthetic LBS data (serving + neighbors + TA + RSSI) | `generate_synthetic_lbs()` inside the same file |
|                                        | SRT 205 model for LBS data in EGTS packets         | **srt205_lbs.py** |
|                                        | LBS integrated into sensor fusion + demo           | generate_data.py, fusion_pipeline.py, demo.py |
| RTLS_v2_full_draft.md                  | High-level TЗ skeleton                           | This sandbox is the living implementation draft |

## Current Implementation Status vs Discussions

**Main repo (SERVICE/egts/)** currently supports:
- SRT 200, 201, 202, 203 (RTLS custom) — fully in models.py + codec.py
- No SRT 204
- No filters/ (no Madgwick, no EKF)
- No map matching layer

**This sandbox** implements the **exact proposals** from the discussions as clean, dependency-light Python modules (numpy + scipy + stdlib for core path).

LBS (cellular base stations) + road graph positioning (discussion 18) is fully prototyped:
- `lbs_map_matcher.py`: likelihood-based snapping using TA/RSSI + known BS locations.
- `srt205_lbs.py`: EGTS SRT 205 model for transmitting LBS data.
- Integrated into `fusion_pipeline.py` (process_imu accepts lbs_data and snaps to road) and `demo.py`/`generate_data.py`.
- Pipeline now combines IMU + GPS + LBS for road-accurate position.

## Next steps (from the discussions themselves)

1. Move mature classes into `SERVICE/egts/filters/` and `models.py` (SRT 204 + new SRT 205 for LBS).
2. Extend codec.py registration for SRT 204/205.
3. Add to Excel parser (new INERTIAL and LBS sheets).
4. Wire real IMU + cellular (LBS) from Flutter app → send SRT 204/205.
5. Production map matching with LBS: PostGIS + pgRouting + LBS likelihood (extend 11/15/18).
6. Fill `DOCS/TZ_EGTS_RTLS_v2.docx` + regenerate RTLS_v2_full_draft.md from this sandbox + discussions (LBS section already added).
7. Test LBS + road graph snapping in real РНИС conditions (weak GNSS scenarios).

## Synthetic Data

`generate_data.py` creates tracks with:
- Realistic GPS noise
- IMU (accel/gyro/mag) consistent with heading + vibration
- Ground truth "road" for map matching evaluation

Real seeds are taken from `SERVICE/egts_20260607.json` (decoded POS_DATA points).

## Dependencies (minimal for core)

See `requirements.txt`. Heavy geo (geopandas, osmnx, leuven-map-matching) are **optional** and commented.

Run core fusion/map demos with just `numpy scipy matplotlib`.

---

**All ideas and code patterns here come directly from the reloaded discussions in `DOCS/discussions/`.**

This sandbox makes them **executable and testable immediately**.
