/**
 * FairTrees — Empty Basin Tracker
 *
 * The whole dataset (a few thousand records, ~130 KB gzipped) is fetched once and
 * filtered in the browser, so changing a filter is instant and needs no round
 * trip. Photographs are the only thing fetched lazily, because each one has to
 * be unwrapped from the City's portal by the Worker.
 */

// Mirrors PLANTED_OUTCOMES / OPEN_OUTCOME in src/transform.mjs, which produces
// these labels. Kept in sync by test/ui-labels.test.mjs.
const PLANTED = new Set(["Tree planted", "Queued for planting"]);

const PAGE_FIRST = 12;   // small first batch so the top of the grid fills fast
const PAGE_MORE = 24;
// Infinite scroll alone would make the outcome breakdown, the method notes and
// the footer unreachable, so it stops after this many cards and hands over to an
// explicit button.
const AUTO_LOAD_MAX = 96;
const TABLE_LIMIT = 500;

const el = (id) => document.getElementById(id);

/**
 * Every same-origin URL is resolved against the document's own directory, so the
 * site works unchanged at the root or under a path such as /tracker/. The Worker
 * redirects /tracker to /tracker/ so this always has a directory to resolve from.
 */
const url = (path) => new URL(path, document.baseURI).toString();
const fmt = new Intl.NumberFormat("en-US");

const state = {
  cases: [],
  boundaryLayers: null,
  matching: [],
  meta: { districts: [], neighborhoods: [] },
  filtered: [],
  shown: 0,
  view: "grid",
  autoLimit: AUTO_LOAD_MAX,
  suppressAutoLoad: false,
  suppressTimer: null,
  map: null,
  markers: null,
  lightboxIndex: -1,
};

const controls = {
  search: el("fSearch"),
  district: el("fDistrict"),
  neighborhood: el("fNeighborhood"),
  status: el("fStatus"),
  reason: el("fReason"),
  since: el("fSince"),
  sort: el("fSort"),
  photos: el("fPhotos"),
};

/* ------------------------------- utilities ------------------------------- */

const DAY = 86400000;

function daysBetween(from, to) {
  if (!from) return null;
  const start = Date.parse(`${from}T00:00:00Z`);
  const end = to ? Date.parse(`${to}T00:00:00Z`) : Date.now();
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  return Math.max(0, Math.round((end - start) / DAY));
}

function prettyDate(iso) {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
}

function photoSrc(token) {
  if (!token) return null;
  if (token.startsWith("v:")) {
    const [caseid, formref] = token.slice(2).split(":");
    return url(`api/photo/${encodeURIComponent(caseid)}/${encodeURIComponent(formref)}`);
  }
  return token;
}

const mapsLink = (addr) =>
  `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${addr}, San Francisco, CA`)}`;
const ticketLink = (id) => `https://mobile311.sfgov.org/tickets/${encodeURIComponent(id)}`;

/* --------------------------- URL <-> filter state --------------------------- */

const URL_KEYS = {
  district: "d", neighborhood: "n", status: "s",
  reason: "r", since: "since", sort: "sort", search: "q",
};

function readUrl() {
  const params = new URLSearchParams(location.search);

  // The Streamlit version linked as ?district=9 (or ?district=Citywide), and
  // that URL is on the petition site and in printed QR codes. Honour it so those
  // links keep landing on the right district.
  const legacyDistrict = params.get("district");
  if (legacyDistrict !== null && !params.has("d") && legacyDistrict !== "Citywide") {
    const id = String(Number(legacyDistrict));
    if (Array.from(controls.district.options).some((o) => o.value === id)) {
      controls.district.value = id;
    }
  }

  for (const [name, key] of Object.entries(URL_KEYS)) {
    const value = params.get(key);
    if (value === null) continue;
    const control = controls[name];
    // Only accept a value the control actually offers.
    if (control.tagName === "SELECT" && !Array.from(control.options).some((o) => o.value === value)) continue;
    control.value = value;
  }
  if (params.get("photos") === "0") controls.photos.checked = false;
}

function writeUrl() {
  const params = new URLSearchParams();
  for (const [name, key] of Object.entries(URL_KEYS)) {
    const value = controls[name].value;
    if (value) params.set(key, value);
  }
  if (!controls.photos.checked) params.set("photos", "0");
  const qs = params.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);  // path preserved
}

/* -------------------------------- filtering -------------------------------- */

/** Every active filter except the photo toggle, which is applied separately. */
function matchesFilters(c, f) {
  if (f.district && c.d !== f.district) return false;
  if (f.neighborhood) {
    if (f.neighborhood === "__none__") { if (c.n) return false; }
    else if (c.n !== f.neighborhood) return false;
  }
  if (f.status === "open" && !c.s) return false;
  if (f.status === "closed" && c.s) return false;
  if (f.reason && c.r !== f.reason) return false;
  if (f.cutoff !== null) {
    const t = c.o ? Date.parse(`${c.o}T00:00:00Z`) : null;
    if (t === null || t < f.cutoff) return false;
  }
  if (f.q && !`${c.a} ${c.n || ""} ${c.note || ""} ${c.id}`.toLowerCase().includes(f.q)) return false;
  return true;
}

function applyFilters() {
  const sinceDays = Number(controls.since.value) || 0;
  const f = {
    q: controls.search.value.trim().toLowerCase(),
    district: controls.district.value,
    neighborhood: controls.neighborhood.value,
    status: controls.status.value,
    reason: controls.reason.value,
    cutoff: sinceDays ? Date.now() - sinceDays * DAY : null,
  };
  const photosOnly = controls.photos.checked;

  // Every report matching the real filters. The statistics are computed from
  // this set, never from the photo-filtered subset: whether a resident attached
  // a photograph says nothing about how the City handled the report, so letting
  // that toggle move the medians would bias them.
  const matching = state.cases.filter((c) => matchesFilters(c, f));
  state.matching = matching;
  state.photosOnly = photosOnly;

  const rows = photosOnly ? matching.filter((c) => c.p) : matching;

  const openDays = (c) => daysBetween(c.o, c.c) ?? -1;
  const sorters = {
    newest: (a, b) => (b.o || "").localeCompare(a.o || ""),
    oldest: (a, b) => (a.o || "").localeCompare(b.o || ""),
    longest: (a, b) => openDays(b) - openDays(a),
  };
  state.filtered = rows.sort(sorters[controls.sort.value] || sorters.newest);
  state.shown = 0;
  state.autoLimit = AUTO_LOAD_MAX;
}

/* --------------------------------- stats ---------------------------------- */

function renderStats() {
  const rows = state.matching;
  const total = rows.length;
  const open = rows.filter((c) => c.s).length;
  const closed = rows.filter((c) => !c.s);

  const durations = closed.map((c) => daysBetween(c.o, c.c)).filter((n) => n !== null).sort((a, b) => a - b);
  const median = durations.length
    ? durations.length % 2
      ? durations[(durations.length - 1) / 2]
      : Math.round((durations[durations.length / 2 - 1] + durations[durations.length / 2]) / 2)
    : null;

  // A closed ticket is not a planted tree. Report the gap directly, since it is
  // the whole point of the tracker.
  const planted = closed.filter((c) => PLANTED.has(c.r)).length;
  const noTree = closed.length - planted;
  const noTreeShare = closed.length ? Math.round((noTree / closed.length) * 100) : 0;

  const tiles = [
    {
      label: "Basins reported",
      value: fmt.format(total),
      note: `${fmt.format(rows.filter((c) => c.p).length)} carry a photograph`,
    },
    {
      label: "Still open",
      value: fmt.format(open),
      note: total ? `${Math.round((open / total) * 100)}% of all reports` : "—",
      open: open > 0,
    },
    {
      label: "Median days to close",
      value: median === null ? "—" : fmt.format(median),
      note: `across ${fmt.format(closed.length)} closed reports`,
    },
    {
      label: "Closed, no planting recorded",
      value: `${noTreeShare}%`,
      note: `${fmt.format(noTree)} of ${fmt.format(closed.length)} closed reports`,
      open: noTreeShare >= 90,
    },
  ];

  el("stats").innerHTML = tiles
    .map(
      (t) => `<div class="stat">
        <div class="stat-label">${t.label}</div>
        <div class="stat-value${t.open ? " is-open" : ""}">${t.value}</div>
        <div class="stat-note">${t.note}</div>
      </div>`
    )
    .join("");

  const scope = [];
  if (controls.district.value) {
    const d = state.meta.districts.find((x) => x.id === controls.district.value);
    scope.push(`District ${controls.district.value}${d?.supervisor ? ` (Supervisor ${d.supervisor})` : ""}`);
  }
  if (controls.neighborhood.value) {
    scope.push(controls.neighborhood.value === "__none__" ? "location not recorded" : controls.neighborhood.value);
  }
  const sinceLabel = controls.since.selectedOptions[0]?.textContent.toLowerCase();
  const photoNote = state.photosOnly
    ? " Figures cover every matching report; the gallery below shows only those with a photograph."
    : "";
  el("statsScope").textContent =
    `Showing ${scope.length ? scope.join(" · ") : "all of San Francisco"}` +
    `${controls.since.value ? `, reported in the ${sinceLabel}` : ", all dates"}.${photoNote}`;
}

/* -------------------------------- breakdown ------------------------------- */

function renderBreakdown() {
  const counts = new Map();
  for (const c of state.matching) counts.set(c.r, (counts.get(c.r) || 0) + 1);

  const rows = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  const total = state.matching.length;
  const max = rows.length ? rows[0][1] : 1;

  if (!rows.length) {
    el("breakdownChart").innerHTML = `<p class="stat-note">No reports match the current filters.</p>`;
    return;
  }

  // One series (counts), so one hue and no legend — the row label is the identity.
  el("breakdownChart").innerHTML = rows
    .map(([reason, count]) => {
      const share = total ? Math.round((count / total) * 100) : 0;
      return `<div class="bar-row">
        <div class="bar-label" title="${escapeAttr(reason)}">${escapeHtml(reason)}</div>
        <div class="bar-track" role="img" aria-label="${escapeAttr(reason)}: ${count} reports, ${share}% of the total">
          <div class="bar-fill" style="width:${Math.max((count / max) * 100, 0.6)}%"></div>
        </div>
        <div class="bar-value">${fmt.format(count)} <span>· ${share}%</span></div>
      </div>`;
    })
    .join("");
}

/* --------------------------------- gallery -------------------------------- */

const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const escapeAttr = escapeHtml;

function statusChip(c) {
  const days = daysBetween(c.o, c.c);
  if (c.s) {
    return `<span class="chip chip-open">⚠ Open ${days !== null ? `${fmt.format(days)} days` : ""}</span>`;
  }
  const good = PLANTED.has(c.r);
  return `<span class="chip${good ? " chip-good" : ""}">${good ? "✓" : "●"} ${escapeHtml(c.r)}</span>`;
}

function cardHtml(c, index) {
  const src = photoSrc(c.p);
  const days = daysBetween(c.o, c.c);
  const place = [c.n, c.d ? `District ${c.d}` : null].filter(Boolean).join(" · ") || "Location not recorded";

  const figure = src
    ? `<button class="card-figure is-pending" data-index="${index}" aria-label="Enlarge photograph of ${escapeAttr(c.a)}">
         <img src="${escapeAttr(src)}" alt="Reported empty tree basin at ${escapeAttr(c.a)}"
              loading="lazy" decoding="async" width="400" height="300">
       </button>`
    : `<div class="card-figure is-failed" aria-hidden="true"></div>`;

  return `<article class="card">
    ${figure}
    <div class="card-body">
      <div class="card-addr"><a href="${escapeAttr(mapsLink(c.a))}" target="_blank" rel="noopener">${escapeHtml(c.a)}</a></div>
      <div class="card-place">${escapeHtml(place)}</div>
      <div class="card-dates">
        Reported ${prettyDate(c.o)}${c.c ? ` · closed ${prettyDate(c.c)}` : ""}${
          days !== null && !c.s ? ` · ${fmt.format(days)} days` : ""
        }
      </div>
      <div class="card-foot">
        ${statusChip(c)}
        <a class="card-ticket" href="${escapeAttr(ticketLink(c.id))}" target="_blank" rel="noopener">#${escapeHtml(c.id)} ↗</a>
      </div>
    </div>
  </article>`;
}

function appendPage(size) {
  const slice = state.filtered.slice(state.shown, state.shown + size);
  if (!slice.length) return;

  const html = slice.map((c, i) => cardHtml(c, state.shown + i)).join("");
  el("gallery").insertAdjacentHTML("beforeend", html);
  state.shown += slice.length;

  // Fade each photograph in only once it has actually decoded, and swap the
  // skeleton for a quiet placeholder if the portal cannot produce it.
  for (const img of el("gallery").querySelectorAll("img:not([data-bound])")) {
    img.dataset.bound = "1";
    const figure = img.closest(".card-figure");
    if (img.complete && img.naturalWidth) {
      figure.classList.remove("is-pending");
      img.classList.add("is-loaded");
      continue;
    }
    img.addEventListener("load", () => {
      figure.classList.remove("is-pending");
      img.classList.add("is-loaded");
    }, { once: true });
    img.addEventListener("error", () => {
      figure.classList.remove("is-pending");
      figure.classList.add("is-failed");
      img.remove();
    }, { once: true });
  }

  updateMoreControls();
}

/** Show whichever of "loading" / "show more" / "that's all" currently applies. */
function updateMoreControls() {
  const remaining = state.filtered.length - state.shown;
  const button = el("showMore");
  el("loadingMore").hidden = true;
  el("allShown").hidden = remaining > 0;
  if (remaining <= 0) {
    button.hidden = true;
    return;
  }
  if (state.shown < state.autoLimit) {
    button.hidden = true;
    el("loadingMore").hidden = false;
    return;
  }
  button.hidden = false;
  button.textContent = `Show more (${fmt.format(remaining)} remaining)`;
}

/* ---------------------------------- table --------------------------------- */

function renderTable() {
  const rows = state.filtered.slice(0, TABLE_LIMIT);
  el("dataTable").querySelector("tbody").innerHTML = rows
    .map((c) => {
      const days = daysBetween(c.o, c.c);
      return `<tr>
        <td><a href="${escapeAttr(ticketLink(c.id))}" target="_blank" rel="noopener">${escapeHtml(c.a)}</a></td>
        <td class="num">${c.d ? escapeHtml(c.d) : "—"}</td>
        <td>${escapeHtml(c.n || "—")}</td>
        <td class="num">${prettyDate(c.o)}</td>
        <td class="num">${c.c ? prettyDate(c.c) : "—"}</td>
        <td class="num">${days === null ? "—" : fmt.format(days)}</td>
        <td>${escapeHtml(c.s ? "Still open" : c.r)}</td>
      </tr>`;
    })
    .join("");
  el("tableMore").hidden = state.filtered.length <= TABLE_LIMIT;
}

/* ----------------------------------- map ---------------------------------- */

let leafletPromise = null;

/**
 * Leaflet is vendored into /vendor rather than pulled from a CDN: one less
 * third-party dependency that can fail, and it is served from the same edge as
 * the rest of the site. Loaded on demand because most visitors never open the map.
 */
function loadLeaflet() {
  if (leafletPromise) return leafletPromise;
  leafletPromise = new Promise((resolve, reject) => {
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = url("vendor/leaflet/leaflet.css");
    document.head.append(css);

    const script = document.createElement("script");
    script.src = url("vendor/leaflet/leaflet.js");
    script.onload = () => (window.L ? resolve(window.L) : reject(new Error("Leaflet did not initialise")));
    script.onerror = () => reject(new Error("Leaflet failed to load"));
    document.head.append(script);
  });
  return leafletPromise;
}

let boundariesPromise = null;

/** Districts and neighborhoods, simplified at build time. ~19 KB gzipped. */
function loadBoundaries() {
  if (!boundariesPromise) {
    boundariesPromise = fetch(url("data/boundaries.json"))
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
  }
  return boundariesPromise;
}

function boundaryStyle(active) {
  return active
    ? { color: "#1b5e45", weight: 2.5, opacity: 0.95, fill: true, fillColor: "#1b5e45", fillOpacity: 0.07 }
    : { color: "#8d8b85", weight: 1, opacity: 0.5, fill: false };
}

/**
 * Restyle rather than redraw: the selected district or neighborhood is outlined
 * so the dots are read against the boundary the filters are talking about.
 */
function styleBoundaries() {
  if (!state.boundaryLayers) return;
  const district = controls.district.value;
  const neighborhood = controls.neighborhood.value;
  for (const { layer, kind, key } of state.boundaryLayers) {
    const active =
      (kind === "district" && district && key === district) ||
      (kind === "neighborhood" && neighborhood && key === neighborhood);
    // Neighborhood outlines only appear when one is selected; all 41 at once is noise.
    const visible = kind === "district" || active;
    layer.setStyle(visible ? boundaryStyle(active) : { opacity: 0, fill: false });
  }
}

async function renderMap() {
  let L;
  try {
    L = await loadLeaflet();
  } catch {
    el("map").innerHTML =
      '<p style="padding:20px;color:var(--ink-muted)">The map library could not be loaded. The photo and table views still work.</p>';
    return;
  }

  if (!state.map) {
    // Canvas rather than one SVG node per report: the city-wide view plots a few
    // thousand points, which is slow and memory-hungry as SVG.
    state.map = L.map("map", { scrollWheelZoom: false, preferCanvas: true })
      .setView([37.7749, -122.4294], 12);

    // A keyless basemap. CARTO's free tiles began demanding an API key and started
    // returning watermarked images, so this one is drawn from Esri instead — and
    // the district outlines below are served from our own origin, so the map still
    // makes sense if this layer ever fails too.
    L.tileLayer(
      "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
      {
        attribution:
          'Tiles &copy; <a href="https://www.esri.com/">Esri</a> — Esri, HERE, Garmin, ' +
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18,
      }
    ).addTo(state.map);

    state.boundaryGroup = L.layerGroup().addTo(state.map);
    state.markers = L.layerGroup().addTo(state.map);

    const boundaries = await loadBoundaries();
    if (boundaries) {
      state.boundaryLayers = [];
      for (const [kind, collection] of [
        ["neighborhood", boundaries.neighborhoods],
        ["district", boundaries.districts],
      ]) {
        for (const feature of collection.features) {
          const key = kind === "district" ? feature.properties.id : feature.properties.name;
          const layer = L.geoJSON(feature, {
            style: boundaryStyle(false),
            interactive: false,   // never steal a click from a report dot
          }).addTo(state.boundaryGroup);
          state.boundaryLayers.push({ layer, kind, key });
        }
      }
    }
  }

  styleBoundaries();
  state.markers.clearLayers();
  const points = state.filtered.filter((c) => c.lat !== null);

  // Reports cluster tightly in some corridors. A small semi-transparent mark lets
  // that density read as a darker patch instead of one dot hiding twenty others.
  const dense = points.length > 400;
  for (const c of points) {
    const open = Boolean(c.s);
    L.circleMarker([c.lat, c.lng], {
      radius: dense ? 4 : 6,
      weight: dense ? 1 : 2,   // a surface ring keeps sparse marks crisp
      color: "#fcfcfb",
      fillColor: open ? "#d03b3b" : "#6b6a65",
      fillOpacity: dense ? 0.6 : 0.92,
      opacity: dense ? 0.5 : 1,
    })
      .bindPopup(
        `<b>${escapeHtml(c.a)}</b>${escapeHtml(c.n || "")}${c.d ? ` · District ${escapeHtml(c.d)}` : ""}<br>` +
          `Reported ${prettyDate(c.o)}<br>${open ? "<b>Still open</b>" : `Closed ${prettyDate(c.c)} — ${escapeHtml(c.r)}`}<br>` +
          `<a href="${escapeAttr(ticketLink(c.id))}" target="_blank" rel="noopener">311 ticket #${escapeHtml(c.id)}</a>`
      )
      .addTo(state.markers);
  }

  if (points.length) {
    state.map.fitBounds(points.map((c) => [c.lat, c.lng]), { padding: [28, 28], maxZoom: 15 });
  }
  state.map.invalidateSize();
}

/* --------------------------------- lightbox -------------------------------- */

const lightbox = el("lightbox");

function openLightbox(index) {
  const withPhotos = state.filtered.slice(0, state.shown);
  const c = withPhotos[index];
  if (!c) return;
  state.lightboxIndex = index;

  el("lightboxImg").src = photoSrc(c.p);
  el("lightboxImg").alt = `Reported empty tree basin at ${c.a}`;
  el("lightboxCaption").innerHTML =
    `<b>${escapeHtml(c.a)}</b>${escapeHtml([c.n, c.d ? `District ${c.d}` : null].filter(Boolean).join(" · "))}<br>` +
    `Reported ${prettyDate(c.o)}${c.c ? ` · closed ${prettyDate(c.c)}` : " · still open"}` +
    `${c.note ? `<br>311 note: ${escapeHtml(c.note)}` : ""}<br>` +
    `<a href="${escapeAttr(ticketLink(c.id))}" target="_blank" rel="noopener">View 311 ticket #${escapeHtml(c.id)}</a>`;

  if (!lightbox.open) lightbox.showModal();
}

function stepLightbox(delta) {
  const pool = state.filtered.slice(0, state.shown);
  let i = state.lightboxIndex;
  for (let guard = 0; guard < pool.length; guard++) {
    i = (i + delta + pool.length) % pool.length;
    if (pool[i]?.p) break;
  }
  openLightbox(i);
}

/* ---------------------------------- render --------------------------------- */

function render() {
  applyFilters();
  renderStats();
  renderBreakdown();

  const count = state.filtered.length;
  el("resultsCount").textContent = count
    ? `${fmt.format(count)} report${count === 1 ? "" : "s"} match`
    : "No reports match these filters";
  el("empty").hidden = count > 0;

  el("gallery").innerHTML = "";
  updateMoreControls();
  if (state.view === "grid") appendPage(PAGE_FIRST);
  if (state.view === "table") renderTable();
  if (state.view === "map") renderMap();

  writeUrl();
}

function setView(view) {
  state.view = view;
  for (const button of document.querySelectorAll(".view-switch button")) {
    button.setAttribute("aria-selected", String(button.dataset.view === view));
  }
  el("viewGrid").hidden = view !== "grid";
  el("viewMap").hidden = view !== "map";
  el("viewTable").hidden = view !== "table";

  el("resultsTitle").textContent =
    view === "map" ? "Map of reports" : view === "table" ? "All matching reports" : "Visual evidence";

  if (view === "grid" && !state.shown) appendPage(PAGE_FIRST);
  if (view === "table") renderTable();
  if (view === "map") renderMap();

  // The switch lives above the results, so bring them into view.
  const top = el("results").getBoundingClientRect().top;
  if (top < 0 || top > window.innerHeight * 0.6) {
    el("results").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

/* ----------------------------------- init ---------------------------------- */

function populateSelects() {
  controls.district.insertAdjacentHTML(
    "beforeend",
    state.meta.districts
      .map((d) => `<option value="${escapeAttr(d.id)}">District ${escapeHtml(d.id)} — ${escapeHtml(d.supervisor)}</option>`)
      .join("")
  );

  const present = new Set(state.cases.map((c) => c.n).filter(Boolean));
  const names = state.meta.neighborhoods.filter((n) => present.has(n));
  controls.neighborhood.insertAdjacentHTML(
    "beforeend",
    names.map((n) => `<option value="${escapeAttr(n)}">${escapeHtml(n)}</option>`).join("") +
      `<option value="__none__">Location not recorded</option>`
  );

  // Label each outcome with its total, so it is obvious up front which outcomes
  // are common and which will narrow the view to almost nothing.
  const reasonCounts = new Map();
  for (const c of state.cases) reasonCounts.set(c.r, (reasonCounts.get(c.r) || 0) + 1);
  const reasons = [...reasonCounts.entries()].sort((a, b) => b[1] - a[1]);
  controls.reason.insertAdjacentHTML(
    "beforeend",
    reasons
      .map(([r, n]) => `<option value="${escapeAttr(r)}">${escapeHtml(r)} (${fmt.format(n)})</option>`)
      .join("")
  );
}

function wireEvents() {
  let debounce;
  controls.search.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(render, 180);
  });
  for (const name of ["district", "neighborhood", "status", "reason", "since", "sort"]) {
    controls[name].addEventListener("change", render);
  }
  controls.photos.addEventListener("change", render);

  const reset = () => {
    controls.search.value = "";
    controls.district.value = "";
    controls.neighborhood.value = "";
    controls.status.value = "";
    controls.reason.value = "";
    controls.since.value = "548";
    controls.sort.value = "newest";
    controls.photos.checked = true;
    render();
  };
  el("fReset").addEventListener("click", reset);
  for (const b of document.querySelectorAll("[data-reset]")) b.addEventListener("click", reset);

  for (const button of document.querySelectorAll(".view-switch button")) {
    button.addEventListener("click", () => setView(button.dataset.view));
  }

  // Infinite scroll: load the next batch as the sentinel nears the viewport.
  new IntersectionObserver(
    (entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      if (state.view !== "grid") return;
      if (state.shown >= state.filtered.length) return;
      if (state.shown >= state.autoLimit) return;   // hand over to the button
      if (state.suppressAutoLoad) return;           // an in-page jump is in flight
      appendPage(PAGE_MORE);
    },
    { rootMargin: "800px 0px" }
  ).observe(el("sentinel"));

  // Jumping to a section scrolls past the sentinel. Without this, the jump would
  // load another batch of cards, push the target back down the page, and land the
  // reader short of the section they asked for.
  for (const link of document.querySelectorAll('a[href^="#"]')) {
    link.addEventListener("click", () => {
      state.suppressAutoLoad = true;
      clearTimeout(state.suppressTimer);
      state.suppressTimer = setTimeout(() => { state.suppressAutoLoad = false; }, 1200);
    });
  }

  el("showMore").addEventListener("click", () => {
    state.autoLimit = state.shown + AUTO_LOAD_MAX;
    appendPage(PAGE_MORE);
  });

  el("gallery").addEventListener("click", (event) => {
    const figure = event.target.closest(".card-figure[data-index]");
    if (figure) openLightbox(Number(figure.dataset.index));
  });

  lightbox.querySelector(".lightbox-close").addEventListener("click", () => lightbox.close());
  lightbox.querySelector(".lightbox-prev").addEventListener("click", () => stepLightbox(-1));
  lightbox.querySelector(".lightbox-next").addEventListener("click", () => stepLightbox(1));
  lightbox.addEventListener("click", (event) => {
    // Clicking the backdrop (but not the image or a control) closes.
    if (event.target === lightbox || event.target.classList.contains("lightbox-figure")) lightbox.close();
  });
  document.addEventListener("keydown", (event) => {
    if (!lightbox.open) return;
    if (event.key === "ArrowRight") stepLightbox(1);
    if (event.key === "ArrowLeft") stepLightbox(-1);
  });

  const toggle = document.querySelector(".theme-toggle");
  toggle.addEventListener("click", () => {
    const dark = matchMedia("(prefers-color-scheme: dark)").matches;
    const current = document.documentElement.dataset.theme || (dark ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("fairtrees-theme", next); } catch { /* private mode */ }
  });
}

function restoreTheme() {
  try {
    const saved = localStorage.getItem("fairtrees-theme");
    if (saved === "dark" || saved === "light") document.documentElement.dataset.theme = saved;
  } catch { /* storage unavailable; fall back to the OS setting */ }
}

async function loadData() {
  const [casesRes, metaRes] = await Promise.all([
    fetch(url("api/cases")).catch(() => null),
    fetch(url("data/meta.json")).catch(() => null),
  ]);

  let payload = casesRes?.ok ? await casesRes.json() : null;
  if (!payload?.cases) {
    // The Worker already falls back to the snapshot; this covers the Worker
    // itself being unreachable.
    const snap = await fetch(url("data/snapshot.json"));
    payload = await snap.json();
  }
  state.cases = payload.cases || [];

  if (metaRes?.ok) state.meta = await metaRes.json();
  if (!state.meta.neighborhoods?.length) {
    state.meta.neighborhoods = [...new Set(state.cases.map((c) => c.n).filter(Boolean))].sort();
  }
  if (!state.meta.districts?.length) {
    state.meta.districts = [...new Set(state.cases.map((c) => c.d).filter(Boolean))]
      .sort((a, b) => Number(a) - Number(b))
      .map((id) => ({ id, supervisor: "" }));
  }

  const when = payload.generated ? new Date(payload.generated) : null;
  const stamp = when ? when.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" }) : null;
  let provenance = "";
  if (stamp && payload.source === "live") {
    provenance = `Data pulled from the City's live 311 API at ${stamp}.`;
  } else if (stamp && payload.refreshing) {
    provenance =
      `Showing the snapshot built ${stamp}. A fresh pull from the City's 311 API is ` +
      `running now — reload in a moment to see it.`;
  } else if (stamp) {
    provenance = `Showing the snapshot built ${stamp}, because the City's 311 API did not respond.`;
  }
  el("updated").textContent = provenance;
}

async function main() {
  restoreTheme();
  try {
    await loadData();
  } catch (err) {
    el("gallery").innerHTML = `<p class="stat-note">Case data could not be loaded: ${escapeHtml(err.message)}</p>`;
    return;
  }
  populateSelects();
  readUrl();
  wireEvents();
  render();
}

main();
