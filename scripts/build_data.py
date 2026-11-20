"""Pre-build the app's data for every 2026 circuit, all through FastF1, into ./data.

FastF1's timing data needs a signed-in F1 account. The script reads the same
credentials as the app, from .streamlit/secrets.toml:

    [f1_credentials]
    username = "..."
    password = "..."

(or the F1_USERNAME / F1_PASSWORD environment variables). The access token is
kept in memory only. Run it with:

    uv run --group data python scripts/build_data.py                  # everything
    uv run --group data python scripts/build_data.py --only laps      # add races not built yet
    uv run --group data python scripts/build_data.py --only map --tracks Hungary

Sources (all FastF1)
--------------------
* Race results / grid slots / race dates: FastF1's Jolpica-F1 (Ergast) interface.
* Lap and sector times, car positions: FastF1 timing (2018 onward).
* Track outline, rotation + corner numbers: FastF1's MultiViewer interface (fastf1.mvapi).

Outputs
-------
data/grid_results.csv  one row per driver per race: race date, grid slot and finish
data/laps.csv.gz       every clean race lap, 2018 onward: track, season, driver, lap,
                       lap / sector 1-3 times (s). The app's field and driver distributions
data/race_drivers.csv  who set clean laps in each race: name, team (fills the driver picker)
data/track_map.csv     track outline (x, y), tagged by timing sector
data/corners.csv       corner numbers and positions for map labels

The app itself never talks to FastF1: everything it shows is pre-built here, so it needs
no credentials and loads instantly.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import tomllib
from pathlib import Path

import fastf1
import numpy as np
import pandas as pd
from fastf1.ergast import Ergast
from fastf1.req import RateLimitExceededError
from fastf1.mvapi.api import get_circuit as mvapi_raw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from f1data import (  # noqa: E402
    ERGAST_CIRCUIT, FIRST_TIMING_SEASON, TRACKS, clean_laps, load_race, pick_clean, setup_cache, sign_in
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = ROOT / ".fastf1_cache"
SECRETS = ROOT / ".streamlit" / "secrets.toml"

FIRST_SEASON = 2000                       # race results history for the grid explorer
LAP_COLUMNS = ["track", "season", "driver", "lap", "lap_time", "s1", "s2", "s3"]
RACE_KEY = ["track", "season"]

log = logging.getLogger("build_data")


def sign_in_from_secrets() -> None:
    """Sign in with [f1_credentials] from .streamlit/secrets.toml, else F1_USERNAME / F1_PASSWORD."""
    if SECRETS.exists():
        creds = tomllib.loads(SECRETS.read_text()).get("f1_credentials", {})
        user, pw = creds.get("username"), creds.get("password")
    else:
        user, pw = os.environ.get("F1_USERNAME"), os.environ.get("F1_PASSWORD")
    if not user or not pw:
        sys.exit(f"No F1 account credentials: add [f1_credentials] to {SECRETS} "
                 "or set F1_USERNAME / F1_PASSWORD.")
    sign_in(user, pw)
    log.info("signed in to the F1 account")


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
                    "date": pd.Timestamp(race["raceDate"]).strftime("%Y-%m-%d"),
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


def timed_races(grid: pd.DataFrame, tracks: list[str]) -> pd.DataFrame:
    """Races with FastF1 lap timing (2018 onward) at the given tracks, newest first."""
    races = grid.loc[(grid.season >= FIRST_TIMING_SEASON) & grid.track.isin(tracks), ["track", "season", "date"]]
    return races.drop_duplicates(RACE_KEY).sort_values("season", ascending=False, ignore_index=True)


# --------------------------------------------------------------------------- laps
def race_drivers(track: str, season: int, laps: pd.DataFrame) -> pd.DataFrame:
    """Who set clean laps in one race, with their name and team (the driver picker)."""
    drivers = (laps.groupby(["driver", "driver_name", "team"]).size().rename("laps").reset_index()
               .assign(track=track, season=season))
    return drivers[["track", "season", "driver", "driver_name", "team", "laps"]]


def load_with_wait(season: int, date: str, telemetry: bool = False):
    """load_race(), waiting out FastF1's built-in limit of 500 API calls per hour when it's hit."""
    for attempt in range(8):
        try:
            return load_race(season, date, telemetry=telemetry)
        except RateLimitExceededError:
            log.info("FastF1's 500 calls/hour limit reached; waiting 10 minutes (attempt %d)", attempt + 1)
            time.sleep(600)
    raise RuntimeError("FastF1 rate limit didn't clear")


def lap_data(races: pd.DataFrame, laps_old: pd.DataFrame, drivers_old: pd.DataFrame):
    """Clean laps and driver lists for each race not already in laps_old. One failed race is
    skipped, not fatal."""
    done = set(map(tuple, laps_old[RACE_KEY].drop_duplicates().to_numpy())) if len(laps_old) else set()
    if len(drivers_old):   # keep driver rows only for races whose laps are kept
        drivers_old = drivers_old[[tuple(k) in done for k in drivers_old[RACE_KEY].to_numpy()]]
    laps_out, drivers_out = [laps_old], [drivers_old]
    for r in races.itertuples():
        if (r.track, r.season) in done:
            continue
        try:
            laps = clean_laps(load_with_wait(r.season, r.date))
        except Exception as exc:
            log.warning("laps %s %s: %s", r.track, r.season, exc)
            continue
        if len(laps) < 20:
            log.warning("laps %s %s: only %d clean laps, skipped", r.track, r.season, len(laps))
            continue
        laps_out.append(laps.assign(track=r.track, season=r.season)[LAP_COLUMNS])
        drivers_out.append(race_drivers(r.track, r.season, laps))
        log.info("laps %s %s: %d clean laps from %d drivers", r.track, r.season, len(laps), laps.driver.nunique())
    return (pd.concat([d for d in laps_out if len(d)], ignore_index=True),
            pd.concat([d for d in drivers_out if len(d)], ignore_index=True))


# --------------------------------------------------------------------------- track map
def rotate(xy: np.ndarray, angle_deg: float) -> np.ndarray:
    a = np.deg2rad(angle_deg)
    rot = np.array([[np.cos(a), np.sin(a)], [-np.sin(a), np.cos(a)]])
    return xy @ rot


REF_LAPS = 6          # fastest clean laps (one per driver) used to place the sector lines
# Position-data timestamp corrections (seconds) for sessions on circuits without a MultiViewer
# outline, where there is no known finish line to line them up on automatically. Sepang 2026's
# position data runs 19 s off its lap timing; the value was fitted so the start and sector lines
# match the formula1.com 2026 circuit map.
POSITION_TIME_FIX = {("Malaysia", 2026): 19.0}
# Rotation (degrees, counter-clockwise) that turns each outline to match the official 2026
# circuit map on formula1.com/en/racing/2026/<event>. Fitted once by overlaying each outline on
# that image; MultiViewer's own rotation is the fallback for a circuit missing here.
F1_ROTATION = {
    "Australia": 45, "China": 238, "Japan": 359, "Miami": 13, "Canada": 57, "Monaco": 315,
    "Barcelona": 324, "Austria": 9, "Britain": 270, "Belgium": 97, "Hungary": 309, "Netherlands": 359,
    "Italy": 95, "Madrid": 270, "Azerbaijan": 307, "Malaysia": 355, "Singapore": 0, "Austin": 354,
    "Mexico": 8, "Brazil": 270, "Las Vegas": 89, "Qatar": 61, "Abu Dhabi": 262,
}


def lap_positions(session, lap, pad: float = 8.0) -> pd.DataFrame:
    """FastF1 car positions from `pad` s before to `pad` s after one lap, with t = seconds since the
    lap started (negative before it). The padding shows the car crossing the line at both ends."""
    pos = session.pos_data[lap.DriverNumber]
    t = (pos.SessionTime - lap.LapStartTime).dt.total_seconds()
    keep = (t > -pad) & (t < lap.LapTime.total_seconds() + pad) & ((pos.X != 0) | (pos.Y != 0))
    return pd.DataFrame({"t": t[keep].values, "x": pos.X[keep].values, "y": pos.Y[keep].values})


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


def finish_line_offset(loc: pd.DataFrame, lap_time: float, outline: np.ndarray, i0: int) -> float | None:
    """Seconds by which this lap's position timestamps run behind (+) or ahead (-) of its timing,
    within half a lap.

    The car should cross the start/finish line (outline index i0) at t = 0 and t = lap_time.
    Finds where it actually does in this lap's (padded) position data, as signed track index going
    from negative (before the line) to positive, and takes the gap modulo one lap. Some sessions
    are well off: ~1.9 s at the Red Bull Ring 2026, ~23 s at Sepang 2026."""
    n = len(outline)
    if len(loc) < 4:
        return None
    idx = np.array([int(np.argmin(((outline - p) ** 2).sum(1))) for p in loc[["x", "y"]].to_numpy()])
    signed = (idx - i0 + n // 2) % n - n // 2        # points before the line < 0, after it >= 0
    cross = np.where((signed[:-1] < 0) & (signed[1:] >= 0) & (np.abs(np.diff(signed)) < n // 4))[0]
    if not len(cross):
        return None
    offs = []
    for j in cross:
        t0, t1, d0, d1 = loc.t.iloc[j], loc.t.iloc[j + 1], signed[j], signed[j + 1]
        t_line = t0 + (t1 - t0) * (-d0) / (d1 - d0) if d1 != d0 else t0
        offs.append((t_line + lap_time / 2) % lap_time - lap_time / 2)
    return float(min(offs, key=abs))


def wrap_time(loc: pd.DataFrame, t: float, lap_time: float) -> float:
    """Bring t inside this lap's position data by whole laps (for large timestamp offsets)."""
    while t > loc.t.max() and t - lap_time >= loc.t.min():
        t -= lap_time
    while t < loc.t.min() and t + lap_time <= loc.t.max():
        t += lap_time
    return t


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


def track_maps(races: pd.DataFrame, tracks: list[str]):
    """Track outline split into the official timing sectors, oriented like formula1.com's circuit maps.

    Shape: MultiViewer's track outline (fastf1.mvapi), a dense, clean trace of one lap.
    Circuits MultiViewer doesn't cover get a median of several laps' car positions instead.
    Start line: MultiViewer's index 0, which is the finish line (without MultiViewer: where cars
    are at the start of each lap, with the position timestamps corrected at lights out). Sector lines: where cars actually were at their sector 1 /
    sector 2 split times, over the REF_LAPS fastest clean laps, with each lap's position timestamps
    first lined up on the start/finish line (some sessions' position data runs off the lap timing,
    by up to ~20 s at Sepang 2026)."""
    map_out, corners_out = [], []
    for track in tracks:
        for r in races[races.track == track].itertuples():     # newest first
            try:
                session = load_with_wait(r.season, r.date, telemetry=True)
                clean = pick_clean(session)
                ref = clean.sort_values("LapTime").drop_duplicates("Driver").head(REF_LAPS)
                good = []
                for _, lap in ref.iterlaps():
                    loc = lap_positions(session, lap)
                    if len(loc) > 50:
                        good.append((lap.Sector1Time.total_seconds(), lap.Sector2Time.total_seconds(),
                                     lap.LapTime.total_seconds(), loc))
                circuit_key = session.session_info["Meeting"]["Circuit"]["Key"]
            except Exception as exc:        # try an earlier season
                log.warning("map %s %s: %s", track, r.season, exc)
                continue
            if len(good) < 2:
                log.warning("map %s %s: no position data, trying an earlier season", track, r.season)
                continue

            mv = mv_circuit(r.season, circuit_key)
            if mv is not None:
                outline, source = np.c_[mv["x"], mv["y"]].astype(float), f"MultiViewer {mv['year']}"
            else:
                outline = averaged_outline([g[3] for g in good], [g[2] for g in good])
                source = f"median of {len(good)} laps"
            n = len(outline)

            def nearest(pt):
                return int(np.argmin(((outline - pt) ** 2).sum(axis=1)))

            # start line: MultiViewer's index 0 (its trace starts on the finish line)
            if mv is not None:
                i0, start_src = 0, "MultiViewer"
            else:
                # Without MultiViewer: where the cars are as each lap starts. Their position
                # timestamps can't be checked against a known finish line here, so a session known
                # to be off gets a fixed correction (POSITION_TIME_FIX)
                shift = POSITION_TIME_FIX.get((track, int(r.season)), 0.0)
                starts = [position_at(g[3], wrap_time(g[3], g[2] + shift, g[2])) for g in good]
                starts = [nearest(p) for p in starts if p is not None]
                if not starts:
                    log.warning("map %s %s: can't place the start line, trying an earlier season", track, r.season)
                    continue
                i0, start_src = circular_median(starts, n), f"lap starts (timestamps {shift:+.1f} s)"
            # sector lines: car positions at the sector split times, after lining each lap's
            # position timestamps up on the start/finish line
            marks, offsets = {"s1": [], "s2": []}, []
            for s1, s2, lt, loc in good:
                off = finish_line_offset(loc, lt, outline, i0)
                if off is None:
                    continue
                offsets.append(off)
                for name, t in (("s1", s1 + off), ("s2", s1 + s2 + off)):
                    pt = position_at(loc, wrap_time(loc, t, lt))
                    if pt is not None:
                        marks[name].append(nearest(pt))
            if not marks["s1"] or not marks["s2"]:
                log.warning("map %s %s: couldn't place sector lines, trying an earlier season", track, r.season)
                continue
            i1, i2 = circular_median(marks["s1"], n), circular_median(marks["s2"], n)
            note = f"start from {start_src}, timestamp offset {np.median(offsets):+.2f} s over {len(offsets)} laps"
            order = (np.arange(n) + i0) % n                     # re-start the outline at the start line
            b1, b2 = (i1 - i0) % n, (i2 - i0) % n
            spread = max(np.ptp([(m - i + n // 2) % n - n // 2 for m in marks[k]]) if marks[k] else 0
                         for k, i in (("s1", i1), ("s2", i2))) / n
            if spread > 0.015:
                log.warning("map %s %s: sector marks disagree by %.1f%% of a lap (patchy position data), "
                            "trying an earlier season", track, r.season, spread * 100)
                continue
            if not 0 < b1 < b2 < n:
                log.warning("map %s %s: sector lines out of order (%d, %d of %d)", track, r.season, b1, b2, n)
                continue
            pos = np.arange(n)
            sector = np.where(pos < b1, 1, np.where(pos < b2, 2, 3))
            rot = float(F1_ROTATION.get(track, mv["rotation"] if mv is not None else 0.0))
            xy = rotate(outline[order], rot)
            map_out.append(pd.DataFrame({"track": track, "season": r.season, "x": xy[:, 0], "y": xy[:, 1],
                                         "sector": sector}))
            if mv is not None:
                cn = pd.DataFrame(mv["corners"])
                cxy = rotate(np.c_[[c["trackPosition"]["x"] for c in mv["corners"]],
                                   [c["trackPosition"]["y"] for c in mv["corners"]]], rot)
                letters = cn["letter"].fillna("") if "letter" in cn else ""
                corners_out.append(pd.DataFrame({"track": track, "number": cn["number"].astype(str) + letters,
                                                 "x": cxy[:, 0], "y": cxy[:, 1]}))
            log.info("map %s: %s outline (%d points), rotation %.0f, sectors from %s %d laps "
                     "(spread %.1f%% of a lap, %s)", track, source, n, rot, r.season, len(good), spread * 100, note)
            break
    empty_map = pd.DataFrame(columns=["track", "season", "x", "y", "sector"])
    empty_cn = pd.DataFrame(columns=["track", "number", "x", "y"])
    return (pd.concat(map_out, ignore_index=True) if map_out else empty_map,
            pd.concat(corners_out, ignore_index=True) if corners_out else empty_cn)


def write_merged(name: str, new: pd.DataFrame, replaced_tracks: set[str]) -> None:
    """Write data/<name>.csv: rows for replaced_tracks come from `new`, other tracks keep their old rows."""
    path = DATA / f"{name}.csv"
    old = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=new.columns)
    old = old[old.track.isin(TRACKS) & ~old.track.isin(replaced_tracks)]
    out = pd.concat([old, new.round(1)], ignore_index=True)
    out["order"] = out.track.map(TRACKS.index)
    out.sort_values("order", kind="stable").drop(columns="order").to_csv(path, index=False)


def read_or_empty(name: str) -> pd.DataFrame:
    path = DATA / f"{name}.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=["grid", "laps", "map"], help="build just one part")
    parser.add_argument("--tracks", nargs="+", choices=TRACKS, metavar="TRACK",
                        help="limit lap/map building to these tracks (others keep their current data)")
    parser.add_argument("--rebuild", action="store_true",
                        help="rebuild lap aggregates for races already in data/ (default: only add new races)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    log.setLevel(logging.INFO)
    fastf1.set_log_level("ERROR")
    DATA.mkdir(exist_ok=True)
    setup_cache(CACHE)
    tracks = args.tracks or TRACKS

    if args.only in (None, "grid"):
        grid = grid_results()
        grid.to_csv(DATA / "grid_results.csv", index=False)
        print("\nGrid results:")
        print(grid.groupby("track")["season"].agg(["min", "max", "nunique"]))
    grid = pd.read_csv(DATA / "grid_results.csv")
    races = timed_races(grid, tracks)

    if args.only in (None, "laps", "map"):
        sign_in_from_secrets()

    if args.only in (None, "laps"):
        laps_path = DATA / "laps.csv.gz"
        laps_old = pd.read_csv(laps_path) if laps_path.exists() else pd.DataFrame(columns=LAP_COLUMNS)
        drivers_old = read_or_empty("race_drivers")
        if args.rebuild:   # drop the races we're about to rebuild
            laps_old = laps_old[~laps_old.track.isin(tracks)]
            drivers_old = drivers_old[~drivers_old.track.isin(tracks)] if len(drivers_old) else drivers_old
        laps, drivers = lap_data(races, laps_old, drivers_old)

        def in_order(df):
            df = df.assign(order=df.track.map(TRACKS.index))
            sort = ["order", "season", "driver"] + (["lap"] if "lap" in df else [])
            asc = [True, False, True] + ([True] if "lap" in df else [])
            return df.sort_values(sort, ascending=asc, kind="stable").drop(columns="order")

        # mtime=0 keeps the gzip bytes identical when the laps haven't changed (no git churn)
        in_order(laps).to_csv(laps_path, index=False, compression={"method": "gzip", "mtime": 0})
        in_order(drivers).to_csv(DATA / "race_drivers.csv", index=False)
        print(f"\nLaps: {laps.groupby(RACE_KEY).ngroups} races, {len(laps):,} clean laps "
              f"({laps_path.stat().st_size / 1e6:.1f} MB)")
        missing = sorted(set(map(tuple, races[RACE_KEY].to_numpy())) - set(map(tuple, laps[RACE_KEY].to_numpy())))
        if missing:
            print("No lap data for:", ", ".join(f"{t} {s}" for t, s in missing))

    if args.only in (None, "map"):
        track_map, corners = track_maps(races, tracks)
        built = set(track_map.track)
        write_merged("track_map", track_map, built)
        write_merged("corners", corners, built)
        missing = [t for t in tracks if t not in built]
        if missing:
            print("\nNo new outline this run for:", ", ".join(missing))
        print("\nTrack map points this run:", track_map.groupby("track").size().to_dict())


if __name__ == "__main__":
    main()
