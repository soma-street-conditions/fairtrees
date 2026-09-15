# Hearing exhibit generator

Builds a printable PDF exhibit of empty street-tree basin reports for a single
supervisor district, from the same San Francisco 311 data as the tracker.

Two documents come out of it:

- **Exhibit** — 10 pages: cover, what the record shows, the City's own closure
  language, six sheets of photographs, and a method/verification page.
- **Appendix** — every photographed report in the period, 20 to a sheet, so the
  exhibit's selection cannot be characterised as cherry-picking.

## Running it

```bash
python3 exhibit/fetch-photos.py     # resumable; unwraps photos from the 311 portal
python3 exhibit/build-exhibit.py    # writes exhibit.html and appendix.html
node    exhibit/render.mjs          # renders both to PDF via headless Chromium
```

Paths at the top of each script point at a scratch directory; set them to
wherever you want the images and output to live. `DISTRICT` and `WINDOW_DAYS` in
`build-exhibit.py` select which district and how far back to go.

## Before filing anything

Every figure in the exhibit is computed from the data at build time rather than
typed in, but **re-verify against the live API before submitting**, because the
dataset changes daily. The counts that appear in the document are printed to the
terminal by `build-exhibit.py` for exactly that purpose.

The exhibit states one qualification prominently, and it should stay: "no closure
records a tree planted" describes the public record, not what physically
happened. Closure notes became far terser after about 2015. Overstating that
point is the fastest way to lose credibility in a hearing.
