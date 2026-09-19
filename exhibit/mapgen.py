"""Locator map: District 6 with neighbourhood structure and one dot per open basin."""
import json, math

# The document spends its one accent colour on District 6's bar, so the map is
# drawn entirely in ink and greys.
LAND      = "#F0F0F0"   # a shade off the #FAFAFA page, so the shape reads
LAND_EDGE = "#1A1A1A"
HAIR      = "#DCDCDC"   # neighbourhood hairlines inside the district
DOT       = "#1A1A1A"
HALO      = "#FAFAFA"
LABEL     = "#767676"


def district_map(open_cases, boundaries_path, district="6", width=560, pad=10, labels=4, fs=9.5):
    b = json.load(open(boundaries_path))
    dfeat = [f for f in b["districts"]["features"]
             if f["properties"]["id"] == district][0]
    geom = dfeat["geometry"]
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    pts = [(c["lng"], c["lat"]) for c in open_cases if c.get("lat") is not None]

    bbox = lambda r: (min(p[0] for p in r), min(p[1] for p in r),
                      max(p[0] for p in r), max(p[1] for p in r))

    # Fit to the polygon holding the dots: District 6 also contains Treasure
    # Island, and fitting the whole district would leave the frame mostly water.
    def holds(poly):
        x0, y0, x1, y1 = bbox(poly[0])
        return sum(1 for x, y in pts if x0 <= x <= x1 and y0 <= y <= y1)
    main = max(polys, key=holds)

    x0, y0, x1, y1 = bbox(main[0])
    k = math.cos(math.radians((y0 + y1) / 2))   # longitude degrees are shorter
    sx, sy = (x1 - x0) * k, (y1 - y0)
    height = round((width - 2 * pad) * (sy / sx) + 2 * pad)

    def proj(x, y):
        return (pad + (x - x0) * k / sx * (width - 2 * pad),
                pad + (y1 - y) / sy * (height - 2 * pad))

    def path(rings):
        out = []
        for r in rings:
            for i, (x, y) in enumerate(r):
                px, py = proj(x, y)
                out.append(f"{'M' if i == 0 else 'L'}{px:.1f},{py:.1f}")
            out.append("Z")
        return " ".join(out)

    inside = lambda x, y: x0 <= x <= x1 and y0 <= y <= y1

    def in_ring(ring, x, y):
        c = False
        for i in range(len(ring)):
            xi, yi = ring[i]; xj, yj = ring[i - 1]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                c = not c
        return c

    in_district = lambda x, y: in_ring(main[0], x, y) and not any(
        in_ring(h, x, y) for h in main[1:])
    district_path = path(main)

    # Neighbourhood outlines give the shape internal structure; clipped to the
    # district so they read as subdivisions rather than a second map.
    hairs = []
    for f in b["neighborhoods"]["features"]:
        g = f["geometry"]
        ps = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in ps:
            ring = poly[0]
            if any(inside(px, py) for px, py in ring):
                hairs.append(path([ring]))

    by_hood = {}
    for c in open_cases:
        if c.get("lat") is None:
            continue
        by_hood.setdefault(c.get("n") or "", []).append((c["lng"], c["lat"]))

    label_svg = ""
    for name, group in sorted(by_hood.items(), key=lambda kv: -len(kv[1]))[:labels]:
        if not name:
            continue
        cx = sum(p[0] for p in group) / len(group)
        cy = sum(p[1] for p in group) / len(group)
        lx, ly = proj(cx, cy)
        if not (pad + 22 < lx < width - pad - 22 and pad + 12 < ly < height - pad - 10):
            continue
        short = name.split("/")[0]
        # A filled plate rather than a stroked copy of the text underneath it:
        # paint-order is not honoured by every renderer, and two stacked text
        # elements duplicate the label in the PDF's text layer.
        w = len(short) * fs * 0.54 + 6
        label_svg += (f'<rect x="{lx - w / 2:.1f}" y="{ly - fs * 0.95:.1f}" '
                      f'width="{w:.1f}" height="{fs * 1.35:.1f}" rx="1.5" '
                      f'fill="#FAFAFA" fill-opacity="0.85"/>'
                      f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="{fs}" text-anchor="middle" '
                      f'font-family="Source Sans 3,Helvetica,Arial,sans-serif" fill="{LABEL}" '
                      f'font-weight="bold">{short}</text>')

    hair_paths = "".join(f'<path d="{h}"/>' for h in hairs)
    dots = "".join(f'<circle cx="{proj(x,y)[0]:.1f}" cy="{proj(x,y)[1]:.1f}" r="2.7"/>'
                   for x, y in pts)

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
        f'<defs><clipPath id="d{district}"><path d="{district_path}"/></clipPath></defs>'
        f'<path d="{district_path}" fill="{LAND}"/>'
        f'<g clip-path="url(#d{district})" fill="none" stroke="{HAIR}" stroke-width="0.6">'
        f'{hair_paths}</g>'
        f'<g clip-path="url(#d{district})">{label_svg}</g>'
        f'<path d="{district_path}" fill="none" stroke="{LAND_EDGE}" stroke-width="1.1" '
        f'stroke-linejoin="round"/>'
        f'<g fill="{DOT}" fill-opacity="0.9" stroke="{HALO}" stroke-width="0.8">{dots}</g>'
        f'</svg>')
