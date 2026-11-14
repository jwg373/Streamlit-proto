"""Pull Monaco + Mexico City data and write small CSVs to ./data.

The app reads these CSVs for the grid explorer and track map (lap timing is
fetched on demand from OpenF1, see f1data.py). Re-run this script to refresh:

    uv run --group data python scripts/build_data.py            # everything
    uv run --group data python scripts/build_data.py --only map

Sources (no account needed)
---------------------------
* Race results / grid slots: FastF1's Jolpica-F1 (Ergast) interface.
* Car positions for the track outline: the OpenF1 API (api.openf1.org).
  FastF1's own live-timing loader now needs an F1TV subscription. The app
  itself fetches lap/sector timing from OpenF1 on demand (see f1data.py).
* Track rotation + corner numbers: FastF1's MultiViewer interface (fastf1.mvapi).

Outputs
-------
data/grid_results.csv  one row per driver per race: grid slot and finish
data/track_map.csv     track outline (x, y) from the fastest race lap, tagged by sector
data/corners.csv       corner numbers and positions for map labels
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import fastf1
import fastf1.mvapi
import numpy as np
import pandas as pd
from fastf1.ergast import Ergast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from f1data import LAP_SEASONS, clean_laps, openf1  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = ROOT / ".fastf1_cache"

TRACKS = {
    "Monaco": {"ergast": "monaco"},
    "Mexico": {"ergast": "rodriguez"},
}
GRID_SEASONS = range(2000, 2027)          # race results history for the grid explorer

log = logging.getLogger("build_data")


# --------------------------------------------------------------------------- grid history
def grid_results() -> pd.DataFrame:
    ergast = Ergast()
    rows = []
    for track, cfg in TRACKS.items():
        for season in GRID_SEASONS:
            try:
                resp = ergast.get_race_results(season=season, circuit=cfg["ergast"])
            except Exception as exc:  # network hiccup
                log.warning("results %s %s: %s", track, season, exc)
                continue
            if not resp.content:      # no race that year
                continue
            df = resp.content[0]
            rows.append(pd.DataFrame({
                "track": track,
                "season": season,
                "driver": df["driverCode"].fillna(df["familyName"].str[:3].str.upper()),
                "driver_name": df["givenName"] + " " + df["familyName"],
                "team": df["constructorName"],
                "grid": df["grid"].astype(int),
                "position": df["position"].astype(int),
                "status": df["status"],
            }))
            log.info("results %s %s: %d drivers", track, season, len(df))
            time.sleep(0.3)  # stay under the Jolpica rate limit
    return pd.concat(rows, ignore_index=True)


# --------------------------------------------------------------------------- track map
def rotate(xy: np.ndarray, angle_deg: float) -> np.ndarray:
    a = np.deg2rad(angle_deg)
    rot = np.array([[np.cos(a), np.sin(a)], [-np.sin(a), np.cos(a)]])
    return xy @ rot


def track_maps():
    """Track outline from the fastest clean race lap (OpenF1 car positions), split into
    the official timing sectors, rotated like the TV graphics (fastf1.mvapi)."""
    map_out, corners_out = [], []
    for track in TRACKS:
        for season in LAP_SEASONS:          # newest first; fall back if positions are missing
            laps, sess = clean_laps(track, season)
            if laps.empty:
                continue
            fl = laps.loc[laps.lap_time.idxmin()]
            start = pd.Timestamp(fl.date_start).tz_convert("UTC").tz_localize(None)
            end = start + pd.Timedelta(seconds=fl.lap_time)
            fmt = "%Y-%m-%dT%H:%M:%S.%f"
            loc = pd.DataFrame(openf1("location", session_key=sess["session_key"],
                                      driver_number=int(fl.driver_number),
                                      **{"date>": start.strftime(fmt), "date<": end.strftime(fmt)}))
            if len(loc) < 50:
                log.warning("map %s %s: no position data, trying an earlier season", track, season)
                continue
            loc["t"] = (pd.to_datetime(loc.date, format="ISO8601").dt.tz_convert("UTC").dt.tz_localize(None)
                        - start).dt.total_seconds()
            loc = loc.sort_values("t")
            s1_end, s2_end = fl.s1, fl.s1 + fl.s2
            sector = np.where(loc.t <= s1_end, 1, np.where(loc.t <= s2_end, 2, 3))
            ci = fastf1.mvapi.get_circuit_info(year=season, circuit_key=sess["circuit_key"])
            rot = ci.rotation if ci is not None else 0.0
            xy = rotate(loc[["x", "y"]].to_numpy(dtype=float), rot)
            map_out.append(pd.DataFrame({"track": track, "season": season, "x": xy[:, 0], "y": xy[:, 1],
                                         "t": loc.t.values, "sector": sector}))
            if ci is not None:
                cxy = rotate(ci.corners[["X", "Y"]].to_numpy(dtype=float), rot)
                corners_out.append(pd.DataFrame({
                    "track": track,
                    "number": ci.corners["Number"].astype(str) + ci.corners["Letter"].fillna(""),
                    "x": cxy[:, 0], "y": cxy[:, 1],
                }))
            log.info("map %s from %s fastest lap (%s, %d points)", track, season, fl.driver, len(loc))
            break
    return pd.concat(map_out, ignore_index=True), pd.concat(corners_out, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=["grid", "map"], help="build just one part")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    fastf1.set_log_level("WARNING")
    CACHE.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE))

    if args.only in (None, "grid"):
        grid = grid_results()
        grid.to_csv(DATA / "grid_results.csv", index=False)
        print("\nGrid results:")
        print(grid.groupby("track")["season"].agg(["min", "max", "nunique"]))

    if args.only in (None, "map"):
        track_map, corners = track_maps()
        track_map.round(1).to_csv(DATA / "track_map.csv", index=False)
        corners.round(1).to_csv(DATA / "corners.csv", index=False)
        print("\nTrack map points:")
        print(track_map.groupby(["track", "sector"]).size())


if __name__ == "__main__":
    main()
