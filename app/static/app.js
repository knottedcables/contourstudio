/* Contour Studio frontend: map + geographic selection box + render preview.
 *
 * The selection box is stored as a geographic bbox (west/south/east/north)
 * and re-projected to screen pixels whenever the map moves, so it stays
 * anchored to the terrain while panning/zooming.
 */

"use strict";

const statusEl = document.getElementById("status");
const previewEl = document.getElementById("preview");
const renderBtn = document.getElementById("render-btn");
const boxEl = document.getElementById("selbox");

/* Basemap layers (UI only — never in exports). CyclOSM default: its
 * hillshading reads terrain far better than the standard OSM style.
 * "Cycle Map" (Thunderforest) needs a paid API key, so OpenTopoMap is the
 * third option instead. */
const BASEMAPS = {
  cyclosm: {
    tiles: ["a", "b", "c"].map(
      (s) => `https://${s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png`
    ),
    maxzoom: 19,
    attribution: "© OpenStreetMap contributors · CyclOSM",
  },
  osm: {
    tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    maxzoom: 19,
    attribution: "© OpenStreetMap contributors",
  },
  opentopo: {
    tiles: ["a", "b", "c"].map(
      (s) => `https://${s}.tile.opentopomap.org/{z}/{x}/{y}.png`
    ),
    maxzoom: 17,
    attribution: "© OpenStreetMap contributors, SRTM · © OpenTopoMap (CC-BY-SA)",
  },
};

function basemapStyle(key) {
  const b = BASEMAPS[key];
  return {
    version: 8,
    sources: {
      basemap: {
        type: "raster",
        tiles: b.tiles,
        tileSize: 256,
        maxzoom: b.maxzoom,
        attribution: b.attribution,
      },
    },
    layers: [{ id: "basemap", type: "raster", source: "basemap" }],
  };
}

const basemapEl = document.getElementById("basemap");
basemapEl.value = localStorage.getItem("basemap") || "cyclosm";

const map = new maplibregl.Map({
  container: "map",
  center: [-121.76, 46.86], // Mt. Rainier — instant gratification terrain
  zoom: 10,
  style: basemapStyle(basemapEl.value),
});
map.addControl(new maplibregl.NavigationControl(), "top-left");

basemapEl.addEventListener("change", () => {
  localStorage.setItem("basemap", basemapEl.value);
  map.setStyle(basemapStyle(basemapEl.value)); // keeps center/zoom; the
  // selection box is a DOM overlay, so it is unaffected by style swaps
});

/* ---------- selection box ---------- */

let bbox = null; // {w, s, e, n} in degrees

function defaultBbox() {
  const b = map.getBounds();
  const cx = (b.getWest() + b.getEast()) / 2;
  const cy = (b.getSouth() + b.getNorth()) / 2;
  const spanX = (b.getEast() - b.getWest()) * 0.3;
  const spanY = (b.getNorth() - b.getSouth()) * 0.3;
  return { w: cx - spanX, s: cy - spanY, e: cx + spanX, n: cy + spanY };
}

function positionBox() {
  if (!bbox) return;
  const tl = map.project([bbox.w, bbox.n]);
  const br = map.project([bbox.e, bbox.s]);
  boxEl.style.left = `${tl.x}px`;
  boxEl.style.top = `${tl.y}px`;
  boxEl.style.width = `${br.x - tl.x}px`;
  boxEl.style.height = `${br.y - tl.y}px`;
}

map.on("load", () => {
  bbox = defaultBbox();
  positionBox();
  requestRender();
});
map.on("move", positionBox);

/* Drag to move; corner handles to resize. Coordinates are tracked in screen
 * space during the gesture and converted back to geography on every step. */
let drag = null; // {mode, startX, startY, startBox}

boxEl.addEventListener("pointerdown", (ev) => {
  ev.stopPropagation(); // keep the map from panning underneath
  ev.preventDefault();
  const handle = ev.target.classList.contains("handle") ? ev.target : null;
  drag = {
    mode: handle ? [...handle.classList].find((c) => c !== "handle") : "move",
    startX: ev.clientX,
    startY: ev.clientY,
    startBox: { ...bbox },
  };
  boxEl.setPointerCapture(ev.pointerId);
});

boxEl.addEventListener("pointermove", (ev) => {
  if (!drag) return;
  const dx = ev.clientX - drag.startX;
  const dy = ev.clientY - drag.startY;
  const sb = drag.startBox;
  const tl = map.project([sb.w, sb.n]);
  const br = map.project([sb.e, sb.s]);

  if (drag.mode === "move") {
    tl.x += dx; tl.y += dy; br.x += dx; br.y += dy;
  } else {
    if (drag.mode.includes("n")) tl.y += dy;
    if (drag.mode.includes("s")) br.y += dy;
    if (drag.mode.includes("w")) tl.x += dx;
    if (drag.mode.includes("e")) br.x += dx;
    // enforce a minimum 20 px box so it cannot be inverted
    if (br.x - tl.x < 20 || br.y - tl.y < 20) return;
  }
  const nw = map.unproject([tl.x, tl.y]);
  const se = map.unproject([br.x, br.y]);
  bbox = { w: nw.lng, n: nw.lat, e: se.lng, s: se.lat };
  positionBox();
});

boxEl.addEventListener("pointerup", (ev) => {
  if (!drag) return;
  drag = null;
  boxEl.releasePointerCapture(ev.pointerId);
  requestRender(); // re-render when the user releases the box
});

/* ---------- style controls ---------- */

const SLIDERS = ["interval", "smoothing", "simplify", "min_ring", "line_weight"];
const SLIDER_UNITS = { simplify: " mm", min_ring: " mm²", line_weight: " mm" };

/* interval slider range depends on the elevation unit */
const INTERVAL_RANGES = {
  ft: { min: 5, max: 500, step: 5, initial: 150 },
  m: { min: 2, max: 150, step: 2, initial: 50 },
};

function currentUnits() {
  return document.querySelector('input[name="units"]:checked').value;
}

function readSettings() {
  const s = { units: currentUnits() };
  for (const id of SLIDERS) s[id] = Number(document.getElementById(id).value);
  return s;
}

function updateValueLabels() {
  const s = readSettings();
  for (const id of SLIDERS) {
    const unit = id === "interval" ? ` ${s.units}` : SLIDER_UNITS[id] || "";
    document.getElementById(`${id}-val`).textContent = `${s[id]}${unit}`;
  }
}

for (const id of SLIDERS) {
  document.getElementById(id).addEventListener("input", () => {
    updateValueLabels();
    requestRender();
  });
}

for (const radio of document.querySelectorAll('input[name="units"]')) {
  radio.addEventListener("change", () => {
    // convert the interval to the new unit and swap the slider's range
    const el = document.getElementById("interval");
    const to = currentUnits();
    const factor = to === "m" ? 0.3048 : 1 / 0.3048;
    const r = INTERVAL_RANGES[to];
    const converted = Number(el.value) * factor;
    el.min = r.min;
    el.max = r.max;
    el.step = r.step;
    el.value = Math.min(r.max, Math.max(r.min, Math.round(converted / r.step) * r.step));
    updateValueLabels();
    requestRender();
  });
}

updateValueLabels();

/* ---------- place search (Nominatim, fail-soft) ---------- */

const searchEl = document.getElementById("search");
const resultsEl = document.getElementById("search-results");

searchEl.addEventListener("keydown", async (ev) => {
  if (ev.key !== "Enter" || !searchEl.value.trim()) return;
  resultsEl.hidden = true;
  setStatus("Searching…");
  try {
    const url =
      "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&q=" +
      encodeURIComponent(searchEl.value.trim());
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`search failed (${resp.status})`);
    const places = await resp.json();
    setStatus("");
    if (!places.length) return setStatus("No places found.", true);
    resultsEl.innerHTML = "";
    for (const place of places) {
      const li = document.createElement("li");
      li.textContent = place.display_name;
      li.addEventListener("click", () => {
        resultsEl.hidden = true;
        const [s, n, w, e] = place.boundingbox.map(Number);
        // maxZoom keeps point results (Nominatim returns a tiny box for
        // named places) from zooming past useful terrain-selection scale
        map.fitBounds([[w, s], [e, n]], { padding: 40, duration: 1200, maxZoom: 12 });
        // once we arrive, drop the selection box onto the new view
        map.once("moveend", () => {
          bbox = defaultBbox();
          positionBox();
          requestRender();
        });
      });
      resultsEl.appendChild(li);
    }
    resultsEl.hidden = false;
  } catch (err) {
    // Nominatim being down must never block the app (fail soft)
    setStatus(`Place search unavailable: ${err.message}`, true);
  }
});

document.addEventListener("click", (ev) => {
  if (!ev.target.closest("#search-wrap")) resultsEl.hidden = true;
});

/* ---------- rendering ---------- */

let renderTimer = null;
let inFlight = null;

function requestRender() {
  clearTimeout(renderTimer);
  renderTimer = setTimeout(doRender, 400); // debounce rapid changes
}

async function doRender() {
  if (!bbox) return;
  if (inFlight) inFlight.abort();
  const ctrl = new AbortController();
  inFlight = ctrl;
  setStatus("Rendering…");
  renderBtn.disabled = true;
  try {
    const resp = await fetch("/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bbox: [bbox.w, bbox.s, bbox.e, bbox.n], ...readSettings() }),
      signal: ctrl.signal,
    });
    if (!resp.ok) {
      const detail = (await resp.json().catch(() => ({}))).detail;
      throw new Error(detail || `Server error (${resp.status})`);
    }
    previewEl.innerHTML = await resp.text();
    previewEl.classList.remove("empty");
    setStatus("");
  } catch (err) {
    if (err.name !== "AbortError") setStatus(err.message, true);
  } finally {
    if (inFlight === ctrl) {
      inFlight = null;
      renderBtn.disabled = false;
    }
  }
}

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", isError);
}

renderBtn.addEventListener("click", doRender);
