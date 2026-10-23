"""
The Upper Charles trail lines, from OpenStreetMap. Our data decides *which* trails there
are (their names, blazes and signs); OSM gives *where* each one runs, wherever it has it
(OSM first, as Jason decided 2026-10-23: its lines sit on the map tiles' and are mostly
traced from imagery, where our Trailforks lines were GPS tracks rounded to a meter).

For each trail, the matching OSM line is the way through OSM's path network, from near
our trail's start to near its end, that stays closest to our line. It's taken if it
follows ours (strays no more than STRAY_OK_M); the lists below override that:
  KEEP_OURS     keep our line;  USE_OSM  take OSM's however far it strays
  RELAXED       matched loosely and routed by the middle of our line (a loop goes round)
  WAYS_ALLOWED  which OSM ways a trail may use (the Rail Trail is OSM's Upper Charles
                Trail; the Tow Roads beside it are the unnamed towpath), cut level with
                our ends (TRIMMED); EXTEND_FAR runs one on to the end of its OSM way
A matched line that starts by running along another trail's is trimmed back to where it
leaves it, and one that stops a point short of OSM's own junction carries on to it.

Then the intersections. Each keeps only the trails that really meet there (the old 20 m
reach between signs and trails credited two signs 12 m apart with each other's trails),
and moves to where its trails' OSM lines meet: on the lines running through it, a trail
that ends at it getting a short connector, and a sign staying on its side of any CR line.
A line OSM has elsewhere lets the intersection go and meets its neighbors where it really
does. Last, it checks that every intersection still joins the same trails as before.

  python uc_osm_geometry.py           match, and write osm_geometry_preview.html to look at
  python uc_osm_geometry.py --write   ...and write the new lines and intersection positions
  python uc_osm_geometry.py --fresh   download OSM again first (uc_data/osm_paths.json)

This was run once (2026-10-23) on the data as it was before (lines from Trailforks), then:
sign_logos.csv positions updated for the moved signs, add_junctions.py (junctions where
OSM's lines meet), unmarked junctions joining fewer than two trails dropped, blaze runs
anchored to a sign no longer on their trail re-anchored to the trail's end, build_map.py.
Running it again on today's data isn't what it's for. Don't edit OSM from here.
"""

import contextlib
import heapq
import io
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

PROJ = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(PROJ, "uc_data")
OSM_FILE = os.path.join(DATA, "osm_paths.json")
TRAILS = os.path.join(PROJ, "trails_selected.geojson")
INTS = os.path.join(PROJ, "intersections_zoned.geojson")
BBOX = "(42.155,-71.520,42.202,-71.480)"   # south, west, north, east, around the trails
SERVERS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
QUERY = ('[out:json][timeout:120];way%s["highway"~"^(path|footway|track|bridleway|cycleway|service|unclassified)$"]'
         '["footway"!~"^(sidewalk|crossing)$"];(._;>;);out qt;' % BBOX)

NEAR_M = 25          # OSM edges farther than this from our trail aren't considered
END_M = 15           # the OSM line must start and end this close to ours
MAX_OFF_M = 15       # ...and never stray farther than this from ours, or ours from it
LENGTH_RATIO = (0.8, 1.25)
STEP_M = 4           # lines are compared at points this far apart
INT_MOVE_M = 20      # an intersection moves at most this far onto the new lines


def xy(p):
    return (p[0] * 82000.0, p[1] * 111000.0)


def dist(a, b):
    return math.hypot((a[0] - b[0]) * 82000, (a[1] - b[1]) * 111000)


def length(c):
    return sum(dist(a, b) for a, b in zip(c, c[1:]))


def samples(c, step=STEP_M):
    """Points every `step` meters along a line, [lon, lat]"""
    out = [c[0]]
    for a, b in zip(c, c[1:]):
        n = max(1, int(dist(a, b) / step))
        out += [[a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n] for k in range(1, n + 1)]
    return out


class Line:
    """A line, for nearest-point questions (a grid of its segments)"""
    CELL = 30.0

    def __init__(self, c):
        self.c = c
        self.grid = {}
        for i, (a, b) in enumerate(zip(c, c[1:])):
            (ax, ay), (bx, by) = xy(a), xy(b)
            for gx in range(int(min(ax, bx) // self.CELL) - 1, int(max(ax, bx) // self.CELL) + 2):
                for gy in range(int(min(ay, by) // self.CELL) - 1, int(max(ay, by) // self.CELL) + 2):
                    self.grid.setdefault((gx, gy), []).append(i)

    def nearest(self, p, reach=60.0):
        """(meters, point [lon, lat], segment index) of the nearest point on the line to p"""
        px, py = xy(p)
        best = (math.inf, None, None)
        seen = set()
        r = int(reach // self.CELL) + 1
        for gx in range(int(px // self.CELL) - r, int(px // self.CELL) + r + 1):
            for gy in range(int(py // self.CELL) - r, int(py // self.CELL) + r + 1):
                for i in self.grid.get((gx, gy), ()):
                    if i in seen:
                        continue
                    seen.add(i)
                    a, b = self.c[i], self.c[i + 1]
                    (ax, ay), (bx, by) = xy(a), xy(b)
                    vx, vy = bx - ax, by - ay
                    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / ((vx * vx + vy * vy) or 1e-9)))
                    d = math.hypot(ax + t * vx - px, ay + t * vy - py)
                    if d < best[0]:
                        best = (d, [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])], i)
        return best

    def off(self, p):
        return self.nearest(p)[0]


# --- OSM

def fetch():
    os.makedirs(DATA, exist_ok=True)
    for attempt in range(6):
        url = SERVERS[attempt % 2]
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": QUERY}).encode(),
                                         headers={"User-Agent": "trail-map/1.0 (tendiamonds@gmail.com)"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode("utf-8"))
            with open(OSM_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
            print("Downloaded %d OSM elements (%s)" % (len(data["elements"]), data.get("osm3s", {}).get("timestamp_osm_base")))
            return
        except Exception as e:   # busy server: wait and try the other one
            print("  %s: %s; retrying" % (url, e))
            time.sleep(5 * (attempt + 1))
    raise SystemExit("Couldn't download from OSM")


WAY_TAGS = {}   # way id: its OSM tags (osm_graph fills it)


def osm_graph():
    """nodes {id: [lon, lat]}, adjacency {id: [(id, meters, way id)]}, way names {id: name}"""
    els = json.load(open(OSM_FILE, encoding="utf-8"))["elements"]
    WAY_TAGS.update({w["id"]: w.get("tags", {}) for w in els if w["type"] == "way"})
    nodes = {e["id"]: [e["lon"], e["lat"]] for e in els if e["type"] == "node"}
    adj, names = {}, {}
    for w in els:
        if w["type"] != "way":
            continue
        names[w["id"]] = w.get("tags", {}).get("name", "")
        ns = [n for n in w["nodes"] if n in nodes]
        for a, b in zip(ns, ns[1:]):
            d = dist(nodes[a], nodes[b])
            adj.setdefault(a, []).append((b, d, w["id"]))
            adj.setdefault(b, []).append((a, d, w["id"]))
    return nodes, adj, names


# --- Matching one trail

def match(c, nodes, adj, near_m=NEAR_M, end_m=END_M, via=False, allow=None, trim=False):
    """The OSM line for our line c: (coords, node ids, way ids, why not). near_m: how far
    from ours OSM paths are considered; end_m: how close the OSM line's ends must be to
    ours; via: route it by the middle of our line too (a loop whose ends are close would
    otherwise take the short way between them); allow: a test of an OSM way's tags, for
    the ways it may use; trim: the trail's ends fall partway along OSM's ways, so look
    farther for them and cut OSM's line level with our ends."""
    if trim:   # (it's held to its own ways, so it can look farther for them)
        near_m = max(near_m, TRIM_END_M)
    ours = Line(c)
    L = length(c)
    pad_x, pad_y = near_m / 82000, near_m / 111000
    x0, x1 = min(p[0] for p in c) - pad_x, max(p[0] for p in c) + pad_x
    y0, y1 = min(p[1] for p in c) - pad_y, max(p[1] for p in c) + pad_y
    near = {n for n, p in nodes.items() if n in adj and x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and ours.off(p) <= near_m}
    if not near:
        return None, None, None, "no OSM path near it"
    edge_cost = {}

    def cost(a, b, d):
        # length, more the farther it runs from our line
        key = (min(a, b), max(a, b))
        if key not in edge_cost:
            offs = [ours.off(p) for p in samples([nodes[a], nodes[b]], 5)]
            edge_cost[key] = None if max(offs) > near_m else d * (1 + (sum(offs) / len(offs) / 4.0) ** 2)
        return edge_cost[key]

    def route(starts, ends):
        """The cheapest way from any of starts to any of ends ({node: meters off}): (nodes, ways)"""
        best = {n: 3 * d for n, d in starts.items()}
        prev = {n: (None, None) for n in starts}
        heap = [(v, n) for n, v in best.items()]
        heapq.heapify(heap)
        done, goal = set(), None
        while heap:
            v, n = heapq.heappop(heap)
            if n in done:
                continue
            done.add(n)
            if n in ends:
                total = v + 3 * ends[n]   # finishing here costs the step from the node to our end
                if goal is None or total < goal[0]:
                    goal = (total, n)
            for m, d, wid in adj.get(n, ()):
                if m not in near or m in done or (allow and not allow(WAY_TAGS.get(wid, {}))):
                    continue
                ec = cost(n, m, d)
                if ec is not None and v + ec < best.get(m, math.inf):
                    best[m] = v + ec
                    prev[m] = (n, wid)
                    heapq.heappush(heap, (v + ec, m))
        if goal is None:
            return None, None
        path, ways, n = [], [], goal[1]
        while n is not None:
            path.append(n)
            n, wid = prev[n]
            if wid is not None:
                ways.append(wid)
        return path[::-1], ways[::-1]

    if trim:
        end_m = max(end_m, TRIM_END_M)
    starts = {n: dist(nodes[n], c[0]) for n in near if dist(nodes[n], c[0]) <= end_m}
    ends = {n: dist(nodes[n], c[-1]) for n in near if dist(nodes[n], c[-1]) <= end_m}
    if not starts or not ends:
        return None, None, None, "no OSM path at its %s" % ("start" if not starts else "end")
    if via:
        # the point halfway along ours, and the OSM nodes near it
        half, run, mid = L / 2, 0.0, c[-1]
        for a, b in zip(c, c[1:]):
            if run + dist(a, b) >= half:
                t = (half - run) / max(dist(a, b), 1e-9)
                mid = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
                break
            run += dist(a, b)
        mids = {n: dist(nodes[n], mid) for n in near if dist(nodes[n], mid) <= end_m}
        p1, w1 = route(starts, mids) if mids else (None, None)
        p2, w2 = route({p1[-1]: 0.0}, ends) if p1 else (None, None)
        path, ways = (p1 + p2[1:], w1 + w2) if p2 else (None, None)
    else:
        path, ways = route(starts, ends)
    if not path:
        return None, None, None, "no OSM way along it from end to end"
    new = [nodes[n] for n in path]
    if trim and len(new) >= 2:
        new, path = cut_to(new, path, c[0], c[-1])
    if len(new) < 2:
        return None, None, None, "its OSM match is a single point"
    # It has to follow ours all the way, both ways round, and be about as long
    theirs = Line(new)
    off1 = max(theirs.off(p) for p in samples(c))
    off2 = max(ours.off(p) for p in samples(new))
    ratio = length(new) / L
    if max(off1, off2) > MAX_OFF_M:
        return new, path, ways, "strays %.0f m from ours" % max(off1, off2)
    if not LENGTH_RATIO[0] <= ratio <= LENGTH_RATIO[1]:
        return new, path, ways, "is %.0f%% as long as ours" % (100 * ratio)
    return new, path, ways, None


def cut_to(new, path, a, b):
    """OSM's line new (its nodes path) cut level with points a and b: (coords, nodes)"""
    line = Line(new)
    da, pa, ia = line.nearest(a, reach=TRIM_END_M + 20)
    db, pb, ib = line.nearest(b, reach=TRIM_END_M + 20)
    if ia is None or ib is None or (ia, dist(new[ia], pa)) > (ib, dist(new[ib], pb)):
        return new, path
    return [pa] + new[ia + 1:ib + 1] + [pb], path[ia + 1:ib + 1]


def wiggle(c):
    """degrees of turning per 100 m"""
    P = [xy(p) for p in c]
    turn = 0.0
    for a, b, e in zip(P, P[1:], P[2:]):
        h1 = math.atan2(b[1] - a[1], b[0] - a[0])
        h2 = math.atan2(e[1] - b[1], e[0] - b[0])
        turn += abs((math.degrees(h2 - h1) + 180) % 360 - 180)
    return 100 * turn / max(length(c), 1)


# --- The network as the build sees it: which intersections are on which trails

def network(ints, trails, sign_snap=None):
    """{intersection label: {trail ids}}, as the build snaps them (or with sign_snap)"""
    import trailmap
    tim = trailmap.build_trail_int_map(ints, trails, sign_snap)
    joins = {}
    for ti, info in tim.items():
        for label, _ in info["ints"]:
            joins.setdefault(label, set()).add(trails["features"][int(ti)]["properties"]["id"])
    return joins


def labeled(ints):
    """The intersections with a label for build_trail_int_map: their data number"""
    out = json.loads(json.dumps(ints))
    for f in out["features"]:
        f["properties"]["label"] = str(f["properties"]["number"])
    return out


STRAY_OK_M = 30      # an OSM line straying up to this far from ours is still taken (OSM first)
# Trails whose OSM match follows the wrong way, so they keep our line: the Tow Road Middle
# runs 5-10 m beside the Rail Trail, and its match took the Rail Trail for 200 m
KEEP_OURS = set()
# Trails whose OSM line strays farther than STRAY_OK_M from ours but is the better one
# (Jason, 2026-10-23)
USE_OSM = {"NEMBA Loop", "Burnt Ends"}
# ...and where OSM is taken as it is, whatever it has (Jason, 2026-10-23: "Powerlines and
# south is all insane"): matched more loosely, routed by the middle of our line (so a loop
# goes round), and taken however far it strays
RELAXED = {"Powerlines", "495 -Milford Rock Run", "495 Run B", "Access road via Milford Rock Quarry", "Armageddon",
           "F16", "No Name", "Random Connector", "Charles River Loop", "Lost Trail", "Found", "Optional Rocks"}
# (not The Maine Line: OSM folds it into its 495 Rock Run, which 495 -Milford Rock Run
# already follows, so the two would lie on top of each other)
RELAXED_NEAR_M, RELAXED_END_M = 40, 30
# Which OSM ways a trail may use, where neighbors run side by side: the Rail Trail is
# OSM's Upper Charles Trail cycleway, and the Charles River Tow Roads beside it never are
# (the towpath is OSM's unnamed path beside it). Their ends fall partway along OSM's
# ways, so their lines are cut level with our ends (TRIMMED).
RAIL = lambda t: t.get("name") == "Upper Charles Trail"
TOWPATH = lambda t: not t.get("name") and t.get("highway") == "path"
WAYS_ALLOWED = {"Upper Charles Rail Trail": RAIL, "Charles River Tow Road Lower": TOWPATH,
                "Charles River Tow Road Middle": TOWPATH, "Charles River Tow Road Upper": TOWPATH}
TRIMMED = set(WAYS_ALLOWED)
TRIM_END_M = 80
EXTEND_FAR = {"Upper Charles Rail Trail": RAIL}
THRU_ON_M = 3        # an OSM line running through an intersection must pass this close to it
END_AT_M = 8         # a trail whose end is this close to an intersection ends there


def cr_status():
    """A function telling which CR parcel (or None) a point is in, from cr_parcels.geojson"""
    crs = json.load(open(os.path.join(PROJ, "cr_parcels.geojson"), encoding="utf-8"))["features"]
    rings = [(f["properties"]["MAP_PAR_ID"], [xy(q) for q in f["geometry"]["coordinates"][0]]) for f in crs]

    def inside(p, ring):
        x, y = p
        hit = False
        for (ax, ay), (bx, by) in zip(ring, ring[1:]):
            if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                hit = not hit
        return hit
    return lambda p: next((pid for pid, r in rings if inside(xy(p), r)), None)


def with_point(c, q):
    """Line c with point q put in where it's nearest (pulling the line to it), unless a
    point is already there"""
    d, at, i = Line(c).nearest(q, reach=60)
    if i is None or min(dist(c[i], q), dist(c[i + 1], q)) <= 0.5:
        return c
    return c[:i + 1] + [[round(q[0], 7), round(q[1], 7)]] + c[i + 1:]


def taken(r):
    """Whether a trail takes OSM's line: matched, or straying no more than STRAY_OK_M"""
    if r["name"] in KEEP_OURS:
        return False
    if r["why"] is None or (r["name"] in USE_OSM | RELAXED | TRIMMED and r["new"] is not None):
        return True
    return r["new"] is not None and r["why"].startswith("strays") and int(r["why"].split()[1]) <= STRAY_OK_M


def main(args):
    if "--fresh" in args or not os.path.exists(OSM_FILE):
        fetch()
    nodes, adj, names = osm_graph()
    trails = json.load(open(TRAILS, encoding="utf-8"))
    ints = json.load(open(INTS, encoding="utf-8"))
    before = network(labeled(ints), trails, sign_snap=20)   # as built before lines came from OSM
    by_id = {f["properties"]["id"]: f for f in trails["features"]}
    int_at = {str(f["properties"]["number"]): f["geometry"]["coordinates"] for f in ints["features"]}
    in_cr = cr_status()

    ran_on = set()   # trails that now run on past their old far end (EXTEND_FAR)

    def ends_at(t, at):
        # its end is right there, or its nearest point to it is its end (old signs often
        # stood 10-20 m off the end of a trail they meet)
        c = by_id[t]["geometry"]["coordinates"]
        e = dist(at, c[0]) if t in ran_on else min(dist(at, c[0]), dist(at, c[-1]))
        return e <= END_AT_M or (e <= 30 and e <= Line(c).off(at) + 2)

    # 1. Match each trail; OSM's line is taken wherever it's a match (or strays a little)
    results = {}
    for f in trails["features"]:
        p = f["properties"]
        c = f["geometry"]["coordinates"]
        allow = WAYS_ALLOWED.get(p.get("name"))
        if dist(c[0], c[-1]) < 10:   # a closed loop (Dirty Little Secret): round by its middle
            new, path, ways, why = match(c, nodes, adj, via=True, allow=allow)
        elif p.get("name") in RELAXED:
            new, path, ways, why = match(c, nodes, adj, RELAXED_NEAR_M, RELAXED_END_M, via=True, allow=allow)
        else:
            new, path, ways, why = match(c, nodes, adj, allow=allow, trim=p.get("name") in TRIMMED)
        results[p["id"]] = {"name": p.get("name") or "(unnamed)", "old": c, "new": new, "path": path, "ways": ways, "why": why,
                            "len_old": length(c), "len_new": length(new) if new else None,
                            "wig_old": wiggle(c), "wig_new": wiggle(new) if new else None}
    ok = {k for k, r in results.items() if taken(r)}

    # A matched line that starts (or ends) by running along another trail's OSM line starts
    # where it leaves it instead: our One Ledges began up by D9, so its match ran down
    # Nemba Way from D9 to where One Ledges really branches off. The shared stretch goes to
    # the trail whose own line runs closest to it.
    old_line = {k: Line(by_id[k]["geometry"]["coordinates"]) for k in by_id}
    edges_of = {k: {frozenset(e) for e in zip(results[k]["path"], results[k]["path"][1:])} for k in ok}
    trimmed = []
    for k in sorted(ok):
        path = results[k]["path"]

        def owner(e):
            """The other trails whose OSM lines use edge e"""
            return [j for j in ok if j != k and e in edges_of[j]]

        def run(seq):
            """How many leading edges of seq are shared, and whether they belong to the others"""
            n = 0
            while n < len(seq) - 2 and owner(frozenset((seq[n], seq[n + 1]))):
                n += 1
            if not n:
                return 0
            pts = [nodes[x] for x in seq[:n + 1]]
            mine = sum(old_line[k].off(p) for p in pts) / len(pts)
            theirs = min(sum(old_line[j].off(p) for p in pts) / len(pts)
                         for j in set(sum((owner(frozenset((seq[m], seq[m + 1]))) for m in range(n)), [])))
            return n if theirs < mine else 0
        i = run(path)
        j = run(path[::-1])
        if (i or j) and len(path) - i - j >= 2:
            cut = path[i:len(path) - j]
            gone = length([nodes[x] for x in path[:i + 1]]) + length([nodes[x] for x in path[len(path) - j - 1:]])
            trimmed.append((results[k]["name"], gone))
            results[k]["path"] = cut
            results[k]["new"] = [nodes[x] for x in cut]
            results[k]["len_new"] = length(results[k]["new"])
            edges_of[k] = {frozenset(e) for e in zip(cut, cut[1:])}
    for name, gone in sorted(trimmed):
        print("  %s starts where it leaves the trail it ran along (%.0f m shorter)" % (name, gone))

    # A matched line that stops a point short of where OSM joins it to another trail
    # carries on along its OSM way to that junction (One Ledges' way ends on Nemba Way,
    # one point past where its match stopped)
    way_nodes = {w["id"]: [n for n in w["nodes"] if n in nodes]
                 for w in json.load(open(OSM_FILE, encoding="utf-8"))["elements"] if w["type"] == "way"}
    on_paths = {}
    for k in ok:
        for n in results[k]["path"]:
            on_paths.setdefault(n, set()).add(k)
    extended = []
    for k in sorted(ok):
        path, ways_k = results[k]["path"], results[k]["ways"]
        for at_start in (True, False):
            end = path[0] if at_start else path[-1]
            if any(j != k for j in on_paths.get(end, ())):
                continue   # already at a junction
            nxt = path[1] if at_start else path[-2]
            for wid in set(ways_k):
                seq = way_nodes.get(wid, [])
                if end not in seq or nxt not in seq:
                    continue
                i, j = seq.index(end), seq.index(nxt)
                step = 1 if i > j else -1
                walk, d, m = [], 0.0, i
                while 0 <= m + step < len(seq) and d <= 25:
                    d += dist(nodes[seq[m]], nodes[seq[m + step]])
                    m += step
                    walk.append(seq[m])
                    if any(x != k for x in on_paths.get(seq[m], ())):
                        break
                else:
                    walk = []
                if walk and d <= 25 and any(x != k for x in on_paths.get(walk[-1], ())):
                    path = walk[::-1] + path if at_start else path + walk
                    extended.append((results[k]["name"], d))
                    break
        if len(path) != len(results[k]["path"]):
            results[k]["path"] = path
            results[k]["new"] = [nodes[x] for x in path]
            results[k]["len_new"] = length(results[k]["new"])
            for n in path:
                on_paths.setdefault(n, set()).add(k)
    for name, d in sorted(extended):
        print("  %s carries on %.0f m along its OSM way to where it joins another trail" % (name, d))
    # A trail that OSM has running on past our far end, all of it ours (the Rail Trail, on
    # past B1 to the end of OSM's Upper Charles Trail)
    for k in sorted(ok):
        allow = EXTEND_FAR.get(results[k]["name"])
        if not allow:
            continue
        path, seen, d = list(results[k]["path"]), set(results[k]["path"]), 0.0
        n0 = len(path)
        others = [old_line[j] for j in by_id if j != k]
        while True:
            step = [(m, dd) for m, dd, wid in adj.get(path[-1], ()) if m not in seen and allow(WAY_TAGS.get(wid, {}))]
            if len(step) != 1:
                break
            # (only as far as our network goes: not past 150 m from all our other trails)
            if min(o.nearest(nodes[step[0][0]], reach=150)[0] for o in others) > 150:
                break
            m, dd = step[0]
            path.append(m)
            seen.add(m)
            d += dd
        if d:
            base = results[k]["new"]
            if dist(base[-1], nodes[path[n0 - 1]]) > 0.5:
                base = base[:-1]   # (its end was cut partway along a segment)
            results[k]["new"] = base + [nodes[x] for x in path[n0:]]
            results[k]["path"] = path
            results[k]["len_new"] = length(results[k]["new"])
            ran_on.add(k)
            print("  %s carries on %.0f m past our end, along its OSM way" % (results[k]["name"], d))
    lines = {k: Line(results[k]["new"] if k in ok else by_id[k]["geometry"]["coordinates"]) for k in by_id}

    # Which trails really belong to each intersection. The old 20 m reach credited a sign
    # with every trail near it, so two signs a few meters apart shared their trails (E1 got
    # The Main Trail and Gintro, which meet at D9, 12 m away). A trail belongs if its line
    # comes within 10 m, or it ends near (the end its nearest point, up to 30 m), unless
    # OSM has that end joining another trail more than 10 m away: that's a junction of
    # its own (Three Ledges, which leaves Nemba Way 23 m south of E1).
    def osm_end(t, at):
        c = results[t]["new"]
        return c[0] if dist(c[0], at) <= dist(c[-1], at) else c[-1]

    raw, before, dropped = before, {}, []
    for num, mine in raw.items():
        at = int_at[num]
        keep = set()
        for t in mine:
            if t in ok and results[t]["name"] in RELAXED | TRIMMED | USE_OSM and lines[t].off(at) > 10 and not ends_at(t, at):
                # OSM's line, taken as it is, doesn't come by here: it meets its neighbors
                # where it really runs (add_junctions.py joins them there)
                dropped.append((num, t))
            elif old_line[t].off(at) <= 10:
                keep.add(t)
            elif ends_at(t, at):
                e = osm_end(t, at) if t in ok else None
                if e is not None and dist(e, at) > 10 and any(lines[u].off(e) <= 1 for u in ok if u != t):
                    dropped.append((num, t))
                else:
                    keep.add(t)
            else:
                dropped.append((num, t))
        before[num] = keep
    # A trail's end belongs to one intersection: the one nearest where it really ends (its
    # OSM end, if matched). One Ledges ends 14 m from E1 and 18 m from D9: it's E1's.
    claims = {}
    for num, keep in before.items():
        at = int_at[num]
        for t in keep:
            if ends_at(t, at):
                c = by_id[t]["geometry"]["coordinates"]
                side = 0 if dist(c[0], at) <= dist(c[-1], at) else -1
                end = (results[t]["new"] if t in ok else c)[side]
                claims.setdefault((t, side), []).append((dist(end, at), num))
    for (t, side), cs in claims.items():
        for d, num in sorted(cs)[1:]:
            if old_line[t].off(int_at[num]) > 3:   # (unless it truly runs right by it)
                before[num].discard(t)
                dropped.append((num, t))
    label_of ={str(f["properties"]["number"]): f["properties"].get("sign") or f["properties"].get("code") for f in ints["features"]}
    for num, t in sorted(dropped, key=lambda x: label_of[x[0]] or ""):
        print("  (%s: %s really meets elsewhere)" % (label_of[num], results[t]["name"]))
    print("Taking OSM's line for %d of %d trails (%.1f of %.1f km)" % (
        len(ok), len(results), sum(results[k]["len_old"] for k in ok) / 1000, sum(r["len_old"] for r in results.values()) / 1000))

    # 2. Each intersection moves to where its trails' OSM lines meet (or onto its one OSM
    # line); our kept lines are pulled to it
    moves, problems = {}, []
    for f in ints["features"]:
        num = str(f["properties"]["number"])
        at = f["geometry"]["coordinates"]
        mine = sorted(before.get(num, ()))
        # (a trail that ran more than 12 m past it was only joined by the old loose 20 m
        # reach, like Milford Byway at B11, which really meets Highway Connector at B12)
        mine = [t for t in mine if ends_at(t, at) or Line(by_id[t]["geometry"]["coordinates"]).off(at) <= 12]
        osm = [t for t in mine if t in ok]
        if not osm:
            continue
        cands = [q for t in osm for q in results[t]["new"] if dist(q, at) <= INT_MOVE_M]
        cands += [lines[t].nearest(at)[1] for t in osm if lines[t].nearest(at)[0] <= INT_MOVE_M]
        kept_thru = [t for t in mine if t not in ok and not ends_at(t, at)]
        cands += [lines[u].nearest(q)[1] for q in list(cands) for u in osm + kept_thru if lines[u].nearest(q)[0] <= 5]
        cands += [lines[u].nearest(at)[1] for u in kept_thru if lines[u].nearest(at)[0] <= 5]
        if not cands:
            problems.append((f, "none of its OSM lines comes within %d m" % INT_MOVE_M))
            continue
        # on as many OSM lines as can be (a trail ending here gets joined anyway), near the old spot
        # (right on the lines running through it; a trail ending here gets a connector)
        # (on OSM's lines first; one of our kept lines through it bends to it if it must)
        best = min(cands, key=lambda q: (10 * sum(lines[t].off(q) for t in osm if not ends_at(t, at)) +
                                         3 * sum(lines[t].off(q) for t in kept_thru) +
                                         sum(lines[t].off(q) for t in osm if ends_at(t, at)) + 0.5 * dist(q, at)))
        # With only trails running through it left, it goes where a trail that really meets
        # nearby joins them, and takes it back (B13, beside the spot where Log Run joins
        # Milford Byway). With a trail ending at it, it stays (E1, with One Ledges).
        thru = [t for t in osm if not ends_at(t, at)]
        if thru and len(thru) == len(mine):
            joins_here = []
            for m, t in dropped:
                if m == num and t in ok:
                    e = osm_end(t, at)
                    if dist(e, at) <= INT_MOVE_M and all(lines[u].off(e) <= 1 for u in thru):
                        joins_here.append((dist(e, at), e, t))
            if joins_here:
                d, e, t = min(joins_here)
                best = e
                back = [u for dd, ee, u in joins_here if dist(ee, e) <= 3]
                before[num] = set(before[num]) | set(back)
                print("  (%s moves %.0f m to where %s join%s)" % (label_of[num], d, ", ".join(results[u]["name"] for u in back),
                                                                    "s" if len(back) == 1 else ""))
        if f["properties"].get("sign") and in_cr(best) != in_cr(at):
            problems.append((f, "would cross a CR line (%s to %s)" % (in_cr(at) or "off CR", in_cr(best) or "off CR")))
        if dist(best, at) > 0.5:
            moves[num] = (at, best)

    new_trails = json.loads(json.dumps(trails))
    nb = {f["properties"]["id"]: f for f in new_trails["features"]}
    new_ints = json.loads(json.dumps(ints))
    pos = {}
    for f in new_ints["features"]:
        num = str(f["properties"]["number"])
        if num in moves:
            f["geometry"]["coordinates"] = [round(moves[num][1][0], 7), round(moves[num][1][1], 7)]
        pos[num] = f["geometry"]["coordinates"]
    for k in ok:
        nb[k]["geometry"]["coordinates"] = [[round(x, 7), round(y, 7)] for x, y in results[k]["new"]]
        nb[k]["properties"]["osm_ways"] = sorted(set(results[k]["ways"]))
        ws = nb[k]["properties"].get("widths")
        if ws:   # meters along the trail: scaled to the new length
            s = results[k]["len_new"] / results[k]["len_old"]
            nb[k]["properties"]["widths"] = [[w[0], round(w[1] * s, 1), round(w[2] * s, 1)] + w[3:] for w in ws]
    pulled = []
    # Join every trail to its intersections: an end is joined to the one it ends at, and a
    # line running through gets a point right at it
    let_go = []
    for num, mine in before.items():
        for k in list(mine):
            c = nb[k]["geometry"]["coordinates"]
            at = int_at[num]
            if ends_at(k, at):
                old = by_id[k]["geometry"]["coordinates"]
                i = 0 if dist(old[0], at) <= dist(old[-1], at) else -1
                d = dist(c[i], pos[num])
                if d > 0.5:
                    if k not in ok or d <= 2:
                        c[i] = list(pos[num])
                    elif i == 0:
                        c.insert(0, list(pos[num]))
                    else:
                        c.append(list(pos[num]))
            elif Line(by_id[k]["geometry"]["coordinates"]).off(at) > 12:
                continue   # loose: left to go
            elif num in moves or k in ok:
                off = Line(c).off(pos[num])
                if k in ok and off > THRU_ON_M and results[k]["name"] in RELAXED | TRIMMED | USE_OSM and len(mine) > 2:
                    # an OSM line taken as it is, running past where the intersection had to
                    # go: it lets it go, and meets its neighbors where it really crosses them
                    mine.discard(k)
                    let_go.append((label_of[num], results[k]["name"], off))
                    continue
                if k in ok and off > THRU_ON_M:
                    problems.append((next(f for f in new_ints["features"] if str(f["properties"]["number"]) == num),
                                     "%s's OSM line passes %.0f m from it" % (results[k]["name"], off)))
                if k not in ok and off > 5:
                    pulled.append((results[k]["name"], label_of[num], off))
                nb[k]["geometry"]["coordinates"] = with_point(c, pos[num])

    # 3. Does every intersection still join the same trails?
    after = network(labeled(new_ints), new_trails)
    broken, loose = [], set()
    for f in new_ints["features"]:
        num = str(f["properties"]["number"])
        b, a = before.get(num, set()), after.get(num, set())
        label = f["properties"].get("sign") or f["properties"].get("code") or "#" + num
        # a trail more than 12 m away was only joined by the build's old loose 20 m reach
        far = {t for t in b - a if Line(by_id[t]["geometry"]["coordinates"]).off(int_at[num]) > 12}
        for t in sorted(far):
            loose.add((label, results[t]["name"]))
        if (b - far) != a:
            broken.append((label, num, sorted(results[t]["name"] for t in b - a - far), sorted(results[t]["name"] for t in a - b)))
    print("%d intersections move (farthest %.0f m)" % (len(moves), max((dist(o, n) for o, n in moves.values()), default=0)))
    for label, name in sorted(loose):
        print("  (%s no longer reaches %s, which was over 12 m away)" % (label, name))
    for label, name, off in sorted(let_go):
        print("  (%s lets %s go: its OSM line runs %.0f m past it)" % (label, name, off))
    for name, label, off in sorted(pulled, key=lambda x: -x[2]):
        print("  (our kept line of %s bends %.0f m to %s, where OSM's lines meet)" % (name, off, label))
    print("Problems to look at: %d" % len(problems))
    for f, why in problems:
        print("  %-5s %s" % (f["properties"].get("sign") or f["properties"].get("code"), why))
    print("Intersections joining different trails than before: %d" % len(broken))
    for label, num, lost, gained in broken:
        print("  %-5s lost %s%s" % (label, lost or "nothing", ", gained %s" % gained if gained else ""))
    kept = sorted((r["name"], r["len_old"], r["why"] or "its OSM match follows another trail") for k, r in results.items() if k not in ok)
    print("\nKeeping our line (drawn as a curve): %d trails, %.1f km" % (len(kept), sum(t[1] for t in kept) / 1000))
    for name, L, why in sorted(kept, key=lambda t: -t[1]):
        print("  %-30s %5.0f m  %s" % (name[:30], L, why))

    for k, r in results.items():
        if k in ok:
            r["why"] = None
    preview(results, moves, broken, ints)
    if "--write" in args:
        if broken and "--force" not in args:
            raise SystemExit("Not writing: fix the intersections above first (or --force, to fix them after)")
        with open(TRAILS, "w", encoding="utf-8") as f:
            f.write(json.dumps(new_trails, indent=2) + "\n")
        with open(INTS, "w", encoding="utf-8") as f:
            f.write(json.dumps(new_ints, indent=2) + "\n")
        print("Wrote %s and %s. Next: update sign_logos.csv positions, add_junctions.py --dry, build_map.py" % (TRAILS, INTS))


def preview(results, moves, broken, ints):
    """osm_geometry_preview.html: each trail's line before (red) and from OSM (blue)"""
    rows = []
    for k, r in sorted(results.items(), key=lambda kv: (kv[1]["why"] is not None, kv[1]["name"])):
        rows.append({"id": k, "name": r["name"], "why": r["why"], "old": [[p[1], p[0]] for p in r["old"]],
                     "new": [[p[1], p[0]] for p in r["new"]] if r["new"] else None,
                     "len": round(r["len_old"]), "wig": [round(r["wig_old"]), round(r["wig_new"]) if r["wig_new"] is not None else None]})
    mv = [{"from": [o[1], o[0]], "to": [n[1], n[0]]} for o, n in moves.values()]
    html = PREVIEW.replace("__ROWS__", json.dumps(rows)).replace("__MOVES__", json.dumps(mv)).replace(
        "__BROKEN__", json.dumps([b[0] for b in broken]))
    with open(os.path.join(PROJ, "osm_geometry_preview.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote osm_geometry_preview.html")


PREVIEW = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Trail lines from OSM</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 body{margin:0;font:13px system-ui,sans-serif;display:flex;height:100vh}
 #side{width:340px;overflow:auto;padding:10px;border-right:1px solid #ccc}
 #map{flex:1}
 .row{padding:4px 6px;border-radius:4px;cursor:pointer}
 .row:hover,.row.on{background:#e3f2fd}
 .row.no{color:#888}
 .sub{color:#666;font-size:11px}
 .key span{display:inline-block;width:18px;height:4px;vertical-align:middle;margin:0 4px 0 10px}
</style></head><body>
<div id="side"><h3 style="margin:4px 0">Trail lines from OSM</h3>
<div class="key"><span style="background:#e53935"></span>ours now<span style="background:#1565c0"></span>from OSM</div>
<p class="sub">Grey dots: intersections moved onto the new lines. Click a trail to zoom.</p>
<div id="list"></div></div><div id="map"></div>
<script>
var ROWS = __ROWS__, MOVES = __MOVES__, BROKEN = __BROKEN__;
var map = L.map("map");
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 20, maxNativeZoom: 19, attribution: "&copy; OSM"}).addTo(map);
var all = L.featureGroup().addTo(map), list = document.getElementById("list");
var matched = ROWS.filter(function(r) { return !r.why; }).length;
list.innerHTML = '<p><b>' + matched + '</b> of ' + ROWS.length + ' trails matched' +
  (BROKEN.length ? '; <b style="color:#c62828">' + BROKEN.length + ' intersections would change</b>: ' + BROKEN.join(", ") : '') + '</p>';
ROWS.forEach(function(r) {
  var old = L.polyline(r.old, {color: "#e53935", weight: 3, opacity: 0.8}).bindTooltip(r.name).addTo(all);
  var nw = r.new && !r.why ? L.polyline(r.new, {color: "#1565c0", weight: 3, opacity: 0.9}).bindTooltip(r.name + " (OSM)").addTo(all) : null;
  var d = document.createElement("div");
  d.className = "row" + (r.why ? " no" : "");
  d.innerHTML = '<b>' + r.name + '</b> <span class="sub">' + r.len + ' m' +
    (r.why ? ', not matched: ' + r.why : ', turning ' + r.wig[0] + '° → ' + r.wig[1] + '° per 100 m') + '</span>';
  d.onclick = function() {
    [].forEach.call(list.querySelectorAll(".row"), function(x) { x.classList.remove("on"); });
    d.classList.add("on");
    map.fitBounds((nw ? L.featureGroup([old, nw]) : old).getBounds().pad(0.3), {maxZoom: 19});
  };
  list.appendChild(d);
});
MOVES.forEach(function(m) {
  L.polyline([m.from, m.to], {color: "#555", weight: 1, dashArray: "2,3"}).addTo(all);
  L.circleMarker(m.to, {radius: 4, color: "#fff", weight: 1, fillColor: "#555", fillOpacity: 1}).addTo(all);
});
map.fitBounds(all.getBounds());
</script></body></html>"""


if __name__ == "__main__":
    main(sys.argv[1:])
