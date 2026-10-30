"""
Build the Blue Hills Reservation trail map into bluehills/ (map.html, index.html, icons).

From bluehills_data/ (see bluehills_fetch.py):
  dcr_trails.geojson, dcr_intersections.geojson   the Massachusetts DCR's own trail data:
                      the lines, with names, blazes, loops and widths, and the numbered
                      intersections (what the park's trail map is drawn from)
  osm_roads.json, osm_parking.json                 OpenStreetMap's roads and parking lots

DCR's trail pieces meet at shared points, so the network comes straight from them, but it
stops at the public roads: each section is an island. So a trail end close to a road is
tied onto it, short stretches of road between trail ends become road links (drawn dashed,
and routing avoids them a little), as does the shortest road walk from any part of the
network that would otherwise be cut off (Ponkapoag, across I-93) to the rest. Pieces that
only continue each other (same name, nothing else there) are joined into one trail, and
every other place trails meet is an intersection, numbered if DCR numbers it and an
unsigned junction otherwise.

Intersection numbers are four digits; the first is the section (zone).
"""

import collections
import heapq
import json
import math
import os

from reports import build_reports_page
from trailmap import build_map_page, dist_m, maps_menu_html
import make_favicon

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"
DATA = os.path.join(PROJ, "bluehills_data")
OUT = os.path.join(PROJ, "bluehills")
ENTRY_LOT_M = 200        # a parking lot this close to a numbered intersection makes it an entry
ROAD_LINK_M = 400        # longest stretch of road kept as a link between trails
ROAD_COST = 1.5          # routing counts road links as this much longer than they are
BRIDGE_M = 1000          # longest road walk that joins a cut-off part of the network
LOT_ROAD_M = 150         # an unnamed lot is "off" the nearest named road this close
ATTACH_M = 60            # a number off DCR's lines joins the nearest line point this close
LOOSE_END_M = 3          # a line end this close to another line's point meets it
ROAD_TIE_M = 25          # a dead-end trail this close to a road meets it
FIRST_NODE = 9 * 10 ** 12   # DCR's points get ids from here, clear of OpenStreetMap's

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
# DCR's blaze colors (BLAZECOLOR, several joined by "/") as BLAZES
DCR_BLAZES = {"Blue": "skyline", "Yellow": "yellow_dots", "Green": "green_dots", "Red": "red_dots",
              "White Triangle": "white_arrows", "Yellow Triangle": "yellow_arrows"}
# How wide each trail is says a lot about its terrain: a wide trail or road is easy going, a
# narrow trail rougher, and how rough depends on its blaze (BLAZES terrain). The map app
# works out the terrain from these.
WIDTHS = {"road": "Unpaved road", "paved": "Paved", "wide": "Wide trail", "narrow": "Narrow trail"}
DCR_WIDTHS = {"Narrow Trail": "narrow", "Boardwalk": "narrow", "Wide Trail": "wide", "Unpaved Road": "road",
              "Paved Road": "paved", "Paved Path": "paved", "Paved Bridge": "paved"}
TERRAIN = ["Easy", "Moderate", "Challenging", "Difficult"]

SECTIONS = {   # from the Friends of the Blue Hills
    "1": ("Great Blue Hill", "#1565c0"),
    "2": ("Houghton's Pond", "#00897b"),
    "3": ("Chickatawbut", "#6d4c41"),
    "4": ("Quincy", "#8e24aa"),
    "5": ("Ponkapoag", "#2e7d32"),
    "6": ("Fowl Meadow", "#ef6c00"),
}


# The checks page's base look (the Upper Charles pages share theirs from build_map.py)
CHECKS_CSS = """
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #222; background: #fafafa; }
  a { color: #0277bd; }
  .container { max-width: 760px; margin: 0 auto; padding: 20px; }
  h1 { font-size: 22px; margin: 4px 0; }
  .subtitle { color: #666; margin-bottom: 18px; font-size: 14px; }
  nav.topnav { background: #2c3e50; padding: 10px 20px; display: flex; gap: 18px; align-items: center; flex-wrap: wrap; }
  @media (max-width: 420px) { nav.topnav { gap: 12px; padding: 10px 12px; } nav.topnav a { font-size: 13px; } }   /* one row on a phone */
  nav.topnav a { text-decoration: none; }
"""


def load(name):
    return json.load(open(os.path.join(DATA, name), encoding="utf-8"))


def dcr_ways():
    """DCR's trail pieces as ways over shared points: ([{name, surface, nodes, dcr, width,
    blazes}], {node: (lon, lat)}). A piece's end that misses the point it meets by a little
    (LOOSE_END_M) is joined to it."""
    nodes, ids = {}, {}

    def node(c):
        k = (round(c[0], 7), round(c[1], 7))
        if k not in ids:
            ids[k] = FIRST_NODE + len(ids)
            nodes[ids[k]] = (c[0], c[1])
        return ids[k]
    ways = []
    for f in load("dcr_trails.geojson")["features"]:
        p, cs = f["properties"], f["geometry"]["coordinates"]
        ns = [node(c) for c in cs]
        ns = [n for i, n in enumerate(ns) if i == 0 or n != ns[i - 1]]
        if len(ns) < 2:
            continue
        colors = [c.strip() for c in (p.get("BLAZECOLOR") or "").split("/") if c.strip()]
        unknown = [c for c in colors if c not in DCR_BLAZES]
        if unknown:
            print("  note: DCR blaze color %s on piece %s isn't in DCR_BLAZES; left off" % (unknown, p["FID"]))
        ways.append({"name": (p.get("NAME") or "").strip(), "surface": (p.get("SURFACE") or "").strip() or None,
                     "nodes": ns, "dcr": p["FID"], "width": DCR_WIDTHS.get(p.get("MAP_SYMBOL"), "narrow"),
                     "blazes": sorted({DCR_BLAZES[c] for c in colors if c in DCR_BLAZES})})
    # Loose ends: onto the nearest point of another piece, if close
    ends = collections.Counter(n for w in ways for n in (w["nodes"][0], w["nodes"][-1]))
    inner = {n for w in ways for n in w["nodes"][1:-1]}
    cell = 0.0003
    grid = collections.defaultdict(set)
    for wi, w in enumerate(ways):
        for n in w["nodes"]:
            grid[(int(nodes[n][0] / cell), int(nodes[n][1] / cell))].add((n, wi))
    for wi, w in enumerate(ways):
        for k in (0, -1):
            n = w["nodes"][k]
            if ends[n] == 1 and n not in inner:
                gx, gy = int(nodes[n][0] / cell), int(nodes[n][1] / cell)
                near = [(dist_m(*nodes[n], *nodes[m]), m) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                        for m, wj in grid[(gx + dx, gy + dy)] if wj != wi and m != n]
                best = min(near, default=None)
                if best and best[0] <= LOOSE_END_M:
                    w["nodes"][k] = best[1]
    loop_directions(ways, nodes)
    return ways, nodes


def loop_directions(ways, nodes):
    """Which way each piece of a one-way loop runs: w["dirs"] = {blaze: +1 or -1 along the
    piece's points, or 0 both ways}. The loops run counterclockwise (the park map's legend).
    A loop's pieces form its ring: the small gaps where DCR doesn't mark the blaze are
    jumped (each open end to the nearest other, an odd one out to the nearest piece), spurs off it (walked out and back) are
    marked both ways, and of the ways round what's left, the longest is the loop; its
    outline says which way round is counterclockwise. A piece off it (a second way between
    two of its points) runs from the one the loop reaches first."""
    for w in ways:
        w["dirs"] = {}
    for key, bl in BLAZES.items():
        if not bl.get("one_way"):
            continue
        pieces = [w for w in ways if key in w["blazes"]]
        if not pieces:
            continue
        # The ring's graph: piece ends as points, pieces (and gap jumps) as edges
        edges = [(w["nodes"][0], w["nodes"][-1], w) for w in pieces]
        deg = collections.Counter(n for e in edges for n in e[:2])
        loose = [n for n, c in deg.items() if c == 1]
        pairs = sorted((dist_m(*nodes[x], *nodes[y]), x, y) for i, x in enumerate(loose) for y in loose[i + 1:])
        used = set()
        for d, x, y in pairs:
            if x not in used and y not in used:
                edges.append((x, y, None))
                used |= {x, y}
        # (an odd one out joins the nearest end of another of the loop's pieces)
        for x in loose:
            if x not in used:
                own = next(w for w in pieces if x in (w["nodes"][0], w["nodes"][-1]))
                y = min((m for w in pieces if w is not own for m in (w["nodes"][0], w["nodes"][-1])),
                        key=lambda m: dist_m(*nodes[x], *nodes[m]))
                edges.append((x, y, None))
        # Spurs: peel off ends that still lead nowhere
        alive = list(range(len(edges)))
        while True:
            deg = collections.Counter(n for i in alive for n in edges[i][:2])
            leaf = [i for i in alive if deg[edges[i][0]] == 1 or deg[edges[i][1]] == 1]
            if not leaf:
                break
            for i in leaf:
                if edges[i][2]:
                    edges[i][2]["dirs"][key] = 0
            alive = [i for i in alive if i not in leaf]
        if not alive:
            continue
        # The ring: the longest way round. Runs of edges between branch points (or the
        # whole ring, if it has none) are its building blocks.
        length = {i: (sum(dist_m(*nodes[x], *nodes[y]) for x, y in zip(edges[i][2]["nodes"], edges[i][2]["nodes"][1:]))
                      if edges[i][2] else dist_m(*nodes[edges[i][0]], *nodes[edges[i][1]])) for i in alive}
        at = collections.defaultdict(list)
        for i in alive:
            at[edges[i][0]].append(i)
            at[edges[i][1]].append(i)
        branch = [n for n in at if len(at[n]) > 2] or [edges[alive[0]][0]]
        runs, seen = [], set()
        for n0 in branch:
            for i0 in at[n0]:
                if i0 in seen:
                    continue
                run, n, i = [], n0, i0
                while True:
                    x, y, w = edges[i]
                    run.append((i, 1 if x == n else -1))
                    seen.add(i)
                    n = y if x == n else x
                    if n in branch:
                        break
                    i = next(j for j in at[n] if j != i)
                runs.append((n0, n, run))
        # Every way round through the runs (there are only a few), the longest kept
        best = None
        run_len = [sum(length[i] for i, _ in run) for u, v, run in runs]

        def search(start, n, used, path, total):
            nonlocal best
            for r, (u, v, run) in enumerate(runs):
                if r in used or n not in (u, v):
                    continue
                forward = n == u
                other = v if forward else u
                step, size = path + [(r, forward)], total + run_len[r]
                if other == start:
                    if best is None or size > best[0]:
                        best = (size, step)
                else:
                    search(start, other, used | {r}, step, size)
        for r, (u, v, run) in enumerate(runs):
            if u == v:   # a run that comes back to where it began is a way round by itself
                if best is None or run_len[r] > best[0]:
                    best = (run_len[r], [(r, True)])
            else:
                search(u, v, {r}, [(r, True)], run_len[r])
        walked, order, pts = {}, {}, []
        for r, forward in best[1]:
            u, v, run = runs[r]
            order.setdefault(u if forward else v, len(order))
            for i, way in (run if forward else [(i, -d) for i, d in run[::-1]]):
                walked[i] = way
                x, y, w = edges[i]
                ns = w["nodes"] if w else [x, y]
                pts += [nodes[m] for m in (ns if way > 0 else ns[::-1])]
        area = sum(p[0] * 82000 * q[1] * 111000 - q[0] * 82000 * p[1] * 111000 for p, q in zip(pts, pts[1:] + pts[:1]))
        turn = 1 if area > 0 else -1
        for r, (u, v, run) in enumerate(runs):
            # Off the ring: a second way between two of its points, from the one reached first
            forward = order.get(u, 1e9) <= order.get(v, 1e9)
            for i, way in run:
                if i not in walked:
                    walked[i] = way if forward else -way
        for i in alive:
            if edges[i][2]:
                edges[i][2]["dirs"][key] = walked[i] * turn


def tie_to_roads(ways, nodes, roads_osm):
    """Trails that end near a road (DCR's lines stop at the public roads) meet it: each such
    end gets a point on the road, put into the road's line and added to the trail's end"""
    nodes.update({e["id"]: (e["lon"], e["lat"]) for e in roads_osm if e["type"] == "node"})
    roads = [r for r in roads_osm if r["type"] == "way"]
    cell = 0.002
    grid = collections.defaultdict(set)
    for ri, r in enumerate(roads):
        for a, b in zip(r["nodes"], r["nodes"][1:]):
            if a in nodes and b in nodes:
                for c in (nodes[a], nodes[b]):
                    grid[(int(c[0] / cell), int(c[1] / cell))].add(ri)
    touch = collections.Counter(n for w in ways for n in set(w["nodes"]))
    inserts = collections.defaultdict(list)    # road index -> [(segment, t, node)]
    tied = 0
    for w in ways:
        for k in (0, -1):
            n = w["nodes"][k]
            if touch[n] != 1:
                continue
            px, py = nodes[n][0] * 82000, nodes[n][1] * 111000
            gx, gy = int(nodes[n][0] / cell), int(nodes[n][1] / cell)
            best = None
            for ri in {ri for dx in (-1, 0, 1) for dy in (-1, 0, 1) for ri in grid[(gx + dx, gy + dy)]}:
                rn = roads[ri]["nodes"]
                for s in range(len(rn) - 1):
                    if rn[s] not in nodes or rn[s + 1] not in nodes:
                        continue
                    ax, ay = nodes[rn[s]][0] * 82000, nodes[rn[s]][1] * 111000
                    vx, vy = nodes[rn[s + 1]][0] * 82000 - ax, nodes[rn[s + 1]][1] * 111000 - ay
                    l2 = vx * vx + vy * vy
                    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / l2)) if l2 else 0.0
                    d = math.hypot(px - ax - t * vx, py - ay - t * vy)
                    if best is None or d < best[0]:
                        best = (d, ri, s, t)
            if best and best[0] <= ROAD_TIE_M:
                d, ri, s, t = best
                rn = roads[ri]["nodes"]
                a, b = nodes[rn[s]], nodes[rn[s + 1]]
                m = FIRST_NODE * 2 + len(nodes)
                nodes[m] = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
                inserts[ri].append((s, t, m))
                if k == 0:
                    w["nodes"].insert(0, m)
                else:
                    w["nodes"].append(m)
                tied += 1
    for ri, ins in inserts.items():
        rn = roads[ri]["nodes"]
        for s, t, m in sorted(ins, reverse=True):
            rn.insert(s + 1, m)
    return tied


def road_links(roads_osm, ways, nodes):
    """Stretches of road no longer than ROAD_LINK_M from one trail point to another"""
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
            cut = [c for c in counts if c != main]
            if cut:
                print("  note: %d part(s) of the network with numbered intersections stay cut off" % len(cut))
            return links


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


def flipped(edges):
    """A way's edges the other way along it: in reverse order, one-way directions turned"""
    return [(width, keys, surf, tuple((k, -d) for k, d in dirs)) for width, keys, surf, dirs in edges[::-1]]


def join_continuations(ways, numbered):
    """Join pieces that continue each other: the same kind (trail or road link) meeting end
    to end, either with nothing else there (no other trail, no number) and the same name,
    or, where other trails meet them too, the only two pieces there of one named trail
    (DCR ends its pieces at every junction; a trail runs on through). Each piece's own
    width, blazes and surface stay with its stretch (edges: one per pair of points)."""
    for w in ways:
        w["edges"] = [(w.get("width"), tuple(w.get("blazes", ())), w.get("surface"),
                       tuple(sorted(w.get("dirs", {}).items())))] * (len(w["nodes"]) - 1)
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
            pair = None
            if len(ws) == 2 and ws[0] != ws[1] and touch[n] == 2 and n not in numbered and \
                    ways[ws[0]]["name"] == ways[ws[1]]["name"] and ways[ws[0]].get("road") == ways[ws[1]].get("road"):
                pair = ws
            else:
                same = collections.defaultdict(list)
                for i in ws:
                    if ways[i]["name"] and not ways[i].get("road"):
                        same[ways[i]["name"]].append(i)
                pair = next((v for v in same.values() if len(v) == 2 and v[0] != v[1]), None)
            if pair:
                a, b = ways[pair[0]], ways[pair[1]]
                fa, fb = a["nodes"][-1] == n, b["nodes"][0] == n
                an, ae = (a["nodes"], a["edges"]) if fa else (a["nodes"][::-1], flipped(a["edges"]))
                bn, be = (b["nodes"], b["edges"]) if fb else (b["nodes"][::-1], flipped(b["edges"]))
                a["nodes"], a["edges"] = an + bn[1:], ae + be
                alive.discard(pair[1])
                ends[n] = [i for i in ends[n] if i not in pair]
                other = bn[-1]
                ends[other] = [pair[0] if i == pair[1] else i for i in ends[other]]
                changed = True
    return [ways[i] for i in sorted(alive)]


def runs_along(w, nodes):
    """A joined way's widths ([[width, from m, to m]]), blazes ([[blaze, from m, to m,
    direction]], direction +1 or -1 along it for the one-way loops (loop_directions), else
    0), and the surface covering most of it, from its edges"""
    cum = [0.0]
    for a, b in zip(w["nodes"], w["nodes"][1:]):
        cum.append(cum[-1] + dist_m(*nodes[a], *nodes[b]))
    widths, blazes, surface = [], [], collections.Counter()
    for k, (width, keys, surf, dirs) in enumerate(w["edges"]):
        s0, s1 = cum[k], cum[k + 1]
        width = width or ("road" if w.get("road") else None)
        if surf:
            surface[surf] += s1 - s0
        if width:
            if widths and widths[-1][0] == width:
                widths[-1][2] = s1
            else:
                widths.append([width, s0, s1])
        for key in keys:
            way = dict(dirs).get(key, 0)
            last = next((r for r in reversed(blazes) if r[0] == key), None)
            if last and abs(last[2] - s0) < 0.01 and last[3] == way:
                last[2] = s1
            else:
                blazes.append([key, s0, s1, way])
    widths = [[k, round(a), round(b)] for k, a, b in widths]
    blazes = sorted(([k, round(a), round(b), d] for k, a, b, d in blazes if b - a >= 1), key=lambda r: (r[1], r[0]))
    return widths, blazes, (surface.most_common(1)[0][0] if surface else None)


def main():
    ways, nodes = dcr_ways()

    # The numbered intersections, onto the line point they sit on (or the nearest, if close)
    numbered, placed_off = {}, []
    cell = 0.0003
    grid = collections.defaultdict(set)
    for w in ways:
        for n in w["nodes"]:
            grid[(int(nodes[n][0] / cell), int(nodes[n][1] / cell))].add(n)
    for f in load("dcr_intersections.geojson")["features"]:
        num = str(f["properties"]["INT_NUMBER"]).strip()
        c = f["geometry"]["coordinates"]
        gx, gy = int(c[0] / cell), int(c[1] / cell)
        near = [(dist_m(c[0], c[1], *nodes[n]), n) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for n in grid[(gx + dx, gy + dy)]
                if n not in numbered]
        best = min(near, default=None)
        if best and best[0] <= ATTACH_M:
            numbered[best[1]] = num
        else:
            placed_off.append((num, c))
    if placed_off:
        print("  note: %d DCR number(s) not on any line, placed where DCR has them: %s" % (len(placed_off), ", ".join(n for n, c in placed_off)))
    dup = [k for k, v in collections.Counter(numbered.values()).items() if v > 1]
    if dup:
        raise RuntimeError("DCR intersections: the same number twice: %s" % dup)

    roads_osm = load("osm_roads.json")
    tied = tie_to_roads(ways, nodes, roads_osm)
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
    for n in points:
        if n in numbered:
            num = numbered[n]
            label[n] = num
            props = {"label": num, "sign": num, "zone": num[0], "number": n}
        else:
            jn += 1
            label[n] = "J%d" % jn
            props = {"label": label[n], "code": label[n], "zone": "", "no_sign": True, "junction": True, "number": n}
        features.append({"type": "Feature", "properties": props,
                         "geometry": {"type": "Point", "coordinates": list(nodes[n])}})
    for num, c in placed_off:
        features.append({"type": "Feature", "properties": {"label": num, "sign": num, "zone": num[0], "estimated": True},
                         "geometry": {"type": "Point", "coordinates": c}})
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
    trail_feats, tim = [], {}
    total = collections.Counter()
    for ti, w in enumerate(ways):
        coords = [list(nodes[n]) for n in w["nodes"]]
        widths, blazes, surface = runs_along(w, nodes)
        props = {"id": ("osm_%d_%d" % (w["osm"], ti)) if w.get("road") else "dcr_%d" % w["dcr"], "name": w["name"], "pdf_name": w["name"]}
        if w.get("highway"):
            props["highway"] = w["highway"]
        if surface:
            props["surface"] = surface
        if w.get("road"):
            props["road"] = True
            props["route_cost"] = ROAD_COST
        if blazes:
            props["blazes"] = blazes
        if widths:
            props["widths"] = widths
        for r in blazes:
            total[r[0]] += r[2] - r[1]
        for r in widths:
            total["width " + r[0]] += r[2] - r[1]
        trail_feats.append({"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}})
        cum, s, ints = [0.0], 0.0, []
        for k in range(1, len(coords)):
            s += dist_m(coords[k - 1][0], coords[k - 1][1], coords[k][0], coords[k][1])
            cum.append(s)
        for k, n in enumerate(w["nodes"]):
            if n in label and (not ints or ints[-1][0] != label[n]):
                ints.append([label[n], round(cum[k])])
        tim[ti] = {"length": round(s), "ints": ints}

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
        "checks": [],
        # DCR marks each piece's blazes, so they already run piece to piece; not snapped
        "blazeStops": None,
        "otherMaps": [{"name": "Upper Charles", "href": "../map.html"}],
        "zonesPage": False,
        "dem": os.path.join(PROJ, "elevation_cache", "bluehills.tif"),
        "blazes": BLAZES,
        "widths": WIDTHS,
        "terrain": TERRAIN,
        "credit": 'Trails: <a href="https://www.mass.gov/orgs/department-of-conservation-recreation">Massachusetts DCR</a>',
        "nav": ('<nav class="topnav"><a href="map.html" style="color:white;font-weight:700">Blue Hills Reservation</a>'
                '<a href="reports.html" style="color:#ecf0f1;font-size:14px">Reports</a>'
                + maps_menu_html("bh", "../") + '</nav>'),
    }
    os.makedirs(OUT, exist_ok=True)
    build_map_page(ints_fc, trails_fc, region, OUT, trail_int_map=tim)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write('<!DOCTYPE html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=map.html">'
                '<title>Blue Hills Reservation</title><a href="map.html">Blue Hills Reservation trail map</a>\n')
    make_favicon.make_icons(OUT, label="BH", color="#1f4e79", name="Blue Hills Reservation", short_name="Blue Hills")
    build_reports_page(os.path.join(OUT, "reports.html"), title="Reports — Blue Hills Reservation", css=CHECKS_CSS,
                       nav=region["nav"], storage_prefix=region["storagePrefix"], email=region["report"]["email"],
                       blazes=BLAZES, checks=[])

    for k in WIDTHS:
        print("  %-14s %.1f km" % (k, total["width " + k] / 1000))
    for b in BLAZES:
        print("  %-14s %.1f km" % (b, total[b] / 1000))
    n_num = sum(1 for f in features if not f["properties"].get("no_sign"))
    print("Blue Hills: %d trails (%d named, %d road links), %d numbered intersections, %d unsigned junctions, %d entries; %d trail ends tied to roads" % (
        len(trail_feats), sum(1 for w in ways if w["name"]), sum(1 for w in ways if w.get("road")), n_num, jn,
        sum(1 for f in features if f["properties"].get("entry")), tied))


if __name__ == "__main__":
    main()
