"""
Place the Blue Hills intersection numbers that OpenStreetMap doesn't have, from the
park's own trail map (bluehills_data/blue-hills-trail-map-2020.pdf).

The PDF is drawn with real text and shapes: each four-digit number labels a small dark
dot at its intersection. The numbers OSM does have are reference points with a known
place on both the page and the ground; from them comes the page-to-map conversion
(a straight fit, then nudged by how far off nearby reference points are). Each missing
number's dot is converted, then moved onto the nearest OSM trail junction not already
numbered. A test on the known numbers (each hidden in turn) says how often that's right.

Writes bluehills_data/pdf_placed.json: {number: {"lonlat", "node" (OSM point, or null if no
junction was close enough), "moved_m"}}. Every one is only an estimate until someone at
the sign confirms it.
"""

import collections
import json
import math
import os
import re

import pymupdf

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"
DATA = os.path.join(PROJ, "bluehills_data")
PDF = os.path.join(DATA, "blue-hills-trail-map-2020.pdf")
DOT_FILL = (0.14, 0.12, 0.13)   # the dark intersection dots
LABEL_TO_DOT_PT = 25            # a label is this close to its dot on the page
RADIUS_M = 80                   # a junction this close to the converted dot can be it
NOT_INTERSECTIONS = {"1186", "1904"}   # the legend's example sign, and a date
M_LON, M_LAT = 82000, 111000   # meters per degree near 42 N (as in trailmap.dist_m)


def dist(a, b):
    return math.hypot((a[0] - b[0]) * M_LON, (a[1] - b[1]) * M_LAT)


def solve(A, b):
    """Least squares, by the normal equations"""
    n = len(A[0])
    M = [[sum(r[i] * r[j] for r in A) for j in range(n)] for i in range(n)]
    v = [sum(r[i] * y for r, y in zip(A, b)) for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i]))
        M[i], M[p], v[i], v[p] = M[p], M[i], v[p], v[i]
        for r in range(n):
            if r != i:
                f = M[r][i] / M[i][i]
                M[r] = [a - f * c for a, c in zip(M[r], M[i])]
                v[r] -= f * v[i]
    return [v[i] / M[i][i] for i in range(n)]


def page_dots():
    """{number: (x, y)} of each intersection's dot on the page"""
    page = pymupdf.open(PDF)[0]
    labels = collections.defaultdict(list)
    for x0, y0, x1, y1, w, *_ in page.get_text("words"):
        if re.fullmatch(r"\d{4}", w) and w not in NOT_INTERSECTIONS:
            labels[w].append(((x0 + x1) / 2, (y0 + y1) / 2))
    dots = []
    for d in page.get_drawings():
        r, f = d["rect"], d.get("fill") or ()
        if (d.get("type") == "f" and len(f) == 3 and max(abs(c - t) for c, t in zip(f, DOT_FILL)) < 0.03
                and 1.5 <= max(r.width, r.height) <= 6):
            dots.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
    # Each label takes the nearest dot, closest pairs first, each dot used once
    pairs = sorted((math.hypot(p[0] - q[0], p[1] - q[1]), n, k) for n, ps in labels.items() if len(ps) == 1
                   for p in ps for k, q in enumerate(dots) if math.hypot(p[0] - q[0], p[1] - q[1]) <= LABEL_TO_DOT_PT)
    taken_n, taken_d, at = set(), set(), {}
    for _, n, k in pairs:
        if n not in taken_n and k not in taken_d:
            taken_n.add(n)
            taken_d.add(k)
            at[n] = dots[k]
    return at, sorted(n for n in labels if n not in at)


def make_predictor(at, known, controls):
    """Page -> lon/lat: an affine fit on the controls, nudged by their nearby residuals"""
    A = [[at[n][0], at[n][1], 1] for n in controls]
    cx = solve(A, [known[n][0] for n in controls])
    cy = solve(A, [known[n][1] for n in controls])
    aff = lambda p: (cx[0] * p[0] + cx[1] * p[1] + cx[2], cy[0] * p[0] + cy[1] * p[1] + cy[2])
    ctl = [(aff(at[n]), (known[n][0] - aff(at[n])[0], known[n][1] - aff(at[n])[1])) for n in controls]

    def predict(p):
        g = aff(p)
        near = sorted(ctl, key=lambda c: dist(c[0], g))[:6]
        w = [1 / max(dist(c[0], g), 30) ** 2 for c in near]
        return (g[0] + sum(wi * c[1][0] for wi, c in zip(w, near)) / sum(w),
                g[1] + sum(wi * c[1][1] for wi, c in zip(w, near)) / sum(w))
    return predict


def main():
    els = json.load(open(os.path.join(DATA, "osm_trails.json")))
    numbered = {e["tags"]["ref"]: (e["lon"], e["lat"], e["id"]) for e in json.load(open(os.path.join(DATA, "osm_numbered.json")))}
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in els if e["type"] == "node"}
    use = collections.Counter()
    for w in (e for e in els if e["type"] == "way"):
        for k, n in enumerate(w["nodes"]):
            use[n] += 2 if k in (0, len(w["nodes"]) - 1) else 1
    junctions = {n: nodes[n] for n, c in use.items() if c >= 3}

    at, nodot = page_dots()
    known = {n: v[:2] for n, v in numbered.items()}
    controls = [n for n in at if n in known]
    print("%d numbers on the page with their dots (%d without: %s); %d also in OSM" % (len(at), len(nodot), nodot, len(controls)))

    # How well does it work? Hide each known number in turn
    right = 0
    for n in controls:
        pred = make_predictor(at, known, [m for m in controls if m != n])(at[n])
        cands = sorted((dist(pred, ll), j) for j, ll in junctions.items() if dist(pred, ll) <= RADIUS_M)
        right += bool(cands) and cands[0][1] == numbered[n][2]
    print("test on the known numbers: the nearest junction is right for %d of %d (%.0f%%)" % (right, len(controls), 100 * right / len(controls)))

    predict = make_predictor(at, known, controls)
    taken = {v[2] for v in numbered.values()}
    out = {}
    for n in sorted(m for m in at if m not in known):
        pred = predict(at[n])
        cands = sorted((dist(pred, ll), j) for j, ll in junctions.items() if dist(pred, ll) <= RADIUS_M and j not in taken)
        if cands:
            taken.add(cands[0][1])
            out[n] = {"lonlat": junctions[cands[0][1]], "node": cands[0][1], "moved_m": round(cands[0][0])}
        else:
            out[n] = {"lonlat": pred, "node": None, "moved_m": None}
    json.dump(out, open(os.path.join(DATA, "pdf_placed.json"), "w"), indent=1)
    on = sum(1 for v in out.values() if v["node"])
    print("Wrote pdf_placed.json: %d numbers, %d on a junction, %d left where the map puts them" % (len(out), on, len(out) - on))


if __name__ == "__main__":
    main()
