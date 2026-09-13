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

  // Some rows arrive without a district or neighbourhood label. When they carry
  // coordinates we can place them ourselves rather than dropping them into an
  // "unknown" bucket.
  let placedNeighborhood = 0;
  let placedDistrict = 0;
  for (const c of cases) {
    if (c.lat === null) continue;
    if (!c.n) {
      const found = locate(neighborhoodIndex, c.lng, c.lat);
      if (found) { c.n = found; placedNeighborhood++; }
    }
    if (!c.d) {
      const found = locate(districtIndex, c.lng, c.lat);
      if (found) { c.d = found; placedDistrict++; }
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

  await mkdir(resolve(ROOT, "public/data"), { recursive: true });
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

  const open = cases.filter((c) => c.s).length;
  process.stderr.write(
    `\nWrote ${cases.length} cases (${withPhoto} with photos, ${open} still open)\n` +
      `  districts: ${districts.length}   neighborhoods: ${neighborhoods.length}\n` +
      `  placed from coordinates: ${placedNeighborhood} neighborhood, ${placedDistrict} district\n` +
      `  cases with no coordinates: ${cases.filter((c) => c.lat === null).length}\n`
  );
}

main().catch((err) => {
  console.error(`Build failed: ${err.message}`);
  process.exit(1);
});
