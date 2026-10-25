"""
Build the Saratoga Springs trail map (saratoga/map.html): the Skidmore North Woods, Daniels
Road State Forest (with the Saratoga Mountain Bike Association's trails around it), and the
Graphite Range Community Forest, all from OpenStreetMap (saratoga_data/, from Overpass):

  osm_trails.json    paths, tracks and footways, with their points
  osm_roads.json     roads, for short walks along them between trails
  osm_parking.json   parking lots, for entrances
  osm_areas.json     the three areas' boundaries
  osm_campus_buildings.json   Skidmore's buildings, and its 815 North Broadway address points
  building_labels.json        the residence buildings' names, from Skidmore's sustainability map

None of these trails have numbered intersections, so the map draws each intersection as a
small picture of the trails meeting there, and names it by them (shape: true; trailmap.py).
Each still has a label (its area's letter and a number) for links and reports.

Blazes: the North Woods trails are named for their colors in OpenStreetMap. Daniels Road's
come from the SMBA trail map (saratoga_blazes.py, which writes saratoga_data/blazes.json).
"""

import collections
import json
import math
import os

import make_favicon
from build_bluehills import dist_m, road_links, name_continuations, join_continuations, CHECKS_CSS
from reports import build_reports_page
from trailmap import build_map_page, maps_menu_html

PROJ = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(PROJ, "saratoga_data")
OUT = os.path.join(PROJ, "saratoga")

# The areas: their letter (for labels), name, map color, and OpenStreetMap boundary
AREAS = {
    "N": ("North Woods", "#006a52", "Skidmore North Woods"),   # Skidmore's green
    "D": ("Daniels Road", "#455a64", "Daniels Road State Forest"),
    "G": ("Graphite Range", "#5d4037", "Graphite Range Community Forest"),
}
TRAIL_KINDS = {"path", "track", "bridleway", "cycleway"}   # grown out from the areas
# Trails worth including that the rules above leave out: OSM way: (name, why)
EXTRA_WAYS = {
    337625056: ("North Broadway", "the double-track road from the lot at the end of North Broadway, north along "
                "the North Woods' east side to the middle school (unnamed and tagged a footway in OSM, and outside "
                "the boundary; some maps call it North Broadway)"),
}
# Ways inside an area that aren't woods trails: OSM way: why
LEFT_OUT = {
    1018910711: "a campus footway along Perimeter Road, past the parking lots (each made an entrance)",
}
# Parking OpenStreetMap doesn't have: (lon, lat), name
EXTRA_LOTS = [((-73.77806, 43.09949), "North Broadway lot"),     # where North Broadway ends
              ((-73.772149, 43.118), "Artisanal Brew Works")]        # its lot behind the building (Gupthill Road, Wilton)
# Lots OpenStreetMap has that aren't the way in they seem: no parking for the trails there
NOT_TRAIL_PARKING = {"North Hall Lot",   # nearest the Red Trail's dead end at Falstaff's, but not its parking
                     "Falstaff's Lot"}   # its way in, where the Red and Green Trails meet, isn't worth it
# Ways in on foot, without parking: (lon, lat) near the trail's end, what it connects to
ACCESS_POINTS = [((-73.782664, 43.099376), "Falstaff Lane"),                # the Red Trail's dead end, by Falstaff's
                 ((-73.784872, 43.098929), "Campus, by Wilson Chapel"),      # the Spirit in Nature Trail's
                 ((-73.784819, 43.101758), "Northwoods Village, by Building 4")]  # the Red Trail's bend north
# The entrances' names (in place of the trails they're on), by where they are: (lon, lat), name
ENTRANCE_NAMES = [
    ((-73.76868, 43.13961), "Graphite Range lot (Route 9)"),
    ((-73.78799, 43.11107), "State Forest lot"),
    ((-73.79484, 43.10496), "Carriage Trail at Clinton St"),
    ((-73.78716, 43.10202), "Cane Lot"),
    ((-73.77806, 43.09949), "North Broadway lot"),
    ((-73.78266, 43.09938), "Falstaff's"),   # at Falstaff Lane, by Falstaff's (the building)
    ((-73.78487, 43.09893), "Wilson Chapel"),
    ((-73.784819, 43.101758), "Northwoods Village"),
    ((-73.772149, 43.118), "Artisanal Brew Works lot"),        # the Eileen Phillips Trail's end, at the lot behind it
]
ENTRANCE_NAME_M = 40     # an entrance this close to a named spot takes its name
LABEL_BUILDING_M = 40    # a building this close to where Skidmore puts a name is the one it names
LABEL_ALONG = 0.55       # ...and the name goes this far from its middle toward an end
ENTRY_LOT_M = 150        # a parking lot this close to a trail point makes it an entrance
MIN_NETWORK_M = 400      # smaller cut-off bits of trail are left out
ROAD_COST = 1.5

# The North Woods trails are named for their blazes
NAMED_BLAZES = {"Red Trail": "red", "Blue Trail": "blue", "Orange Trail": "orange", "Green Trail": "green",
                "Spirit in Nature Trail": "purple"}
BLAZES = {
    "red": {"name": "Red-blazed trail", "marks": "red blazes", "color": "#e53935", "style": "blazes"},
    "blue": {"name": "Blue-blazed trail", "marks": "blue blazes", "color": "#1e88e5", "style": "blazes"},
    "yellow": {"name": "Yellow-blazed trail", "marks": "yellow blazes", "color": "#fdd835", "style": "blazes"},
    "orange": {"name": "Orange-blazed trail", "marks": "orange blazes", "color": "#fb8c00", "style": "blazes"},
    "green": {"name": "Green-blazed trail", "marks": "green blazes", "color": "#43a047", "style": "blazes"},
    "purple": {"name": "Purple-blazed trail", "marks": "purple blazes", "color": "#8e24aa", "style": "blazes"},
    # The SMBA map's brown singletrack and black trails, colored as if blazed (pick: what
    # the Report sheet calls them, for someone who sees one)
    "brown": {"name": "Brown trail (SMBA map)", "marks": "shown brown on the SMBA map", "pick": "brown blazes", "color": "#a0522d", "style": "blazes"},
    "black": {"name": "Black trail (SMBA map)", "marks": "shown black on the SMBA map", "pick": "black blazes", "color": "#212121", "style": "blazes"},
}


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def inside(pt, ring):
    x, y, hit = pt[0], pt[1], False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def area_rings():
    """{letter: [ring of (lon, lat)]}, from the boundary ways or relations"""
    rings = collections.defaultdict(list)
    by_name = {v[2]: k for k, v in AREAS.items()}
    for e in load("osm_areas.json")["elements"]:
        k = by_name.get(e.get("tags", {}).get("name"))
        if not k:
            continue
        if e["type"] == "way":
            rings[k].append([(p["lon"], p["lat"]) for p in e["geometry"]])
        else:
            for mem in e.get("members", []):
                if mem.get("role") == "outer" and mem.get("geometry"):
                    rings[k].append([(p["lon"], p["lat"]) for p in mem["geometry"]])
    return rings


def area_ways(els, rings):
    """The trails: those with a point in an area, and the paths and tracks joined to them
    (the SMBA trails reach well south of the state forest). Sidewalks, crossings, and campus
    footways outside the areas are left out."""
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in els if e["type"] == "node"}
    cands = []
    for w in els:
        t = w.get("tags", {}) if w["type"] == "way" else None
        if t is None or t.get("footway") in ("sidewalk", "crossing", "link") or t.get("cycleway") == "sidewalk" or t.get("access") == "private":
            continue
        if w["id"] in LEFT_OUT:
            continue
        if w["id"] in EXTRA_WAYS:   # a double track, whatever OSM calls it
            t = dict(t, highway="track", name=t.get("name") or EXTRA_WAYS[w["id"]][0])
        ns = [n for n in w["nodes"] if n in nodes]
        if len(ns) >= 2:
            cands.append({"name": t.get("name", ""), "highway": t.get("highway"), "surface": t.get("surface"),
                          "imba": t.get("mtb:scale:imba"), "nodes": ns, "osm": w["id"]})
    def area_of(w):
        for k, rs in rings.items():
            if any(inside(nodes[n], r) for r in rs for n in w["nodes"][::2] + [w["nodes"][-1]]):
                return k
        return None
    keep = {i for i, w in enumerate(cands) if area_of(w) or w["osm"] in EXTRA_WAYS}
    at = collections.defaultdict(list)
    for i, w in enumerate(cands):
        for n in w["nodes"]:
            at[n].append(i)
    todo = list(keep)
    while todo:
        i = todo.pop()
        for n in cands[i]["nodes"]:
            for j in at[n]:
                if j not in keep and cands[j]["highway"] in TRAIL_KINDS:
                    keep.add(j)
                    todo.append(j)
    return [cands[i] for i in sorted(keep)], nodes


def drop_small_networks(ways, nodes):
    """Leave out cut-off bits of trail too short to be worth it"""
    parent = list(range(len(ways)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    first = {}
    for i, w in enumerate(ways):
        for n in w["nodes"]:
            if n in first:
                parent[find(i)] = find(first[n])
            else:
                first[n] = i
    length = collections.Counter()
    for i, w in enumerate(ways):
        length[find(i)] += sum(dist_m(*nodes[a], *nodes[b]) for a, b in zip(w["nodes"], w["nodes"][1:]))
    return [w for i, w in enumerate(ways) if length[find(i)] >= MIN_NETWORK_M]


def zone_of(pt, rings):
    """The area a point is in, or the nearest one"""
    for k, rs in rings.items():
        if any(inside(pt, r) for r in rs):
            return k
    return min(rings, key=lambda k: min(dist_m(*pt, *q) for r in rings[k] for q in r[::3]))


def trail_zones(ways, nodes, rings):
    """Each trail point's area: the one nearest along the trails (not as the crow flies, so
    the SMBA trails south of the state forest are Daniels Road's, not the North Woods')"""
    import heapq
    graph = collections.defaultdict(list)
    for w in ways:
        if not w.get("road"):
            for a, b in zip(w["nodes"], w["nodes"][1:]):
                d = dist_m(*nodes[a], *nodes[b])
                graph[a].append((b, d))
                graph[b].append((a, d))
    best, queue = {}, []
    for n in graph:
        for k, rs in rings.items():
            if any(inside(nodes[n], r) for r in rs):
                best[n] = (0.0, k)
                queue.append((0.0, n, k))
    heapq.heapify(queue)
    while queue:
        d, n, k = heapq.heappop(queue)
        if best.get(n, (math.inf,))[0] < d:
            continue
        for v, w in graph[n]:
            if d + w < best.get(v, (math.inf,))[0]:
                best[v] = (d + w, k)
                heapq.heappush(queue, (d + w, v, k))
    return {n: k for n, (_, k) in best.items()}


def building_labels():
    """Names for the campus residences next to the North Woods, which OpenStreetMap has no
    names for (saratoga_data/building_labels.json, from Skidmore's sustainability map), each
    on the OSM building nearest the point Skidmore gives. The map tiles print Skidmore's one
    street address (815) in each building, at its middle or at an address point inside it, so
    the name goes along the building's length, toward the end away from that."""
    names = load("building_labels.json")["buildings"]
    els = load("osm_campus_buildings.json")["elements"]
    addr = [(e["lon"], e["lat"]) for e in els if e["type"] == "node"]
    blds = []
    for e in els:
        if e["type"] == "way" and e.get("geometry") and not e["tags"].get("name"):
            ring = [(p["lon"], p["lat"]) for p in e["geometry"]]
            blds.append((ring, centroid(ring)))
    pairs = sorted((dist_m(b["lon"], b["lat"], c[1], c[2]), i, j) for i, b in enumerate(names) for j, (_, c) in enumerate(blds))
    at, used = {}, set()
    for d, i, j in pairs:   # nearest pairs first, each building once
        if d <= LABEL_BUILDING_M and i not in at and j not in used:
            at[i] = j
            used.add(j)
    # On the map, just Sussman's letters and Northwoods' numbers (unique across its streets)
    short = lambda n: n.split()[-1] if n.startswith("Sussman") else n.split()[0]
    out = []
    for i, b in enumerate(names):
        lon, lat = b["lon"], b["lat"]
        if i in at:
            ring, (_, cx, cy) = blds[at[i]]
            pts = [((x - cx) * 81300, (y - cy) * 111000) for x, y in ring[:-1]]
            # the long way along the building, and how far its ends are from the middle
            sxx = sum(x * x for x, _ in pts); syy = sum(y * y for _, y in pts); sxy = sum(x * y for x, y in pts)
            ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
            ux, uy = math.cos(ang), math.sin(ang)
            reach = max(x * ux + y * uy for x, y in pts)
            # the 815: an address point inside, or else the middle
            inner = [((x - cx) * 81300, (y - cy) * 111000) for x, y in addr if inside((x, y), ring)]
            side = -1 if inner and inner[0][0] * ux + inner[0][1] * uy > 0 else 1
            k = LABEL_ALONG * reach * side
            lon, lat = cx + k * ux / 81300, cy + k * uy / 111000
        out.append({"name": short(b["name"]), "lat": round(lat, 6), "lon": round(lon, 6)})
    return out


def centroid(ring):
    """A polygon's area (square meters) and center (lon, lat), as the map tiles place a name.
    (Worked out from the first corner: whole coordinates lose too much to rounding.)"""
    x0, y0 = ring[0]
    ring = [(x - x0, y - y0) for x, y in ring]
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(a) < 1e-15:
        return 0.0, x0, y0
    return abs(a / 2) * 81300 * 111000, x0 + cx / (3 * a), y0 + cy / (3 * a)


def main():
    rings = area_rings()
    ways, nodes = area_ways(load("osm_trails.json")["elements"], rings)
    roads_osm = load("osm_roads.json")["elements"]
    ways = drop_small_networks(ways, nodes)
    ways += road_links(roads_osm, ways, nodes)
    ways = join_continuations(name_continuations(ways, {}), {})

    # Intersections: where three or more trail ends meet. Where one trail just becomes
    # another, a quiet junction (no icon), so routes and trail details still know it.
    degree = collections.Counter()
    on = collections.defaultdict(set)
    for i, w in enumerate(ways):
        for k, n in enumerate(w["nodes"]):
            on[n].add(i)
            degree[n] += 1 if k in (0, len(w["nodes"]) - 1) else 2
    points = {n for n in on if len(on[n]) >= 2 or degree[n] >= 3}

    # Entrances: the trail point nearest each parking lot, if close
    trail_pts = {n for w in ways if not w.get("road") for n in w["nodes"]}
    entries = {}
    lots = load("osm_parking.json")["elements"] + [{"lon": lon, "lat": lat, "tags": {"name": name}} for (lon, lat), name in EXTRA_LOTS]
    for lot in lots:
        c = lot.get("center") or lot
        ll = (c.get("lon"), c.get("lat"))
        if ll[0] is None:
            continue
        n = min(trail_pts, key=lambda q: dist_m(*ll, *nodes[q]))
        name = lot.get("tags", {}).get("name")
        if dist_m(*ll, *nodes[n]) <= ENTRY_LOT_M and n not in entries and name not in NOT_TRAIL_PARKING:
            entries[n] = (ll, name)
            points.add(n)
    access = {}
    for ll, connects in ACCESS_POINTS:
        n = min(trail_pts, key=lambda q: dist_m(*ll, *nodes[q]))
        access[n] = connects
        points.add(n)
        entries.pop(n, None)   # a way in on foot, whatever lot is nearby

    zones = trail_zones(ways, nodes, rings)
    count = collections.Counter()
    label, features = {}, []
    for n in sorted(points, key=lambda q: (-nodes[q][1], nodes[q][0])):   # north to south
        z = zones.get(n) or zone_of(nodes[n], rings)
        if degree[n] >= 3 or n in entries or n in access:
            count[z] += 1
            label[n] = "%s%d" % (z, count[z])
            props = {"label": label[n], "code": label[n], "zone": z, "shape": True, "number": n}
        else:
            count["J"] += 1
            label[n] = "J%d" % count["J"]
            props = {"label": label[n], "code": label[n], "zone": z, "no_sign": True, "junction": True, "number": n}
        if n in access:
            props.update({"entry": True, "connects": access[n]})
        if n in access or n in entries:
            here = min(ENTRANCE_NAMES, key=lambda e: dist_m(*e[0], *nodes[n]))
            if dist_m(*here[0], *nodes[n]) <= ENTRANCE_NAME_M:
                props["place_name"] = here[1]
        if n in entries:
            (lon, lat), name = entries[n]
            props.update({"entry": True, "parking": True, "drive_to": [round(lon, 6), round(lat, 6)]})
            if name:
                props["parking_name"] = name
        features.append({"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": list(nodes[n])}})

    # Blazes: the North Woods' by their trails' names; Daniels Road's from the SMBA map
    pdf_blazes = load("blazes.json") if os.path.exists(os.path.join(DATA, "blazes.json")) else {}
    trail_feats, tim = [], {}
    for ti, w in enumerate(ways):
        coords = [list(nodes[n]) for n in w["nodes"]]
        cum = [0.0]
        for k in range(1, len(coords)):
            cum.append(cum[-1] + dist_m(coords[k - 1][0], coords[k - 1][1], coords[k][0], coords[k][1]))
        tid = "osm_%d" % w["osm"] + ("_%d" % ti if w.get("road") else "")
        props = {"id": tid, "name": w["name"], "highway": w["highway"]}
        if w.get("surface"):
            props["surface"] = w["surface"]
        if w.get("road"):
            props["road"] = True
            props["route_cost"] = ROAD_COST
        if w["name"] in NAMED_BLAZES:
            props["blazes"] = [[NAMED_BLAZES[w["name"]], 0, round(cum[-1], 1), 0]]
        elif pdf_blazes.get(tid):
            props["blazes"] = pdf_blazes[tid]
        trail_feats.append({"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}})
        ints = []
        for k, n in enumerate(w["nodes"]):
            if n in label and (not ints or ints[-1][0] != label[n]):
                ints.append([label[n], round(cum[k])])
        tim[ti] = {"length": round(cum[-1]), "ints": ints}

    # The trails and intersections as built, for saratoga_blazes.py to match the SMBA map to
    with open(os.path.join(DATA, "built.json"), "w", encoding="utf-8") as f:
        json.dump({"trails": trail_feats, "ints": features}, f)

    lons = [c[0] for f in trail_feats for c in f["geometry"]["coordinates"]]
    lats = [c[1] for f in trail_feats for c in f["geometry"]["coordinates"]]
    region = {
        "name": "Saratoga Woods",
        "zones": {z: {"name": n, "color": c} for z, (n, c, _) in AREAS.items()},
        "view": {"center": [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2], "zoom": 14},
        "bounds": [[min(lats), min(lons)], [max(lats), max(lons)]],
        "storagePrefix": "sar",
        "report": {"email": "tendiamonds@gmail.com", "signReports": False},
        "otherMaps": [{"name": "Upper Charles Forest", "href": "../map.html"}, {"name": "Blue Hills", "href": "../bluehills/map.html"}],
        "zonesPage": False,
        "dem": os.path.join(PROJ, "elevation_cache", "saratoga.tif"),
        "blazes": BLAZES,
        "placeLabels": building_labels(),
        "nav": ('<nav class="topnav"><a href="map.html" style="color:white;font-weight:700">Saratoga Woods</a>'
                '<a href="reports.html" style="color:#ecf0f1;font-size:14px">Reports</a>'
                + maps_menu_html("sar", "../") + '</nav>'),
    }
    os.makedirs(OUT, exist_ok=True)
    build_map_page({"type": "FeatureCollection", "features": features}, {"type": "FeatureCollection", "features": trail_feats},
                   region, OUT, trail_int_map=tim)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write('<!DOCTYPE html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=map.html">'
                '<title>Saratoga Woods</title><a href="map.html">Saratoga Woods trail map</a>\n')
    # Skidmore's green and yellow
    make_favicon.make_icons(OUT, label="S", color="#006A52", ink="#FFD100", name="Saratoga Woods", short_name="Saratoga")
    build_reports_page(os.path.join(OUT, "reports.html"), title="Reports — Saratoga Woods", css=CHECKS_CSS,
                       nav=region["nav"], storage_prefix=region["storagePrefix"], email=region["report"]["email"],
                       blazes=BLAZES, checks=[])

    by_zone = collections.Counter(f["properties"]["zone"] for f in features if f["properties"].get("shape"))
    km = collections.Counter()
    for f, w in zip(trail_feats, ways):
        mid = w["nodes"][len(w["nodes"]) // 2]
        km[zones.get(mid) or zone_of(nodes[mid], rings)] += tim[trail_feats.index(f)]["length"] / 1000
    print("Saratoga: %d trails (%d named, %d road links), %d intersections %s, %d quiet junctions, %d entrances" % (
        len(ways), sum(1 for w in ways if w["name"]), sum(1 for w in ways if w.get("road")),
        sum(by_zone.values()), dict(by_zone), count["J"], len(entries)))
    print("  trail km by area: " + ", ".join("%s %.1f" % (AREAS[z][0], km[z]) for z in AREAS))
    print("  blazed: " + ", ".join("%s %.1f km" % (b, sum(r[2] - r[1] for f in trail_feats for r in f["properties"].get("blazes", []) if r[0] == b) / 1000) for b in BLAZES))


if __name__ == "__main__":
    main()
