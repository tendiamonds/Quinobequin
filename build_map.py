"""
Build the Vietnam Trail Network website (4 pages):
  index.html  — landing page
  map.html    — interactive Leaflet map
  zones.html  — zone-by-zone intersection report
  owners.html — owner-grouped intersection report

All pages cross-link: intersection labels link to the map,
owner names link to the owner page, zone badges link to the zone page.
"""

import json
import math
import re
from collections import OrderedDict

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
    "A": (-71.4856, 42.1786),
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

def load_and_process():
    with open(rf"{PROJ}\parcels_all.geojson") as f:
        parcels = json.load(f)
    with open(r"C:\Users\jbreslau\Downloads\intersections_zoned.geojson") as f:
        ints = json.load(f)
    with open(rf"{PROJ}\trails_selected.geojson") as f:
        trails = json.load(f)

    by_zone = {}
    for feat in ints["features"]:
        z = feat["properties"]["zone"]
        by_zone.setdefault(z, []).append(feat)

    for z in "ABCDEF":
        pts = by_zone.get(z, [])
        ex, ey = EXIT_POINTS[z]
        pts.sort(key=lambda f: math.sqrt(
            ((f["geometry"]["coordinates"][0] - ex) * 82000) ** 2 +
            ((f["geometry"]["coordinates"][1] - ey) * 111000) ** 2
        ))
        if z == "F":
            f_main = [f for f in pts if f["properties"]["number"] not in F_G_GROUP]
            f_tail = [f for f in pts if f["properties"]["number"] in F_G_GROUP]
            pts = f_main + f_tail
        for i, feat in enumerate(pts, 1):
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
  Some zones have an associated organization:</p>

  <table class="zone-table">
    <thead><tr><th>Zone</th><th>Name</th><th>Organization</th><th>Towns</th></tr></thead>
    <tbody>
      <tr><td><a href="zones.html#zone-A" class="tag tag-zone" style="background:#e74c3c">A</a></td>
          <td>Adams Town Forest</td><td>The Trustees of Reservations</td><td>Holliston</td></tr>
      <tr><td><a href="zones.html#zone-B" class="tag tag-zone" style="background:#3498db">B</a></td>
          <td>Beaver Brook Woods</td><td></td><td>Milford, Holliston</td></tr>
      <tr><td><a href="zones.html#zone-C" class="tag tag-zone" style="background:#2ecc71">C</a></td>
          <td>College Rock Park</td><td></td><td>Hopkinton, Holliston, Milford</td></tr>
      <tr><td><a href="zones.html#zone-D" class="tag tag-zone" style="background:#f39c12">D</a></td>
          <td>Rocky Woods</td><td></td><td>Holliston, Milford</td></tr>
      <tr><td><a href="zones.html#zone-E" class="tag tag-zone" style="background:#9b59b6">E</a></td>
          <td>NEMBA Land</td><td>New England Mountain Bike Association</td><td>Milford, Holliston</td></tr>
      <tr><td><a href="zones.html#zone-F" class="tag tag-zone" style="background:#1abc9c">F</a></td>
          <td>Fairbanks</td><td>The Trustees of Reservations / DCR</td><td>Holliston, Milford</td></tr>
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


def build_map_page(ints, trails, rows):
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

    html = MAP_TEMPLATE
    html = html.replace("__NAV__", nav_html("map"))
    html = html.replace("__TRAIL_DATA__", trail_data)
    html = html.replace("__INT_DATA__", int_data)
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
    width: 300px; max-height: calc(100vh - 62px); overflow-y: auto;
    font-size: 13px;
  }
  .info-panel h2 {
    font-size: 15px; padding: 12px 14px 8px; margin: 0;
    border-bottom: 1px solid #e0e0e0;
  }
  .info-panel .content { padding: 10px 14px 14px; }
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

  @media (max-width: 640px) {
    .info-panel { width: calc(100vw - 20px); top: auto; bottom: 0; left: 0;
      border-radius: 12px 12px 0 0; max-height: 45vh; }
    .zone-filter { top: 52px; right: 10px; }
    .legend-panel { display: none; }
  }
</style>
</head>
<body>
__NAV__
<div id="map"></div>

<div class="info-panel" id="infoPanel">
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
  <div class="legend-row"><div class="legend-line" style="background:#e67e22;height:4px"></div> Trail (highlighted)</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#888"></div> Intersection</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#f1c40f;border-color:#222"></div> Selected</div>
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

intData.features.forEach(function(f) {
  var zone = f.properties.zone;
  var label = f.properties.label;
  var ll = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
  var color = ZONE_COLORS[zone];

  var marker = L.circleMarker(ll, {
    radius: 7, fillColor: color, color: "#fff",
    weight: 2, fillOpacity: 0.85
  }).addTo(map);
  marker.on("click", function(e) {
    L.DomEvent.stopPropagation(e);
    showIntInfo(f, marker);
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

function showIntInfo(feature, marker) {
  clearSelection();
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
    '<tr><td>Owner</td><td><a href="' + ownerHref + '">' + p.owner + '</a> ' + pubTag + '</td></tr>' +
    '<tr><td>Town</td><td>' + p.town + '</td></tr>' +
    '<tr><td>Degree</td><td>' + p.degree + '-way intersection</td></tr>' +
    '</table>';
  document.getElementById("infoContent").innerHTML = html;
}

function showTrailInfo(feature, layer) {
  clearSelection();

  var p = feature.properties;
  var name = p.pdf_name || p.name || "";

  highlightedSegments = [];
  trailLayer.eachLayer(function(l) {
    var ln = l.feature.properties.pdf_name || l.feature.properties.name || "";
    if (ln === name && name !== "") {
      l.setStyle({color: "#e67e22", weight: 5, opacity: 1});
      highlightedSegments.push(l);
    }
  });
  if (highlightedSegments.length === 0) {
    layer.setStyle({color: "#e67e22", weight: 5, opacity: 1});
    highlightedSegments.push(layer);
  }

  var displayName = name || "Unnamed trail";
  var segments = name ? (trailsByName[name] || []) : [feature];

  var html = '<table>' +
    '<tr><td>Trail</td><td><strong style="font-size:16px">' + displayName + '</strong></td></tr>';
  if (p.surface) html += '<tr><td>Surface</td><td>' + p.surface + '</td></tr>';
  if (p.highway) html += '<tr><td>Type</td><td>' + p.highway + '</td></tr>';
  if (segments.length > 1) html += '<tr><td>Segments</td><td>' + segments.length + '</td></tr>';
  html += '</table>';

  document.getElementById("infoContent").innerHTML = html;
}

function clearSelection() {
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
}

var defaultInfo = '<p style="color:#888">Click a trail or intersection marker for details.</p>' +
  '<p style="margin-top:8px;color:#888;font-size:11px">__N_INTS__ numbered intersections across 6 zones.<br>' +
  '__N_TRAILS__ trail segments, __N_NAMES__ named trails.</p>';

map.on("click", function() {
  clearSelection();
  document.getElementById("infoContent").innerHTML = defaultInfo;
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
    if (zoneVisible[z]) {
      if (!map.hasLayer(intMarkers[label])) intMarkers[label].addTo(map);
      if (!map.hasLayer(labelMarkers[label])) labelMarkers[label].addTo(map);
    } else {
      if (map.hasLayer(intMarkers[label])) map.removeLayer(intMarkers[label]);
      if (map.hasLayer(labelMarkers[label])) map.removeLayer(labelMarkers[label]);
    }
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
