# District 6's tree deficit: the number, and how it was derived

Reference record for anyone — person or model — writing FairTrees advocacy
material. Everything here is reproducible by running
`python3 exhibit/canopy-deficit.py`, which prints every figure below.

Last computed **19 September 2026** against the live City datasets. The
datasets change; re-run before filing.

---

## 1. The number

> **District 6's four core neighborhoods are missing 192 acres of tree canopy
> — 8.4 million square feet — relative to the citywide average.**
>
> **Converting that to trees, at a generous 600 sq ft of crown per mature
> street tree, is about 14,000 trees.** At 433 sq ft, what comparable dense
> neighborhoods actually achieve, it is 19,312. At 300 sq ft, a street tree at
> 10–15 years old, it is 27,874.

**Quote 14,000 as the floor.** It survives every plausible assumption.

Always attach **"and allowed to mature."** 14,000 trees planted tomorrow
deliver 14,000 saplings' worth of shade; the canopy arrives in roughly twenty
years. Conceding the timeline pre-empts the obvious rebuttal.

For scale: the 151 confirmed-empty basins in the hearing exhibit are **under 2%
of the gap**.

---

## 2. Read this before using any tree-count statistic

**Do not claim District 6 has too few trees. It does not, and the City's own
inventory proves it does not.**

| Neighborhood | Inventoried trees / acre | Canopy |
|---|---|---|
| Tenderloin | **6.22** | 2.6% |
| Financial District / South Beach | **6.03** | 4.5% |
| South of Market | **5.53** | 2.7% |
| Mission Bay | 4.10 | 3.2% |
| **San Francisco average** | **4.37** | **12.8%** |

Three of the four core neighborhoods sit *above* the citywide rate. The citywide
average is depressed by Golden Gate Park, the Presidio, McLaren Park and Lake
Merced — thousands of acres carrying almost nothing in the street-tree
inventory. Any staffer with `tkzw-k3nq` can demonstrate this in minutes.

Trees per **street mile** fails the same way. District 6 looks low in aggregate
(8,864 trees over ~100 street miles, 89/mile, third-lowest of eleven districts),
but the Tenderloin alone runs about 134 trees per mile — above the median
district. One counterexample inside our own district discredits the filing.

**The real finding is stronger.** District 6 has the trees. It does not have the
canopy those trees are supposed to produce:

| Neighborhood | Trees / acre | Canopy | **Sq ft of canopy per tree** |
|---|---|---|---|
| Tenderloin | 6.22 | 2.6% | **182** |
| South of Market | 5.53 | 2.7% | **213** |
| Financial District / South Beach | 6.03 | 4.5% | **325** |
| Mission Bay | 4.10 | 3.2% | **340** |
| Hayes Valley | 11.13 | 9.0% | 352 |
| Mission | 7.74 | 6.9% | 389 |
| North Beach | 7.32 | 7.8% | 464 |
| Western Addition | 9.59 | 11.6% | 527 |
| Bernal Heights | 7.56 | 11.9% | 686 |
| Noe Valley | 8.53 | 15.7% | 802 |

A Tenderloin tree throws roughly **a quarter** the crown of a Noe Valley tree.
That is young stock, constrained basins, and no private yards or parks
contributing anything alongside the street.

The most instructive case is **Inner Sunset: 3.74 trees per acre — the
*lowest* density in the comparison set — and 22.0% canopy**, the highest. Its
canopy is private, in back gardens. Density does not predict canopy. This is
why the argument must rest on canopy per unit of land, not on headcount.

---

## 3. Data sources

| Input | Source | Identifier |
|---|---|---|
| Canopy cover by neighborhood | USDA Forest Service & CAL FIRE, *California Urban Tree Canopy Viewer: 2022 Canopy Cover and Change Analysis (2018–2022)*, released April 2025 | stored at `public/data/canopy.json`, 40 neighborhoods, citywide 12.8% |
| Street tree inventory | DataSF Street Tree List | `tkzw-k3nq` (131,720 rows with usable coordinates; 131,499 fall inside a neighborhood polygon) |
| Neighborhood boundaries | DataSF Analysis Neighborhoods | `j2bu-swwd`, simplified into `public/data/boundaries.json` |
| Supervisor districts | DataSF Current Supervisor Districts | `f2zs-jevy` |
| Empty basin reports | DataSF 311 Cases | `vw6y-z8j6` |
| Street centerlines (density cross-check only) | DataSF | `pu5n-qu5c` / `3psu-pn9h` |

The canopy dataset is **federal**, not municipal. That matters rhetorically: it
is not a number the City can dispute as ours, and it is not a number we
produced.

---

## 4. Computation, step by step

### 4.1 Assigning trees to neighborhoods

Each inventory row carries a latitude/longitude. Every tree is assigned by
**point-in-polygon** (ray casting, with a bounding-box prefilter for speed)
against the City's own neighborhood boundaries, including interior-ring holes.
Rows without a usable coordinate are dropped, not imputed.

We do **not** use any neighborhood or district label carried in a City feed.
The 311 district field still reflects the **pre-2022 district lines** and files
parts of the Tenderloin under District 6. Everything is derived from
coordinates.

### 4.2 Land area

Planar shoelace on the boundary rings, with longitude scaled by `cos(latitude)`
at each ring's mean latitude, converted at 69.055 statute miles per degree of
latitude. Interior rings are subtracted as holes.

**Validation:** the 41 neighborhood polygons sum to **47.1 square miles**
against San Francisco's actual land area of **46.9** — 0.4% high, consistent
with boundary simplification. The script prints this check on every run. If it
drifts, the boundary file or the area maths has moved and the figures should not
be used.

### 4.3 Canopy acres required

For each neighborhood:

```
acres_needed = land_area × (citywide_canopy_pct − neighborhood_canopy_pct) / 100
```

| Neighborhood | Canopy | Land (ac) | Canopy today (ac) | **Needed (ac)** |
|---|---|---|---|---|
| South of Market | 2.7% | 563 | 15 | 57 |
| Tenderloin | 2.6% | 249 | 6 | 25 |
| Mission Bay | 3.2% | 521 | 17 | 50 |
| Financial District / South Beach | 4.5% | 720 | 32 | 60 |
| **Total** | — | **2,052** | **70** | **192** |

192 acres is **9% of those neighborhoods' entire land area**, to be grown along
their sidewalks. Golden Gate Park is 1,017 acres, for scale.

**This step involves no modelling.** It is a published canopy percentage
multiplied by a measured land area. There is nothing in it to attack except the
boundary file and the canopy dataset, both of which are the City's and the
federal government's respectively.

### 4.4 Converting to a tree count — the one assumption

```
trees = 8,360,000 sq ft ÷ assumed_crown_area
```

| Assumed mature crown | Basis | Trees |
|---|---|---|
| 600 sq ft | ~28 ft crown; generous for a constrained sidewalk basin | **13,937** |
| 433 sq ft | Observed canopy-per-tree in Mission, Hayes Valley, Western Addition, North Beach | 19,312 |
| 300 sq ft | A street tree at 10–15 years old | 27,874 |

State the conversion out loud as a separate step so the assumption is visible
and is not carrying the argument. The deficit stays in five figures across the
entire plausible range, which is the actual point.

---

## 5. Known weaknesses

Anticipate these; do not wait to be shown them.

1. **The 433 sq ft benchmark is biased upward.** Benchmark neighborhoods have
   back-yard trees that never enter the street-tree inventory, which inflates
   their canopy-per-*inventoried*-tree. This is the main reason to lead with the
   600 sq ft floor. It is also why the canopy-per-tree table in §2 overstates
   the benchmark neighborhoods' street trees specifically — the *direction* of
   the finding holds regardless, but the magnitude is soft.

2. **Canopy measures all canopy, the inventory measures street trees.** The two
   datasets have different denominators by construction. This is fine for §4.3,
   which never divides one by the other, but §2's per-tree figures should be
   described as "canopy per inventoried tree," not "crown size."

3. **Boundary simplification** introduces ~0.4% area error (see §4.2). Immaterial
   at this precision; disclose it if pressed.

4. **Canopy data is 2022**, published 2025. Plantings since are not reflected.
   This cuts slightly against us and should be conceded rather than hidden.

5. **Treasure Island is in District 6** but is excluded from the four-neighborhood
   figures. It is a separate island with its own planting history and including
   it distorts every per-acre number. Say "District 6's four core neighborhoods,"
   not "District 6," whenever quoting the 192 acres.

6. **"Citywide average" is a floor, not a goal.** Reaching 12.8% would still
   leave these neighborhoods below the City's own Urban Forest Plan ambitions.
   The 192 acres is the gap to *average*, which makes it a conservative ask.

---

## 6. Prepared rebuttals

**"District 6 already has more street trees per acre than the city average."**
Correct, and it is the point. The district has the trees and not the canopy. The
citywide density average includes Golden Gate Park and the Presidio, where
almost nothing is in the street-tree inventory — density is the wrong measure in
both directions. Canopy is what the City's own Urban Forest Plan sets targets
against.

**"Your 433 sq ft per tree is inflated."**
It may be, for the reason in §5.1. That is why the floor figure uses 600 sq ft,
and the deficit is still about 14,000 trees.

**"SoMa is industrial; you cannot compare it to Noe Valley."**
It *was* industrial. It is now one of the fastest-growing residential
neighborhoods in San Francisco. The comparison set here is deliberately dense
and urban — Hayes Valley, the Mission, Western Addition, North Beach — and every
one of them clears 6.9%.

**"Trees won't survive there anyway."**
Then the City should say so in writing, because it is currently closing
confirmed-empty-basin cases with a note saying it lacks *resources*, not that
the sites are unsuitable. See the hearing exhibit.

---

## 7. Reproducing

```bash
python3 exhibit/canopy-deficit.py            # ~30MB fetch on first run, then cached
python3 exhibit/canopy-deficit.py --refresh  # re-fetch the inventory
```

Prints four sections: (A) the trees-per-acre framing that loses, shown
deliberately so it is not reached for by accident; (B) canopy acres needed;
(C) the conversion to trees across the assumption range; (D) canopy delivered
per tree. Ends with the 46.9 sq mi validation check.

---

## 8. One-paragraph version

> South of Market has 2.7% tree canopy and the Tenderloin 2.6%, against 12.8%
> citywide — roughly one-fifth the citywide rate. Closing that gap across
> District 6's four core neighborhoods requires 192 acres of new tree canopy:
> 8.4 million square feet, or nine percent of those neighborhoods' entire land
> area. At a generous 600 square feet of crown for a mature street tree, that is
> about 14,000 trees, planted and allowed to mature. The City has confirmed 151
> basins in District 6 empty and told residents it has no resources to fill them;
> filling every one of them closes under 2% of the gap.
