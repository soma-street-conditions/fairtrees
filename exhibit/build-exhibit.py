#!/usr/bin/env python3
"""District 6 hearing exhibit.

Leads with the City's own closure language; organises photographs by block
rather than by date; no appendix (the full set lives on the website).
"""
import json, os, re, html, datetime, collections, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapgen import district_map

SCR = "/tmp/claude-0/-home-user-fairtrees/6033c420-3be7-5d5a-929d-e2a8b1fd6fea/scratchpad"
SUBMITTER, ORG = "Shaun Aukland", "FairTrees.org"
TODAY = datetime.date(2026, 9, 18)
CUT = (TODAY - datetime.timedelta(days=730)).isoformat()

cases = json.load(open("/home/user/fairtrees/public/data/snapshot.json"))["cases"]
d6 = [c for c in cases if c["d"] == "6"]
# 1532 Harrison St was photographed as an empty basin and its 311 cases are
# still open, but trees have since been planted there. It is withheld from every
# photograph page: an open case is not proof of an empty basin, and one frame a
# reader can disprove on foot would be used against the whole document.
WITHHELD = {"1532 harrison st"}

def has(c):
    if re.sub(r"\s+", " ", c["a"].strip().lower()) in WITHHELD:
        return False
    return os.path.exists(f"{SCR}/print/{c['id']}.jpg")
norm = lambda a: re.sub(r"\s+", " ", a.strip().lower())
citywide = [c for c in cases if c["o"] and c["o"] >= CUT and c["d"]]
d6 = [c for c in cases if c["d"] == "6"]
win = [c for c in d6 if c["o"] and c["o"] >= CUT]

n_win = len(win)
op = [c for c in win if c["s"]]
cl = [c for c in win if not c["s"]]
n_canc = sum(1 for c in cl if c["r"].startswith("Cancelled"))
n_plant = sum(1 for c in win if c["r"] in ("Tree planted", "Queued for planting"))
odays = sorted((TODAY - datetime.date.fromisoformat(c["o"])).days for c in op)
median_open, longest_open = odays[len(odays) // 2], max(odays)
hoods = collections.Counter(c["n"] or "Not recorded" for c in win).most_common()
MAIN_STREETS = ["6th", "7th", "8th", "9th", "10th", "11th", "12th",
                "Mission", "Howard", "Market", "Folsom", "Harrison"]
_main_re = re.compile(r"\b(" + "|".join(MAIN_STREETS) + r")\s+(st|ave|blvd)\b", re.I)
on_main = [c for c in win if _main_re.search(c["a"])]
on_main_open = [c for c in on_main if c["s"]]

MAP_SVG = district_map([c for c in win if c["s"]],
                       "/home/user/fairtrees/public/data/boundaries.json", labels=3)

EXACT = "do not currently have the resources to plant a new tree at this location"
# Split the quoted set by whether the district could be confirmed from
# coordinates. Reports the feed never geocoded keep the 311 field, which is the
# stale pre-2022 district, so they are reported separately rather than claimed.
quoted = [c for c in d6 if c["note"] and EXACT in c["note"]]
nores = [c for c in quoted if c["lat"] is not None]
nores_ungeocoded = [c for c in quoted if c["lat"] is None]
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

def block(*street_names, limit=None, open_first=False):
    names = set(street_names)
    sel = [c for c in win if has(c)
           and re.sub(r"^\d+\s+", "", c["a"]).strip().lower() in names]
    if open_first:
        # Twelve to a page, so spend them on the basins still waiting.
        sel = [c for c in sel if c["s"]] + [c for c in sel if not c["s"]]
        sel = sel[:limit or PER_PAGE]
    num = lambda c: int(re.match(r"^(\d+)", c["a"]).group(1)) if re.match(r"^(\d+)", c["a"]) else 0
    sel.sort(key=lambda c: (re.sub(r"^\d+\s+", "", c["a"]).strip().lower(), num(c)))
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
/* One sans family at two weights. Source Sans 3 is a text face rather than a
   display one: at 10.5pt in a dense evidence document it holds up where a
   geometric face (Montserrat, the site's own) goes wide and loose. The brand
   link is carried by the paper colour and the green instead.
   The file is the variable roman, so every weight comes from one download. */
@font-face {
  font-family: "Source Sans 3";
  src: url("sourcesans3.woff2") format("woff2");
  font-weight: 100 900; font-style: normal;
}

/* One accent colour, used twice: section headings and the cover figures. The
   coral appears exactly once in the document, on District 6's bar. */
:root {
  --paper:    #FAFAFA;
  --ink:      #1A1A1A;
  --green:    #35803A;
  --grey:     #767676;
  --hair:     #E4E4E4;
  --coral:    #C9502E;
}

@page { size: Letter; margin: 0.9in 0.9in 0.85in 0.9in; background: #FAFAFA; }
* { box-sizing: border-box; }
body { font-family: "Source Sans 3", Helvetica, Arial, sans-serif; font-size: 10.5pt;
       line-height: 1.52; color: var(--ink); background: var(--paper); margin: 0;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { page-break-after: always; background: var(--paper); }
.page:last-child { page-break-after: auto; }

h1 { font-size: 34pt; line-height: 1.12; margin: 0 0 10pt; font-weight: 700; }
/* No rule under a heading: weight and the space above do that work. */
h2 { font-size: 18pt; margin: 0 0 11pt; font-weight: 700; color: var(--green); }
h3 { font-size: 11pt; margin: 15pt 0 5pt; font-weight: 700; }
p { margin: 0 0 10pt; }
.sub { font-size: 13pt; color: var(--grey); margin-bottom: 3pt; font-weight: 400; }
.dateline { font-size: 10pt; color: var(--grey); }
.rule { border-top: 1pt solid var(--hair); margin: 12pt 0 12pt; }
.small { font-size: 9pt; }
.muted { color: var(--grey); }

/* the closure note leads the document */
.quote { margin: 0 0 6pt; padding-left: 14pt; border-left: 2.5pt solid var(--green); }
.quote p { font-size: 11.5pt; line-height: 1.5; margin: 0; }
.quote .src { font-size: 8.5pt; color: var(--grey); margin-top: 8pt; }

/* the three cover figures: the second thing the eye lands on */
.figs { display: flex; gap: 26pt; margin: 15pt 0 4pt; padding: 0; }
.figs div { flex: 1; }
.figs .n { font-size: 42pt; line-height: 0.95; font-weight: 700; color: var(--green);
           letter-spacing: -0.03em; }
.figs .t { font-size: 9pt; line-height: 1.44; color: var(--grey); margin-top: 7pt; }
.figs.three .n { font-size: 34pt; }

table { width: 100%; border-collapse: collapse; font-size: 9.5pt; }
th { text-align: left; font-weight: 700; font-size: 9pt; color: var(--ink);
     border-bottom: 1pt solid var(--hair); padding: 4pt 5pt; }
td { padding: 3.5pt 5pt; border-bottom: 1pt solid var(--hair); }
td.n, th.n { text-align: right; white-space: nowrap; }

/* Captions run two lines of content plus the case number, with the date
   abbreviated so nothing wraps -- a wrapped date sets every row in the grid to
   a different height and the page goes ragged. */
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 9pt 10pt; margin-top: 11pt; }
.cell img { width: 100%; height: 1.80in; object-fit: cover; display: block;
            background: var(--hair); }
.cap { font-size: 8.5pt; line-height: 1.3; margin-top: 4pt; }
.cap b { display: block; font-weight: 700; }
.cap .when { display: block; }
.cap .id { display: block; font-size: 7.5pt; color: var(--grey); }
.foot { font-size: 8pt; color: var(--grey); border-top: 1pt solid var(--hair);
        padding-top: 5pt; margin-top: 9pt; }
.lede { font-size: 10.5pt; }

/* Context photographs, one row of four at a single ratio: two landscape and
   two portrait in a 2x2 leaves holes down the column. */
.sites-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10pt; margin-top: 14pt; }
.sites-grid figure { margin: 0; }
.sites-grid img { width: 100%; height: 3.15in; object-fit: cover; display: block;
                  background: var(--hair); }
.sites-grid figcaption { font-size: 8.2pt; line-height: 1.36; margin-top: 5pt; color: var(--ink); }
.sites-grid figcaption b { display: block; font-weight: 700; }

/* display findings */
.display { padding: 0; margin: 15pt 0; }
.display .dnum { font-size: 28pt; line-height: 1; font-weight: 700; color: var(--green);
                 letter-spacing: -0.02em; }
.display .dline { font-size: 17pt; line-height: 1.24; font-weight: 700; color: var(--green); }
.display .dtxt { font-size: 9.5pt; color: var(--ink); margin-top: 8pt; }
.src { font-size: 8pt; color: var(--grey); margin-top: 6pt; }
table.tight { font-size: 8pt; }
table.tight td, table.tight th { padding: 1.6pt 5pt; }
tr.me td { font-weight: 700; }
.twocol { display: flex; gap: 20pt; margin-top: 12pt; align-items: flex-start; }
.twocol > div { min-width: 0; }
.twocol > div:first-child { flex: 1.55; }
.twocol > div:last-child { flex: 1; }
.twocol svg { display: block; margin-top: 4pt; height: 2.78in; width: auto; max-width: 100%; }

/* cover: the closure note and the photograph that answers it, side by side */
.coverflex { display: flex; gap: 18pt; align-items: flex-start; margin-top: 2pt; }
.coverflex > div, .coverflex > figure { min-width: 0; }
.coverflex > div { flex: 1.6; }
.coverfig { flex: 1; margin: 0; }
.coverfig img { width: 100%; height: 2.62in; object-fit: cover; object-position: 50% 60%;
                display: block; }
.coverfig figcaption { font-size: 8.2pt; line-height: 1.38; margin-top: 5pt; color: var(--ink); }
.coverfig figcaption b { display: block; font-weight: 700; }
.coverflex .quote p { font-size: 10.5pt; }
.claim { font-size: 15pt; line-height: 1.3; margin: 13pt 0 0; font-weight: 700; }

/* One picture, no reading required. Coral appears here and nowhere else. */
.bhead, .brow { display: grid; grid-template-columns: 58pt 1fr 26pt;
                align-items: center; gap: 9pt; }
.bhead { font-size: 8.4pt; color: var(--grey); padding-bottom: 5pt; }
.brow { font-size: 9.5pt; padding: 1.1pt 0; }
.bars { margin: 3pt 0 11pt; max-width: 76%; }
.btrack { background: transparent; height: 11.5pt; }
/* #E4E4E4 on #FAFAFA is too close to the paper to read as a bar. */
.bfill { background: #CFCFCF; height: 100%; }
.brow.me { font-weight: 700; }
.brow.me .bfill { background: var(--coral); }
.bv { text-align: right; }
"""

def short_date(iso):
    """26 Dec 2025. The full month name wraps in a four-across grid, and a
    wrapped date sets every row to a different height."""
    return datetime.date.fromisoformat(iso).strftime("%-d %b %Y")

def cell(c):
    state = (f'open {days_open(c)} days' if c["s"] else e(c["r"][:22]).lower())
    return (f'<div class="cell"><img src="print/{c["id"]}.jpg" alt="">'
            f'<div class="cap"><b>{e(c["a"])}</b>'
            f'<span class="when">{short_date(c["o"])} &middot; {state}</span>'
            f'<span class="id">#{e(c["id"])}</span></div></div>')

PER_PAGE = 12

def photo_page(title, lede, items, foot, cols=4):
    shown = items[:PER_PAGE]
    return (f'<div class="page"><h2>{title}</h2><p class="lede">{lede}</p>'
            f'<div class="grid" style="grid-template-columns:repeat({cols},1fr)">{"".join(cell(c) for c in shown)}</div>'
            f'<div class="foot">{foot}</div></div>')

# ---------------------------------------------------------------- districts
# Supervisor names are deliberately left out: the finding is about the
# distribution of the backlog, not about who represents where.
dist_rows = []
for d in sorted({c["d"] for c in citywide if c["d"]}, key=int):
    ds = [c for c in citywide if c["d"] == d]
    o = [c for c in ds if c["s"]]
    dd = sorted(days_open(c) for c in o)
    dist_rows.append((d, len(ds), len(o), dd[len(dd) // 2] if dd else 0))
city_open = sum(r[2] for r in dist_rows)
city_n = sum(r[1] for r in dist_rows)
pct_open = lambda r: (r[2] / r[1] * 100) if r[1] else 0
median_of_medians = statistics.median([r[3] for r in dist_rows])
# The longest median belongs to a district with a handful of open cases, so it
# is named rather than glossed: "longest wait" is a claim that would not hold.
longest_median = max(dist_rows, key=lambda r: r[3])

def bar_row(r):
    d, n, o, med = r
    pct = pct_open(r)
    cls = "brow me" if d == "6" else "brow"
    return (f'<div class="{cls}"><div class="bl">District {d}</div>'
            f'<div class="btrack"><div class="bfill" style="width:{pct:.0f}%"></div></div>'
            f'<div class="bv">{pct:.0f}%</div></div>')

dist_bars = "".join(bar_row(r) for r in sorted(dist_rows, key=pct_open, reverse=True))

def dist_row(r):
    d, n, o, med = r
    cls = ' class="me"' if d == "6" else ""
    return (f'<tr{cls}><td>District {d}</td><td class="n">{fmt(n)}</td>'
            f'<td class="n">{fmt(o)}</td><td class="n">{pct_open(r):.0f}%</td>'
            f'<td class="n">{med}</td></tr>')

dist_table = "".join(dist_row(r) for r in sorted(dist_rows, key=pct_open, reverse=True))

# ---------------------------------------------------------------- page 1
cover = f"""
<div class="page">
  <h1>{fmt(len(op))} Empty Tree Basins,<br>Still Waiting</h1>
  <div class="sub">Supervisor District 6 &mdash; photos and case records from San Francisco 311</div>
  <div class="dateline">Open cases as of {pretty(TODAY.isoformat())}</div>
  <div class="rule"></div>

  <div class="coverflex">
    <div>
      <p>San Francisco Public Works closed <strong>{fmt(len(nores))} District 6 cases</strong>
      with this note:</p>

      <div class="quote">
        <p>&ldquo;We have confirmed that this is an empty basin. Unfortunately, we do not currently
        have the resources to plant a new tree at this location, but it is on our list of sites to
        plant once funding is available. If you want to pursue the planting of and can water a new
        tree weekly for three years, please let us know at urbanforestry@sfdpw.org&rdquo;</p>
        <div class="src">Reproduced verbatim from the City&rsquo;s 311 records. The
        {fmt(len(nores))} cases carrying this note were closed between {pretty(nores_from)} and
        {pretty(nores_to)}.</div>
      </div>

      <p>The basin was inspected and confirmed empty. The case was closed without a tree being
      planted. The resident was invited to buy the tree and water it weekly for three years
      themselves &mdash; on a public sidewalk the City is responsible for maintaining.</p>
    </div>

    <figure class="coverfig"><img src="sites/site8.jpg" alt="">
      <figcaption><b>9th Street, approaching Brannan</b>A Public Works barricade
      (SFDPW&#8209;BSSR) posts a no&#8209;stopping work window for 20&ndash;24 October 2025.
      Utility locates are sprayed in orange and a tree basin is laid out in white. The concrete
      inside the marks was never cut.</figcaption></figure>
  </div>

  <div class="figs three">
    <div><div class="n">{fmt(len(op))}</div>
      <div class="t">empty basins reported in District 6 and still open today,
      out of {fmt(n_win)} reported in the last two years</div></div>
    <div><div class="n">{round(len(op)/city_open*100)}%</div>
      <div class="t">of every empty-basin report still open anywhere in San Francisco is in
      District 6 &mdash; which filed {round(n_win/city_n*100)}% of the city&rsquo;s reports</div></div>
    <div><div class="n">{median_open} days</div>
      <div class="t">median wait for an open case; the longest has been open
      {longest_open} days</div></div>
  </div>

  <p class="claim">The sites already exist. They are already cut, and already empty.</p>

  <p class="small" style="margin-top:9pt">Filling every basin in this document would close under
  2% of District 6&rsquo;s tree canopy gap.</p>

  <p class="small muted" style="margin-top:11pt">Every case in this document carries its 311
  case number and can be verified independently at
  mobile311.sfgov.org/tickets/&lt;case&nbsp;number&gt;. The complete set of
  {fmt(sum(1 for c in win if has(c)))} photographs is published at fairtrees.org and is
  available on request.</p>

  <p class="small muted" style="margin-top:13pt">Prepared by {e(SUBMITTER)}, {e(ORG)} &mdash;
  {pretty(TODAY.isoformat())}. Covers reports filed between {pretty(CUT)} and
  {pretty(TODAY.isoformat())}. Every figure comes from the City&rsquo;s own open data.</p>
</div>
"""

# ---------------------------------------------------------------- page 2
SHORT_HOOD = {"Financial District/South Beach": "FiDi / South Beach"}
hood_rows = "".join(
    f'<tr><td>{e(SHORT_HOOD.get(k, k))}</td><td class="n">{fmt(v)}</td>' 
    f'<td class="n">{fmt(sum(1 for c in win if (c["n"] or "Not recorded")==k and c["s"]))}</td></tr>'
    for k, v in hoods)

stevenson = sorted([c for c in win if norm(c["a"]).startswith("548 stevenson") and c["s"]],
                   key=lambda c: c["o"])

stevenson = sorted([c for c in win if norm(c["a"]).startswith("548 stevenson") and c["s"]],
                   key=lambda c: c["o"])

findings = f"""
<div class="page">
  <h2>Three in five reports are still open</h2>

  <p>Residents filed <strong>{fmt(n_win)}</strong> reports of empty street-tree basins in
  District 6 between {pretty(CUT)} and {pretty(TODAY.isoformat())}.
  <strong>{fmt(len(op))} of them &mdash; {round(len(op)/n_win*100)}% &mdash; are still open.</strong>
  The median open case has waited {median_open} days; the longest has been open
  {longest_open} days.</p>

  <div class="display">
    <div class="dnum">{fmt(len(mass_all))}</div>
    <div class="dtxt">empty-basin reports closed across San Francisco in a single day,
    {pretty(MASS)} &mdash; every one of them noted
    &ldquo;Cancelled&nbsp;&mdash;&nbsp;Planned Maintenance.&rdquo;
    <strong>{fmt(len(mass_d6))} were in District 6.</strong> Residents have since filed fresh
    reports at {fmt(len(reported_again))} of those District 6 locations, and every one of those
    new reports is still open. {fmt(len(reported_again_photo))} of them are photographed on page 6.</div>
  </div>

  <div class="display">
    <div class="dline">Six reports. One basin. One year. All still open.</div>
    <div class="dtxt">548 Stevenson Street was reported on
    {", ".join(pretty(c["o"], False) for c in stevenson[:-1])} and
    {pretty(stevenson[-1]["o"], False)} of this year. Each report is a separate 311 case. Not one
    has been closed.</div>
  </div>


  <div class="twocol">
    <div>
      <h3 style="margin-top:0">Where the open reports are</h3>
      {MAP_SVG}
      <p class="src">One dot per open report. Treasure Island, also in District 6, is not shown;
      none of its {fmt(sum(1 for c in win if c["n"]=="Treasure Island"))} reports is open.</p>
    </div>
    <div>
      <h3 style="margin-top:0">By neighborhood</h3>
      <table>
        <thead><tr><th>Neighborhood</th><th class="n">Reports</th><th class="n">Open</th></tr></thead>
        <tbody>{hood_rows}</tbody>
      </table>
    </div>
  </div>

  <h3>How the {fmt(len(cl))} closed reports were closed</h3>
  <p>Of the {fmt(len(cl))} reports the City closed in this period,
  <strong>{fmt(n_canc)} ({round(n_canc/len(cl)*100)}%)</strong> carry the note
  &ldquo;Cancelled &mdash; Planned Maintenance,&rdquo; and <strong>none</strong> record a tree
  having been planted. That figure describes the public record rather than the ground: closure
  notes became markedly less specific after about 2015, and today almost every closed report
  carries only that one phrase. Something may well have been planted at some of them. The point
  is that <strong>a resident cannot tell from the public record what happened to their
  report</strong>, which is why the same basins keep being reported again.</p>
</div>
"""

SHORT_HOOD = {"Financial District/South Beach": "FiDi / South Beach"}
hood_rows = "".join(
    f'<tr><td>{e(SHORT_HOOD.get(k, k))}</td><td class="n">{fmt(v)}</td>' 
    f'<td class="n">{fmt(sum(1 for c in win if (c["n"] or "Not recorded")==k and c["s"]))}</td></tr>'
    for k, v in hoods)

comparison = f"""
<div class="page">
  <h2>District 6 against the rest of the city</h2>

  <p>District 6 filed <strong>{round(n_win/city_n*100)}%</strong> of San Francisco&rsquo;s
  empty-basin reports over these two years and holds
  <strong>{round(len(op)/city_open*100)}% of every one still open</strong> &mdash;
  {fmt(len(op))} of {fmt(city_open)}, more than twice the next district. Everywhere else the
  share still open is below one in three. Its median open case has waited {median_open} days
  against {int(median_of_medians)} citywide: the second-longest, and the longest of any district
  with more than a handful of open cases. (District {longest_median[0]}&rsquo;s median is
  {longest_median[3]} days, on {longest_median[2]} open cases.)</p>

  <div class="bars">
    <div class="bhead"><div></div><div>Share of this district&rsquo;s reports still open</div>
      <div></div></div>
    {dist_bars}
  </div>

  <table class="tight">
    <thead><tr><th>District</th><th class="n">Reports</th><th class="n">Still open</th>
    <th class="n">% open</th><th class="n">Median days open</th></tr></thead>
    <tbody>{dist_table}</tbody>
  </table>
  <p class="src">All eleven districts, same period and same query. District is assigned from each
  report&rsquo;s coordinates against the City&rsquo;s current boundary file &mdash; the 311
  feed&rsquo;s own district field still carries the pre-2022 lines, and querying it directly
  returns a larger District 6.</p>

</div>
"""

lang_open = sum(1 for c in langton if c["s"])
lang_days = sorted(days_open(c) for c in langton if c["s"])
page_langton = photo_page(
    "One block: Langton Street",
    f"Langton Street is a two-block alley between Folsom and Howard. Residents photographed "
    f"<strong>{fmt(len(langton))}</strong> empty basins along it and "
    f"<strong>all {fmt(lang_open)} are still open</strong>, between {min(lang_days)} and "
    f"{max(lang_days)} days after they were reported. Twelve are shown here, in street-number "
    f"order. Three addresses appear twice: reported once in December 2025, again in March 2026, "
    f"both reports still open.",
    langton,
    "Every photograph was taken and submitted by a resident as part of their own 311 report.")

page_again = photo_page(
    "Closed as &ldquo;Planned&nbsp;Maintenance,&rdquo; then reported again",
    f"Each of these basins was among the {fmt(len(mass_d6))} District 6 reports the City closed on "
    f"{pretty(MASS)}. Each was then reported again by a resident &mdash; between 15 and 264 days "
    f"later &mdash; and photographed. <strong>Every one of these newer reports is still open.</strong> "
    f"The date shown is the date of the new report, not the closed one.",
    reported_again_photo,
    "The closure of a 311 case is not evidence that a tree was planted.", cols=4)

mix = china + howard[:max(0, 15 - len(china))]
china_days = sorted(days_open(c) for c in china if c["s"])
page_mix = photo_page(
    "Two more streets: China Basin and Howard",
    f"<strong>{fmt(len(china))}</strong> basins on China Basin Street in Mission Bay, "
    f"<strong>all still open</strong> &mdash; seven reported on one day, 22 February 2026, and "
    f"open {max(china_days)} days since. Two have been empty long enough that wild fennel has "
    f"filled them; the green in those frames is a weed, not a tree. They are followed by basins "
    f"on Howard Street, where every photographed report in this period is also still open.",
    mix,
    "Addresses run in street-number order.")


def page_stats(items):
    op = [c for c in items if c["s"]]
    dd = sorted(days_open(c) for c in op)
    return len(items), len(op), (min(dd) if dd else 0), (max(dd) if dd else 0)

# --- 9th Street -----------------------------------------------------------
ninth = block("9th st", open_first=True)
n_n, n_o, n_lo, n_hi = page_stats(ninth)
page_9th = photo_page(
    "9th Street",
    f"9th Street is six lanes wide with sidewalks to match, and it carries the barricade and the "
    f"white basin outline on the cover of this document. Residents photographed empty basins at "
    f"<strong>{fmt(len(block('9th st')))}</strong> addresses along it in this period. "
    f"<strong>{fmt(n_o)} of the twelve shown here are still open</strong>, between {n_lo} and "
    f"{n_hi} days after they were reported.",
    ninth,
    "Every photograph was taken by the resident who filed the report.")

# --- Harrison Street ------------------------------------------------------
harrison = block("harrison st", open_first=True)
h_n, h_o, h_lo, h_hi = page_stats(harrison)
page_harrison = photo_page(
    "Harrison Street",
    f"Harrison runs the width of the district, four lanes and a bike lane, from the Embarcadero to "
    f"the Mission. These twelve basins were photographed along it; "
    f"<strong>{fmt(h_o)} are still open</strong>, the oldest {h_hi} days after it was reported. "
    f"Five of them were reported on a single day, 23 January 2026.",
    harrison,
    "One further Harrison Street site has been withheld: trees were planted there after the "
    "photograph was taken, although its 311 cases remain open.")

# --- Market Street --------------------------------------------------------
market = block("market st", open_first=True)
m_n, m_o, m_lo, m_hi = page_stats(market)
page_market = photo_page(
    "Market Street",
    f"Market Street is the City&rsquo;s principal civic address and the one visitors walk. "
    f"Residents photographed empty basins at <strong>{fmt(len(block('market st')))}</strong> "
    f"addresses along the District 6 stretch of it. {fmt(m_o)} of the twelve here are still open, "
    f"the oldest {m_hi} days on. The remainder were closed without a planting recorded.",
    market,
    "Addresses run in street-number order.")

# --- the alleys -----------------------------------------------------------
alleys = block("minna st", "natoma st", "stevenson st", open_first=True)
a_n, a_o, a_lo, a_hi = page_stats(alleys)
page_alleys = photo_page(
    "The alleys: Minna, Natoma and Stevenson",
    f"Minna, Natoma and Stevenson run parallel between Mission and Howard and carry as much "
    f"pedestrian traffic as some of the numbered streets. Residents photographed "
    f"<strong>{fmt(len(block('minna st', 'natoma st', 'stevenson st')))}</strong> empty basins "
    f"across the three. <strong>{fmt(a_o)} of the twelve shown are still open</strong>, between "
    f"{a_lo} and {a_hi} days after they were reported. 548 Stevenson, reported six times in one "
    f"year, is one of these addresses.",
    alleys,
    "Grouped by street, then by street number.")

# --- Folsom and Mission ---------------------------------------------------
folmis = block("folsom st", "mission st", open_first=True)
f_n, f_o, f_lo, f_hi = page_stats(folmis)
page_folmis = photo_page(
    "Folsom Street and Mission Street",
    f"Two of the thoroughfares named on page 2. Residents photographed "
    f"<strong>{fmt(len(block('folsom st', 'mission st')))}</strong> empty basins along them; "
    f"<strong>{fmt(f_o)} of the twelve here are still open</strong>, the oldest {f_hi} days after "
    f"it was reported.",
    folmis,
    "Folsom Street first, then Mission, each in street-number order.")

# --- the remaining numbered streets --------------------------------------
numbered = block("7th st", "8th st", "10th st", "11th st", open_first=True)
u_n, u_o, u_lo, u_hi = page_stats(numbered)
page_numbered = photo_page(
    "7th, 8th, 10th and 11th Streets",
    f"The rest of the numbered thoroughfares named on page 2, each of them four lanes or more. "
    f"Residents photographed "
    f"<strong>{fmt(len(block('7th st', '8th st', '10th st', '11th st')))}</strong> empty basins "
    f"across the four. {fmt(u_o)} of the twelve shown are still open, the oldest {u_hi} days on.",
    numbered,
    "Grouped by street, then by street number.")

sites = f"""
<div class="page">
  <h2>The sites already exist</h2>

  <p>Public Works and the Urban Forestry Council tell this district it has too few places to put
  a tree, and that its streets are too narrow. The City&rsquo;s own reports say otherwise.
  <strong>{fmt(len(on_main))}
  of the {fmt(n_win)} empty basins reported here &mdash; half of them &mdash; are on the
  district&rsquo;s widest thoroughfares</strong>: 6th, 7th, 8th, 9th, 10th, 11th and 12th Streets,
  and Mission, Howard, Market, Folsom and Harrison. <strong>{fmt(len(on_main_open))}</strong> of
  those are still open. Not one of them requires a new cut in the pavement.</p>

  <p>Beyond them are long stretches of wide sidewalk carrying no basins at all &mdash; and sites
  the City has itself surveyed, marked out and posted for work, where the pavement was never cut.
  The barricade and white basin outline on the cover of this document stand on 9th Street, two
  blocks from the frontage below.</p>

  <div class="sites-grid">
    <figure><img src="sites/site2.jpg" alt="">
      <figcaption><b>9th Street at Brannan Street</b>An entire block frontage, wide throughout,
      carrying no street tree and no basin.</figcaption></figure>
    <figure><img src="sites/site3.jpg" alt="">
      <figcaption><b>The same block, at pavement level</b>Full width the length of the building.
      No basin anywhere along it.</figcaption></figure>
    <figure><img src="sites/site5.jpg" alt="">
      <figcaption><b>Two basins marked out, at dusk</b>Two outlines sprayed in white on a wide
      sidewalk. The pavement inside them has not been cut.</figcaption></figure>
    <figure><img src="sites/site9.jpg" alt="">
      <figcaption><b>Beneath the freeway viaduct</b>Basins laid out in white along a wide
      sidewalk. Neither side of the street carries a tree.</figcaption></figure>
  </div>

  <div class="foot">District 6 has room for trees. Thousands of basins here were cut years ago
  and now sit empty, and at the sites above the City has sprayed out where the next ones go and
  left the pavement uncut.</div>
</div>
"""

doc = (f'<!doctype html><html><head><meta charset="utf-8">'
       f'<title>{fmt(len(op))} Empty Tree Basins, Still Waiting — Supervisor District 6</title>'
       f'<style>{CSS}</style></head><body>'
       + cover + sites + findings + comparison
       + page_langton + page_again + page_mix
       + page_9th + page_harrison + page_market + page_alleys + page_folmis + page_numbered
       + '</body></html>')
open(f"{SCR}/exhibit_v2.html", "w").write(doc)

print(f"window {CUT} .. {TODAY}")
print(f"reports={n_win} open={len(op)} ({round(len(op)/n_win*100)}%) closed={len(cl)} "
      f"cancelled={n_canc} planted={n_plant} median={median_open} longest={longest_open}")
print(f"mass closure {MASS}: citywide={len(mass_all)} d6={len(mass_d6)} "
      f"re-reported={len(reported_again)} (photo {len(reported_again_photo)})")
print(f"548 Stevenson open reports={len(stevenson)}")
print(f"photo pages: langton={len(langton)} again={len(reported_again_photo)} mix={len(mix)} "
      f"9th={len(ninth)} harrison={len(harrison)} market={len(market)} alleys={len(alleys)} "
      f"folsom+mission={len(folmis)} numbered={len(numbered)}")
print(f"quoted cases={len(nores)} ({nores_from}..{nores_to})")
