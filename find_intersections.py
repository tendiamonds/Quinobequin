"""
Find trail intersections for Zone E by detecting where trail segments
meet or cross. Outputs an updated intersections_zoned.geojson with
existing non-E intersections preserved and new E intersections added.
"""
import json
import math
from collections import defaultdict

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"

# E zone bounding box (tight, based on actual E intersection extent + small buffer)
E_BOUNDS = {
    "min_lon": -71.508, "max_lon": -71.496,
    "min_lat": 42.1655, "max_lat": 42.1710,
}


def dist_m(lon1, lat1, lon2, lat2):
    return math.sqrt(((lon1 - lon2) * 82000)**2 + ((lat1 - lat2) * 111000)**2)


def interpolate_segment(p1, p2, max_spacing=5):
    """Interpolate points along a segment at ~max_spacing meter intervals."""
    d = dist_m(p1[0], p1[1], p2[0], p2[1])
    if d < max_spacing:
        return [p1, p2]
    n = max(2, int(d / max_spacing) + 1)
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append([p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])])
    return pts


def get_coords(feature):
    geom = feature["geometry"]
    if geom["type"] == "LineString":
        return geom["coordinates"]
    elif geom["type"] == "MultiLineString":
        coords = []
        for part in geom["coordinates"]:
            coords.extend(part)
        return coords
    return []


def in_e_zone(lon, lat):
    return (E_BOUNDS["min_lon"] <= lon <= E_BOUNDS["max_lon"] and
            E_BOUNDS["min_lat"] <= lat <= E_BOUNDS["max_lat"])


with open(r"C:\Users\jbreslau\Downloads\trails_selected (1).geojson") as f:
    trails = json.load(f)
with open(r"C:\Users\jbreslau\Downloads\intersections_zoned (1).geojson") as f:
    ints = json.load(f)

# Keep non-E intersections
non_e = [f for f in ints["features"] if f["properties"]["zone"] != "E"]
print(f"Keeping {len(non_e)} non-E intersections")

# Filter trails that pass through E zone
e_trails = []
for feat in trails["features"]:
    coords = get_coords(feat)
    if any(in_e_zone(c[0], c[1]) for c in coords):
        e_trails.append(feat)

print(f"{len(e_trails)} trails in/near E zone")

# For each trail, densify coordinates and build a spatial grid
GRID_SIZE = 0.0002  # ~16m grid cells
SNAP_DIST = 8  # meters - two trails within 8m are "meeting"
MIN_DEGREE = 2  # keep intersections where 2+ different named trails meet

grid = defaultdict(list)  # grid_cell -> [(lon, lat, trail_idx, coord_idx)]

for ti, feat in enumerate(e_trails):
    coords = get_coords(feat)
    dense = []
    for i in range(len(coords) - 1):
        pts = interpolate_segment(coords[i], coords[i+1])
        if i > 0:
            pts = pts[1:]  # avoid duplication at segment joins
        dense.extend(pts)

    for ci, (lon, lat) in enumerate(dense):
        if not in_e_zone(lon, lat):
            continue
        gx = int(lon / GRID_SIZE)
        gy = int(lat / GRID_SIZE)
        grid[(gx, gy)].append((lon, lat, ti, ci))

# Find points where multiple trails are close together
# Use a union-find to cluster nearby meeting points
candidate_clusters = []  # each cluster: list of (lon, lat, set of trail indices)

meeting_points = []
checked = set()

for (gx, gy), pts in grid.items():
    # Check this cell and neighbors
    nearby = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            nearby.extend(grid.get((gx+dx, gy+dy), []))

    # Group by trail
    by_trail = defaultdict(list)
    for lon, lat, ti, ci in nearby:
        by_trail[ti].append((lon, lat, ci))

    if len(by_trail) < 2:
        continue

    # Find pairs of trails that are close
    trail_ids = list(by_trail.keys())
    for i in range(len(trail_ids)):
        for j in range(i+1, len(trail_ids)):
            ti1 = trail_ids[i]
            ti2 = trail_ids[j]
            pair_key = (min(ti1, ti2), max(ti1, ti2), gx, gy)
            if pair_key in checked:
                continue
            checked.add(pair_key)

            for lon1, lat1, _ in by_trail[ti1]:
                for lon2, lat2, _ in by_trail[ti2]:
                    d = dist_m(lon1, lat1, lon2, lat2)
                    if d < SNAP_DIST:
                        avg_lon = (lon1 + lon2) / 2
                        avg_lat = (lat1 + lat2) / 2
                        meeting_points.append((avg_lon, avg_lat, ti1, ti2))

print(f"Found {len(meeting_points)} raw meeting points")

# Cluster meeting points that are within SNAP_DIST of each other
clusters = []
used = [False] * len(meeting_points)

for i in range(len(meeting_points)):
    if used[i]:
        continue
    lon_i, lat_i, ti1, ti2 = meeting_points[i]
    cluster_lons = [lon_i]
    cluster_lats = [lat_i]
    cluster_trails = {ti1, ti2}
    used[i] = True

    changed = True
    while changed:
        changed = False
        for j in range(len(meeting_points)):
            if used[j]:
                continue
            lon_j, lat_j, tj1, tj2 = meeting_points[j]
            avg_lon = sum(cluster_lons) / len(cluster_lons)
            avg_lat = sum(cluster_lats) / len(cluster_lats)
            if dist_m(avg_lon, avg_lat, lon_j, lat_j) < SNAP_DIST * 2:
                cluster_lons.append(lon_j)
                cluster_lats.append(lat_j)
                cluster_trails.add(tj1)
                cluster_trails.add(tj2)
                used[j] = True
                changed = True

    avg_lon = sum(cluster_lons) / len(cluster_lons)
    avg_lat = sum(cluster_lats) / len(cluster_lats)
    clusters.append((avg_lon, avg_lat, cluster_trails))

print(f"Clustered into {len(clusters)} candidate intersections")

# Also add trail endpoints as candidates (where trails dead-end or connect)
endpoint_clusters = []
endpoints = []
for ti, feat in enumerate(e_trails):
    coords = get_coords(feat)
    if len(coords) < 2:
        continue
    for pt in [coords[0], coords[-1]]:
        if in_e_zone(pt[0], pt[1]):
            endpoints.append((pt[0], pt[1], ti))

# Cluster endpoints
ep_used = [False] * len(endpoints)
for i in range(len(endpoints)):
    if ep_used[i]:
        continue
    lon_i, lat_i, ti = endpoints[i]
    cluster_lons = [lon_i]
    cluster_lats = [lat_i]
    cluster_trails = {ti}
    ep_used[i] = True

    for j in range(i+1, len(endpoints)):
        if ep_used[j]:
            continue
        lon_j, lat_j, tj = endpoints[j]
        avg_lon = sum(cluster_lons) / len(cluster_lons)
        avg_lat = sum(cluster_lats) / len(cluster_lats)
        if dist_m(avg_lon, avg_lat, lon_j, lat_j) < SNAP_DIST * 2:
            cluster_lons.append(lon_j)
            cluster_lats.append(lat_j)
            cluster_trails.add(tj)
            ep_used[j] = True

    if len(cluster_trails) >= 2:
        avg_lon = sum(cluster_lons) / len(cluster_lons)
        avg_lat = sum(cluster_lats) / len(cluster_lats)
        endpoint_clusters.append((avg_lon, avg_lat, cluster_trails))

print(f"Found {len(endpoint_clusters)} endpoint clusters (2+ trails meeting)")

# Merge endpoint clusters with main clusters
all_candidates = list(clusters)
for ep_lon, ep_lat, ep_trails in endpoint_clusters:
    merged = False
    for i, (c_lon, c_lat, c_trails) in enumerate(all_candidates):
        if dist_m(ep_lon, ep_lat, c_lon, c_lat) < SNAP_DIST * 2:
            new_lon = (c_lon + ep_lon) / 2
            new_lat = (c_lat + ep_lat) / 2
            all_candidates[i] = (new_lon, new_lat, c_trails | ep_trails)
            merged = True
            break
    if not merged:
        all_candidates.append((ep_lon, ep_lat, ep_trails))

# Build list of non-E intersection locations for exclusion
non_e_locs = []
for f in non_e:
    c = f["geometry"]["coordinates"]
    non_e_locs.append((c[0], c[1]))

# Filter: only keep intersections where 3+ trail segments meet (degree >= 3)
# and that aren't too close to an existing non-E intersection
EXCL_DIST = 15  # meters - skip if within 15m of a non-E intersection
filtered = []
skipped_near_other = 0
for lon, lat, trail_set in all_candidates:
    too_close = any(dist_m(lon, lat, nx, ny) < EXCL_DIST for nx, ny in non_e_locs)
    if too_close:
        skipped_near_other += 1
        continue
    names = set()
    for ti in trail_set:
        feat = e_trails[ti]
        name = feat["properties"].get("pdf_name") or feat["properties"].get("name") or ""
        names.add(name if name else f"unnamed_{ti}")
    degree = len(names)
    if degree >= MIN_DEGREE:
        filtered.append((lon, lat, degree))

print(f"Skipped {skipped_near_other} candidates too close to non-E intersections")

print(f"Filtered to {len(filtered)} intersections (degree >= 3)")

# De-duplicate: merge any remaining clusters within 20m
final = []
f_used = [False] * len(filtered)
for i in range(len(filtered)):
    if f_used[i]:
        continue
    lon_i, lat_i, deg_i = filtered[i]
    lons = [lon_i]
    lats = [lat_i]
    max_deg = deg_i
    f_used[i] = True
    for j in range(i+1, len(filtered)):
        if f_used[j]:
            continue
        lon_j, lat_j, deg_j = filtered[j]
        if dist_m(sum(lons)/len(lons), sum(lats)/len(lats), lon_j, lat_j) < 20:
            lons.append(lon_j)
            lats.append(lat_j)
            max_deg = max(max_deg, deg_j)
            f_used[j] = True
    final.append((sum(lons)/len(lons), sum(lats)/len(lats), max_deg))

print(f"After de-duplication: {len(final)} E-zone intersections")

# Build new intersection features
max_number = max((f["properties"].get("number", 0) for f in non_e), default=0)
new_e_features = []
for i, (lon, lat, degree) in enumerate(final):
    max_number += 1
    feat = {
        "type": "Feature",
        "properties": {
            "number": max_number,
            "degree": degree,
            "zone": "E",
        },
        "geometry": {
            "type": "Point",
            "coordinates": [round(lon, 7), round(lat, 7)]
        }
    }
    new_e_features.append(feat)

# Combine
all_features = non_e + new_e_features
output = {"type": "FeatureCollection", "features": all_features}

out_path = rf"{PROJ}\intersections_e_draft.geojson"
with open(out_path, "w") as f:
    json.dump(output, f, indent=2)

print(f"\nWrote {out_path}")
print(f"  {len(non_e)} non-E + {len(new_e_features)} new E = {len(all_features)} total")
