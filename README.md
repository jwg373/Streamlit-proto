# 🏁 F1 Circuit Explorer (Streamlit prototype)

Interactive prototype for exploring two F1 circuits, **Monaco** and **Mexico City**:

1. **Grid Explorer**: a map of the starting grid (P1–P20) for the selected track, coloured by
   win %, podium % or average finish from each slot. Click a slot for its details.
2. **Segment Explorer**: the real track outline split into its three timing sectors. Click a
   sector to see the lap / sector time distribution, and pick a driver to compare against the field.

Live app: https://blank-app-t8weoxwxcf.streamlit.app/

## Data

| Data | Source | How it gets into the app |
|---|---|---|
| Grid slot + finish for every driver (Monaco 2000–2026, Mexico 2015–2026) | FastF1 → Jolpica-F1 (Ergast) | `data/grid_results.csv`, built by `scripts/build_data.py` |
| Track outline split into timing sectors | OpenF1 car positions + FastF1 (MultiViewer) rotation | `data/track_map.csv`, `data/corners.csv`, built by `scripts/build_data.py` |
| Clean race laps with sector times (2023–2026) | OpenF1 API | fetched on demand by `f1data.py`, cached for 24 h |

FastF1's own live-timing loader now requires an F1TV subscription, so lap timing and car
positions come from OpenF1's free historical API instead. No account is needed.

## Run it locally

Prerequisite: install [`uv`](https://docs.astral.sh/uv/).

```
uv sync
uv run streamlit run streamlit_app.py
```

Streamlit Community Cloud installs from `requirements.txt`. Locally, `pyproject.toml` is used by uv.

Refresh the pre-built data (installs the optional `data` group with FastF1):

```
uv run --group data python scripts/build_data.py              # everything
uv run --group data python scripts/build_data.py --only map   # just the track outline
```
