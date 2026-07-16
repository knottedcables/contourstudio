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

const map = new maplibregl.Map({
  container: "map",
  center: [-121.76, 46.86], // Mt. Rainier — instant gratification terrain
  zoom: 10,
  style: {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: "© OpenStreetMap contributors",
      },
    },
    layers: [{ id: "osm", type: "raster", source: "osm" }],
  },
});
map.addControl(new maplibregl.NavigationControl(), "top-left");

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

/* ---------- rendering ---------- */

/* UI defaults sent with every render; these become the M3 slider values.
 * interval 150 ft keeps big mountainous selections readable — the spec's
 * 40 ft example turns Rainier-sized areas solid black. */
const settings = { interval: 150, units: "ft" };

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
      body: JSON.stringify({ bbox: [bbox.w, bbox.s, bbox.e, bbox.n], ...settings }),
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
