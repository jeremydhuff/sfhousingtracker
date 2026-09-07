"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const num = (n) => Math.round(n || 0).toLocaleString();
const homesLabel = (n) => `${num(n)} ${Math.round(n) === 1 ? "home" : "homes"}`;

const STAGE = {
  under_construction: { cls: "built",  label: "under construction" },
  permitted:          { cls: "permit", label: "permitted" },
};
const cssVar = (n, d) =>
  getComputedStyle(document.documentElement).getPropertyValue(n).trim() || d;
const COLOR = {
  built: cssVar("--blueprint", "#1a3a5c"),
  permit: cssVar("--ochre", "#9a5b12"),
  ink: cssVar("--ink", "#12100e"),
};

const S = {
  projects: [], completions: [], summary: {}, timeseries: {}, manifest: {},
  filters: { nb: "", stage: "", q: "" },
  sort: { key: "net_units", dir: -1 },
  markers: new Map(),
};

async function boot() {
  const j = async (f) => {
    const r = await fetch("data/" + f + "?" + Date.now());
    if (!r.ok) throw new Error(f + " " + r.status);
    return r.json();
  };
  try {
    [S.projects, S.completions, S.summary, S.timeseries, S.manifest] = await Promise.all([
      j("projects.json"), j("completions.json"), j("summary.json"),
      j("timeseries.json"), j("manifest.json"),
    ]);
  } catch (e) {
    $("#dateline").textContent = "Could not load data/ — run: python scripts/update.py";
    console.error(e);
    return;
  }
  renderMasthead();
  renderMap();
  renderLedger();
  renderCharts();
  buildTable();
  renderFooter();
}

/* ------------------------------------------------------------ masthead */
function renderMasthead() {
  const s = S.summary;
  const gen = (S.manifest.generated_at || s.generated_at || "").slice(0, 10);
  $("#dateline").innerHTML =
    `City data as of <b>${gen}</b> &nbsp;&middot;&nbsp; ` +
    `pipeline snapshot ${(sourceDate("pipeline") || "").slice(0, 10)} &nbsp;&middot;&nbsp; ` +
    `${S.projects.length} projects`;

  const figs = [
    { cls: "built", n: num(s.under_construction_units), lbl: "homes under construction",
      sub: `${s.under_construction_projects} projects` },
    { cls: "permit", n: num(s.permitted_units), lbl: "construction permit issued, not started",
      sub: `${s.permitted_projects} projects` },
    { cls: "done", n: num(s.completed_this_year_units), yr: s.year,
      lbl: `homes finished in ${s.year} so far`,
      sub: `${num(s.completed_prev_year_full)} in all of ${s.year - 1}` },
    { cls: "aff", n: (s.affordable_active_pct || 0) + "%",
      lbl: "BMR, where the count is known",
      sub: `${num(s.affordable_active_units)} homes` },
  ];
  $("#standings").innerHTML = figs.map((f) => `
    <div class="fig ${f.cls}">
      <span class="n">${f.n}${f.yr ? `<span class="yr">${String(f.yr).slice(2)}</span>` : ""}</span>
      <span class="lbl">${f.lbl}</span>
      <span class="sub">${f.sub}</span>
    </div>`).join("");
}
function sourceDate(name) {
  const src = (S.manifest.sources || []).find((x) => x.source === name);
  return src ? (src.source_updated_at || src.fetched_at) : "";
}

/* ------------------------------------------------------------ map */
let map;
function renderMap() {
  map = L.map("map", { scrollWheelZoom: false, zoomSnap: 0.5 }).setView([37.766, -122.44], 12);
  L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 16, attribution: "Esri, HERE, Garmin, &copy; OpenStreetMap contributors" }
  ).addTo(map);
  L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 16, opacity: 0.9 }
  ).addTo(map);

  $("#maplegend").innerHTML = `
    <span class="legend-key" data-k="under_construction"><span class="g built"></span> under construction</span>
    <span class="legend-key" data-k="permitted"><span class="g permit"></span> permitted</span>
    <span style="color:var(--faint)">circle area &prop; homes &middot; click a key to isolate</span>`;
  $$(".legend-key").forEach((k) => k.addEventListener("click", () =>
    setFilter("stage", S.filters.stage === k.dataset.k ? "" : k.dataset.k)));

  drawMarkers();
}

function radius(u) { return Math.max(4, Math.min(26, 3 + Math.sqrt(Math.max(u, 0)) * 1.25)); }

let layerProjects;
function drawMarkers() {
  if (layerProjects) map.removeLayer(layerProjects);
  S.markers.clear();
  layerProjects = L.layerGroup();
  visibleProjects().forEach((p) => {
    if (p.lat == null || p.lon == null) return;
    const built = p.stage === "under_construction";
    const m = L.circleMarker([p.lat, p.lon], {
      radius: radius(p.net_units),
      fillColor: built ? COLOR.built : COLOR.permit,
      color: COLOR.ink, weight: 0.6, opacity: 0.55, fillOpacity: built ? 0.75 : 0.5,
    });
    m.on("mouseover", (e) => showCard(p, e.originalEvent));
    m.on("mouseout", hideCardSoon);
    m.on("click", () => pinProject(p));
    m.addTo(layerProjects);
    S.markers.set(p.id, m);
  });
  layerProjects.addTo(map);
  $$(".legend-key").forEach((k) =>
    k.classList.toggle("off", S.filters.stage && S.filters.stage !== k.dataset.k));
}

/* ------------------------------------------------------------ ledger */
function renderLedger() {
  const rows = (S.summary.by_neighborhood || []).slice(0, 12);
  $("#ledger").innerHTML = rows.map((r) => `
    <li data-nb="${esc(r.neighborhood)}" class="${S.filters.nb === r.neighborhood ? "active" : ""}">
      <span class="place">${esc(r.neighborhood)} <span class="sub">${r.projects}&nbsp;proj</span></span>
      <span class="val">${num(r.units)}</span>
    </li>`).join("");
  $$("#ledger li").forEach((li) => li.addEventListener("click", () =>
    setFilter("nb", S.filters.nb === li.dataset.nb ? "" : li.dataset.nb)));
  $("#ledger-clear").hidden = !S.filters.nb;
  $("#ledger-clear").onclick = () => setFilter("nb", "");
}

/* ------------------------------------------------------------ charts */
function svgEl(w, h) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", `0 0 ${w} ${h}`);
  return s;
}
function tag(name, attrs, text) {
  const e = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text != null) e.textContent = text;
  return e;
}
function note(t) {
  const d = document.createElement("div");
  d.className = "note"; d.textContent = t; return d;
}

function renderCharts() {
  chartCompletions();
  chartStage();
  chartHistory();
}

function chartCompletions() {
  const yr = S.summary.year;
  const annual = S.timeseries.completions_annual || {};
  const years = Object.keys(annual).map(Number).sort((a, b) => a - b);
  const box = $("#chart-completions");
  $("#cc-hd").textContent = "Homes completed per year";
  $("#cc-note").textContent =
    `Net new homes receiving a certificate of occupancy, by year. The ${yr} bar is far from ` +
    `final — the city keeps entering these records for a year or more after a building opens, ` +
    `so it will keep rising. It also nets out HOPE SF public-housing rebuilds (Sunnydale, ` +
    `Potrero) that demolish before their replacements finish.`;
  if (!years.length) { box.append(note("no completion data")); return; }

  const vals = years.map((y) => annual[y]);
  const max = Math.ceil(Math.max(100, ...vals) / 1000) * 1000;
  const W = 640, H = 250, pl = 46, pr = 14, pt = 18, pb = 28;
  const bx = (i) => pl + (i + 0.5) * (W - pl - pr) / years.length;
  const bw = Math.min(48, (W - pl - pr) / years.length * 0.6);
  const y = (v) => H - pb - (Math.max(v, 0) / max) * (H - pt - pb);
  const s = svgEl(W, H);

  const defs = tag("defs", {});
  const pat = tag("pattern", { id: "cc-hatch", width: 7, height: 7,
    patternTransform: "rotate(45)", patternUnits: "userSpaceOnUse" });
  pat.append(tag("line", { x1: 0, y1: 0, x2: 0, y2: 7,
    stroke: "var(--verdigris)", "stroke-width": 3.5 }));
  defs.append(pat);
  s.append(defs);

  for (let i = 0; i <= 4; i++) {
    const yy = pt + (i / 4) * (H - pt - pb);
    s.append(tag("line", { class: "gl", x1: pl, y1: yy, x2: W - pr, y2: yy }));
    s.append(tag("text", { x: pl - 8, y: yy + 3, "text-anchor": "end" },
      num(max - (i / 4) * max)));
  }
  years.forEach((yEach, i) => {
    const v = annual[yEach], partial = yEach === yr;
    const top = y(v), h = Math.max(1, y(0) - top);
    s.append(tag("rect", { x: bx(i) - bw / 2, y: top, width: bw, height: h,
      fill: partial ? "url(#cc-hatch)" : "var(--verdigris)",
      stroke: "var(--verdigris)", "stroke-width": partial ? 1 : 0 }));
    s.append(tag("text", { x: bx(i), y: top - 5, "text-anchor": "middle", fill: "var(--ink)" },
      num(v)));
    s.append(tag("text", { x: bx(i), y: H - 9, "text-anchor": "middle",
      fill: partial ? "var(--verdigris)" : "var(--faint)" },
      partial ? `${yEach}→` : String(yEach)));
  });
  box.append(s);

  const recent = S.completions.slice(0, 4)
    .map((c) => `${c.address} (${c.net_units})`).join("  ·  ");
  if (recent) box.append(note("latest certificates: " + recent));
}

function chartStage() {
  const box = $("#chart-stage");
  const data = [
    { label: "under construction", cls: "bar-uc", key: "under_construction" },
    { label: "permitted", cls: "bar-permit", key: "permitted" },
  ].map((d) => {
    const ps = S.projects.filter((p) => p.stage === d.key);
    return { ...d,
      units: ps.reduce((a, p) => a + p.net_units, 0),
      aff: ps.reduce((a, p) => a + (p.affordable_known ? p.affordable_units : 0), 0) };
  });
  const W = 420, H = 150, pl = 4, pr = 56, pt = 8, gap = 30;
  const bh = (H - pt - data.length * gap) / data.length;
  const max = Math.max(1, ...data.map((d) => d.units));
  const bw = (v) => (v / max) * (W - pl - pr);
  const s = svgEl(W, H);
  data.forEach((d, i) => {
    const yy = pt + i * (bh + gap);
    s.append(tag("rect", { class: d.cls, x: pl, y: yy, width: bw(d.units), height: bh }));
    if (d.aff > 0)
      s.append(tag("rect", { class: "bar-aff", x: pl, y: yy + bh - 5, width: bw(d.aff), height: 5 }));
    s.append(tag("text", { x: pl + bw(d.units) + 6, y: yy + bh / 2 + 4, fill: "var(--ink)" },
      num(d.units)));
    s.append(tag("text", { x: pl + 2, y: yy - 5 },
      `${d.label}${d.aff ? `  ·  ${num(d.aff)} BMR` : ""}`));
  });
  box.append(s);
}

function chartHistory() {
  const box = $("#chart-history");
  const h = (S.timeseries.history || []).filter((r) => r.under_construction_units != null);
  if (h.length < 2) {
    $("#hist-note").textContent =
      `${h.length || "No"} snapshot${h.length === 1 ? "" : "s"} so far — this line fills in as you run updates.`;
    return;
  }
  $("#hist-note").textContent = `${h.length} snapshots since ${h[0].date}.`;
  const W = 420, H = 170, pl = 38, pr = 12, pt = 10, pb = 20;
  const vals = h.map((r) => r.under_construction_units);
  const hi = Math.max(...vals) * 1.06, lo = Math.min(...vals) * 0.94;
  const span = (hi - lo) || 1;
  const x = (i) => pl + (i / (h.length - 1)) * (W - pl - pr);
  const y = (v) => H - pb - ((v - lo) / span) * (H - pt - pb);
  const s = svgEl(W, H);
  for (let i = 0; i <= 3; i++) {
    const yy = pt + (i / 3) * (H - pt - pb);
    s.append(tag("line", { class: "gl", x1: pl, y1: yy, x2: W - pr, y2: yy }));
    s.append(tag("text", { x: pl - 6, y: yy + 3, "text-anchor": "end" }, num(hi - (i / 3) * span)));
  }
  s.append(tag("path", { class: "series-cur", fill: "none", "stroke-width": 2,
    d: "M" + h.map((r, i) => `${x(i)},${y(r.under_construction_units)}`).join("L") }));
  s.append(tag("text", { x: pl, y: H - 5 }, h[0].date.slice(5)));
  s.append(tag("text", { x: W - pr, y: H - 5, "text-anchor": "end" }, h[h.length - 1].date.slice(5)));
  box.append(s);
}

/* ------------------------------------------------------------ table */
const COLS = [
  { key: "_glyph", label: "", sortable: false, get: () => "" },
  { key: "name", label: "project", get: (p) => p.name.toLowerCase() },
  { key: "neighborhood", label: "neighborhood", get: (p) => p.neighborhood },
  { key: "net_units", label: "homes", num: true, get: (p) => p.net_units },
  { key: "affordable_units", label: "BMR", num: true, get: (p) => p.affordable_units },
  { key: "change", label: "site change", get: (p) => p.change },
  { key: "status_date", label: "since", get: (p) => p.status_date || "" },
];

function buildTable() {
  const nbSel = $("#f-nb");
  [...new Set(S.projects.map((p) => p.neighborhood))].sort().forEach((n) => {
    const o = document.createElement("option");
    o.value = o.textContent = n;
    nbSel.append(o);
  });
  $("#idx-head").innerHTML = COLS.map((c) =>
    `<th data-k="${c.key}"${c.sortable === false ? ' style="cursor:default"' : ""}>` +
    `${c.label}<span class="arr"></span></th>`).join("");
  $$("#idx-head th").forEach((th) => {
    const col = COLS.find((c) => c.key === th.dataset.k);
    if (col.sortable === false) return;
    th.addEventListener("click", () => {
      S.sort = S.sort.key === col.key
        ? { key: col.key, dir: -S.sort.dir }
        : { key: col.key, dir: col.num ? -1 : 1 };
      renderTable();
    });
  });
  let deb;
  $("#q").addEventListener("input", (e) => {
    clearTimeout(deb);
    const v = e.target.value;
    deb = setTimeout(() => setFilter("q", v), 160);
  });
  $("#f-stage").addEventListener("change", (e) => setFilter("stage", e.target.value));
  $("#f-nb").addEventListener("change", (e) => setFilter("nb", e.target.value));
  $("#tbl-clear").addEventListener("click", () => {
    S.filters = { nb: "", stage: "", q: "" };
    $("#q").value = ""; $("#f-stage").value = ""; $("#f-nb").value = "";
    syncAll();
  });
  renderTable();
}

function passesNB(nb) { return !S.filters.nb || nb === S.filters.nb; }
function visibleProjects() {
  const q = S.filters.q.toLowerCase();
  return S.projects.filter((p) =>
    passesNB(p.neighborhood) &&
    (!S.filters.stage || p.stage === S.filters.stage) &&
    (!q || (p.name + " " + p.address + " " + p.change).toLowerCase().includes(q)));
}

function renderTable() {
  const col = COLS.find((c) => c.key === S.sort.key) || COLS[3];
  const rows = visibleProjects().slice().sort((a, b) => {
    const va = col.get(a), vb = col.get(b);
    return (va < vb ? -1 : va > vb ? 1 : 0) * S.sort.dir;
  });
  $("#tbl-count").textContent =
    `${rows.length} shown · ${num(rows.reduce((a, p) => a + p.net_units, 0))} homes`;
  $$("#idx-head th").forEach((th) => {
    th.querySelector(".arr").textContent =
      th.dataset.k === S.sort.key ? (S.sort.dir < 0 ? " ▼" : " ▲") : "";
  });

  $("#idx-body").innerHTML = rows.map((p) => `
    <tr data-id="${esc(p.id)}" class="${p.stage === "under_construction" ? "st-built" : "st-permit"}">
      <td class="glyph" title="${esc(p.status || "")}"></td>
      <td class="addr">${esc(p.name)}<br><span style="color:var(--faint)">${esc(p.address)}</span></td>
      <td>${esc(p.neighborhood)}</td>
      <td class="num">${num(p.net_units)}</td>
      <td class="num">${p.affordable_known ? (p.affordable_units ? num(p.affordable_units) : "0") : "?"}</td>
      <td class="replaces">${esc(p.change)}</td>
      <td>${esc(p.status_date || "·")}</td>
    </tr>`).join("");
  const byId = new Map(S.projects.map((p) => [p.id, p]));
  $$("#idx-body tr").forEach((tr) => {
    const p = byId.get(tr.dataset.id);
    tr.addEventListener("mouseenter", (e) => { showCard(p, e); highlight(p, true); });
    tr.addEventListener("mouseleave", () => { hideCardSoon(); highlight(p, false); });
    tr.addEventListener("click", () => pinProject(p));
  });
  drawMarkers();
}

function highlight(p, on) {
  const m = S.markers.get(p.id);
  if (!m) return;
  m.setStyle({ weight: on ? 2.6 : 0.6, opacity: on ? 1 : 0.55 });
  if (on) m.bringToFront();
}
function pinProject(p) {
  if (p.lat == null) return;
  map.setView([p.lat, p.lon], 15, { animate: true });
  const m = S.markers.get(p.id);
  if (m) { highlight(p, true); setTimeout(() => highlight(p, false), 1800); }
}

/* ------------------------------------------------------------ hover card */
let cardTimer;
function showCard(p, ev) {
  clearTimeout(cardTimer);
  const c = $("#card");
  const img = p.media && p.media.path
    ? `<img src="${esc(p.media.path)}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'noimg',textContent:'no image yet'}))">`
    : `<div class="noimg">no image yet</div>`;
  const stg = (STAGE[p.stage] || {}).label || "";
  c.innerHTML = img + `<div class="body">
    <div class="nm">${esc(p.name)}</div>
    <div class="meta"><span class="u">${homesLabel(p.net_units)}</span> &middot; ${esc(stg)} &middot; ${esc(p.neighborhood || "")}</div>
    ${p.change ? `<div class="rep"><b>${esc(p.change)}</b></div>` : ""}
    ${p.media && p.media.caption ? `<div class="rep" style="border:0;padding-top:4px">${esc(p.media.caption)}</div>` : ""}
  </div>`;
  c.hidden = false;
  moveCard(ev.clientX || 0, ev.clientY || 0);
}
function moveCard(x, y) {
  const c = $("#card");
  const w = 260, h = c.offsetHeight || 240;
  c.style.left = Math.min(x + 16, innerWidth - w - 10) + "px";
  c.style.top = Math.max(10, Math.min(y + 16, innerHeight - h - 10)) + "px";
}
function hideCardSoon() { cardTimer = setTimeout(() => { $("#card").hidden = true; }, 120); }
document.addEventListener("mousemove", (e) => {
  if (!$("#card").hidden) moveCard(e.clientX, e.clientY);
});

/* ------------------------------------------------------------ filters */
function setFilter(k, v) {
  S.filters[k] = v;
  if (k === "nb") $("#f-nb").value = v;
  if (k === "stage") $("#f-stage").value = v;
  syncAll();
}
function syncAll() {
  renderLedger();
  renderTable();   // also redraws markers
}

/* ------------------------------------------------------------ footer */
function renderFooter() {
  const withImg = S.projects.filter((p) => p.media).length;
  const cov = S.projects.length ? Math.round((withImg / S.projects.length) * 100) : 0;
  const bySource = {};
  S.projects.forEach((p) => { bySource[p.media ? p.media.source : "none"] =
    (bySource[p.media ? p.media.source : "none"] || 0) + 1; });
  const names = {
    "6jgi-cpb4": "Development Pipeline",
    "i98e-djp9": "Building Permits (DBI)",
    "xdht-4php": "Housing Production 2005-present",
    "j67f-aayr": "Dwelling Unit Completion Counts",
  };
  const srcs = (S.manifest.sources || []).map((s) => {
    const d = (s.source_updated_at || s.fetched_at || "").slice(0, 10);
    return `<a href="https://data.sfgov.org/d/${s.resource_id}" target="_blank" rel="noopener">` +
      `${names[s.resource_id] || s.title}</a> <span>${d}</span>`;
  }).join("");
  $("#footer").innerHTML = `
    <div>Built from the City &amp; County of San Francisco open data portal.
    <b>Under construction</b> and <b>permitted</b> come from the Planning Department's quarterly
    Development Pipeline, topped up with new-construction permits the Dept. of Building Inspection
    issued in the last 24 months. Only projects with an <b>issued</b> construction permit are
    counted &mdash; ones merely approved or applied for are left out.
    <b>Completed ${S.summary.year || ""}</b> counts net certificates of occupancy from Housing
    Production and runs low early in the year because the city backfills it for months
    (it can also dip when phased public-housing rebuilds demolish before the replacements finish).
    <b>Adds vs. replaces</b> is read from the city's recorded demolition and existing-use fields:
    "adds" when nothing is torn down (ADUs, additions), "replaces" for teardowns and new
    construction on vacant or parking lots.
    <b>BMR</b> = below-market-rate (deed-restricted affordable) homes, from the pipeline's
    affordable-unit count; unknown for the raw DBI permits, shown as "?".
    Imagery: renderings and construction photos from Wikimedia Commons and SF Planning where
    available, otherwise a site aerial from Esri (${withImg}/${S.projects.length}, ${cov}%).</div>
    <div class="method"><b>How to read the counts.</b> These are a <i>cumulative stock</i> &mdash;
    every project currently building or currently holding an unbuilt permit &mdash; not a single
    year's activity. They count <i>net</i> new homes (proposed minus existing minus demolished)
    and include a long tail of small ADU / added-unit projects. So they are not comparable to
    annual permit or completion figures from the Census Building Permits Survey or dashboards
    built on it; expect this page to read higher.</div>
    <div class="src">${srcs}</div>
    <div style="margin-top:8px">Refresh locally with <code>python scripts/update.py</code>.</div>`;
}

/* ------------------------------------------------------------ util */
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

boot();
