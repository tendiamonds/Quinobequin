"""
Add trails to the Upper Charles map from GPX files (Trailforks lets you download one trail
at a time): each track becomes a trail in trails_selected.geojson, named as in the file.

  python import_gpx.py FILE.gpx ...            add them
  python import_gpx.py --replace FILE.gpx ...  ...taking out any trail already there with the same name
  python import_gpx.py --dry ...               just report

A downloaded trail's ends often stop a few meters short of the trail they meet, so an end
within SNAP_M of another trail is moved onto it. Afterwards run add_junctions.py (the
junctions where the new trails meet the others) and build_map.py.
"""

import datetime
import json
import math
import os
import sys
import xml.etree.ElementTree as ET

PROJ = os.path.dirname(os.path.abspath(__file__))
TRAILS = os.path.join(PROJ, "trails_selected.geojson")
SNAP_M = 10      # a trail end this close to another trail is moved onto it
MIN_STEP_M = 2   # points closer together than this are thinned


def m(p):
    return (p[0] * 82000, p[1] * 111000)


def dist(a, b):
    return math.hypot((a[0] - b[0]) * 82000, (a[1] - b[1]) * 111000)


def read_gpx(path):
    """[(name, [[lon, lat], ...])], a track (or route) at a time"""
    root = ET.parse(path).getroot()
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    out = []
    for trk in root.iter(ns + "trk"):
        name = (trk.findtext(ns + "name") or "").strip()
        pts = [[float(p.get("lon")), float(p.get("lat"))] for p in trk.iter(ns + "trkpt")]
        out.append((name, pts))
    for rte in root.iter(ns + "rte"):
        name = (rte.findtext(ns + "name") or "").strip()
        out.append((name, [[float(p.get("lon")), float(p.get("lat"))] for p in rte.iter(ns + "rtept")]))
    fallback = os.path.splitext(os.path.basename(path))[0]
    return [(n or fallback, p) for n, p in out if len(p) >= 2]


def thin(pts):
    out = [pts[0]]
    for p in pts[1:-1]:
        if dist(out[-1], p) >= MIN_STEP_M:
            out.append(p)
    out.append(pts[-1])
    return [[round(x, 7), round(y, 7)] for x, y in out]


def nearest_on(trails, p, skip=None):
    """The nearest point on any trail (but skip) to p: (meters, [lon, lat], trail name)"""
    best = (math.inf, None, None)
    px, py = m(p)
    for f in trails:
        if f is skip:
            continue
        c = f["geometry"]["coordinates"]
        for a, b in zip(c, c[1:]):
            (ax, ay), (bx, by) = m(a), m(b)
            vx, vy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / ((vx * vx + vy * vy) or 1e-9)))
            d = math.hypot(ax + t * vx - px, ay + t * vy - py)
            if d < best[0]:
                best = (d, [round(a[0] + t * (b[0] - a[0]), 7), round(a[1] + t * (b[1] - a[1]), 7)], f["properties"].get("name"))
    return best


def main(args):
    dry = "--dry" in args
    replace = "--replace" in args
    files = [a for a in args if not a.startswith("--")]
    raw = open(TRAILS, encoding="utf-8").read()
    data = json.loads(raw)
    today = datetime.date.today().isoformat()
    new = []
    taken = {f["properties"]["id"] for f in data["features"]}
    serial = 0
    for path in files:
        for name, pts in read_gpx(path):
            serial += 1
            while "gpx_%s_%d" % (today, serial) in taken:     # ids from earlier imports today
                serial += 1
            new.append({"type": "Feature", "properties": {"id": "gpx_%s_%d" % (today, serial), "name": name,
                                                         "source": "trailforks gpx %s" % today},
                        "geometry": {"type": "LineString", "coordinates": thin(pts)}})
    if replace:
        names = {f["properties"]["name"].lower() for f in new}
        gone = [f for f in data["features"] if (f["properties"].get("name") or "").lower() in names]
        data["features"] = [f for f in data["features"] if f not in gone]
        for f in gone:
            print("replacing %s (%s)" % (f["properties"]["name"], f["properties"]["id"]))
    for f in new:
        c = f["geometry"]["coordinates"]
        length = sum(dist(a, b) for a, b in zip(c, c[1:]))
        notes = []
        for k in (0, -1):
            d, at, onto = nearest_on(data["features"] + [g for g in new if g is not f], c[k])
            if d <= SNAP_M:
                c[k] = at
                notes.append("%s end onto %s (%.0f m)" % ("start" if k == 0 else "far", onto or "a trail", d))
        print("adding %s, %.0f m%s" % (f["properties"]["name"], length, "; " + "; ".join(notes) if notes else ""))
    data["features"] += new
    if not dry:
        with open(TRAILS, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2) + "\n")
        print("Wrote %s (%d trails). Next: add_junctions.py, then build_map.py" % (TRAILS, len(data["features"])))


if __name__ == "__main__":
    main(sys.argv[1:])
