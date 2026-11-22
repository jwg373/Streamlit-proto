"""F1 Circuit Explorer: Streamlit prototype covering every circuit on the 2026 F1 calendar.

All data comes from FastF1, pre-built into ./data by scripts/build_data.py: grid
history, track outlines and every clean race lap since 2018 (data/laps.csv.gz). The
app itself never calls FastF1, so it needs no credentials and no network access.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from f1data import COMPOUNDS, TRACK_LABEL, TRACKS

st.set_page_config(page_title="F1 Circuit Explorer", page_icon="🏁", layout="wide")

DATA = Path(__file__).parent / "data"
GRID_SLOTS = 20
METRICS = {"win": "Win %", "podium": "Podium %", "finish": "Avg finish"}
SECTORS = {0: "Full lap", 1: "Sector 1", 2: "Sector 2", 3: "Sector 3"}

# palette (validated categorical slots + one-hue blue ramp)
BLUE, ORANGE, F1_RED = "#2a78d6", "#eb6834", "#e10600"
SEQ_LO, SEQ_HI = (205, 226, 251), (13, 54, 107)
SECTOR_COLORS = {1: "#2a78d6", 2: "#1baf7a", 3: "#6250d6"}
ASPHALT, PAINT, MUTED = "#3b3b39", "#f4f4f0", "#898781"
GAIN, LOSS = "#1a9e5c", "#d93a2b"   # faster / slower than the field
# one colour per compared driver (neither is the field's blue); more than two curves gets too busy
DRIVER_COLORS = ["#eb6834", "#d6336c"]
MAX_DRIVERS = len(DRIVER_COLORS)
MIN_CURVE_LAPS = 15      # fewer field laps than this on a tyre: bars only, no smoothed curve

HELP = {
    "grid": "A map of the starting grid. Each slot is coloured by how drivers starting there "
            "have done at this track (win %, podium % or average finish; pick one under the map). "
            "Darker = better. The small +/− in each slot's corner is how many places the slot moves "
            "when the grid is sorted by that metric (ties keep grid order; blank = no change). "
            "Click a slot to see its details.",
    "segment": "The track is split into its three official timing sectors. Click a sector on the "
               "map (or use the buttons) to update the time distribution.",
    "dist": "Bars and the blue curve show every clean race lap for the selected season. "
            f"Pick up to {MAX_DRIVERS} drivers to overlay their own curves, each in its own colour; "
            "left of the field = faster. Remove a driver with the × on their name. The tyre buttons keep "
            "only laps on that compound (for the field and the drivers). Harder tyres are often run later in "
            "the race on less fuel, so they can look quicker than softer ones.",
}

st.markdown(
    f"""
    <style>
      .block-container {{ padding-top: 2.2rem; max-width: 1250px; }}
      h1.title {{ font-size: 1.9rem; margin: 0; }}
      .rule {{ border-top: 3px solid {F1_RED}; margin: 0.2rem 0 0.6rem; }}
      .badge {{ background:{F1_RED}; color:#fff; border-radius:4px; padding:0 7px; margin-right:6px; font-size:0.85em; }}
      div[data-testid="stMetricValue"] {{ font-size: 1.6rem; }}
      .st-key-gap_faster div[data-testid="stMetricValue"] {{ color: {GAIN}; font-size: 1.35rem; }}
      .st-key-gap_slower div[data-testid="stMetricValue"] {{ color: {LOSS}; font-size: 1.35rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- data
@st.cache_data
def load_data():
    names = ("grid_results", "track_map", "corners", "race_drivers")
    laps = pd.read_csv(DATA / "laps.csv.gz")
    return (*(pd.read_csv(DATA / f"{name}.csv") for name in names), laps)


GRID, TRACK_MAP, CORNERS, RACE_DRIVERS, LAPS = load_data()


@st.cache_data
def race_laps(track: str, season: int) -> pd.DataFrame:
    """Every clean lap of one race (pre-built)."""
    return LAPS[(LAPS.track == track) & (LAPS.season == season)].reset_index(drop=True)


@st.cache_data
def segment_laps(track: str, season: int, tyre: str = "All") -> pd.DataFrame:
    """The race's clean laps, optionally only those on one tyre compound."""
    laps = race_laps(track, season)
    return laps if tyre == "All" else laps[laps.compound == tyre].reset_index(drop=True)


def field_bins(track: str, season: int, metric: str, tyre: str = "All") -> tuple[np.ndarray, np.ndarray]:
    """The field's clean laps for one race as (time, weight); every lap counts once."""
    t = segment_laps(track, season, tyre)[metric].to_numpy(float)
    return t, np.ones_like(t)


def field_stat(track: str, season: int, metric: str, stat: str, tyre: str = "All") -> float:
    t = segment_laps(track, season, tyre)[metric]
    if t.empty:
        return np.nan
    return float(t.median() if stat == "median" else t.min())


def weighted_percentile(values: np.ndarray, weights: np.ndarray, q: list[float]) -> np.ndarray:
    order = np.argsort(values)
    cum = np.cumsum(weights[order]) / weights.sum() * 100
    return np.interp(q, cum, values[order])


@st.cache_data
def grid_stats(track: str) -> pd.DataFrame:
    g = GRID[(GRID.track == track) & (GRID.grid.between(1, GRID_SLOTS))]
    stats = g.groupby("grid").agg(
        races=("position", "size"),
        win=("position", lambda p: (p == 1).mean()),
        podium=("position", lambda p: (p <= 3).mean()),
        finish=("position", "mean"),
    )
    return stats.reindex(range(1, GRID_SLOTS + 1))


def fmt_metric(metric: str, v: float) -> str:
    if pd.isna(v):
        return "–"
    return f"P{v:.1f}" if metric == "finish" else f"{v:.0%}"


def fmt_time(s: float, lap: bool) -> str:
    if pd.isna(s):
        return "–"
    if lap:
        return f"{int(s // 60)}:{s % 60:06.3f}"
    return f"{s:.3f}s"


def seq_color(t: float) -> str:
    t = float(np.clip(t, 0, 1))
    r, g, b = (round(lo + (hi - lo) * t) for lo, hi in zip(SEQ_LO, SEQ_HI))
    return f"rgb({r},{g},{b})"


def kde(values: np.ndarray, xs: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    """Gaussian KDE (Silverman bandwidth), returned as a density. `weights` lets binned data
    (bin time, lap count) stand in for the individual laps."""
    w = np.ones_like(values, dtype=float) if weights is None else np.asarray(weights, dtype=float)
    keep = ~np.isnan(values)
    values, w = values[keep], w[keep]
    n = w.sum()
    if n < 2:
        return np.zeros_like(xs)
    mean = (values * w).sum() / n
    std = np.sqrt((w * (values - mean) ** 2).sum() / n)
    bw = 1.06 * std * n ** (-1 / 5) or 0.05
    z = (xs[:, None] - values[None, :]) / bw
    return (w * np.exp(-0.5 * z**2)).sum(axis=1) / (n * bw * np.sqrt(2 * np.pi))


# --------------------------------------------------------------------------- state
DEFAULTS = {"track": "Monaco", "metric": "win", "grid": 1, "sector": 0, "drivers": [], "season": None,
            "tyre": "All"}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, list(v) if isinstance(v, list) else v)
st.session_state.setdefault("nonce", 0)          # bump to clear chart click selections


def reset(*keys: str) -> None:
    for k in keys or DEFAULTS:
        st.session_state[k] = list(DEFAULTS[k]) if isinstance(DEFAULTS[k], list) else DEFAULTS[k]
    st.session_state.nonce += 1


def _clicked(chart_key: str):
    """customdata[0] of the clicked point in a plotly chart selection, or None."""
    sel = st.session_state.get(chart_key)
    pts = (sel or {}).get("selection", {}).get("points", []) if sel else []
    if not pts or "customdata" not in pts[0]:
        return None
    cd = pts[0]["customdata"]
    return int(cd[0] if isinstance(cd, (list, tuple)) else cd)


def on_grid_click() -> None:
    gp = _clicked(f"gridmap_{st.session_state.nonce}")
    if gp is not None:
        st.session_state.grid = gp


def on_map_click() -> None:
    s = _clicked(f"trackmap_{st.session_state.track}_{st.session_state.nonce}")
    if s is not None:
        st.session_state.sector = s


def on_sector_change() -> None:
    if st.session_state.sector is None:  # segmented control toggled off -> full lap
        st.session_state.sector = 0


def on_track_change() -> None:
    st.session_state.season = None
    st.session_state.drivers = []
    st.session_state.tyre = "All"
    st.session_state.grid = 1
    st.session_state.sector = 0
    st.session_state.nonce += 1


@st.dialog("F1 Primer")
def primer() -> None:
    st.markdown(
        """
**Grid position**: where a driver starts the race. P1 (*pole position*) is the front of the
grid, earned with the fastest qualifying lap. Cars line up in two staggered columns.

**Win % / Podium %**: share of races won (or finished in the top 3) by drivers who started
from that grid slot at this track.

**Average finish**: mean finishing position from that slot (lower is better). Retirements
count at the position they were classified in.

**Sectors**: every circuit is split into three timed sectors. Comparing sector times
shows where on the lap a driver gains or loses time.

**Time distribution**: how lap or sector times are spread across the field. Only clean
race laps are used (no lap 1, pit laps, safety-car laps or other slow laps).
        """
    )


# --------------------------------------------------------------------------- header
h1, h2, h3, h4 = st.columns([0.9, 2.2, 3.4, 1.0], vertical_alignment="center")
with h1:
    st.button("Reset ↺", on_click=reset, use_container_width=True, help="Reset every view")
with h2:
    st.selectbox("Select track", TRACKS, key="track", format_func=lambda t: TRACK_LABEL[t],
                 on_change=on_track_change)
with h3:
    st.markdown("<h1 class='title' style='text-align:right'>F1 Circuit Explorer</h1>"
                "<div style='text-align:right;color:#898781'>Grid position &amp; sector times · "
                "data via FastF1</div>", unsafe_allow_html=True)
with h4:
    if st.button("F1 Primer", type="primary", use_container_width=True):
        primer()
st.markdown("<div class='rule'></div>", unsafe_allow_html=True)

track = st.session_state.track
nonce = st.session_state.nonce

# --------------------------------------------------------------------------- 1. grid explorer
stats = grid_stats(track)
seasons_grid = GRID.loc[GRID.track == track, "season"]

c1, c3 = st.columns([3.8, 1.2], vertical_alignment="bottom")
with c1:
    st.markdown("### <span class='badge'>1</span>Grid Explorer", unsafe_allow_html=True, help=HELP["grid"])
with c3:
    st.button("Reset grid ↺", key="reset_grid", on_click=reset, args=("metric", "grid"),
              use_container_width=True)
metric = st.session_state.metric   # the selector itself sits under the grid map


def metric_places(vals: pd.Series, metric: str) -> dict[int, int]:
    """Each grid slot's place when the slots with data are sorted best first on the metric (higher
    win/podium %, lower avg finish). Ties go to the higher grid slot, so tied slots keep grid order."""
    v = vals.dropna()
    order = sorted(v.index, key=lambda gp: (v[gp] if metric == "finish" else -v[gp], gp))
    return {int(gp): i + 1 for i, gp in enumerate(order)}


def place_shifts(places: dict[int, int]) -> dict[int, int]:
    """Places gained (+) or lost (−) versus grid order: P2 sorted 1st -> +1, P1 sorted 2nd -> −1.
    Compared with each slot's order among the slots with data, so a slot with no starts shifts nothing."""
    return {gp: i + 1 - places[gp] for i, gp in enumerate(sorted(places))}


def grid_figure(stats: pd.DataFrame, metric: str, selected: int) -> go.Figure:
    vals = stats[metric]
    places = metric_places(vals, metric)
    shifts = place_shifts(places)
    lo, hi = np.nanmin(vals), np.nanmax(vals)
    if metric == "finish":
        norm = lambda v: (hi - v) / (hi - lo) if hi > lo else 0.5  # noqa: E731  lower finish = darker
    else:
        norm = lambda v: v / hi if hi > 0 else 0  # noqa: E731

    fig = go.Figure()
    cols = GRID_SLOTS // 2
    slot_w, slot_h = 0.78, 0.8
    front_x = 0.0
    shapes = [dict(type="rect", x0=-cols - 0.25, x1=front_x + 0.75, y0=-0.62, y1=1.62,
                   fillcolor=ASPHALT, line_width=0, layer="below")]
    # chequered start/finish line
    for i in range(12):
        for j in range(2):
            shapes.append(dict(type="rect", x0=front_x + 0.3 + j * 0.15, x1=front_x + 0.45 + j * 0.15,
                               y0=-0.55 + i * 0.18, y1=-0.55 + (i + 1) * 0.18, line_width=0, layer="below",
                               fillcolor=PAINT if (i + j) % 2 == 0 else "#111"))
    shapes.append(dict(type="line", x0=-cols, x1=front_x + 0.2, y0=0.5, y1=0.5, layer="below",
                       line=dict(color="rgba(244,244,240,.35)", width=1.5, dash="dash")))
    xs, ys, texts, colors_txt, custom = [], [], [], [], []
    for gp in range(1, GRID_SLOTS + 1):
        col, even = (gp - 1) // 2, gp % 2 == 0
        xc = front_x - col - (0.5 if even else 0) - slot_w / 2
        yc = 0 if even else 1
        v, r = vals.get(gp), stats.at[gp, "races"]
        has = not pd.isna(v)
        fill = seq_color(norm(v)) if has else "#5a5a57"
        # painted grid box (front line + side ticks)
        x_front = xc + slot_w / 2 + 0.06
        shapes.append(dict(type="path", layer="below", line=dict(color=PAINT, width=2),
                           path=f"M {x_front - 0.14},{yc + slot_h / 2 + 0.04} L {x_front},{yc + slot_h / 2 + 0.04} "
                                f"L {x_front},{yc - slot_h / 2 - 0.04} L {x_front - 0.14},{yc - slot_h / 2 - 0.04}"))
        shapes.append(dict(type="rect", x0=xc - slot_w / 2, x1=xc + slot_w / 2, y0=yc - slot_h / 2,
                           y1=yc + slot_h / 2, fillcolor=fill, layer="below",
                           line=dict(color=F1_RED if gp == selected else fill, width=2 if gp == selected else 0)))
        dark = has and norm(v) > 0.45
        txt_color = "#ffffff" if (dark or not has) else "#0b0b0b"
        xs.append(xc); ys.append(yc)
        texts.append(f"<b>P{gp}</b><br>{fmt_metric(metric, v)}")
        colors_txt.append(txt_color)
        shift = shifts.get(gp, 0)
        if shift:   # places gained / lost when sorted on the metric: a small badge in the bottom-right corner
            # sized and offset in pixels from the box corner, so it stays inside however wide the grid is drawn
            label = f"{shift:+d}".replace("-", "−")
            d, inset = 17, 2                       # badge height and gap from the box edges (px)
            w = d if abs(shift) < 10 else d + 5    # a slightly wider oval for two digits
            right, bottom = xc + slot_w / 2, yc - slot_h / 2
            shapes.append(dict(type="circle", xref="x", yref="y", layer="above",
                               xsizemode="pixel", ysizemode="pixel", xanchor=right, yanchor=bottom,
                               x0=-inset - w, x1=-inset, y0=inset, y1=inset + d,
                               fillcolor=GAIN if shift > 0 else LOSS, line=dict(width=0)))
            fig.add_annotation(x=right, y=bottom, text=f"<b>{label}</b>", showarrow=False, xanchor="center",
                               yanchor="middle", xshift=-inset - w / 2, yshift=inset + d / 2,
                               font=dict(size=10, color="#ffffff"))
        place = (f"<br>Sorted by {METRICS[metric]}: #{places[gp]}"
                 + (f" ({shift:+d})".replace("-", "−") if shift else "")) if gp in places else ""
        custom.append([gp, fmt_metric("win", stats.at[gp, "win"]), fmt_metric("podium", stats.at[gp, "podium"]),
                       fmt_metric("finish", stats.at[gp, "finish"]), 0 if pd.isna(r) else int(r), place])
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text", text=texts, textfont=dict(color=colors_txt, size=12),
        marker=dict(size=46, symbol="square", color="rgba(0,0,0,0.01)"),
        customdata=custom, showlegend=False,
        hovertemplate="<b>P%{customdata[0]}</b><br>Win: %{customdata[1]}<br>Podium: %{customdata[2]}"
                      "<br>Avg finish: %{customdata[3]}<br>Starts: %{customdata[4]}%{customdata[5]}<extra></extra>",
    ))
    # pole label
    fig.add_annotation(x=front_x - slot_w / 2, y=1 + slot_h / 2 + 0.11, text="POLE", showarrow=False,
                       font=dict(color=PAINT, size=10))
    fig.update_layout(
        shapes=shapes, height=330, margin=dict(l=4, r=4, t=28, b=4), dragmode=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", clickmode="event+select",
        xaxis=dict(visible=False, range=[-cols - 0.3, front_x + 0.8], fixedrange=True),
        yaxis=dict(visible=False, range=[-0.68, 1.68], fixedrange=True),
        title=dict(text="Back of grid  ·····  race direction →  start / finish", x=0.99, xanchor="right",
                   font=dict(size=11, color=MUTED)),
    )
    return fig


g_left, g_right = st.columns([1.75, 1])
with g_left:
    st.markdown(f"**{METRICS[metric]} by starting slot · {track}**  "
                f"<span style='color:{MUTED}'>{seasons_grid.min()}–{seasons_grid.max()}, "
                f"{seasons_grid.nunique()} races · darker = better</span>", unsafe_allow_html=True)
    st.plotly_chart(grid_figure(stats, metric, st.session_state.grid), key=f"gridmap_{nonce}",
                    on_select=on_grid_click, selection_mode="points", use_container_width=True,
                    config={"displayModeBar": False})
    st.segmented_control("Colour the grid by", list(METRICS), key="metric", format_func=METRICS.get,
                         required=True, width="stretch")
    st.markdown(
        f"<span style='color:{MUTED};font-size:0.9em'>Corner <span style='color:{GAIN}'>●</span>+ / "
        f"<span style='color:{LOSS}'>●</span>− = places a slot moves up or down when the "
        f"grid is sorted by {METRICS[metric]} (ties keep grid order; blank = same place)</span>",
        unsafe_allow_html=True)

with g_right:
    gp = st.session_state.grid
    row = stats.loc[gp]
    places = metric_places(stats[metric], metric)
    rank = places.get(gp)
    with st.container(border=True):
        st.caption("Details · click a grid slot")
        st.markdown(f"## P{gp} · {track}")
        if pd.isna(row["races"]):
            st.info(f"No race at {track} has started from P{gp} in this data.")
        else:
            st.write(f"Starting P{gp} at {track}, drivers won **{row['win']:.0%}** of races and reached the "
                     f"podium **{row['podium']:.0%}** of the time. Ranked **#{rank}** of {len(places)} "
                     f"slots on {METRICS[metric]}.")
            m1, m2 = st.columns(2)
            m1.metric("Win %", f"{row['win']:.0%}")
            m2.metric("Podium %", f"{row['podium']:.0%}")
            m3, m4 = st.columns(2)
            m3.metric("Avg finish", f"P{row['finish']:.1f}")
            m4.metric("Starts (n)", int(row["races"]))
            winners = GRID[(GRID.track == track) & (GRID.grid == gp) & (GRID.position == 1)]
            if not winners.empty:
                st.caption("Won from here: " + ", ".join(
                    f"{r.driver_name} ({r.season})" for r in winners.sort_values("season").itertuples()))
            st.caption(f"Small sample (n = {int(row['races'])}): treat percentages with caution. Weather, "
                       "crashes, safety cars and strategy also affect outcomes.")

# --------------------------------------------------------------------------- 2. segment explorer
st.markdown("<div class='rule' style='border-color:#e1e0d9;border-width:1px;margin-top:1rem'></div>",
            unsafe_allow_html=True)
# seasons with lap timing for this circuit (FastF1 timing starts in 2018)
lap_seasons = sorted(LAPS.loc[LAPS.track == track, "season"].unique().tolist(), reverse=True) or [None]
if st.session_state.season not in lap_seasons:
    st.session_state.season = int(lap_seasons[0])

s1c, s2c, s3c, s4c = st.columns([2.0, 0.9, 2.6, 1.1], vertical_alignment="bottom")
with s1c:
    st.markdown("### <span class='badge'>2</span>Segment Explorer", unsafe_allow_html=True,
                help=HELP["segment"])
with s2c:
    st.selectbox("Season", lap_seasons, key="season")
with s3c:
    st.segmented_control("Segment", list(SECTORS), key="sector", format_func=SECTORS.get,
                         selection_mode="single", on_change=on_sector_change)
with s4c:
    st.button("Reset segment ↺", key="reset_seg", on_click=reset, args=("sector", "drivers", "tyre"),
              use_container_width=True)
season, sector = st.session_state.season, st.session_state.sector or 0

col = {0: "lap_time", 1: "s1", 2: "s2", 3: "s3"}[sector]
is_lap = sector == 0
# tyre filter options: the compounds used in this race, softest first, with lap counts
race_all = race_laps(track, season)
tyre_counts = race_all.compound.value_counts()
tyre_opts = ["All"] + [c for c in COMPOUNDS if c in tyre_counts.index]
if st.session_state.tyre not in tyre_opts:      # e.g. switched to a race without that compound
    st.session_state.tyre = "All"
tyre = st.session_state.tyre
ft, fw = field_bins(track, season, col, tyre)    # the field (on the selected tyre): times + weights
if not len(ft):
    st.info(f"No lap timing available for {track} {season} yet.")


def label_spots(track_xy: np.ndarray, pts: np.ndarray, dist: float) -> np.ndarray:
    """Spots for labels just off the track: from each point, step `dist` along the track's
    normal, on whichever side is further from the rest of the circuit."""
    out = []
    for p in pts:
        i = int(np.argmin(((track_xy - p) ** 2).sum(1)))
        tangent = track_xy[(i + 3) % len(track_xy)] - track_xy[(i - 3) % len(track_xy)]
        normal = np.array([-tangent[1], tangent[0]]) / (np.hypot(*tangent) or 1)
        cands = [p + normal * dist, p - normal * dist]
        out.append(max(cands, key=lambda c: np.sqrt(((track_xy - c) ** 2).sum(1)).min()))
    return np.array(out).reshape(-1, 2)


def track_figure(track: str, sector: int) -> go.Figure:
    tm = TRACK_MAP[TRACK_MAP.track == track]
    cn = CORNERS[CORNERS.track == track]
    fig = go.Figure()
    if tm.empty:
        fig.add_annotation(text="No track outline available", showarrow=False, font=dict(color=MUTED))
        fig.update_layout(height=420, xaxis=dict(visible=False), yaxis=dict(visible=False),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        return fig
    fig.add_trace(go.Scatter(x=tm.x, y=tm.y, mode="lines", hoverinfo="skip", showlegend=False,
                             line=dict(color="rgba(137,135,129,.25)", width=16)))
    for s in (1, 2, 3):
        part = tm[tm.sector == s]
        # include the first point of the next sector so the line has no gap (sector 3 closes the loop)
        nxt = tm[tm.sector == (s % 3) + 1].head(1)
        part = pd.concat([part, nxt])
        on = sector in (0, s)
        fig.add_trace(go.Scatter(
            x=part.x, y=part.y, mode="lines+markers", name=f"Sector {s}",
            line=dict(color=SECTOR_COLORS[s] if on else MUTED, width=9 if sector == s else 5),
            marker=dict(size=10, color="rgba(0,0,0,0.01)"), opacity=1 if on else 0.45,
            customdata=np.full(len(part), s),
            hovertemplate=(f"<b>Sector {s}</b><br>Median: {fmt_time(field_stat(track, season, f's{s}', 'median', tyre), False)}"
                           f"<br>Fastest: {fmt_time(field_stat(track, season, f's{s}', 'fastest', tyre), False)}"
                           "<br>Click to select<extra></extra>"),
        ))
    xy = tm[["x", "y"]].to_numpy(float)
    span = max(np.ptp(xy[:, 0]), np.ptp(xy[:, 1]))
    start = tm.iloc[0]
    fig.add_trace(go.Scatter(x=[start.x], y=[start.y], mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(symbol="square", size=11, color=F1_RED)))
    sx, sy = label_spots(xy, xy[:1], span * 0.03)[0]
    side = "right" if sx < start.x else "left"          # text runs away from the track
    fig.add_annotation(x=sx, y=sy, text="Start / finish", showarrow=False, xanchor=side,
                       font=dict(size=11, color=F1_RED))
    if not cn.empty:
        spots = label_spots(xy, cn[["x", "y"]].to_numpy(float), span * 0.035)
        fig.add_trace(go.Scatter(x=spots[:, 0], y=spots[:, 1], mode="text", text=cn.number, hoverinfo="skip",
                                 showlegend=False, textfont=dict(size=10, color="#5f5d58")))
    pad = span * 0.1
    x_range = [min(xy[:, 0].min() - pad, sx - span * 0.3 if side == "right" else np.inf),
               max(xy[:, 0].max() + pad, sx + span * 0.3 if side == "left" else -np.inf)]
    y_range = [xy[:, 1].min() - pad, xy[:, 1].max() + pad]
    fig.update_layout(
        height=420, margin=dict(l=4, r=4, t=4, b=4), dragmode=False, clickmode="event+select",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=0.0, x=0.0, itemclick=False, itemdoubleclick=False),
        xaxis=dict(visible=False, fixedrange=True, range=x_range),
        yaxis=dict(visible=False, fixedrange=True, range=y_range, scaleanchor="x", scaleratio=1),
    )
    return fig


driver_opts = RACE_DRIVERS[(RACE_DRIVERS.track == track) & (RACE_DRIVERS.season == season)].sort_values(
    ["team", "driver_name"])
labels = {r.driver: f"{r.driver_name} ({r.team})" for r in driver_opts.itertuples()}
# keep only drivers who raced in this season (the picker hasn't rendered yet, so this is allowed)
st.session_state.drivers = [d for d in st.session_state.drivers if d in labels][:MAX_DRIVERS]
drvs = st.session_state.drivers
# each driver keeps their colour while selected, so removing one doesn't recolour the others
kept = {d: c for d, c in st.session_state.get("drv_colors", {}).items() if d in drvs}
free = [c for c in DRIVER_COLORS if c not in kept.values()]
drv_color = {d: kept[d] if d in kept else free.pop(0) for d in drvs}
st.session_state.drv_colors = drv_color

m_left, m_right = st.columns(2)
with m_left:
    st.markdown(f"**Circuit map · {track}**  <span style='color:{MUTED}'>click a sector</span>",
                unsafe_allow_html=True)
    st.plotly_chart(track_figure(track, sector), key=f"trackmap_{track}_{nonce}", on_select=on_map_click,
                    selection_mode="points", use_container_width=True, config={"displayModeBar": False})

    rl = segment_laps(track, season, tyre)
    dtimes = {d: rl.loc[rl.driver == d, col].to_numpy() for d in drvs}
    dtimes = {d: t for d, t in dtimes.items() if len(t)}
    field_median = field_stat(track, season, col, "median", tyre)
    gaps = {d: float(np.median(t) - field_median) for d, t in dtimes.items()}
    k1, k2, k3 = st.columns(3)
    k1.metric(f"{SECTORS[sector]} median", fmt_time(field_median, is_lap))
    k2.metric("Fastest clean lap" if is_lap else "Fastest sector", fmt_time(field_stat(track, season, col, "fastest", tyre), is_lap))
    if gaps:
        best = min(gaps, key=gaps.get)
        gap = gaps[best]
        # one value only, coloured green (faster) or red (slower) via the container's CSS key
        with k3.container(key="gap_faster" if gap < 0 else "gap_slower"):
            st.metric(f"{best} vs field (median)" if len(gaps) == 1 else f"Quickest of {len(gaps)}: {best}",
                      f"{abs(gap):.3f}s {'faster' if gap < 0 else 'slower'}")
    else:
        k3.metric("Driver vs field", "–")

with m_right:
    tyre_title = "" if tyre == "All" else f" · {tyre} tyres"
    st.markdown(f"**Time distribution · {track} {season} · {SECTORS[sector]}{tyre_title}**", help=HELP["dist"])
    st.segmented_control(
        "Tyre", tyre_opts, key="tyre", required=True, width="stretch",
        format_func=lambda c: "Inter" if c == "Intermediate" else c)
    st.caption("Clean laps per tyre: " + " · ".join(f"{c} {tyre_counts[c]:,}" for c in tyre_opts[1:]))
    fig = go.Figure()
    if len(ft):
        lo, hi = weighted_percentile(ft, fw, [0.5, 99.5])
        for t in dtimes.values():
            dlo, dhi = np.percentile(t, [0.5, 99.5])
            lo, hi = min(lo, dlo), max(hi, dhi)
        pad = (hi - lo) * 0.05
        lo, hi = lo - pad, hi + pad
        nb = 30
        width = (hi - lo) / nb
        counts, edges = np.histogram(ft, bins=nb, range=(lo, hi), weights=fw)
        counts = counts.round().astype(int)
        pct = counts / fw.sum() * 100
        centers = (edges[:-1] + edges[1:]) / 2
        fig.add_trace(go.Bar(x=centers, y=pct, width=width * 0.92, marker_color="#9ec5f4", name="All laps",
                             customdata=np.stack([counts, [fmt_time(a, is_lap) for a in edges[:-1]],
                                                  [fmt_time(b, is_lap) for b in edges[1:]]], axis=1),
                             hovertemplate="%{customdata[1]} – %{customdata[2]}<br>%{customdata[0]} laps "
                                           "(%{y:.1f}%)<extra></extra>", showlegend=False))
        xs = np.linspace(lo, hi, 300)
        y_top = pct.max()
        if len(ft) >= MIN_CURVE_LAPS:       # too few laps make a misleading smooth curve
            overall = kde(ft, xs, fw) * width * 100
            fig.add_trace(go.Scatter(x=xs, y=overall, mode="lines", name="Overall (all drivers)",
                                     line=dict(color=BLUE, width=2.5), hoverinfo="skip"))
            y_top = max(y_top, overall.max())
        for d, t in dtimes.items():
            fig.add_vline(x=float(np.median(t)), line=dict(color=drv_color[d], dash="dot", width=1.5))
            if len(t) < 3:                   # median line only
                continue
            driver_curve = kde(t, xs) * width * 100
            fig.add_trace(go.Scatter(x=xs, y=driver_curve, mode="lines", name=labels[d],
                                     line=dict(color=drv_color[d], width=2.5),
                                     hovertemplate=f"<b>{labels[d]}</b><br>median {fmt_time(float(np.median(t)), is_lap)}"
                                                   f" ({gaps[d]:+.3f}s vs field)<extra></extra>"))
            y_top = max(y_top, driver_curve.max())
        # size the axis to the tallest of the bars and both curves so no curve is clipped
        fig.update_yaxes(range=[0, y_top * 1.08])
        fig.add_vline(x=field_median, line=dict(color=BLUE, dash="dot", width=1.5))
        step = next(s for s in (0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10) if (hi - lo) / s <= 8)
        ticks = np.arange(np.ceil(lo / step) * step, hi, step)
        dec = 0 if step >= 1 else (1 if step in (0.1, 0.2, 0.5) else 2)

        def tick_label(t: float) -> str:
            if is_lap:
                return f"{int(t // 60)}:{t % 60:0{3 + dec if dec else 2}.{dec}f}"
            return f"{t:.{dec}f}s"

        fig.update_xaxes(tickvals=ticks, ticktext=[tick_label(t) for t in ticks],
                         title_text=("lap time" if is_lap else "sector time") + " →")
    fig.update_yaxes(title_text="% of laps", ticksuffix="%")
    fig.update_layout(height=400, margin=dict(l=8, r=8, t=8, b=8), bargap=0, dragmode=False,
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, key="dist", use_container_width=True, config={"displayModeBar": False})
    if 0 < len(ft) < MIN_CURVE_LAPS:
        st.caption(f"Only {len(ft)} clean laps on {tyre} tyres in this race: bars only, no smoothed curve.")
    short = [labels[d] for d, t in dtimes.items() if len(t) < 3]
    if short:
        st.caption(f"Fewer than 3 laps for {', '.join(short)} on this selection: median line only.")
    # colour each picked driver's chip to match their curve (chip i is the i-th driver in the list)
    st.markdown("<style>" + "".join(
        f".st-key-drivers [data-tag-index='{i}'] {{ background-color: {drv_color[d]} !important; "
        "color: #fff !important; }" for i, d in enumerate(drvs))
        + ".st-key-drivers [data-tag-index] * { color: #fff !important; fill: #fff !important; }</style>",
        unsafe_allow_html=True)
    d1, d2 = st.columns([3, 1], vertical_alignment="bottom")
    with d1:
        st.multiselect(f"Compare drivers (up to {MAX_DRIVERS})", list(labels), key="drivers",
                       format_func=labels.get, max_selections=MAX_DRIVERS, select_all=False,
                       placeholder="Driver Name (Team)", wrap=True)
    with d2:
        st.button("Clear all", on_click=reset, args=("drivers",), use_container_width=True, disabled=not drvs)
    missing = [labels[d] for d in drvs if d not in dtimes]
    if missing:
        st.caption(f"No clean laps{'' if tyre == 'All' else f' on {tyre} tyres'} for {', '.join(missing)}.")
    if gaps:
        dot = "display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;background:{}"
        st.markdown("  \n".join(
            f"<span style='{dot.format(drv_color[d])}'></span>**{labels[d]}** · median "
            f"{fmt_time(float(np.median(dtimes[d])), is_lap)} · "
            f"{abs(g):.3f}s {'faster' if g < 0 else 'slower'} than the field · {len(dtimes[d])} laps"
            for d, g in sorted(gaps.items(), key=lambda kv: kv[1])), unsafe_allow_html=True)
    on_tyre = "" if tyre == "All" else f" on {tyre} tyres"
    st.caption(f"{int(fw.sum()):,} clean race laps{on_tyre} from {segment_laps(track, season, tyre).driver.nunique()} "
               "drivers (lap 1, pit in/out laps, "
               "laps under a safety car, VSC or yellow flag, and laps slower than 107% of the race's fastest lap "
               "are removed).")

st.caption("Data: all via FastF1. Race results through its Jolpica-F1 (Ergast) interface, lap/sector timing "
           "and car positions from F1 live timing, track outline and corners from MultiViewer. Grid, maps and "
           "every clean race lap are pre-built by `scripts/build_data.py`. Prototype for DS 511.")

# Plotly's click-to-select uses the point under the last *hover*. Each rerun redraws the charts, so a click
# or tap with no mouse movement first (touchscreens) selected nothing until the second try. Sending the chart
# a hover at the pointer just before each press makes the first click count.
st.html("""<script>
if (!window.__f1HoverBeforeClick) {
  window.__f1HoverBeforeClick = true;
  document.addEventListener("pointerdown", (e) => {
    const drag = e.target.closest && e.target.closest(".js-plotly-plot .nsewdrag");
    if (drag) drag.dispatchEvent(new MouseEvent("mousemove",
        {clientX: e.clientX, clientY: e.clientY, bubbles: true}));
  }, true);
}
</script>""", unsafe_allow_javascript=True)
