"""
Generate parcel reports from source GeoJSON data.

Reads intersections_zoned.geojson and parcels_all.geojson, does
point-in-polygon lookup, classifies Holliston public land into three
categories based on deed research, and writes reports.

Holliston public land categories (from assessor deed records):
  - Adams Town Forest (Trustees CR): deed 50653/93 parcels + blank-owner parcel
  - Fairbanks Land (Trustees/DCR CR): deed 38378/0240 (210 acres)
  - Town of Holliston: all other town-owned parcels

Other public owners kept as-is: Town of Milford, Town of Hopkinton.
"""

import heapq
import json
import math
import re
from collections import OrderedDict, defaultdict

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"
TOWNS = {136: "Holliston", 139: "Hopkinton", 185: "Milford"}

# Deed 50653/93 parcels = Adams Town Forest (Trustees CR, ~87 acres)
TOWN_FOREST_LOCS = {
    "M_201192_880840",  # 18.3 ac, A1/A2/A3/A5
    "M_200767_881204",  # 34.8 ac, A16/A17
    "M_200582_881415",  # 18.3 ac, B22
    "M_200791_880798",  # 84.4 ac blank-owner parcel, A4/A7/A8/A9/A11/A12/A15/A18/A20
}

# Deed 38378/0240 = Fairbanks Land (Trustees/DCR CR, 210 acres)
FAIRBANKS_LOCS = {
    "M_200659_879945",  # 210 ac, D1-D7/E24-E25/F1-F20
}


def proper_case(s):
    if not s:
        return s
    words = s.split()
    result = []
    small = {"of", "the", "and", "at", "in", "on", "for", "to", "a", "an"}
    suffix_upper = {"LLC", "LP", "LLP", "PC", "PA", "II", "III", "IV"}
    for i, w in enumerate(words):
        wu = w.upper()
        if wu in suffix_upper:
            result.append(wu)
        elif wu == "INC." or wu == "INC":
            result.append("Inc." if wu == "INC." else "Inc.")
        elif wu in ("ST", "ST.") and i > 0:
            result.append("St")
        elif wu in ("RD", "RD.") and i > 0:
            result.append("Rd")
        elif wu in ("LN", "LN.") and i > 0:
            result.append("Ln")
        elif wu in ("DR", "DR.") and i > 0:
            result.append("Dr")
        elif wu in ("AVE", "AVE.") and i > 0:
            result.append("Ave")
        elif wu in ("TRUSTEE", "TRUSTEES", "TTEE"):
            result.append("Trustee" if wu != "TRUSTEES" else "Trustees")
        elif w.lower() in small and i > 0:
            result.append(w.lower())
        else:
            result.append(w.capitalize())
    return " ".join(result)


def point_in_polygon(px, py, coords_ring):
    n = len(coords_ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = coords_ring[i]
        xj, yj = coords_ring[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def find_parcel(lon, lat, parcels):
    for feat in parcels["features"]:
        geom = feat["geometry"]
        if geom["type"] == "Polygon":
            rings = geom["coordinates"]
            if point_in_polygon(lon, lat, rings[0]):
                return feat
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                if point_in_polygon(lon, lat, poly[0]):
                    return feat
    best_dist = 100
    best = None
    for feat in parcels["features"]:
        geom = feat["geometry"]
        if geom["type"] == "Polygon":
            rings = [geom["coordinates"]]
        elif geom["type"] == "MultiPolygon":
            rings = [p for p in geom["coordinates"]]
        else:
            continue
        for poly in rings:
            for c in poly[0]:
                d = math.sqrt(((lon - c[0]) * 82000) ** 2 + ((lat - c[1]) * 111000) ** 2)
                if d < best_dist:
                    best_dist = d
                    best = feat
    return best


def classify_owner(parcel_feat):
    if not parcel_feat:
        return "Unknown", "Unknown", False

    pp = parcel_feat["properties"]
    raw_owner = (pp.get("OWNER1") or "").strip()
    town_id = pp.get("TOWN_ID")
    town = TOWNS.get(town_id, "Unknown")
    loc_id = pp.get("LOC_ID") or ""

    if town == "Holliston":
        if loc_id in TOWN_FOREST_LOCS:
            return "Adams Town Forest (Trustees CR)", town, True
        if loc_id in FAIRBANKS_LOCS:
            return "Fairbanks Land (Trustees/DCR CR)", town, True
        upper = raw_owner.upper()
        if upper in ("HOLLISTON, TOWN OF", "TOWN OF HOLLISTON", "CONSERVATION COMMISSION", "UNKNOWN", ""):
            return "Town of Holliston", town, True
        if "HOLLISTON" in upper and "TOWN" in upper:
            return "Town of Holliston", town, True
        if not raw_owner:
            return "Town of Holliston", town, True

    if town == "Hopkinton":
        upper = raw_owner.upper()
        if "HOPKINTON" in upper or "TOWN" in upper:
            return "Town of Hopkinton", town, True

    if town == "Milford":
        upper = raw_owner.upper()
        if "MILFORD" in upper and "TOWN" in upper:
            return "Town of Milford", town, True
        if "TOWN OF MILFORD" in upper:
            return "Town of Milford", town, True
        if "NEMBA" in upper or "NEW ENGLAND MOUNTAIN BIKE" in upper:
            return "New England Mountain Bike Association Inc.", town, False
        if "NEW ENGLAND POWER" in upper:
            return "New England Power Co", town, False

    return proper_case(raw_owner) if raw_owner else "Unknown", town, False


EXIT_POINTS = {
    "A": (-71.4856, 42.1786),
    "B": (-71.5056, 42.1796),
    "C": (-71.498, 42.196),
    "D": (-71.493, 42.171),
    "E": (-71.500, 42.171),
    "F": (-71.485, 42.170),
}
F_G_GROUP = {36, 178, 213, 214, 176, 4, 129, 1, 245, 135, 9, 175, 10, 248, 130}


def dist_m(lon1, lat1, lon2, lat2):
    return math.sqrt(((lon1 - lon2) * 82000)**2 + ((lat1 - lat2) * 111000)**2)


def build_trail_graph(ints, trails):
    SNAP_DIST = 20
    int_pts = {}
    for feat in ints["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        int_pts[id(feat)] = (lon, lat)

    def cumulative_distances(coords):
        cum = [0.0]
        for i in range(1, len(coords)):
            cum.append(cum[-1] + dist_m(coords[i-1][0], coords[i-1][1],
                                         coords[i][0], coords[i][1]))
        return cum

    graph = defaultdict(list)
    for trail in trails["features"]:
        geom = trail["geometry"]
        if geom["type"] == "LineString":
            coords = geom["coordinates"]
        elif geom["type"] == "MultiLineString":
            coords = []
            for part in geom["coordinates"]:
                coords.extend(part)
        else:
            continue
        if len(coords) < 2:
            continue
        cum = cumulative_distances(coords)
        hits = []
        for fid, (ilon, ilat) in int_pts.items():
            best_d = float("inf")
            best_cum = 0
            for j, c in enumerate(coords):
                d = dist_m(ilon, ilat, c[0], c[1])
                if d < best_d:
                    best_d = d
                    best_cum = cum[j]
            if best_d < SNAP_DIST:
                hits.append((best_cum, fid))
        hits.sort()
        for i in range(len(hits) - 1):
            cum1, fid1 = hits[i]
            cum2, fid2 = hits[i+1]
            if fid1 == fid2:
                continue
            seg_len = cum2 - cum1
            if seg_len > 0:
                graph[fid1].append((fid2, seg_len))
                graph[fid2].append((fid1, seg_len))
    return graph


def dijkstra(graph, start_nodes):
    dist = {}
    pq = []
    for s in start_nodes:
        dist[s] = 0
        heapq.heappush(pq, (0, s))
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, float("inf")):
            continue
        for v, w in graph.get(u, []):
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def order_subgroup(graph, pts, ex, ey):
    exit_feat = min(pts, key=lambda f: dist_m(
        f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1], ex, ey))
    dists = dijkstra(graph, [id(exit_feat)])
    reachable = [(f, dists[id(f)]) for f in pts if id(f) in dists]
    unreachable = [f for f in pts if id(f) not in dists]
    reachable.sort(key=lambda pair: pair[1])
    unreachable.sort(key=lambda f: dist_m(
        f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1], ex, ey))
    return [f for f, _ in reachable] + unreachable


def main():
    with open(rf"{PROJ}\parcels_all.geojson") as f:
        parcels = json.load(f)
    with open(r"C:\Users\jbreslau\Downloads\intersections_zoned.geojson") as f:
        ints = json.load(f)
    with open(rf"{PROJ}\trails_selected.geojson") as f:
        trails = json.load(f)

    graph = build_trail_graph(ints, trails)

    by_zone = {}
    for feat in ints["features"]:
        z = feat["properties"]["zone"]
        by_zone.setdefault(z, []).append(feat)

    for z in "ABCDEF":
        pts = by_zone.get(z, [])
        ex, ey = EXIT_POINTS[z]
        if z == "F":
            main_pts = [f for f in pts if f["properties"]["number"] not in F_G_GROUP]
            tail_pts = [f for f in pts if f["properties"]["number"] in F_G_GROUP]
            ordered = order_subgroup(graph, main_pts, ex, ey) + \
                      order_subgroup(graph, tail_pts, ex, ey)
        else:
            ordered = order_subgroup(graph, pts, ex, ey)
        for i, feat in enumerate(ordered, 1):
            feat["properties"]["label"] = "%s%d" % (z, i)

    rows = []
    for feat in ints["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        label = feat["properties"]["label"]
        zone = feat["properties"]["zone"]
        parcel = find_parcel(lon, lat, parcels)
        owner, town, is_public = classify_owner(parcel)

        rows.append({
            "label": label,
            "zone": zone,
            "owner": owner,
            "town": town,
            "is_public": is_public,
        })

    rows.sort(key=lambda r: (r["zone"], int(r["label"][1:])))
    print("Processed %d intersections" % len(rows))

    # --- Zone report (combined rows within each zone) ---
    zone_lines = ["# Intersection Parcel Report\n"]
    for zone in "ABCDEF":
        zone_rows = [r for r in rows if r["zone"] == zone]
        zone_lines.append("## Zone %s (%d intersections)\n" % (zone, len(zone_rows)))
        zone_lines.append("| Owner | Town | Intersections |")
        zone_lines.append("|-------|------|---------------|")

        groups = OrderedDict()
        for r in zone_rows:
            key = (r["owner"], r["town"])
            if key not in groups:
                groups[key] = []
            groups[key].append(r["label"])

        for (owner, town), labels in groups.items():
            labels_sorted = sorted(labels, key=lambda l: (l[0], int(l[1:])))
            zone_lines.append("| %s | %s | %s |" % (owner, town, ", ".join(labels_sorted)))

        zone_lines.append("")

    with open(rf"{PROJ}\zone_parcel_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(zone_lines))
    print("Wrote zone_parcel_report.md")

    # --- Parcel report (two tables: public and private) ---
    owner_groups = OrderedDict()
    for r in rows:
        key = r["owner"]
        if key not in owner_groups:
            owner_groups[key] = {
                "owner": key,
                "towns": set(),
                "labels": [],
                "is_public": r["is_public"],
            }
        g = owner_groups[key]
        g["towns"].add(r["town"])
        g["labels"].append(r["label"])

    public = [g for g in owner_groups.values() if g["is_public"]]
    private = [g for g in owner_groups.values() if not g["is_public"]]

    public_order = [
        "Adams Town Forest (Trustees CR)",
        "Fairbanks Land (Trustees/DCR CR)",
        "Town of Holliston",
        "Town of Hopkinton",
        "Town of Milford",
    ]
    public.sort(key=lambda g: (
        public_order.index(g["owner"]) if g["owner"] in public_order else 99,
    ))
    private.sort(key=lambda g: g["owner"])

    total_pub = sum(len(g["labels"]) for g in public)
    total_priv = sum(len(g["labels"]) for g in private)

    lines = ["# Parcels and Their Intersections\n"]
    lines.append("%d intersections across %d owners.\n" % (
        total_pub + total_priv, len(public) + len(private)))

    lines.append("## Public Parcels\n")
    lines.append("| Owner | Town | Intersections |")
    lines.append("|-------|------|---------------|")
    for g in public:
        town = ", ".join(sorted(g["towns"]))
        labels_sorted = sorted(g["labels"], key=lambda l: (l[0], int(l[1:])))
        lines.append("| %s | %s | %s |" % (g["owner"], town, ", ".join(labels_sorted)))
    lines.append("")

    lines.append("## Private Parcels\n")
    lines.append("| Owner | Town | Intersections |")
    lines.append("|-------|------|---------------|")
    for g in private:
        town = ", ".join(sorted(g["towns"]))
        labels_sorted = sorted(g["labels"], key=lambda l: (l[0], int(l[1:])))
        lines.append("| %s | %s | %s |" % (g["owner"], town, ", ".join(labels_sorted)))
    lines.append("")

    with open(rf"{PROJ}\parcel_intersection_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Wrote parcel_intersection_report.md")


if __name__ == "__main__":
    main()
