"""Pull data for every 2026 circuit and write small CSVs to ./data.

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
import f1data  # noqa: E402
from f1data import ERGAST_CIRCUIT, LAP_SEASONS, TRACKS, clean_laps, openf1  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = ROOT / ".fastf1_cache"

FIRST_SEASON = 2000                       # race results history for the grid explorer

log = logging.getLogger("build_data")


# --------------------------------------------------------------------------- grid history
def ergast_page(ergast: Ergast, season: int, offset: int):
    """One page (100 rows) of a season's race results, retrying when Jolpica rate-limits."""
    for attempt in range(6):
        try:
            return ergast.get_race_results(season=season, limit=100, offset=offset)
        except Exception as exc:
            wait = 5 * (attempt + 1)
            log.warning("results %s @%s: %s (retrying in %ss)", season, offset, exc, wait)
            time.sleep(wait)
    raise RuntimeError(f"Jolpica kept failing for {season} offset {offset}")


def grid_results() -> pd.DataFrame:
    """Every race result since FIRST_SEASON at the circuits in TRACKS. Paged by season
    (about 5 pages of 100 rows each), which keeps us well under Jolpica's rate limit."""
    ergast = Ergast()
    track_of = {cid: t for t, cid in ERGAST_CIRCUIT.items()}
    rows = []
    for season in range(FIRST_SEASON, pd.Timestamp.now().year + 1):
        offset, total = 0, 1
        while offset < total:
            page = ergast_page(ergast, season, offset)
            total = page.total_results
            offset += 100
            for (_, race), df in zip(page.description.iterrows(), page.content):
                track = track_of.get(race["circuitId"])
                if track is None:
                    continue
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
            time.sleep(0.8)  # stay under the Jolpica rate limit
        log.info("results %s: %d rows", season, total)
    grid = pd.concat(rows, ignore_index=True)
    return grid.sort_values(["track", "season", "position"], ignore_index=True)


# --------------------------------------------------------------------------- track map
def rotate(xy: np.ndarray, angle_deg: float) -> np.ndarray:
    a = np.deg2rad(angle_deg)
    rot = np.array([[np.cos(a), np.sin(a)], [-np.sin(a), np.cos(a)]])
    return xy @ rot


def track_maps(tracks: list[str]):
    """Track outline from the fastest clean race lap (OpenF1 car positions), split into
    the official timing sectors, rotated like the TV graphics (fastf1.mvapi)."""
    map_out, corners_out = [], []
    for track in tracks:
        for season in LAP_SEASONS:          # newest first; fall back if positions are missing
            try:
                laps, sess = clean_laps(track, season)
            except Exception as exc:        # keep going; this track keeps its old outline
                log.warning("map %s %s: %s", track, season, exc)
                break
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
            try:
                ci = fastf1.mvapi.get_circuit_info(year=season, circuit_key=sess["circuit_key"])
            except Exception as exc:  # MultiViewer has no info for this circuit/year
                log.warning("circuit info %s %s: %s", track, season, exc)
                ci = None
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
    empty_map = pd.DataFrame(columns=["track", "season", "x", "y", "t", "sector"])
    empty_cn = pd.DataFrame(columns=["track", "number", "x", "y"])
    return (pd.concat(map_out, ignore_index=True) if map_out else empty_map,
            pd.concat(corners_out, ignore_index=True) if corners_out else empty_cn)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=["grid", "map"], help="build just one part")
    parser.add_argument("--tracks", nargs="+", choices=TRACKS, metavar="TRACK",
                        help="rebuild the map for just these tracks (others keep their current outline)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    fastf1.set_log_level("WARNING")
    CACHE.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE))
    f1data.MIN_INTERVAL = 2.1           # ~28 calls a minute keeps OpenF1's free tier happy

    if args.only in (None, "grid"):
        grid = grid_results()
        grid.to_csv(DATA / "grid_results.csv", index=False)
        print("\nGrid results:")
        print(grid.groupby("track")["season"].agg(["min", "max", "nunique"]))

    if args.only in (None, "map"):
        track_map, corners = track_maps(args.tracks or TRACKS)
        built = set(track_map.track)
        # keep the existing outline for any track that wasn't (re)built this run
        for name, new in (("track_map", track_map), ("corners", corners)):
            path = DATA / f"{name}.csv"
            old = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=new.columns)
            old = old[old.track.isin(TRACKS) & ~old.track.isin(built)]
            out = pd.concat([old, new.round(1)], ignore_index=True)
            out["order"] = out.track.map(TRACKS.index)
            out.sort_values("order", kind="stable").drop(columns="order").to_csv(path, index=False)
        missing = [t for t in TRACKS if t not in built]
        if missing:
            print("\nNo new outline this run for:", ", ".join(missing))
        print("\nTrack map points this run:", track_map.groupby("track").size().to_dict())


if __name__ == "__main__":
    main()
