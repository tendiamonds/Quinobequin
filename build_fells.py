"""
Build the Middlesex Fells map (fells/map.html), from OpenStreetMap (fells_data/, from
fells_fetch.py): the trails inside the reservation's boundary, their blazes from OSM's
route relations for the marked trails (Skyline, Reservoir, Cross Fells...: each relation's
member ways carry its color), parking for the ways in, and I-93 to split the West Fells
from the East Fells.

The intersections are the Fells' own numbers, on posts at the trail junctions and on DCR's
trail map: the map's grid square and a number (C5-17), which OpenStreetMap has on its
junction points (ref). A way in without a number is drawn as a small picture of the trails
meeting there (as at Saratoga), labeled by its zone (W or E and a number); other junctions
(mostly on unofficial paths) are quiet ones, for routing.

Only the official trails: OpenStreetMap also has the user-created paths DCR asks people to
stay off (and is closing), so a path is kept only where it follows DCR's own trail lines
(fells_data/dcr_trails.geojson, what DCR's trail map shows), or is part of a marked trail.
DCR's inventory of points (dcr_points.geojson) adds its parking areas OSM doesn't have.
Nor any trail mostly on water-supply land with no public access (water_supply.geojson, from
MassGIS: Winchester's around its reservoirs, and MWRA's at the Fells Reservoir), unless
it's a marked trail (those run along its edges).
"""

import collections
import json
import os
import re

import make_favicon
from build_bluehills import dist_m, road_links, bridge_gaps, name_continuations, join_continuations, runs_along, CHECKS_CSS
from build_saratoga import inside, drop_small_networks
from reports import build_reports_page
from trailmap import build_map_page, maps_menu_html

PROJ = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(PROJ, "fells_data")
OUT = os.path.join(PROJ, "fells")

ZONES = {"W": ("West Fells", "#2e7d32"), "E": ("East Fells", "#6a1b9a")}
TRAIL_KINDS = {"path", "footway", "track", "bridleway", "cycleway", "steps"}
ENTRY_LOT_M = 120        # a parking lot this close to a trail point makes it an entrance
DCR_LOT_M = 60           # a DCR parking area this close to an OSM lot is the same lot
LOT_ROAD_M = 150         # an unnamed lot is "off" the nearest named road this close
MIN_NETWORK_M = 400      # smaller cut-off bits of trail are left out
OFFICIAL_M = 15          # a path point this close to a DCR trail line is on it...
OFFICIAL_SHARE = 0.6     # ...and a path this much on them is an official trail
STEP_M = 5               # lines are looked at this often along them
RESTRICTED_SHARE = 0.5   # an unmarked path this much on no-access land is left out
ROAD_COST = 1.5

# The marked trails: OpenStreetMap's route relations, by name, and their blazes. A trail
# keeps its own key (the legend lists the trails, as at the Blue Hills), so two white-blazed
# trails are two rows. Colors are OSM's (osmc:symbol, else colour); relations not here
# (unmarked paths, bike routes through town) give no blazes.
# The legend uses DCR's names (its trail map's "Trail Loops"); Long Pond's color is DCR's
# (OSM has it pink).
ROUTES = {
    "Skyline Trail": ("skyline", "white", "Skyline Trail"),
    "Reservoir Trail": ("reservoir", "orange", "Reservoir Trail"),
    "Long Pond Nature Trail": ("long_pond", "yellow", "Long Pond Nature Trail"),
    "Mountain Bike Loop": ("mountain_bike", "green", "Mountain Bike Loop"),
    "Cross Fells Trail": ("cross_fells", "blue", "Cross Fells Trail"),
    "Crystal Spring Trail": ("crystal_spring", "red", "Crystal Spring Trail"),
    "Historic Trail": ("historic", "yellow", "Spot Pond Brook Historic Trail"),
    "Rock Circuit Trail": ("rock_circuit", "white", "Rock Circuit Trail"),
    "Rock Circuit Connector": ("rock_circuit_connector", "orange", "Rock Circuit Connector"),
    "Virginia Wood Trail": ("virginia_wood", "red", "Virginia Wood Trail"),
}
NUMBER = re.compile(r"^[A-G][0-9]-[0-9]+$")   # an intersection's number, as on its post
COLORS = {"white": "#ffffff", "orange": "#fb8c00", "blue": "#1e88e5", "green": "#43a047", "red": "#e53935",
          "yellow": "#fdd835"}
BLAZES = {key: {"name": shown, "marks": color + " blazes", "color": COLORS[color], "style": "blazes"}
          for key, color, shown in ROUTES.values()}


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def boundary_rings():
    """The reservation's outer rings, [(lon, lat), ...], joined up from the relation's
    outer member ways (each is only a piece of a ring)"""
    rel = next(e for e in load("osm_boundary.json") if e["type"] == "relation")
    pieces = [[(p["lon"], p["lat"]) for p in m["geometry"]] for m in rel["members"]
              if m["type"] == "way" and m.get("role") == "outer" and m.get("geometry")]
    rings = []
    while pieces:
        ring = pieces.pop(0)
        while ring[0] != ring[-1]:
            for i, p in enumerate(pieces):
                if p[0] == ring[-1]:
                    ring += p[1:]
                elif p[-1] == ring[-1]:
                    ring += p[::-1][1:]
                else:
                    continue
                pieces.pop(i)
                break
            else:
                break   # an open ring (a gap in the data): close it straight across
        rings.append(ring)
    return rings


def divide_at(lat, divide):
    """I-93's longitude at a latitude (the middle of its two carriageways), from the
    motorway's segments that cross it; None away from it"""
    hits = []
    for seg in divide:
        for (x1, y1), (x2, y2) in zip(seg, seg[1:]):
            if (y1 - lat) * (y2 - lat) <= 0 and y1 != y2:
                hits.append(x1 + (x2 - x1) * (lat - y1) / (y2 - y1))
    return sum(hits) / len(hits) if hits else None


def side_of(pt, divide):
    x = divide_at(pt[1], divide)
    return "W" if x is None or pt[0] < x else "E"


def fells_ways(els, rings):
    """The trails: paths and tracks with a point inside the reservation (no sidewalks or
    crossings, nothing private), with their route memberships for blazes"""
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in els if e["type"] == "node"}
    ways = []
    for w in els:
        t = w.get("tags", {}) if w["type"] == "way" else None
        if t is None or t.get("highway") not in TRAIL_KINDS:
            continue
        if t.get("footway") in ("sidewalk", "crossing", "link") or t.get("access") in ("private", "no"):
            continue
        ns = [n for n in w["nodes"] if n in nodes]
        if len(ns) < 2 or not any(inside(nodes[n], r) for r in rings for n in ns[::2] + [ns[-1]]):
            continue
        ways.append({"name": t.get("name", ""), "highway": t.get("highway"), "surface": t.get("surface"),
                     "nodes": ns, "osm": w["id"]})
    return ways, nodes


def along(pts, step=STEP_M):
    """Points every step meters along a line of (lon, lat)"""
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        k = max(1, int(dist_m(*a, *b) / step))
        out += [(a[0] + (b[0] - a[0]) * i / k, a[1] + (b[1] - a[1]) * i / k) for i in range(1, k + 1)]
    return out


def official(ways, nodes):
    """The ways that are official trails: on DCR's trail lines (OFFICIAL_SHARE of them
    within OFFICIAL_M), or part of a marked trail"""
    cell = 0.0003   # about 25-33 m
    grid = collections.defaultdict(list)
    for f in load("dcr_trails.geojson")["features"]:
        g = f["geometry"]
        for line in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]):
            for q in along([tuple(c[:2]) for c in line]):
                grid[(int(q[0] / cell), int(q[1] / cell))].append(q)
    def near(q):
        gx, gy = int(q[0] / cell), int(q[1] / cell)
        return any(dist_m(*q, *r) <= OFFICIAL_M for dx in (-1, 0, 1) for dy in (-1, 0, 1) for r in grid[(gx + dx, gy + dy)])
    keep = []
    for w in ways:
        pts = along([nodes[n] for n in w["nodes"]])
        if w["blazes"] or sum(map(near, pts)) >= OFFICIAL_SHARE * len(pts):
            keep.append(w)
    return keep


def open_to_all(ways, nodes):
    """The ways not mostly on water-supply land the public can't enter (marked trails
    always: they run along its edges)"""
    rings = []
    for f in load("water_supply.geojson")["features"]:
        g = f["geometry"]
        for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            ring = [tuple(c[:2]) for c in poly[0]]
            xs, ys = [c[0] for c in ring], [c[1] for c in ring]
            rings.append((ring, (min(xs), min(ys), max(xs), max(ys))))
    def closed(q):
        return any(b[0] <= q[0] <= b[2] and b[1] <= q[1] <= b[3] and inside(q, r) for r, b in rings)
    keep = []
    for w in ways:
        pts = along([nodes[n] for n in w["nodes"]])
        if w["blazes"] or sum(map(closed, pts)) < RESTRICTED_SHARE * len(pts):
            keep.append(w)
    return keep


def route_blazes(ways):
    """Each way's blazes, from the marked trails' relations it's in; an unnamed way takes
    its first marked trail's name"""
    on = collections.defaultdict(list)
    for r in load("osm_routes.json"):
        name = r.get("tags", {}).get("name")
        if r["type"] == "relation" and name in ROUTES:
            for m in r["members"]:
                if m["type"] == "way":
                    on[m["ref"]].append(name)
    for w in ways:
        names = sorted(set(on.get(w["osm"], [])), key=list(ROUTES).index)
        w["blazes"] = tuple(ROUTES[n][0] for n in names)
        if names and not w["name"]:
            w["name"] = names[0]


def numbers(els, ways):
    """{node: its intersection number}, for the numbered points on the trails (one point
    per number: OSM has C7-1 twice, 6 m apart)"""
    on = {n for w in ways for n in w["nodes"]}
    out, seen = {}, set()
    for e in els:
        ref = e.get("tags", {}).get("ref", "") if e["type"] == "node" else ""
        if NUMBER.match(ref) and e["id"] in on and ref not in seen:
            out[e["id"]] = ref
            seen.add(ref)
    return out


def main():
    rings = boundary_rings()
    divide = [[(p["lon"], p["lat"]) for p in w["geometry"]] for w in load("osm_divide.json") if w.get("geometry")]
    els = load("osm_trails.json")
    ways, nodes = fells_ways(els, rings)
    route_blazes(ways)
    unofficial = len(ways)
    ways = official(ways, nodes)
    unofficial -= len(ways)
    restricted = len(ways)
    ways = open_to_all(ways, nodes)
    restricted -= len(ways)
    roads_osm = load("osm_roads.json")
    for e in roads_osm:
        if e["type"] == "node":
            nodes.setdefault(e["id"], (e["lon"], e["lat"]))
    ways = drop_small_networks(ways, nodes)
    numbered = numbers(els, ways)
    ways += road_links(roads_osm, ways, nodes)
    # Where trails stop at a road without meeting across it (Woodland Road, between Spot
    # Pond and the East Fells), the walk along the road that joins them
    ways += bridge_gaps(roads_osm, ways, nodes, numbered)
    ways = join_continuations(name_continuations(ways, numbered), numbered)

    # Intersections: where three or more trail ends meet. Where one trail just becomes
    # another, a quiet junction (no icon), so routes and trail details still know it.
    degree = collections.Counter()
    on = collections.defaultdict(set)
    for i, w in enumerate(ways):
        for k, n in enumerate(w["nodes"]):
            on[n].add(i)
            degree[n] += 1 if k in (0, len(w["nodes"]) - 1) else 2
    points = {n for n in on if len(on[n]) >= 2 or degree[n] >= 3} | set(numbered)

    # Entrances: the trail point nearest each parking lot (OpenStreetMap's, and DCR's where
    # OSM has none), if close
    trail_pts = [n for w in ways if not w.get("road") for n in w["nodes"]]
    lots = []
    for lot in load("osm_parking.json"):
        c = lot.get("center") or lot
        t = lot.get("tags", {})
        if c.get("lon") is not None and t.get("access") not in ("private", "customers", "no"):
            lots.append(((c["lon"], c["lat"]), t.get("name")))
    for f in load("dcr_points.geojson")["features"]:
        if f["properties"].get("TYPE") == "Parking Area":
            ll = tuple(f["geometry"]["coordinates"][:2])
            if all(dist_m(*ll, *q) > DCR_LOT_M for q, _ in lots):
                lots.append((ll, None))
    # Most lots have no name in OpenStreetMap; those go by the road they're off
    road_pts = [(nodes[n], r["tags"]["name"]) for r in roads_osm if r["type"] == "way" and r.get("tags", {}).get("name")
                and r["tags"].get("highway") != "service" for n in r["nodes"] if n in nodes]
    def lot_name(ll):
        d, road = min((dist_m(*ll, *q), name) for q, name in road_pts)
        return "Lot off " + road if d <= LOT_ROAD_M else None
    lots = [(ll, name or lot_name(ll)) for ll, name in lots]
    entries = {}
    for ll, name in lots:
        n = min(trail_pts, key=lambda q: dist_m(*ll, *nodes[q]))
        if dist_m(*ll, *nodes[n]) <= ENTRY_LOT_M and (n not in entries or (name and not entries[n][1])):
            entries[n] = (ll, name)
            points.add(n)

    # Zones: the side of I-93 each point is on
    zones = {n: side_of(nodes[n], divide) for n in points}
    count = collections.Counter()
    label, features = {}, []
    for n in sorted(points, key=lambda q: (-nodes[q][1], nodes[q][0])):   # north to south
        z = zones[n]
        if n in numbered:
            label[n] = numbered[n]
            props = {"label": label[n], "code": label[n], "zone": z, "number": n}
        elif n in entries:
            count[z] += 1
            label[n] = "%s%d" % (z, count[z])
            props = {"label": label[n], "code": label[n], "zone": z, "shape": True, "number": n}
        else:
            count["J"] += 1
            label[n] = "J%d" % count["J"]
            props = {"label": label[n], "code": label[n], "zone": z, "no_sign": True, "junction": True, "number": n}
        if n in entries:
            (lon, lat), name = entries[n]
            props.update({"entry": True, "parking": True, "drive_to": [round(lon, 6), round(lat, 6)]})
            if name:
                props["parking_name"] = name
        features.append({"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": list(nodes[n])}})

    trail_feats, tim = [], {}
    for ti, w in enumerate(ways):
        coords = [list(nodes[n]) for n in w["nodes"]]
        cum = [0.0]
        for k in range(1, len(coords)):
            cum.append(cum[-1] + dist_m(coords[k - 1][0], coords[k - 1][1], coords[k][0], coords[k][1]))
        tid = "osm_%d" % w["osm"] + ("_%d" % ti if w.get("road") else "")
        props = {"id": tid, "name": w["name"], "highway": w["highway"]}
        _, blazes, surface = runs_along(w, nodes)
        if surface:
            props["surface"] = surface
        if blazes:
            props["blazes"] = blazes
        if w.get("road"):
            props["road"] = True
            props["route_cost"] = ROAD_COST
        trail_feats.append({"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}})
        ints = []
        for k, n in enumerate(w["nodes"]):
            if n in label and (not ints or ints[-1][0] != label[n]):
                ints.append([label[n], round(cum[k])])
        tim[ti] = {"length": round(cum[-1]), "ints": ints}

    lons = [c[0] for f in trail_feats for c in f["geometry"]["coordinates"]]
    lats = [c[1] for f in trail_feats for c in f["geometry"]["coordinates"]]
    region = {
        "name": "Middlesex Fells Reservation",
        "zones": {z: {"name": n, "color": c} for z, (n, c) in ZONES.items()},
        "view": {"center": [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2], "zoom": 14},
        "bounds": [[min(lats), min(lons)], [max(lats), max(lons)]],
        "storagePrefix": "fells",
        "report": {"email": "tendiamonds@gmail.com", "name": "Jason Breslau", "signReports": False},
        "zonesPage": False,
        # OSM's relations cover whole ways: no snapping to stretches between intersections
        "blazeStops": None,
        "dem": os.path.join(PROJ, "elevation_cache", "fells.tif"),
        "blazes": BLAZES,
        "nav": ('<nav class="topnav"><a href="map.html" style="color:white;font-weight:700">Middlesex Fells</a>'
                + maps_menu_html("fells", "../") + '</nav>'),
    }
    os.makedirs(OUT, exist_ok=True)
    build_map_page({"type": "FeatureCollection", "features": features}, {"type": "FeatureCollection", "features": trail_feats},
                   region, OUT, trail_int_map=tim)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write('<!DOCTYPE html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=map.html">'
                '<title>Middlesex Fells Reservation</title><a href="map.html">Middlesex Fells trail map</a>\n')
    make_favicon.make_icons(OUT, label="MF", color="#2e7d32", name="Middlesex Fells Reservation", short_name="Fells", root="../")
    build_reports_page(os.path.join(OUT, "reports.html"), title="Reports — Middlesex Fells Reservation", css=CHECKS_CSS,
                       nav=region["nav"], storage_prefix=region["storagePrefix"], email=region["report"]["email"],
                       name=region["report"]["name"], blazes=BLAZES, checks=[])

    by_zone = collections.Counter(f["properties"]["zone"] for f in features if not f["properties"].get("no_sign"))
    print("Fells: %d trails (%d named, %d road links), %d numbered intersections, %d marked %s, %d quiet junctions, "
          "%d entrances (%d named)" % (
        len(ways), sum(1 for w in ways if w["name"]), sum(1 for w in ways if w.get("road")), len(numbered),
        sum(by_zone.values()), dict(by_zone), count["J"], len(entries), sum(1 for e in entries.values() if e[1])))
    print("  left out: %d user-created paths, %d on water-supply land with no public access" % (unofficial, restricted))
    print("  km: %.1f; blazed: %s" % (sum(t["length"] for t in tim.values()) / 1000, ", ".join(
        "%s %.1f km" % (BLAZES[b]["name"], sum(r[2] - r[1] for f in trail_feats for r in f["properties"].get("blazes", []) if r[0] == b) / 1000)
        for b in BLAZES)))


if __name__ == "__main__":
    main()
