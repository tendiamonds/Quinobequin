"""
Tidy how trails connect, and add unsigned junctions wherever trails meet with no
intersection to join them.

The routing graph only connects trails at intersections. Where two trails meet without
one (a trail ending on another, or two trails crossing), routing can't get from one to
the other. This finds those places and adds an unsigned junction at each: a routing point
with no sign and no number (junction: true, labeled J<n> in the code), invisible on the
map. First it tidies up:
  - drops junctions a sign beside them already covers
  - trims a trail line that runs a few meters past an intersection to a dead end (a
    drawing overshoot), unless its tip touches another trail
Safe to rerun after adding trails; it only changes what needs it.

  python add_junctions.py          tidy, add junctions, and write the data
  python add_junctions.py --dry    just report what it would do

Writes intersections_zoned.geojson and trails_selected.geojson.
"""

import io
import json
import math
import sys
import contextlib
import importlib.util

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"
INTS = PROJ + r"\intersections_zoned.geojson"
TRAILS = PROJ + r"\trails_selected.geojson"

TOUCH_M = 5        # a trail end this close to another trail meets it
NEAR_INT_M = 25    # an existing intersection this close that joins both trails covers it
ATTACH_M = 10      # a sign this close that misses one of the trails gets it attached
MERGE_M = 8        # candidate junctions closer than this are one junction
OVERSHOOT_M = 25   # a dead end this short past an intersection is a drawing overshoot
CELL_M = 60        # grid cell for finding nearby segments


def xy(c):
    return c[0] * 82000, c[1] * 111000


def lonlat(p):
    return [round(p[0] / 82000, 7), round(p[1] / 111000, 7)]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def project(p, a, b):
    """Nearest point to p on segment ab, and the fraction along it"""
    vx, vy = b[0] - a[0], b[1] - a[1]
    l2 = vx * vx + vy * vy
    t = 0 if l2 == 0 else max(0, min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / l2))
    return (a[0] + t * vx, a[1] + t * vy), t


def crossing(a, b, c, d):
    """Where segments ab and cd cross, or None"""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-9:
        return None
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    return (a[0] + t * r[0], a[1] + t * r[1]) if 0 <= t <= 1 and 0 <= u <= 1 else None


def lines(f):
    g = f["geometry"]
    return [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]


def name(f):
    return f["properties"].get("pdf_name") or f["properties"].get("name") or "Unnamed"


def network():
    """The data, labeled the way the build labels it, and which trails each place joins"""
    ints = json.load(open(INTS, encoding="utf-8"))
    trails = json.load(open(TRAILS, encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("bm", PROJ + r"\build_map.py")
    bm = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(bm)
        labeled, _, _ = bm.load_and_process()
    tim = bm.build_trail_int_map(labeled, trails)
    joins = {}
    for ti, info in tim.items():
        for label, _ in info["ints"]:
            joins.setdefault(label, set()).add(int(ti))
    return ints, trails, labeled, tim, joins


def tidy(dry):
    ints, trails, labeled, tim, joins = network()
    feats = {f["properties"]["label"]: f for f in labeled["features"]}

    # Junctions a sign beside them already covers
    signs = [(xy(f["geometry"]["coordinates"]), f["properties"]["label"]) for f in labeled["features"]
             if not f["properties"].get("no_sign")]
    drop = set()
    for label, f in feats.items():
        if f["properties"].get("junction"):
            p = xy(f["geometry"]["coordinates"])
            for q, s in signs:
                if dist(p, q) <= NEAR_INT_M and joins.get(label, set()) <= joins.get(s, set()):
                    drop.add(f["properties"]["number"])
                    print("  drop %s: %s already joins its trails, %.0f m away" % (label, s, dist(p, q)))
                    break

    # Overshoots: a short dead end past a trail's first or last intersection. Its tip may
    # touch other trails; that's only a link worth keeping if they don't all meet at the
    # same intersection anyway.
    def touches_other(ti, c, label):
        p, touched = xy(c), set()
        for tj, g in enumerate(trails["features"]):
            if tj != ti:
                for line in lines(g):
                    pts = [xy(k) for k in line]
                    if any(dist(p, project(p, pts[k], pts[k + 1])[0]) <= TOUCH_M for k in range(len(pts) - 1)):
                        touched.add(tj)
        return not touched <= joins.get(label, set())

    trims = []
    for ti, f in enumerate(trails["features"]):
        info = tim.get(ti)
        if f["geometry"]["type"] != "LineString" or not info or not info["ints"]:
            continue
        c = f["geometry"]["coordinates"]
        cum = [0.0]
        for k in range(1, len(c)):
            cum.append(cum[-1] + dist(xy(c[k - 1]), xy(c[k])))
        first, last = info["ints"][0], info["ints"][-1]
        lo, hi, why = 0, len(c) - 1, []
        if 0.5 < first[1] <= OVERSHOOT_M and not touches_other(ti, c[0], first[0]):
            lo = min(range(len(c)), key=lambda k: abs(cum[k] - first[1]))
            why.append("%s: %.0f m before %s" % (name(f), first[1], first[0]))
        if 0.5 < info["length"] - last[1] <= OVERSHOOT_M and not touches_other(ti, c[-1], last[0]):
            hi = min(range(len(c)), key=lambda k: abs(cum[k] - last[1]))
            why.append("%s: %.0f m past %s" % (name(f), info["length"] - last[1], last[0]))
        # A trail that's nothing but the overshoot (a short connector) stays as it is
        if why and hi - lo >= 1:
            f["geometry"]["coordinates"] = c[lo:hi + 1]
            trims.extend(why)
    print("%d junctions to drop, %d overshoots to trim" % (len(drop), len(trims)))
    for t in sorted(trims):
        print("  trim " + t)
    if not dry and (drop or trims):
        ints["features"] = [f for f in ints["features"] if f["properties"]["number"] not in drop]
        open(INTS, "w", encoding="utf-8").write(json.dumps(ints, indent=2) + "\n")
        open(TRAILS, "w", encoding="utf-8").write(json.dumps(trails, indent=2) + "\n")
    return len(drop) + len(trims)


def main(dry):
    ints, trails, labeled, tim, joins = network()
    existing = [(xy(f["geometry"]["coordinates"]), f["properties"]["label"]) for f in labeled["features"]]

    # Every segment of every trail, bucketed by grid cell
    segs = []   # (ti, li, k, a, b)
    grid = {}
    for ti, f in enumerate(trails["features"]):
        for li, line in enumerate(lines(f)):
            pts = [xy(c) for c in line]
            for k in range(len(pts) - 1):
                s = (ti, li, k, pts[k], pts[k + 1])
                segs.append(s)
                xs, ys = (pts[k][0], pts[k + 1][0]), (pts[k][1], pts[k + 1][1])
                for gx in range(int(min(xs) // CELL_M), int(max(xs) // CELL_M) + 1):
                    for gy in range(int(min(ys) // CELL_M), int(max(ys) // CELL_M) + 1):
                        grid.setdefault((gx, gy), []).append(len(segs) - 1)

    def near_segs(p):
        gx, gy = int(p[0] // CELL_M), int(p[1] // CELL_M)
        out = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                out.update(grid.get((gx + dx, gy + dy), []))
        return [segs[i] for i in out]

    # Candidates: (point, {trail: (li, k, t) where the point lies on it})
    cands = []
    # 1. A trail end touching another trail
    for ti, f in enumerate(trails["features"]):
        for li, line in enumerate(lines(f)):
            for k_end in (0, len(line) - 1):
                p = xy(line[k_end])
                for (tj, lj, k, a, b) in near_segs(p):
                    if tj == ti:
                        continue
                    q, t = project(p, a, b)
                    if dist(p, q) <= TOUCH_M:
                        cands.append((q, {ti: (li, max(k_end - 1, 0), 1.0 if k_end else 0.0), tj: (lj, k, t)}))
    # 2. Two trails crossing mid-line
    for i, (ti, li, k, a, b) in enumerate(segs):
        for (tj, lj, m, c, d) in near_segs(a):
            if tj > ti:
                x = crossing(a, b, c, d)
                if x:
                    _, t1 = project(x, a, b)
                    _, t2 = project(x, c, d)
                    cands.append((x, {ti: (li, k, t1), tj: (lj, m, t2)}))

    # Drop those an existing intersection already covers. Where a sign is right there but
    # misses a trail (its line passes just too far from the sign's point), attach that trail
    # to the sign instead of adding a junction beside it.
    found, attach = [], {}
    for p, on in cands:
        covered = any(dist(p, q) <= NEAR_INT_M and set(on) <= joins.get(lab, set()) for q, lab in existing)
        if covered:
            continue
        q, lab = min(existing, key=lambda e: dist(e[0], p))
        if dist(q, p) <= ATTACH_M:
            for t in set(on) - joins.get(lab, set()):
                attach.setdefault((lab, t), q)
            continue
        for g in found:
            if dist(g["p"], p) <= MERGE_M:
                for t, where in on.items():
                    g["on"].setdefault(t, where)
                break
        else:
            found.append({"p": p, "on": dict(on)})
    # A junction is only useful where at least two trails meet
    found = [g for g in found if len(g["on"]) >= 2]

    report = []
    for g in found:
        nearest = min(existing, key=lambda e: dist(e[0], g["p"]))
        report.append("%s at %.6f,%.6f (%.0f m from %s)" % (
            " / ".join(sorted(name(trails["features"][t]) for t in g["on"])),
            g["p"][1] / 111000, g["p"][0] / 82000, dist(nearest[0], g["p"]), nearest[1]))
    print("%d junctions to add" % len(found))
    for line in sorted(report):
        print("  " + line)
    print("%d trails to attach to a sign beside them" % len(attach))
    for (lab, t) in sorted(attach):
        print("  %s onto %s" % (name(trails["features"][t]), lab))
    if dry or not (found or attach):
        return

    # Put a point on each trail's line where a junction lands between its points, so the
    # build's tight junction snap finds it, and next to each sign a trail attaches to;
    # insert from the end so indices stay valid
    inserts = {}
    for g in found:
        for t, (li, k, frac) in g["on"].items():
            if 0.001 < frac < 0.999:
                inserts.setdefault((t, li), []).append((k, frac, g["p"]))
    for (lab, t), q in attach.items():
        best = None
        for li, line in enumerate(lines(trails["features"][t])):
            pts = [xy(c) for c in line]
            for k in range(len(pts) - 1):
                r, frac = project(q, pts[k], pts[k + 1])
                if best is None or dist(q, r) < best[0]:
                    best = (dist(q, r), li, k, frac, r)
        if best and 0.001 < best[3] < 0.999:
            inserts.setdefault((t, best[1]), []).append((best[2], best[3], best[4]))
    for (t, li), items in inserts.items():
        line = lines(trails["features"][t])[li]
        for k, frac, p in sorted(items, key=lambda x: (x[0], x[1]), reverse=True):
            line.insert(k + 1, lonlat(p))

    # The junctions themselves
    number = max(f["properties"]["number"] for f in ints["features"])
    codes = [f["properties"].get("code", "") for f in ints["features"]]
    jn = max([int(c[1:]) for c in codes if c.startswith("J") and c[1:].isdigit()] or [0])
    signed = [(xy(f["geometry"]["coordinates"]), f["properties"]["zone"]) for f in ints["features"]
              if not f["properties"].get("no_sign")]
    for g in found:
        number += 1
        jn += 1
        zone = min(signed, key=lambda e: dist(e[0], g["p"]))[1]
        ints["features"].append({"type": "Feature",
            "properties": {"number": number, "degree": len(g["on"]) + 1, "zone": zone,
                           "no_sign": True, "junction": True, "code": "J%d" % jn},
            "geometry": {"type": "Point", "coordinates": lonlat(g["p"])}})
    open(INTS, "w", encoding="utf-8").write(json.dumps(ints, indent=2) + "\n")
    open(TRAILS, "w", encoding="utf-8").write(json.dumps(trails, indent=2) + "\n")
    print("Wrote %d junctions; added %d points to trail lines" % (len(found), sum(len(v) for v in inserts.values())))


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    # A trim can leave a neighboring trail's tip free, so tidy until nothing changes
    passes = 1
    while tidy(dry) and not dry and passes < 10:
        passes += 1
    main(dry)
