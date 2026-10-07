"""
Build the Vietnam Trail Network website (4 pages):
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

def dist_m(lon1, lat1, lon2, lat2):
    return math.sqrt(((lon1 - lon2) * 82000)**2 + ((lat1 - lat2) * 111000)**2)


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

    graph = build_trail_graph(ints, trails)

    by_zone = {}
    feat_by_id = {}
    for feat in ints["features"]:
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

        for i, feat in enumerate(ordered, 1):
            feat["properties"]["label"] = "%s%d" % (z, i)

    rows = []
    for feat in ints["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        parcel = find_parcel(lon, lat, parcels)
        owner, town, is_public = classify_owner(parcel)
        feat["properties"]["owner"] = owner
        feat["properties"]["town"] = town
        feat["properties"]["is_public"] = is_public
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
<title>Vietnam Trail Network</title>
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
  <h1>Vietnam Trail Network</h1>
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
  trail intersections in the forest area spanning Holliston, Milford, and Hopkinton.
  The network is commonly known as the &ldquo;Vietnam Trail Network&rdquo; or the
  &ldquo;Upper Charles&rdquo; trails.</p>

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
<title>Zone Report — Vietnam Trail Network</title>
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
<title>Owner Report — Vietnam Trail Network</title>
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


def build_trail_int_map(ints, trails):
    """Map each trail feature index to its intersections with distances."""
    SNAP_DIST = 20
    int_list = [(feat["properties"]["label"],
                 feat["geometry"]["coordinates"][0],
                 feat["geometry"]["coordinates"][1])
                for feat in ints["features"]]

    def cumulative_distances(coords):
        cum = [0.0]
        for i in range(1, len(coords)):
            cum.append(cum[-1] + dist_m(coords[i-1][0], coords[i-1][1],
                                         coords[i][0], coords[i][1]))
        return cum

    result = {}
    for ti, trail in enumerate(trails["features"]):
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
        total_length = cum[-1]

        hits = []
        for label, ilon, ilat in int_list:
            best_d = float("inf")
            best_cum = 0
            for j, c in enumerate(coords):
                d = dist_m(ilon, ilat, c[0], c[1])
                if d < best_d:
                    best_d = d
                    best_cum = cum[j]
            if best_d < SNAP_DIST:
                hits.append((best_cum, label))

        hits.sort()
        result[ti] = {
            "length": round(total_length),
            "ints": [[label, round(d)] for d, label in hits]
        }

    return result


def build_map_page(ints, trails, rows):
    for i, f in enumerate(trails["features"]):
        f["properties"]["_idx"] = i

    int_data = json.dumps(ints)
    trail_data = json.dumps(trails)

    n_trails = len(trails["features"])
    n_ints = len(ints["features"])
    trail_names = set()
    for f in trails["features"]:
        name = f["properties"].get("pdf_name") or f["properties"].get("name") or ""
        if name:
            trail_names.add(name)
    n_names = len(trail_names)

    trail_int_map = build_trail_int_map(ints, trails)
    trail_int_json = json.dumps(trail_int_map)

    int_trail_map = {}
    for ti_str, info in trail_int_map.items():
        ti = int(ti_str)
        feat = trails["features"][ti]
        name = feat["properties"].get("pdf_name") or feat["properties"].get("name") or ""
        if not name:
            name = "Unnamed"
        total_length = info["length"]
        ints_list = info["ints"]

        for i, (label, cum_dist) in enumerate(ints_list):
            if label not in int_trail_map:
                int_trail_map[label] = []

            if i > 0:
                prev_label = ints_list[i - 1][0]
                prev_dist = round(cum_dist - ints_list[i - 1][1])
                int_trail_map[label].append([name, prev_label, prev_dist])
            elif cum_dist > 3:
                int_trail_map[label].append([name, None, round(cum_dist)])

            if i < len(ints_list) - 1:
                next_label = ints_list[i + 1][0]
                next_dist = round(ints_list[i + 1][1] - cum_dist)
                int_trail_map[label].append([name, next_label, next_dist])
            elif total_length - cum_dist > 3:
                int_trail_map[label].append([name, None, round(total_length - cum_dist)])

    int_trail_json = json.dumps(int_trail_map)

    html = MAP_TEMPLATE
    html = html.replace("__NAV__", nav_html("map"))
    html = html.replace("__TRAIL_DATA__", trail_data)
    html = html.replace("__INT_DATA__", int_data)
    html = html.replace("__TRAIL_INT_MAP__", trail_int_json)
    html = html.replace("__INT_TRAIL_MAP__", int_trail_json)
    html = html.replace("__N_INTS__", str(n_ints))
    html = html.replace("__N_TRAILS__", str(n_trails))
    html = html.replace("__N_NAMES__", str(n_names))

    with open(rf"{PROJ}\map.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote map.html")


# ---------------------------------------------------------------------------
# Map HTML template
# ---------------------------------------------------------------------------

MAP_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<title>Map — Vietnam Trail Network</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  a { color: #2980b9; text-decoration: none; }
  a:hover { text-decoration: underline; }
  nav.topnav { background: #2c3e50; padding: 10px 20px; display: flex; gap: 18px;
               align-items: center; flex-wrap: wrap; position: relative; z-index: 1001; }
  nav.topnav a { color: #ecf0f1; font-size: 14px; font-weight: 500; }
  nav.topnav a:hover { color: white; text-decoration: none; }
  nav.topnav .brand { font-weight: 700; font-size: 15px; margin-right: 12px; }
  #map { height: calc(100vh - 42px); width: 100%; }

  .info-panel {
    position: absolute; top: 52px; left: 10px; z-index: 1000;
    background: white; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.25);
    width: 300px; max-height: calc(100vh - 62px); overflow: hidden;
    display: flex; flex-direction: column;
    font-size: 13px;
  }
  .info-panel h2 {
    font-size: 15px; padding: 12px 40px 8px 14px; margin: 0;
    border-bottom: 1px solid #e0e0e0;
  }
  .info-panel .content { padding: 10px 14px 14px; overflow-y: auto; min-height: 0; }
  .panel-size { position: absolute; top: 7px; right: 7px; z-index: 1; width: 28px; height: 28px;
    padding: 4px; border: none; border-radius: 4px; background: none; color: #666; cursor: pointer; }
  .panel-size:hover { background: #eee; color: #222; }
  .panel-size svg { display: block; }
  .info-panel.compact h2 { display: none; }
  .info-panel.compact .content { padding: 10px 40px 10px 12px; }
  .info-panel.compact .full-only, .info-panel:not(.compact) .compact-only { display: none !important; }
  .info-panel table { width: 100%; border-collapse: collapse; }
  .info-panel td { padding: 3px 0; vertical-align: top; }
  .info-panel td:first-child { font-weight: 600; width: 90px; color: #555; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 10px;
         font-size: 11px; font-weight: 600; }
  .tag-public { background: #d5f5e3; color: #1e8449; }
  .tag-private { background: #fadbd8; color: #922b21; }
  .tag-zone { color: white; padding: 2px 10px; }

  .legend-panel {
    position: absolute; bottom: 24px; left: 10px; z-index: 1000;
    background: white; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.25);
    padding: 10px 14px; font-size: 12px;
  }
  .legend-panel h3 { font-size: 13px; margin-bottom: 6px; }
  .legend-row { display: flex; align-items: center; margin: 3px 0; }
  .legend-swatch {
    width: 14px; height: 14px; border-radius: 50%; margin-right: 8px;
    border: 2px solid white; box-shadow: 0 0 2px rgba(0,0,0,0.3); flex-shrink: 0;
  }
  .legend-line {
    width: 20px; height: 3px; margin-right: 8px; border-radius: 2px; flex-shrink: 0;
  }

  .zone-filter {
    position: absolute; top: 52px; right: 54px; z-index: 1000;
    background: white; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.25);
    padding: 10px 14px; font-size: 12px;
  }
  .zone-filter h3 { font-size: 13px; margin-bottom: 6px; }
  .zone-btn {
    display: inline-block; width: 32px; height: 28px; line-height: 28px;
    text-align: center; border-radius: 4px; margin: 2px;
    cursor: pointer; font-weight: 700; font-size: 13px;
    color: white; border: 2px solid transparent; transition: opacity 0.15s;
    user-select: none;
  }
  .zone-btn.off { opacity: 0.3; }
  .zone-btn-all {
    display: inline-block; height: 28px; line-height: 28px; padding: 0 10px;
    text-align: center; border-radius: 4px; margin: 2px;
    cursor: pointer; font-weight: 600; font-size: 11px;
    background: #eee; color: #333; border: 1px solid #ccc; user-select: none;
  }

  .marker-label {
    background: none !important; border: none !important; box-shadow: none !important;
    font-size: 10px; font-weight: bold; font-family: -apple-system, sans-serif;
    white-space: nowrap;
  }
  .pulse-ring { animation: pulse 1.5s ease-in-out infinite; }
  @keyframes pulse {
    0%, 100% { opacity: 0.7; }
    50% { opacity: 0.25; }
  }
  .int-list { margin-top: 8px; }
  .int-list .int-row { display: flex; align-items: center; gap: 6px; padding: 3px 0; }
  .int-link {
    font-weight: 700; cursor: pointer; padding: 1px 6px; border-radius: 4px;
    font-size: 12px; color: white; display: inline-block; min-width: 36px; text-align: center;
  }
  .int-link:hover { opacity: 0.8; text-decoration: none; }
  .int-list .int-dist { color: #888; font-size: 11px; }
  .int-list .seg-bar { color: #bbb; font-size: 10px; padding: 0 0 0 16px; }
  .int-terminus { display: inline-block; width: 12px; height: 12px; background: #333;
    border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 2px rgba(0,0,0,0.3); }

  #searchBadge {
    position: fixed; top: 12px; left: 50%; transform: translateX(-50%); z-index: 2000;
    background: rgba(0,0,0,0.82); color: #fff; font: 600 22px/1 monospace;
    padding: 8px 18px; border-radius: 8px; display: none;
    pointer-events: none; letter-spacing: 2px;
  }
  .route-btn {
    display: inline-block; margin-top: 8px; padding: 5px 14px; font-size: 12px;
    font-weight: 600; color: #fff; background: #2980b9; border: none; border-radius: 4px;
    cursor: pointer;
  }
  .route-btn:hover { background: #1a6da0; }
  .route-msg {
    margin-top: 8px; padding: 8px 12px; background: #eaf2f8; border-left: 3px solid #2980b9;
    font-size: 12px; color: #2c3e50;
  }
  .route-step { display: flex; align-items: center; gap: 6px; margin: 4px 0; font-size: 12px; }
  .route-arrow { color: #0d47a1; font-weight: 700; }
  .route-trail-name { color: #555; font-style: italic; }
  .entry-diamond { width: 24px; height: 24px; margin: 5px; transform: rotate(45deg);
    border: 4px solid #555; background: rgba(255,255,255,0.9); box-sizing: border-box;
    box-shadow: 0 0 0 1.5px #222; }
  .legend-diamond { width: 12px; height: 12px; margin: 2px 6px 2px 2px; border-width: 2px; display: inline-block; box-shadow: none; }
  .entry-tag { font-size: 11px; font-weight: 700; color: #333; }
  .parking-badge { position: absolute; left: -9px; top: 22px; width: 15px; height: 15px;
    border-radius: 3px; background: #1565c0; color: #fff; border: 1.5px solid #fff;
    font: 700 11px/15px sans-serif; text-align: center; box-shadow: 0 0 0 1px #0d3c78; }
  .legend-row .parking-badge { position: static; display: inline-block; margin: 0 6px 0 1px; vertical-align: middle; }
  .parking-tag { font-size: 11px; font-weight: 700; color: #1565c0; margin-left: 6px; }
  .connects-tag { font-size: 11px; color: #555; margin-top: 2px; }
  .locate-ctl a { display: flex; align-items: center; justify-content: center; }
  .locate-ctl a.active { color: #1e88e5; }
  .locate-ctl a.following { background: #1e88e5; color: #fff; }
  .user-icon { background: none; border: none; }
  .user-dot { width: 18px; height: 18px; margin: 6px; border-radius: 50%; background: #1e88e5;
    border: 3px solid #fff; box-shadow: 0 0 0 1px rgba(0,0,0,0.25), 0 1px 4px rgba(0,0,0,0.4); box-sizing: border-box; }
  .user-arrow { width: 30px; height: 30px; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.45)); }
  .user-arrow svg { display: block; }
  .live-tag { font-size: 10px; font-weight: 700; color: #fff; background: #c62828; border-radius: 3px;
    padding: 1px 5px; vertical-align: middle; animation: live-pulse 2s ease-in-out infinite; }
  @keyframes live-pulse { 50% { opacity: 0.55; } }
  .crumb-clear { font-size: 11px; color: #1e88e5; cursor: pointer; }
  .seg-view { padding: 4px 2px 0; }
  .seg-row { display: flex; align-items: center; padding-top: 18px; }
  .seg-part { position: relative; flex-basis: 0; min-width: 52px; height: 4px; background: #555;
    border-radius: 2px; margin: 0 -1px; }
  .seg-dist { position: absolute; bottom: 7px; left: 50%; transform: translateX(-50%);
    font-size: 11px; color: #333; white-space: nowrap; }
  .seg-you { flex: none; width: 16px; height: 16px; border-radius: 50%; background: #1e88e5;
    border: 3px solid #fff; box-shadow: 0 0 0 1px #1e88e5; position: relative; z-index: 1; }
  .seg-you-slot { flex: none; display: flex; position: relative; z-index: 1; }
  .seg-you-arrow { display: block; width: 24px; height: 24px; margin: 0 -2px;
    filter: drop-shadow(0 1px 1px rgba(0,0,0,0.4)); }
  .seg-you-arrow svg { display: block; width: 24px; height: 24px; }
  .int-link.seg-end { background: #999; cursor: default; font-weight: 600; }
  .seg-trail { text-align: center; font-size: 12px; color: #555; margin-top: 6px; }
  .you-badge { display: inline-block; padding: 1px 7px; border-radius: 10px; background: #1e88e5;
    color: #fff; font-size: 11px; font-weight: 700; }
  .int-link.passed { filter: grayscale(1); opacity: 0.4; }
  .int-link.here { box-shadow: 0 0 0 2px #fff, 0 0 0 4px #1e88e5; }
  .route-step.passed .route-arrow, .route-step.passed .route-trail-name,
  .route-step.passed .int-dist { color: #bbb; }
  .route-compact-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
    font-size: 13px; margin-bottom: 6px; }
  .route-row { display: flex; align-items: center; overflow-x: auto; position: relative;
    padding: 5px 4px 7px; scrollbar-width: none; }
  .route-row::-webkit-scrollbar { display: none; }
  .route-row .int-link { flex: none; min-width: 30px; }
  .rr-link { flex: none; width: 14px; border-top: 3px dashed #0d47a1; margin: 0 3px; }
  .rr-link.passed { border-top-color: #bbb; }
  .route-row .seg-you { margin: 0 1px; }
  .exits { margin-top: 10px; padding-top: 8px; border-top: 1px solid #eee; }
  .exits-head { font-size: 12px; font-weight: 600; color: #555; margin-bottom: 4px; }
  .exit-btn { display: flex; align-items: center; gap: 8px; width: 100%; margin: 4px 0; padding: 6px 8px;
    border: 1px solid #cfd8dc; border-radius: 6px; background: #f7f9fa; cursor: pointer;
    font: inherit; text-align: left; }
  .exit-btn:hover { background: #eaf2f8; }
  .exit-dist { font-weight: 600; color: #222; }
  .exit-note { font-size: 11px; color: #666; }

  @media (max-width: 640px) {
    .info-panel { width: calc(100vw - 20px); top: auto; bottom: 0; left: 0;
      border-radius: 12px 12px 0 0; max-height: 45vh; }
    .zone-filter { top: 52px; left: 10px; right: auto; }
    .legend-panel { display: none; }
  }
</style>
</head>
<body>
__NAV__
<div id="map"></div>
<div id="searchBadge"></div>

<div class="info-panel" id="infoPanel">
  <button class="panel-size" id="panelSize" onclick="togglePanelSize()"></button>
  <h2>Vietnam Trail Network</h2>
  <div class="content" id="infoContent">
    <p style="color:#888">Click a trail or intersection marker for details.</p>
    <p style="margin-top:8px;color:#888;font-size:11px">__N_INTS__ numbered intersections across 6 zones.<br>
    __N_TRAILS__ trail segments, __N_NAMES__ named trails.</p>
  </div>
</div>

<div class="zone-filter" id="zoneFilter">
  <h3>Zones</h3>
  <div id="zoneButtons"></div>
</div>

<div class="legend-panel">
  <h3>Legend</h3>
  <div class="legend-row"><div class="legend-line" style="background:#2c3e50"></div> Trail</div>
  <div class="legend-row"><div class="legend-line" style="background:#00b8d4;height:4px"></div> Trail (highlighted)</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#888"></div> Intersection</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#f1c40f;border-color:#222"></div> Selected</div>
  <div class="legend-row"><div class="entry-diamond legend-diamond"></div> Entry point</div>
  <div class="legend-row"><div class="parking-badge">P</div> Parking</div>
</div>

<script>
var ZONE_COLORS = {
  A: "#e74c3c", B: "#3498db", C: "#2ecc71",
  D: "#f39c12", E: "#9b59b6", F: "#1abc9c"
};
var ZONE_NAMES = {
  A: "Adams Town Forest", B: "Beaver Brook Woods", C: "College Rock Park",
  D: "Rocky Woods", E: "NEMBA Land", F: "Fairbanks"
};

var trailData = __TRAIL_DATA__;
var intData = __INT_DATA__;
var trailIntMap = __TRAIL_INT_MAP__;
var intTrailMap = __INT_TRAIL_MAP__;

// Build adjacency graph for routing
var routeGraph = {};
Object.keys(intTrailMap).forEach(function(label) {
  if (!routeGraph[label]) routeGraph[label] = [];
  (intTrailMap[label] || []).forEach(function(c) {
    if (c[1]) routeGraph[label].push({to: c[1], dist: c[2], trail: c[0]});
  });
});

// Shortest paths from start to everywhere. The graph never changes, so each start's
// tree is worked out once and kept; a live locate panel asks for the same few often.
var pathTrees = {};
function pathTree(start) {
  if (pathTrees[start]) return pathTrees[start];
  var dist = {}, prev = {}, via = {}, visited = {};
  Object.keys(routeGraph).forEach(function(n) { dist[n] = Infinity; });
  dist[start] = 0;
  var queue = [{node: start, d: 0}];
  while (queue.length > 0) {
    queue.sort(function(a, b) { return a.d - b.d; });
    var u = queue.shift();
    if (visited[u.node]) continue;
    visited[u.node] = true;
    (routeGraph[u.node] || []).forEach(function(edge) {
      var alt = dist[u.node] + edge.dist;
      if (alt < dist[edge.to]) {
        dist[edge.to] = alt;
        prev[edge.to] = u.node;
        via[edge.to] = edge.trail;
        queue.push({node: edge.to, d: alt});
      }
    });
  }
  return (pathTrees[start] = {dist: dist, prev: prev, via: via});
}

function dijkstra(start, end) {
  var tree = pathTree(start), result = null;
  // Also covers an end that isn't in the graph (dist[end] undefined)
  if (tree.dist[end] < Infinity) {
    var path = [], node = end;
    while (node) {
      path.unshift({label: node, trail: tree.via[node] || null});
      node = tree.prev[node];
    }
    result = {path: path, totalDist: tree.dist[end]};
  }
  return result;
}

var routeMode = false;
var plan = null;       // the route on the map; see renderRoute
var routeFrom = null;
var routeLine = null;
var routeMarkers = [];
var currentIntFeature = null;
var userLatLng = null;

var map = L.map("map", {zoomControl: false}).setView([42.178, -71.498], 14);
L.control.zoom({position: "topright"}).addTo(map);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '&copy; <a href="https://osm.org/copyright">OSM</a>',
  maxZoom: 19
}).addTo(map);

var selectedTrailLayer = null;
var highlightedSegments = [];

var trailsByName = {};
trailData.features.forEach(function(f) {
  var name = f.properties.pdf_name || f.properties.name || "";
  if (!trailsByName[name]) trailsByName[name] = [];
  trailsByName[name].push(f);
});

var trailLayer = L.geoJSON(trailData, {
  style: function() { return {color: "#2c3e50", weight: 3, opacity: 0.6}; },
  onEachFeature: function(feature, layer) {
    layer.on("click", function(e) {
      L.DomEvent.stopPropagation(e);
      showTrailInfo(feature, layer);
    });
    layer.on("mouseover", function() {
      if (highlightedSegments.indexOf(layer) === -1)
        layer.setStyle({weight: 5, opacity: 0.9});
    });
    layer.on("mouseout", function() {
      if (highlightedSegments.indexOf(layer) === -1)
        layer.setStyle({weight: 3, opacity: 0.6});
    });
  }
}).addTo(map);

var zoneVisible = {A:true, B:true, C:true, D:true, E:true, F:true};
var intMarkers = {};
var labelMarkers = {};
var selectedMarker = null;
var selectedRing = null;
var intFeatures = {};
var entryMarkers = {};
map.createPane("entryPane").style.zIndex = 390;

intData.features.forEach(function(f) {
  var zone = f.properties.zone;
  var label = f.properties.label;
  var ll = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
  var color = ZONE_COLORS[zone];

  if (f.properties.entry) {
    var em = L.marker(ll, {
      pane: "entryPane", interactive: false,
      icon: L.divIcon({className: "", iconSize: [34, 34], iconAnchor: [17, 17],
        html: '<div class="entry-diamond" style="border-color:' + color + '"></div>' +
          (f.properties.parking ? '<div class="parking-badge">P</div>' : '')})
    }).addTo(map);
    em._zone = zone;
    entryMarkers[label] = em;
  }

  var marker = L.circleMarker(ll, {
    radius: 7, fillColor: color, color: "#fff",
    weight: 2, fillOpacity: 0.85
  }).addTo(map);
  marker.on("click", function(e) {
    L.DomEvent.stopPropagation(e);
    if (routeMode) {
      completeRoute(f.properties.label);
    } else {
      showIntInfo(f, marker);
    }
  });
  intMarkers[label] = marker;
  intFeatures[label] = f;
  marker._zone = zone;

  var lbl = L.marker(ll, {
    icon: L.divIcon({
      className: "marker-label",
      html: '<span style="color:' + color + ';text-shadow:1px 1px 0 #fff,-1px 1px 0 #fff,1px -1px 0 #fff,-1px -1px 0 #fff">' + label + '</span>',
      iconAnchor: [-6, 12]
    }),
    interactive: false
  }).addTo(map);
  labelMarkers[label] = lbl;
  lbl._zone = zone;
});

function ownerSlug(s) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

// Text from the data, made safe to put in HTML (some trail names contain quotes)
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// A string as a JavaScript argument inside an onclick-style attribute
function jsArg(s) { return esc(JSON.stringify(String(s))); }

function showIntInfo(feature, marker) {
  clearSelection(true);
  marker.setStyle({fillColor: "#f1c40f", radius: 11, weight: 3, color: "#222", fillOpacity: 1});
  selectedMarker = marker;
  selectedRing = L.circleMarker(marker.getLatLng(), {
    radius: 20, color: "#f1c40f", weight: 2, fillOpacity: 0, opacity: 0.7,
    dashArray: "4,4", className: "pulse-ring"
  }).addTo(map);

  var p = feature.properties;
  var pubTag = p.is_public
    ? '<span class="tag tag-public">Public</span>'
    : '<span class="tag tag-private">Private</span>';
  var zoneTag = '<a href="zones.html#zone-' + p.zone + '" class="tag tag-zone" style="background:' +
    ZONE_COLORS[p.zone] + '">' + p.zone + ': ' + ZONE_NAMES[p.zone] + '</a>';
  var ownerHref = 'owners.html#' + ownerSlug(p.owner);

  var html = '<table>' +
    '<tr><td>Label</td><td><strong style="font-size:16px">' + p.label + '</strong> ' + zoneTag + '</td></tr>' +
    (p.entry ? '<tr><td>Access</td><td><span class="entry-tag">◆ Entry point</span>' +
      (p.parking ? '<span class="parking-tag">P Parking</span>' : '') +
      (p.connects ? '<div class="connects-tag">Connects to ' + esc(p.connects) + '</div>' : '') +
      '</td></tr>' : '') +
    '<tr class="full-only"><td>Owner</td><td><a href="' + esc(ownerHref) + '" onmouseover="hoverOwner(' + jsArg(p.owner) + ')" onmouseout="unhover()">' + esc(p.owner) + '</a> ' + pubTag + '</td></tr>' +
    '<tr class="full-only"><td>Town</td><td>' + esc(p.town) + '</td></tr>' +
    '</table>';

  var connections = intTrailMap[p.label] || [];
  if (connections.length > 0) {
    var byTrail = {};
    connections.forEach(function(c) {
      var trail = c[0], neighbor = c[1], dist = c[2];
      if (!byTrail[trail]) byTrail[trail] = [];
      byTrail[trail].push({neighbor: neighbor, dist: dist});
    });
    html += '<div class="int-list full-only"><strong style="font-size:12px;color:#555">Trails</strong>';
    Object.keys(byTrail).forEach(function(trail) {
      html += '<div style="margin-top:6px;font-weight:600;font-size:12px"><a href="#" onmouseover="hoverTrail(' + jsArg(trail) + ')" onmouseout="unhover()" onclick="selectTrailByName(' + jsArg(trail) + ');return false" style="color:#2c3e50">' + esc(trail) + '</a></div>';
      byTrail[trail].forEach(function(seg) {
        var distFt = Math.round(seg.dist * 3.28084);
        if (seg.neighbor) {
          var nZone = seg.neighbor.replace(/[0-9]/g, "");
          var nBg = ZONE_COLORS[nZone] || "#888";
          html += '<div class="int-row">' +
            '<span class="seg-bar" style="padding:0">→</span> ' +
            '<a class="int-link" style="background:' + nBg + '" onmouseover="hoverInt(\'' + seg.neighbor + '\')" onmouseout="unhover()" onclick="selectIntFromTrail(\'' + seg.neighbor + '\')">' + seg.neighbor + '</a>' +
            '<span class="int-dist">' + distFt.toLocaleString() + ' ft</span>' +
            '</div>';
        } else {
          html += '<div class="int-row">' +
            '<span class="seg-bar" style="padding:0">→</span> ' +
            '<span class="int-terminus">●</span>' +
            '<span class="int-dist">' + distFt.toLocaleString() + ' ft</span>' +
            '</div>';
        }
      });
    });
    html += '</div>';
  }

  html += backToRouteBtn() + '<button class="route-btn" onclick="startRoute(\'' + p.label + '\')">Route from here</button>';
  if (userLatLng) {
    html += ' <button class="route-btn" style="background:#1e88e5" onclick="routeFromMe(\'' + p.label + '\')">Route here from my location</button>';
  }

  document.getElementById("infoContent").innerHTML = html;
  currentIntFeature = feature;
}

function startRoute(label) {
  routeFrom = label;
  routeMode = true;
  clearRouteDisplay();
  document.getElementById("infoContent").innerHTML =
    '<div class="route-msg">Routing from <strong>' + label + '</strong><br>' +
    'Click a destination intersection.<br><br>' +
    '<button class="route-btn" style="background:#888" onclick="cancelRoute()">Cancel</button></div>';
}

function cancelRoute() {
  clearSelection();   // also drops the starting intersection's highlight
  document.getElementById("infoContent").innerHTML = defaultInfo;
}

function removeRouteLayers() {
  if (routeLine) { map.removeLayer(routeLine); routeLine = null; }
  routeMarkers.forEach(function(m) { map.removeLayer(m); });
  routeMarkers = [];
}

function clearRouteDisplay() {
  removeRouteLayers();
  plan = null;
}

function completeRoute(destLabel) {
  routeMode = false;
  var startLabel = routeFrom;
  routeFrom = null;
  if (startLabel === destLabel) { cancelRoute(); return; }

  var result = dijkstra(startLabel, destLabel);
  if (!result) {
    clearSelection();   // so a first GPS fix doesn't reopen the start intersection over this
    document.getElementById("infoContent").innerHTML =
      '<div class="route-msg">No route found from <strong>' + startLabel + '</strong> to <strong>' + destLabel + '</strong>.<br><br>' +
      '<button class="route-btn" style="background:#888" onclick="cancelRoute()">Close</button></div>';
    return;
  }
  renderRoute(startLabel, destLabel, result, null);
}

// Route edges indexed by "from|to|trail" -> {ti, a, b}: trail feature and the positions
// along it of the two intersections. Built on first use.
var edgeIndex = null;
function routeEdge(u, v, trail) {
  if (!edgeIndex) {
    edgeIndex = {};
    Object.keys(trailIntMap).forEach(function(ti) {
      var p = trailData.features[ti].properties;
      var name = p.pdf_name || p.name || "Unnamed";
      var ints = trailIntMap[ti].ints;
      for (var i = 0; i < ints.length - 1; i++) {
        var x = ints[i], y = ints[i + 1];
        edgeIndex[x[0] + "|" + y[0] + "|" + name] = {ti: +ti, a: x[1], b: y[1]};
        edgeIndex[y[0] + "|" + x[0] + "|" + name] = {ti: +ti, a: y[1], b: x[1]};
      }
    });
  }
  return edgeIndex[u + "|" + v + "|" + trail] || null;
}

function pointAlong(ti, s) {
  var c = flatCoords(trailData.features[ti].geometry), cum = trailCum[ti];
  for (var j = 0; j < c.length - 1; j++) {
    if (s <= cum[j + 1] || j === c.length - 2) {
      var t = cum[j + 1] > cum[j] ? Math.max(0, Math.min(1, (s - cum[j]) / (cum[j + 1] - cum[j]))) : 0;
      return L.latLng(c[j][1] + t * (c[j + 1][1] - c[j][1]), c[j][0] + t * (c[j + 1][0] - c[j][0]));
    }
  }
  return L.latLng(c[0][1], c[0][0]);
}

// The stretch of trail ti between positions a and b, in walking order
function sliceTrail(ti, a, b) {
  var c = flatCoords(trailData.features[ti].geometry), cum = trailCum[ti];
  var lo = Math.min(a, b), hi = Math.max(a, b);
  var pts = [pointAlong(ti, lo)];
  for (var j = 0; j < c.length; j++) {
    if (cum[j] > lo && cum[j] < hi) pts.push(L.latLng(c[j][1], c[j][0]));
  }
  pts.push(pointAlong(ti, hi));
  return a <= b ? pts : pts.reverse();
}

// Shorten a line by the given pixel lengths at each end, so it stops at the intersection rings
function trimLine(latlngs, startPx, endPx) {
  var pts = latlngs.map(function(ll) { return map.latLngToLayerPoint(ll); });
  var total = 0;
  for (var i = 1; i < pts.length; i++) total += pts[i].distanceTo(pts[i - 1]);
  if (total <= startPx + endPx + 4) return null;
  function cut(points, px) {
    var out = [points[0]], left = px;
    for (var i = 1; i < points.length; i++) {
      var d = points[i].distanceTo(points[i - 1]);
      if (left > 0 && d <= left) { left -= d; out = [points[i]]; continue; }
      if (left > 0) {
        var t = left / d;
        out = [points[i - 1].add(points[i].subtract(points[i - 1]).multiplyBy(t))];
        left = 0;
      }
      out.push(points[i]);
    }
    return out;
  }
  pts = cut(pts, startPx);
  pts = cut(pts.reverse(), endPx).reverse();
  return pts.map(function(p) { return map.layerPointToLatLng(p); });
}

var ROUTE_TRIM_PX = 20;   // ring radius 13 + ring stroke + the casing's round cap
var OFF_ROUTE_M = 40;     // farther than this from a live route triggers a reroute

// Approximate meters along a polyline, matching the distances used elsewhere
function lineCum(pts) {
  var cum = [0];
  for (var i = 1; i < pts.length; i++) {
    var dx = (pts[i].lng - pts[i - 1].lng) * 82000, dy = (pts[i].lat - pts[i - 1].lat) * 111000;
    cum.push(cum[i - 1] + Math.sqrt(dx * dx + dy * dy));
  }
  return cum;
}

function segLen(seg) { return seg.cum[seg.cum.length - 1]; }

function segPointAt(seg, r) {
  for (var j = 0; j < seg.pts.length - 1; j++) {
    if (r <= seg.cum[j + 1] || j === seg.pts.length - 2) {
      var span = seg.cum[j + 1] - seg.cum[j];
      var t = span > 0 ? Math.max(0, Math.min(1, (r - seg.cum[j]) / span)) : 0;
      var a = seg.pts[j], b = seg.pts[j + 1];
      return L.latLng(a.lat + t * (b.lat - a.lat), a.lng + t * (b.lng - a.lng));
    }
  }
  return seg.pts[0];
}

// The part of a route piece between route positions a and b, or null if empty
function segPiece(seg, a, b) {
  a = Math.max(a - seg.s0, 0);
  b = Math.min(b - seg.s0, segLen(seg));
  if (b - a <= 0.01) return null;
  var pts = [segPointAt(seg, a)];
  for (var i = 0; i < seg.pts.length; i++) {
    if (seg.cum[i] > a && seg.cum[i] < b) pts.push(seg.pts[i]);
  }
  pts.push(segPointAt(seg, b));
  return pts;
}

// passed, here (within AT_INT_M of it), or ahead
function stepState(i) {
  if (plan.progress === null) return "ahead";
  if (plan.arrived) return i === plan.steps.length - 1 ? "here" : "passed";
  var d = plan.steps[i].at - plan.progress;
  return d < -AT_INT_M ? "passed" : d <= AT_INT_M ? "here" : "ahead";
}

// Draw the route: walked parts grey, the rest navy, each piece stopping short of the rings
function drawRoute() {
  removeRouteLayers();
  var layers = [];
  function add(pts, trimStart, trimEnd, past) {
    var p = pts && trimLine(pts, trimStart ? ROUTE_TRIM_PX : 0, trimEnd ? ROUTE_TRIM_PX : 0);
    if (p) {
      layers.push(L.polyline(p, {color: "#fff", weight: 10, opacity: past ? 0.7 : 0.9, lineCap: "round", lineJoin: "round", interactive: false}));
      layers.push(L.polyline(p, {color: past ? "#9e9e9e" : "#0d47a1", weight: 6, opacity: 1, dashArray: "10,6", lineCap: "round", lineJoin: "round", interactive: false}));
    }
  }
  plan.hist.segs.forEach(function(s) { add(s.pts, s.trimStart, s.trimEnd, true); });
  var prog = plan.progress === null ? 0 : plan.progress;
  plan.segs.forEach(function(seg) {
    var end = seg.s0 + segLen(seg);
    if (prog <= seg.s0) {
      add(seg.pts, seg.trimStart, seg.trimEnd, false);
    } else if (prog >= end) {
      add(seg.pts, seg.trimStart, seg.trimEnd, true);
    } else {
      add(segPiece(seg, seg.s0, prog), seg.trimStart, false, true);
      add(segPiece(seg, prog, end), false, seg.trimEnd, false);
    }
  });
  routeLine = L.featureGroup(layers).addTo(map);
  routeLine.bringToFront();

  function ring(label, past) {
    routeMarkers.push(L.circleMarker(intMarkers[label].getLatLng(), {
      radius: 13, color: past ? "#9e9e9e" : "#0d47a1", weight: 3, fillOpacity: 0, opacity: 0.9, interactive: false
    }).addTo(map));
  }
  plan.hist.steps.forEach(function(s) { ring(s.label, true); });
  plan.steps.forEach(function(s, i) { ring(s.label, stepState(i) === "passed"); });
}

// Trimming is in pixels, so it has to be redone at each zoom level
map.on("zoomend", function() { if (plan) drawRoute(); });

function stepRowHtml(step, state) {
  var html = '<div class="route-step' + (state === "passed" ? ' passed' : '') + '">' +
    (state === "here" ? '<span class="you-badge">You</span>' : '') + intPill(step.label, state);
  if (step.nextTrail) {
    html += '<span class="route-arrow">→</span>' +
      '<span class="route-trail-name">' + esc(step.nextTrail) + '</span>' +
      '<span class="int-dist">' + formatDist(step.nextFt / 3.28084) + '</span>';
  }
  return html + '</div>';
}

function routePanelHtml() {
  var states = plan.steps.map(function(s, i) { return stepState(i); });
  // You are either at a step ("here") or on the way to the first step still ahead
  var youBefore = -1;
  if (plan.live && !plan.arrived && states.indexOf("here") < 0) youBefore = states.indexOf("ahead");
  var toGo = plan.live ? Math.max(plan.total - plan.progress, 0) : plan.graphDist;
  var toGoStr = formatDist(toGo);
  var dest = plan.steps[plan.steps.length - 1].label;
  var live = plan.live && !plan.arrived ? ' <span class="live-tag">LIVE</span>' : '';

  // Small view: one row of pills
  var row = '';
  var link = function(past) { return '<span class="rr-link' + (past ? ' passed' : '') + '"></span>'; };
  plan.hist.steps.forEach(function(s) { row += intPill(s.label, "passed") + link(true); });
  plan.steps.forEach(function(s, i) {
    if (i === youBefore) {
      if (i > 0) row += link(true);
      row += '<span class="seg-you rr-you"></span>' + link(false);
    } else if (i > 0) {
      row += link(states[i] !== "ahead");
    }
    row += intPill(s.label, states[i]);
  });
  var small = '<div class="compact-only">' +
    '<div class="route-compact-head">' + (plan.arrived
      ? "You've arrived at " + intPill(dest)
      : '<span class="route-arrow">→</span>' + intPill(dest) + ' <strong>' + toGoStr + '</strong>' + (plan.live ? ' to go' : '') + live) +
    '</div><div class="route-row">' + row + '</div></div>';

  // Large view: the step list
  var html = '<div style="margin-bottom:6px"><strong style="font-size:14px">' + (plan.arrived
      ? "You've arrived at " + intPill(dest)
      : 'Route: ' + (plan.live ? 'Your location' : plan.start) + ' → ' + dest) + '</strong>' + live + '</div>';
  if (!plan.arrived) {
    html += '<div style="font-size:13px;margin-bottom:8px"><strong>' + toGoStr + '</strong>' +
      (plan.live ? ' to go' : '') + '</div>';
  }
  html += '<div class="int-list">';
  plan.hist.steps.forEach(function(s) { html += stepRowHtml(s, "passed"); });
  plan.steps.forEach(function(s, i) {
    if (i === youBefore) {
      var trail = i === 0 ? plan.legTrail : s.trail;
      html += '<div class="route-step"><span class="you-badge">You</span>' +
        '<span class="route-arrow">→</span>' +
        '<span class="route-trail-name">' + esc(trail) + '</span>' +
        '<span class="int-dist">' + formatDist(s.at - plan.progress) + '</span></div>';
    }
    html += stepRowHtml(s, states[i]);
  });
  html += '</div>';
  html += '<div style="margin-top:10px">' +
    (plan.live ? '' : '<button class="route-btn" onclick="startRoute(\'' + plan.start + '\')">New route from ' + plan.start + '</button> ') +
    '<button class="route-btn" onclick="startRoute(\'' + dest + '\')">New route from ' + dest + '</button> ' +
    '<button class="route-btn" style="background:#888" onclick="cancelRoute()">Clear</button></div>';

  return '<div id="routeInfo">' + small + '<div class="full-only">' + html + '</div></div>';
}

function showRoutePanel() {
  document.getElementById("infoContent").innerHTML = routePanelHtml();
  // Keep where you are in view in the pill row
  var rowEl = document.querySelector("#routeInfo .route-row");
  var you = rowEl && rowEl.querySelector(".rr-you, .int-link.here");
  if (you) rowEl.scrollLeft = Math.max(0, you.offsetLeft - rowEl.clientWidth / 3);
}

// userLeg (optional): {dist, trail, ti, along, cum} for the walk from the user's position to
// the first intersection (ti/along: where the user snaps onto that trail, if on one).
// A route with a userLeg is live: progress along it is tracked as the user moves.
// noFit keeps the view. hist: {steps, segs} already walked before a reroute; a reroute
// leaves the panel and any selection alone, and the caller redraws.
function renderRoute(startLabel, destLabel, result, userLeg, noFit, hist) {
  if (!hist) clearSelection();
  clearRouteDisplay();

  var path = result.path;
  var segs = [];
  if (userLeg) {
    var legPts = [userLatLng];
    if (userLeg.ti !== undefined) {
      legPts = legPts.concat(sliceTrail(userLeg.ti, userLeg.along, userLeg.cum));
    }
    legPts.push(intMarkers[path[0].label].getLatLng());
    segs.push({pts: legPts, trimStart: false, trimEnd: true});
  }
  for (var k = 0; k < path.length - 1; k++) {
    var u = path[k].label, v = path[k + 1].label;
    var e = routeEdge(u, v, path[k + 1].trail);
    var pts = e ? sliceTrail(e.ti, e.a, e.b) : [];
    pts.unshift(intMarkers[u].getLatLng());
    pts.push(intMarkers[v].getLatLng());
    segs.push({pts: pts, trimStart: true, trimEnd: true});
  }
  // Lay the pieces end to end so every point has a position along the route
  var s = 0;
  segs.forEach(function(seg) { seg.cum = lineCum(seg.pts); seg.s0 = s; s += segLen(seg); });

  var steps = path.map(function(step, i) {
    var k = userLeg ? i : i - 1;
    var next = path[i + 1], nextFt = 0;
    if (next) {
      (intTrailMap[step.label] || []).forEach(function(c) {
        if (c[0] === next.trail && c[1] === next.label) nextFt = c[2] * 3.28084;
      });
    }
    return {label: step.label, trail: step.trail, nextTrail: next ? next.trail : null, nextFt: nextFt,
            at: k < 0 ? 0 : segs[k].s0 + segLen(segs[k])};
  });

  plan = {start: startLabel, dest: destLabel, live: !!userLeg, segs: segs, steps: steps, total: s,
          graphDist: result.totalDist, progress: userLeg ? 0 : null, arrived: false,
          legTrail: userLeg ? (userLeg.trail || 'off trail') : null,
          hist: hist || {steps: [], segs: []}};
  if (hist) return;
  drawRoute();

  if (!noFit) {
    setFollowing(false);   // show the whole route; tap locate to follow again
    var allPts = [].concat.apply([], segs.map(function(seg) { return seg.pts; }));
    map.fitBounds(L.latLngBounds(allPts).pad(0.1));
  }
  showRoutePanel();
}

// A rough fix (say, a phone that just woke up) isn't good enough to call you off the route
var REROUTE_MAX_ACC_M = 50;

function liveRouting() { return plan && plan.live && !plan.arrived; }

// Where on the live route you are. Prefers spots at or past your last position, so a
// route that doubles back doesn't jump ahead. Returns false when you're off the route.
function trackProgress() {
  var px = userLatLng.lng * 82000, py = userLatLng.lat * 111000, cands = [];
  plan.segs.forEach(function(seg) {
    for (var i = 0; i < seg.pts.length - 1; i++) {
      var ax = seg.pts[i].lng * 82000, ay = seg.pts[i].lat * 111000;
      var vx = seg.pts[i + 1].lng * 82000 - ax, vy = seg.pts[i + 1].lat * 111000 - ay;
      var len2 = vx * vx + vy * vy;
      var t = len2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * vx + (py - ay) * vy) / len2)) : 0;
      var dx = px - (ax + t * vx), dy = py - (ay + t * vy);
      cands.push({d: Math.sqrt(dx * dx + dy * dy), s: seg.s0 + seg.cum[i] + t * (seg.cum[i + 1] - seg.cum[i])});
    }
  });
  var tol = Math.max(OFF_ROUTE_M, Math.min(userAccuracy, 60));
  var near = cands.filter(function(c) { return c.d <= tol; });
  if (near.length === 0) return false;
  var ahead = near.filter(function(c) { return c.s >= plan.progress - 30; });
  if (ahead.length === 0) ahead = near;
  var minD = Math.min.apply(null, ahead.map(function(c) { return c.d; }));
  var best = null;
  ahead.forEach(function(c) { if (c.d <= minD + 5 && (!best || c.s < best.s)) best = c; });
  plan.progress = best.s;
  return true;
}

// Called on each new fix while a live route is up
function updateLiveRoute() {
  if (userLatLng.distanceTo(intMarkers[plan.dest].getLatLng()) <= AT_INT_M) {
    plan.progress = plan.total;
    plan.arrived = true;
  } else if (trackProgress()) {
    if (plan.total - plan.progress <= AT_INT_M) plan.arrived = true;
  } else if (userAccuracy <= REROUTE_MAX_ACC_M) {
    rerouteFromHere();   // with no way from here, the old route stays up
  }
  drawRoute();
  if (document.getElementById("routeInfo")) showRoutePanel();
  else refreshLocateInfo();
}

// Off the route: plan again from here, keeping what was already walked as grey history
function rerouteFromHere() {
  var best = bestRouteFromMe(plan.dest);
  if (!best) return;
  var hist = {steps: plan.hist.steps.slice(), segs: plan.hist.segs.slice()};
  plan.steps.forEach(function(st) { if (st.at <= plan.progress + AT_INT_M) hist.steps.push(st); });
  plan.segs.forEach(function(seg) {
    var pts = segPiece(seg, seg.s0, plan.progress);
    if (pts) hist.segs.push({pts: pts, trimStart: seg.trimStart,
                             trimEnd: plan.progress >= seg.s0 + segLen(seg) && seg.trimEnd});
  });
  renderRoute(best.anchor.label, plan.dest, best.result, best.anchor, true, hist);
}

var hoverMarker = null;
var hoverTrailLayers = [];
var hoverOwnerMarkers = [];

function hoverOwner(ownerName) {
  unhover();
  Object.keys(intFeatures).forEach(function(label) {
    var f = intFeatures[label];
    var m = intMarkers[label];
    if (f.properties.owner === ownerName && m && m !== selectedMarker) {
      m.setStyle({radius: 11, weight: 4, color: "#111", fillColor: ZONE_COLORS[m._zone], fillOpacity: 1});
      m.bringToFront();
      hoverOwnerMarkers.push(label);
    }
  });
}

function hoverInt(label) {
  unhover();
  if (intMarkers[label]) {
    intMarkers[label].setStyle({radius: 11, weight: 3, color: "#f1c40f", fillColor: "#f1c40f", fillOpacity: 1});
    hoverMarker = label;
  }
}

function hoverTrail(name) {
  unhover();
  trailLayer.eachLayer(function(l) {
    var ln = l.feature.properties.pdf_name || l.feature.properties.name || "";
    if (ln === name) {
      l.setStyle({color: "#00b8d4", weight: 6, opacity: 1});
      hoverTrailLayers.push(l);
    }
  });
}

function unhover() {
  if (hoverMarker && intMarkers[hoverMarker]) {
    var z = intMarkers[hoverMarker]._zone;
    if (!selectedMarker || selectedMarker !== intMarkers[hoverMarker]) {
      intMarkers[hoverMarker].setStyle({radius: 7, weight: 2, color: "#fff", fillColor: ZONE_COLORS[z], fillOpacity: 0.85});
    }
    hoverMarker = null;
  }
  hoverOwnerMarkers.forEach(function(label) {
    var m = intMarkers[label];
    if (m && m !== selectedMarker) {
      var z = m._zone;
      m.setStyle({radius: 7, weight: 2, color: "#fff", fillColor: ZONE_COLORS[z], fillOpacity: 0.85});
    }
  });
  hoverOwnerMarkers = [];
  hoverTrailLayers.forEach(function(l) {
    if (highlightedSegments.indexOf(l) === -1) {
      l.setStyle({color: "#2c3e50", weight: 3, opacity: 0.6});
    }
  });
  hoverTrailLayers = [];
}

function selectTrailByName(name) {
  var layer = null;
  trailLayer.eachLayer(function(l) {
    var ln = l.feature.properties.pdf_name || l.feature.properties.name || "";
    if (ln === name && !layer) layer = l;
  });
  if (layer) showTrailInfo(layer.feature, layer);
}

function selectIntFromTrail(label) {
  if (intMarkers[label] && intFeatures[label]) {
    showIntInfo(intFeatures[label], intMarkers[label]);
    map.panTo(intMarkers[label].getLatLng());
  }
}

function showTrailInfo(feature, layer) {
  clearSelection(true);

  var p = feature.properties;
  var name = p.pdf_name || p.name || "";

  highlightedSegments = [];
  var segIndices = [];
  trailLayer.eachLayer(function(l) {
    var ln = l.feature.properties.pdf_name || l.feature.properties.name || "";
    if (ln === name && name !== "") {
      l.setStyle({color: "#00b8d4", weight: 6, opacity: 1});
      highlightedSegments.push(l);
      segIndices.push(l.feature.properties._idx);
    }
  });
  if (highlightedSegments.length === 0) {
    layer.setStyle({color: "#00b8d4", weight: 6, opacity: 1});
    highlightedSegments.push(layer);
    segIndices.push(feature.properties._idx);
  }

  var displayName = name || "Unnamed trail";

  var totalLength = 0;
  var allInts = [];
  var seen = {};
  segIndices.forEach(function(si) {
    var info = trailIntMap[si];
    if (!info) return;
    totalLength += info.length;
    info.ints.forEach(function(pair) {
      if (!seen[pair[0]]) {
        seen[pair[0]] = true;
        allInts.push({label: pair[0], dist: pair[1]});
      }
    });
  });

  var html = '<table>' +
    '<tr><td>Trail</td><td><strong style="font-size:16px">' + esc(displayName) + '</strong></td></tr>';
  var totalFt = Math.round(totalLength * 3.28084);
  var totalMi = (totalLength * 0.000621371);
  var lengthStr = totalMi >= 0.1 ? totalMi.toFixed(1) + ' mi (' + totalFt.toLocaleString() + ' ft)' : totalFt.toLocaleString() + ' ft';
  if (totalLength > 0) html += '<tr><td>Length</td><td>' + lengthStr + '</td></tr>';
  if (p.surface) html += '<tr class="full-only"><td>Surface</td><td>' + esc(p.surface) + '</td></tr>';
  if (p.highway) html += '<tr class="full-only"><td>Type</td><td>' + esc(p.highway) + '</td></tr>';
  html += '</table>';

  var TERMINUS_MIN = 10;
  html += '<div class="int-list full-only"><strong style="font-size:12px;color:#555">Intersections</strong>';

  if (allInts.length > 0) {
    var startGap = Math.round(allInts[0].dist * 3.28084);
    if (startGap > TERMINUS_MIN) {
      html += '<div class="int-row"><span class="int-terminus">●</span></div>';
      html += '<div class="seg-bar">↕ ' + startGap.toLocaleString() + ' ft</div>';
    }
    for (var i = 0; i < allInts.length; i++) {
      var label = allInts[i].label;
      var zone = label.replace(/[0-9]/g, "");
      var bg = ZONE_COLORS[zone] || "#888";
      html += '<div class="int-row">' +
        '<a class="int-link" style="background:' + bg + '" onmouseover="hoverInt(\'' + label + '\')" onmouseout="unhover()" onclick="selectIntFromTrail(\'' + label + '\')">' + label + '</a>' +
        '</div>';
      if (i < allInts.length - 1) {
        var segFt = Math.round((allInts[i+1].dist - allInts[i].dist) * 3.28084);
        if (segFt > 0) html += '<div class="seg-bar">↕ ' + segFt.toLocaleString() + ' ft</div>';
      }
    }
    var endGap = Math.round((totalLength - allInts[allInts.length - 1].dist) * 3.28084);
    if (endGap > TERMINUS_MIN) {
      html += '<div class="seg-bar">↕ ' + endGap.toLocaleString() + ' ft</div>';
      html += '<div class="int-row"><span class="int-terminus">●</span></div>';
    }
  } else if (totalLength > 0) {
    html += '<div class="int-row"><span class="int-terminus">●</span></div>';
    html += '<div class="seg-bar">↕ ' + totalFt.toLocaleString() + ' ft</div>';
    html += '<div class="int-row"><span class="int-terminus">●</span></div>';
  }

  html += '</div>';
  if (plan) html += '<div style="margin-top:6px">' + backToRouteBtn() + '</div>';

  document.getElementById("infoContent").innerHTML = html;
}

function clearSelection(keepRoute) {
  if (selectedRing) {
    map.removeLayer(selectedRing);
    selectedRing = null;
  }
  if (selectedMarker) {
    var z = selectedMarker._zone;
    selectedMarker.setStyle({fillColor: ZONE_COLORS[z], radius: 7, weight: 2, color: "#fff", fillOpacity: 0.85});
    selectedMarker = null;
  }
  highlightedSegments.forEach(function(l) {
    l.setStyle({color: "#2c3e50", weight: 3, opacity: 0.6});
  });
  highlightedSegments = [];
  if (!keepRoute) clearRouteDisplay();
  routeMode = false;
  routeFrom = null;
  currentIntFeature = null;
}

// Details opened while a route is up keep the route going and offer a way back to it
function backToRouteBtn() {
  return plan ? '<button class="route-btn" style="background:#0d47a1" onclick="backToRoute()">Back to route</button> ' : '';
}

function backToRoute() {
  clearSelection(true);
  showRoutePanel();
}

// Small and large panel views. Content marks parts with full-only / compact-only.
var PANEL_KEY = "vtnPanelCompact";
var ICON_SHRINK = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
  '<path d="M20 4l-6 6M14 5v5h5M4 20l6-6M10 19v-5H5"/></svg>';
var ICON_GROW = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
  '<path d="M14 10l6-6M15 4h5v5M10 14l-6 6M9 20H4v-5"/></svg>';

function setPanelCompact(on) {
  document.getElementById("infoPanel").classList.toggle("compact", on);
  var btn = document.getElementById("panelSize");
  btn.innerHTML = on ? ICON_GROW : ICON_SHRINK;
  btn.title = on ? "Larger panel" : "Smaller panel";
  try { localStorage.setItem(PANEL_KEY, on ? "1" : "0"); } catch (e) {}
  if (on && plan && document.getElementById("routeInfo")) showRoutePanel();   // re-center the pill row
}

function togglePanelSize() {
  setPanelCompact(!document.getElementById("infoPanel").classList.contains("compact"));
}

var panelStartsCompact = false;
try { panelStartsCompact = localStorage.getItem(PANEL_KEY) === "1"; } catch (e) {}
setPanelCompact(panelStartsCompact);

var defaultInfo = '<p style="color:#888">Click a trail or intersection marker for details.</p>' +
  '<p class="full-only" style="margin-top:8px;color:#888;font-size:11px">__N_INTS__ numbered intersections across 6 zones.<br>' +
  '__N_TRAILS__ trail segments, __N_NAMES__ named trails.</p>';

// Only the Clear button ends a route; a tap on the map just brings the route panel back
map.on("click", function() {
  if (plan) {
    if (!document.getElementById("routeInfo")) backToRoute();
  } else {
    clearSelection();
    document.getElementById("infoContent").innerHTML = defaultInfo;
  }
});

var btnContainer = document.getElementById("zoneButtons");
["A","B","C","D","E","F"].forEach(function(z) {
  var btn = document.createElement("span");
  btn.className = "zone-btn";
  btn.style.background = ZONE_COLORS[z];
  btn.textContent = z;
  btn.title = z + ": " + ZONE_NAMES[z];
  btn.onclick = function() { toggleZone(z, btn); };
  btnContainer.appendChild(btn);
});
var allBtn = document.createElement("span");
allBtn.className = "zone-btn-all";
allBtn.textContent = "All";
allBtn.onclick = function() {
  Object.keys(zoneVisible).forEach(function(z) { zoneVisible[z] = true; });
  updateZoneVisibility();
  document.querySelectorAll(".zone-btn").forEach(function(b) { b.classList.remove("off"); });
};
btnContainer.appendChild(allBtn);

function toggleZone(z, btn) {
  zoneVisible[z] = !zoneVisible[z];
  btn.classList.toggle("off");
  updateZoneVisibility();
}

function updateZoneVisibility() {
  Object.keys(intMarkers).forEach(function(label) {
    var z = intMarkers[label]._zone;
    var layers = [intMarkers[label], labelMarkers[label]];
    if (entryMarkers[label]) layers.push(entryMarkers[label]);
    layers.forEach(function(l) {
      if (zoneVisible[z] && !map.hasLayer(l)) l.addTo(map);
      if (!zoneVisible[z] && map.hasLayer(l)) map.removeLayer(l);
    });
  });
}

// Deep-link support: map.html?int=A1 zooms to that intersection
var params = new URLSearchParams(window.location.search);
var targetInt = params.get("int");
if (targetInt && intMarkers[targetInt]) {
  var m = intMarkers[targetInt];
  var f = intFeatures[targetInt];
  map.setView(m.getLatLng(), 17);
  setTimeout(function() { showIntInfo(f, m); }, 300);
} else {
  map.fitBounds([[42.156, -71.518], [42.201, -71.483]]);
}

// Geolocation
var userAccuracy = 0, userDot = null, userAccCircle = null, watchId = null;
var locateRequested = false, locateBtn = null;
var NETWORK_BOUNDS = L.latLngBounds([[42.156, -71.518], [42.201, -71.483]]);

function approxDist(lon1, lat1, lon2, lat2) {
  var dx = (lon1 - lon2) * 82000, dy = (lat1 - lat2) * 111000;
  return Math.sqrt(dx * dx + dy * dy);
}

function flatCoords(geom) {
  if (geom.type === "LineString") return geom.coordinates;
  if (geom.type === "MultiLineString") return [].concat.apply([], geom.coordinates);
  return [];
}

// Cumulative distances match build_trail_int_map so positions line up with trailIntMap
var trailCum = trailData.features.map(function(f) {
  var c = flatCoords(f.geometry), cum = [0];
  for (var i = 1; i < c.length; i++) {
    cum.push(cum[i - 1] + approxDist(c[i - 1][0], c[i - 1][1], c[i][0], c[i][1]));
  }
  return cum;
});

function formatDist(m) {
  var ft = m * 3.28084;
  return ft < 1000 ? (Math.round(ft / 10) * 10).toLocaleString() + " ft"
                   : (m / 1609.344).toFixed(1) + " mi";
}

// A short message in the panel; like other panels, it leaves any route in place
function showPanelMsg(text) {
  clearSelection(true);
  document.getElementById("infoContent").innerHTML = '<div class="route-msg" style="margin-top:0">' + text +
    (plan ? '<br><br>' + backToRouteBtn() : '') + '</div>';
}

function nearestInt(ll) {
  var best = null, bestD = Infinity;
  Object.keys(intMarkers).forEach(function(label) {
    var d = ll.distanceTo(intMarkers[label].getLatLng());
    if (d < bestD) { bestD = d; best = label; }
  });
  return {label: best, dist: bestD};
}

var SNAP_M = 60;     // farther than this from every trail counts as off trail
var AT_INT_M = 20;   // this close to an intersection counts as being at it

// Nearest point on any trail: distance to it, which trail, and how far along that trail
function snapToTrail(ll) {
  var px = ll.lng * 82000, py = ll.lat * 111000, best = {d: Infinity};
  trailData.features.forEach(function(f, ti) {
    var c = flatCoords(f.geometry), cum = trailCum[ti];
    for (var i = 0; i < c.length - 1; i++) {
      var ax = c[i][0] * 82000, ay = c[i][1] * 111000;
      var vx = c[i + 1][0] * 82000 - ax, vy = c[i + 1][1] * 111000 - ay;
      var len2 = vx * vx + vy * vy;
      var t = len2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * vx + (py - ay) * vy) / len2)) : 0;
      var dx = px - (ax + t * vx), dy = py - (ay + t * vy);
      var d = Math.sqrt(dx * dx + dy * dy);
      if (d < best.d) {
        // tan: compass bearing of the trail here, pointing toward increasing "along"
        best = {d: d, ti: ti, along: cum[i] + t * (cum[i + 1] - cum[i]),
                tan: (Math.atan2(vx, vy) * 180 / Math.PI + 360) % 360};
      }
    }
  });
  if (best.d < Infinity) {
    var props = trailData.features[best.ti].properties;
    best.name = props.pdf_name || props.name || "Unnamed";
  }
  return best;
}

// Intersections on either side of a snapped point along its trail (either may be null)
function segmentEnds(snap) {
  var before = null, after = null;
  trailIntMap[snap.ti].ints.forEach(function(e) {
    if (e[1] <= snap.along) before = e;
    if (e[1] > snap.along && !after) after = e;
  });
  return {before: before, after: after};
}

// Places the user can join the graph: intersections on either side along the nearest trail,
// or the closest few by straight line when not near any trail
function userAnchors(ll) {
  var best = snapToTrail(ll);
  var anchors = [];
  if (best.d < SNAP_M) {
    var ends = segmentEnds(best);
    [ends.before, ends.after].forEach(function(e) {
      if (e) anchors.push({label: e[0], dist: best.d + Math.abs(best.along - e[1]), trail: best.name,
                           ti: best.ti, along: best.along, cum: e[1]});
    });
  }
  if (anchors.length === 0) {
    anchors = Object.keys(intMarkers).map(function(label) {
      return {label: label, dist: ll.distanceTo(intMarkers[label].getLatLng()), trail: null};
    }).sort(function(a, b) { return a.dist - b.dist; }).slice(0, 3);
  }
  return anchors;
}

// anchors (optional): userAnchors(userLatLng), when asking about several destinations
function bestRouteFromMe(destLabel, anchors) {
  var best = null;
  (anchors || userAnchors(userLatLng)).forEach(function(a) {
    var r = dijkstra(a.label, destLabel);
    if (r && (!best || a.dist + r.totalDist < best.total)) {
      best = {anchor: a, result: r, total: a.dist + r.totalDist};
    }
  });
  return best;
}

function routeFromMe(destLabel) {
  var best = null;
  if (userLatLng.distanceTo(intMarkers[destLabel].getLatLng()) <= AT_INT_M) {
    showPanelMsg('You are already at ' + intPill(destLabel));
  } else if ((best = bestRouteFromMe(destLabel))) {
    renderRoute(best.anchor.label, destLabel, best.result, best.anchor);
  } else {
    showPanelMsg('No route found from your location to <strong>' + destLabel + '</strong>.');
  }
}

// state (optional): "passed" greys the pill, "here" rings it
function intPill(label, state) {
  var bg = ZONE_COLORS[label.replace(/[0-9]/g, "")] || "#888";
  var cls = state === "passed" || state === "here" ? ' ' + state : '';
  return '<a class="int-link' + cls + '" style="background:' + bg + '" onmouseover="hoverInt(\'' + label + '\')" onmouseout="unhover()" onclick="selectIntFromTrail(\'' + label + '\')">' + label + '</a>';
}

// Where the user is: at an intersection, on a segment between two ends, or off trail
function userPlace(ll) {
  var n = nearestInt(ll);
  if (n.dist <= AT_INT_M) return {type: "at", label: n.label};
  var snap = snapToTrail(ll);
  if (snap.d >= SNAP_M) return {type: "off", label: n.label, dist: n.dist};

  var ends = segmentEnds(snap);
  var c = flatCoords(trailData.features[snap.ti].geometry);
  function end(e, isStart) {
    if (e) return {label: e[0], dist: Math.abs(snap.along - e[1]), ll: intMarkers[e[0]].getLatLng()};
    var pt = isStart ? c[0] : c[c.length - 1];
    return {label: null, dist: isStart ? snap.along : trailIntMap[snap.ti].length - snap.along,
            ll: L.latLng(pt[1], pt[0])};
  }
  var a = end(ends.before, true), b = end(ends.after, false);
  // Lay the strip out west to east so it matches the map
  var west = a.ll.lng <= b.ll.lng ? a : b;
  return {type: "seg", trail: snap.name, off: snap.d, left: west, right: west === a ? b : a,
          tan: snap.tan, afterIsRight: west === a};
}

// Which way the strip's "you" marker should point: 1 right, -1 left, 0 no heading
function stripDir(place) {
  var h = currentHeading();
  if (h === null) return 0;
  var towardAfter = Math.abs(((h - place.tan + 540) % 360) - 180) < 90;
  return towardAfter === place.afterIsRight ? 1 : -1;
}

function stripYouHtml(dir) {
  return dir === 0 ? '<span class="seg-you" title="You"></span>'
    : '<span class="seg-you-arrow" style="transform:rotate(' + (dir * 90) + 'deg)" title="You">' + USER_ARROW + '</span>';
}

// Called whenever the heading changes; only touches the DOM when the direction flips
var shownPlace = null, shownStripDir = null;
function updateStripArrow() {
  var slot = document.querySelector("#locateInfo .seg-you-slot");
  if (slot && shownPlace && shownPlace.type === "seg") {
    var dir = stripDir(shownPlace);
    if (dir !== shownStripDir) {
      shownStripDir = dir;
      slot.innerHTML = stripYouHtml(dir);
    }
  }
}

function locateHtml(place) {
  var html;
  shownPlace = place;
  if (place.type === "at") {
    html = '<div class="route-msg" style="margin-top:0;font-size:13px">You are at ' + intPill(place.label) + '</div>';
  } else if (place.type === "off") {
    html = '<div class="route-msg" style="margin-top:0;font-size:13px">You are off trail, about <strong>' +
      formatDist(place.dist) + '</strong> from ' + intPill(place.label) + '</div>';
  } else {
    var endHtml = function(e) {
      return e.label ? intPill(e.label) : '<span class="int-link seg-end" title="Trail ends here">end</span>';
    };
    html = '<div class="seg-view">' +
      '<div class="seg-row">' + endHtml(place.left) +
        '<div class="seg-part" style="flex-grow:' + Math.max(place.left.dist, 1) + '"><span class="seg-dist">' + formatDist(place.left.dist) + '</span></div>' +
        '<span class="seg-you-slot">' + stripYouHtml(shownStripDir = stripDir(place)) + '</span>' +
        '<div class="seg-part" style="flex-grow:' + Math.max(place.right.dist, 1) + '"><span class="seg-dist">' + formatDist(place.right.dist) + '</span></div>' +
        endHtml(place.right) +
      '</div>' +
      '<div class="seg-trail">on <em>' + esc(place.trail) + '</em>' +
        (place.off > 25 ? ' · about ' + formatDist(place.off) + ' off the trail' : '') + '</div>' +
    '</div>';
  }
  if (userAccuracy > 30) {
    html += '<div class="full-only" style="color:#777;font-size:11px;margin-top:4px">GPS accuracy ±' + formatDist(userAccuracy) + '</div>';
  }
  if (crumbs.length > 1) {
    html += '<div class="full-only" style="text-align:right;margin-top:4px"><a class="crumb-clear" onclick="clearCrumbs()">Clear breadcrumbs</a></div>';
  }
  if (plan) html += '<div style="margin-top:2px">' + backToRouteBtn() + '</div>';
  else html += exitsHtml();
  return '<div id="locateInfo">' + html + '</div>';
}

var ENTRY_NEAR_M = 60;   // crumbs this close to an entry point count as passing it
var showAllExits = false;

function entryLabels() {
  return Object.keys(intFeatures).filter(function(label) { return intFeatures[label].properties.entry; });
}

// The entry point this outing started from: the first one the breadcrumbs pass near.
// The breadcrumbs only ever hold the current outing; see checkFreshStart. Once found it
// stays found, and only new crumbs are checked until then.
var entrance = null, entranceScanned = 0;
function inferEntrance() {
  var entries = entryLabels();
  while (!entrance && entranceScanned < crumbs.length) {
    var ll = L.latLng(crumbs[entranceScanned][0], crumbs[entranceScanned][1]);
    entranceScanned++;
    for (var k = 0; k < entries.length && !entrance; k++) {
      if (ll.distanceTo(intMarkers[entries[k]].getLatLng()) <= ENTRY_NEAR_M) entrance = entries[k];
    }
  }
  return entrance;
}

function exitBtnHtml(e) {
  var p = intFeatures[e.label].properties;
  return '<button class="exit-btn" onclick="routeFromMe(\'' + e.label + '\')">' +
    '<span class="int-link" style="background:' + ZONE_COLORS[p.zone] + '">' + e.label + '</span>' +
    '<span class="exit-dist">' + formatDist(e.dist) + '</span>' +
    (p.parking ? '<span class="parking-tag" style="margin-left:0">P</span>' : '') +
    (p.connects ? '<span class="exit-note">to ' + esc(p.connects) + '</span>' : '') + '</button>';
}

// Large view only, when not navigating: quick routes out to the entry points
function exitsHtml() {
  var exits = [], anchors = userAnchors(userLatLng);
  entryLabels().forEach(function(label) {
    if (userLatLng.distanceTo(intMarkers[label].getLatLng()) > AT_INT_M) {
      var best = bestRouteFromMe(label, anchors);
      if (best) exits.push({label: label, dist: best.total});
    }
  });
  exits.sort(function(a, b) { return a.dist - b.dist; });
  if (exits.length === 0) return '';

  var entrance = inferEntrance();
  var mine = exits.filter(function(e) { return e.label === entrance; })[0];
  var html = '<div class="full-only exits">';
  if (mine) {
    html += '<div class="exits-head">Back to your entrance</div>' + exitBtnHtml(mine);
    var others = exits.filter(function(e) { return e !== mine; });
    if (others.length) {
      html += '<div><a class="crumb-clear" onclick="showAllExits=!showAllExits;refreshLocateInfo()">' +
        (showAllExits ? 'Hide other exits' : 'Show other exits (' + others.length + ')') + '</a></div>';
      if (showAllExits) html += others.map(exitBtnHtml).join('');
    }
  } else {
    html += '<div class="exits-head">Exits</div>' + exits.map(exitBtnHtml).join('');
  }
  return html + '</div>';
}

function showLocateInfo() {
  clearSelection(true);
  var place = userPlace(userLatLng);
  document.getElementById("infoContent").innerHTML = locateHtml(place);

  var pts = [userLatLng];
  if (place.type === "at") pts.push(intMarkers[place.label].getLatLng());
  else if (place.type === "seg") pts.push(place.left.ll, place.right.ll);
  else if (place.dist < 3000) pts.push(intMarkers[place.label].getLatLng());
  if (pts.length > 1) {
    map.fitBounds(L.latLngBounds(pts).pad(0.3), {maxZoom: 17});
  } else {
    map.setView(userLatLng, Math.max(map.getZoom(), 14));
  }
}

// Keep an open locate panel current as you walk, without moving the map
function refreshLocateInfo() {
  var el = document.getElementById("locateInfo");
  if (el) el.outerHTML = locateHtml(userPlace(userLatLng));
}

// Breadcrumbs: where you've walked in this browser tab (survives a reload)
var CRUMB_KEY = "vtnCrumbs";
var crumbs = [];
try { crumbs = JSON.parse(sessionStorage.getItem(CRUMB_KEY)) || []; } catch (e) { crumbs = []; }
// Each outing starts fresh. The phone stops tracking whenever the screen is off, so a gap
// alone doesn't mean you left; these are the signs that you did:
var FIX_KEY = "vtnLastFix";                 // time and place of the last fix, across reloads
var FAR_FROM_NETWORK_M = 1000;              // this far outside the network: you drove away
var EXIT_NEAR_M = 100, EXIT_GAP_MS = 30 * 60 * 1000;   // stopped near an exit, back much later
var NEW_DAY_GAP_MS = 4 * 3600 * 1000;       // a long break, wherever you were

function readLastFix() {
  try { return JSON.parse(sessionStorage.getItem(FIX_KEY)); } catch (e) { return null; }
}

function distFromNetwork(ll) {
  var sw = NETWORK_BOUNDS.getSouthWest(), ne = NETWORK_BOUNDS.getNorthEast();
  return ll.distanceTo(L.latLng(Math.max(sw.lat, Math.min(ne.lat, ll.lat)),
                                Math.max(sw.lng, Math.min(ne.lng, ll.lng))));
}

function nearEntry(ll, m) {
  return entryLabels().some(function(label) { return ll.distanceTo(intMarkers[label].getLatLng()) <= m; });
}

// Called with each fix, before it is added as a crumb. The place rules only trust fixes
// good enough to tell: a rough fix can land a kilometer off, or near an entry you aren't at.
// Stopping near an exit only counts if you also come back near one (the same lot or
// another); otherwise it was probably a glance at the phone while walking past.
function checkFreshStart(ll, acc) {
  var last = readLastFix();
  var gap = last ? Date.now() - last.t : Infinity;
  var left = distFromNetwork(ll) - acc > FAR_FROM_NETWORK_M || gap >= NEW_DAY_GAP_MS ||
    (gap >= EXIT_GAP_MS && last.acc <= EXIT_NEAR_M && acc <= EXIT_NEAR_M &&
     nearEntry(L.latLng(last.lat, last.lng), EXIT_NEAR_M) && nearEntry(ll, EXIT_NEAR_M));
  if (crumbs.length && left) clearCrumbs();
  try {
    sessionStorage.setItem(FIX_KEY, JSON.stringify({t: Date.now(), lat: ll.lat, lng: ll.lng, acc: acc}));
  } catch (e) {}
}

// Don't even draw yesterday's walk while waiting for the first fix
var lastFixOnLoad = readLastFix();
if (!lastFixOnLoad || Date.now() - lastFixOnLoad.t >= NEW_DAY_GAP_MS) {
  crumbs = [];
  try { sessionStorage.removeItem(CRUMB_KEY); } catch (e) {}
}

var crumbLine = L.polyline(crumbs, {
  color: "#1e88e5", weight: 4, opacity: 0.6, dashArray: "1,8", lineCap: "round", interactive: false
}).addTo(map);

function addCrumb(ll, acc) {
  var last = crumbs.length ? L.latLng(crumbs[crumbs.length - 1]) : null;
  if (acc <= 40 && (!last || last.distanceTo(ll) >= 5) && distFromNetwork(ll) <= FAR_FROM_NETWORK_M) {
    crumbs.push([+ll.lat.toFixed(6), +ll.lng.toFixed(6), Date.now()]);
    if (crumbs.length > 5000) {
      crumbs.shift();
      if (entranceScanned > 0) entranceScanned--;
    }
    crumbLine.setLatLngs(crumbs);
    try { sessionStorage.setItem(CRUMB_KEY, JSON.stringify(crumbs)); } catch (e) {}
  }
}

function clearCrumbs() {
  crumbs = [];
  entrance = null;
  entranceScanned = 0;
  crumbLine.setLatLngs([]);
  try { sessionStorage.removeItem(CRUMB_KEY); } catch (e) {}
  refreshLocateInfo();
}

// Heading: compass when the phone provides one, otherwise direction of travel
var compassHeading = null, compassTime = 0, moveHeading = null, headingAnchor = null;
var shownHeading = null;
var compassStarted = false;

function bearing(a, b) {
  var dx = (b.lng - a.lng) * 82000, dy = (b.lat - a.lat) * 111000;
  return (Math.atan2(dx, dy) * 180 / Math.PI + 360) % 360;
}

function onOrientation(e) {
  var h = null;
  if (typeof e.webkitCompassHeading === "number") {
    h = e.webkitCompassHeading;
  } else if (e.absolute && e.alpha !== null) {
    h = 360 - e.alpha;
  }
  if (h !== null) {
    var screenAngle = (screen.orientation && screen.orientation.angle) || window.orientation || 0;
    compassHeading = (h + screenAngle + 360) % 360;
    compassTime = Date.now();
    updateUserIcon();
  }
}

function startCompass() {
  if (!compassStarted && window.DeviceOrientationEvent) {
    var listen = function() {
      compassStarted = true;
      window.addEventListener("ondeviceorientationabsolute" in window ? "deviceorientationabsolute" : "deviceorientation", onOrientation);
    };
    if (typeof DeviceOrientationEvent.requestPermission === "function") {
      // iOS asks for permission, and only from a tap
      DeviceOrientationEvent.requestPermission().then(function(s) { if (s === "granted") listen(); }).catch(function() {});
    } else {
      listen();
    }
  }
}

function updateMoveHeading(pos, ll) {
  var c = pos.coords;
  if (typeof c.heading === "number" && !isNaN(c.heading) && c.speed > 0.5) {
    moveHeading = c.heading;
    headingAnchor = ll;
  } else if (!headingAnchor) {
    headingAnchor = ll;
  } else if (c.accuracy <= 40 && headingAnchor.distanceTo(ll) >= 8) {
    moveHeading = bearing(headingAnchor, ll);
    headingAnchor = ll;
  }
}

function currentHeading() {
  return Date.now() - compassTime < 3000 ? compassHeading : moveHeading;
}

var USER_ARROW = '<svg width="30" height="30" viewBox="0 0 30 30"><path d="M15 2 L26 27 L15 21 L4 27 Z" ' +
  'fill="#1e88e5" stroke="#fff" stroke-width="2.5" stroke-linejoin="round"/></svg>';

function updateUserIcon() {
  if (userDot) {
    var el = userDot.getElement();
    var h = currentHeading();
    if (el) {
      var inner = el.firstChild;
      if (h === null) {
        if (shownHeading !== null || !inner.classList.contains("user-dot")) {
          inner.className = "user-dot";
          inner.innerHTML = "";
          inner.style.transform = "";
        }
        shownHeading = null;
      } else {
        if (!inner.classList.contains("user-arrow")) {
          inner.className = "user-arrow";
          inner.innerHTML = USER_ARROW;
          shownHeading = h;
        }
        // Ease toward the new heading the short way round, to calm compass jitter
        var diff = ((h - shownHeading + 540) % 360) - 180;
        shownHeading = (shownHeading + diff * 0.4 + 360) % 360;
        inner.style.transform = "rotate(" + shownHeading.toFixed(1) + "deg)";
      }
    }
  }
  updateStripArrow();
}

// Follow mode: keep the map centered on you until you pan it yourself
var following = false;

function setFollowing(on) {
  following = on;
  if (locateBtn) locateBtn.classList.toggle("following", on);
}

map.on("dragstart", function() { setFollowing(false); });

function onLocation(pos) {
  var first = !userLatLng;
  userLatLng = L.latLng(pos.coords.latitude, pos.coords.longitude);
  userAccuracy = pos.coords.accuracy;
  checkFreshStart(userLatLng, userAccuracy);
  addCrumb(userLatLng, userAccuracy);
  updateMoveHeading(pos, userLatLng);
  if (!userDot) {
    userAccCircle = L.circle(userLatLng, {
      radius: userAccuracy, stroke: false, fillColor: "#1e88e5", fillOpacity: 0.12, interactive: false
    }).addTo(map);
    userDot = L.marker(userLatLng, {
      icon: L.divIcon({className: "user-icon", iconSize: [30, 30], iconAnchor: [15, 15],
        html: '<div class="user-dot"></div>'}),
      title: "You", keyboard: false
    }).addTo(map);
    userDot.on("click", function(e) { L.DomEvent.stopPropagation(e); showLocateInfo(); });
  } else {
    userAccCircle.setLatLng(userLatLng).setRadius(userAccuracy);
    userDot.setLatLng(userLatLng);
  }
  updateUserIcon();
  locateBtn.classList.add("active");

  if (locateRequested) {
    locateRequested = false;
    showLocateInfo();
  } else if (first) {
    // Add "Route here from my location" to an open intersection panel, but don't
    // interrupt picking a destination
    if (currentIntFeature && selectedMarker && !routeMode) showIntInfo(currentIntFeature, selectedMarker);
    if (!targetInt && NETWORK_BOUNDS.contains(userLatLng)) map.setView(userLatLng, 16);
  } else if (liveRouting()) {
    updateLiveRoute();
  } else {
    refreshLocateInfo();
  }
  if (following) map.panTo(userLatLng);
}

function onLocationError(err) {
  if (err.code === 1 && watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }
  if (locateRequested) {
    locateRequested = false;
    showPanelMsg(err.code === 1
      ? "Location access is blocked for this site. You can allow it in your browser's site settings."
      : "Couldn't get your location. Try again in a moment.");
  }
}

function startWatch() {
  if (watchId === null) {
    watchId = navigator.geolocation.watchPosition(onLocation, onLocationError,
      {enableHighAccuracy: true, maximumAge: 10000, timeout: 30000});
  }
}

function locateMe() {
  if (!navigator.geolocation) {
    showPanelMsg("This browser can't share its location.");
  } else {
    startWatch();
    startCompass();
    setFollowing(true);
    if (userLatLng && liveRouting()) {
      map.setView(userLatLng, Math.max(map.getZoom(), 17));   // keep the route panel
    } else if (userLatLng) {
      showLocateInfo();
    } else {
      locateRequested = true;
      showPanelMsg("Finding your location…");
    }
  }
}

var LocateControl = L.Control.extend({
  options: {position: "topright"},
  onAdd: function() {
    var div = L.DomUtil.create("div", "leaflet-bar locate-ctl");
    var a = L.DomUtil.create("a", "", div);
    a.href = "#";
    a.title = "Locate me";
    a.setAttribute("role", "button");
    a.setAttribute("aria-label", "Locate me");
    a.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">' +
      '<circle cx="12" cy="12" r="4"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>';
    L.DomEvent.disableClickPropagation(div);
    L.DomEvent.on(a, "click", function(e) { L.DomEvent.preventDefault(e); locateMe(); });
    locateBtn = a;
    return div;
  }
});
new LocateControl().addTo(map);

// ?sim: fake geolocation driven by mobile_preview.html via window.simLocate
var simMode = new URLSearchParams(location.search).has("sim");
if (simMode) {
  var simCallback = null;
  var simPos = null;
  var fakeGeo = {
    watchPosition: function(ok) {
      simCallback = ok;
      if (simPos) setTimeout(function() { ok(simPos); }, 0);
      return 1;
    },
    clearWatch: function() { simCallback = null; }
  };
  Object.defineProperty(navigator, "geolocation", {value: fakeGeo, configurable: true});
  window.simLocate = function(lat, lon, acc) {
    simPos = {coords: {latitude: lat, longitude: lon, accuracy: acc || 10}, timestamp: Date.now()};
    if (simCallback) simCallback(simPos);
  };
  // Behave as if permission was granted earlier
  startWatch();
} else if (navigator.geolocation && navigator.permissions && navigator.permissions.query) {
  // If permission was granted on an earlier visit, show the dot without prompting
  navigator.permissions.query({name: "geolocation"}).then(function(r) {
    if (r.state === "granted") startWatch();
  }).catch(function() {});
}

// Keyboard intersection search
var searchBuf = "";
var searchTimer = null;
var searchHighlighted = [];
var searchBadge = document.getElementById("searchBadge");

function clearSearch() {
  searchBuf = "";
  searchBadge.style.display = "none";
  searchHighlighted.forEach(function(label) {
    var m = intMarkers[label];
    if (m && m !== selectedMarker) {
      var z = m._zone;
      m.setStyle({radius: 7, weight: 2, color: "#fff", fillColor: ZONE_COLORS[z], fillOpacity: 0.85});
    }
  });
  searchHighlighted = [];
}

function applySearch() {
  searchHighlighted.forEach(function(label) {
    var m = intMarkers[label];
    if (m && m !== selectedMarker) {
      var z = m._zone;
      m.setStyle({radius: 7, weight: 2, color: "#fff", fillColor: ZONE_COLORS[z], fillOpacity: 0.85});
    }
  });
  searchHighlighted = [];

  var matches = Object.keys(intMarkers).filter(function(label) {
    return label.toUpperCase().indexOf(searchBuf) === 0 && zoneVisible[label.replace(/[0-9]/g, "")];
  });

  if (matches.length === 0) {
    searchBadge.textContent = searchBuf + " ?";
    clearTimeout(searchTimer);
    searchTimer = setTimeout(clearSearch, 1200);
    return;
  }

  if (matches.length === 1) {
    searchBadge.style.display = "none";
    var label = matches[0];
    if (routeMode) {
      completeRoute(label);
    } else if (intMarkers[label] && intFeatures[label]) {
      showIntInfo(intFeatures[label], intMarkers[label]);
      map.panTo(intMarkers[label].getLatLng());
    }
    searchBuf = "";
    searchHighlighted = [];
    return;
  }

  matches.forEach(function(label) {
    var m = intMarkers[label];
    if (m && m !== selectedMarker) {
      m.setStyle({radius: 11, weight: 3, color: "#f1c40f", fillColor: "#f1c40f", fillOpacity: 1});
      m.bringToFront();
    }
  });
  searchHighlighted = matches;
}

document.addEventListener("keydown", function(e) {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
  var key = e.key.toUpperCase();

  if (/^[A-F]$/.test(key)) {
    clearSearch();
    searchBuf = key;
    searchBadge.textContent = searchBuf;
    searchBadge.style.display = "block";
    applySearch();
    var zonePts = [];
    Object.keys(intMarkers).forEach(function(label) {
      if (label.replace(/[0-9]/g, "") === key) zonePts.push(intMarkers[label].getLatLng());
    });
    if (zonePts.length > 0) {
      map.fitBounds(L.latLngBounds(zonePts).pad(0.15));
    }
  } else if (/^[0-9]$/.test(key) && searchBuf.length > 0) {
    searchBuf += key;
    searchBadge.textContent = searchBuf;
    applySearch();
  } else if (e.key === "Backspace" && searchBuf.length > 0) {
    e.preventDefault();
    searchBuf = searchBuf.slice(0, -1);
    if (searchBuf.length === 0) {
      clearSearch();
    } else {
      searchBadge.textContent = searchBuf;
      applySearch();
    }
  } else if (e.key === "Escape") {
    clearSearch();
  }
});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------

def main():
    ints, trails, rows = load_and_process()
    print("Processed %d intersections" % len(rows))

    build_landing(rows)
    build_map_page(ints, trails, rows)
    build_zones_page(rows)
    build_owners_page(rows)


if __name__ == "__main__":
    main()
