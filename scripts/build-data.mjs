#!/usr/bin/env node
/**
 * Builds the data snapshot and reference lists the app ships with.
 *
 * Everything is filtered server-side by SoQL, so only the few thousand matching
 * rows are ever transferred — never the full 311 table.
 *
 * Outputs:
 *   public/data/snapshot.json  compact case records (fallback when 311 is down)
 *   public/data/meta.json      districts + neighbourhood reference lists
 */
import { writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { casesRequestUrl, dedupe, toCase } from "../src/transform.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const DISTRICTS_URL = "https://data.sf.gov/resource/cqbw-m5m3.geojson";
const NEIGHBORHOODS_URL = "https://data.sf.gov/resource/j2bu-swwd.geojson";

async function getJSON(url, label) {
  for (let attempt = 1; attempt <= 4; attempt++) {
    try {
      const r = await fetch(url, { headers: { "User-Agent": "fairtrees.org data build" } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (err) {
      if (attempt === 4) throw new Error(`${label}: ${err.message}`);
      await new Promise((ok) => setTimeout(ok, 2 ** attempt * 1000));
    }
  }
}

/** Page through the feed so the build keeps working as the dataset grows. */
async function fetchAllCases() {
  const PAGE = 5000;
  const rows = [];
  for (let offset = 0; ; offset += PAGE) {
    const page = await getJSON(casesRequestUrl({ limit: PAGE, offset }), `cases offset=${offset}`);
    rows.push(...page);
    process.stderr.write(`  fetched ${rows.length} rows\n`);
    if (page.length < PAGE) break;
  }
  return rows;
}

/* ---------- geometry: place cases the 311 feed left unlabelled ---------- */

function ringContains(ring, x, y) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

// Inside the outer ring and outside every hole.
function polygonContains(polygon, x, y) {
  if (!polygon.length || !ringContains(polygon[0], x, y)) return false;
  return polygon.slice(1).every((hole) => !ringContains(hole, x, y));
}

function geometryContains(geometry, x, y) {
  if (geometry?.type === "Polygon") return polygonContains(geometry.coordinates, x, y);
  if (geometry?.type === "MultiPolygon") {
    return geometry.coordinates.some((poly) => polygonContains(poly, x, y));
  }
  return false;
}

function bbox(geometry) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const walk = (node) => {
    if (typeof node[0] === "number") {
      minX = Math.min(minX, node[0]); maxX = Math.max(maxX, node[0]);
      minY = Math.min(minY, node[1]); maxY = Math.max(maxY, node[1]);
    } else for (const child of node) walk(child);
  };
  if (geometry) walk(geometry.coordinates);
  return [minX, minY, maxX, maxY];
}

function buildIndex(features, nameOf) {
  return features
    .filter((f) => f.geometry)
    .map((f) => ({ name: nameOf(f.properties), geometry: f.geometry, box: bbox(f.geometry) }));
}

// Bounding-box reject first; full ray cast only for the few candidates left.
function locate(index, lng, lat) {
  for (const entry of index) {
    const [minX, minY, maxX, maxY] = entry.box;
    if (lng < minX || lng > maxX || lat < minY || lat > maxY) continue;
    if (geometryContains(entry.geometry, lng, lat)) return entry.name;
  }
  return null;
}


/* ---------- boundary simplification ---------- */

/** Perpendicular distance from p to the segment ab, in degrees. */
function segmentDistance(p, a, b) {
  let [x, y] = a;
  let dx = b[0] - x;
  let dy = b[1] - y;
  if (dx !== 0 || dy !== 0) {
    const t = ((p[0] - x) * dx + (p[1] - y) * dy) / (dx * dx + dy * dy);
    if (t > 1) [x, y] = b;
    else if (t > 0) { x += dx * t; y += dy * t; }
  }
  return Math.hypot(p[0] - x, p[1] - y);
}

/** Douglas-Peucker. Keeps the shape, drops the survey-grade vertex count. */
function simplifyRing(points, tolerance) {
  if (points.length <= 4) return points;
  let maxDist = 0;
  let index = 0;
  for (let i = 1; i < points.length - 1; i++) {
    const d = segmentDistance(points[i], points[0], points[points.length - 1]);
    if (d > maxDist) { maxDist = d; index = i; }
  }
  if (maxDist <= tolerance) return [points[0], points[points.length - 1]];
  return [
    ...simplifyRing(points.slice(0, index + 1), tolerance).slice(0, -1),
    ...simplifyRing(points.slice(index), tolerance),
  ];
}

const roundPoint = ([x, y]) => [Number(x.toFixed(5)), Number(y.toFixed(5))];

function simplifyGeometry(geometry, tolerance) {
  const ring = (r) => {
    // A polygon ring must stay closed after simplification.
    const simplified = simplifyRing(r.map(roundPoint), tolerance);
    if (simplified.length < 4) return null;
    const [first] = simplified;
    const last = simplified[simplified.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) simplified.push(first);
    return simplified;
  };
  const polygon = (rings) => rings.map(ring).filter(Boolean);

  if (geometry.type === "Polygon") {
    const rings = polygon(geometry.coordinates);
    return rings.length ? { type: "Polygon", coordinates: rings } : null;
  }
  if (geometry.type === "MultiPolygon") {
    const polys = geometry.coordinates.map(polygon).filter((p) => p.length);
    return polys.length ? { type: "MultiPolygon", coordinates: polys } : null;
  }
  return null;
}

/**
 * The map draws these itself rather than relying on a tile provider for the only
 * geographic context. Tiles can start demanding an API key — CARTO did — and when
 * that happens the districts and neighbourhoods still render.
 */
function boundaryCollection(features, nameOf, tolerance) {
  return {
    type: "FeatureCollection",
    features: features
      .filter((f) => f.geometry)
      .map((f) => ({
        type: "Feature",
        properties: nameOf(f.properties),
        geometry: simplifyGeometry(f.geometry, tolerance),
      }))
      .filter((f) => f.geometry),
  };
}

async function main() {
  process.stderr.write("Fetching 311 cases...\n");
  const [rawRows, districtGeo, neighborhoodGeo] = await Promise.all([
    fetchAllCases(),
    getJSON(DISTRICTS_URL, "districts"),
    getJSON(NEIGHBORHOODS_URL, "neighborhoods"),
  ]);

  const neighborhoodIndex = buildIndex(neighborhoodGeo.features, (p) => p.nhood);
  const districtIndex = buildIndex(districtGeo.features, (p) => String(Number(p.sup_dist_num)));

  const cases = dedupe(rawRows).map(toCase);

  // The 311 feed's supervisor_district field is not kept current: it still
  // reflects the pre-2022 district lines, so (for example) Tenderloin cases are
  // labelled District 6 although redistricting moved them to District 5. Where a
  // report has coordinates, assign its district from the City's current boundary
  // file instead of trusting that field. Reports without coordinates keep the
  // feed's value, since it is the only signal available.
  let placedNeighborhood = 0;
  let placedDistrict = 0;
  let correctedDistrict = 0;
  for (const c of cases) {
    if (c.lat === null) continue;
    // Derive the neighbourhood the same way as the district. The feed's
    // analysis_neighborhood field is currently accurate (4 disagreements
    // citywide at the time of writing, all on boundary edges), but deriving it
    // means neither field can drift out of step with the City's own polygons.
    const hood = locate(neighborhoodIndex, c.lng, c.lat);
    if (hood) {
      if (!c.n) placedNeighborhood++;
      c.n = hood;
    }
    const geo = locate(districtIndex, c.lng, c.lat);
    if (geo) {
      if (!c.d) placedDistrict++;
      else if (c.d !== geo) correctedDistrict++;
      c.d = geo;
    }
  }

  const withPhoto = cases.filter((c) => c.p).length;
  const neighborhoods = [...new Set(cases.map((c) => c.n).filter(Boolean))].sort();

  const districts = districtGeo.features
    .map((f) => ({
      id: String(Number(f.properties.sup_dist_num)),
      supervisor: f.properties.sup_name,
    }))
    .sort((a, b) => Number(a.id) - Number(b.id));

  // ~20 m of detail is plenty at city zoom and cuts the payload by an order of
  // magnitude; the map lazy-loads this only when the map view is opened.
  const TOLERANCE = 0.0002;
  const boundaries = {
    districts: boundaryCollection(
      districtGeo.features,
      (p) => ({ id: String(Number(p.sup_dist_num)), supervisor: p.sup_name }),
      TOLERANCE
    ),
    neighborhoods: boundaryCollection(
      neighborhoodGeo.features,
      (p) => ({ name: p.nhood }),
      TOLERANCE
    ),
  };

  await mkdir(resolve(ROOT, "public/data"), { recursive: true });
  await writeFile(resolve(ROOT, "public/data/boundaries.json"), JSON.stringify(boundaries));
  await writeFile(
    resolve(ROOT, "public/data/snapshot.json"),
    JSON.stringify({
      generated: new Date().toISOString(),
      source: "https://data.sfgov.org/City-Infrastructure/311-Cases/vw6y-z8j6",
      count: cases.length,
      withPhoto,
      cases,
    })
  );
  await writeFile(
    resolve(ROOT, "public/data/meta.json"),
    JSON.stringify({ generated: new Date().toISOString(), districts, neighborhoods }, null, 2)
  );

  const countPoints = (fc) =>
    fc.features.reduce((sum, f) => {
      const walk = (n) => (typeof n[0] === "number" ? 1 : n.reduce((a, c) => a + walk(c), 0));
      return sum + walk(f.geometry.coordinates);
    }, 0);
  process.stderr.write(
    `  boundaries: ${boundaries.districts.features.length} districts ` +
      `(${countPoints(boundaries.districts)} pts), ` +
      `${boundaries.neighborhoods.features.length} neighborhoods ` +
      `(${countPoints(boundaries.neighborhoods)} pts)\n`
  );

  const open = cases.filter((c) => c.s).length;
  process.stderr.write(
    `\nWrote ${cases.length} cases (${withPhoto} with photos, ${open} still open)\n` +
      `  districts: ${districts.length}   neighborhoods: ${neighborhoods.length}\n` +
      `  placed from coordinates: ${placedNeighborhood} neighborhood, ${placedDistrict} district\n` +
      `  district corrected against current boundaries: ${correctedDistrict}\n` +
      `  cases with no coordinates: ${cases.filter((c) => c.lat === null).length}\n`
  );
}

main().catch((err) => {
  console.error(`Build failed: ${err.message}`);
  process.exit(1);
});
