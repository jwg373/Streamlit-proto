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
* Track outline, rotation + corner numbers: FastF1's MultiViewer interface (fastf1.mvapi).

Outputs
-------
data/grid_results.csv  one row per driver per race: grid slot and finish
data/track_map.csv     track outline (x, y), tagged by timing sector
data/corners.csv       corner numbers and positions for map labels
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import fastf1
import numpy as np
import pandas as pd
from fastf1.ergast import Ergast
from fastf1.mvapi.api import get_circuit as mvapi_raw

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


REF_LAPS = 6          # fastest clean laps (one per driver) used to place the sector lines
# Rotation (degrees, counter-clockwise) that turns each outline to match the official 2026
# circuit map on formula1.com/en/racing/2026/<event>. Fitted once by overlaying each outline on
# that image; MultiViewer's own rotation is the fallback for a circuit missing here.
F1_ROTATION = {
    "Australia": 45,
    "China": 238,
    "Japan": 359,
    "Miami": 13,
    "Canada": 57,
    "Monaco": 315,
    "Barcelona": 324,
    "Austria": 9,
    "Britain": 270,
    "Belgium": 97,
    "Hungary": 309,
    "Netherlands": 359,
    "Italy": 95,
    "Madrid": 270,
    "Azerbaijan": 307,
    "Malaysia": 355,
    "Singapore": 0,
    "Austin": 354,
    "Mexico": 8,
    "Brazil": 270,
    "Las Vegas": 89,
    "Qatar": 61,
    "Abu Dhabi": 262,
}


def lap_positions(sess: dict, lap) -> pd.DataFrame:
    """OpenF1 car positions during one lap, with t = seconds since the lap started."""
    start = pd.Timestamp(lap.date_start).tz_convert("UTC").tz_localize(None)
    end = start + pd.Timedelta(seconds=lap.lap_time)
    fmt = "%Y-%m-%dT%H:%M:%S.%f"
    loc = pd.DataFrame(openf1("location", session_key=sess["session_key"], driver_number=int(lap.driver_number),
                              **{"date>": start.strftime(fmt), "date<": end.strftime(fmt)}))
    if loc.empty:
        return loc
    loc["t"] = (pd.to_datetime(loc.date, format="ISO8601").dt.tz_convert("UTC").dt.tz_localize(None)
                - start).dt.total_seconds()
    loc = loc[(loc.x != 0) | (loc.y != 0)]          # (0, 0) = no fix
    return loc.sort_values("t")[["t", "x", "y"]].reset_index(drop=True)


def position_at(loc: pd.DataFrame, t: float, max_gap: float = 1.5):
    """Car position at time t (linear interpolation), or None if the samples around t are too sparse."""
    i = np.searchsorted(loc.t.values, t)
    if i == 0 or i >= len(loc):
        return None
    a, b = loc.iloc[i - 1], loc.iloc[i]
    if b.t - a.t > max_gap:
        return None
    w = (t - a.t) / (b.t - a.t)
    return np.array([a.x + w * (b.x - a.x), a.y + w * (b.y - a.y)])


def circular_median(idx: list[int], n: int) -> int:
    """Median of indices on a closed loop of n points (picks the cut that keeps them together)."""
    idx = np.asarray(idx)
    ref = idx[0]
    shifted = (idx - ref + n // 2) % n
    return int((np.median(shifted) + ref - n // 2) % n)


def averaged_outline(lap_locs: list[pd.DataFrame], lap_times: list[float], n: int = 600) -> np.ndarray:
    """Outline for circuits MultiViewer doesn't cover: each lap resampled on lap fraction,
    then the per-fraction median across laps, lightly smoothed."""
    f = np.linspace(0, 1, n, endpoint=False)
    stack = []
    for loc, lt in zip(lap_locs, lap_times):
        frac = loc.t.values / lt
        gaps = np.diff(frac, prepend=frac[0])
        xs, ys = np.interp(f, frac, loc.x.values), np.interp(f, frac, loc.y.values)
        # blank out stretches where this lap had a gap in its samples (> 1.2 s)
        gap_mask = np.zeros(n, bool)
        for j in np.where(gaps * lt > 1.2)[0]:
            gap_mask |= (f > frac[j - 1]) & (f < frac[j])
        xs[gap_mask], ys[gap_mask] = np.nan, np.nan
        stack.append(np.c_[xs, ys])
    xy = np.nanmedian(np.stack(stack), axis=0)
    k = 5                                           # circular moving average
    pad = np.r_[xy[-k:], xy, xy[:k]]
    kernel = np.ones(2 * k + 1) / (2 * k + 1)
    return np.c_[np.convolve(pad[:, 0], kernel, "same"), np.convolve(pad[:, 1], kernel, "same")][k:-k]


def mv_circuit(season: int, circuit_key: int):
    try:
        return mvapi_raw(year=season, circuit_key=circuit_key)
    except Exception as exc:  # MultiViewer has no info for this circuit/year
        log.warning("multiviewer %s %s: %s", circuit_key, season, exc)
        return None


def track_maps(tracks: list[str]):
    """Track outline split into the official timing sectors, oriented like formula1.com's circuit maps.

    Shape: MultiViewer's track outline (fastf1.mvapi), a dense, clean trace of one lap.
    Circuits MultiViewer doesn't cover get a median of several OpenF1 laps instead.
    Start line and sector lines: where cars actually were at the lap start and at their
    sector 1 / sector 2 split times, over the REF_LAPS fastest clean laps (OpenF1)."""
    map_out, corners_out = [], []
    for track in tracks:
        for season in LAP_SEASONS:          # newest first; fall back if positions are missing
            try:
                laps, sess = clean_laps(track, season)
                if laps.empty:
                    continue
                ref = laps.sort_values("lap_time").drop_duplicates("driver").head(REF_LAPS)
                locs = [lap_positions(sess, lap) for lap in ref.itertuples()]
            except Exception as exc:        # keep going; this track keeps its old outline
                log.warning("map %s %s: %s", track, season, exc)
                break
            good = [(lap, loc) for lap, loc in zip(ref.itertuples(), locs) if len(loc) > 50]
            if len(good) < 2:
                log.warning("map %s %s: no position data, trying an earlier season", track, season)
                continue

            mv = mv_circuit(season, sess["circuit_key"])
            if mv is not None:
                outline, source = np.c_[mv["x"], mv["y"]].astype(float), f"MultiViewer {mv['year']}"
            else:
                outline = averaged_outline([l for _, l in good], [lap.lap_time for lap, _ in good])
                source = f"median of {len(good)} OpenF1 laps"
            n = len(outline)

            def nearest(pt):
                return int(np.argmin(((outline - pt) ** 2).sum(axis=1)))

            marks = {"start": [], "s1": [], "s2": []}
            for lap, loc in good:
                for name, t in (("start", 0.05), ("s1", lap.s1), ("s2", lap.s1 + lap.s2)):
                    pt = position_at(loc, t)
                    if pt is not None:
                        marks[name].append(nearest(pt))
            if not marks["s1"] or not marks["s2"]:
                log.warning("map %s %s: couldn't place sector lines, trying an earlier season", track, season)
                continue
            # start line: the lap-start position; if that's too sparse, the outline's own first point
            i0 = circular_median(marks["start"], n) if marks["start"] else 0
            i1, i2 = circular_median(marks["s1"], n), circular_median(marks["s2"], n)
            order = (np.arange(n) + i0) % n                     # re-start the outline at the start line
            pos = (np.arange(n))                                # position along the lap after re-starting
            b1, b2 = (i1 - i0) % n, (i2 - i0) % n
            if not 0 < b1 < b2 < n:
                log.warning("map %s %s: sector lines out of order (%d, %d of %d)", track, season, b1, b2, n)
                continue
            sector = np.where(pos < b1, 1, np.where(pos < b2, 2, 3))
            rot = float(F1_ROTATION.get(track, mv["rotation"] if mv is not None else 0.0))
            xy = rotate(outline[order], rot)
            # spread of the per-lap sector marks along the outline, as a share of the lap
            spread = max(np.ptp([(m - i + n // 2) % n - n // 2 for m in marks[k]]) if marks[k] else 0
                         for k, i in (("s1", i1), ("s2", i2))) / n
            map_out.append(pd.DataFrame({"track": track, "season": season, "x": xy[:, 0], "y": xy[:, 1],
                                         "sector": sector}))
            if mv is not None:
                cn = pd.DataFrame(mv["corners"])
                cxy = rotate(np.c_[[c["trackPosition"]["x"] for c in mv["corners"]],
                                   [c["trackPosition"]["y"] for c in mv["corners"]]], rot)
                corners_out.append(pd.DataFrame({
                    "track": track,
                    "number": cn["number"].astype(str) + cn.get("letter", pd.Series([""] * len(cn))).fillna(""),
                    "x": cxy[:, 0], "y": cxy[:, 1],
                }))
            log.info("map %s: %s outline (%d points), rotation %.0f, sectors from %s %d laps "
                     "(spread %.1f%% of a lap)", track, source, n, rot, season, len(good), spread * 100)
            break
    empty_map = pd.DataFrame(columns=["track", "season", "x", "y", "sector"])
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
