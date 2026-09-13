/**
 * Shared normalization for SF 311 empty-tree-basin records.
 *
 * Imported by both the offline build script and the Worker so the snapshot and
 * the live API can never disagree about how a case is shaped.
 */

export const CASES_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json";

// Matches the upstream 311 taxonomy for a tree basin with no tree in it.
export const SUBJECT_PATTERN = "%EMPTY_TREE_BASIN%";

export const FIELDS = [
  "service_request_id", "requested_datetime", "closed_date", "status_description",
  "status_notes", "service_details", "service_subtype", "address", "street",
  "media_url", "supervisor_district", "analysis_neighborhood", "lat", "long",
];

/** SoQL that filters server-side so only matching rows are ever transferred. */
export function casesQuery({ limit = 5000, offset = 0 } = {}) {
  return (
    `SELECT ${FIELDS.join(", ")}` +
    ` WHERE upper(service_details) LIKE '${SUBJECT_PATTERN}'` +
    ` ORDER BY requested_datetime DESC LIMIT ${limit} OFFSET ${offset}`
  );
}

export function casesRequestUrl(options) {
  return `${CASES_URL}?${new URLSearchParams({ $query: casesQuery(options) })}`;
}

/**
 * Outcome labels that mean a tree actually went into the ground, or is formally
 * scheduled to. Everything else is a closure without a tree.
 */
export const PLANTED_OUTCOMES = new Set(["Tree planted", "Queued for planting"]);

/** An outcome meaning the case is acknowledged but unresolved. */
export const OPEN_OUTCOME = "Accepted \u2014 still open";

/**
 * The 311 status_notes field is free text typed by whoever closed the case.
 * Collapse it into a small, stable set of outcomes.
 *
 * The ordering is deliberate: the most specific and most consequential phrases
 * are tested first, because many notes contain several keywords at once (a note
 * reading "in queue to plant" must not be counted as a completed planting, and a
 * note recording both a planting and a letter counts as the planting).
 *
 * These labels are an interpretation of the City's free text, not an official
 * 311 category — the Method section on the site says so plainly.
 */
export function closureReason(note, statusDescription) {
  const raw = (note ?? "").toString().trim();
  const isOpen = (statusDescription || "").toLowerCase() === "open";

  if (!raw || ["nan", "null", "none"].includes(raw.toLowerCase())) {
    return isOpen ? OPEN_OUTCOME : "No reason recorded";
  }

  const t = raw.toLowerCase();

  // The City's standard acknowledgement on a case it has not yet worked.
  if (isOpen && (t === "accepted" || t === "open")) return OPEN_OUTCOME;

  // The City confirms the basin is empty and states it cannot plant. This is the
  // single most consequential outcome in the dataset, so it is matched first.
  if (t.includes("do not currently have the resources") || t.includes("limited planting resources")) {
    return "Confirmed empty \u2014 no resources to plant";
  }
  if (t.includes("queue to plant")) return "Queued for planting";
  if (/action:\s*plant|trees? planted|tree was planted/.test(t)) return "Tree planted";
  if (t.includes("backfill")) return "Basin backfilled";
  if (t.includes("serviced in the next few years")) return "Deferred several years";
  if (t.includes("letter")) return "Letter sent to property owner";
  if (t.includes("duplicate")) return "Duplicate report";
  if (t.includes("insufficient info")) return "Insufficient information";
  if (t.includes("administrative")) return "Administrative closure";
  if (t.includes("transferred")) return "Transferred to Urban Forestry";
  if (t.includes("not a dpw") || t.includes("wrong department")) return "Wrong department";
  if (t.includes("not found")) return "Basin not found";

  // Far and away the most common closure: routed into planned maintenance.
  if (t.startsWith("cancelled") || t.includes("action reason: planned maintenance")) {
    return t.includes("planned maintenance") ? "Cancelled \u2014 planned maintenance" : "Cancelled";
  }

  // The portal shows this when the explanation is only in a staff-only tab.
  if (t.includes("see notes tab")) return "No public explanation";
  if (t.includes("comment noted")) return "Comment noted only";

  // "Case Resolved" / "Case Completed - resolved:" with nothing after it.
  if (t.startsWith("case resolved") || t.startsWith("case completed") || t.includes("resolved")) {
    return "Marked resolved \u2014 no detail";
  }

  return isOpen ? OPEN_OUTCOME : "Other";
}

/**
 * The 311 feed points at several kinds of attachment. Only two actually yield a
 * usable image today: the Verint portal (which needs a server-side handshake to
 * unwrap) and a few direct image URLs. Links to social-media posts and the
 * retired mobile311 photo pages are dead or serve HTML, so they are not treated
 * as photos rather than rendered as broken thumbnails.
 */
const DIRECT_IMAGE_HOSTS = new Set(["spot-sf-res.cloudinary.com", "pbs.twimg.com"]);

export function photoToken(media) {
  if (!media) return null;
  const url = typeof media === "object" ? media.url : media;
  if (typeof url !== "string" || !url.startsWith("http")) return null;

  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }

  if (parsed.hostname.includes("verintcloudservices")) {
    // Store only the two identifiers the handshake needs; the Worker rebuilds
    // the wrapper URL. Saves most of the snapshot's photo bytes.
    const caseid = parsed.searchParams.get("caseid");
    const formref = parsed.searchParams.get("formref");
    if (!caseid || !formref) return null;
    return `v:${caseid}:${formref}`;
  }

  if (DIRECT_IMAGE_HOSTS.has(parsed.hostname) || /\.(jpg|jpeg|png|webp|gif)$/i.test(parsed.pathname)) {
    return url;
  }
  return null;
}

export function titleCase(value) {
  return (value || "")
    .toString()
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b[a-z]/g, (c) => c.toUpperCase())
    // SF street names the simple rule gets wrong.
    .replace(/\bMc([a-z])/g, (_, c) => `Mc${c.toUpperCase()}`)
    .replace(/\bO'([a-z])/g, (_, c) => `O'${c.toUpperCase()}`);
}

const CITY_SUFFIX = /,?\s*(san francisco|sf)\b.*$/i;

/**
 * Addresses arrive in three shapes, and roughly a sixth of reports are filed at
 * an intersection rather than a street number:
 *
 *   "214 STEINER ST, SAN FRANCISCO, CA, 94117"
 *   "Intersection of HYDE ST and MARKET ST"
 *   "INTERSECTION VAN NESS AVE, CLAY ST, SAN FRANCISCO, CA 94109, US"
 *
 * All three collapse to a short, readable label.
 */
export function shortAddress(address, street) {
  const raw = (address || "").toString().trim();

  const joined = raw.match(/^intersection\s+of\s+(.+?)\s+and\s+(.+?)(?:,|$)/i);
  if (joined) return `${titleCase(joined[1])} & ${titleCase(joined[2])}`;

  if (/^intersection\b/i.test(raw)) {
    const parts = raw
      .replace(/^intersection\s*(of\s*)?/i, "")
      .replace(CITY_SUFFIX, "")
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    if (parts.length >= 2) return `${titleCase(parts[0])} & ${titleCase(parts[1])}`;
    if (parts.length === 1) return titleCase(parts[0]);
  }

  const first = raw.split(",")[0].trim();
  return titleCase(first || street || "Location not recorded");
}

/**
 * Turn a raw Socrata row into the compact record the client consumes.
 * Short keys keep the full-dataset payload small enough to ship at once.
 */
export function toCase(row) {
  const lat = row.lat ? Number(row.lat) : null;
  const lng = row.long ? Number(row.long) : null;
  const hasPoint =
    Number.isFinite(lat) && Number.isFinite(lng) && lat !== 0 && lng !== 0;

  const districtRaw = row.supervisor_district ? Number(row.supervisor_district) : NaN;
  const district = Number.isFinite(districtRaw) ? String(districtRaw) : null;

  const opened = row.requested_datetime || null;
  const closed = row.closed_date || null;

  return {
    id: row.service_request_id,
    // Time of day is not meaningful for this data; keep plain ISO day strings.
    o: opened ? opened.slice(0, 10) : null,
    c: closed ? closed.slice(0, 10) : null,
    d: district,
    n: row.analysis_neighborhood || null,
    a: shortAddress(row.address, row.street),
    t: titleCase(row.service_subtype || row.service_details),
    r: closureReason(row.status_notes, row.status_description),
    s: closed ? 0 : 1,
    p: photoToken(row.media_url),
    lat: hasPoint ? Number(lat.toFixed(6)) : null,
    lng: hasPoint ? Number(lng.toFixed(6)) : null,
    note: (row.status_notes || "").toString().slice(0, 240) || null,
  };
}

/** Dedupe on service_request_id, preserving feed order (newest first). */
export function dedupe(rows) {
  const seen = new Set();
  const out = [];
  for (const row of rows) {
    const id = row.service_request_id;
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(row);
  }
  return out;
}
