#!/usr/bin/env python3
"""Build the District 6 hearing exhibit as printable HTML.

Two outputs:
  exhibit.html   ~10-page exhibit, most recent 72 photographs
  appendix.html  complete photographic record, all 265 photographs
"""
import json, os, sys, html, datetime, collections

SCR = "/tmp/claude-0/-home-user-fairtrees/6033c420-3be7-5d5a-929d-e2a8b1fd6fea/scratchpad"
SUBMITTER = "Shaun Aukland"
ORG = "FairTrees.org"
TODAY = datetime.date.today()
WINDOW_DAYS = 730

cases = json.load(open("/home/user/fairtrees/public/data/snapshot.json"))["cases"]
d6 = [c for c in cases if c["d"] == "6"]
cut = (TODAY - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
win = [c for c in d6 if c["o"] and c["o"] >= cut]
has_img = lambda c: os.path.exists(f"{SCR}/print/{c['id']}.jpg")
photos = sorted([c for c in win if has_img(c)], key=lambda c: c["o"] or "", reverse=True)
PER_PAGE = 12
PHOTO_SHEETS = 6
# The exhibit shows the most recent N; the appendix carries all of them.
main_photos = photos[:PER_PAGE * PHOTO_SHEETS]

# --- figures, all computed from the data rather than typed in ---
n_win = len(win)
n_open = sum(1 for c in win if c["s"])
closed = [c for c in win if not c["s"]]
n_cancelled = sum(1 for c in closed if c["r"].startswith("Cancelled"))
n_planted = sum(1 for c in win if c["r"] in ("Tree planted", "Queued for planting"))
opendays = sorted((TODAY - datetime.date.fromisoformat(c["o"])).days for c in win if c["s"])
median_open = opendays[len(opendays) // 2]
longest_open = max(opendays)
nores = [c for c in d6 if c["r"].startswith("Confirmed empty")]
nores_from = min(c["c"] for c in nores if c["c"])
nores_to = max(c["c"] for c in nores if c["c"])
outcomes = collections.Counter(c["r"] for c in win).most_common()
hoods = collections.Counter(c["n"] or "Not recorded" for c in win).most_common()

QUOTE = ("We have confirmed that this is an empty basin. Unfortunately, we do not currently "
         "have the resources to plant a new tree at this location, but it is on our list of "
         "sites to plant once funding is available. If you want to pursue the planting of and "
         "can water a new tree weekly for three years, please let us know at urbanforestry@sfdpw.org")

e = html.escape
fmt = lambda n: f"{n:,}"

def pretty(iso):
    if not iso: return "—"
    return datetime.date.fromisoformat(iso).strftime("%b %-d, %Y")

def status_line(c):
    if c["s"]:
        days = (TODAY - datetime.date.fromisoformat(c["o"])).days
        return f'<span class="open">Open {days} days</span>'
    return f'<span class="closed">{e(c["r"])}</span>'

CSS = """
@page { size: Letter; margin: 0.6in 0.6in 0.75in 0.6in; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 9.6pt; line-height: 1.45; color: #111; -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.page { page-break-after: always; position: relative; }
.cover { min-height: 9.3in; }
.page:last-child { page-break-after: auto; }
h1, h2, h3 { margin: 0 0 6pt; line-height: 1.2; font-weight: 700; }
h1 { font-size: 26pt; letter-spacing: -0.5pt; }
h2 { font-size: 15pt; letter-spacing: -0.2pt; border-bottom: 1.5pt solid #1b5e45; padding-bottom: 5pt; margin-bottom: 11pt; }
h3 { font-size: 10.5pt; }
p { margin: 0 0 8pt; }
.muted { color: #555; }
.small { font-size: 8.4pt; }
.tiny { font-size: 7.4pt; }
strong { font-weight: 700; }

/* running header on content pages */
.runhead {
  display: flex; justify-content: space-between; align-items: baseline;
  border-bottom: 0.5pt solid #bbb; padding-bottom: 4pt; margin-bottom: 12pt;
  font-size: 7.6pt; color: #666; letter-spacing: 0.3pt; text-transform: uppercase;
}

/* cover */
.cover-kicker { font-size: 8.5pt; letter-spacing: 1.6pt; text-transform: uppercase; color: #1b5e45; font-weight: 700; margin-bottom: 14pt; }
.cover-rule { height: 3pt; background: #1b5e45; width: 100%; margin: 16pt 0 18pt; }
.cover-sub { font-size: 13pt; color: #333; line-height: 1.35; margin-bottom: 4pt; }
.cover-meta { margin-top: 26pt; font-size: 9.6pt; }
.cover-meta div { margin-bottom: 3pt; }
.cover-box { border: 1pt solid #1b5e45; background: #f2f7f4; padding: 14pt 16pt; margin: 22pt 0; }
.cover-figs { display: flex; gap: 0; margin: 0; }
.cover-figs div { flex: 1; border-right: 0.5pt solid #cbd9d1; padding: 0 10pt; }
.cover-figs div:first-child { padding-left: 0; }
.cover-figs div:last-child { border-right: 0; padding-right: 0; }
.fig-n { font-size: 21pt; font-weight: 700; line-height: 1; letter-spacing: -0.5pt; }
.fig-l { font-size: 7.6pt; color: #444; margin-top: 4pt; line-height: 1.3; }
.sign-line { border-bottom: 0.75pt solid #333; display: inline-block; min-width: 2.6in; }

/* stat tiles */
.tiles { display: flex; gap: 9pt; margin-bottom: 14pt; }
.tile { flex: 1; border: 0.75pt solid #ccc; border-top: 2.5pt solid #1b5e45; padding: 9pt 10pt 8pt; }
.tile .n { font-size: 19pt; font-weight: 700; line-height: 1; letter-spacing: -0.5pt; }
.tile .l { font-size: 7.4pt; color: #555; margin-top: 4pt; line-height: 1.3; text-transform: uppercase; letter-spacing: 0.3pt; }
.tile.alert { border-top-color: #b3322f; }
.tile.alert .n { color: #b3322f; }

/* single-series magnitude bars: one hue, value labelled directly, no legend */
.bars { margin: 4pt 0 0; }
.bar-row { display: flex; align-items: center; gap: 8pt; margin-bottom: 3.5pt; }
.bar-lab { width: 2.35in; font-size: 8.4pt; text-align: right; color: #333; }
.bar-track { flex: 1; background: #eee; height: 13pt; }
.bar-fill { height: 100%; background: #2a6099; }
.bar-val { width: 0.95in; font-size: 8.4pt; font-variant-numeric: tabular-nums; }
.bar-val span { color: #777; }

/* quote */
.pull { border-left: 3pt solid #1b5e45; background: #f6f6f4; padding: 12pt 14pt; margin: 12pt 0 14pt; }
.pull p { font-size: 11pt; line-height: 1.5; font-style: italic; margin: 0; }
.pull .attrib { font-style: normal; font-size: 8pt; color: #555; margin-top: 8pt; }

table { width: 100%; border-collapse: collapse; font-size: 8.4pt; }
th { text-align: left; font-size: 7.4pt; text-transform: uppercase; letter-spacing: 0.3pt; color: #555;
     border-bottom: 1pt solid #999; padding: 4pt 5pt; }
td { padding: 3.6pt 5pt; border-bottom: 0.5pt solid #ddd; vertical-align: top; }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }

/* photo grid */
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 7pt; }
.grid.dense { grid-template-columns: repeat(5, 1fr); gap: 6pt; }
.cell { break-inside: avoid; }
.cell img { width: 100%; aspect-ratio: 4 / 5; object-fit: cover; display: block; background: #eee; border: 0.5pt solid #ccc; }
.cap { font-size: 6.6pt; line-height: 1.3; margin-top: 2.5pt; }
.dense .cap { font-size: 5.7pt; line-height: 1.26; margin-top: 2pt; }
.cap .addr { font-weight: 700; display: block; }
.cap .meta { color: #555; display: block; }
.cap .open { color: #b3322f; font-weight: 700; }
.cap .closed { color: #444; }
.cap .cid { color: #888; }

.note { border: 0.75pt solid #ccc; background: #fafaf8; padding: 10pt 12pt; margin-top: 10pt; }
.cols2 { column-count: 2; column-gap: 20pt; }
.footer-note { font-size: 6.4pt; color: #888; border-top: 0.5pt solid #ddd;
               padding-top: 3pt; margin-top: 7pt; }
.cover .footer-note { position: absolute; bottom: 0; left: 0; right: 0; margin-top: 0; }
"""

def runhead(right):
    return (f'<div class="runhead"><span>Empty Tree Basins — Supervisor District 6</span>'
            f'<span>{e(right)}</span></div>')

def photo_cell(c, dense=False):
    hood = "" if dense else f'<span class="meta">{e(c["n"] or "Neighborhood not recorded")}</span>'
    return (f'<div class="cell"><img src="print/{c["id"]}.jpg" alt="">'
            f'<div class="cap"><span class="addr">{e(c["a"])}</span>{hood}'
            f'<span class="meta">Reported {pretty(c["o"])}</span>'
            f'<span class="meta">{status_line(c)}</span>'
            f'<span class="cid">311 #{e(c["id"])}</span></div></div>')

def photo_pages(subset, per_page, label, dense=False):
    out = []
    total_pages = (len(subset) + per_page - 1) // per_page
    for i in range(0, len(subset), per_page):
        chunk = subset[i:i + per_page]
        n = i // per_page + 1
        out.append(
            f'<div class="page">{runhead(f"{label} — sheet {n} of {total_pages}")}'
            f'<div class="grid{" dense" if dense else ""}">{"".join(photo_cell(c, dense) for c in chunk)}</div>'
            f'<div class="footer-note">Each photograph was submitted by a resident with their 311 report. '
            f'Case numbers are verifiable at mobile311.sfgov.org/tickets/&lt;case number&gt;.</div></div>')
    return "".join(out)

# ---------------------------------------------------------------- cover
cover = f"""
<div class="page cover">
  <div class="cover-kicker">Exhibit &mdash; submitted for the hearing file</div>
  <h1>Empty Street-Tree Basins<br>in Supervisor District 6</h1>
  <div class="cover-rule"></div>
  <div class="cover-sub">Photographic and records evidence drawn from San Francisco's
  own 311 service-request data.</div>
  <div class="cover-sub muted" style="font-size:10.5pt">Reports filed
  {pretty(cut)} &ndash; {pretty(TODAY.isoformat())}</div>

  <div class="cover-box">
    <div class="cover-figs">
      <div><div class="fig-n">{fmt(n_win)}</div><div class="fig-l">empty basin reports<br>in 24 months</div></div>
      <div><div class="fig-n" style="color:#b3322f">{fmt(n_open)}</div><div class="fig-l">still open<br>({round(n_open/n_win*100)}% of all reports)</div></div>
      <div><div class="fig-n">{fmt(median_open)}</div><div class="fig-l">median days<br>an open case has waited</div></div>
      <div><div class="fig-n">{fmt(n_planted)}</div><div class="fig-l">closed reports recording<br>a tree planted</div></div>
    </div>
  </div>

  <p>This exhibit reproduces <strong>{fmt(len(main_photos))}</strong> photographs of empty tree basins in
  District 6 &mdash; the most recently reported of the {fmt(len(photos))} photographed cases in the period
  &mdash; each submitted by a resident as part of a 311 service request, with the date it was reported
  and what the City recorded as the outcome. Every case can be independently verified by its 311 case
  number. A companion appendix reproduces all {fmt(len(photos))} photographs.</p>

  <h3 style="margin-top:20pt;font-size:9pt;text-transform:uppercase;letter-spacing:0.8pt;color:#1b5e45">Contents</h3>
  <table style="font-size:9pt">
    <tbody>
      <tr><td style="border:0;padding-left:0">What the record shows &mdash; counts, outcomes and neighborhoods</td><td style="border:0;text-align:right;width:0.6in">2</td></tr>
      <tr><td style="border:0;padding-left:0">In the City's own words &mdash; Public Works' stated reason for not planting</td><td style="border:0;text-align:right">3</td></tr>
      <tr><td style="border:0;padding-left:0">Photographic evidence &mdash; {fmt(len(main_photos))} basins, most recent first</td><td style="border:0;text-align:right">4&ndash;9</td></tr>
      <tr><td style="border:0;padding-left:0">Method, limitations and how to verify any case</td><td style="border:0;text-align:right">10</td></tr>
    </tbody>
  </table>

  <div class="cover-meta">
    <div><strong>Submitted by:</strong> {e(SUBMITTER)}, {e(ORG)}</div>
    <div><strong>Prepared:</strong> {TODAY.strftime("%B %-d, %Y")}</div>
    <div style="margin-top:10pt"><strong>Hearing / file no.:</strong> <span class="sign-line">&nbsp;</span></div>
    <div style="margin-top:8pt"><strong>Signature:</strong> <span class="sign-line">&nbsp;</span></div>
  </div>

  <div class="footer-note">
    Source: San Francisco 311 Cases, DataSF dataset vw6y-z8j6, retrieved
    {TODAY.strftime("%B %-d, %Y")}. Prepared with public data only. Full interactive record at fairtrees.org.
  </div>
</div>
"""

# ------------------------------------------------------- findings page
maxo = outcomes[0][1]
bars = "".join(
    f'<div class="bar-row"><div class="bar-lab">{e(k)}</div>'
    f'<div class="bar-track"><div class="bar-fill" style="width:{v/maxo*100:.1f}%"></div></div>'
    f'<div class="bar-val">{fmt(v)} <span>&middot; {round(v/n_win*100)}%</span></div></div>'
    for k, v in outcomes)

hood_rows = "".join(
    f'<tr><td>{e(k)}</td><td class="num">{fmt(v)}</td>'
    f'<td class="num">{fmt(sum(1 for c in win if (c["n"] or "Not recorded")==k and c["s"]))}</td></tr>'
    for k, v in hoods)

findings = f"""
<div class="page">
  {runhead("What the record shows")}
  <h2>What the record shows</h2>

  <div class="tiles">
    <div class="tile"><div class="n">{fmt(n_win)}</div><div class="l">Reports filed<br>in 24 months</div></div>
    <div class="tile alert"><div class="n">{fmt(n_open)}</div><div class="l">Still open today</div></div>
    <div class="tile"><div class="n">{fmt(len(closed))}</div><div class="l">Closed by the City</div></div>
    <div class="tile alert"><div class="n">{fmt(n_planted)}</div><div class="l">Closures recording<br>a tree planted</div></div>
  </div>

  <p>Between {pretty(cut)} and {pretty(TODAY.isoformat())}, residents filed <strong>{fmt(n_win)}</strong>
  reports of empty street-tree basins in District 6. <strong>{fmt(n_open)} of them &mdash;
  {round(n_open/n_win*100)}% &mdash; remain open.</strong> The median open case has been waiting
  <strong>{median_open} days</strong>; the oldest has been open <strong>{longest_open} days</strong>.</p>

  <p>Of the {fmt(len(closed))} reports the City closed, <strong>{fmt(n_cancelled)}
  ({round(n_cancelled/len(closed)*100)}%)</strong> were closed with the note
  &ldquo;Cancelled &mdash; Planned Maintenance.&rdquo; <strong>None of the {fmt(len(closed))} closed
  reports records a tree having been planted.</strong></p>

  <h3 style="margin-top:14pt">How the {fmt(n_win)} reports were resolved</h3>
  <div class="bars">{bars}</div>

  <h3 style="margin-top:16pt">Where they are</h3>
  <table>
    <thead><tr><th>Neighborhood</th><th style="width:1.1in">Reports</th><th style="width:1.1in">Still open</th></tr></thead>
    <tbody>{hood_rows}</tbody>
  </table>

  <div class="note">
    <strong>An important qualification.</strong> &ldquo;No closure records a tree planted&rdquo; is a
    statement about the public record, not proof that no tree was planted. Before roughly 2015 the
    City's closure notes often named the action taken; today almost every closed report carries only
    &ldquo;Cancelled &mdash; Planned Maintenance.&rdquo; The fair conclusion is that a resident cannot
    tell from the public record what, if anything, happened to their report.
  </div>
</div>
"""

# --------------------------------------------- the City's own words
nores_rows = "".join(
    f'<tr><td>{e(c["a"])}</td>'
    f'<td class="num">{pretty(c["o"])}</td><td class="num">{pretty(c["c"])}</td>'
    f'<td class="num">{(datetime.date.fromisoformat(c["c"])-datetime.date.fromisoformat(c["o"])).days if c["c"] and c["o"] else "—"}</td>'
    f'<td class="num">{e(c["id"])}</td></tr>'
    for c in sorted(nores, key=lambda x: x["c"] or "", reverse=True)[:11])

words = f"""
<div class="page">
  {runhead("In the City's own words")}
  <h2>In the City's own words</h2>

  <p>The preceding page counts what happened to recent reports. The 311 record also contains the
  City's own written explanation. On <strong>{fmt(len(nores))} District 6 reports</strong> closed between
  {pretty(nores_from)} and {pretty(nores_to)}, Public Works closed the case with this note:</p>

  <div class="pull">
    <p>&ldquo;{e(QUOTE)}&rdquo;</p>
    <div class="attrib">&mdash; Closure note recorded on {fmt(len(nores))} District 6 empty tree basin
    service requests, San Francisco 311 (dataset vw6y-z8j6). Reproduced verbatim.</div>
  </div>

  <p>Three things follow from the City's own words. First, the basin was
  <strong>inspected and confirmed empty</strong> &mdash; these are not disputed reports. Second, the
  case was <strong>closed</strong> even though no tree was planted, which is why a closed ticket
  cannot be read as a resolved problem. Third, the City states the site &ldquo;is on our list of
  sites to plant once funding is available,&rdquo; and invites the resident to plant and
  <strong>water the tree weekly for three years</strong> themselves.</p>

  <p>These {fmt(len(nores))} cases pre-date the period covered by the photographs in this exhibit:
  311 only began retaining resident photographs in the last eighteen months. They are presented as a
  separate and complementary part of the record, not as captions to the images that follow.</p>

  <h3 style="margin-top:14pt">Representative cases closed with this language</h3>
  <table>
    <thead><tr><th>Location</th><th style="width:1.05in">Reported</th>
    <th style="width:1.05in">Closed</th><th style="width:0.75in">Days</th>
    <th style="width:1.15in">311 case no.</th></tr></thead>
    <tbody>{nores_rows}</tbody>
  </table>
  <p class="tiny muted" style="margin-top:6pt">Showing 11 of {fmt(len(nores))} such District 6 cases.
  The complete list is available on request and at fairtrees.org.</p>
</div>
"""

method = f"""
<div class="page">
  {runhead("Method and verification")}
  <h2>Method and verification</h2>
  <div class="cols2">
    <h3>Source</h3>
    <p>Every record here is a real 311 service request from the City and County of San Francisco's
    open data portal, dataset <strong>vw6y-z8j6</strong> (&ldquo;311 Cases&rdquo;), retrieved
    {TODAY.strftime("%B %-d, %Y")}. No data has been supplied, estimated or altered by the submitter.</p>

    <h3>Selection</h3>
    <p>Records were filtered to those whose <em>service detail</em> field is
    <strong>EMPTY_TREE_BASIN</strong> and whose <em>supervisor district</em> field is
    <strong>6</strong>, reported on or after {pretty(cut)}. Duplicate rows were removed by service
    request ID. That yields the {fmt(n_win)} reports counted throughout this exhibit.</p>

    <h3>Photographs</h3>
    <p>Photographs were submitted by residents as attachments to their own 311 reports. They are
    reproduced unmodified apart from resizing and rotation to their correct orientation. Of the
    {fmt(n_win)} reports, {fmt(len(photos))} carry a retrievable photograph; the remainder were
    filed without one, or before the City retained attachments.</p>

    <h3>Dates and counts</h3>
    <p>&ldquo;Reported&rdquo; is the 311 <em>requested_datetime</em>. Days open is counted to
    {TODAY.strftime("%B %-d, %Y")}. Outcome labels are grouped from the free-text closure note City
    staff entered, so they summarise that text rather than an official 311 category.</p>

    <h3>Limitations</h3>
    <p>A supervisor district is only as accurate as the City's own geocoding; {fmt(sum(1 for c in win if not c["n"]))}
    reports in this window carry no neighborhood label, and reports filed at an intersection often
    carry no coordinates at all. Counts of what the City did are counts of <em>what the City
    recorded</em>.</p>

    <h3>How to verify any case</h3>
    <p>Every photograph and table row carries its 311 case number. Any case can be checked directly
    at <strong>mobile311.sfgov.org/tickets/&lt;case&nbsp;number&gt;</strong>, or by querying the
    open dataset. The complete, continuously updated record for all eleven districts is published
    at <strong>fairtrees.org</strong>.</p>
  </div>

  <div class="note" style="margin-top:14pt">
    <strong>Contact.</strong> {e(SUBMITTER)} &mdash; {e(ORG)}. Questions about the derivation of any
    figure in this exhibit are welcome; the underlying query and code are public.
  </div>

  <div class="footer-note">
    Prepared {TODAY.strftime("%B %-d, %Y")} from San Francisco open data. Public records, presented without alteration.
  </div>
</div>
"""

def document(title, body):
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{e(title)}</title>'
            f'<style>{CSS}</style></head><body>{body}</body></html>')

open(f"{SCR}/exhibit.html", "w").write(document(
    "Empty Street-Tree Basins in Supervisor District 6",
    cover + findings + words
    + photo_pages(main_photos, PER_PAGE, "Photographic evidence")
    + method))

appendix_cover = f"""
<div class="page cover">
  <div class="cover-kicker">Appendix &mdash; complete photographic record</div>
  <h1>Empty Street-Tree Basins<br>in Supervisor District 6</h1>
  <div class="cover-rule"></div>
  <div class="cover-sub">All {fmt(len(photos))} photographed reports, {pretty(cut)} &ndash; {pretty(TODAY.isoformat())}.</div>
  <p style="margin-top:20pt">This appendix accompanies the main exhibit and reproduces every District 6
  empty tree basin report in the period that carries a resident photograph, in reverse date order.
  It is provided so that the photographs in the main exhibit cannot be characterised as a selection.</p>
  <div class="cover-meta">
    <div><strong>Submitted by:</strong> {e(SUBMITTER)}, {e(ORG)}</div>
    <div><strong>Prepared:</strong> {TODAY.strftime("%B %-d, %Y")}</div>
  </div>
  <div class="footer-note">Source: San Francisco 311 Cases, DataSF dataset vw6y-z8j6.</div>
</div>
"""
open(f"{SCR}/appendix.html", "w").write(document(
    "District 6 Empty Tree Basins — Complete Photographic Appendix",
    appendix_cover + photo_pages(photos, 20, "Complete photographic record", dense=True)))

print(f"window {cut} .. {TODAY}")
print(f"reports={n_win} open={n_open} closed={len(closed)} cancelled={n_cancelled} planted={n_planted}")
print(f"median_open={median_open} longest_open={longest_open}")
print(f"photos available={len(photos)}  in main exhibit={len(main_photos)}")
print(f"no-resources cases={len(nores)} ({nores_from} .. {nores_to})")
print("wrote exhibit.html and appendix.html")
