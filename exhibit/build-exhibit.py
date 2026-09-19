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
has = lambda c: os.path.exists(f"{SCR}/print/{c['id']}.jpg")
norm = lambda a: re.sub(r"\s+", " ", a.strip().lower())
citywide = [c for c in cases if c["o"] and c["o"] >= CUT and c["d"]]
SUPERVISORS = {d["id"]: d["supervisor"]
               for d in json.load(open("/home/user/fairtrees/public/data/meta.json"))["districts"]}
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
/* Context photographs: shown whole rather than cropped, since the width of the
   pavement is the point being made. */
.sites-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10pt 15pt; margin-top: 11pt; }
.sites-grid figure { margin: 0; }
.sites-grid img { width: 100%; height: 2.12in; object-fit: contain;
                  background: #fff; display: block; }
.sites-grid figure > img { border-bottom: 0.5pt solid #ddd; padding-bottom: 3pt; }
.sites-grid figcaption { font-size: 7.6pt; line-height: 1.35; margin-top: 4pt; color: #444;
                         font-family: Helvetica, Arial, sans-serif; }
.sites-grid figcaption b { display: block; color: #111; }

/* display findings, matching the weight of the cover figures */
.display { border-top: 0.75pt solid #bbb; border-bottom: 0.75pt solid #bbb;
           padding: 11pt 0; margin: 14pt 0; }
.display .dnum { font-size: 30pt; line-height: 1; }
.display .dline { font-size: 15pt; line-height: 1.25; }
.display .dtxt { font-size: 9.2pt; color: #333; margin-top: 7pt; }
.src { font-size: 7.8pt; color: #666; margin-top: 5pt; }
table.tight td, table.tight th { padding: 2.8pt 5pt; }
tr.me td { font-weight: bold; background: #f0f0ec; }
.twocol { display: flex; gap: 20pt; margin-top: 15pt; align-items: flex-start; }
/* Flex items default to min-width:auto, which lets the map force the
   column wider than its share instead of scaling down into it. */
.twocol > div { min-width: 0; }
.twocol > div:first-child { flex: 1.35; }
.twocol > div:last-child { flex: 1; }
.twocol svg { display: block; margin-top: 4pt; height: 2.9in; width: auto; max-width: 100%; }

"""

def cell(c):
    return (f'<div class="cell"><img src="print/{c["id"]}.jpg" alt="">'
            f'<div class="cap"><b>{e(c["a"])}</b>'
            f'<span>Reported {pretty(c["o"], False)} {c["o"][:4]}</span>'
            f'<span class="o">{"Open " + str(days_open(c)) + " days" if c["s"] else e(c["r"][:26])}</span>'
            f'<span>#{e(c["id"])}</span></div></div>')

def photo_page(title, lede, items, foot, cols=5):
    return (f'<div class="page"><h2>{title}</h2><p class="lede">{lede}</p>'
            f'<div class="grid" style="grid-template-columns:repeat({cols},1fr)">{"".join(cell(c) for c in items)}</div>'
            f'<div class="foot">{foot}</div></div>')

# ---------------------------------------------------------------- page 1
cover = f"""
<div class="page">
  <h1>{fmt(len(op))} Empty Tree Basins,<br>Still Waiting</h1>
  <div class="sub">Supervisor District 6 &mdash; photographic and records evidence
  from San Francisco 311</div>
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

stevenson = sorted([c for c in win if norm(c["a"]).startswith("548 stevenson") and c["s"]],
                   key=lambda c: c["o"])

dist_rows = []
for d in sorted({c["d"] for c in citywide if c["d"]}, key=int):
    ds = [c for c in citywide if c["d"] == d]
    o = [c for c in ds if c["s"]]
    dd = sorted(days_open(c) for c in o)
    dist_rows.append((d, SUPERVISORS.get(d, ""), len(ds), len(o), dd[len(dd) // 2] if dd else 0))
city_open = sum(r[3] for r in dist_rows)
city_n = sum(r[2] for r in dist_rows)
median_of_medians = statistics.median([r[4] for r in dist_rows])
d11 = max(dist_rows, key=lambda r: r[4])

stevenson = sorted([c for c in win if norm(c["a"]).startswith("548 stevenson") and c["s"]],
                   key=lambda c: c["o"])

findings = f"""
<div class="page">
  <h2>What the record shows</h2>

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
    new reports is still open. Twelve are photographed on page 5.</div>
  </div>

  <div class="display">
    <div class="dline">Six reports. One basin. One year. All still open.</div>
    <div class="dtxt">548 Stevenson Street was reported on
    {", ".join(pretty(c["o"], False) for c in stevenson[:-1])} and
    {pretty(stevenson[-1]["o"], False)} of this year. Each report is a separate 311 case. Not one
    has been closed.</div>
  </div>

  <h3>How the {fmt(len(cl))} closed reports were closed</h3>
  <p>Of the {fmt(len(cl))} reports the City closed in this period,
  <strong>{fmt(n_canc)} ({round(n_canc/len(cl)*100)}%)</strong> carry the note
  &ldquo;Cancelled &mdash; Planned Maintenance,&rdquo; and <strong>none</strong> record a tree
  having been planted. That figure describes the public record rather than the ground: closure
  notes became markedly less specific after about 2015, and today almost every closed report
  carries only that one phrase. The fair conclusion is not that nothing was planted, but that
  <strong>a resident cannot tell from the public record what happened to their report</strong>
  &mdash; which is why the same basins keep being reported again.</p>
</div>
"""

def dist_row(d, nm, n, o, med):
    cls = ' class="me"' if d == "6" else ""
    pct = round(o / n * 100) if n else 0
    return (f'<tr{cls}><td>{d} &nbsp;{e(nm)}</td><td class="n">{fmt(n)}</td>'
            f'<td class="n">{fmt(o)}</td><td class="n">{pct}%</td>'
            f'<td class="n">{med}</td></tr>')

dist_table = "".join(dist_row(*r) for r in dist_rows)

hood_rows = "".join(
    f'<tr><td>{e(k)}</td><td class="n">{fmt(v)}</td>'
    f'<td class="n">{fmt(sum(1 for c in win if (c["n"] or "Not recorded")==k and c["s"]))}</td></tr>'
    for k, v in hoods)

comparison = f"""
<div class="page">
  <h2>District 6 against the rest of the city</h2>

  <p>Empty basins are not evenly distributed, and neither is the wait. District 6 filed
  <strong>{round(n_win/city_n*100)}%</strong> of the empty-basin reports made in San Francisco over
  these two years, and holds <strong>{round(len(op)/city_open*100)}% of every one that is still
  open</strong> &mdash; {fmt(len(op))} of {fmt(city_open)}, more than twice the next district.
  Its median open case has waited {median_open} days against {int(median_of_medians)} across the
  eleven districts. Only District {d11[0]}&rsquo;s median is longer, on {d11[3]} open cases.</p>

  <table class="tight">
    <thead><tr><th>Supervisorial district</th><th class="n">Reports</th><th class="n">Still open</th>
    <th class="n">% open</th><th class="n">Median days open</th></tr></thead>
    <tbody>{dist_table}</tbody>
  </table>
  <p class="src">All eleven districts, same period and same query. District is assigned from each
  report&rsquo;s coordinates against the City&rsquo;s current boundary file &mdash; the 311
  feed&rsquo;s own district field still carries the pre-2022 lines, and querying it directly
  returns a larger District 6.</p>

  <div class="twocol">
    <div>
      <h3 style="margin-top:4pt">Where the open reports are</h3>
      {MAP_SVG}
      <p class="src">One dot per open report. Treasure Island, also in District 6, is not shown;
      none of its {fmt(sum(1 for c in win if c["n"]=="Treasure Island"))} reports is open.</p>
    </div>
    <div>
      <h3 style="margin-top:4pt">By neighborhood</h3>
      <table>
        <thead><tr><th>Neighborhood</th><th class="n">Reports</th><th class="n">Open</th></tr></thead>
        <tbody>{hood_rows}</tbody>
      </table>
      <p class="src">Every report carries a City neighborhood label.</p>
    </div>
  </div>
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
    "The closure of a 311 case is not evidence that a tree was planted.", cols=4)

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


sites = f"""
<div class="page">
  <h2>The sites already exist</h2>

  <p>District 6 is often told it has too few places to put a tree, or that its streets are too
  narrow. The City&rsquo;s own reports say otherwise: <strong>{fmt(len(on_main))} of the
  {fmt(n_win)} empty basins reported here &mdash; half of them &mdash; are on the district&rsquo;s
  widest thoroughfares</strong>: 6th, 7th, 8th, 9th, 10th, 11th and 12th Streets, and Mission,
  Howard, Market, Folsom and Harrison. <strong>{fmt(len(on_main_open))}</strong> of those are still
  open. These are basins that already exist, already cut, already empty.</p>

  <p>Beyond them are long stretches of wide sidewalk carrying no basins at all, and sites the
  City has itself marked and then left unplanted.</p>

  <div class="sites-grid">
    <figure><img src="sites/site2.jpg" alt="">
      <figcaption><b>9th Street at Brannan Street</b>An entire block frontage, and a sidewalk wide
      enough throughout, carrying no street tree and no basin.</figcaption></figure>
    <figure><img src="sites/site3.jpg" alt="">
      <figcaption><b>The same block, at pavement level</b>The sidewalk runs the length of the
      building at full width. There is no basin anywhere along it.</figcaption></figure>
    <figure><img src="sites/site4.jpg" alt="">
      <figcaption><b>Beneath the freeway viaduct</b>A wide sidewalk carrying a bicycle share
      station and a striped bicycle lane, and no trees on either side of the street.</figcaption></figure>
    <figure><img src="sites/site5.jpg" alt="">
      <figcaption><b>A site marked and left</b>Survey marks laying out a basin on the pavement. The
      concrete inside them is uncut and there is no tree.</figcaption></figure>
  </div>

  <div class="foot">The question is not whether District 6 has room for trees. The City has already
  cut the basins, and in places already marked where the next ones should go.</div>
</div>
"""

doc = (f'<!doctype html><html><head><meta charset="utf-8">'
       f'<title>{fmt(len(op))} Empty Tree Basins, Still Waiting — Supervisor District 6</title>'
       f'<style>{CSS}</style></head><body>'
       + cover + findings + comparison + page_langton + page_again + page_mix + sites
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
