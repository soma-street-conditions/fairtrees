# Hearing exhibit generator

Builds a twelve-page printable PDF of empty street-tree basin reports for one
supervisor district, from the same San Francisco 311 data as the tracker.

```
1   Cover       the City's own closure note, a marked-but-uncut basin beside
                it, and three headline figures
2   Sites       the "no room for trees" rebuttal, four context photographs
3   Findings    the mass closure, repeat reports, the locator map, how
                closed cases were closed
4   Comparison  all eleven districts as a bar chart, with the table beneath
5-12 Blocks     photographs grouped by street, up to twelve to a page
```

There is no method page. Source, date range, dataset, authorship and how to
verify a case all sit on the cover, and the document ends on evidence rather
than on housekeeping. One sentence has to survive that cut, on the comparison
page: that the district is derived from coordinates because the 311 field is
stale. Without it the figures do not reproduce — a reader who queries the feed
directly gets a larger District 6 and concludes the exhibit is wrong.

## Running it

```bash
python3 exhibit/fetch-photos.py     # resumable; unwraps photos from the 311 portal
python3 exhibit/build-exhibit.py    # writes exhibit_v2.html, prints every figure it used
node    exhibit/render.mjs          # renders to PDF via headless Chromium

python3 exhibit/canopy-deficit.py   # the canopy argument, separately
```

Paths at the top of each script point at a scratch directory; set them to
wherever the images and output should live.

## Why it is shaped this way

**Lead with the closure note.** The strongest thing in the data is the City's own
sentence closing a confirmed-empty basin and inviting the resident to plant and
water the tree themselves for three years. It carries the argument better than
any statistic, and it cannot be argued with.

**Group photographs by block, not by date.** A date-ordered grid reads as a list;
a street with fourteen open basins on it reads as a street the City stopped
maintaining. Pick the blocks per district — `block()` takes a street name, and
the clusters worth using are found by grouping the window by street and sorting
by how many are still open.

**No appendix.** Fifteen pages of thumbnails nobody opens makes a filing feel
auto-generated. The completeness objection is answered in one sentence in the
method section: the full photographic set is published on the site and available
on request.

**One typeface, two weights, one accent colour.** Source Sans 3 rather than the
site's Montserrat: at 10.5pt in a dense document a geometric display face goes
wide and loose, and the brand link is carried by the paper colour instead. The
green is spent on section headings and the three cover figures; the coral
appears exactly once in the document, on District 6's bar. A document that uses
colour once reads as confident; one that uses it throughout reads as agitated,
and an earlier draft set "Open 183 days" in red sixty times over.

**No rules under headings, and no red anywhere.** A horizontal line under every
section head is a report convention that ages the document. Weight and the space
above do that work. Days-open figures are bold ink, not an error state.

**Abbreviate the dates in captions.** "Reported 26 December 2025" wraps in a
four-across grid, which sets every row to a different height and makes the page
look ragged. `26 Dec 2025 · open 266 days` on one line keeps the grid locked.

**Photograph pages carry open cases only, and one photograph per address.**
Four rules, enforced by assertions at the end of the build rather than by
care:

- *Open only.* A closed case on a photograph page hands the department an
  opening — "that case was closed, we handled it" — and the argument about what
  a closure note actually means belongs on page 3, where it is framed properly.
- *At least 30 days open.* A report filed last week is not evidence that anyone
  has been ignored, and printing one invites exactly the wrong response.
- *One photograph per address.* Three frames of 346 9th Street reads as
  padding, and padding is the one real risk of running long. Where an address
  carries several cases, the longest-waiting one is shown.
- *No address on two pages.* The "reported again" page has first claim on its
  cases; the street pages skip those addresses. Reserved by address, not by
  case id, since the same basin is often carried by several cases.

A page therefore holds *up to* twelve, not exactly twelve. Say what is on the
page — "All eleven here are still open" — and never let a count and its spelled
form drift apart ("12 of the twelve shown here" was a template filling both
slots).

**Four across, up to twelve to a page.** At five across the basin — the thing the
reader is meant to look at — stops being legible. Four fits three rows at 0.9in
margins, so a photo page carries twelve and the lede says so.

**Put a photograph on page 1, and the rebuttal on page 2.** Attention is highest
on the first page and falls off fast, so neither should be spent on prose. The
photograph makes the document identifiable in two seconds; the rebuttal answers
"the streets are too narrow" while the reader is still forming the objection
rather than after they have settled it. Both were originally later in the
document, and both were wasted there.

**One of the three cover figures has to be relative.** Absolute counts tell a
supervisor who does not know the district nothing. The share of the city's open
backlog sitting in this one district, set against the share of reports it filed,
is the only figure on the cover that can be acted on without further reading.

**Show the district comparison as a sorted chart, and leave the supervisors'
names out.** A table makes a reader search for the finding; a chart sorted by
share-still-open hands it to them, and the counts and medians survive as labels,
so nothing is lost. Names invite each member to look up their own row instead of
reading the distribution, and hand a chair with a backlog of their own a way to
make the hearing about that instead.

**Keep the headline figures unattackable.** Put counts that cannot be
re-characterised on the cover — still open, median wait. Anything needing a
paragraph of qualification belongs in the body, stated narrowly, with the
qualification attached.

**Answer the stock objections with the City's own records.** "There is no room"
and "the streets are too narrow" are answered by the fact that half the reported
empty basins sit on the district's widest thoroughfares. That is computed, not
asserted. The context photographs on that page are the submitter's own rather
than 311 attachments, so their captions carry a location and no case number;
never caption them in a way that implies they came from a service request.

**Give the numbers scale.** A count on its own tells a supervisor nothing: 151
open and a 194-day median only mean something beside the other ten districts.
The comparison table is computed from the same query for every district, so it
cannot be waved away as a different method applied to someone else's ward.

**Geocode the intersections.** About a third of reports are filed at an
intersection and arrive from 311 with no coordinates, so they cannot be placed
in a district or drawn on a map. The City's centreline file (`gmfx-8h6i`) lists
every node with the streets meeting it; matching both named streets recovers the
position. Note that numbered streets are zero-padded there — 8th St is `08TH ST`.

**Never trust the 311 district field.** It still carries the pre-2022 lines, so
it files parts of the Tenderloin under District 6. `build-data.mjs` assigns every
geocoded report from its coordinates against the City's current boundary file,
in both directions. Getting this wrong in a filing about one district would be
fatal: a staffer who maps the dots finds basins attributed to a district that no
longer contains them. Reports the feed never geocoded keep the old label and are
reported separately rather than counted.

## An open case is not an empty basin

This is the document's one real vulnerability, and it has already bitten once.
1532 Harrison St was photographed as an empty basin, its 311 cases are still
open, and trees have since been planted there. The address sits in `WITHHELD` in
`build-exhibit.py` and is kept off every photograph page.

Cross-check every planting list you can get against `WITHHELD` before filing.
Friends of the Urban Forest's SOMA West CBD list (45 trees, planted 18 April
2026, kept here as `fuf-soma-west-2026-04.json`) added three more addresses.
Match on exact street address, not proximity: a tree 30 metres away is a
different basin on the same block, and withholding those would weaken the
document for nothing.

The document's claim is that these cases are "still open," which a reader takes
to mean the basins are still empty. If a tree was planted while the case stayed
open, open status does not prove an empty basin, and anyone who finds a second
example can use it against the whole exhibit. Roughly 110 sites are now shown.
Walking them and confirming each basin is still empty would turn the weakest
part of the document into its strongest claim — a sentence no one else at the
hearing can make. **Do not write that sentence until the walk is actually
done.**

## Before filing anything

Every figure is computed at build time rather than typed in, and printed to the
terminal when you build. **Re-verify against the live API before submitting** —
the dataset changes daily, and a stale number in a public record is not
recoverable.

Two qualifications in the document should stay. "None record a tree having been
planted" describes the public record, not the ground: closure notes became far
terser after about 2015. And district and neighborhood assignment is the City's
own geocoding, not the author's. Overstating either is the fastest way to lose a
hearing.

**Keep the register plain.** Two habits crept in and were removed: the
"it is not X, it is Y" construction, which reads as a formula once you notice it
repeating, and self-justifying lines like "no figure has been estimated or
supplied by the author". Say what the thing is. "Every figure comes from the
City's own open data" does the same work without sounding defensive. Headings
should carry the finding — "Three in five reports are still open", not "What
the record shows".

**Lead with what, not when.** The cover used to open with a two-year date range,
which invites a reader to dismiss the data as old. The window is a strength, it
shows duration, but it belongs in the attribution line rather than third from
the top. The cover says "Open cases as of <date>" instead.

**Check every claim against the frame beneath it.** The page 2 footer once said
the City "has already cut thousands of basins here, and has marked out where the
next ones should go" — directly under a photograph of spray paint on uncut
pavement. Spray paint is not a cut basin.

**Closure reasons are rewritten, not truncated.** The raw 311 strings run past
the caption box and stop mid-word ("cancelled — planned ma"). `SHORT_OUTCOME`
maps them; add to it rather than slicing.

**Every case number is a live link, so check they resolve.** The exhibit is
filed as a PDF that others open and click, and Chromium turns each absolute
`href` into a real PDF link annotation. `https://mobile311.sfgov.org/tickets/<id>`
returns 200 for a valid case and 404 for an invalid one, so the whole set can be
checked in one pass before filing:

```bash
python3 -c "import re;print('\n'.join(sorted(set(re.findall(r'print/(\d+)\.jpg',open('exhibit_v2.html').read())))))" \
  | xargs -P 6 -I{} sh -c 'printf "%s %s\n" {} "$(curl -sSL -o /dev/null -w "%{http_code}" https://mobile311.sfgov.org/tickets/{})"' \
  | awk '$2 != 200'
```

That should print nothing. A filing full of dead links to the City's own records
would undo the point of citing them.

Do not put an uncited statistic in a filing. If a canopy percentage or similar is
wanted, carry its source with it.

`canopy-deficit.py` is the other half of the argument and deliberately separate
from the exhibit: the hearing document is about 151 confirmed-empty basins, and
the canopy deficit belongs in a covering letter. Read its own header before
using its numbers. The short version is that **the tree-count framing loses** —
three of District 6's four core neighbourhoods have more inventoried trees per
acre than the citywide average, because that average includes Golden Gate Park
and the Presidio. The defensible claim is canopy area, which needs no
assumption; the conversion to a tree count does, so it is reported as a range
and the floor is the figure to quote.

Two traps this document has already fallen into, worth re-checking each build.
The district median is the *second*-longest in the city; the longest belongs to a
district with eight open cases. State that outright rather than caveating it, or
someone repeats "District 6 has the longest waits" from the dais and is wrong.
And look at every photograph at the size it will print: two China Basin basins
are so long-neglected that wild fennel has filled them, and at thumbnail size
they read as planted trees unless the caption says otherwise.
