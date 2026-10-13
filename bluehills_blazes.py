"""
Find the blazed trails on the park's trail map (bluehills_data/blue-hills-trail-map-2020.pdf).

The map marks each blazed trail with its own symbols, drawn along the trail:
  skyline        Skyline Trail, blue rectangular blazes: teal dashes
  yellow_dots    Yellow Dot Loops: yellow dots
  green_dots     Green Dot Loops: green dots
  red_dots       Red Dot Loops: red dots
  white_arrows   Forest Path Loop: white triangles, pointing the one way it's marked
  yellow_arrows  Breakneck Ledge Loop: yellow triangles, the same

Each symbol's place converts to the ground (as in bluehills_pdf.py). Writes
bluehills_data/pdf_blazes.json: {blaze: [[lon, lat, heading or null], ...]}, heading in
degrees clockwise from north, for the triangles. build_bluehills.py matches them to trails.
"""

import json
import math
import os

import pymupdf

import bluehills_pdf as P
from build_bluehills import load_numbered

LEGEND = pymupdf.Rect(1578, 765, 1890, 1296)   # the legend's own samples aren't on the map
SKYLINE_COLOR = (0.0, 0.54, 0.67)
DOTS = {"yellow_dots": (1.0, 0.95, 0.0), "green_dots": (0.0, 0.65, 0.32), "red_dots": (0.93, 0.11, 0.14)}
DARK = (0.14, 0.12, 0.13)
SKYLINE_STEP_PT = 2      # Skyline dashes are sampled this often


def near(c, target, tol=0.03):
    return c is not None and len(c) == 3 and max(abs(a - b) for a, b in zip(c, target)) < tol


def corners(d):
    """The corner points of a small drawn shape"""
    pts = []
    for it in d["items"]:
        if it[0] == "l":
            pts += [it[1], it[2]]
        elif it[0] == "qu":
            q = it[1]
            pts += [q.ul, q.ur, q.lr, q.ll]
    out = []
    for p in pts:
        if all(abs(p.x - q.x) + abs(p.y - q.y) > 0.3 for q in out):
            out.append(p)
    return out


def heading(d):
    """Which way a triangle points, on the page: from the middle of its base to its tip.
    They point along their long axis, so the base is the shortest side. Some are drawn with
    an extra point; the triangle is the three corners spanning the most area."""
    pts = corners(d)
    if len(pts) < 3:
        return None
    area = lambda a, b, c: abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y))
    tri = max(((a, b, c) for i, a in enumerate(pts) for j, b in enumerate(pts) if j > i
               for c in pts[j + 1:]), key=lambda t: area(*t))
    side = lambda i: math.hypot(tri[(i + 1) % 3].x - tri[(i + 2) % 3].x, tri[(i + 1) % 3].y - tri[(i + 2) % 3].y)
    i = min(range(3), key=side)
    a, b, tip = tri[(i + 1) % 3], tri[(i + 2) % 3], tri[i]
    return (tip.x - (a.x + b.x) / 2, tip.y - (a.y + b.y) / 2)


def page_symbols():
    """{blaze: [(x, y, page direction or None)]}"""
    out = {k: [] for k in ("skyline", "white_arrows", "yellow_arrows", *DOTS)}
    for d in pymupdf.open(P.PDF)[0].get_drawings():
        r = d["rect"]
        if LEGEND.contains(r.tl):
            continue
        fill, color = d.get("fill"), d.get("color")
        mid = ((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
        if d["type"] == "s" and near(color, SKYLINE_COLOR) and abs((d.get("width") or 0) - 2) < 0.2:
            for it in d["items"]:
                if it[0] == "c":
                    a, b, c, e = it[1:5]
                    n = max(1, int(math.hypot(e.x - a.x, e.y - a.y) / SKYLINE_STEP_PT))
                    for k in range(n + 1):
                        t = k / n
                        x = (1 - t) ** 3 * a.x + 3 * (1 - t) ** 2 * t * b.x + 3 * (1 - t) * t * t * c.x + t ** 3 * e.x
                        y = (1 - t) ** 3 * a.y + 3 * (1 - t) ** 2 * t * b.y + 3 * (1 - t) * t * t * c.y + t ** 3 * e.y
                        out["skyline"].append((x, y, None))
                elif it[0] == "l":
                    out["skyline"] += [(it[1].x, it[1].y, None), (it[2].x, it[2].y, None)]
        elif d["type"] == "f" and max(r.width, r.height) <= 4:
            for k, c in DOTS.items():
                if near(fill, c):
                    out[k].append((mid[0], mid[1], None))
        elif d["type"] == "fs" and near(fill, (1.0, 0.95, 0.0)) and near(color, DARK) and max(r.width, r.height) <= 10:
            out["yellow_arrows"].append((mid[0], mid[1], heading(d)))
        elif d["type"] == "s" and near(color, DARK) and any(it[0] == "qu" for it in d["items"]) and 5 <= max(r.width, r.height) <= 10:
            # White triangles: a white fill with this outline drawn over it
            out["white_arrows"].append((mid[0], mid[1], heading(d)))
    return out


def main():
    osm = {num: ll for num, node, ll in load_numbered()}
    at, _ = P.page_dots()
    to_ground = P.make_predictor(at, osm, [n for n in at if n in osm])
    out = {}
    for blaze, syms in page_symbols().items():
        pts = []
        for x, y, d in syms:
            g = to_ground((x, y))
            h = None
            if d:
                n = math.hypot(*d) or 1
                g2 = to_ground((x + 5 * d[0] / n, y + 5 * d[1] / n))
                h = round(math.degrees(math.atan2((g2[0] - g[0]) * P.M_LON, (g2[1] - g[1]) * P.M_LAT)) % 360)
            pts.append([round(g[0], 6), round(g[1], 6), h])
        out[blaze] = pts
        print("%-14s %d symbols" % (blaze, len(pts)))
    json.dump(out, open(os.path.join(P.DATA, "pdf_blazes.json"), "w"))


if __name__ == "__main__":
    main()
