"""Lap / sector timing from the free OpenF1 API (https://openf1.org).

Shared by the Streamlit app (fetched on demand, then cached) and by
scripts/build_data.py (which uses the fastest lap to draw the track map).
FastF1's own live-timing loader now needs an F1TV subscription, so lap timing
comes from OpenF1's free historical endpoints instead.
"""

from __future__ import annotations

import time

import pandas as pd
import requests

OPENF1 = "https://api.openf1.org/v1"
OPENF1_CIRCUIT = {"Monaco": "Monte Carlo", "Mexico": "Mexico City"}
LAP_SEASONS = [2026, 2025, 2024, 2023]   # OpenF1 coverage starts in 2023
QUICK = 1.07                             # keep laps within 107% of the race's fastest lap


def openf1(endpoint: str, **params) -> list[dict]:
    """GET an OpenF1 endpoint, retrying on rate limits. 404 means 'no rows'."""
    for attempt in range(5):
        r = requests.get(f"{OPENF1}/{endpoint}", params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(2 + 2 * attempt)
            continue
        if r.status_code == 404:
            return []
        r.raise_for_status()
        time.sleep(0.35)
        return r.json()
    raise RuntimeError(f"OpenF1 {endpoint} kept rate-limiting")


def race_session(track: str, season: int) -> dict | None:
    sessions = openf1("sessions", year=season, circuit_short_name=OPENF1_CIRCUIT[track], session_name="Race")
    return sessions[0] if sessions else None


def clean_laps(track: str, season: int) -> tuple[pd.DataFrame, dict | None]:
    """Clean race laps for one race: no lap 1, no pit in/out laps, all sectors
    timed, and within 107% of the fastest lap (drops safety-car / traffic laps).

    Returns (laps, session) where laps has: driver, driver_name, team, lap,
    lap_time, s1, s2, s3 (+ driver_number, date_start for map building).
    """
    sess = race_session(track, season)
    if sess is None:
        return pd.DataFrame(), None
    key = sess["session_key"]
    laps = pd.DataFrame(openf1("laps", session_key=key))
    if laps.empty or "lap_duration" not in laps or laps["lap_duration"].isna().all():
        return pd.DataFrame(), sess
    drivers = pd.DataFrame(openf1("drivers", session_key=key)).drop_duplicates("driver_number")
    pits = pd.DataFrame(openf1("pit", session_key=key))

    laps = laps.dropna(subset=["lap_duration", "duration_sector_1", "duration_sector_2", "duration_sector_3"])
    laps = laps[(laps.lap_number > 1) & (~laps.is_pit_out_lap.fillna(False).astype(bool))]
    if not pits.empty:
        pit_in = set(zip(pits.driver_number, pits.lap_number))
        laps = laps[[(d, n) not in pit_in for d, n in zip(laps.driver_number, laps.lap_number)]]
    laps = laps[laps.lap_duration <= laps.lap_duration.min() * QUICK]

    info = drivers.set_index("driver_number") if not drivers.empty else pd.DataFrame()

    def field(n, col, default=""):
        return info.at[n, col] if n in info.index and col in info else default

    out = pd.DataFrame({
        "driver_number": laps.driver_number.astype(int).values,
        "driver": [field(n, "name_acronym", str(n)) for n in laps.driver_number],
        "driver_name": [f"{field(n, 'first_name')} {field(n, 'last_name')}".strip() or str(n)
                        for n in laps.driver_number],
        "team": [field(n, "team_name") for n in laps.driver_number],
        "lap": laps.lap_number.astype(int).values,
        "date_start": laps.date_start.values,
        "lap_time": laps.lap_duration.round(3).values,
        "s1": laps.duration_sector_1.round(3).values,
        "s2": laps.duration_sector_2.round(3).values,
        "s3": laps.duration_sector_3.round(3).values,
    })
    return out.reset_index(drop=True), sess
