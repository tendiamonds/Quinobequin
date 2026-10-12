"""
Build the Upper Charles Forest website (4 pages):
  index.html  — landing page
  map.html    — interactive Leaflet map
  zones.html  — zone-by-zone intersection report
  owners.html — owner-grouped intersection report

All pages cross-link: intersection labels link to the map,
owner names link to the owner page, zone badges link to the zone page.
"""

import heapq
import json
import math
import re
from collections import OrderedDict, defaultdict

from trailmap import build_map_page, build_trail_int_map, dist_m

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"
TOWNS = {136: "Holliston", 139: "Hopkinton", 185: "Milford"}

TOWN_FOREST_LOCS = {
    "M_201192_880840",
    "M_200767_881204",
    "M_200582_881415",
    "M_200791_880798",
}
FAIRBANKS_LOCS = {
    "M_200659_879945",
}

EXIT_POINTS = {
    "A": (-71.4845932, 42.1782725),
    "B": (-71.5056, 42.1796),
    "C": (-71.498, 42.196),
    "D": (-71.493, 42.171),
    "E": (-71.500, 42.171),
    "F": (-71.485, 42.170),
}
F_G_GROUP = {36, 178, 213, 214, 176, 4, 129, 1, 245, 135, 9, 175, 10, 248, 130}

PUBLIC_ORDER = [
    "Adams Town Forest (Trustees CR)",
    "Fairbanks Land (Trustees/DCR CR)",
    "Town of Holliston",
    "Town of Hopkinton",
    "Town of Milford",
]

ZONE_COLORS = {
    "A": "#e74c3c", "B": "#3498db", "C": "#2ecc71",
    "D": "#f39c12", "E": "#9b59b6", "F": "#1abc9c",
}

ZONE_NAMES = {
    "A": "Adams Town Forest",
    "B": "Beaver Brook Woods",
    "C": "College Rock Park",
    "D": "Rocky Woods",
    "E": "NEMBA Land",
    "F": "Fairbanks",
}


def region():
    """This site's settings for the shared map app (trailmap.py)"""
    return {
        "name": "Upper Charles Forest",
        "zones": {z: {"name": ZONE_NAMES[z], "color": ZONE_COLORS[z]} for z in ZONE_COLORS},
        "view": {"center": [42.178, -71.498], "zoom": 14},
        "bounds": [[42.156, -71.518], [42.201, -71.483]],
        "storagePrefix": "vtn",   # kept from when this was the Vietnam Trail Network map
        # The prototype signs up now use an abandoned numbering, so no "I'm at this sign"
        "report": {"email": "tendiamonds@gmail.com", "signReports": False},
        "otherMaps": [{"name": "Blue Hills", "href": "bluehills/map.html"}],
        "zonesPage": True,
        "nav": nav_html("map"),
    }


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


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
        elif wu in ("INC.", "INC"):
            result.append("Inc.")
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
            if point_in_polygon(lon, lat, geom["coordinates"][0]):
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
            rings = list(geom["coordinates"])
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
        if upper in ("HOLLISTON, TOWN OF", "TOWN OF HOLLISTON",
                     "CONSERVATION COMMISSION", "UNKNOWN", ""):
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


# ---------------------------------------------------------------------------
# Data loading & processing
# ---------------------------------------------------------------------------

def build_trail_graph(ints, trails):
    """Build adjacency graph from trail segments snapped to intersections."""
    SNAP_DIST = 20
    int_pts = {}
    for feat in ints["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        int_pts[id(feat)] = (lon, lat, feat)

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
        for fid, (ilon, ilat, feat) in int_pts.items():
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


def load_and_process():
    with open(rf"{PROJ}\parcels_all.geojson") as f:
        parcels = json.load(f)
    with open(rf"{PROJ}\intersections_zoned.geojson") as f:
        ints = json.load(f)
    with open(rf"{PROJ}\trails_selected.geojson") as f:
        trails = json.load(f)

    # Labels are printed on signs, so once given they never change: each sign's label is
    # frozen in the data ("sign"), and only a new intersection without one is numbered,
    # after the highest label in its zone. Signless intersections (a post with no sign
    # like Post 4, or a landmark on a trail like Teetering Rock) aren't numbered at all.
    signed = {"features": [f for f in ints["features"] if not f["properties"].get("no_sign")]}
    graph = build_trail_graph(signed, trails)

    by_zone = {}
    feat_by_id = {}
    for feat in signed["features"]:
        z = feat["properties"]["zone"]
        by_zone.setdefault(z, []).append(feat)
        feat_by_id[id(feat)] = feat

    def order_subgroup(pts, ex, ey):
        exit_feat = min(pts, key=lambda f: dist_m(
            f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1], ex, ey))
        dists = dijkstra(graph, [id(exit_feat)])
        reachable = [(f, dists[id(f)]) for f in pts if id(f) in dists]
        unreachable = [f for f in pts if id(f) not in dists]
        reachable.sort(key=lambda pair: pair[1])
        unreachable.sort(key=lambda f: dist_m(
            f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1], ex, ey))
        return [f for f, _ in reachable] + unreachable

    for z in "ABCDEF":
        pts = by_zone.get(z, [])
        ex, ey = EXIT_POINTS[z]

        if z == "F":
            main_pts = [f for f in pts if f["properties"]["number"] not in F_G_GROUP]
            tail_pts = [f for f in pts if f["properties"]["number"] in F_G_GROUP]
            ordered = order_subgroup(main_pts, ex, ey) + order_subgroup(tail_pts, ex, ey)
        else:
            ordered = order_subgroup(pts, ex, ey)

        taken = [int(f["properties"]["sign"][1:]) for f in ordered if f["properties"].get("sign")]
        n = max(taken, default=0)
        for feat in ordered:
            if feat["properties"].get("sign"):
                feat["properties"]["label"] = feat["properties"]["sign"]
            else:
                n += 1
                feat["properties"]["label"] = "%s%d" % (z, n)
    for feat in ints["features"]:
        if feat["properties"].get("no_sign"):
            feat["properties"]["label"] = feat["properties"].get("code") or "P%d" % feat["properties"]["post"]

    rows = []
    for feat in ints["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        parcel = find_parcel(lon, lat, parcels)
        owner, town, is_public = classify_owner(parcel)
        feat["properties"]["owner"] = owner
        feat["properties"]["town"] = town
        feat["properties"]["is_public"] = is_public
        if feat["properties"].get("no_sign"):
            continue   # the zone and owner pages list signs
        rows.append({
            "label": feat["properties"]["label"],
            "zone": feat["properties"]["zone"],
            "owner": owner,
            "town": town,
            "is_public": is_public,
        })

    rows.sort(key=lambda r: (r["zone"], int(r["label"][1:])))
    return ints, trails, rows


# ---------------------------------------------------------------------------
# Shared HTML pieces
# ---------------------------------------------------------------------------

COMMON_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         color: #222; line-height: 1.5; }
  a { color: #2980b9; text-decoration: none; }
  a:hover { text-decoration: underline; }
"""

PAGE_CSS = COMMON_CSS + """
  .container { max-width: 960px; margin: 0 auto; padding: 24px 20px; }
  h1 { font-size: 24px; margin-bottom: 4px; }
  .subtitle { color: #666; margin-bottom: 24px; font-size: 14px; }
  h2 { font-size: 18px; margin: 28px 0 12px; padding-bottom: 6px; border-bottom: 2px solid #eee; }
  nav.topnav { background: #2c3e50; padding: 10px 20px; display: flex; gap: 18px;
               align-items: center; flex-wrap: wrap; }
  nav.topnav a { color: #ecf0f1; font-size: 14px; font-weight: 500; }
  nav.topnav a:hover { color: white; text-decoration: none; }
  nav.topnav .brand { font-weight: 700; font-size: 15px; margin-right: 12px; }
  table.report { width: 100%; border-collapse: collapse; margin: 12px 0 24px; font-size: 13px; }
  table.report th { text-align: left; padding: 8px 10px; background: #f7f7f7;
                    border-bottom: 2px solid #ddd; font-size: 12px; color: #555;
                    text-transform: uppercase; letter-spacing: 0.5px; }
  table.report td { padding: 7px 10px; border-bottom: 1px solid #eee; vertical-align: top; }
  table.report tr:hover { background: #fafafa; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 10px;
         font-size: 11px; font-weight: 600; }
  .tag-public { background: #d5f5e3; color: #1e8449; }
  .tag-private { background: #fadbd8; color: #922b21; }
  .tag-zone { color: white; padding: 2px 10px; border-radius: 10px;
              font-size: 11px; font-weight: 600; }
  .int-links { display: flex; flex-wrap: wrap; gap: 4px; }
  .int-links a { display: inline-block; padding: 1px 6px; border-radius: 4px;
                 font-size: 12px; font-weight: 600; background: #eee; color: #333; }
  .int-links a:hover { background: #d5e8f7; text-decoration: none; }
  .section-public { }
  .section-private { margin-top: 32px; }
"""


def nav_html(active):
    items = [
        ("index.html", "Home"),
        ("map.html", "Map"),
        ("zones.html", "Zones"),
        ("owners.html", "Owners"),
    ]
    parts = ['<nav class="topnav">']
    for href, label in items:
        style = "color:white;text-decoration:underline" if label.lower() == active else ""
        parts.append('<a href="%s" style="%s">%s</a>' % (href, style, label))
    parts.append('<a href="bluehills/map.html" style="margin-left:auto;opacity:0.8">Blue Hills &rarr;</a>')
    parts.append("</nav>")
    return "\n".join(parts)


def int_link(label):
    return '<a href="map.html?int=%s">%s</a>' % (label, label)


def int_links_html(labels):
    sorted_labels = sorted(labels, key=lambda l: (l[0], int(l[1:])))
    return '<span class="int-links">%s</span>' % " ".join(int_link(l) for l in sorted_labels)


def owner_link(owner):
    return '<a href="owners.html#%s">%s</a>' % (slugify(owner), owner)


def zone_link(zone):
    color = ZONE_COLORS[zone]
    name = ZONE_NAMES.get(zone, "")
    return '<a href="zones.html#zone-%s" class="tag tag-zone" style="background:%s">%s: %s</a>' % (
        zone, color, zone, name)


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def build_landing(rows):
    total = len(rows)
    public_count = sum(1 for r in rows if r["is_public"])
    private_count = total - public_count
    owners = set(r["owner"] for r in rows)

    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#2c3e50">
<title>Upper Charles Forest</title>
<style>PAGE_CSS
  .hero { text-align: center; padding: 48px 20px 32px; }
  .hero h1 { font-size: 32px; margin-bottom: 8px; }
  .hero .sub { color: #666; font-size: 16px; margin-bottom: 32px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
           gap: 16px; max-width: 860px; margin: 0 auto; padding: 0 20px; }
  .card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;
          transition: box-shadow 0.15s; }
  .card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.1); }
  .card h3 { font-size: 16px; margin-bottom: 6px; }
  .card p { color: #555; font-size: 13px; margin-bottom: 12px; }
  .card a.btn { display: inline-block; padding: 6px 16px; border-radius: 4px;
                background: #2980b9; color: white; font-size: 13px; font-weight: 600; }
  .card a.btn:hover { background: #2471a3; text-decoration: none; }
  .about { max-width: 700px; margin: 40px auto; padding: 0 20px 48px; font-size: 14px;
           color: #444; line-height: 1.7; }
  .about h2 { font-size: 18px; margin-bottom: 12px; color: #222; }
  .stats { display: flex; gap: 32px; justify-content: center; margin: 24px 0 36px;
           flex-wrap: wrap; }
  .stat { text-align: center; }
  .stat .num { font-size: 28px; font-weight: 700; color: #2c3e50; }
  .stat .lbl { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
  .zone-table { width: 100%; border-collapse: collapse; margin: 12px 0 20px; font-size: 13px; }
  .zone-table th { text-align: left; padding: 8px 10px; background: #f7f7f7;
                   border-bottom: 2px solid #ddd; font-size: 12px; color: #555;
                   text-transform: uppercase; letter-spacing: 0.5px; }
  .zone-table td { padding: 7px 10px; border-bottom: 1px solid #eee; }
</style>
</head>
<body>
NAV_PLACEHOLDER
<div class="hero">
  <h1>Upper Charles Forest</h1>
  <p class="sub">Holliston, Hopkinton &amp; Milford, Massachusetts</p>
  <div class="stats">
    <div class="stat"><div class="num">TOTAL_COUNT</div><div class="lbl">Intersections</div></div>
    <div class="stat"><div class="num">OWNER_COUNT</div><div class="lbl">Landowners</div></div>
    <div class="stat"><div class="num">6</div><div class="lbl">Zones</div></div>
    <div class="stat"><div class="num">PUBLIC_PCT%</div><div class="lbl">Public Land</div></div>
  </div>
</div>
<div class="cards">
  <div class="card">
    <h3>Interactive Map</h3>
    <p>Explore all trails and numbered intersections. Click any marker to see
    owner, town, and zone information.</p>
    <a class="btn" href="map.html">Open Map</a>
  </div>
  <div class="card">
    <h3>Zone Report</h3>
    <p>Intersections organized by zone (A through F), showing which landowners
    are in each zone.</p>
    <a class="btn" href="zones.html">View Zones</a>
  </div>
  <div class="card">
    <h3>Owner Report</h3>
    <p>All public and private landowners and which intersections fall on their
    parcels.</p>
    <a class="btn" href="owners.html">View Owners</a>
  </div>
</div>
<div class="about">
  <h2>About This Project</h2>
  <p>The Holliston Town Forest Committee is developing a wayfinding sign system for
  trail intersections in the forest area spanning Holliston, Milford, and Hopkinton,
  near the headwaters of the Charles River. We call it the Upper Charles Forest; riders
  have long known these trails as &ldquo;Vietnam.&rdquo;</p>

  <p>This project is a collaboration with the Holliston Conservation Commission,
  The Trustees of Reservations, the New England Mountain Bike Association,
  the Hopkinton Trails Committee, and the Milford Conservation Commission.</p>

  <h2>Zoning Philosophy</h2>
  <p>The full area is divided into 6 regions spanning across three towns. The regions are
  broken up by how they feel connected in the woods &mdash; they are loosely based on actual
  parcels in the area, but not a 1-to-1 matchup. The regions do not adhere to town boundaries
  either, so some regions span multiple towns. Every sign is in exactly one town and exactly one
  region.</p>

  <p>Several non-town organizations have overlapping concerns in the area, including
  The Trustees of Reservations, New England Mountain Bike Association, and DCR.
  Signs that fall on an organization&rsquo;s parcel will carry that organization&rsquo;s
  logo or name, so each sign accurately reflects who manages the land it stands on.</p>

  <p>As we reach out to private parcel owners whose land the trail network crosses,
  we will offer them the option to add a small image or logo to the corner of the
  signs on their parcels.</p>

  <table class="zone-table">
    <thead><tr><th>Zone</th><th>Name</th><th>Towns</th></tr></thead>
    <tbody>
      <tr><td><a href="zones.html#zone-A" class="tag tag-zone" style="background:#e74c3c">A</a></td>
          <td>Adams Town Forest</td><td>Holliston</td></tr>
      <tr><td><a href="zones.html#zone-B" class="tag tag-zone" style="background:#3498db">B</a></td>
          <td>Beaver Brook Woods</td><td>Milford, Holliston</td></tr>
      <tr><td><a href="zones.html#zone-C" class="tag tag-zone" style="background:#2ecc71">C</a></td>
          <td>College Rock Park</td><td>Hopkinton, Holliston, Milford</td></tr>
      <tr><td><a href="zones.html#zone-D" class="tag tag-zone" style="background:#f39c12">D</a></td>
          <td>Rocky Woods</td><td>Holliston, Milford</td></tr>
      <tr><td><a href="zones.html#zone-E" class="tag tag-zone" style="background:#9b59b6">E</a></td>
          <td>NEMBA Land</td><td>Milford, Holliston</td></tr>
      <tr><td><a href="zones.html#zone-F" class="tag tag-zone" style="background:#1abc9c">F</a></td>
          <td>Fairbanks</td><td>Holliston, Milford</td></tr>
    </tbody>
  </table>

  <h2>Sign Design</h2>
  <p>Each intersection will have a sign with the following elements:</p>
  <ul style="margin:8px 0 8px 20px">
    <li>A letter-number combination that uniquely identifies the intersection (e.g. A1, C14).
    The letter corresponds to the zone; lower numbers are generally closer to parking areas.</li>
    <li>The name of the town the intersection is in</li>
    <li>The name of the zone</li>
    <li>The town seal</li>
    <li>The logo of the non-town organization for the zone</li>
  </ul>
  <p style="margin-top:16px">Sample signs:</p>
  <div style="display:flex;gap:12px;flex-wrap:wrap;margin:12px 0">
    <img src="sign_sample_1.png" alt="Sample sign A1 — Holliston, Adams Town Forest" style="width:200px;border-radius:6px;border:1px solid #ddd">
    <img src="sign_sample_2.png" alt="Sample sign E1 — Milford, NEMBA Land" style="width:200px;border-radius:6px;border:1px solid #ddd">
    <img src="sign_sample_3.png" alt="Sample sign C1 — Hopkinton, College Rock Park" style="width:200px;border-radius:6px;border:1px solid #ddd">
  </div>

  <h2>Entry Kiosks</h2>
  <p>Kiosks at major entry points will have a full map of the area, a description of the
  signage system, and descriptions and logos for all towns and organizations represented.
  Entry points include:</p>
  <ul style="margin:8px 0 8px 20px">
    <li>College Rock Park</li>
    <li>Adams Street Parking Lot</li>
    <li>Dunster Road Trailhead</li>
    <li>The "Milford Byway" connection to the Milford Rail Trail</li>
    <li>The "Chicken Run" connection to the Milford Rail Trail side path</li>
  </ul>

  <h2>Land Ownership</h2>
  <p>Holliston public land is classified into three categories based on deed records:</p>
  <ul style="margin:8px 0 8px 20px">
    <li><strong>Adams Town Forest</strong> &mdash; ~87 acres with a Conservation Restriction
    held by The Trustees of Reservations</li>
    <li><strong>Fairbanks Land</strong> &mdash; 210 acres with a CR co-held by
    The Trustees and DCR</li>
    <li><strong>Town of Holliston</strong> &mdash; other town-owned conservation parcels</li>
  </ul>
  <p>See the <a href="owners.html">Owner Report</a> for the full breakdown of all public
  and private parcels the trail network crosses.</p>

  <h2>Contact</h2>
  <p>This project is led by the Holliston Town Forest Committee. If you have questions or
  comments, please email
  <a href="mailto:townforest@holliston.k12.ma.us">townforest@holliston.k12.ma.us</a>.</p>

  <h2>Data Sources</h2>
  <p>OpenStreetMap (trails), MassGIS (parcels), Holliston assessor records via Tyler/iasWorld
  (deed research).</p>
</div>
</body>
</html>"""

    pct = int(round(100 * public_count / total)) if total else 0
    html = html.replace("NAV_PLACEHOLDER", nav_html("home"))
    html = html.replace("TOTAL_COUNT", str(total))
    html = html.replace("OWNER_COUNT", str(len(owners)))
    html = html.replace("PUBLIC_PCT", str(pct))
    html = html.replace("PAGE_CSS", PAGE_CSS)

    with open(rf"{PROJ}\index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote index.html")


def build_zones_page(rows):
    lines = ["""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#2c3e50">
<title>Zone Report — Upper Charles Forest</title>
<style>""", PAGE_CSS, """</style>
</head>
<body>""", nav_html("zones"), """
<div class="container">
<h1>Zone Report</h1>
<p class="subtitle">Intersections grouped by zone, with owners combined within each zone.</p>
"""]

    for zone in "ABCDEF":
        zone_rows = [r for r in rows if r["zone"] == zone]
        color = ZONE_COLORS[zone]
        zname = ZONE_NAMES.get(zone, "")
        lines.append('<h2 id="zone-%s"><span class="tag tag-zone" style="background:%s">%s</span> %s &mdash; %d intersections</h2>'
                     % (zone, color, zone, zname, len(zone_rows)))
        lines.append('<table class="report"><thead><tr><th>Owner</th><th>Town</th><th>Intersections</th></tr></thead><tbody>')

        groups = OrderedDict()
        for r in zone_rows:
            key = (r["owner"], r["town"])
            groups.setdefault(key, []).append(r["label"])

        for (owner, town), labels in groups.items():
            lines.append('<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
                         % (owner_link(owner), town, int_links_html(labels)))

        lines.append("</tbody></table>")

    lines.append("</div></body></html>")

    with open(rf"{PROJ}\zones.html", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Wrote zones.html")


def build_owners_page(rows):
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

    public.sort(key=lambda g: (
        PUBLIC_ORDER.index(g["owner"]) if g["owner"] in PUBLIC_ORDER else 99,
    ))
    private.sort(key=lambda g: g["owner"])

    total_pub = sum(len(g["labels"]) for g in public)
    total_priv = sum(len(g["labels"]) for g in private)

    lines = ["""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#2c3e50">
<title>Owner Report — Upper Charles Forest</title>
<style>""", PAGE_CSS, """</style>
</head>
<body>""", nav_html("owners"), """
<div class="container">
<h1>Owner Report</h1>
<p class="subtitle">TOTAL intersections across OWNER_CT owners.</p>
"""]

    lines.append('<div class="section-public">')
    lines.append('<h2>Public Parcels <span class="tag tag-public">%d intersections</span></h2>' % total_pub)
    lines.append('<table class="report"><thead><tr><th>Owner</th><th>Town</th><th>Intersections</th></tr></thead><tbody>')
    for g in public:
        town = ", ".join(sorted(g["towns"]))
        slug = slugify(g["owner"])
        zones_in = sorted(set(l[0] for l in g["labels"]))
        zone_tags = " ".join(zone_link(z) for z in zones_in)
        lines.append('<tr id="%s"><td><strong>%s</strong><br>%s</td><td>%s</td><td>%s</td></tr>'
                     % (slug, g["owner"], zone_tags, town, int_links_html(g["labels"])))
    lines.append("</tbody></table></div>")

    lines.append('<div class="section-private">')
    lines.append('<h2>Private Parcels <span class="tag tag-private">%d intersections</span></h2>' % total_priv)
    lines.append('<table class="report"><thead><tr><th>Owner</th><th>Town</th><th>Intersections</th></tr></thead><tbody>')
    for g in private:
        town = ", ".join(sorted(g["towns"]))
        slug = slugify(g["owner"])
        zones_in = sorted(set(l[0] for l in g["labels"]))
        zone_tags = " ".join(zone_link(z) for z in zones_in)
        lines.append('<tr id="%s"><td><strong>%s</strong><br>%s</td><td>%s</td><td>%s</td></tr>'
                     % (slug, g["owner"], zone_tags, town, int_links_html(g["labels"])))
    lines.append("</tbody></table></div>")

    lines.append("</div></body></html>")

    html = "\n".join(lines)
    html = html.replace("TOTAL", str(total_pub + total_priv))
    html = html.replace("OWNER_CT", str(len(public) + len(private)))

    with open(rf"{PROJ}\owners.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote owners.html")





# ---------------------------------------------------------------------------

def main():
    ints, trails, rows = load_and_process()
    print("Processed %d intersections" % len(rows))

    build_landing(rows)
    build_map_page(ints, trails, region(), PROJ)
    build_zones_page(rows)
    build_owners_page(rows)


if __name__ == "__main__":
    main()
