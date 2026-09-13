import { test } from "node:test";
import assert from "node:assert/strict";
import {
  closureReason, photoToken, shortAddress, titleCase, toCase, dedupe, casesQuery,
  PLANTED_OUTCOMES, OPEN_OUTCOME,
} from "../src/transform.mjs";

test("shortAddress keeps street addresses short", () => {
  assert.equal(shortAddress("214 STEINER ST, SAN FRANCISCO, CA, 94117"), "214 Steiner St");
  assert.equal(shortAddress("3505 20TH ST, SAN FRANCISCO, CA, 94110"), "3505 20th St");
  assert.equal(shortAddress("701 GOLDEN GATE AVE, SAN FRANCISCO, CA, 94102"), "701 Golden Gate Ave");
});

test("shortAddress renders both intersection formats", () => {
  assert.equal(shortAddress("Intersection of HYDE ST and MARKET ST"), "Hyde St & Market St");
  assert.equal(shortAddress("Intersection of 6TH ST and NATOMA ST"), "6th St & Natoma St");
  assert.equal(
    shortAddress("INTERSECTION VAN NESS AVE, CLAY ST, SAN FRANCISCO, CA 94109, US"),
    "Van Ness Ave & Clay St"
  );
});

test("shortAddress falls back to the street field, then to a label", () => {
  assert.equal(shortAddress("", "FOLSOM ST"), "Folsom St");
  assert.equal(shortAddress(null, null), "Location Not Recorded");
});

test("titleCase handles SF street-name quirks", () => {
  assert.equal(titleCase("MCALLISTER ST"), "McAllister St");
  assert.equal(titleCase("O'FARRELL ST"), "O'Farrell St");
  assert.equal(titleCase("EMPTY_TREE_BASIN"), "Empty Tree Basin");
  // Ordinals must not become "6Th".
  assert.equal(titleCase("6TH ST"), "6th St");
});

test("closureReason groups the free-text notes", () => {
  assert.equal(closureReason("Case is a Duplicate of another"), "Duplicate report");
  assert.equal(closureReason("Case Transferred"), "Transferred to Urban Forestry");
  assert.equal(closureReason("Insufficient info to locate"), "Insufficient information");
  assert.equal(closureReason("Case Resolved"), "Marked resolved \u2014 no detail");
  assert.equal(closureReason("Case Resolved - backfill"), "Basin backfilled");
  assert.equal(closureReason("Comment Noted"), "Comment noted only");
  assert.equal(closureReason("See Notes tab for more details"), "No public explanation");
});

test("closureReason surfaces the City's own stated reason for not planting", () => {
  assert.equal(
    closureReason("Case Resolved - We have confirmed that this is an empty basin. Unfortunately, we do not currently have the resources to plant a new tree at this time"),
    "Confirmed empty \u2014 no resources to plant"
  );
  assert.equal(
    closureReason("Case Resolved - the city currently has very limited planting resources"),
    "Confirmed empty \u2014 no resources to plant"
  );
});

test("closureReason separates the most common closure from a plain cancellation", () => {
  assert.equal(closureReason("Cancelled - Planned Maintenance"), "Cancelled \u2014 planned maintenance");
  assert.equal(
    closureReason("Cancelled - Should be routed to 311 Call Center  (No change)  Action Reason: Planned Maintenance"),
    "Cancelled \u2014 planned maintenance"
  );
  assert.equal(closureReason("Cancelled"), "Cancelled");
});

test("closureReason does not count a queued planting as a completed one", () => {
  assert.equal(closureReason("Case Resolved - in queue to plant"), "Queued for planting");
  assert.equal(
    closureReason('Case Completed - resolved: Request closed by SES . Notes = " BUF Action:Plant. date completed - 1/27/2015. ".'),
    "Tree planted"
  );
  // A note recording both a planting and correspondence counts as the planting.
  assert.equal(closureReason("BUF Action:Plant. Letter also sent."), "Tree planted");
  assert.equal(closureReason("Case Completed - resolved: Request Letter Sent."), "Letter sent to property owner");
});

test("closureReason distinguishes an open case from a closed one with no note", () => {
  assert.equal(closureReason("", "Open"), OPEN_OUTCOME);
  assert.equal(closureReason("accepted", "Open"), OPEN_OUTCOME);
  assert.equal(closureReason(null, "Closed"), "No reason recorded");
  assert.equal(closureReason("nan", "Closed"), "No reason recorded");
});

test("PLANTED_OUTCOMES covers exactly the outcomes that put a tree in the ground", () => {
  assert.ok(PLANTED_OUTCOMES.has("Tree planted"));
  assert.ok(PLANTED_OUTCOMES.has("Queued for planting"));
  assert.ok(!PLANTED_OUTCOMES.has("Cancelled \u2014 planned maintenance"));
  assert.ok(!PLANTED_OUTCOMES.has("Confirmed empty \u2014 no resources to plant"));
});

test("photoToken compacts Verint links and rejects dead ones", () => {
  assert.equal(
    photoToken({ url: "https://sanfrancisco.form.us.empro.verintcloudservices.com/form/auto/download_attachments?caseid=202000053188&formref=2658Y732K" }),
    "v:202000053188:2658Y732K"
  );
  // Social-media and retired photo pages serve HTML, not an image.
  assert.equal(photoToken({ url: "https://twitter.com/someone/status/123" }), null);
  assert.equal(photoToken({ url: "http://mobile311.sfgov.org/reports/13437452/photos" }), null);
  assert.equal(photoToken(null), null);
  assert.equal(photoToken({ url: "not-a-url" }), null);
  // A direct image URL is kept as-is.
  assert.equal(
    photoToken({ url: "https://spot-sf-res.cloudinary.com/image/upload/v1/x.jpg" }),
    "https://spot-sf-res.cloudinary.com/image/upload/v1/x.jpg"
  );
});

test("toCase normalizes a row into the compact shape", () => {
  const row = {
    service_request_id: "123456789",
    requested_datetime: "2026-01-15T09:30:00.000",
    closed_date: "2026-02-01T11:00:00.000",
    status_description: "Closed",
    status_notes: "Tree planted",
    service_subtype: "Empty_Tree_Basin",
    address: "214 STEINER ST, SAN FRANCISCO, CA, 94117",
    supervisor_district: "5.00000",
    analysis_neighborhood: "Western Addition",
    lat: "37.7751234567",
    long: "-122.4321987654",
    media_url: null,
  };
  const c = toCase(row);
  assert.equal(c.id, "123456789");
  assert.equal(c.o, "2026-01-15");
  assert.equal(c.c, "2026-02-01");
  assert.equal(c.d, "5", "district arrives as a float string and must normalize");
  assert.equal(c.n, "Western Addition");
  assert.equal(c.a, "214 Steiner St");
  assert.equal(c.r, "Tree planted");
  assert.equal(c.s, 0, "a closed case is not open");
  assert.equal(c.lat, 37.775123);
  assert.equal(c.lng, -122.432199);
});

test("toCase marks a case with no closed date as open", () => {
  const c = toCase({ service_request_id: "1", requested_datetime: "2026-01-01T00:00:00.000", status_description: "Open" });
  assert.equal(c.s, 1);
  assert.equal(c.c, null);
});

test("toCase drops null-island coordinates", () => {
  const c = toCase({ service_request_id: "1", lat: "0", long: "0" });
  assert.equal(c.lat, null);
  assert.equal(c.lng, null);
});

test("dedupe keeps the first occurrence of each request id", () => {
  const rows = dedupe([
    { service_request_id: "a", n: 1 }, { service_request_id: "b" }, { service_request_id: "a", n: 2 },
  ]);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].n, 1);
});

test("casesQuery filters server-side so the full table is never transferred", () => {
  const q = casesQuery({ limit: 10, offset: 20 });
  assert.match(q, /WHERE upper\(service_details\) LIKE '%EMPTY_TREE_BASIN%'/);
  assert.match(q, /LIMIT 10 OFFSET 20/);
});
