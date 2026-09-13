/**
 * fairtrees.org — SF empty tree basin tracker
 *
 * Two jobs:
 *   GET /api/cases              live 311 data, edge-cached, snapshot fallback
 *   GET /api/photo/<case>/<ref> unwraps a photo from the SF 311 Verint portal
 *
 * Static assets are served by the [assets] binding. Nothing here keeps state in
 * memory, so there is no warm-up cost and nothing to go stale between requests.
 */
import { casesRequestUrl, dedupe, toCase } from "../src/transform.mjs";

const CASES_TTL = 1800;        // 30 min — 311 updates in daily batches
const UPSTREAM_TIMEOUT = 25000; // the city's API takes 5-15s; never on a visitor's path
const PHOTO_TTL = 2592000;     // 30 days — an attachment never changes
const VERINT_BASE = "https://sanfrancisco.form.us.empro.verintcloudservices.com";
const BROWSER_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

const json = (body, { status = 200, maxAge = 0, stale = 0 } = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": maxAge
        ? `public, max-age=${maxAge}, stale-while-revalidate=${stale || maxAge}`
        : "no-store",
    },
  });

/* ------------------------------- cases ------------------------------- */

async function fetchLiveCases() {
  const res = await fetch(casesRequestUrl({ limit: 5000 }), {
    headers: { "User-Agent": "fairtrees.org (+https://fairtrees.org)" },
    signal: AbortSignal.timeout(UPSTREAM_TIMEOUT),
  });
  if (!res.ok) throw new Error(`311 API returned ${res.status}`);
  const rows = await res.json();
  if (!Array.isArray(rows)) throw new Error("311 API returned an unexpected shape");
  const cases = dedupe(rows).map(toCase);
  return {
    generated: new Date().toISOString(),
    source: "live",
    count: cases.length,
    withPhoto: cases.filter((c) => c.p).length,
    cases,
  };
}

/** The snapshot shipped with the deployment. Always available, always instant. */
async function snapshotResponse(request, env, extra = {}) {
  const asset = await env.ASSETS.fetch(new URL("/data/snapshot.json", request.url));
  if (!asset.ok) return json({ error: "Case data is temporarily unavailable." }, { status: 503 });
  const payload = await asset.json();
  return json({ ...payload, source: "snapshot", ...extra }, { maxAge: 300, stale: CASES_TTL });
}

/** Pull fresh data and park it in the edge cache for subsequent visitors. */
async function refreshCases(env, cache, cacheKey) {
  try {
    const payload = await fetchLiveCases();
    await cache.put(cacheKey, json(payload, { maxAge: CASES_TTL, stale: CASES_TTL * 4 }));
  } catch {
    // The snapshot keeps serving; the next cold request will try again.
  }
}

/**
 * Nobody waits on the city's API. A warm edge cache answers in milliseconds; a
 * cold one is answered from the shipped snapshot immediately while the live pull
 * happens behind the response. Either way the page renders at once, and an
 * upstream outage is never a blank page — which is how the Streamlit version
 * failed.
 */
async function handleCases(request, env, ctx) {
  const cache = caches.default;
  const cacheKey = new Request(new URL("/api/cases", request.url).toString(), { method: "GET" });

  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  ctx.waitUntil(refreshCases(env, cache, cacheKey));
  return snapshotResponse(request, env, { refreshing: true });
}

/* ------------------------------- photos ------------------------------- */

// These two identifiers are interpolated into an upstream URL, so they are
// constrained to exactly the shape the 311 feed produces.
const CASE_ID = /^[0-9]{6,24}$/;
const FORM_REF = /^[A-Za-z0-9]{4,24}$/;

/** Base64 -> bytes via the runtime's own decoder; far cheaper than a JS loop. */
async function decodeBase64(b64) {
  const payload = b64.includes(",") ? b64.slice(b64.indexOf(",") + 1) : b64;
  try {
    const res = await fetch(`data:application/octet-stream;base64,${payload}`);
    if (res.ok) return new Uint8Array(await res.arrayBuffer());
  } catch {
    // Fall through to the manual path below.
  }
  const binary = atob(payload);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function pickAttachment(filenameList) {
  for (const raw of (filenameList || "").split(";")) {
    const name = raw.trim();
    if (!name) continue;
    const lower = name.toLowerCase();
    // The portal also attaches a generated location map per case; skip those.
    if (/(m\.jpg|_map\.jpe?g)$/.test(lower)) continue;
    if (/\.(jpe?g|png)$/.test(lower)) return name;
  }
  return null;
}

/**
 * The SF 311 portal does not expose attachments directly: you must load the
 * wrapper page for a CSRF token, trade it for a bearer token, ask for the case's
 * file list, then request one file as base64. Four round trips, ~3s.
 *
 * Doing this per page view is what made the old app unusable. Here it happens
 * once per photo, then the result is cached at the edge (and in R2 when bound),
 * so visitors never pay the cost.
 */
async function resolveVerintPhoto(caseid, formref) {
  const headers = { "User-Agent": BROWSER_UA, Referer: "https://mobile311.sfgov.org/" };
  const wrapper = `${VERINT_BASE}/form/auto/download_attachments?caseid=${caseid}&formref=${formref}`;

  const page = await fetch(wrapper, { headers, signal: AbortSignal.timeout(10000) });
  if (!page.ok) throw new Error(`wrapper page ${page.status}`);
  const html = await page.text();

  const csrf = html.match(/name="_csrf_token"\s+content="([^"]+)"/)?.[1];

  const apiHeaders = {
    "User-Agent": BROWSER_UA,
    Referer: wrapper,
    Origin: VERINT_BASE,
    "Content-Type": "application/json",
    ...(csrf ? { "X-CSRF-TOKEN": csrf } : {}),
  };

  // The handshake hands back a bearer token in a response header.
  const handshake = await fetch(
    `${VERINT_BASE}/api/citizen?archived=Y&preview=false&locale=en`,
    { headers: apiHeaders, signal: AbortSignal.timeout(10000) }
  );
  const auth = handshake.headers.get("Authorization");
  if (auth) apiHeaders.Authorization = auth;

  const body = (extra = {}) => ({
    data: { caseid: String(caseid), formref: String(formref), ...extra },
    name: "download_attachments",
    email: "",
    xref: "",
    xref1: "",
    xref2: "",
  });

  const listRes = await fetch(
    `${VERINT_BASE}/api/custom?action=get_attachments_details&actionedby=&loadform=true&access=citizen&locale=en`,
    { method: "POST", headers: apiHeaders, body: JSON.stringify(body()), signal: AbortSignal.timeout(10000) }
  );
  if (!listRes.ok) throw new Error(`attachment list ${listRes.status}`);

  const filename = pickAttachment((await listRes.json())?.data?.formdata_filenames);
  if (!filename) throw new Error("no image attachment on this case");

  const fileRes = await fetch(
    `${VERINT_BASE}/api/custom?action=download_attachment&actionedby=&loadform=true&access=citizen&locale=en`,
    {
      method: "POST",
      headers: apiHeaders,
      body: JSON.stringify(body({ filename })),
      signal: AbortSignal.timeout(20000),
    }
  );
  if (!fileRes.ok) throw new Error(`attachment download ${fileRes.status}`);

  const encoded = (await fileRes.json())?.data?.txt_file;
  if (!encoded) throw new Error("attachment response had no file body");

  const bytes = await decodeBase64(encoded);
  if (bytes.byteLength < 256) throw new Error("attachment was empty");

  return {
    bytes,
    contentType: filename.toLowerCase().endsWith(".png") ? "image/png" : "image/jpeg",
  };
}

const imageResponse = (body, contentType, extra = {}) =>
  new Response(body, {
    headers: {
      "Content-Type": contentType,
      "Cache-Control": `public, max-age=${PHOTO_TTL}, immutable`,
      ...extra,
    },
  });

/**
 * Three tiers, cheapest first: R2 (when enabled), then the edge cache, then the
 * upstream handshake. Only the very first viewer of a given photo ever waits.
 */
async function handlePhoto(request, env, ctx, caseid, formref) {
  if (!CASE_ID.test(caseid) || !FORM_REF.test(formref)) {
    return new Response("Bad photo reference", { status: 400 });
  }

  const key = `verint/${caseid}-${formref}`;
  const cache = caches.default;
  const cacheKey = new Request(
    new URL(`/api/photo/${caseid}/${formref}`, request.url).toString(),
    { method: "GET" }
  );

  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  if (env.PHOTOS) {
    const stored = await env.PHOTOS.get(key);
    if (stored) {
      const response = imageResponse(stored.body, stored.httpMetadata?.contentType || "image/jpeg", {
        "X-Photo-Source": "r2",
      });
      ctx.waitUntil(cache.put(cacheKey, response.clone()));
      return response;
    }
  }

  let photo;
  try {
    photo = await resolveVerintPhoto(caseid, formref);
  } catch (err) {
    // Short negative cache: retry later without hammering a flaky upstream.
    return new Response(`Photo unavailable: ${err.message}`, {
      status: 502,
      headers: { "Cache-Control": "public, max-age=600" },
    });
  }

  if (env.PHOTOS) {
    ctx.waitUntil(
      env.PHOTOS.put(key, photo.bytes, { httpMetadata: { contentType: photo.contentType } })
    );
  }

  const response = imageResponse(photo.bytes, photo.contentType, { "X-Photo-Source": "origin" });
  ctx.waitUntil(cache.put(cacheKey, response.clone()));
  return response;
}

/* ---------------------------- scheduled warm ---------------------------- */

/**
 * With R2 bound, a cron run pulls a batch of not-yet-stored photos so the
 * archive fills in on its own. Without R2 there is nothing durable to write to,
 * so the warm-up is skipped; the on-demand path still serves every photo.
 */
async function warmPhotos(env, limit = 40) {
  if (!env.PHOTOS) return { skipped: "no R2 bucket bound" };

  const { cases } = await fetchLiveCases();
  const pending = cases.filter((c) => c.p?.startsWith("v:")).map((c) => c.p.slice(2));

  let stored = 0;
  let failed = 0;
  for (const token of pending) {
    if (stored + failed >= limit) break;
    const [caseid, formref] = token.split(":");
    if (!CASE_ID.test(caseid || "") || !FORM_REF.test(formref || "")) continue;
    const key = `verint/${caseid}-${formref}`;
    if (await env.PHOTOS.head(key)) continue;
    try {
      const photo = await resolveVerintPhoto(caseid, formref);
      await env.PHOTOS.put(key, photo.bytes, { httpMetadata: { contentType: photo.contentType } });
      stored++;
    } catch {
      failed++;
    }
  }
  return { stored, failed };
}

/* -------------------------------- router -------------------------------- */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
    }

    if (url.pathname === "/api/cases") return handleCases(request, env, ctx);

    const photo = url.pathname.match(/^\/api\/photo\/([^/]+)\/([^/]+)$/);
    if (photo) return handlePhoto(request, env, ctx, photo[1], photo[2]);

    if (url.pathname === "/api/health") {
      return json({ ok: true, r2: Boolean(env.PHOTOS), time: new Date().toISOString() });
    }

    // An unmatched /api/ path is a client error, not a page — don't let it fall
    // through to the single-page-application asset handler.
    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
      return json({ error: "Unknown endpoint" }, { status: 404 });
    }

    return env.ASSETS.fetch(request);
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(warmPhotos(env));
  },
};
