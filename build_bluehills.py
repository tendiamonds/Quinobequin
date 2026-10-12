"""
Build the Blue Hills Reservation trail map into bluehills/ (map.html, index.html, icons).

From bluehills_data/ (see bluehills_fetch.py and bluehills_pdf.py):
  osm_trails.json, osm_numbered.json, osm_parking.json, osm_roads.json, osm_routes.json   OpenStreetMap
  pdf_placed.json   numbers OSM doesn't have, placed from the park's trail map

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

from trailmap import build_map_page, dist_m
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

SECTIONS = {   # from the Friends of the Blue Hills
    "1": ("Great Blue Hill", "#1565c0"),
    "2": ("Houghton's Pond", "#00897b"),
    "3": ("Chickatawbut", "#6d4c41"),
    "4": ("Quincy", "#8e24aa"),
    "5": ("Ponkapoag", "#2e7d32"),
    "6": ("Fowl Meadow", "#ef6c00"),
}


def load(name):
    return json.load(open(os.path.join(DATA, name), encoding="utf-8"))


def reservation_ways(els, numbered_pts, route_names):
    """Trail ways in the reservation: not sidewalks or crossings, near a numbered intersection.
    A path with no name of its own takes its hiking route's (route_names: way -> name)."""
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
            ways.append({"name": t.get("name") or route_names.get(w["id"], ""), "highway": t.get("highway"), "surface": t.get("surface"),
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
    numbered = {e["id"]: e["tags"]["ref"] for e in load("osm_numbered.json")}
    numbered_ll = {e["tags"]["ref"]: (e["lon"], e["lat"]) for e in load("osm_numbered.json")}
    placed = load("pdf_placed.json")
    for n, v in placed.items():
        if v["node"]:
            numbered[v["node"]] = n
    numbered_pts = list(numbered_ll.values()) + [tuple(v["lonlat"]) for v in placed.values()]

    route_names = {m["ref"]: r["tags"]["name"] for r in load("osm_routes.json") if r.get("tags", {}).get("name")
                   for m in r["members"] if m["type"] == "way"}
    ways, nodes = reservation_ways(trails_osm, numbered_pts, route_names)
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
    ways = join_continuations(ways, numbered)

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

    # Trails, and which intersections lie along each, straight from the shared points
    trail_feats, tim = [], {}
    for ti, w in enumerate(ways):
        coords = [list(nodes[n]) for n in w["nodes"]]
        props = {"id": "osm_%d" % w["osm"] + ("_%d" % ti if w.get("road") else ""), "name": w["name"], "pdf_name": w["name"], "highway": w["highway"]}
        if w["surface"]:
            props["surface"] = w["surface"]
        if w.get("road"):
            props["road"] = True
            props["route_cost"] = ROAD_COST
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
        "otherMaps": [{"name": "Upper Charles Forest", "href": "../map.html"}],
        "zonesPage": False,
        "nav": ('<nav class="topnav"><a href="map.html" style="color:white;font-weight:700">Blue Hills Reservation</a>'
                '<span style="color:#f0b429;font-size:12px;font-weight:600">DRAFT</span>'
                '<a href="../map.html" style="margin-left:auto;opacity:0.8">Upper Charles &rarr;</a></nav>'),
    }
    os.makedirs(OUT, exist_ok=True)
    build_map_page(ints_fc, trails_fc, region, OUT, trail_int_map=tim)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write('<!DOCTYPE html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=map.html">'
                '<title>Blue Hills Reservation</title><a href="map.html">Blue Hills Reservation trail map</a>\n')
    make_favicon.make_icons(OUT, label="BH", color="#1f4e79", name="Blue Hills Reservation", short_name="Blue Hills")

    n_num = sum(1 for f in features if not f["properties"].get("no_sign"))
    n_est = sum(1 for f in features if f["properties"].get("estimated"))
    print("Blue Hills: %d trails (%d named, %d road links), %d numbered intersections (%d estimated), %d unsigned junctions, %d entries" % (
        len(trail_feats), sum(1 for w in ways if w["name"]), sum(1 for w in ways if w.get("road")), n_num, n_est, jn,
        sum(1 for f in features if f["properties"].get("entry"))))


if __name__ == "__main__":
    main()
