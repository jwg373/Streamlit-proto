# 🏁 F1 Circuit Explorer (Streamlit prototype)

Interactive prototype for exploring every circuit on the **2026 F1 calendar** (23 tracks, from
Albert Park to Yas Marina):

1. **Grid Explorer**: a map of the starting grid (P1–P20) for the selected track, coloured by
   win %, podium % or average finish from each slot. Click a slot for its details.
2. **Segment Explorer**: the real track outline split into its three timing sectors. Click a
   sector to see the lap / sector time distribution, and pick a driver to compare against the field.

Live app: https://blank-app-t8weoxwxcf.streamlit.app/

## Data

Everything comes from **FastF1**:

| Data | FastF1 source | How it gets into the app |
|---|---|---|
| Grid slot + finish for every driver at each circuit (2000–2026) | Jolpica-F1 (Ergast) interface | `data/grid_results.csv` |
| The field's lap / sector time distribution per race (2018–2026) | F1 live timing | `data/lap_bins.csv` (fine time bins), `data/lap_stats.csv`, `data/race_drivers.csv` |
| Track outline split into timing sectors | MultiViewer outline + car positions at the sector split times, oriented like formula1.com's circuit maps | `data/track_map.csv`, `data/corners.csv` |
| One driver's laps (the comparison overlay) | F1 live timing | loaded live when a driver is picked, cached for a day |

All `data/` files are built by `scripts/build_data.py`. The track list (app name, Jolpica
circuit id) lives in `TRACK_INFO` in `f1data.py`.

### F1 account credentials

FastF1's timing data needs a signed-in Formula 1 account. Copy
`.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` (git-ignored) and fill in
`[f1_credentials]`. Both the build script and the app read it from there; the access token
FastF1 gets back is kept in memory only. On Streamlit Community Cloud, paste the same
section into the app's **Settings → Secrets**. Without credentials the app still works;
only the live driver comparison is unavailable.

## Run it locally

Prerequisite: install [`uv`](https://docs.astral.sh/uv/).

```
uv sync
uv run streamlit run streamlit_app.py
```

Streamlit Community Cloud installs from `requirements.txt`. Locally, `pyproject.toml` is used by uv.

Refresh the pre-built data (needs the credentials above):

```
uv run python scripts/build_data.py                        # everything
uv run python scripts/build_data.py --only laps            # add races that aren't built yet
uv run python scripts/build_data.py --only map --tracks Hungary
```
