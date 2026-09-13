# FairTrees — SF Empty Tree Basin Tracker

Every empty street-tree basin reported to San Francisco 311, with the resident's
photograph beside what the City recorded as the outcome. Filterable by supervisor
district, neighborhood, status, outcome and date.

Runs on Cloudflare Workers. No server to sleep, nothing to warm up.

---

## Why this was rebuilt

The previous version was a Streamlit app. It resolved every photograph from the
City's Verint portal **on each page view** — four sequential HTTP round trips per
photo, about 2–3 seconds each. With 100 photos on screen that is roughly four
minutes of fetching, and Streamlit's free tier discards the cache whenever the app
sleeps, so most visitors paid that cost from scratch.

What changed:

| | Before (Streamlit) | Now (Cloudflare) |
|---|---|---|
| Cold page load | minutes, or a timeout | ~30 ms |
| Photo, first ever view | ~2.3 s, every visitor | ~2 s once, then ~5 ms for everyone |
| Idle behaviour | sleeps, then cold-starts | always on |
| If the 311 API is down | blank page | serves the bundled snapshot |
| Filters | supervisor district only | district, neighborhood, status, outcome, date, text search |
| Views | photo grid | photo grid, map, sortable table |
| Broken images | 68 dead links rendered as broken thumbnails | dead links detected and excluded |

## How it works

```
public/            static site (Workers Assets) — plain HTML/CSS/JS, no build step
  data/snapshot.json   full dataset, ~130 KB gzipped, offline fallback
  data/meta.json       district + neighborhood reference lists
  vendor/leaflet/      Leaflet, vendored rather than pulled from a CDN
worker/index.js    the only server-side code
src/transform.mjs  record normalization, shared by the Worker and the build script
scripts/build-data.mjs   regenerates the snapshot from the City's open data
test/              unit tests for the normalization rules
```

**The whole dataset is sent to the browser once** (~130 KB gzipped — smaller than
a single one of the photographs) and every filter is applied client-side. That is
why changing a filter is instant: there is no round trip.

### `GET /api/cases`

Returns every matching 311 record. A warm edge cache answers in milliseconds. On a
cold cache the bundled snapshot is returned **immediately** while the live pull runs
behind the response, because the City's API takes 5–15 seconds and no visitor
should wait for it. If that pull fails, the snapshot simply keeps serving.

### `GET /api/photo/<caseid>/<formref>`

The City does not serve 311 attachments as plain images. Getting one requires
loading a wrapper page for a CSRF token, trading it for a bearer token, requesting
the case's file list, then requesting a single file as base64 — four round trips.

This endpoint does that **once per photograph**, then caches the result at the edge
for 30 days (and in R2 when enabled). Only the very first viewer of a given photo
waits; everyone after gets it in about 5 ms.

## Local development

```bash
npm install
npm run dev        # http://localhost:8787
npm test           # normalization unit tests
npm run data       # refresh public/data/*.json from the City's open data
```

## Deploying

```bash
npx wrangler login
npm run deploy
```

To serve it from `fairtrees.org`, add the domain as a Custom Domain on the Worker
(Cloudflare dashboard → Workers & Pages → fairtrees → Settings → Domains & Routes).

### Optional: durable photo storage with R2

Photographs work without R2 — they are resolved on demand and cached at the edge.
R2 makes the archive permanent rather than cache-resident, and lets the scheduled
job fill it in ahead of visitors.

1. Enable R2 once in the Cloudflare dashboard (R2 → Overview). The free tier covers
   this project many times over — the full archive is well under 1 GB.
2. `npx wrangler r2 bucket create fairtrees-photos`
3. Uncomment the `[[r2_buckets]]` block in `wrangler.toml` and redeploy.

The Worker detects the binding at runtime; with it absent, everything still works.

## Data sources

- [311 Cases](https://data.sfgov.org/City-Infrastructure/311-Cases/vw6y-z8j6) — filtered
  server-side by SoQL to `service_details LIKE '%EMPTY_TREE_BASIN%'`, so only the few
  thousand matching rows are ever transferred, never the full table.
- [Supervisor districts](https://data.sf.gov/resource/cqbw-m5m3.geojson) — supervisor
  names are read from here, so they stay current without editing any code.
- [Analysis neighborhoods](https://data.sf.gov/resource/j2bu-swwd.geojson) — also used
  to place any report that arrives with coordinates but no neighborhood label.

## A note on the outcome labels

The "outcome" of a report is grouped from the free-text closure note a staff member
typed, so the labels are an interpretation, not an official 311 category. The rules
live in `src/transform.mjs` and are covered by tests.

One caveat matters enough to be stated on the site itself: closure notes became much
terser after about 2015. Nearly every report closed in the last 18 months carries only
*"Cancelled — Planned Maintenance"*. So **"no planting recorded" means the 311 record
shows no planting** — it is not by itself proof that no tree was planted.

## Legacy

`app.py` and `requirements.txt` are the previous Streamlit app. They are kept so the
old deployment keeps running until this one is live on `fairtrees.org`; delete them
once you have cut over.
