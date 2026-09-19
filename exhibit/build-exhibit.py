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
# Addresses that were photographed as empty basins but have since been planted.
# A frame a reader can disprove on foot would be used against the whole document,
# so these never reach a page no matter what the 311 record still says.
#
#   1532 Harrison St   trees planted; its 311 cases are nonetheless still open.
#   1174 Bryant St     planted by Friends of the Urban Forest, 18 April 2026
#   333 11th St        "
#   355 11th St        "
#
# The Friends of the Urban Forest entries come from the SOMA West CBD watering
# list dated 22 April 2026 (45 trees, all planted 18 April 2026). Cross-matched
# on exact street address; the four City cases at those addresses were all
# closed on 5 December 2025 as "Cancelled - Planned Maintenance", four months
# before a tree went in, and none of them was open. Nothing else on that list
# lands within a parcel of a report in this document.
WITHHELD = {"1532 harrison st", "1174 bryant st", "333 11th st", "355 11th st"}

def has(c):
    if re.sub(r"\s+", " ", c["a"].strip().lower()) in WITHHELD:
        return False
    return os.path.exists(f"{SCR}/print/{c['id']}.jpg")
norm = lambda a: re.sub(r"\s+", " ", a.strip().lower())
days_open = lambda c: (TODAY - datetime.date.fromisoformat(c["o"])).days
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
        if has(first) and days_open(first) >= 30:
            reported_again_photo.append(first)
reported_again_photo.sort(key=lambda c: c["o"])

# A report filed last week is not evidence that anyone has been ignored.
MIN_DAYS = 30
# Four across holds three rows on a 0.9in-margin page.
PER_PAGE = 12

# The "reported again" page makes a specific argument about these cases, so it
# has first claim on them. Reserved by address rather than by case id: the same
# basin is often carried by several cases, and two of them on two pages reads
# as padding just as plainly as one photograph printed twice.
RESERVED = {norm(c["a"]) for c in reported_again_photo}

street_of = lambda c: re.sub(r"^\d+\s+", "", c["a"]).strip().lower()
num_of = lambda c: int(re.match(r"^(\d+)", c["a"]).group(1)) if re.match(r"^(\d+)", c["a"]) else 0


def candidates(names=None, exclude=None):
    """Photographed, still open, and open long enough to mean something.

    Closed cases are kept off the photograph pages entirely. Each one hands the
    department an opening -- "that case was closed, we handled it" -- and the
    argument about what a closure note actually means belongs on page 3, where
    it is properly framed.
    """
    sel = [c for c in win if has(c) and c["s"] and days_open(c) >= MIN_DAYS
           and norm(c["a"]) not in RESERVED]
    if names is not None:
        sel = [c for c in sel if street_of(c) in names]
    if exclude is not None:
        sel = [c for c in sel if street_of(c) not in exclude]
    return sel


def block(*street_names, limit=PER_PAGE, exclude=None):
    """One photograph per address, longest-waiting first, shown in street order.

    Three frames of the same address reads as padding, and padding is the one
    real risk of running long.
    """
    names = set(street_names) if street_names else None
    best = {}
    for c in candidates(names, exclude):
        k = norm(c["a"])
        if k not in best or days_open(c) > days_open(best[k]):
            best[k] = c
    chosen = sorted(best.values(), key=days_open, reverse=True)[:limit]
    return sorted(chosen, key=lambda c: (street_of(c), num_of(c)))


def addr_count(*street_names):
    names = set(street_names)
    return len({norm(c["a"]) for c in win if has(c) and street_of(c) in names})

langton = block("langton st")
ninth_harrison = block("9th st", "harrison st")
china_howard = block("china basin st", "howard st")
alleys = block("minna st", "natoma st", "stevenson st")
folmis = block("folsom st", "mission st")
market_num = block("market st", "7th st", "8th st", "10th st", "11th st")
NAMED = {"langton st", "9th st", "harrison st", "china basin st", "howard st",
         "minna st", "natoma st", "stevenson st", "folsom st", "mission st",
         "market st", "7th st", "8th st", "10th st", "11th st"}
elsewhere = block(exclude=NAMED)
oldest = sorted([c for c in op if has(c)], key=lambda c: c["o"])[:15]

e = html.escape
fmt = lambda n: f"{n:,}"
TICKET = "https://mobile311.sfgov.org/tickets/"
def pretty(iso, yr=True):
    if not iso: return "—"
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%-d %B %Y") if yr else d.strftime("%-d %B")

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
/* The case number is a link to the City's own record for that ticket. Kept in
   the caption grey, with a hairline underline so it reads as clickable on
   screen and still looks deliberate in print. */
.cap .id { display: block; font-size: 7.5pt; color: var(--grey); }
.cap .id a { color: inherit; text-decoration: underline;
             text-decoration-color: var(--hair); text-underline-offset: 1.5pt; }
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

# Closure reasons are rewritten rather than truncated: the raw strings run past
# the caption box and stop mid-word.
SHORT_OUTCOME = {
    "Cancelled — planned maintenance": "closed, planned maintenance",
    "Cancelled": "closed, cancelled",
    "Marked resolved — no detail": "closed, no detail",
    "Duplicate report": "closed, duplicate",
    "Tree planted": "tree planted",
    "Queued for planting": "queued for planting",
}

def cell(c):
    if c["s"]:
        d = days_open(c)
        state = f'open {d} day' + ("" if d == 1 else "s")
    else:
        state = e(SHORT_OUTCOME.get(c["r"], "closed"))
    return (f'<div class="cell"><img src="print/{c["id"]}.jpg" alt="">'
            f'<div class="cap"><b>{e(c["a"])}</b>'
            f'<span class="when">{short_date(c["o"])} &middot; {state}</span>'
            f'<span class="id"><a href="{TICKET}{e(c["id"])}">#{e(c["id"])}</a></span>'
            f'</div></div>')

WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
         "nine", "ten", "eleven", "twelve"]
words = lambda n: WORDS[n] if n < len(WORDS) else fmt(n)


def photo_page(title, lede, items, foot, cols=None):
    shown = items[:PER_PAGE]
    # Nine across four columns leaves a row of one. Three columns fills it, and
    # the photographs come out larger for it.
    if cols is None:
        cols = 3 if len(shown) == 9 else 4
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
  case number, and <strong>each one is a link</strong> to the City&rsquo;s own record for that
  ticket at <a href="https://mobile311.sfgov.org/">mobile311.sfgov.org</a>. The complete set of
  {fmt(sum(1 for c in win if has(c)))} photographs is published at
  <a href="https://fairtrees.org">fairtrees.org</a> and is available on request.</p>

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

def spread(items):
    d = sorted(days_open(c) for c in items)
    return d[0], d[-1]


def same_day(items):
    """The busiest single filing date on a page, as (count, pretty date)."""
    day, n = collections.Counter(c["o"] for c in items).most_common(1)[0]
    return n, pretty(day)


def page(title, lede, items, foot):
    return photo_page(title, lede, items, foot)


lang_lo, lang_hi = spread(langton)
lang_same = same_day(langton)
page_langton = page(
    "One block: Langton Street",
    f"Langton Street is a two-block alley between Folsom and Howard. Residents photographed "
    f"empty basins at <strong>{words(addr_count('langton st'))} addresses</strong> along it, and "
    f"<strong>every one is still open</strong> &mdash; between {lang_lo} and {lang_hi} days "
    f"after it was reported. {words(lang_same[0]).capitalize()} were filed on a single day, "
    f"{lang_same[1]}.",
    langton,
    "One photograph per address. Every one was taken by the resident who filed the report.")

again_lo, again_hi = spread(reported_again_photo)
page_again = page(
    "Closed as &ldquo;Planned&nbsp;Maintenance,&rdquo; then reported again",
    f"Each of these basins was among the {fmt(len(mass_d6))} District 6 reports the City closed on "
    f"{pretty(MASS)}. Each was reported again afterwards by a resident, and photographed. "
    f"<strong>Every one of these newer reports is still open</strong>, between {again_lo} and "
    f"{again_hi} days on. The date shown is the date of the new report, not the closed one.",
    reported_again_photo,
    "The closure of a 311 case is not evidence that a tree was planted.")

ch_lo, ch_hi = spread(china_howard)
page_china_howard = page(
    "China Basin Street and Howard Street",
    f"China Basin Street runs through Mission Bay, the newest housing in the district; Howard "
    f"carries four lanes through the oldest. Residents photographed empty basins at "
    f"<strong>{fmt(addr_count('china basin st', 'howard st'))} addresses</strong> across the two. "
    f"<strong>All {words(len(china_howard))} here are still open</strong>, between {ch_lo} and "
    f"{ch_hi} days on. Two of the China Basin basins have stood empty long enough for wild fennel "
    f"to fill them; the green in those frames is a weed, not a tree.",
    china_howard,
    "China Basin Street first, then Howard, each in street-number order.")

nh_lo, nh_hi = spread(ninth_harrison)
page_ninth_harrison = page(
    "9th Street and Harrison Street",
    f"9th Street is six lanes wide with sidewalks to match, and carries the barricade and white "
    f"basin outline on the cover of this document. Harrison runs the width of the district. "
    f"Residents photographed empty basins at "
    f"<strong>{fmt(addr_count('9th st', 'harrison st'))} addresses</strong> along the two. "
    f"<strong>All {words(len(ninth_harrison))} here are still open</strong>, between {nh_lo} and "
    f"{nh_hi} days on.",
    ninth_harrison,
    "One Harrison Street site is withheld: trees were planted there after the photograph was "
    "taken, although its 311 cases remain open.")

al_lo, al_hi = spread(alleys)
page_alleys = page(
    "The alleys: Minna, Natoma and Stevenson",
    f"Minna, Natoma and Stevenson run parallel between Mission and Howard and carry as much foot "
    f"traffic as some of the numbered streets. Residents photographed empty basins at "
    f"<strong>{fmt(addr_count('minna st', 'natoma st', 'stevenson st'))} addresses</strong> across "
    f"the three. <strong>All {words(len(alleys))} here are still open</strong>, between {al_lo} and "
    f"{al_hi} days on. 548 Stevenson, reported six times in one year, is one of them.",
    alleys,
    "Grouped by street, then by street number.")

fm_lo, fm_hi = spread(folmis)
page_folmis = page(
    "Folsom Street and Mission Street",
    f"Two of the thoroughfares named on page 2. Residents photographed empty basins at "
    f"<strong>{fmt(addr_count('folsom st', 'mission st'))} addresses</strong> along them. "
    f"<strong>All {words(len(folmis))} here are still open</strong>, the oldest {fm_hi} days after "
    f"it was reported.",
    folmis,
    "Folsom Street first, then Mission, each in street-number order.")

mn_lo, mn_hi = spread(market_num)
page_market_num = page(
    "Market Street and the numbered thoroughfares",
    f"Market Street is the City&rsquo;s principal civic address and the one visitors walk; 7th, "
    f"8th, 10th and 11th are four lanes or more apiece. Residents photographed empty basins at "
    f"<strong>{fmt(addr_count('market st', '7th st', '8th st', '10th st', '11th st'))} "
    f"addresses</strong> across the five. <strong>All {words(len(market_num))} here are still "
    f"open</strong>, between {mn_lo} and {mn_hi} days on.",
    market_num,
    "Grouped by street, then by street number.")

el_lo, el_hi = spread(elsewhere)
page_elsewhere = page(
    "The rest of the district",
    f"Not every empty basin sits on a street with enough of them to fill a page. These are on "
    f"Otis, Grove, Moss, Beale, Clarence, Page, Mission Rock, Terry A Francois and the "
    f"Embarcadero, among others. <strong>All {words(len(elsewhere))} are still open</strong>, "
    f"between {el_lo} and {el_hi} days on.",
    elsewhere,
    "One photograph per address, longest-waiting first.")

sites = f"""
<div class="page">
  <h2>The sites already exist</h2>

  <p>Public Works tells this district it has too few places to put a tree, and that its streets
  are too narrow. The City&rsquo;s own reports say otherwise.
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
       + page_langton + page_again + page_ninth_harrison
       + page_alleys + page_folmis + page_china_howard + page_market_num
       + page_elsewhere
       + '</body></html>')
open(f"{SCR}/exhibit_v2.html", "w").write(doc)

print(f"window {CUT} .. {TODAY}")
print(f"reports={n_win} open={len(op)} ({round(len(op)/n_win*100)}%) closed={len(cl)} "
      f"cancelled={n_canc} planted={n_plant} median={median_open} longest={longest_open}")
print(f"mass closure {MASS}: citywide={len(mass_all)} d6={len(mass_d6)} "
      f"re-reported={len(reported_again)} (photo {len(reported_again_photo)})")
print(f"548 Stevenson open reports={len(stevenson)}")
shown_ids = set()
for nm, it in (("langton", langton), ("again", reported_again_photo),
               ("9th+harrison", ninth_harrison), ("alleys", alleys),
               ("folsom+mission", folmis), ("china+howard", china_howard),
               ("market+numbered", market_num), ("elsewhere", elsewhere)):
    addrs = {norm(c["a"]) for c in it}
    ids = {norm(c["a"]) for c in it}
    assert len(addrs) == len(it), f"{nm}: repeated address"
    assert not (ids & shown_ids), f"{nm}: address already on another page"
    shown_ids |= ids
    assert all(c["s"] and days_open(c) >= MIN_DAYS for c in it), f"{nm}: closed or too new"
    print(f"  {nm:<16} {len(it):>2} photos, {len(addrs):>2} addresses, "
          f"{min(days_open(c) for c in it)}-{max(days_open(c) for c in it)} days open")
print(f"quoted cases={len(nores)} ({nores_from}..{nores_to})")
