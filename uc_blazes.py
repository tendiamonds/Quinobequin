"""
Import the blazed trails, and which trails are double or single track, from NEMBA's 2012
map of the area (nemba_vietnam_map_2012.pdf, kept locally: it's NEMBA's, not ours to
publish) into trails_selected.geojson ("blazes" and "widths").

The map draws each blazed trail in its blaze's color under the trail line (3 pt wide under
a double track, 1.31 pt under a single track). What counts is what shows: a stroke painted
over by a later one of another color is hidden. A trail blazed in two colors is drawn
dashed, the colors taking turns in long pieces, so it gets both blazes.

The map is placed on the ground from its five numbered posts, fitted closely to our trails
using all its trail lines, and corrected locally by how far its lines nearby are from ours.
Each trail is then judged a stretch at a time, between intersections: colors that switch
back and forth along it are both blazes; otherwise each color marks its own part. Checked
against what's known on the ground around the Log Run: green B17-B13-C29-C26, red
B13-C29-C27.

This is a one-time import: run it again and it replaces every trail's blazes and widths
with the 2012 map's. Corrections found on the ground go straight into
trails_selected.geojson.

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
# Blaze strokes, told by their hue: the map uses a few shades of each, and draws a blaze
# 3 pt wide under a double track's dots, 1.31 pt under a single track's. Its other lines
# are other colors: the dark blue double track dots, the brown single track dots, black
# roads, grey contours and the like.
BLAZE_COLORS = ["red", "green", "orange", "blue", "yellow"]
BLAZE_MIN_WIDTH = 1.2


def blaze_color(c):
    """Which blaze a stroke color is, or None"""
    if c is None or len(c) != 3:
        return None
    r, g, b = c
    if r > 0.85 and g < 0.2 and b < 0.2:
        return "red"
    if g > 0.45 and r < 0.15 and b < 0.15:
        return "green"
    if r > 0.9 and 0.4 < g < 0.7 and b < 0.15:
        return "orange"
    if r > 0.9 and g > 0.85 and b < 0.2:
        return "yellow"
    if b > 0.85 and r < 0.15 and g < 0.15:
        return "blue"
    return None
MAP_AREA = pymupdf.Rect(0, 20, 1150, 580)   # leaves out the legend and the no-parking signs
SHIFT_SAMPLE_M = 40   # a map trail line this close to one of ours says how far off the fit is
SHIFT_RADIUS_M = 80   # ...for points this close to it
ON_TRAIL_M = 12    # a stroke this close to a trail (after the shift) is on it
JOIN_M = 60        # pieces of one color this close along a trail are one run (dashes)
MIN_RUN_M = 40     # shorter runs are where a blazed trail crosses or meets this one
SNAP_M = 35        # a run's end this close to an intersection ends there
DASH_BIN_M = 5     # a stretch's colors are looked at this often along it
DASH_SWITCHES = 3  # a stretch whose color switches this often is dashed...
DASH_SHARE = 0.15  # ...in the colors that make up this much of it each
WIDTH_STEP_M = 10  # trails are checked for their width this often
WIDTH_NEAR_M = 15  # a map trail line this close (after the shift), running the same way, is this trail
WIDTH_MIN_M = 40   # shorter stretches of one width join the stretch before
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

    def through(self, p, tol):
        """Every trail passing within tol of p: [(trail index, meters along it)]"""
        ax, ay, bx, by, ti, s0, s1 = self.seg.T
        vx, vy = bx - ax, by - ay
        t = np.clip(((p[0] - ax) * vx + (p[1] - ay) * vy) / (vx * vx + vy * vy + 1e-9), 0, 1)
        d = np.hypot(ax + t * vx - p[0], ay + t * vy - p[1])
        best = {}
        for i in np.nonzero(d < tol)[0]:
            k = int(ti[i])
            if k not in best or d[i] < best[k][0]:
                best[k] = (d[i], float(s0[i] + t[i] * (s1[i] - s0[i])))
        return [(k, at) for k, (_, at) in best.items()]


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
    return T, lines


def local_shift(T, lines, trails):
    """A function moving a converted point by how far the map's own trail lines near it are
    from ours: the fit is good overall but off by 10-25 m in places, as much as trails are
    apart. Each nearby line sample says how far its trail is off (the nearest of ours, if
    close); the middle of what they say (median, so a sample near the wrong trail doesn't
    count for much) is the shift."""
    g, dv = [], []
    for x, y in lines:
        p = np.array([x, y, 1]) @ T
        d, _, _, q = trails.nearest(p)
        if d < SHIFT_SAMPLE_M:
            g.append(p)
            dv.append((q[0] - p[0], q[1] - p[1]))
    g, dv = np.array(g), np.array(dv)

    def shift(p):
        near = np.hypot(g[:, 0] - p[0], g[:, 1] - p[1]) < SHIFT_RADIUS_M
        return (p[0] + float(np.median(dv[near, 0])), p[1] + float(np.median(dv[near, 1]))) if near.sum() >= 5 else tuple(p)
    return shift


def width_runs(page, T, shift, trails):
    """How wide each trail is along its length, from the map's double track and single
    track lines: {trail index: [["wide" or "narrow", from m, to m]]}. A trail the map
    doesn't have gets none, so the map app shows no terrain for it rather than a guess."""
    pts, kinds = [], []
    for d in page.get_drawings():
        kind = None
        for k, (color, width) in (("wide", DOUBLE_TRACK), ("narrow", SINGLE_TRACK)):
            if close(d.get("color"), color) and abs((d.get("width") or 0) - width) < 0.05:
                kind = k
        if kind:
            s = [shift(np.array([x, y, 1]) @ T) for x, y in samples(d, 2.0)]
            for a, b in zip(s, s[1:]):
                pts.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 180))
                kinds.append(kind)
    P = np.array(pts)
    runs = {}
    for ti, (c, s) in enumerate(trails.lines):
        seq = []
        for i in range(len(c) - 1):
            (ax, ay), (bx, by) = c[i], c[i + 1]
            seg = s[i + 1] - s[i]
            bearing = math.degrees(math.atan2(bx - ax, by - ay)) % 180
            for at in np.arange(WIDTH_STEP_M / 2, seg, WIDTH_STEP_M) if seg > WIDTH_STEP_M / 2 else [seg / 2]:
                t = at / seg if seg else 0
                px, py = ax + t * (bx - ax), ay + t * (by - ay)
                dist = np.hypot(P[:, 0] - px, P[:, 1] - py)
                turn = np.abs(P[:, 2] - bearing)
                dist[np.minimum(turn, 180 - turn) > 35] = np.inf
                j = int(np.argmin(dist))
                seq.append([s[i] + at, kinds[j] if dist[j] <= WIDTH_NEAR_M else None])
        # Smooth: each sample takes the most common width around it
        found = [k for _, k in seq]
        for i in range(len(seq)):
            around = defaultdict(int)
            for k in found[max(0, i - 2):i + 3]:
                if k:
                    around[k] += 1
            seq[i][1] = max(around, key=around.get) if around else None
        out = []
        for at, kind in seq:
            if out and out[-1][0] == kind:
                out[-1][2] = at
            else:
                out.append([kind, at, at])
        # Runs meet halfway; short ones join the run before; unknown stretches are dropped
        for i in range(1, len(out)):
            out[i][1] = out[i - 1][2] = (out[i - 1][2] + out[i][1]) / 2
        if out:
            out[0][1], out[-1][2] = 0.0, s[-1]
        merged = []
        for r in out:
            if merged and (r[2] - r[1] < WIDTH_MIN_M or merged[-1][0] == r[0]):
                merged[-1][2] = r[2]
            else:
                merged.append(list(r))
        if len(merged) > 1 and merged[0][2] - merged[0][1] < WIDTH_MIN_M:   # a short first one joins the next
            merged[1][1] = merged[0][1]
            merged.pop(0)
        known = [[k, round(a, 1), round(b, 1)] for k, a, b in merged if k]
        if known:
            runs[ti] = known
    return runs


def visible_blazes(page):
    """Points along the blaze strokes, [((x, y), color)], leaving out the parts painted over:
    the map draws shapes in order, and where a later stroke of another color covers an
    earlier one (Gulley's green, under its red from C29 to C27), only the later one shows.
    A dashed two-color line's pieces sit end to end, not on top of each other, so both
    colors show."""
    pts, cols, widths, order = [], [], [], []
    for i, d in enumerate(page.get_drawings()):
        w = d.get("width") or 0
        color = blaze_color(d.get("color")) if w >= BLAZE_MIN_WIDTH else None
        if color:
            for p in samples(d, 1.0):
                pts.append(p)
                cols.append(color)
                widths.append(w)
                order.append(i)
    P, W, O = np.array(pts), np.array(widths), np.array(order)
    C = np.array([BLAZE_COLORS.index(c) for c in cols])
    out = []
    for k in range(len(P)):
        later = (O > O[k]) & (C != C[k])
        covered = np.hypot(P[later, 0] - P[k, 0], P[later, 1] - P[k, 1]) < W[later] / 2
        if not covered.any():
            out.append((tuple(P[k]), cols[k]))
    print("Blaze strokes: %d points, %d painted over" % (len(P), len(P) - len(out)))
    return out


def edges(stops, length):
    """A trail's stretches between intersections: [(from m, to m)]"""
    cuts = sorted(set([0.0, length] + [s for s in stops if 0 < s < length]))
    joined = [cuts[0]]
    for c in cuts[1:]:
        if c - joined[-1] > 3:
            joined.append(c)
    joined[-1] = length
    return list(zip(joined, joined[1:]))


def edge_blazes(colors, a, b, stops, length):
    """The blazes on one stretch between intersections, from the colors seen along it.
    Two colors taking turns again and again (the map's dashed look) mean the stretch is
    blazed with both; otherwise each color marks its own part of it."""
    bins = defaultdict(lambda: defaultdict(int))   # bin: color: samples
    for color, positions in colors.items():
        for at in positions:
            if a <= at <= b:
                bins[int((at - a) // DASH_BIN_M)][color] += 1
    if not bins:
        return []
    seq = [max(bins[k], key=bins[k].get) for k in sorted(bins)]
    switches = sum(1 for x, y in zip(seq, seq[1:]) if x != y)
    share = {c: seq.count(c) / len(seq) for c in set(seq)}
    two = [c for c, f in share.items() if f >= DASH_SHARE]
    if switches >= DASH_SWITCHES and len(two) >= 2:
        lo = a + min(bins) * DASH_BIN_M
        hi = min(b, a + (max(bins) + 1) * DASH_BIN_M)
        lo, hi = snap([lo, hi], stops, length)
        return [[c, round(lo, 1), round(hi, 1), 0] for c in sorted(two, key=BLAZE_COLORS.index)] if hi - lo >= MIN_RUN_M else []
    out = []
    for color, positions in colors.items():
        for run in runs_along([at for at in positions if a <= at <= b]):
            lo, hi = snap(run, stops, length)
            if hi - lo >= MIN_RUN_M:
                out.append([color, round(lo, 1), round(hi, 1), 0])
    return out


def merge_runs(rs):
    """Runs of one color that meet (at an intersection) as one"""
    out = []
    for r in sorted(rs, key=lambda r: (BLAZE_COLORS.index(r[0]), r[1])):
        if out and out[-1][0] == r[0] and r[1] - out[-1][2] <= 1:
            out[-1][2] = max(out[-1][2], r[2])
        else:
            out.append(list(r))
    return sorted(out, key=lambda r: (r[1], BLAZE_COLORS.index(r[0])))


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
    T, lines = fit(page, trails, {f["properties"]["post"]: f["geometry"]["coordinates"] for f in ints if f["properties"].get("post")})
    shift = local_shift(T, lines, trails)

    # Intersections along each trail, as positions on it (and their labels, for the report)
    # (on every trail through it, not just the nearest)
    stops, labels = defaultdict(list), defaultdict(list)
    for f in ints:
        p = f["properties"]
        for ti, at in trails.through(m(*f["geometry"]["coordinates"]), 15):
            stops[ti].append(at)
            labels[ti].append((at, p.get("sign") or p.get("code") or "P%s" % p.get("post", "?")))

    found = defaultdict(lambda: defaultdict(list))   # trail index: color: positions
    for (x, y), color in visible_blazes(page):
        dist, ti, at, _ = trails.nearest(shift(np.array([x, y, 1]) @ T))
        if dist < ON_TRAIL_M:
            found[ti][color].append(at)

    blazes = {}
    for ti, colors in found.items():
        length = trails.lines[ti][1][-1]
        rs = []
        for a, b in edges(stops[ti], length):
            rs += edge_blazes(colors, a, b, stops[ti], length)
        if rs:
            blazes[ti] = merge_runs(rs)

    def chain(ti, a, b):
        """A stretch as the labeled intersections along it, ends and all: "B13-B16-C29" """
        on = sorted((at, lab) for at, lab in labels[ti] if a - SNAP_M <= at <= b + SNAP_M)
        names = [lab for _, lab in on if not lab.startswith("J")]
        return "-".join(names) if names else "(%.0f-%.0f m)" % (a, b)

    total = defaultdict(float)
    for ti in sorted(blazes, key=lambda t: features[t]["properties"].get("name") or ""):
        p = features[ti]["properties"]
        print("%-28s %s" % ((p.get("name") or p["id"])[:28], ", ".join("%s %s" % (r[0], chain(ti, r[1], r[2])) for r in blazes[ti])))
        for r in blazes[ti]:
            total[r[0]] += r[2] - r[1]
    print("Total: " + ", ".join("%s %.1f km" % (k, total[k] / 1000) for k in BLAZE_COLORS if total[k]))

    widths = width_runs(page, T, shift, trails)
    wtot = defaultdict(float)
    for rs in widths.values():
        for k, a, b in rs:
            wtot[k] += b - a
    all_m = sum(s[-1] for _, s in trails.lines)
    print("Widths: double track %.1f km, single track %.1f km, not on the map %.1f km" %
          (wtot["wide"] / 1000, wtot["narrow"] / 1000, (all_m - sum(wtot.values())) / 1000))

    if write:
        for ti, f in enumerate(features):
            for key, found in (("blazes", blazes), ("widths", widths)):
                f["properties"].pop(key, None)
                if ti in found:
                    f["properties"][key] = found[ti]
        with open(TRAILS, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2) + "\n")
        print("Wrote %s (%d trails blazed, %d with widths)" % (TRAILS, len(blazes), len(widths)))


if __name__ == "__main__":
    main("--write" in sys.argv)
