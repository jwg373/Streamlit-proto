"""Track list, plus FastF1 sign-in, race lookup and clean race laps for the data build.

The Streamlit app only uses the track list; it never imports FastF1. Everything else
here is for scripts/build_data.py, which pre-builds all of data/ through FastF1, so
FastF1 is imported inside the functions that need it.

FastF1's timing data needs a signed-in Formula 1 account. Credentials are never
stored here: the build script reads them from .streamlit/secrets.toml (git-ignored).
The access token FastF1 gets back is kept in memory only.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

# The 2026 calendar, in round order: app name -> (dropdown label, Jolpica/Ergast circuit id).
# The 2026 Bahrain GP was run at Sepang, so it's listed as Malaysia.
TRACK_INFO = {
    "Australia":   ("Australia (Albert Park)", "albert_park"),
    "China":       ("China (Shanghai International Circuit)", "shanghai"),
    "Japan":       ("Japan (Suzuka)", "suzuka"),
    "Miami":       ("Miami (Miami International Autodrome)", "miami"),
    "Canada":      ("Canada (Circuit Gilles Villeneuve)", "villeneuve"),
    "Monaco":      ("Monaco (Circuit de Monaco)", "monaco"),
    "Barcelona":   ("Barcelona (Circuit de Barcelona-Catalunya)", "catalunya"),
    "Austria":     ("Austria (Red Bull Ring)", "red_bull_ring"),
    "Britain":     ("Britain (Silverstone)", "silverstone"),
    "Belgium":     ("Belgium (Spa-Francorchamps)", "spa"),
    "Hungary":     ("Hungary (Hungaroring)", "hungaroring"),
    "Netherlands": ("Netherlands (Zandvoort)", "zandvoort"),
    "Italy":       ("Italy (Monza)", "monza"),
    "Madrid":      ("Madrid (Madring)", "madring"),
    "Azerbaijan":  ("Azerbaijan (Baku City Circuit)", "baku"),
    "Malaysia":    ("Malaysia (Sepang)", "sepang"),
    "Singapore":   ("Singapore (Marina Bay)", "marina_bay"),
    "Austin":      ("Austin (Circuit of the Americas)", "americas"),
    "Mexico":      ("Mexico (Autódromo Hermanos Rodríguez)", "rodriguez"),
    "Brazil":      ("Brazil (Interlagos)", "interlagos"),
    "Las Vegas":   ("Las Vegas (Strip Circuit)", "vegas"),
    "Qatar":       ("Qatar (Lusail)", "losail"),
    "Abu Dhabi":   ("Abu Dhabi (Yas Marina)", "yas_marina"),
}
TRACKS = list(TRACK_INFO)
TRACK_LABEL = {t: v[0] for t, v in TRACK_INFO.items()}
ERGAST_CIRCUIT = {t: v[1] for t, v in TRACK_INFO.items()}

FIRST_TIMING_SEASON = 2018     # FastF1 lap timing starts in 2018
QUICK = 1.07                   # keep laps within 107% of the race's fastest lap
METRICS = {"lap_time": "LapTime", "s1": "Sector1Time", "s2": "Sector2Time", "s3": "Sector3Time"}

_signed_in = False


def setup_cache(path: str | Path | None = None) -> None:
    """FastF1's HTTP/parse cache (a temp dir unless a path is given)."""
    import fastf1

    path = Path(path) if path else Path(tempfile.gettempdir()) / "fastf1_cache"
    path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(path))


def sign_in(username: str, password: str) -> None:
    """Sign in to the F1 account FastF1 uses for timing data. The access token is kept in
    memory only (FastF1 would otherwise save it under the user's data folder)."""
    global _signed_in
    from fastf1.internals import f1account
    from fastf1.internals.f1account.login import login

    f1account.token_manager.store = lambda token: None
    f1account.token_manager.get(force_renew=True, auth_func=lambda: login(username, password))
    _signed_in = True


def is_signed_in() -> bool:
    if not _signed_in:
        return False
    from fastf1.internals import f1account
    token = f1account.token_manager.get_stored()
    return token is not None and token.is_valid()


def race_session(season: int, race_date: str):
    """The race session of the event held on race_date (YYYY-MM-DD, from Jolpica).
    Matched by date, since cancelled rounds can shift round numbers between sources."""
    import fastf1

    schedule = fastf1.get_event_schedule(season, include_testing=False)
    gap = (schedule.EventDate.dt.normalize() - pd.Timestamp(race_date)).abs()
    if gap.min() > pd.Timedelta(days=1):
        raise LookupError(f"No {season} event on {race_date} in FastF1's schedule")
    return fastf1.get_session(season, int(schedule.loc[gap.idxmin(), "RoundNumber"]), "R")


def load_race(season: int, race_date: str, telemetry: bool = False):
    session = race_session(season, race_date)
    session.load(laps=True, telemetry=telemetry, weather=False, messages=False)
    return session


def pick_clean(session):
    """Clean race laps (FastF1 Laps): green-flag laps only, no lap 1, no pit in/out laps,
    all three sectors timed, and within 107% of the race's fastest lap."""
    laps = session.laps
    laps = laps[laps.LapNumber > 1].pick_wo_box().pick_track_status("1")
    laps = laps.dropna(subset=list(METRICS.values()))
    return laps.pick_quicklaps(QUICK)


# tyre compounds, softest first. 2018 used Pirelli's absolute names (Hypersoft ... Superhard); from 2019
# each race's three dry compounds are just Soft / Medium / Hard (relative to what Pirelli brought).
COMPOUNDS = ["Hypersoft", "Ultrasoft", "Supersoft", "Soft", "Medium", "Hard", "Superhard",
             "Intermediate", "Wet", "Unknown"]


def compound_name(raw) -> str:
    """FastF1's compound code (e.g. 'SOFT', 'ULTRASOFT', 'TEST_UNKNOWN', NaN) as one of COMPOUNDS."""
    name = str(raw).strip().title() if isinstance(raw, str) else ""
    return name if name in COMPOUNDS else "Unknown"


def clean_laps(session) -> pd.DataFrame:
    """pick_clean() as a plain table: driver, driver_name, team, lap, lap_time, s1, s2, s3 (seconds),
    compound (see COMPOUNDS) and tyre_life (laps on that set of tyres, counting this one)."""
    laps = pick_clean(session)
    res = session.results.set_index("Abbreviation") if len(session.results) else pd.DataFrame()

    def field(abbr, col):
        return res.at[abbr, col] if abbr in res.index and col in res else ""

    out = pd.DataFrame({
        "driver": laps.Driver.values,
        "driver_name": [field(a, "FullName") or a for a in laps.Driver],
        "team": [field(a, "TeamName") for a in laps.Driver],
        "lap": laps.LapNumber.astype(int).values,
        **{m: laps[c].dt.total_seconds().round(3).values for m, c in METRICS.items()},
        "compound": [compound_name(c) for c in laps.Compound],
        "tyre_life": pd.to_numeric(laps.TyreLife, errors="coerce").round().astype("Int64").values,
    })
    return out.reset_index(drop=True)
