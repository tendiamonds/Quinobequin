"""
Find how wide each Blue Hills trail is, from the park's trail map
(bluehills_data/blue-hills-trail-map-2020.pdf). Its legend has:
  Narrow Trail    thin brown dashes
  Wide Trail      thick brown dashes (with a white line down the middle)
  Unpaved Road    thick solid brown (the same, solid)

The lines are sampled every few points, each with its direction, and converted to the
ground (as in bluehills_pdf.py). Writes bluehills_data/pdf_widths.json:
{"narrow" | "wide" | "road": [[lon, lat, bearing], ...]}, bearing in degrees from north
(0-180: a line runs both ways). build_bluehills.py matches them to trails.
"""

import json
import math
import os

import pymupdf

import bluehills_pdf as P
from build_bluehills import load_numbered

TRAIL_BROWN = (0.38, 0.21, 0.0)
LEGEND = pymupdf.Rect(1330, 1095, 1890, 1296)
STEP_PT = 2          # sample the lines this often
ROAD_MIN_PT = 10     # shorter solid pieces are the ends of dashes, not roads


def bezier(a, b, c, e, t):
    u = 1 - t
    return (u ** 3 * a.x + 3 * u * u * t * b.x + 3 * u * t * t * c.x + t ** 3 * e.x,
            u ** 3 * a.y + 3 * u * u * t * b.y + 3 * u * t * t * c.y + t ** 3 * e.y)


def samples(d):
    """(x, y, dx, dy) every STEP_PT along a drawn path"""
    out = []
    for it in d["items"]:
        if it[0] == "l":
            pts = [(it[1].x, it[1].y), (it[2].x, it[2].y)]
        elif it[0] == "c":
            n = max(2, int(math.hypot(it[4].x - it[1].x, it[4].y - it[1].y) / STEP_PT) + 1)
            pts = [bezier(*it[1:5], k / n) for k in range(n + 1)]
        else:
            continue
        for p, q in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(q[0] - p[0], q[1] - p[1]) / STEP_PT))
            for k in range(n):
                t = (k + 0.5) / n
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]), q[0] - p[0], q[1] - p[1]))
    return out


def page_lines():
    """{kind: [(x, y, dx, dy)]}"""
    out = {"narrow": [], "wide": [], "road": []}
    for d in pymupdf.open(P.PDF)[0].get_drawings():
        if d["type"] != "s" or LEGEND.contains(d["rect"].tl) or not d.get("color"):
            continue
        if max(abs(a - b) for a, b in zip(d["color"], TRAIL_BROWN)) > 0.03:
            continue
        w = d.get("width") or 0
        dashed = bool(d.get("dashes")) and not d["dashes"].strip().startswith("[]")
        s = samples(d)
        if abs(w - 0.65) < 0.05:
            out["narrow"] += s
        elif abs(w - 2.0) < 0.1 and dashed:
            out["wide"] += s
        elif abs(w - 2.0) < 0.1 and len(s) * STEP_PT >= ROAD_MIN_PT:
            out["road"] += s
    return out


def main():
    osm = {num: ll for num, node, ll in load_numbered()}
    at, _ = P.page_dots()
    to_ground = P.make_predictor(at, osm, [n for n in at if n in osm])
    out = {}
    for kind, pts in page_lines().items():
        res = []
        for x, y, dx, dy in pts:
            n = math.hypot(dx, dy) or 1
            g, g2 = to_ground((x, y)), to_ground((x + 3 * dx / n, y + 3 * dy / n))
            bearing = math.degrees(math.atan2((g2[0] - g[0]) * P.M_LON, (g2[1] - g[1]) * P.M_LAT)) % 180
            res.append([round(g[0], 6), round(g[1], 6), round(bearing)])
        out[kind] = res
        print("%-7s %d samples (about %.0f km)" % (kind, len(res), len(res) * STEP_PT * 8.2 / 1000))
    json.dump(out, open(os.path.join(P.DATA, "pdf_widths.json"), "w"))


if __name__ == "__main__":
    main()
