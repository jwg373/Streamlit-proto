import streamlit as st

st.title("🎈 My new app")
st.write(
    "Let's start building! For help and inspiration, head over to [docs.streamlit.io](https://docs.streamlit.io/)."
)
st.html("""
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>F1 Circuit Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
/* Single US Letter portrait page: 8.5in x 11in */
@page { size: letter portrait; margin: 0; }
:root {
  color-scheme: light;
  --desk: #e4e3de;
  --page: #ffffff;
  --surface: #fcfcfb;
  --ink: #0b0b0b;
  --ink-2: #52514e;
  --muted: #898781;
  --grid: #e1e0d9;
  --axis: #c3c2b7;
  --border: rgba(11,11,11,0.12);
  --s1: #2a78d6;
  --s1-soft: #9ec5f4;
  --s2: #eb6834;
  --soft: #e34948;
  --medium: #eda100;
  --hard: #898781;
  --inter: #008300;
  --seq-lo: #cde2fb;
  --seq-hi: #0d366b;
  --chip: #f0efec;
  --f1: #e10600;
}
@media screen and (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --desk: #0d0d0d; --page: #141413; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --s1: #3987e5; --s1-soft: #184f95; --s2: #d95926;
    --soft: #e66767; --medium: #c98500; --hard: #a9a79f; --inter: #0ca30c;
    --seq-lo: #1c2a3d; --seq-hi: #86b6ef; --chip: #2c2c2a;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --desk: #0d0d0d; --page: #141413; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
  --s1: #3987e5; --s1-soft: #184f95; --s2: #d95926;
  --soft: #e66767; --medium: #c98500; --hard: #a9a79f; --inter: #0ca30c;
  --seq-lo: #1c2a3d; --seq-hi: #86b6ef; --chip: #2c2c2a;
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body {
  background: var(--desk); color: var(--ink);
  font: 10px/1.3 system-ui, -apple-system, "Segoe UI", sans-serif;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.page {
  width: 8.5in; height: 11in; margin: 16px auto; padding: 0.3in 0.32in;
  background: var(--page); overflow: hidden;
  box-shadow: 0 2px 14px rgba(0,0,0,.18);
  display: flex; flex-direction: column; gap: 5px;
}
@media print {
  body { background: #fff; }
  html, body { height: 11in; overflow: hidden; }
  .page { margin: 0; box-shadow: none; height: 10.96in; break-after: avoid; }
  select, button { -webkit-appearance: none; appearance: none; }
}

/* ---------- header / global filters ---------- */
header.top { border-bottom: 2.5px solid var(--f1); padding-bottom: 5px; }
.titlerow { display: flex; align-items: baseline; gap: 10px; }
header.top h1 { font-size: 17px; margin: 0; letter-spacing: -0.01em; }
header.top .sub { color: var(--ink-2); font-size: 9.5px; }
header.top .meta { margin-left: auto; color: var(--muted); font-size: 9px; }
.filters { display: flex; flex-wrap: wrap; gap: 4px 7px; align-items: center; margin-top: 5px; }
.filters label, .local-filter label { font-size: 9.5px; color: var(--ink-2); display: inline-flex; align-items: center; gap: 4px; }
select, button {
  font: inherit; font-size: 9.5px; color: var(--ink); background: var(--surface);
  border: 1px solid var(--axis); border-radius: 4px; padding: 1px 4px; height: 18px;
}
button { cursor: pointer; }
.seg-toggle { display: inline-flex; border: 1px solid var(--axis); border-radius: 4px; overflow: hidden; height: 18px; }
.seg-toggle button { border: 0; border-radius: 0; padding: 0 7px; height: 16px; }
.seg-toggle button[aria-pressed="true"] { background: var(--ink); color: var(--page); }
.reset { font-weight: 600; margin-left: 8px; }
.chip { display: none; background: var(--chip); border-radius: 999px; padding: 1px 7px; font-size: 9.5px; }
.chip.on { display: inline-flex; gap: 4px; align-items: center; }
.chip button { border: 0; background: none; padding: 0 2px; height: auto; color: var(--ink-2); }

/* ---------- KPI row ---------- */
.kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 4px 9px; display: flex; align-items: baseline; gap: 8px; }
.kpi .k-label { color: var(--ink-2); font-size: 9.5px; }
.kpi .k-val { font-size: 19px; font-weight: 650; line-height: 1.15; }
.kpi .k-note { color: var(--muted); font-size: 8.5px; margin-left: auto; }

/* ---------- sections ---------- */
section.module { display: flex; flex-direction: column; gap: 4px; }
.mod-head { display: flex; align-items: baseline; gap: 8px; margin-top: 2px; }
.mod-head h2 { font-size: 12px; margin: 0; }
.mod-head .num { display: inline-block; background: var(--f1); color: #fff; border-radius: 3px; font-size: 9px; padding: 0 4px; margin-right: 4px; vertical-align: 1px; }
.mod-head .by { color: var(--muted); font-size: 9px; }
.mod-head .ops { color: var(--ink-2); font-size: 8.5px; margin-left: auto; text-align: right; }
.grid { display: grid; gap: 5px; }
.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
  padding: 4px 7px 3px; min-width: 0; position: relative;
}
.card h3 { font-size: 10px; margin: 0; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card h3 .hint { color: var(--muted); font-size: 8.5px; font-weight: 400; margin-left: 4px; }
.chart { width: 100%; }
.chart svg { display: block; width: 100%; overflow: visible; }

.g-grid-top { grid-template-columns: 1.85fr 1fr; }
.g-grid-bot { grid-template-columns: 1fr 1.15fr; }
.g-seg { grid-template-columns: 1.35fr 1fr; }
.g-seg-bottom { grid-template-columns: 1fr 1.25fr 1fr; }
.g-strat { grid-template-columns: repeat(4, 1fr); }
.mini-row { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 2px; }
.mini { border: 1px solid var(--border); border-radius: 5px; padding: 2px 5px; cursor: pointer; }
.mini.sel { border-color: var(--ink); }
.mini .m-title { font-size: 9px; font-weight: 600; }

/* selected info panel */
.info .big { font-size: 15px; font-weight: 650; margin-top: 2px; }
.info dl { display: grid; grid-template-columns: auto 1fr auto 1fr; gap: 3px 8px; margin: 5px 0 0; }
.info dt { color: var(--ink-2); }
.info dd { margin: 0; font-weight: 600; font-variant-numeric: tabular-nums; }
.info .warn { color: var(--ink-2); font-size: 8.5px; margin-top: 6px; border-top: 1px solid var(--grid); padding-top: 4px; }

/* legends */
.legend { display: flex; flex-wrap: wrap; gap: 1px 8px; font-size: 8.5px; color: var(--ink-2); margin: 1px 0 0; min-height: 11px; }
.legend span { display: inline-flex; align-items: center; gap: 3px; }
.legend .clickable { cursor: pointer; }
.legend .dim { opacity: .35; }
.legend .note { color: var(--muted); font-style: italic; }
.sw { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
.sw.line { height: 2px; width: 11px; border-radius: 1px; }
.sw.dash { height: 0; width: 11px; border-top: 2px dashed var(--ink-2); border-radius: 0; }
.sw.diamond { width: 6px; height: 6px; transform: rotate(45deg); border-radius: 1px; }

/* svg text */
.axis text { fill: var(--muted); font-size: 8.5px; font-variant-numeric: tabular-nums; }
.axis path, .axis line { stroke: var(--axis); }
.gridline line { stroke: var(--grid); }
.gridline path { display: none; }
.lbl { fill: var(--ink-2); font-size: 8.5px; }
.lbl-strong { fill: var(--ink); font-size: 9px; font-weight: 600; }
.ax-title { fill: var(--muted); font-size: 8.5px; }
.clickable { cursor: pointer; }

/* tooltip */
#tip {
  position: fixed; pointer-events: none; z-index: 10; opacity: 0;
  background: var(--surface); color: var(--ink); border: 1px solid var(--border);
  box-shadow: 0 4px 16px rgba(0,0,0,.14); border-radius: 7px; padding: 6px 8px;
  font-size: 11px; min-width: 120px; transition: opacity .08s;
}
#tip .t-h { font-weight: 600; margin-bottom: 3px; }
#tip .t-r { display: flex; justify-content: space-between; gap: 14px; color: var(--ink-2); }
#tip .t-r b { color: var(--ink); font-variant-numeric: tabular-nums; }

footer { margin-top: auto; color: var(--muted); font-size: 8px; border-top: 1px solid var(--grid); padding-top: 3px; display: flex; justify-content: space-between; }
</style>
</head>
<body>
<div class="page">

  <header class="top">
    <div class="titlerow">
      <h1>F1 Circuit Explorer</h1>
      <span class="sub">Grid Position · Segment Analysis · Strategy</span>
      <span class="meta">Combined dashboard mock · DS 511 Final Project</span><button class="reset" id="reset">Reset ↺</button>
    </div>
    <div class="filters">
      <label>Circuit <select id="f-circuit" style="max-width:84px"></select></label>
      <label>Years <select id="f-from"></select> to <select id="f-to"></select></label>
      <label>Driver <select id="f-driver"></select></label>
      <label>Team <select id="f-team" style="max-width:84px"></select></label>
      <label>Metric <select id="f-metric">
        <option value="win">Win %</option>
        <option value="podium">Podium %</option>
        <option value="finish">Avg finish</option>
      </select></label>
      <span class="seg-toggle" role="group" aria-label="Perspective">
        <button id="p-driver" aria-pressed="true">Driver</button>
        <button id="p-cons" aria-pressed="false">Constructor</button>
      </span>
      <span class="chip" id="year-chip">Focus year <b id="year-chip-v"></b><button id="year-clear" aria-label="Clear focus year">✕</button></span>
    </div>
  </header>

  <!-- KPI row -->
  <div class="kpis">
    <div class="kpi"><span class="k-label"># Crashes</span><span class="k-val" id="k1"></span><span class="k-note" id="k1n"></span></div>
    <div class="kpi"><span class="k-label">Avg pit stops</span><span class="k-val" id="k2"></span><span class="k-note" id="k2n"></span></div>
    <div class="kpi"><span class="k-label">Overtakes / race</span><span class="k-val" id="k3"></span><span class="k-note" id="k3n"></span></div>
  </div>

  <!-- 1. GRID POSITION EXPLORER -->
  <section class="module">
    <div class="mod-head">
      <h2><span class="num">1</span>Grid Position Explorer</h2>
      <span class="ops">Hover cell = details · click cell = select circuit + grid position</span>
    </div>
    <div class="grid g-grid-top">
      <div class="card">
        <h3><span id="hm-title">Win probability heatmap</span><span class="hint">darker = higher</span></h3>
        <div class="chart" id="heatmap"></div>
      </div>
      <div class="card info" id="info"></div>
    </div>
    <div class="grid g-grid-bot">
      <div class="card">
        <h3>Small multiples by circuit<span class="hint" id="sm-hint"></span></h3>
        <div class="mini-row" id="smalls"></div>
      </div>
      <div class="card">
        <h3 id="gv-title">Grid position vs win probability</h3>
        <div class="legend" id="gv-legend"></div>
        <div class="chart" id="gridvs"></div>
      </div>
    </div>
  </section>

  <!-- 2. SEGMENT ANALYSIS -->
  <section class="module">
    <div class="mod-head">
      <h2><span class="num">2</span>Segment Analysis</h2>
      <span class="ops">Click a track segment to update every chart in this panel</span>
    </div>
    <div class="grid g-seg">
      <div class="card">
        <h3><span id="map-title">Circuit map</span><span class="hint">clickable segments</span></h3>
        <div class="chart" id="trackmap"></div>
      </div>
      <div class="card">
        <h3><span id="fr-title">Fastest record by drivers</span><span class="hint">best segment time</span></h3>
        <div class="chart" id="fastest"></div>
      </div>
    </div>
    <div class="grid g-seg-bottom">
      <div class="card">
        <h3>Number of overtakes</h3>
        <div class="legend" id="ot-legend"></div>
        <div class="chart" id="overtakes"></div>
      </div>
      <div class="card">
        <h3>Segment time distribution</h3>
        <div class="legend" id="dist-legend"></div>
        <div class="chart" id="dist"></div>
        <div class="local-filter" style="text-align:center;margin-top:1px">
          <label>Driver <select id="f-driver2"></select></label>
        </div>
      </div>
      <div class="card">
        <h3>Number of DNF<span class="hint">in this segment</span></h3>
        <div class="legend"></div>
        <div class="chart" id="dnf"></div>
      </div>
    </div>
  </section>

  <!-- 3. STRATEGY -->
  <section class="module">
    <div class="mod-head">
      <h2><span class="num">3</span>Strategy</h2>
      <span class="ops">Team = overlay vs avg · click tyre = highlight · click year = focus all views</span>
    </div>
    <div class="grid g-strat">
      <div class="card">
        <h3>Laps by tyre type</h3>
        <div class="legend" id="lt-legend"></div>
        <div class="chart" id="laps"></div>
      </div>
      <div class="card">
        <h3>Pit stop distribution</h3>
        <div class="legend" id="pd-legend"></div>
        <div class="chart" id="pitdist"></div>
      </div>
      <div class="card">
        <h3>Tyre composition over time</h3>
        <div class="legend" id="tc-legend"></div>
        <div class="chart" id="tyrecomp"></div>
      </div>
      <div class="card">
        <h3>Avg pit stops over time</h3>
        <div class="legend" id="ap-legend"></div>
        <div class="chart" id="avgpit"></div>
      </div>
    </div>
  </section>

  <footer><span>Mock-up only: all values are generated placeholder data, not real race results.</span><span>F1 Circuit Explorer</span></footer>
</div>
<div id="tip"></div>

<script>
/* =========================================================
   Placeholder data (deterministic, seeded)
   ========================================================= */
const CIRCUITS = ['Monaco','Monza','Spa','Suzuka','Silverstone','Mexico'];
const SMALLS = ['Monaco','Monza','Spa','Suzuka'];
const DRIVERS = ['All','HAM','VER','LEC','NOR','PIA','SAI','RUS','ALO'];
const TEAMS = ['All','Ferrari','Red Bull','Mercedes','McLaren','Aston Martin'];
const TYRES = [{k:'S',name:'Soft',v:'--soft'},{k:'M',name:'Medium',v:'--medium'},{k:'H',name:'Hard',v:'--hard'},{k:'I',name:'Inter',v:'--inter'}];
const GRID_N = 10;
const YEAR_MIN = 2014, YEAR_MAX = 2024;

const CP = {
  Monaco:     {dom:.46,k:.80,stops:1.05,crash:4.2,ot:.25,t:[18.9,24.6,29.8]},
  Monza:      {dom:.30,k:.42,stops:1.25,crash:2.6,ot:1.3,t:[26.4,27.1,26.0]},
  Spa:        {dom:.26,k:.38,stops:1.70,crash:3.1,ot:1.4,t:[30.8,47.6,29.9]},
  Suzuka:     {dom:.36,k:.55,stops:1.85,crash:2.4,ot:.8, t:[32.1,38.9,19.7]},
  Silverstone:{dom:.33,k:.50,stops:1.65,crash:2.8,ot:1.1,t:[29.4,34.8,22.9]},
  Mexico:     {dom:.35,k:.52,stops:1.35,crash:2.2,ot:.9, t:[24.8,31.2,20.6]},
};
const DRV_OFF = {HAM:-.12,VER:-.22,LEC:-.15,NOR:-.10,PIA:-.04,SAI:.02,RUS:-.06,ALO:.08};
const TEAM_OFF = {Ferrari:.18,'Red Bull':-.12,Mercedes:.05,McLaren:-.04,'Aston Martin':.12};

function rng(key){
  let h = 2166136261 >>> 0;
  for (const ch of String(key)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); }
  return function(){ h += 0x6D2B79F5; let t = h; t = Math.imul(t ^ t>>>15, t|1); t ^= t + Math.imul(t ^ t>>>7, t|61); return ((t ^ t>>>14) >>> 0) / 4294967296; };
}
const clamp = (v,a,b) => Math.max(a, Math.min(b, v));
const years = () => d3.range(S.from, S.to + 1);
const activeYears = () => S.year ? [S.year] : years();

function gridStat(c, g){
  const p = CP[c], r = rng(`g${c}${g}${S.from}${S.to}${S.persp}`);
  const win = clamp(p.dom * Math.exp(-p.k*(g-1)) * (0.85 + 0.3*r()), 0, .9);
  const podium = clamp(0.92*Math.exp(-p.k*0.38*(g-1)) * (0.9 + 0.2*r()), win, .97);
  const finish = clamp(1.6 + (g-1)*(0.55 + p.k*0.6) + (r()-.5)*1.2, 1, 20);
  const races = years().length - (r() < .2 ? 1 : 0);
  return {win, podium, finish, races};
}
const metricVal = (st) => S.metric === 'finish' ? st.finish : st[S.metric];
const metricName = () => ({win:'Win %', podium:'Podium %', finish:'Avg finish'})[S.metric];
const fmtMetric = (v) => S.metric === 'finish' ? 'P' + v.toFixed(1) : d3.format('.0%')(v);

function crashes(c, y){ const r = rng(`cr${c}${y}`); return Math.round(CP[c].crash * (0.5 + r()*1.1)); }
function tyreMix(c, y){
  const r = rng(`ty${c}${y}`), t = y - 2014;
  let S_ = clamp(.48 - .025*t + (r()-.5)*.1, .12, .7);
  let H_ = clamp(.14 + .028*t + (r()-.5)*.08, .05, .55);
  let I_ = r() < .22 ? .06 + r()*.12 : 0;
  let M_ = Math.max(.08, 1 - S_ - H_ - I_);
  const sum = S_ + M_ + H_ + I_;
  return {S:S_/sum, M:M_/sum, H:H_/sum, I:I_/sum};
}
function meanStops(c, y, team){
  const r = rng(`ms${c}${y}${team}`);
  return clamp(CP[c].stops + (2019 - y)*0.03 + (team && team!=='All' ? TEAM_OFF[team] : 0) + (r()-.5)*.35, .6, 3.2);
}
function pitDist(c, ys, team){
  const out = [0,0,0,0,0];
  ys.forEach(y => {
    const m = meanStops(c, y, team);
    const w = out.map((_,k) => Math.exp(-((k-m)**2)/0.55));
    const s = d3.sum(w); w.forEach((v,k)=> out[k] += v/s);
  });
  return out.map(v => v/ys.length);
}
function overtakes(c, seg, y, drv){
  const r = rng(`ot${c}${seg}${y}${drv||''}`), base = [16,9,5][seg-1]*CP[c].ot;
  const v = base*(0.7 + (y-2014)*0.04 + r()*.5);
  return drv && drv!=='All' ? Math.max(0, Math.round(v/7 + (r()-.5)*2)) : Math.round(v);
}
function dnfs(c, seg, y){ const r = rng(`dn${c}${seg}${y}`); return Math.max(0, Math.round([2.5,3.5,2][seg-1]*(1.3 - (y-2014)*.05)*(0.4+r()*1.2))); }
function segTimes(c, seg, drv){
  const r = rng(`st${c}${seg}${drv}${S.from}${S.to}`), mu = CP[c].t[seg-1] + (drv==='All'?0:DRV_OFF[drv]*1.8), sd = .55;
  return d3.range(drv==='All'?600:120).map(()=>{ const u = r()||1e-9, v = r(); return mu + sd*Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v) + (r()<.08 ? r()*2.2 : 0); });
}
function fastest(c, seg){
  return DRIVERS.slice(1).map(d => {
    const r = rng(`fr${c}${seg}${d}`);
    return {d, t: CP[c].t[seg-1] - 0.9 + DRV_OFF[d]*1.4 + r()*.35};
  }).sort((a,b)=>a.t-b.t).slice(0,6);
}

/* =========================================================
   State
   ========================================================= */
const DEFAULT = {circuit:'Mexico', from:2018, to:2024, driver:'All', team:'All', metric:'win', persp:'Driver', grid:3, seg:2, tyre:null, year:null};
let S = {...DEFAULT};

/* =========================================================
   Helpers
   ========================================================= */
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const tip = d3.select('#tip');
function showTip(ev, title, rows){
  tip.html(`<div class="t-h">${title}</div>` + rows.map(([k,v]) => `<div class="t-r"><span>${k}</span><b>${v}</b></div>`).join(''));
  const n = tip.node(), w = n.offsetWidth, h = n.offsetHeight;
  let x = ev.clientX + 14, y = ev.clientY + 14;
  if (x + w > innerWidth - 8) x = ev.clientX - w - 14;
  if (y + h > innerHeight - 8) y = ev.clientY - h - 14;
  tip.style('left', x+'px').style('top', y+'px').style('opacity', 1);
}
const hideTip = () => tip.style('opacity', 0);

function frame(id, height, m){
  const el = d3.select('#'+id); el.selectAll('*').remove();
  const W = Math.max(120, el.node().clientWidth);
  const svg = el.append('svg').attr('viewBox', `0 0 ${W} ${height}`).attr('height', height);
  const g = svg.append('g').attr('transform', `translate(${m.l},${m.t})`);
  return {svg, g, w: W - m.l - m.r, h: height - m.t - m.b};
}
function yGrid(g, y, w, ticks, fmt){
  g.append('g').attr('class','gridline').call(d3.axisLeft(y).ticks(ticks).tickSize(-w).tickFormat(''));
  g.append('g').attr('class','axis').call(d3.axisLeft(y).ticks(ticks).tickSize(0).tickPadding(4).tickFormat(fmt)).select('.domain').remove();
}
function xAxis(g, x, h, fmt, ticks){
  const a = d3.axisBottom(x).tickSizeOuter(0).tickSize(2).tickPadding(2);
  if (fmt) a.tickFormat(fmt); if (ticks) a.ticks(ticks);
  g.append('g').attr('class','axis').attr('transform',`translate(0,${h})`).call(a);
}
function legend(id, items){
  d3.select('#'+id).html(items.map(it => {
    if (it.note) return `<span class="note">${it.note}</span>`;
    const sw = it.kind==='line' ? `<i class="sw line" style="background:${it.color}"></i>`
             : it.kind==='dash' ? `<i class="sw dash"></i>`
             : it.kind==='diamond' ? `<i class="sw diamond" style="background:${it.color}"></i>`
             : `<i class="sw" style="background:${it.color}"></i>`;
    return `<span class="${it.cls||''}" data-k="${it.k||''}">${sw}${it.label}</span>`;
  }).join(''));
}
function barPath(x, y, w, h, r=3){
  r = Math.min(r, w/2, h); if (h <= 0) return '';
  return `M${x},${y+h}V${y+r}Q${x},${y} ${x+r},${y}H${x+w-r}Q${x+w},${y} ${x+w},${y+r}V${y+h}Z`;
}
function hBarPath(x, y, w, h, r=3){
  r = Math.min(r, h/2, w); if (w <= 0) return '';
  return `M${x},${y}H${x+w-r}Q${x+w},${y} ${x+w},${y+r}V${y+h-r}Q${x+w},${y+h} ${x+w-r},${y+h}H${x}Z`;
}
const tyreColor = (k) => css(TYRES.find(t=>t.k===k).v);
const tyreName = (k) => TYRES.find(t=>t.k===k).name;

/* =========================================================
   KPIs
   ========================================================= */
function renderKPIs(){
  const ys = activeYears(), c = S.circuit;
  const span = S.year ? `${S.year}` : `${S.from}–${S.to}`;
  d3.select('#k1').text(d3.sum(ys, y => crashes(c,y)));
  d3.select('#k1n').text(`${c} · ${span}`);
  d3.select('#k2').text(d3.mean(ys, y => meanStops(c,y,S.team)).toFixed(2));
  d3.select('#k2n').text(`${S.team==='All'?'All teams':S.team} · ${span}`);
  d3.select('#k3').text(Math.round(d3.mean(ys, y => d3.sum([1,2,3], s => overtakes(c,s,y)))));
  d3.select('#k3n').text(`All segments · ${span}`);
}

/* =========================================================
   1. Grid Position Explorer
   ========================================================= */
function seqScale(){
  const vals = CIRCUITS.flatMap(c => d3.range(1,GRID_N+1).map(g => metricVal(gridStat(c,g))));
  const ext = d3.extent(vals);
  const dom = S.metric === 'finish' ? [ext[1], ext[0]] : [0, ext[1]];
  return d3.scaleSequential(d3.interpolateRgb(css('--seq-lo'), css('--seq-hi'))).domain(dom);
}
function renderHeatmap(){
  const m = {t:3,r:2,b:24,l:56};
  const {g,w,h} = frame('heatmap', 150, m);
  const x = d3.scaleBand().domain(d3.range(1,GRID_N+1)).range([0,w]).paddingInner(.07);
  const y = d3.scaleBand().domain(CIRCUITS).range([0,h]).paddingInner(.09);
  const col = seqScale();
  d3.select('#hm-title').text(`${metricName().replace(' %',' probability').replace('Avg finish','Average finish')} heatmap`);

  CIRCUITS.forEach(c => d3.range(1,GRID_N+1).forEach(gp => {
    const st = gridStat(c,gp), v = metricVal(st), sel = c===S.circuit && gp===S.grid;
    const cell = g.append('g').attr('class','clickable')
      .on('mousemove', ev => showTip(ev, `${c} · P${gp}`, [['Win %',d3.format('.0%')(st.win)],['Podium %',d3.format('.0%')(st.podium)],['Avg finish','P'+st.finish.toFixed(1)],['Races (n)',st.races]]))
      .on('mouseleave', hideTip)
      .on('click', () => { S.circuit = c; S.grid = gp; update(); });
    cell.append('rect').attr('x',x(gp)).attr('y',y(c)).attr('width',x.bandwidth()).attr('height',y.bandwidth())
      .attr('rx',2).attr('fill',col(v))
      .attr('stroke', sel ? css('--ink') : 'none').attr('stroke-width', sel ? 2 : 0);
    const dark = d3.hsl(col(v)).l < .55;
    if (x.bandwidth() > 24) cell.append('text').attr('x',x(gp)+x.bandwidth()/2).attr('y',y(c)+y.bandwidth()/2+3)
      .attr('text-anchor','middle').attr('font-size',8.5).style('font-variant-numeric','tabular-nums')
      .attr('fill', dark ? '#fff' : css('--ink')).attr('pointer-events','none')
      .text(fmtMetric(v));
  }));
  g.selectAll('.rowlab').data(CIRCUITS).join('text')
    .attr('class', d => d===S.circuit ? 'lbl-strong' : 'lbl')
    .attr('x',-5).attr('y',d=>y(d)+y.bandwidth()/2+3).attr('text-anchor','end').text(d=>d);
  g.selectAll('.collab').data(d3.range(1,GRID_N+1)).join('text')
    .attr('class', d => d===S.grid ? 'lbl-strong' : 'lbl')
    .attr('x',d=>x(d)+x.bandwidth()/2).attr('y',h+10).attr('text-anchor','middle').text(d=>'P'+d);
  g.append('text').attr('class','ax-title').attr('x',w).attr('y',h+21).attr('text-anchor','end').text('Starting grid position →');
}
function renderInfo(){
  const st = gridStat(S.circuit, S.grid);
  d3.select('#info').html(`
    <h3>Selected info<span class="hint">click a heatmap cell to drill down</span></h3>
    <div class="big">${S.circuit} · P${S.grid}</div>
    <dl>
      <dt>Circuit</dt><dd>${S.circuit}</dd>
      <dt>Grid</dt><dd>P${S.grid}</dd>
      <dt>Win %</dt><dd>${d3.format('.0%')(st.win)}</dd>
      <dt>Podium %</dt><dd>${d3.format('.0%')(st.podium)}</dd>
      <dt>Avg finish</dt><dd>P${st.finish.toFixed(1)}</dd>
      <dt>Races (n)</dt><dd>${st.races}</dd>
      <dt>Years</dt><dd>${S.from}–${S.to}</dd>
      <dt>View</dt><dd>${S.persp}${S.persp==='Driver' && S.driver!=='All' ? ' · '+S.driver : ''}${S.persp==='Constructor' && S.team!=='All' ? ' · '+S.team : ''}</dd>
    </dl>
    <div class="warn">Small sample (n = ${st.races}): treat percentages with caution. DNFs counted as last-place finish. Weather, crashes, safety cars and strategy also affect outcomes.</div>`);
}
function renderSmalls(){
  const box = d3.select('#smalls'); box.selectAll('*').remove();
  d3.select('#sm-hint').text(`${metricName()}, P1–P5 · click to focus`);
  const all = SMALLS.flatMap(c => d3.range(1,6).map(gp => metricVal(gridStat(c,gp))));
  SMALLS.forEach(c => {
    const card = box.append('div').attr('class','mini' + (c===S.circuit?' sel':''))
      .on('click', () => { S.circuit = c; update(); });
    card.append('div').attr('class','m-title').text(c);
    const W = Math.max(100, card.node().clientWidth - 12), H = 44, m = {t:1,r:28,b:1,l:16};
    const svg = card.append('svg').attr('viewBox',`0 0 ${W} ${H}`).attr('height',H).style('width','100%').style('display','block');
    const g = svg.append('g').attr('transform',`translate(${m.l},${m.t})`);
    const w = W-m.l-m.r, h = H-m.t-m.b;
    const y = d3.scaleBand().domain(d3.range(1,6)).range([0,h]).paddingInner(.22);
    const x = d3.scaleLinear().domain([0, d3.max(all)]).range([0,w]);
    d3.range(1,6).forEach(gp => {
      const st = gridStat(c,gp), v = metricVal(st), hi = c===S.circuit && gp===S.grid;
      g.append('path').attr('d', hBarPath(0, y(gp), Math.max(1,x(v)), y.bandwidth(), 2))
        .attr('fill', hi ? css('--s2') : css('--s1'))
        .on('mousemove', ev => showTip(ev, `${c} · P${gp}`, [[metricName(), fmtMetric(v)],['Races (n)', st.races]]))
        .on('mouseleave', hideTip);
      g.append('text').attr('class','lbl').attr('font-size',7.5).attr('x',-3).attr('y',y(gp)+y.bandwidth()/2+2.5).attr('text-anchor','end').style('font-size','7.5px').text('P'+gp);
      g.append('text').attr('class','lbl').attr('x',x(v)+3).attr('y',y(gp)+y.bandwidth()/2+2.5).style('font-size','7.5px').text(fmtMetric(v));
    });
  });
}
function renderGridVs(){
  const m = {t:8,r:6,b:16,l:30};
  const {g,w,h} = frame('gridvs', 108, m);
  d3.select('#gv-title').text(`Grid position vs ${metricName().toLowerCase().replace(' %',' probability')} · ${S.circuit}`);
  const gs = d3.range(1,GRID_N+1);
  const vals = gs.map(gp => metricVal(gridStat(S.circuit,gp)));
  const avg = gs.map(gp => d3.mean(CIRCUITS, c => metricVal(gridStat(c,gp))));
  const x = d3.scaleBand().domain(gs).range([0,w]).paddingInner(.3).paddingOuter(.15);
  const y = d3.scaleLinear().domain([0, d3.max([...vals,...avg])*1.12]).nice().range([h,0]);
  yGrid(g, y, w, 3, S.metric==='finish' ? (d=>'P'+d) : d3.format('.0%'));
  g.selectAll('.b').data(gs).join('path').attr('class','clickable')
    .attr('d', (gp,i) => barPath(x(gp), y(vals[i]), x.bandwidth(), h - y(vals[i])))
    .attr('fill', gp => gp===S.grid ? css('--s1') : css('--s1-soft'))
    .on('mousemove', (ev,gp) => { const i = gp-1; showTip(ev, `${S.circuit} · P${gp}`, [[metricName(), fmtMetric(vals[i])],['All-circuit avg', fmtMetric(avg[i])],['Races (n)', gridStat(S.circuit,gp).races]]); })
    .on('mouseleave', hideTip)
    .on('click', (ev,gp) => { S.grid = gp; update(); });
  const line = d3.line().x((d,i)=>x(gs[i])+x.bandwidth()/2).y(d=>y(d)).curve(d3.curveMonotoneX);
  g.append('path').attr('d', line(avg)).attr('fill','none').attr('stroke',css('--ink-2')).attr('stroke-width',1.5).attr('stroke-dasharray','4 3');
  const i = S.grid-1;
  g.append('text').attr('class','lbl-strong').attr('x',x(S.grid)+x.bandwidth()/2).attr('y',y(vals[i])-4).attr('text-anchor','middle').text(fmtMetric(vals[i]));
  xAxis(g, x, h, d=>'P'+d);
  legend('gv-legend', [{label:`${S.circuit} (selected P${S.grid} darker)`, color:css('--s1')},{label:'All-circuit average', kind:'dash'}]);
}

/* =========================================================
   2. Segment Analysis
   ========================================================= */
const TRACK = [[6,34],[12,22],[26,17],[46,13],[68,8],[86,6],[95,14],[92,26],[84,30],[80,44],[74,56],[64,54],[60,40],[52,36],[44,44],[34,52],[20,54],[9,46]];
const SPLITS = [0, .40, .72, 1];
function renderTrack(){
  const el = d3.select('#trackmap'); el.selectAll('*').remove();
  const W = Math.max(200, el.node().clientWidth), H = 134;
  const svg = el.append('svg').attr('viewBox',`0 0 ${W} ${H}`).attr('height',H);
  d3.select('#map-title').text(`Circuit map · ${S.circuit}`);
  const k = Math.min((W-110)/100, (H-24)/60);
  const ox = (W - 100*k)/2, oy = (H - 60*k)/2;
  const pts = TRACK.map(([a,b]) => [ox + a*k, oy + b*k]);
  const ghost = svg.append('path').attr('d', d3.line().curve(d3.curveCatmullRomClosed)(pts)).attr('fill','none').attr('stroke','none');
  const L = ghost.node().getTotalLength();
  const sample = (f0,f1) => d3.range(0, 61).map(i => { const p = ghost.node().getPointAtLength(L*(f0 + (f1-f0)*i/60)); return [p.x,p.y]; });
  svg.append('path').attr('d', ghost.attr('d')).attr('fill','none').attr('stroke',css('--grid')).attr('stroke-width',10).attr('stroke-linejoin','round');
  [1,2,3].forEach(s => {
    const seg = sample(SPLITS[s-1], SPLITS[s]), sel = s===S.seg;
    const d = d3.line()(seg);
    const grp = svg.append('g').attr('class','clickable')
      .on('mousemove', ev => showTip(ev, `${S.circuit} · Segment ${s}`, [['Overtakes / race', Math.round(d3.mean(activeYears(), y=>overtakes(S.circuit,s,y)))],['DNFs (total)', d3.sum(activeYears(), y=>dnfs(S.circuit,s,y))],['Fastest', fastest(S.circuit,s)[0].t.toFixed(3)+'s']]))
      .on('mouseleave', hideTip)
      .on('click', () => { S.seg = s; update(); });
    grp.append('path').attr('d',d).attr('fill','none').attr('stroke',sel ? css('--s2') : css('--muted')).attr('stroke-width', sel ? 5 : 3).attr('stroke-linecap','round');
    grp.append('path').attr('d',d).attr('fill','none').attr('stroke','transparent').attr('stroke-width',18);
    const mid = seg[30], off = s===2 ? [44,4] : s===1 ? [0,-12] : [-46,8];
    grp.append('line').attr('x1',mid[0]).attr('y1',mid[1]).attr('x2',mid[0]+off[0]*.55).attr('y2',mid[1]+off[1]*.55).attr('stroke',css('--axis'));
    grp.append('rect').attr('x',mid[0]+off[0]-25).attr('y',mid[1]+off[1]-7).attr('width',50).attr('height',14).attr('rx',7)
      .attr('fill', sel ? css('--s2') : css('--surface')).attr('stroke', sel ? 'none' : css('--axis'));
    grp.append('text').attr('x',mid[0]+off[0]).attr('y',mid[1]+off[1]+3).attr('text-anchor','middle').attr('font-size',8.5).attr('font-weight',600)
      .attr('fill', sel ? '#fff' : css('--ink')).text(`Segment ${s}`);
  });
  SPLITS.slice(0,3).forEach((f,i) => {
    const p = ghost.node().getPointAtLength(L*f), q = ghost.node().getPointAtLength(L*f + 1);
    const ang = Math.atan2(q.y-p.y, q.x-p.x) + Math.PI/2;
    svg.append('line').attr('x1',p.x-Math.cos(ang)*7).attr('y1',p.y-Math.sin(ang)*7).attr('x2',p.x+Math.cos(ang)*7).attr('y2',p.y+Math.sin(ang)*7)
      .attr('stroke', i===0 ? css('--f1') : css('--ink')).attr('stroke-width', i===0 ? 2.5 : 1.5);
    if (i===0) svg.append('text').attr('class','lbl').attr('x',p.x+9).attr('y',p.y+12).text('Start / finish');
  });
}
function renderFastest(){
  const data = fastest(S.circuit, S.seg);
  d3.select('#fr-title').text(`Fastest record by drivers · Segment ${S.seg}`);
  const m = {t:3,r:40,b:14,l:26};
  const {g,w,h} = frame('fastest', 134, m);
  const y = d3.scaleBand().domain(data.map(d=>d.d)).range([0,h]).paddingInner(.28);
  const x = d3.scaleLinear().domain([0, d3.max(data,d=>d.t)]).nice().range([0,w]);
  g.append('g').attr('class','gridline').attr('transform',`translate(0,${h})`).call(d3.axisBottom(x).ticks(4).tickSize(-h).tickFormat(''));
  g.selectAll('.b').data(data).join('path')
    .attr('d', d => hBarPath(0, y(d.d), x(d.t), y.bandwidth()))
    .attr('fill', d => S.driver===d.d ? css('--s2') : css('--s1'))
    .on('mousemove', (ev,d) => showTip(ev, `${d.d} · Segment ${S.seg}`, [['Best time', d.t.toFixed(3)+'s'],['Gap to fastest', '+' + (d.t - data[0].t).toFixed(3)+'s']]))
    .on('mouseleave', hideTip);
  g.selectAll('.n').data(data).join('text').attr('class', d => S.driver===d.d ? 'lbl-strong' : 'lbl').attr('x',-4).attr('y',d=>y(d.d)+y.bandwidth()/2+3).attr('text-anchor','end').text(d=>d.d);
  g.selectAll('.v').data(data).join('text').attr('class','lbl').attr('x',d=>x(d.t)+3).attr('y',d=>y(d.d)+y.bandwidth()/2+3).text(d=>d.t.toFixed(3)+'s');
  xAxis(g, x, h, d=>d+'s', 4);
}
function lineChart(id, ys, series, opts){
  const m = {t:12,r:8,b:14,l:24};
  const {g,w,h} = frame(id, opts.height || 100, m);
  const x = d3.scalePoint().domain(ys).range([0,w]).padding(.2);
  const y = d3.scaleLinear().domain([0, d3.max(series.flatMap(s=>s.vals))*1.15 || 1]).nice().range([h,0]);
  yGrid(g, y, w, 3, opts.yfmt || d3.format('~s'));
  const step = Math.ceil(ys.length / Math.max(2, Math.floor(w/30)));
  g.append('g').attr('class','axis').attr('transform',`translate(0,${h})`)
    .call(d3.axisBottom(x).tickSize(2).tickPadding(2).tickSizeOuter(0).tickValues(ys.filter((d,i)=>i%step===0)).tickFormat(d => "'" + String(d).slice(2)));
  if (S.year && ys.includes(S.year)) g.append('rect').attr('x',x(S.year)-7).attr('y',0).attr('width',14).attr('height',h).attr('fill',css('--chip')).lower();
  series.forEach(s => {
    g.append('path').attr('d', d3.line().x((d,i)=>x(ys[i])).y(d=>y(d))(s.vals)).attr('fill','none').attr('stroke',s.color).attr('stroke-width',1.75);
    g.selectAll(null).data(s.vals).join('circle').attr('cx',(d,i)=>x(ys[i])).attr('cy',d=>y(d)).attr('r', (d,i)=> ys[i]===S.year ? 4 : 2.75)
      .attr('fill',s.color).attr('stroke',css('--surface')).attr('stroke-width',1.25);
  });
  const cross = g.append('line').attr('y1',0).attr('y2',h).attr('stroke',css('--axis')).attr('opacity',0);
  g.append('rect').attr('width',w).attr('height',h).attr('fill','transparent').attr('class', opts.clickYear ? 'clickable' : '')
    .on('mousemove', ev => {
      const [mx] = d3.pointer(ev); const i = d3.minIndex(ys, yy => Math.abs(x(yy)-mx));
      cross.attr('x1',x(ys[i])).attr('x2',x(ys[i])).attr('opacity',1);
      showTip(ev, ys[i] + (opts.clickYear ? ' · click to focus' : ''), series.map(s => [s.name, opts.fmt ? opts.fmt(s.vals[i]) : s.vals[i]]));
    })
    .on('mouseleave', () => { cross.attr('opacity',0); hideTip(); })
    .on('click', ev => { if (!opts.clickYear) return; const [mx] = d3.pointer(ev); const yy = ys[d3.minIndex(ys, v => Math.abs(x(v)-mx))]; S.year = S.year===yy ? null : yy; update(); });
  if (opts.ytitle) g.append('text').attr('class','ax-title').attr('x',-m.l+1).attr('y',-4).text(opts.ytitle);
}
function renderOvertakes(){
  const ys = years();
  const series = [{name:'All drivers', color:css('--s1'), vals: ys.map(y=>overtakes(S.circuit,S.seg,y))}];
  if (S.driver!=='All') series.push({name:S.driver, color:css('--s2'), vals: ys.map(y=>overtakes(S.circuit,S.seg,y,S.driver))});
  legend('ot-legend', series.map(s=>({label:s.name, color:s.color, kind:'line'})).concat(S.driver==='All'?[{note:'pick a driver to compare'}]:[]));
  lineChart('overtakes', ys, series, {ytitle:'# overtakes', clickYear:true});
}
function renderDNF(){
  const ys = years();
  lineChart('dnf', ys, [{name:'DNFs', color:css('--s1'), vals: ys.map(y=>dnfs(S.circuit,S.seg,y))}], {ytitle:'# DNF', clickYear:true, yfmt:d3.format('d')});
}
function renderDist(){
  const m = {t:12,r:6,b:14,l:24};
  const {g,w,h} = frame('dist', 82, m);
  const all = segTimes(S.circuit, S.seg, 'All');
  const drv = S.driver!=='All' ? segTimes(S.circuit, S.seg, S.driver) : null;
  const ext = d3.extent(drv ? all.concat(drv) : all);
  const x = d3.scaleLinear().domain([Math.floor(ext[0]*2)/2, Math.ceil(ext[1]*2)/2]).range([0,w]);
  const bins = d3.bin().domain(x.domain()).thresholds(x.ticks(18))(all);
  const y = d3.scaleLinear().domain([0, d3.max(bins,b=>b.length)*1.12]).nice().range([h,0]);
  yGrid(g, y, w, 2, d3.format('d'));
  g.selectAll('.b').data(bins).join('path')
    .attr('d', b => barPath(x(b.x0)+.75, y(b.length), Math.max(0, x(b.x1)-x(b.x0)-1.5), h - y(b.length), 2))
    .attr('fill', css('--s1-soft'))
    .on('mousemove', (ev,b) => showTip(ev, `${b.x0.toFixed(1)}–${b.x1.toFixed(1)}s`, [['Laps (all drivers)', b.length], ...(drv ? [[S.driver+' laps', drv.filter(v=>v>=b.x0&&v<b.x1).length]] : [])]))
    .on('mouseleave', hideTip);
  const kde = (arr, scaleTo) => {
    const bw = .35, xs = d3.range(x.domain()[0], x.domain()[1]+.01, .05);
    const dens = xs.map(v => d3.mean(arr, a => Math.exp(-.5*((v-a)/bw)**2)/(bw*Math.sqrt(2*Math.PI))));
    const k = scaleTo / d3.max(dens);
    return xs.map((v,i)=>[v, dens[i]*k]);
  };
  const peak = d3.max(bins,b=>b.length);
  const ln = d3.line().x(d=>x(d[0])).y(d=>y(d[1])).curve(d3.curveBasis);
  g.append('path').attr('d', ln(kde(all, peak))).attr('fill','none').attr('stroke',css('--s1')).attr('stroke-width',1.75);
  if (drv) g.append('path').attr('d', ln(kde(drv, peak*.75))).attr('fill','none').attr('stroke',css('--s2')).attr('stroke-width',1.75);
  xAxis(g, x, h, d=>d+'"', 6);
  g.append('text').attr('class','ax-title').attr('x',w).attr('y',-4).attr('text-anchor','end').text('segment time (s) →');
  g.append('text').attr('class','ax-title').attr('x',-m.l+1).attr('y',-4).text('# laps');
  legend('dist-legend', [{label:'Overall history', color:css('--s1'), kind:'line'}].concat(drv ? [{label:`${S.driver} specific`, color:css('--s2'), kind:'line'}] : [{note:'pick a driver below'}]));
}

/* =========================================================
   3. Strategy
   ========================================================= */
function tyreLegend(id){
  legend(id, TYRES.map(t => ({label:t.name, color:css(t.v), k:t.k, cls:'clickable' + (S.tyre && S.tyre!==t.k ? ' dim' : '')})));
  d3.selectAll(`#${id} [data-k]`).on('click', function(){ const k = this.dataset.k; S.tyre = S.tyre===k ? null : k; update(); });
}
const STRAT_H = 126;
function renderLaps(){
  const ys = activeYears(), c = S.circuit;
  const lapsPerRace = {Monaco:78,Monza:53,Spa:44,Suzuka:53,Silverstone:52,Mexico:71}[c] * 20;
  const data = TYRES.map(t => ({k:t.k, v: Math.round(d3.sum(ys, y => tyreMix(c,y)[t.k] * lapsPerRace))}));
  tyreLegend('lt-legend');
  const m = {t:20,r:4,b:14,l:26};
  const {g,w,h} = frame('laps', STRAT_H, m);
  const x = d3.scaleBand().domain(TYRES.map(t=>t.k)).range([0,w]).paddingInner(.3).paddingOuter(.15);
  const y = d3.scaleLinear().domain([0, d3.max(data,d=>d.v)*1.15]).nice().range([h,0]);
  yGrid(g, y, w, 3, d3.format('~s'));
  g.selectAll('.b').data(data).join('path').attr('class','clickable')
    .attr('d', d => barPath(x(d.k), y(d.v), x.bandwidth(), h - y(d.v)))
    .attr('fill', d => tyreColor(d.k)).attr('opacity', d => S.tyre && S.tyre!==d.k ? .25 : 1)
    .on('mousemove', (ev,d) => showTip(ev, `${tyreName(d.k)} tyres`, [['Laps', d3.format(',')(d.v)],['Share', d3.format('.0%')(d.v/d3.sum(data,e=>e.v))],['Period', S.year || `${S.from}–${S.to}`]]))
    .on('mouseleave', hideTip)
    .on('click', (ev,d) => { S.tyre = S.tyre===d.k ? null : d.k; update(); });
  g.selectAll('.v').data(data).join('text').attr('class','lbl').attr('x',d=>x(d.k)+x.bandwidth()/2).attr('y',d=>y(d.v)-3).attr('text-anchor','middle').text(d=>d3.format('.2~s')(d.v));
  xAxis(g, x, h, k => k);
  g.append('text').attr('class','ax-title').attr('x',-m.l+1).attr('y',-10).text('# of laps');
}
function renderPitDist(){
  const ys = activeYears(), c = S.circuit;
  const all = pitDist(c, ys, 'All'), team = S.team!=='All' ? pitDist(c, ys, S.team) : null;
  legend('pd-legend', [{label:'All', color:css('--s1-soft')}].concat(team ? [{label:S.team, color:css('--s2'), kind:'diamond'}] : [{note:'pick a team'}]));
  const m = {t:20,r:4,b:22,l:26};
  const {g,w,h} = frame('pitdist', STRAT_H, m);
  const ks = [0,1,2,3,4];
  const x = d3.scaleBand().domain(ks).range([0,w]).paddingInner(.4).paddingOuter(.15);
  const y = d3.scaleLinear().domain([0, d3.max(all.concat(team||[]))*1.12]).nice().range([h,0]);
  yGrid(g, y, w, 3, d3.format('.0%'));
  const tipRows = k => [['Circuit avg', d3.format('.0%')(all[k])], ...(team ? [[`${S.team} avg`, d3.format('.0%')(team[k])]] : [])];
  g.selectAll('.b').data(ks).join('path')
    .attr('d', k => barPath(x(k), y(all[k]), x.bandwidth(), h - y(all[k])))
    .attr('fill', css('--s1-soft'))
    .on('mousemove', (ev,k) => showTip(ev, `${k} pit stop${k===1?'':'s'}`, tipRows(k)))
    .on('mouseleave', hideTip);
  if (team) g.selectAll('.d').data(ks).join('path')
    .attr('d', d3.symbol(d3.symbolDiamond, 48))
    .attr('transform', k => `translate(${x(k)+x.bandwidth()/2},${y(team[k])})`)
    .attr('fill', css('--s2')).attr('stroke', css('--surface')).attr('stroke-width',1.5)
    .on('mousemove', (ev,k) => showTip(ev, `${k} pit stop${k===1?'':'s'}`, tipRows(k)))
    .on('mouseleave', hideTip);
  xAxis(g, x, h);
  g.append('text').attr('class','ax-title').attr('x',w/2).attr('y',h+20).attr('text-anchor','middle').text('# of pit stops');
  g.append('text').attr('class','ax-title').attr('x',-m.l+1).attr('y',-10).text('freq.');
}
function renderTyreComp(){
  const ys = years(), c = S.circuit;
  tyreLegend('tc-legend');
  const m = {t:20,r:4,b:14,l:26};
  const {g,w,h} = frame('tyrecomp', STRAT_H, m);
  const x = d3.scaleBand().domain(ys).range([0,w]).paddingInner(.25).paddingOuter(.08);
  const y = d3.scaleLinear().domain([0,1]).range([h,0]);
  yGrid(g, y, w, 2, d3.format('.0%'));
  ys.forEach(yr => {
    const mix = tyreMix(c, yr); let acc = 0;
    const col = g.append('g').attr('class','clickable').attr('opacity', S.year && S.year!==yr ? .35 : 1)
      .on('click', () => { S.year = S.year===yr ? null : yr; update(); });
    TYRES.forEach(t => {
      const v = mix[t.k]; if (v <= 0) return;
      const y0 = y(acc), y1 = y(acc+v); acc += v;
      col.append('rect').attr('x',x(yr)).attr('y',y1).attr('width',x.bandwidth()).attr('height',Math.max(0,y0-y1-1.5))
        .attr('fill', css(t.v)).attr('opacity', S.tyre && S.tyre!==t.k ? .2 : 1)
        .on('mousemove', ev => showTip(ev, `${yr} · ${t.name}`, [['Share of laps', d3.format('.0%')(v)],['Click', 'focus this year']]))
        .on('mouseleave', hideTip);
    });
  });
  const step = Math.ceil(ys.length / Math.max(2, Math.floor(w/22)));
  g.append('g').attr('class','axis').attr('transform',`translate(0,${h})`).call(d3.axisBottom(x).tickSize(2).tickPadding(2).tickValues(ys.filter((d,i)=>i%step===0)).tickFormat(d => "'" + String(d).slice(2)));
  g.append('text').attr('class','ax-title').attr('x',-m.l+1).attr('y',-10).text('% composition');
}
function renderAvgPit(){
  const ys = years(), c = S.circuit;
  const series = [{name:'All teams', color:css('--s1'), vals: ys.map(y=>meanStops(c,y,'All'))}];
  if (S.team!=='All') series.push({name:S.team, color:css('--s2'), vals: ys.map(y=>meanStops(c,y,S.team))});
  legend('ap-legend', series.map(s=>({label:s.name, color:s.color, kind:'line'})).concat(S.team==='All'?[{note:'pick a team'}]:[]));
  lineChart('avgpit', ys, series, {ytitle:'avg pit stops', clickYear:true, fmt:v=>v.toFixed(2), yfmt:d3.format('.1f'), height:STRAT_H});
}

/* =========================================================
   Controls
   ========================================================= */
function fill(sel, vals, cur){ d3.select(sel).selectAll('option').data(vals).join('option').attr('value',d=>d).text(d=>d).property('selected', d=>d==cur); }
function syncControls(){
  fill('#f-circuit', CIRCUITS, S.circuit);
  fill('#f-from', d3.range(YEAR_MIN, YEAR_MAX+1), S.from);
  fill('#f-to', d3.range(YEAR_MIN, YEAR_MAX+1), S.to);
  fill('#f-driver', DRIVERS, S.driver);
  fill('#f-driver2', DRIVERS, S.driver);
  fill('#f-team', TEAMS, S.team);
  d3.select('#f-metric').property('value', S.metric);
  d3.select('#p-driver').attr('aria-pressed', S.persp==='Driver');
  d3.select('#p-cons').attr('aria-pressed', S.persp==='Constructor');
  d3.select('#year-chip').classed('on', !!S.year); d3.select('#year-chip-v').text(S.year || '');
}
d3.select('#f-circuit').on('change', e => { S.circuit = e.target.value; update(); });
d3.select('#f-from').on('change', e => { S.from = +e.target.value; if (S.to < S.from) S.to = S.from; if (S.year && S.year < S.from) S.year = null; update(); });
d3.select('#f-to').on('change', e => { S.to = +e.target.value; if (S.from > S.to) S.from = S.to; if (S.year && S.year > S.to) S.year = null; update(); });
d3.selectAll('#f-driver, #f-driver2').on('change', e => { S.driver = e.target.value; update(); });
d3.select('#f-team').on('change', e => { S.team = e.target.value; update(); });
d3.select('#f-metric').on('change', e => { S.metric = e.target.value; update(); });
d3.select('#p-driver').on('click', () => { S.persp = 'Driver'; update(); });
d3.select('#p-cons').on('click', () => { S.persp = 'Constructor'; update(); });
d3.select('#year-clear').on('click', () => { S.year = null; update(); });
d3.select('#reset').on('click', () => { S = {...DEFAULT}; update(); });

function update(){
  hideTip();
  syncControls();
  renderKPIs();
  renderHeatmap(); renderInfo(); renderSmalls(); renderGridVs();
  renderTrack(); renderFastest(); renderOvertakes(); renderDist(); renderDNF();
  renderLaps(); renderPitDist(); renderTyreComp(); renderAvgPit();
}
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', update);
update();
addEventListener('load', () => requestAnimationFrame(update));
</script>
</body>
</html>""", unsafe_allow_javascript=True)
