"""
The Daniels Road blazes, from the Saratoga Mountain Bike Association's trail map
(saratoga_data/SMBA_DanielsRd_Map.pdf): the DEC trails, drawn in red, blue and yellow,
are blazed those colors on the ground. Its brown singletrack and black trails may not be,
but the map shows them in those colors too, as if they were. Writes saratoga_data/blazes.json, {trail id: [[blaze, from m, to m, 0]]},
which build_saratoga.py puts on the trails.

Each label on the map is printed in its trail's color, so a trail OpenStreetMap names
takes its label's blaze, the whole way. The map is dense with trails closer together than
it can be placed, so where OpenStreetMap has no name, only a stretch clearly drawn in one
color (most of it, and no other) is taken as blazed.

The map is placed on the ground by its trail names (each label beside the OpenStreetMap
trail of that name) and then its trail lines (saratoga_data/sara_fit.py), corrected
locally by how far its lines nearby are from ours. Then, as for Upper Charles
(uc_blazes.py): only what shows counts, and each stretch between intersections is judged
whole.

Run build_saratoga.py first (it writes saratoga_data/built.json, the trails to match),
then this, then build_saratoga.py again.
"""

import json
import os
import sys
from collections import defaultdict

import numpy as np
import pymupdf

import uc_blazes as U

PROJ = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(PROJ, "saratoga_data")
sys.path.insert(0, DATA)
import sara_fit as F   # noqa: E402

COLORS = {"red": (0.9, 0.0, 0.0), "blue": (0.0, 0.36, 0.9), "yellow": (1.0, 1.0, 0.0),
          "brown": (0.54, 0.35, 0.27), "black": (0.0, 0.0, 0.0)}
U.BLAZE_COLORS = list(COLORS)   # uc_blazes' stretch helpers, with these colors
BLAZE_WIDTH = 1.5
SHIFT_SAMPLE_M, SHIFT_RADIUS_M = 40, 100
ON_TRAIL_M = 15


TEXT_COLORS = {"red": 0xe60000, "blue": 0x005ce6, "yellow": 0xe6e600, "brown": 0x895a44, "black": 0x000000}
CLEAR_SHARE = 0.6   # an unnamed stretch is blazed if one color covers this much of it, and no other


def norm(name):
    """Names compared without spaces, punctuation, or a trailing number ("Main Trail 2")"""
    whole = "".join(ch for ch in name.lower() if ch.isalnum())
    return whole.rstrip("0123456789") or whole   # ...but a trail named just "107" keeps it


def label_blazes(page):
    """{normalized trail name: blaze}, from the labels' text colors"""
    out = {}
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for sp in l["spans"]:
                k = next((c for c, v in TEXT_COLORS.items() if sp["color"] == v), None)
                if k and norm(sp["text"]):
                    out[norm(sp["text"])] = k
    return out


def blaze_of(c):
    return next((k for k, v in COLORS.items() if F.close(c, v, 0.05)), None)


def main():
    os.chdir(DATA)
    built = json.load(open("built.json", encoding="utf-8"))
    feats = built["trails"]
    trails = U.Trails(feats)
    page = pymupdf.open(F.PDF)[0]
    T = F.fit(verbose=False)

    def to_m(x, y):   # page point -> the map app's meters (uc_blazes.m)
        gx, gy = np.array([x, y, 1]) @ T
        return np.array(U.m(*F.ll(gx, gy)))

    # Local correction from the map's own trail lines
    g, dv = [], []
    for d in page.get_drawings():
        for c, w in F.TRAIL_STROKES:
            if F.close(d.get("color"), c) and abs((d.get("width") or 0) - w) < 0.05:
                for x, y in F.samples(d, 4):
                    p = to_m(x, y)
                    dist, _, _, q = trails.nearest(p)
                    if dist < SHIFT_SAMPLE_M:
                        g.append(p)
                        dv.append((q[0] - p[0], q[1] - p[1]))
    g, dv = np.array(g), np.array(dv)

    def shift(p):
        near = np.hypot(g[:, 0] - p[0], g[:, 1] - p[1]) < SHIFT_RADIUS_M
        return (p[0] + np.median(dv[near, 0]), p[1] + np.median(dv[near, 1])) if near.sum() >= 5 else tuple(p)

    # The blaze strokes, less what's painted over
    pts, cols, widths, order = [], [], [], []
    for i, d in enumerate(page.get_drawings()):
        k = blaze_of(d.get("color"))
        if k and abs((d.get("width") or 0) - BLAZE_WIDTH) < 0.05:
            for p in F.samples(d, 1.0):
                pts.append(p); cols.append(k); widths.append(d["width"]); order.append(i)
    P, W, O = np.array(pts), np.array(widths), np.array(order)
    C = np.array([list(COLORS).index(c) for c in cols])
    found = defaultdict(lambda: defaultdict(list))
    hidden = 0
    for k in range(len(P)):
        later = (O > O[k]) & (C != C[k])
        if (np.hypot(P[later, 0] - P[k, 0], P[later, 1] - P[k, 1]) < W[later] / 2).any():
            hidden += 1
            continue
        dist, ti, at, _ = trails.nearest(shift(to_m(*P[k])))
        if dist < ON_TRAIL_M:
            found[ti][cols[k]].append(at)
    print("Blaze strokes: %d points, %d painted over" % (len(P), hidden))

    stops = defaultdict(list)
    names = defaultdict(list)
    for f in built["ints"]:
        for ti, at in trails.through(U.m(*f["geometry"]["coordinates"]), 12):
            stops[ti].append(at)
            if not f["properties"].get("junction"):
                names[ti].append((at, f["properties"]["label"]))
    by_label = label_blazes(page)
    print("Labels: " + ", ".join("%s %s" % kv for kv in sorted(by_label.items())))
    out = {}
    for ti, f in enumerate(feats):
        name = f["properties"]["name"]
        length = trails.lines[ti][1][-1]
        # (either name can say more than the other: "Backstretch (Lucy's Point)", "Rogue One")
        n = norm(name) if name else ""
        hit = n if n in by_label else max((k for k in by_label if len(k) >= 5 and len(n) >= 5 and
                                           (n.startswith(k) or k.startswith(n))), key=len, default=None)
        if hit:
            out[f["properties"]["id"]] = [[by_label[hit], 0, round(length, 1), 0]]
        elif not name and not f["properties"].get("road"):
            rs = []
            for a, b in U.edges(stops[ti], length):
                bins = defaultdict(lambda: defaultdict(int))
                for c, ats in found[ti].items():
                    for at in ats:
                        if a <= at <= b:
                            bins[int((at - a) // 5)][c] += 1
                n_bins = max(1, int((b - a) // 5) + 1)
                share = defaultdict(float)
                for k in bins:
                    share[max(bins[k], key=bins[k].get)] += 1 / n_bins
                top = max(share, key=share.get) if share else None
                if top and share[top] >= CLEAR_SHARE and all(v < 0.15 for c, v in share.items() if c != top) and b - a >= U.MIN_RUN_M:
                    rs.append([top, round(a, 1), round(b, 1), 0])
            if rs:
                out[f["properties"]["id"]] = U.merge_runs(rs)
    total = defaultdict(float)
    for tid, rs in sorted(out.items(), key=lambda kv: feats[[f["properties"]["id"] for f in feats].index(kv[0])]["properties"]["name"] or ""):
        ti = [f["properties"]["id"] for f in feats].index(tid)
        def chain(a, b):
            on = [lab for at, lab in sorted(names[ti]) if a - 30 <= at <= b + 30]
            return "-".join(on) if on else "(%.0f-%.0f m)" % (a, b)
        print("%-26s %s" % ((feats[ti]["properties"]["name"] or tid)[:26], ", ".join("%s %s" % (r[0], chain(r[1], r[2])) for r in rs)))
        for r in rs:
            total[r[0]] += r[2] - r[1]
    print("Total: " + ", ".join("%s %.1f km" % (k, v / 1000) for k, v in total.items()))
    with open("blazes.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
