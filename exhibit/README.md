# Hearing exhibit generator

Builds a six-page printable PDF of empty street-tree basin reports for one
supervisor district, from the same San Francisco 311 data as the tracker.

```
1  Cover       the City's own closure note, then two headline figures
2  Findings    the mass closure, repeat reports, how closed cases were closed
3  Comparison  all eleven districts, a locator map, neighbourhoods
4-6 Blocks     photographs grouped by street, in street-number order
7  Sites       the "no room for trees" rebuttal, with context photographs
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

Do not put an uncited statistic in a filing. If a canopy percentage or similar is
wanted, carry its source with it.
