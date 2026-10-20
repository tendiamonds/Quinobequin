"""
Build the Blue Hills Reservation trail map into bluehills/ (map.html, index.html, icons).

From bluehills_data/ (see bluehills_fetch.py and bluehills_pdf.py):
  osm_trails.json, osm_numbered.json, osm_parking.json, osm_roads.json, osm_routes.json   OpenStreetMap
  pdf_placed.json   numbers OSM doesn't have, placed from the park's trail map
  pdf_names.json    names for paths OSM leaves unnamed, from the park map's labels (bluehills_names.py)
  pdf_blazes.json   the blazed trails' symbols on the park map (bluehills_blazes.py)
  pdf_widths.json   narrow trail, wide trail, and unpaved road lines on the park map (bluehills_widths.py)

OpenStreetMap trails already meet at shared points, so the network comes straight from
them. Many trails end at a road and pick up again across or along it, so short
stretches of road between trail ends become road links (drawn dashed, and routing
avoids them a little), as does the shortest road walk from any part of the network
that would otherwise be cut off (Ponkapoag, across I-93) to the rest. Trail pieces that only continue each other (same name, nothing else there) are
joined into one trail, and every other place trails meet is an intersection, numbered
if it has a Blue Hills number and an unsigned junction otherwise.

Intersection numbers are four digits; the first is the section (zone).
"""

import collections
import heapq
import json
import math
import os

from checks import build_checks_page
from trailmap import build_map_page, dist_m, maps_menu_html
import make_favicon

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"
DATA = os.path.join(PROJ, "bluehills_data")
OUT = os.path.join(PROJ, "bluehills")
NEAR_NUMBERED_M = 250    # trails this close to a numbered intersection are the reservation's
ENTRY_LOT_M = 200        # a parking lot this close to a numbered intersection makes it an entry
ROAD_LINK_M = 400        # longest stretch of road kept as a link between trails
ROAD_COST = 1.5          # routing counts road links as this much longer than they are
BRIDGE_M = 1000          # longest road walk that joins a cut-off part of the network
LOT_ROAD_M = 150         # an unnamed lot is "off" the nearest named road this close
ATTACH_M = 60            # a number the park map puts off any junction joins a trail point this close

# The blazed trails, as the park map's legend has them. style: how the map app draws
# them; one_way: marked in one direction only (counterclockwise)
# terrain: how rough a narrow trail with this blaze is (TERRAIN), from the legend's ratings
BLAZES = {
    "skyline": {"name": "Skyline Trail", "marks": "blue blazes", "color": "#1e88e5", "style": "blazes", "terrain": 3},
    "yellow_dots": {"name": "Yellow Dot Loop", "marks": "yellow dots", "color": "#fdd835", "style": "dots", "terrain": 0},
    "green_dots": {"name": "Green Dot Loop", "marks": "green dots", "color": "#43a047", "style": "dots", "terrain": 1},
    "red_dots": {"name": "Red Dot Loop", "marks": "red dots", "color": "#e53935", "style": "dots", "terrain": 2},
    "white_arrows": {"name": "Forest Path Loop", "marks": "white triangles", "color": "#ffffff", "style": "arrows",
                     "one_way": True, "terrain": 1},
    "yellow_arrows": {"name": "Breakneck Ledge Loop", "marks": "yellow triangles", "color": "#fdd835", "style": "arrows",
                      "one_way": True, "terrain": 2},
}
# The park map shows how wide each trail is, which says a lot about its terrain: a wide
# trail or unpaved road is easy going, a narrow trail rougher, and how rough depends on its
# blaze (BLAZES terrain). The map app works out the terrain from these.
WIDTHS = {"road": "Unpaved road", "wide": "Wide trail", "narrow": "Narrow trail"}
TERRAIN = ["Easy", "Moderate", "Challenging", "Difficult"]
WIDTH_STEP_M = 10        # trails are checked this often
WIDTH_NEAR_M = 30        # a park map line this close, running the same way, is this trail
WIDTH_MIN_M = 40         # shorter stretches of one width join their neighbors
OSM_WIDTH = {"track": "wide", "bridleway": "wide", "service": "road", "path": "narrow", "footway": "narrow", "cycleway": "wide"}
BLAZE_SNAP_M = 45        # a symbol this close to a trail point is marking it
BLAZE_LINK_M = {"skyline": 30, "dots": 80, "arrows": 450}   # neighboring symbols are this close
BLAZE_DETOUR = 1.6       # the trail between neighbors is at most this much longer than straight
BLAZE_DETOUR_ARROWS = 3.1   # ...or for triangles, joined only to the next one they point at, this
                            # much, on trails (not roads): enough for a hairpin between two
                            # (2129 to 2135, by 2132)
BLAZE_GAP_M = 60         # an unmarked gap this short inside a blazed stretch is blazed too
BLAZE_MIN_M = 30         # shorter blazed stretches are dropped

# Things to check on the ground before fixing them in OpenStreetMap (see
# bluehills_osm_fixes.md): OSM takes corrections from someone who's seen the sign or
# trail, not from the park's map. This map already uses the corrected versions.
OSM_FIX_LOOK = ("the number on the intersection sign (the four-digit number on a post or tree "
                "at the junction).")
FIELD_CHECKS = [
    {"id": "osm-3153", "label": "3153", "lat": 42.223661, "lon": -71.045687,
     "question": "What number is on the sign at this junction?",
     "choices": ["3153", "5153", "Another number (note it)", "No sign"],
     "why": "OpenStreetMap numbers this sign 5153, but 5xxx is the Ponkapoag section, south of I-93. This "
            "junction is in Chickatawbut (3xxx), next to 3151 and 3152, and the park map has 3153 here.",
     "look_for": OSM_FIX_LOOK},
    {"id": "osm-3157", "label": "3157", "lat": 42.223442, "lon": -71.045101,
     "question": "What number is on the sign at this junction?",
     "choices": ["3157", "5157", "Another number (note it)", "No sign"],
     "why": "OpenStreetMap numbers this sign 5157; the park map has 3157 here, about 50 m from 3153.",
     "look_for": OSM_FIX_LOOK},
    {"id": "osm-5422", "label": "5422", "lat": 42.198533, "lon": -71.074663,
     "question": "Is the 5422 sign here, where Middle Road meets the Pipe Line?",
     "choices": ["Yes, it's here", "No, it's 150 m west, at Middle Road and Wannamanhut Path", "Not at either", "Can't tell"],
     "why": "OpenStreetMap puts 5422 about 150 m west, where Middle Road meets Wannamanhut Path. The park "
            "map puts it here, on the straight Pipe Line between 5425 (north) and 5421 (south).",
     "look_for": "the 5422 sign at this junction. If it isn't here, walk west along Middle Road to the "
                 "next junction and check there, and note what number (if any) each junction has."},
    {"id": "osm-4048", "label": "4048", "lat": 42.231346, "lon": -71.061380,
     "question": "Heading north from 4048 (toward 4049, 4046 and 4066), is this the Pipe Line or Headquarters Path?",
     "choices": ["Pipe Line", "Headquarters Path", "Can't tell"],
     "why": "OpenStreetMap calls the whole track Headquarters Path, from 4012 all the way north past 4066. "
            "The park map labels it Headquarters Path only up to 4048, and the Pipe Line from 4048 north.",
     "look_for": "a trail-name sign at 4048 or along the northern stretch, or a gas-pipeline marker "
                 "post along the corridor. \"It's obviously the pipeline corridor\" counts too: note it."},
    {"id": "osm-5343", "label": "5343", "lat": 42.196356, "lon": -71.089654,
     "question": "Is the trail from here east to 5370 (along the green dots) Acton Path, or Prescott Foot Path?",
     "choices": ["Acton Path", "Prescott Foot Path", "Something else (note it)", "No name posted"],
     "why": "OpenStreetMap has Prescott Foot Path continuing past 5343 to 5370. The park map labels "
            "5343 to 5370 Acton Path, the north side of the Acton Path loop around Ponkapoag Pond.",
     "look_for": "a trail-name sign at 5343 or at 5370 (east end). If there's none, note that too."},
]

SECTIONS = {   # from the Friends of the Blue Hills
    "1": ("Great Blue Hill", "#1565c0"),
    "2": ("Houghton's Pond", "#00897b"),
    "3": ("Chickatawbut", "#6d4c41"),
    "4": ("Quincy", "#8e24aa"),
    "5": ("Ponkapoag", "#2e7d32"),
    "6": ("Fowl Meadow", "#ef6c00"),
}


# Numbers OpenStreetMap has wrong. 5153 and 5157 sit in Chickatawbut (section 3), next to
# 3151 and 3152, right where the park map has 3153 and 3157.
OSM_NUMBER_FIXES = {"5153": "3153", "5157": "3157"}
# Numbers OpenStreetMap has on the wrong junction: number -> the right OSM point. The park
# map has 5422 where Middle Road meets the Pipe Line; OSM has it 150 m west, where Middle
# Road meets Wannamanhut Path.
OSM_NODE_FIXES = {"5422": 1564733307}
# Trail names OpenStreetMap has wrong, where the park map's label sits on the trail: OSM
# way -> name. 5343 to 5370 is the north side of the Acton Path loop, not Prescott Foot Path.
OSM_NAME_FIXES = {503099008: "Acton Path"}
# OSM ways that are two trails: way -> (the numbered intersection where they meet, the
# name of the part after it). Way 9113729 is Headquarters Path up to 4048 and Pipe Line
# from there north, as the park map labels them.
OSM_WAY_SPLITS = {9113729: ("4048", "Pipe Line")}


# The checks page's base look (the Upper Charles pages share theirs from build_map.py)
CHECKS_CSS = """
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #222; background: #fafafa; }
  a { color: #0277bd; }
  .container { max-width: 760px; margin: 0 auto; padding: 20px; }
  h1 { font-size: 22px; margin: 4px 0; }
  .subtitle { color: #666; margin-bottom: 18px; font-size: 14px; }
  nav.topnav { background: #2c3e50; padding: 10px 20px; display: flex; gap: 18px; align-items: center; flex-wrap: wrap; }
  nav.topnav a { text-decoration: none; }
"""


def load(name):
    return json.load(open(os.path.join(DATA, name), encoding="utf-8"))


def load_numbered():
    """OpenStreetMap's numbered junctions, [(number, node, (lon, lat))], with OSM_NUMBER_FIXES
    and OSM_NODE_FIXES"""
    raw = load("osm_numbered.json")
    refs = {e["tags"]["ref"] for e in raw}
    for wrong, right in OSM_NUMBER_FIXES.items():
        if wrong not in refs or right in refs:
            print("  note: OSM_NUMBER_FIXES %s -> %s may no longer be needed (OSM has changed)" % (wrong, right))
    out = [(OSM_NUMBER_FIXES.get(e["tags"]["ref"], e["tags"]["ref"]), e["id"], (e["lon"], e["lat"])) for e in raw]
    moved = {e["id"]: (e["lon"], e["lat"]) for e in load("osm_trails.json")
             if e["type"] == "node" and e["id"] in OSM_NODE_FIXES.values()}
    for num, node in OSM_NODE_FIXES.items():
        if node not in moved:
            raise RuntimeError("OSM_NODE_FIXES: point %d for %s is no longer in the OSM trails" % (node, num))
    out = [(num, OSM_NODE_FIXES[num], moved[OSM_NODE_FIXES[num]]) if num in OSM_NODE_FIXES else (num, node, ll)
           for num, node, ll in out]
    for i, what in ((0, "number"), (1, "point")):
        dup = [k for k, c in collections.Counter(x[i] for x in out).items() if c > 1]
        if dup:
            raise RuntimeError("OSM numbered junctions: the same %s twice: %s" % (what, dup))
    return out


def reservation_ways(els, numbered_pts, route_names):
    """Trail ways in the reservation: not sidewalks or crossings, near a numbered intersection.
    A path with no name of its own takes its hiking route's, or the park map's
    (route_names: way -> name)."""
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in els if e["type"] == "node"}
    grid = collections.defaultdict(list)
    for p in numbered_pts:
        grid[(int(p[0] * 400), int(p[1] * 400))].append(p)

    def near(p):
        gx, gy = int(p[0] * 400), int(p[1] * 400)
        return any(dist_m(p[0], p[1], q[0], q[1]) <= NEAR_NUMBERED_M
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in grid[(gx + dx, gy + dy)])
    ways = []
    for w in els:
        t = w.get("tags", {}) if w["type"] == "way" else None
        if t is None or t.get("footway") in ("sidewalk", "crossing") or t.get("cycleway") == "sidewalk":
            continue
        pts = [nodes[n] for n in w["nodes"] if n in nodes]
        if len(pts) >= 2 and any(near(p) for p in pts[::3] + [pts[-1]]):
            ways.append({"name": OSM_NAME_FIXES.get(w["id"]) or t.get("name") or route_names.get(w["id"], ""), "highway": t.get("highway"), "surface": t.get("surface"),
                         "nodes": [n for n in w["nodes"] if n in nodes], "osm": w["id"]})
    return ways, nodes


def road_links(roads_osm, ways, nodes):
    """Stretches of road no longer than ROAD_LINK_M from one trail point to another"""
    nodes.update({e["id"]: (e["lon"], e["lat"]) for e in roads_osm if e["type"] == "node"})
    on_trail = {n for w in ways for n in w["nodes"]}
    links = []
    for r in roads_osm:
        if r["type"] != "way":
            continue
        t = r.get("tags", {})
        ns = [n for n in r["nodes"] if n in nodes]
        hits = [k for k, n in enumerate(ns) if n in on_trail]
        for a, b in zip(hits, hits[1:]):
            piece = ns[a:b + 1]
            length = sum(dist_m(*nodes[p], *nodes[q]) for p, q in zip(piece, piece[1:]))
            if 0 < length <= ROAD_LINK_M:
                links.append({"name": t.get("name") or "Road", "highway": t.get("highway"), "surface": t.get("surface"),
                              "nodes": piece, "osm": r["id"], "road": True})
    return links


def bridge_gaps(roads_osm, ways, nodes, numbered):
    """Road walks joining each cut-off part of the network that has numbered
    intersections to the nearest other part, until nothing more joins"""
    graph = collections.defaultdict(list)
    tags = {}
    for r in roads_osm:
        if r["type"] == "way":
            tags[r["id"]] = r.get("tags", {})
            ns = [n for n in r["nodes"] if n in nodes]
            for a, b in zip(ns, ns[1:]):
                d = dist_m(*nodes[a], *nodes[b])
                graph[a].append((b, d, r["id"]))
                graph[b].append((a, d, r["id"]))
    links = []
    while True:
        parent = {}

        def root(x):
            while parent.setdefault(x, x) != x:
                x = parent[x]
            return x
        for w in ways + links:
            for a, b in zip(w["nodes"], w["nodes"][1:]):
                parent[root(a)] = root(b)
        members = collections.defaultdict(set)
        for n in parent:
            members[root(n)].add(n)
        counts = collections.Counter(root(n) for n in numbered if n in parent)
        main = max(counts, key=counts.get)
        added = False
        for c in counts:
            if c == main:
                continue
            # Shortest road walk out of this part to any other
            best = {n: 0 for n in members[c]}
            prev, queue, hit = {}, [(0, n) for n in members[c]], None
            heapq.heapify(queue)
            while queue:
                d, a = heapq.heappop(queue)
                if d > best.get(a, math.inf) or d > BRIDGE_M:
                    continue
                if a in parent and root(a) != c:
                    hit = a
                    break
                for b, w, rid in graph[a]:
                    if d + w < best.get(b, math.inf):
                        best[b], prev[b] = d + w, (a, rid)
                        heapq.heappush(queue, (d + w, b))
            if hit is not None:
                # One link per road along the walk
                steps, a = [], hit
                while a in prev:
                    steps.append((prev[a][0], a, prev[a][1]))
                    a = prev[a][0]
                steps.reverse()
                for k, (a, b, rid) in enumerate(steps):
                    if k and steps[k - 1][2] == rid:
                        links[-1]["nodes"].append(b)
                    else:
                        t = tags[rid]
                        links.append({"name": t.get("name") or "Road", "highway": t.get("highway"),
                                      "surface": t.get("surface"), "nodes": [a, b], "osm": rid, "road": True})
                added = True
                break   # parts have changed; look again
        if not added:
            return links


def blaze_runs(ways, nodes, symbols):
    """Which stretches of which trails each blaze marks: {way index: [[blaze, from m,
    to m, direction]]}, direction +1 or -1 along the trail for one-way blazes, else 0.

    Each symbol marks the trail point nearest it. Between a symbol and its neighbors (the
    nearest few, or for a triangle the next one the way it points) the blaze follows the
    shortest way along the trails, if that isn't much longer than straight across; a much
    longer way means one of the two is really on another trail."""
    graph = collections.defaultdict(list)
    for wi, w in enumerate(ways):
        for k, (a, b) in enumerate(zip(w["nodes"], w["nodes"][1:])):
            d = dist_m(*nodes[a], *nodes[b])
            graph[a].append((b, d, wi, k, 1))
            graph[b].append((a, d, wi, k, -1))
    cell = 0.001
    grid = collections.defaultdict(list)
    for n in graph:
        grid[(int(nodes[n][0] / cell), int(nodes[n][1] / cell))].append(n)

    def snap(ll):
        gx, gy = int(ll[0] / cell), int(ll[1] / cell)
        near = [(dist_m(*ll, *nodes[n]), n) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for n in grid[(gx + dx, gy + dy)]]
        best = min(near, default=None)
        return best[1] if best and best[0] <= BLAZE_SNAP_M else None

    def between(a, b, limit, trails_only=False):
        """The trail edges from a to b, [(way, edge, direction)], if no longer than limit
        (and with trails_only, not along a road)"""
        best, prev, queue = {a: 0}, {}, [(0, a)]
        while queue:
            d, u = heapq.heappop(queue)
            if u == b:
                steps = []
                while u in prev:
                    u, step = prev[u]
                    steps.append(step)
                return steps
            if d > best.get(u, math.inf):
                continue
            for v, w, wi, k, sign in graph[u]:
                if trails_only and ways[wi].get("road"):
                    continue
                if d + w <= limit and d + w < best.get(v, math.inf):
                    best[v], prev[v] = d + w, (u, (wi, k, sign))
                    heapq.heappush(queue, (d + w, v))
        return None

    marked = collections.defaultdict(collections.Counter)    # (blaze, way) -> edge -> direction votes
    for blaze, syms in symbols.items():
        style = BLAZES[blaze]["style"]
        link = BLAZE_LINK_M["skyline" if style == "blazes" else style]
        pts = [(s[0], s[1]) for s in syms]
        at = [snap(p) for p in pts]
        for i, p in enumerate(pts):
            if at[i] is None:
                continue
            near = sorted((dist_m(*p, *q), j) for j, q in enumerate(pts) if j != i and at[j] is not None and dist_m(*p, *q) <= link)
            h = syms[i][2]
            if style == "arrows" and h is not None:
                # The next triangle ahead, the way this one points
                ahead = [(d, j) for d, j in near
                         if abs((math.degrees(math.atan2((pts[j][0] - p[0]) * 82000, (pts[j][1] - p[1]) * 111000)) - h + 180) % 360 - 180) <= 60]
                near = ahead[:1]
            else:
                near = near[:2]
            for d, j in near:
                limit = max(BLAZE_DETOUR * d, d + 60)
                steps = between(at[i], at[j], limit)
                if steps is None and style == "arrows":
                    steps = between(at[i], at[j], max(BLAZE_DETOUR_ARROWS * d, limit), trails_only=True)
                for wi, k, sign in steps or []:
                    marked[(blaze, wi)][k] += sign if style == "arrows" else 0
                    marked[(blaze, wi)].setdefault(k, 0)
    runs = collections.defaultdict(list)
    for (blaze, wi), edges in marked.items():
        w = ways[wi]["nodes"]
        cum = [0.0]
        for a, b in zip(w, w[1:]):
            cum.append(cum[-1] + dist_m(*nodes[a], *nodes[b]))
        ks = sorted(edges)
        groups = [[ks[0]]]
        for k in ks[1:]:
            if cum[k] - cum[groups[-1][-1] + 1] <= BLAZE_GAP_M:
                groups[-1].append(k)
            else:
                groups.append([k])
        for g in groups:
            s0, s1 = cum[g[0]], cum[g[-1] + 1]
            if s1 - s0 >= BLAZE_MIN_M:
                vote = sum(edges[k] for k in g)
                runs[wi].append([blaze, round(s0), round(s1), (vote > 0) - (vote < 0)])
    return runs


def width_runs(ways, nodes, widths):
    """How wide each trail is along its length: {way index: [[width, from m, to m]]}, from
    the park map's lines, or where it has none, from OpenStreetMap's kind of path"""
    cell = 0.0005
    grid = collections.defaultdict(list)
    for kind, pts in widths.items():
        for lon, lat, bearing in pts:
            grid[(int(lon / cell), int(lat / cell))].append((lon, lat, bearing, kind))
    runs = {}
    for wi, w in enumerate(ways):
        pts = [nodes[n] for n in w["nodes"]]
        fallback = "road" if w.get("road") else OSM_WIDTH.get(w["highway"], "narrow")
        # Sample along the trail: (meters along, width)
        seq, s = [], 0.0
        for a, b in zip(pts, pts[1:]):
            d = dist_m(*a, *b)
            bearing = math.degrees(math.atan2((b[0] - a[0]) * 82000, (b[1] - a[1]) * 111000)) % 180
            k = 0
            while k * WIDTH_STEP_M < d or (k == 0 and d > 0):
                t = min(1, (k * WIDTH_STEP_M + WIDTH_STEP_M / 2) / d) if d else 0
                p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
                gx, gy = int(p[0] / cell), int(p[1] / cell)
                near = [(dist_m(*p, q[0], q[1]), q[3]) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in grid[(gx + dx, gy + dy)]
                        if min(abs(q[2] - bearing), 180 - abs(q[2] - bearing)) <= 35]
                best = min(near, default=None)
                seq.append([s + min(d, k * WIDTH_STEP_M + WIDTH_STEP_M / 2), best[1] if best and best[0] <= WIDTH_NEAR_M else None])
                k += 1
            s += d
        if not w.get("road"):
            # Smooth: each sample takes the most common width around it
            kinds = [k for _, k in seq]
            for i in range(len(seq)):
                around = collections.Counter(k for k in kinds[max(0, i - 2):i + 3] if k)
                seq[i][1] = around.most_common(1)[0][0] if around else fallback
        else:
            seq = [[at, "road"] for at, _ in seq]
        out = []
        for at, kind in seq:
            if out and out[-1][0] == kind:
                out[-1][2] = at
            else:
                out.append([kind, at, at])
        # Stretch the runs to meet, then fold short ones into the run before (or after)
        for i in range(len(out)):
            out[i][1] = 0 if i == 0 else (out[i - 1][2] + out[i][1]) / 2
        for i in range(len(out) - 1):
            out[i][2] = out[i + 1][1]
        if out:
            out[-1][2] = s
        merged = []
        for r in out:
            if merged and (r[2] - r[1] < WIDTH_MIN_M or merged[-1][0] == r[0]):
                merged[-1][2] = r[2]
            elif merged and merged[-1][2] - merged[-1][1] < WIDTH_MIN_M:
                merged[-1] = [r[0], merged[-1][1], r[2]]
            else:
                merged.append(list(r))
        runs[wi] = [[k, round(a), round(b)] for k, a, b in merged]
    return runs


def name_continuations(ways, numbered):
    """An unnamed trail piece that only continues a named one (meeting end to end, nothing
    else there) is the same trail, so takes its name"""
    touch = collections.Counter(n for w in ways for n in set(w["nodes"]))
    ends = collections.defaultdict(list)
    for w in ways:
        if not w.get("road"):
            ends[w["nodes"][0]].append(w)
            ends[w["nodes"][-1]].append(w)
    changed = True
    while changed:
        changed = False
        for n, ws in ends.items():
            if len(ws) == 2 and touch[n] == 2 and n not in numbered and bool(ws[0]["name"]) != bool(ws[1]["name"]):
                named, unnamed = ws if ws[0]["name"] else ws[::-1]
                unnamed["name"] = named["name"]
                changed = True
    return ways


def join_continuations(ways, numbered):
    """Join pieces that only continue each other: same name and kind (trail or road link),
    meeting end to end, with no other trail and no number at the meeting point"""
    ends = collections.defaultdict(list)    # node -> ways ending there
    touch = collections.Counter()           # node -> number of ways through or ending there
    for i, w in enumerate(ways):
        ends[w["nodes"][0]].append(i)
        ends[w["nodes"][-1]].append(i)
        for n in set(w["nodes"]):
            touch[n] += 1
    alive = set(range(len(ways)))
    changed = True
    while changed:
        changed = False
        for n, ws in list(ends.items()):
            ws = [i for i in ws if i in alive]
            if len(ws) == 2 and ws[0] != ws[1] and touch[n] == 2 and n not in numbered and \
                    ways[ws[0]]["name"] == ways[ws[1]]["name"] and ways[ws[0]].get("road") == ways[ws[1]].get("road"):
                a, b = ways[ws[0]], ways[ws[1]]
                an = a["nodes"] if a["nodes"][-1] == n else a["nodes"][::-1]
                bn = b["nodes"] if b["nodes"][0] == n else b["nodes"][::-1]
                a["nodes"] = an + bn[1:]
                alive.discard(ws[1])
                ends[n] = []
                other = bn[-1]
                ends[other] = [ws[0] if i == ws[1] else i for i in ends[other]]
                changed = True
    return [ways[i] for i in sorted(alive)]


def main():
    trails_osm = load("osm_trails.json")
    numbered = {node: num for num, node, ll in load_numbered()}
    numbered_ll = {num: ll for num, node, ll in load_numbered()}
    placed = load("pdf_placed.json")
    for n, v in placed.items():
        if v["node"]:
            numbered[v["node"]] = n
    numbered_pts = list(numbered_ll.values()) + [tuple(v["lonlat"]) for v in placed.values()]

    route_names = {int(w): name for w, name in load("pdf_names.json").items()}
    route_names.update({m["ref"]: r["tags"]["name"] for r in load("osm_routes.json") if r.get("tags", {}).get("name")
                        for m in r["members"] if m["type"] == "way"})
    ways, nodes = reservation_ways(trails_osm, numbered_pts, route_names)
    node_of = {num: node for node, num in numbered.items()}
    for w in list(ways):
        if w["osm"] in OSM_WAY_SPLITS:
            at, name = OSM_WAY_SPLITS[w["osm"]]
            k = w["nodes"].index(node_of[at]) if node_of.get(at) in w["nodes"] else -1
            if not 0 < k < len(w["nodes"]) - 1:
                raise RuntimeError("OSM_WAY_SPLITS: %s isn't partway along way %d any more" % (at, w["osm"]))
            ways.append(dict(w, name=name, nodes=w["nodes"][k:], part=2))
            w["nodes"] = w["nodes"][:k + 1]
    # Numbers the park map puts off any junction: onto the nearest trail point, if close
    on_trail = {n for w in ways for n in w["nodes"]} - set(numbered)
    for num, v in placed.items():
        if not v["node"]:
            near = min(on_trail, key=lambda n: dist_m(*v["lonlat"], *nodes[n]))
            if dist_m(*v["lonlat"], *nodes[near]) <= ATTACH_M:
                v["node"] = near
                numbered[near] = num
                on_trail.discard(near)
    roads_osm = load("osm_roads.json")
    ways += road_links(roads_osm, ways, nodes)
    ways += bridge_gaps(roads_osm, ways, nodes, numbered)
    ways = join_continuations(name_continuations(ways, numbered), numbered)

    # Intersections: numbered points, and anywhere two or more trails meet
    on = collections.defaultdict(set)
    for i, w in enumerate(ways):
        for n in w["nodes"]:
            on[n].add(i)
    points = [n for n in on if len(on[n]) >= 2 or n in numbered]
    label, features = {}, []
    jn = 0
    estimated = {n for n, v in placed.items()}
    for n in points:
        if n in numbered:
            num = numbered[n]
            label[n] = num
            props = {"label": num, "sign": num, "zone": num[0], "number": n}
            if num in estimated:
                props["estimated"] = True
        else:
            jn += 1
            label[n] = "J%d" % jn
            props = {"label": label[n], "code": label[n], "zone": "", "no_sign": True, "junction": True, "number": n}
        features.append({"type": "Feature", "properties": props,
                         "geometry": {"type": "Point", "coordinates": list(nodes[n])}})
    # Numbers the park map has but with no OSM junction near: where the map puts them
    for num, v in placed.items():
        if not v["node"]:
            features.append({"type": "Feature", "properties": {"label": num, "sign": num, "zone": num[0], "estimated": True},
                             "geometry": {"type": "Point", "coordinates": list(v["lonlat"])}})
    # A junction's zone: its nearest numbered neighbor's, for coloring the dot behind it
    signed = [(f["geometry"]["coordinates"], f["properties"]["zone"]) for f in features if not f["properties"].get("no_sign")]
    for f in features:
        if f["properties"].get("junction"):
            c = f["geometry"]["coordinates"]
            f["properties"]["zone"] = min(signed, key=lambda s: dist_m(c[0], c[1], s[0][0], s[0][1]))[1]

    # Entry points: the numbered intersection nearest each parking lot, if close enough.
    # Most lots have no name in OpenStreetMap; those go by the road they're off.
    road_pts = [(nodes[n], r["tags"]["name"]) for r in roads_osm if r["type"] == "way" and r.get("tags", {}).get("name")
                and r["tags"].get("highway") != "service" for n in r["nodes"] if n in nodes]

    def lot_name(lot, ll):
        if lot.get("tags", {}).get("name"):
            return lot["tags"]["name"]
        d, road = min((dist_m(*ll, *q), name) for q, name in road_pts)
        return "lot off " + road if d <= LOT_ROAD_M else None
    by_label = {f["properties"]["label"]: f for f in features if not f["properties"].get("no_sign")}
    for lot in load("osm_parking.json"):
        ll = (lot.get("lon") or lot.get("center", {}).get("lon"), lot.get("lat") or lot.get("center", {}).get("lat"))
        if ll[0] is None:
            continue
        best = min(by_label.values(), key=lambda f: dist_m(ll[0], ll[1], *f["geometry"]["coordinates"]))
        if dist_m(ll[0], ll[1], *best["geometry"]["coordinates"]) <= ENTRY_LOT_M:
            p = best["properties"]
            p["entry"] = True
            p["parking"] = True
            name = lot_name(lot, ll)
            if name and not p.get("connects"):
                p["connects"] = name
            # Driving directions go to the lot itself (the first lot found for this entry)
            if not p.get("drive_to"):
                p["drive_to"] = [round(ll[0], 6), round(ll[1], 6)]
                if name:
                    p["parking_name"] = name[0].upper() + name[1:]

    # Trails, and which intersections lie along each, straight from the shared points
    blazes = blaze_runs(ways, nodes, load("pdf_blazes.json"))
    widths = width_runs(ways, nodes, load("pdf_widths.json"))
    trail_feats, tim = [], {}
    for ti, w in enumerate(ways):
        coords = [list(nodes[n]) for n in w["nodes"]]
        props = {"id": "osm_%d" % w["osm"] + ("_%d" % ti if w.get("road") else "_b" if w.get("part") else ""), "name": w["name"], "pdf_name": w["name"], "highway": w["highway"]}
        if w["surface"]:
            props["surface"] = w["surface"]
        if w.get("road"):
            props["road"] = True
            props["route_cost"] = ROAD_COST
        if blazes.get(ti):
            props["blazes"] = sorted(blazes[ti], key=lambda r: r[1])
        if widths.get(ti):
            props["widths"] = widths[ti]
        trail_feats.append({"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}})
        cum, s, ints = [0.0], 0.0, []
        for k in range(1, len(coords)):
            s += dist_m(coords[k - 1][0], coords[k - 1][1], coords[k][0], coords[k][1])
            cum.append(s)
        for k, n in enumerate(w["nodes"]):
            if n in label and (not ints or ints[-1][0] != label[n]):
                ints.append([label[n], round(cum[k])])
        tim[ti] = {"length": round(s), "ints": ints}

    # Intersections with something to check get a link to it in the map
    checks_at = {c["label"]: c["question"] for c in FIELD_CHECKS}
    for f in features:
        if f["properties"].get("label") in checks_at:
            f["properties"]["check"] = checks_at[f["properties"]["label"]]
    ints_fc = {"type": "FeatureCollection", "features": features}
    trails_fc = {"type": "FeatureCollection", "features": trail_feats}
    lons = [c[0] for f in trail_feats for c in f["geometry"]["coordinates"]]
    lats = [c[1] for f in trail_feats for c in f["geometry"]["coordinates"]]
    region = {
        "name": "Blue Hills Reservation",
        "zones": {z: {"name": n, "color": c} for z, (n, c) in SECTIONS.items()},
        "view": {"center": [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2], "zoom": 13},
        "bounds": [[min(lats), min(lons)], [max(lats), max(lons)]],
        "storagePrefix": "bh",
        "report": {"email": "tendiamonds@gmail.com", "signReports": True},
        "otherMaps": [{"name": "Upper Charles Forest", "href": "../map.html"}],
        "zonesPage": False,
        "dem": os.path.join(PROJ, "elevation_cache", "bluehills.tif"),
        "blazes": BLAZES,
        "widths": WIDTHS,
        "terrain": TERRAIN,
        "nav": ('<nav class="topnav"><a href="map.html" style="color:white;font-weight:700">Blue Hills Reservation</a>'
                '<a href="checks.html" style="color:#ecf0f1;font-size:14px">Checks</a>'
                + maps_menu_html("bh", "../") + '</nav>'),
    }
    os.makedirs(OUT, exist_ok=True)
    build_map_page(ints_fc, trails_fc, region, OUT, trail_int_map=tim)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write('<!DOCTYPE html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=map.html">'
                '<title>Blue Hills Reservation</title><a href="map.html">Blue Hills Reservation trail map</a>\n')
    make_favicon.make_icons(OUT, label="BH", color="#1f4e79", name="Blue Hills Reservation", short_name="Blue Hills")
    build_checks_page(FIELD_CHECKS, os.path.join(OUT, "checks.html"), title="Field Checks — Blue Hills Reservation",
                      subtitle="OpenStreetMap mistakes to confirm on the ground, nearest first. Answers are kept on "
                               "this phone until you send them. Once you've confirmed one, here's "
                               '<a href="https://github.com/tendiamonds/Quinobequin/blob/master/bluehills_osm_fixes.md">'
                               "how to fix it in OpenStreetMap</a>.",
                      css=CHECKS_CSS, nav=region["nav"], storage_prefix=region["storagePrefix"],
                      email=region["report"]["email"])

    for k in WIDTHS:
        print("  %-14s %.1f km" % (k, sum(r[2] - r[1] for rs in widths.values() for r in rs if r[0] == k) / 1000))
    for b in BLAZES:
        km = sum(r[2] - r[1] for rs in blazes.values() for r in rs if r[0] == b) / 1000
        print("  %-14s %.1f km" % (b, km))
    n_num = sum(1 for f in features if not f["properties"].get("no_sign"))
    n_est = sum(1 for f in features if f["properties"].get("estimated"))
    print("Blue Hills: %d trails (%d named, %d road links), %d numbered intersections (%d estimated), %d unsigned junctions, %d entries" % (
        len(trail_feats), sum(1 for w in ways if w["name"]), sum(1 for w in ways if w.get("road")), n_num, n_est, jn,
        sum(1 for f in features if f["properties"].get("entry"))))


if __name__ == "__main__":
    main()
