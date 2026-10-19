"""
Import the blazed trails from NEMBA's 2012 map of the area (nemba_vietnam_map_2012.pdf,
kept locally: it's NEMBA's, not ours to publish) into trails_selected.geojson.

The map draws each blazed trail in its blaze's color under the trail line. A trail blazed
in two colors is drawn dashed, the two colors taking turns, so it gets both blazes.

The map is placed on the ground from its five numbered posts, then fitted closely to our
trails using all its trail lines. Each colored stroke marks the trails it lies along;
along each trail, the stretches of one color (dashes and all) join into runs, ending at
an intersection where there's one close by.

This is a one-time import: run it again and it replaces every trail's blazes with the
2012 map's. Corrections found on the ground go straight into trails_selected.geojson.

    python uc_blazes.py          shows what it found
    python uc_blazes.py --write  also writes it into trails_selected.geojson
"""

import json
import math
import os
import sys
from collections import defaultdict

import numpy as np
import pymupdf

PROJ = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(PROJ, "nemba_vietnam_map_2012.pdf")
TRAILS = os.path.join(PROJ, "trails_selected.geojson")
INTS = os.path.join(PROJ, "intersections_zoned.geojson")

# The numbered posts' discs on the map (PDF points)
POSTS_PDF = {1: (555.7, 230.1), 2: (626.5, 191.0), 3: (735.8, 186.0), 4: (752.2, 259.0), 5: (831.0, 236.2)}
# Stroke colors: trail lines, for the fit, and the blazes
DOUBLE_TRACK = ((0.0, 0.28, 0.71), 3.0)
SINGLE_TRACK = ((0.62, 0.19, 0.18), 1.31)
BLAZE_WIDTH = 1.31
BLAZE_COLORS = {
    "red": [(1, 0, 0), (1, 0.06, 0)],
    "green": [(0, 0.68, 0), (0, 0.58, 0), (0, 0.67, 0)],
    "orange": [(1, 0.52, 0), (1, 0.51, 0)],
    "blue": [(0, 0, 1)],
    "yellow": [(1, 1, 0), (1, 0.96, 0)],
}
MAP_AREA = pymupdf.Rect(0, 20, 1150, 580)   # leaves out the legend and the no-parking signs
ON_TRAIL_M = 15    # a stroke this close to a trail is on it
JOIN_M = 60        # pieces of one color this close along a trail are one run (dashes)
MIN_RUN_M = 40     # shorter runs are where a blazed trail crosses or meets this one
SNAP_M = 35        # a run's end this close to an intersection ends there
LAT0, LON0 = 42.17, -71.49


def m(lon, lat):
    """Meters east and north, as the map app measures (trailmap.py approxDist)"""
    return ((lon - LON0) * 82000, (lat - LAT0) * 111000)


def flat(g):
    return g["coordinates"] if g["type"] == "LineString" else [p for line in g["coordinates"] for p in line]


def close(c, target, tol=0.02):
    return c is not None and len(c) == 3 and max(abs(a - b) for a, b in zip(c, target)) < tol


def samples(d, step):
    """Points every step PDF points along a drawn path"""
    out = []
    for it in d["items"]:
        if it[0] == "l":
            a, b = it[1], it[2]
        elif it[0] == "c":
            a, b = it[1], it[4]
        else:
            continue
        n = max(1, int(math.hypot(b.x - a.x, b.y - a.y) / step))
        out += [(a.x + (b.x - a.x) * i / n, a.y + (b.y - a.y) * i / n) for i in range(n + 1)]
    return [p for p in out if MAP_AREA.contains(pymupdf.Point(*p))]


class Trails:
    """Our trails, as segments in meters, for finding the nearest one to a point"""

    def __init__(self, features):
        self.lines = []
        rows = []
        for ti, f in enumerate(features):
            c = [m(*p[:2]) for p in flat(f["geometry"])]
            s = [0.0]
            for a, b in zip(c, c[1:]):
                s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
            self.lines.append((c, s))
            rows += [(a[0], a[1], b[0], b[1], ti, s[i], s[i + 1]) for i, (a, b) in enumerate(zip(c, c[1:]))]
        self.seg = np.array(rows)

    def nearest(self, p):
        """(distance, trail index, meters along it, nearest point)"""
        ax, ay, bx, by, ti, s0, s1 = self.seg.T
        vx, vy = bx - ax, by - ay
        t = np.clip(((p[0] - ax) * vx + (p[1] - ay) * vy) / (vx * vx + vy * vy + 1e-9), 0, 1)
        qx, qy = ax + t * vx, ay + t * vy
        d = np.hypot(qx - p[0], qy - p[1])
        i = int(np.argmin(d))
        return float(d[i]), int(ti[i]), float(s0[i] + t[i] * (s1[i] - s0[i])), (float(qx[i]), float(qy[i]))


def fit(page, trails, ground_posts):
    """The PDF-to-meters affine map: from the posts, then tightened against the trail lines"""
    lines = []
    for d in page.get_drawings():
        for color, width in (DOUBLE_TRACK, SINGLE_TRACK):
            if close(d.get("color"), color) and abs((d.get("width") or 0) - width) < 0.05:
                lines += samples(d, 4)
    posts_p = [[x, y, 1] for x, y in POSTS_PDF.values()]
    posts_q = [m(*ground_posts[k]) for k in POSTS_PDF]
    T, *_ = np.linalg.lstsq(np.array(posts_p), np.array(posts_q), rcond=None)
    for tol in (60, 40, 30, 25, 20, 20):
        P, Q = [], []
        for x, y in lines:
            d, _, _, q = trails.nearest(np.array([x, y, 1]) @ T)
            if d < tol:
                P.append([x, y, 1])
                Q.append(q)
        for p, q in zip(posts_p, posts_q):   # the posts stay in, weighted
            P += [p] * 20
            Q += [q] * 20
        T, *_ = np.linalg.lstsq(np.array(P), np.array(Q), rcond=None)
    off = sorted(trails.nearest(np.array([x, y, 1]) @ T)[0] for x, y in lines)
    print("Fit: the map's trail lines are a median %.1f m from ours" % off[len(off) // 2])
    return T


def runs_along(positions):
    """Positions along a trail joined into [from, to] runs"""
    runs = []
    for a in sorted(positions):
        if runs and a - runs[-1][1] <= JOIN_M:
            runs[-1][1] = a
        else:
            runs.append([a, a])
    return [r for r in runs if r[1] - r[0] >= MIN_RUN_M]


def snap(run, stops, length):
    """A run's ends moved to an intersection (or the trail's end) close by"""
    out = []
    for v in run:
        near = [s for s in stops + [0.0, length] if abs(s - v) <= SNAP_M]
        out.append(min(near, key=lambda s: abs(s - v)) if near else v)
    return out


def main(write):
    data = json.load(open(TRAILS, encoding="utf-8"))
    features = data["features"]
    ints = json.load(open(INTS, encoding="utf-8"))["features"]
    trails = Trails(features)
    page = pymupdf.open(PDF)[0]
    T = fit(page, trails, {f["properties"]["post"]: f["geometry"]["coordinates"] for f in ints if f["properties"].get("post")})

    # Intersections along each trail, as positions on it
    stops = defaultdict(list)
    for f in ints:
        d, ti, at, _ = trails.nearest(m(*f["geometry"]["coordinates"]))
        if d < 15:
            stops[ti].append(at)

    found = defaultdict(lambda: defaultdict(list))   # trail index: color: positions
    for d in page.get_drawings():
        if abs((d.get("width") or 0) - BLAZE_WIDTH) > 0.05:
            continue
        color = next((k for k, vs in BLAZE_COLORS.items() if any(close(d.get("color"), v) for v in vs)), None)
        if color:
            for x, y in samples(d, 1.0):
                dist, ti, at, _ = trails.nearest(np.array([x, y, 1]) @ T)
                if dist < ON_TRAIL_M:
                    found[ti][color].append(at)

    blazes = {}
    for ti, colors in found.items():
        length = trails.lines[ti][1][-1]
        rs = []
        for color in BLAZE_COLORS:
            for run in runs_along(colors.get(color, [])):
                a, b = snap(run, stops[ti], length)
                if b - a >= MIN_RUN_M:
                    rs.append([color, round(a, 1), round(b, 1), 0])
        if rs:
            blazes[ti] = sorted(rs, key=lambda r: (r[1], r[0]))

    total = defaultdict(float)
    for ti in sorted(blazes, key=lambda t: features[t]["properties"].get("name") or ""):
        p = features[ti]["properties"]
        print("%-28s %s" % ((p.get("name") or p["id"])[:28], ", ".join("%s %.0f-%.0f" % tuple(r[:3]) for r in blazes[ti])))
        for r in blazes[ti]:
            total[r[0]] += r[2] - r[1]
    print("Total: " + ", ".join("%s %.1f km" % (k, total[k] / 1000) for k in BLAZE_COLORS if total[k]))

    if write:
        for ti, f in enumerate(features):
            f["properties"].pop("blazes", None)
            if ti in blazes:
                f["properties"]["blazes"] = blazes[ti]
        with open(TRAILS, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2) + "\n")
        print("Wrote %s (%d trails blazed)" % (TRAILS, len(blazes)))


if __name__ == "__main__":
    main("--write" in sys.argv)
