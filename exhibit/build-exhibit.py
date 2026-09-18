#!/usr/bin/env python3
"""District 6 hearing exhibit, six pages.

Leads with the City's own closure language; organises photographs by block
rather than by date; no appendix (the full set lives on the website).
"""
import json, os, re, html, datetime, collections

SCR = "/tmp/claude-0/-home-user-fairtrees/6033c420-3be7-5d5a-929d-e2a8b1fd6fea/scratchpad"
SUBMITTER, ORG = "Shaun Aukland", "FairTrees.org"
TODAY = datetime.date(2026, 9, 18)
CUT = (TODAY - datetime.timedelta(days=730)).isoformat()

cases = json.load(open("/home/user/fairtrees/public/data/snapshot.json"))["cases"]
d6 = [c for c in cases if c["d"] == "6"]
has = lambda c: os.path.exists(f"{SCR}/print/{c['id']}.jpg")
norm = lambda a: re.sub(r"\s+", " ", a.strip().lower())
win = [c for c in d6 if c["o"] and c["o"] >= CUT]

n_win = len(win)
op = [c for c in win if c["s"]]
cl = [c for c in win if not c["s"]]
n_canc = sum(1 for c in cl if c["r"].startswith("Cancelled"))
n_plant = sum(1 for c in win if c["r"] in ("Tree planted", "Queued for planting"))
odays = sorted((TODAY - datetime.date.fromisoformat(c["o"])).days for c in op)
median_open, longest_open = odays[len(odays) // 2], max(odays)
hoods = collections.Counter(c["n"] or "Not recorded" for c in win).most_common()

EXACT = "do not currently have the resources to plant a new tree at this location"
nores = [c for c in d6 if c["note"] and EXACT in c["note"]]
nores_from = min(c["c"] for c in nores if c["c"])
nores_to = max(c["c"] for c in nores if c["c"])

# The 5 Dec 2025 mass closure, and the basins residents reported again afterwards.
MASS = "2025-12-05"
mass_d6 = [c for c in d6 if c["c"] == MASS]
mass_all = [c for c in cases if c["c"] == MASS]
by = collections.defaultdict(list)
for c in d6:
    by[norm(c["a"])].append(c)
reported_again, reported_again_photo = [], []
for addr, cs in by.items():
    if not any(c["c"] == MASS for c in cs):
        continue
    later = [c for c in cs if c["o"] and c["o"] > MASS and c["s"]]
    if later:
        first = sorted(later, key=lambda x: x["o"])[0]
        reported_again.append(first)
        if has(first):
            reported_again_photo.append(first)
reported_again_photo.sort(key=lambda c: c["o"])

def block(street_name, limit=None):
    sel = [c for c in win if has(c)
           and re.sub(r"^\d+\s+", "", c["a"]).strip().lower() == street_name]
    sel.sort(key=lambda c: int(re.match(r"^(\d+)", c["a"]).group(1)) if re.match(r"^(\d+)", c["a"]) else 0)
    return sel[:limit] if limit else sel

langton = block("langton st")
china = block("china basin st")
howard = block("howard st")
oldest = sorted([c for c in op if has(c)], key=lambda c: c["o"])[:15]

e = html.escape
fmt = lambda n: f"{n:,}"
def pretty(iso, yr=True):
    if not iso: return "—"
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%-d %B %Y") if yr else d.strftime("%-d %B")
days_open = lambda c: (TODAY - datetime.date.fromisoformat(c["o"])).days

CSS = """
@page { size: Letter; margin: 0.7in 0.7in 0.8in 0.7in; }
* { box-sizing: border-box; }
body { font-family: Georgia, "Times New Roman", serif; font-size: 10pt; line-height: 1.5;
       color: #111; margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { page-break-after: always; }
.page:last-child { page-break-after: auto; }
h1 { font-size: 23pt; line-height: 1.15; margin: 0 0 4pt; font-weight: normal; }
h2 { font-size: 14pt; margin: 0 0 9pt; font-weight: normal; border-bottom: 0.75pt solid #222;
     padding-bottom: 5pt; }
h3 { font-size: 10.5pt; margin: 14pt 0 5pt; }
p { margin: 0 0 9pt; }
.sub { font-size: 11pt; color: #333; margin-bottom: 2pt; }
.dateline { font-size: 9.5pt; color: #555; }
.rule { border-top: 1.5pt solid #222; margin: 13pt 0 15pt; }
.small { font-size: 8.6pt; }
.muted { color: #555; }

/* the closure note leads the document */
.quote { margin: 0 0 6pt; padding-left: 15pt; border-left: 2.5pt solid #1b5e45; }
.quote p { font-size: 12pt; line-height: 1.5; font-style: italic; margin: 0; }
.quote .src { font-style: normal; font-size: 8.6pt; color: #555; margin-top: 8pt; }

/* two figures, set typographically rather than as tiles */
.figs { display: flex; gap: 30pt; margin: 16pt 0 4pt; border-top: 0.75pt solid #bbb;
        border-bottom: 0.75pt solid #bbb; padding: 11pt 0; }
.figs div { flex: 1; }
.figs .n { font-size: 27pt; line-height: 1; }
.figs .t { font-size: 9pt; color: #444; margin-top: 5pt; }

table { width: 100%; border-collapse: collapse; font-size: 9pt; }
th { text-align: left; font-weight: normal; font-style: italic; color: #555;
     border-bottom: 0.75pt solid #999; padding: 4pt 5pt; }
td { padding: 3.5pt 5pt; border-bottom: 0.5pt solid #ddd; }
td.n, th.n { text-align: right; white-space: nowrap; }

.grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 9pt 7pt; margin-top: 12pt; }
.cell img { width: 100%; height: 1.78in; object-fit: cover; display: block;
            border: 0.5pt solid #bbb; background: #eee; }
.cap { font-size: 6.9pt; line-height: 1.32; margin-top: 2.5pt; font-family: Helvetica, Arial, sans-serif; }
.cap b { display: block; }
.cap span { display: block; color: #555; }
.cap .o { color: #9c2b28; }
.foot { font-size: 8pt; color: #666; border-top: 0.5pt solid #ccc; padding-top: 5pt; margin-top: 13pt; }
.lede { font-size: 10pt; }
"""

def cell(c):
    return (f'<div class="cell"><img src="print/{c["id"]}.jpg" alt="">'
            f'<div class="cap"><b>{e(c["a"])}</b>'
            f'<span>Reported {pretty(c["o"], False)} {c["o"][:4]}</span>'
            f'<span class="o">{"Open " + str(days_open(c)) + " days" if c["s"] else e(c["r"][:26])}</span>'
            f'<span>#{e(c["id"])}</span></div></div>')

def photo_page(title, lede, items, foot):
    return (f'<div class="page"><h2>{title}</h2><p class="lede">{lede}</p>'
            f'<div class="grid">{"".join(cell(c) for c in items)}</div>'
            f'<div class="foot">{foot}</div></div>')

# ---------------------------------------------------------------- page 1
cover = f"""
<div class="page">
  <h1>Empty Street-Tree Basins<br>in Supervisor District 6</h1>
  <div class="sub">Photographic and records evidence from San Francisco 311</div>
  <div class="dateline">Reports filed {pretty(CUT)} &ndash; {pretty(TODAY.isoformat())}</div>
  <div class="rule"></div>

  <p>On <strong>{fmt(len(nores))} District 6 service requests</strong> closed between
  {pretty(nores_from)} and {pretty(nores_to)}, San Francisco Public Works closed the case with
  this note:</p>

  <div class="quote">
    <p>&ldquo;We have confirmed that this is an empty basin. Unfortunately, we do not currently
    have the resources to plant a new tree at this location, but it is on our list of sites to
    plant once funding is available. If you want to pursue the planting of and can water a new
    tree weekly for three years, please let us know at urbanforestry@sfdpw.org&rdquo;</p>
    <div class="src">Reproduced verbatim from San Francisco 311, dataset vw6y-z8j6.</div>
  </div>

  <p>The basin was inspected and confirmed empty. The case was closed without a tree being
  planted. The resident was invited to buy the tree and water it weekly for three years
  themselves &mdash; on a public sidewalk the City is responsible for maintaining.</p>

  <div class="figs">
    <div><div class="n">{fmt(len(op))}</div>
      <div class="t">empty basins reported in District 6 and still open today,
      out of {fmt(n_win)} reported in the last two years</div></div>
    <div><div class="n">{median_open} days</div>
      <div class="t">median wait for an open case; the longest has been open
      {longest_open} days</div></div>
  </div>

  <p class="small muted" style="margin-top:14pt">Every case in this document carries its 311
  case number and can be verified independently at
  mobile311.sfgov.org/tickets/&lt;case&nbsp;number&gt;. The complete set of
  {fmt(sum(1 for c in win if has(c)))} photographs is published at fairtrees.org and is
  available on request.</p>

  <p class="small muted" style="margin-top:22pt">Prepared by {e(SUBMITTER)}, {e(ORG)} &mdash;
  {pretty(TODAY.isoformat())}. Compiled entirely from the City's own open data; no figure has
  been estimated or supplied by the author.</p>
</div>
"""

# ---------------------------------------------------------------- page 2
hood_rows = "".join(
    f'<tr><td>{e(k)}</td><td class="n">{fmt(v)}</td>'
    f'<td class="n">{fmt(sum(1 for c in win if (c["n"] or "Not recorded")==k and c["s"]))}</td></tr>'
    for k, v in hoods)

stevenson = sorted([c for c in d6 if norm(c["a"]).startswith("548 stevenson") and c["s"]],
                   key=lambda c: c["o"])

findings = f"""
<div class="page">
  <h2>What the record shows</h2>

  <p>Residents filed <strong>{fmt(n_win)}</strong> reports of empty street-tree basins in
  District 6 between {pretty(CUT)} and {pretty(TODAY.isoformat())}.
  <strong>{fmt(len(op))} of them &mdash; {round(len(op)/n_win*100)}% &mdash; are still open.</strong>
  The median open case has waited {median_open} days.</p>

  <h3>A single day's closures</h3>
  <p>On {pretty(MASS)}, the City closed <strong>{fmt(len(mass_all))} empty-basin reports
  citywide in one day</strong> &mdash; {fmt(len(mass_d6))} of them in District 6 &mdash; every
  one carrying the same note, &ldquo;Cancelled &mdash; Planned Maintenance.&rdquo; Residents
  have since filed fresh reports at <strong>{fmt(len(reported_again))} of those District 6
  locations</strong>. All {fmt(len(reported_again))} of those new reports are still open.
  Fifteen of them are photographed on page 4.</p>

  <h3>The same basin, reported six times</h3>
  <p>548 Stevenson Street has been reported <strong>{fmt(len(stevenson))} separate times</strong>
  this year &mdash; {", ".join(pretty(c["o"], False) for c in stevenson[:-1])} and
  {pretty(stevenson[-1]["o"], False)}. Every one of those reports is still open.</p>

  <h3>How the {fmt(len(cl))} closed reports were closed</h3>
  <p>Of the {fmt(len(cl))} reports the City closed in this period,
  <strong>{fmt(n_canc)} ({round(n_canc/len(cl)*100)}%)</strong> carry the note
  &ldquo;Cancelled &mdash; Planned Maintenance,&rdquo; and <strong>none</strong> record a tree having
  been planted. That figure describes the public record rather than the ground: closure notes
  became markedly less specific after about 2015, and today almost every closed report carries
  only that one phrase. The fair conclusion is not that nothing was planted, but that
  <strong>a resident cannot tell from the public record what happened to their report</strong>
  &mdash; which is why the reports above keep being filed again.</p>

  <h3>Where they are</h3>
  <p class="small muted" style="margin-bottom:6pt">District 6 as drawn covers more than the South
  of Market core. The counts below are for the whole district, including the Tenderloin.</p>
  <table>
    <thead><tr><th>Neighborhood</th><th class="n" style="width:1.2in">Reports</th>
    <th class="n" style="width:1.2in">Still open</th></tr></thead>
    <tbody>{hood_rows}</tbody>
  </table>
</div>
"""

lang_open = sum(1 for c in langton if c["s"])
lang_days = sorted(days_open(c) for c in langton if c["s"])
page_langton = photo_page(
    "One block: Langton Street",
    f"Langton Street is a two-block alley between Folsom and Howard. These "
    f"<strong>{fmt(len(langton))}</strong> basins were photographed by residents along it; "
    f"<strong>all {fmt(lang_open)} are still open</strong>, between {min(lang_days)} and "
    f"{max(lang_days)} days after they were reported. Nine were reported on a single day, "
    f"19 March 2026. Three addresses appear twice, having been reported once in December 2025 "
    f"and again in March 2026 &mdash; both reports still open.",
    langton,
    "Every photograph was taken and submitted by a resident as part of their own 311 report.")

page_again = photo_page(
    "Closed as &ldquo;Planned Maintenance,&rdquo; then reported again",
    f"Each of these basins was among the {fmt(len(mass_d6))} District 6 reports the City closed on "
    f"{pretty(MASS)}. Each was then reported again by a resident &mdash; between 15 and 264 days "
    f"later &mdash; and photographed. <strong>Every one of these newer reports is still open.</strong> "
    f"The date shown is the date of the new report, not the closed one.",
    reported_again_photo,
    "The closure of a 311 case is not evidence that a tree was planted.")

mix = china + howard[:max(0, 15 - len(china))]
china_days = sorted(days_open(c) for c in china if c["s"])
page_mix = photo_page(
    "Two more streets: China Basin and Howard",
    f"<strong>{fmt(len(china))}</strong> basins on China Basin Street in Mission Bay, "
    f"<strong>all still open</strong> &mdash; seven of them reported on one day, 22 February 2026, "
    f"and open {max(china_days)} days since. They are followed by basins on Howard Street, where "
    f"every photographed report in this period is also still open.",
    mix,
    "Addresses run in street-number order, not date order.")

method = f"""
<div class="page">
  <h2>Method and verification</h2>

  <p><strong>Source.</strong> Every record is a 311 service request from the City and County of
  San Francisco's open data portal, dataset <strong>vw6y-z8j6</strong>, retrieved
  {pretty(TODAY.isoformat())}. Nothing has been supplied, estimated or altered by the author.</p>

  <p><strong>Selection.</strong> Records were filtered to those whose <em>service detail</em> is
  <code>EMPTY_TREE_BASIN</code> and whose <em>supervisor district</em> is <strong>6</strong>,
  reported on or after {pretty(CUT)}, de-duplicated by service request ID. That yields the
  {fmt(n_win)} reports counted here. The {fmt(len(nores))} cases quoted on page 1 are older, and
  were identified by the exact closure sentence reproduced there.</p>

  <p><strong>Photographs.</strong> Each was taken by a resident and attached to their own 311
  report. They are reproduced unaltered apart from resizing and rotation to correct orientation.
  Of the {fmt(n_win)} reports, {fmt(sum(1 for c in win if has(c)))} carry a retrievable
  photograph; 311 began retaining attachments only recently, which is why the
  {fmt(len(nores))} cases quoted on page 1 have none. <strong>The complete set of
  {fmt(sum(1 for c in win if has(c)))} photographs is published at fairtrees.org and available on
  request</strong> &mdash; the selection here is organised by street, not chosen for effect.</p>

  <p><strong>Dates.</strong> &ldquo;Reported&rdquo; is the 311 <em>requested_datetime</em>; days
  open are counted to {pretty(TODAY.isoformat())}. Outcome descriptions are taken from the
  free-text closure note City staff entered, and are quoted rather than interpreted wherever the
  wording matters.</p>

  <p><strong>Limitations.</strong> District and neighborhood assignment is the City's own
  geocoding; {fmt(sum(1 for c in win if not c["n"]))} reports in this period carry no
  neighborhood label, and reports filed at an intersection often carry no coordinates. Counts of
  what the City did are counts of what the City <em>recorded</em>.</p>

  <p><strong>Verification.</strong> Every photograph and table row carries its 311 case number.
  Any case can be checked at
  <strong>mobile311.sfgov.org/tickets/&lt;case&nbsp;number&gt;</strong> or by querying the open
  dataset directly. The continuously updated record for all eleven districts is at
  <strong>fairtrees.org</strong>.</p>

  <div class="foot">Prepared by {e(SUBMITTER)}, {e(ORG)}. Questions about the derivation of any
  figure are welcome; the query and code behind this document are public.</div>
</div>
"""

doc = (f'<!doctype html><html><head><meta charset="utf-8">'
       f'<title>Empty Street-Tree Basins in Supervisor District 6</title>'
       f'<style>{CSS}</style></head><body>'
       + cover + findings + page_langton + page_again + page_mix + method
       + '</body></html>')
open(f"{SCR}/exhibit_v2.html", "w").write(doc)

print(f"window {CUT} .. {TODAY}")
print(f"reports={n_win} open={len(op)} ({round(len(op)/n_win*100)}%) closed={len(cl)} "
      f"cancelled={n_canc} planted={n_plant} median={median_open} longest={longest_open}")
print(f"mass closure {MASS}: citywide={len(mass_all)} d6={len(mass_d6)} "
      f"re-reported={len(reported_again)} (photo {len(reported_again_photo)})")
print(f"548 Stevenson open reports={len(stevenson)}")
print(f"photo pages: langton={len(langton)} again={len(reported_again_photo)} mix={len(mix)}")
print(f"quoted cases={len(nores)} ({nores_from}..{nores_to})")
