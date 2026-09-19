#!/usr/bin/env python3
"""How large is District 6's tree deficit, and which way of saying so survives?

Prints three things:

  A. Trees per acre, by neighbourhood -- the framing to AVOID, computed so the
     failure is visible rather than discovered by a hostile reader.
  B. Canopy acres needed to reach the citywide rate -- the claim that rests on
     no assumption at all, and is therefore the one to lead with.
  C. The same gap converted to a tree count across a range of crown sizes, so
     the assumption is visible and is not carrying the argument.

Everything comes from the City's own published data. The only judgement in the
whole script is the crown-size range in C, which is why C is reported as a
range and the floor is the number to quote.

    python3 exhibit/canopy-deficit.py

The street-tree inventory is ~30MB; it is cached next to this file after the
first run. Pass --refresh to re-fetch it.
"""
import json, os, sys, csv, io, math, urllib.request, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BOUNDARIES = os.path.join(ROOT, "public", "data", "boundaries.json")
CANOPY = os.path.join(ROOT, "public", "data", "canopy.json")
CACHE = os.path.join(HERE, ".trees-cache.json")

# Street Tree List. Only the two coordinate columns are requested; the full
# table carries 30-odd fields that nothing here reads.
TREES_URL = ("https://data.sf.gov/resource/tkzw-k3nq.csv"
             "?$select=latitude,longitude&$limit=400000")

SQMI_PER_SQFT = 27878400.0
ACRES_PER_SQMI = 640.0
SQFT_PER_ACRE = 43560.0

# District 6's four core neighbourhoods. Treasure Island is also in District 6
# but is a separate island with its own planting history, and including it
# makes every per-acre figure meaningless.
CORE = ["South of Market", "Tenderloin", "Mission Bay",
        "Financial District/South Beach"]

# Dense, comparable, mature neighbourhoods -- the benchmark for what a street
# tree in this kind of fabric actually delivers.
BENCH = ["Hayes Valley", "Mission", "North Beach", "Western Addition",
         "Bernal Heights", "Noe Valley"]

# Crown area of a mature street tree. 600 sq ft is a 28ft crown, generous for a
# constrained sidewalk basin; 300 sq ft is roughly a street tree at 10-15 years.
CROWNS = [(600, "generous for a constrained sidewalk basin"),
          (433, "what District 6's comparable neighbours achieve today"),
          (300, "a street tree at 10 to 15 years old")]


# --------------------------------------------------------------- geometry
def rings_of(feature):
    g = feature["geometry"]
    return g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]


def bbox(polys):
    xs = [x for p in polys for x, y in p[0]]
    ys = [y for p in polys for x, y in p[0]]
    return min(xs), min(ys), max(xs), max(ys)


def in_ring(ring, x, y):
    inside = False
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[i - 1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
    return inside


def in_polys(polys, x, y):
    for poly in polys:
        if in_ring(poly[0], x, y) and not any(in_ring(h, x, y) for h in poly[1:]):
            return True
    return False


def area_sqmi(polys):
    """Planar shoelace with a cos(lat) correction on longitude.

    Good to a fraction of a percent at this latitude and over areas this size,
    and it needs no projection library. The check that it is right: the eleven
    districts sum to 46-47 square miles, against San Francisco's actual 46.9.
    """
    total = 0.0
    for poly in polys:
        for j, ring in enumerate(poly):
            lat0 = sum(p[1] for p in ring) / len(ring)
            k = math.cos(math.radians(lat0))
            s = 0.0
            for i in range(len(ring)):
                x1, y1 = ring[i - 1]
                x2, y2 = ring[i]
                s += (x1 * k) * y2 - (x2 * k) * y1
            # Degrees squared to square miles: 1 degree of latitude is 69.055
            # statute miles, and longitude is already scaled by k.
            a = abs(s) / 2.0 * (69.055 ** 2)
            total += a if j == 0 else -a   # interior rings are holes
    return total


def locate(index, x, y):
    for name, polys, (x0, y0, x1, y1) in index:
        if x0 <= x <= x1 and y0 <= y <= y1 and in_polys(polys, x, y):
            return name
    return None


# ------------------------------------------------------------------- data
def load_trees(refresh=False):
    if os.path.exists(CACHE) and not refresh:
        return json.load(open(CACHE))
    sys.stderr.write("fetching the street tree inventory (~30MB, once)... ")
    sys.stderr.flush()
    with urllib.request.urlopen(TREES_URL, timeout=300) as r:
        body = r.read().decode("utf-8", "replace")
    pts = []
    for row in csv.DictReader(io.StringIO(body)):
        try:
            pts.append((float(row["longitude"]), float(row["latitude"])))
        except (TypeError, ValueError, KeyError):
            continue          # a tree with no usable coordinate
    json.dump(pts, open(CACHE, "w"))
    sys.stderr.write(f"{len(pts):,} geocoded trees\n")
    return pts


def main():
    trees = [tuple(p) for p in load_trees("--refresh" in sys.argv)]
    b = json.load(open(BOUNDARIES))
    canopy = json.load(open(CANOPY))
    citywide = canopy["citywide"]

    hoods = [(f["properties"]["name"], rings_of(f)) for f in b["neighborhoods"]["features"]]
    index = [(n, p, bbox(p)) for n, p in hoods]
    areas = {n: area_sqmi(p) for n, p in hoods}

    counts = collections.Counter()
    for x, y in trees:
        n = locate(index, x, y)
        if n:
            counts[n] += 1

    acres = lambda n: areas[n] * ACRES_PER_SQMI
    city_trees = sum(counts.values())
    city_acres = sum(acres(n) for n in counts)
    city_rate = city_trees / city_acres

    w = "=" * 74
    print(w)
    print("A.  TREES PER ACRE -- the framing that loses, shown so you can see why")
    print(w)
    print(f"  citywide: {city_trees:,} inventoried trees over {city_acres:,.0f} acres"
          f" = {city_rate:.2f} per acre\n")
    print(f"  {'neighbourhood':<36}{'trees':>8}{'acres':>8}{'/acre':>8}   vs city")
    for n in CORE:
        r = counts[n] / acres(n)
        verdict = "ABOVE" if r > city_rate else "below"
        print(f"  {n:<36}{counts[n]:>8,}{acres(n):>8,.0f}{r:>8.2f}   {verdict}")
    print("\n  The citywide rate is dragged down by Golden Gate Park, the Presidio,")
    print("  McLaren Park and Lake Merced -- thousands of acres carrying almost")
    print("  nothing in the street-tree inventory. Do not build a claim on this.")

    print("\n" + w)
    print("B.  CANOPY ACRES NEEDED -- no assumption, nothing to attack")
    print(w)
    print(f"  citywide canopy {citywide}%   ({canopy['source'][:58]}...)\n")
    print(f"  {'neighbourhood':<36}{'canopy':>8}{'land ac':>9}{'has ac':>8}{'needs ac':>10}")
    need_sqft = 0.0
    land_total = 0.0
    for n in CORE:
        land = areas[n] * SQMI_PER_SQFT
        c = canopy["neighborhoods"][n]
        gap = land * (citywide - c) / 100.0
        need_sqft += gap
        land_total += land
        print(f"  {n:<36}{c:>7.1f}%{land/SQFT_PER_ACRE:>9,.0f}"
              f"{land*c/100/SQFT_PER_ACRE:>8,.0f}{gap/SQFT_PER_ACRE:>10,.0f}")
    print(f"  {'FOUR NEIGHBOURHOODS':<36}{'':>8}{land_total/SQFT_PER_ACRE:>9,.0f}"
          f"{'':>8}{need_sqft/SQFT_PER_ACRE:>10,.0f}")
    print(f"\n  {need_sqft/SQFT_PER_ACRE:,.0f} acres of new canopy"
          f" ({need_sqft/1e6:.1f} million sq ft), which is"
          f" {need_sqft/land_total*100:.0f}% of")
    print("  those neighbourhoods' entire land area. Golden Gate Park is 1,017 acres.")

    print("\n" + w)
    print("C.  CONVERTED TO TREES -- a range, because this step needs an assumption")
    print(w)
    for sqft, why in CROWNS:
        print(f"  {sqft:>4} sq ft per mature crown  ->  {need_sqft/sqft:>8,.0f} trees"
              f"   ({why})")
    print(f"\n  Quote the floor: about {need_sqft/max(c for c, _ in CROWNS)/1000:.0f},000 trees,"
          " and say 'allowed to mature'.")

    print("\n" + w)
    print("D.  WHY IT IS SHADE, NOT HEADCOUNT -- canopy delivered per tree")
    print(w)
    print(f"  {'neighbourhood':<36}{'trees/ac':>10}{'canopy':>9}{'sqft/tree':>11}")
    for group in (CORE, None, BENCH):
        if group is None:
            print("  " + "-" * 64)
            continue
        for n in group:
            c = canopy["neighborhoods"].get(n)
            if c is None or not counts[n]:
                continue
            land = areas[n] * SQMI_PER_SQFT
            print(f"  {n:<36}{counts[n]/acres(n):>10.2f}{c:>8.1f}%"
                  f"{land*c/100/counts[n]:>11,.0f}")
    print("\n  A District 6 tree delivers a fraction of what the same tree delivers")
    print("  four neighbourhoods away. That gap -- not the number of trees -- is")
    print("  the finding, and it is the one that holds up.")

    # Sanity check. If this drifts, the boundary file or the area maths moved.
    total_sqmi = sum(areas.values())
    print(f"\n  [check] neighbourhood areas sum to {total_sqmi:.1f} sq mi"
          f" (San Francisco is 46.9)")


if __name__ == "__main__":
    main()
