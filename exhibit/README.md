# Hearing exhibit generator

Builds a six-page printable PDF of empty street-tree basin reports for one
supervisor district, from the same San Francisco 311 data as the tracker.

```
1  Cover      the City's own closure note, then two headline figures
2  Findings   the mass closure, repeat reports, how closed cases were closed
3-5 Blocks    photographs grouped by street, in street-number order
6  Method     sources, limitations, how to verify any case
```

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
