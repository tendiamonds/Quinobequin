"""
The trail map app, shared by every region's site.

build_map_page(ints, trails, region, out_dir) writes out_dir/map.html. region is a dict:
  name           the map's title, e.g. "Upper Charles Forest"
  zones          {code: {"name": ..., "color": ...}}; a label starts with its zone's code
                 (A12, or 2070 for zone 2)
  view           {"center": [lat, lon], "zoom": z}, before the map fits bounds
  bounds         [[south, west], [north, east]] of the trail network
  storagePrefix  prefix for what the browser keeps (settings, breadcrumbs), so two
                 regions served from the same site don't mix them up
  report         where reports go and which kinds this region offers (see the app)
  zonesPage      whether the site has a zones.html for zone tags to link to
  otherMaps      [{"name": ..., "href": ...}] links to the other regions' maps
  placeLabels    (optional) [{"name", "lat", "lon"}] names for places the map tiles don't
                 label (Skidmore's residence buildings), shown up close
  nav            the page's top navigation bar (HTML)
  dem            (optional) where to keep the region's elevation grid (elevation.py); with
                 it, trails get elevation profiles
  blazes, widths, terrain   (optional) blazed trails and trail widths (build_bluehills.py)

The intersections and trails are GeoJSON; build_trail_int_map works out which
intersections lie on which trails, which the app routes over.
"""

import json
import math
import os
import re
import urllib.parse

import elevation


def dist_m(lon1, lat1, lon2, lat2):
    """Approximate meters between two points (good enough near 42 N, where the regions are)"""
    return math.sqrt(((lon1 - lon2) * 82000)**2 + ((lat1 - lat2) * 111000)**2)


def build_trail_int_map(ints, trails):
    """Map each trail feature index to its intersections with distances.
    A trail passes an intersection if it has a point within SNAP_DIST of it. Unsigned
    junctions are placed exactly where trails meet, so they use a tight JUNCTION_SNAP and
    never catch a neighboring trail that only runs close by."""
    SNAP_DIST = 20
    JUNCTION_SNAP = 6
    int_list = [(feat["properties"]["label"],
                 feat["geometry"]["coordinates"][0],
                 feat["geometry"]["coordinates"][1],
                 JUNCTION_SNAP if feat["properties"].get("junction") else SNAP_DIST)
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
        for label, ilon, ilat, snap in int_list:
            best_d = float("inf")
            best_cum = 0
            for j, c in enumerate(coords):
                d = dist_m(ilon, ilat, c[0], c[1])
                if d < best_d:
                    best_d = d
                    best_cum = cum[j]
            if best_d < snap:
                hits.append((best_cum, label))

        hits.sort()
        result[ti] = {
            "length": round(total_length),
            "ints": [[label, round(d)] for d, label in hits]
        }

    return result


# The sites' maps, for each one's menu of the others: (key, name, path from the site's root)
SITE_MAPS = [("uc", "Upper Charles Forest", "map.html"), ("bh", "Blue Hills", "bluehills/map.html"),
             ("sar", "Saratoga Woods", "saratoga/map.html")]


def maps_menu_html(here, root):
    """A drop-down of the other maps, for the right end of a page's top bar. here: this
    site's key in SITE_MAPS; root: the way from this page to the sites' root ("" or "../")."""
    opts = "".join('<option value="%s%s">%s</option>' % (root, path, name) for key, name, path in SITE_MAPS if key != here)
    # Narrow (it would be as wide as its longest name), so a phone's top bar stays one row;
    # the phone's own picker shows the names in full
    return ('<select aria-label="Other maps" onchange="if (this.value) location.href = this.value" style="margin-left:auto;'
            'width:62px;flex:none;background:#2c3e50;color:#ecf0f1;border:1px solid #5d6d7e;border-radius:4px;'
            'font:500 13px sans-serif;padding:3px 2px">'
            '<option value="">Maps</option>' + opts + '</select>')


def build_map_page(ints, trails, region, out_dir, trail_int_map=None):
    """Write out_dir/map.html for a region (see the module docstring for its config).
    trail_int_map (optional): which intersections lie along each trail, as from
    build_trail_int_map, for data that already knows (OpenStreetMap trails meet at shared
    points); otherwise it's worked out by snapping."""
    for i, f in enumerate(trails["features"]):
        f["properties"]["_idx"] = i
    ele_step = elevation.add_elevations(ints, trails, region["bounds"], region["dem"]) if region.get("dem") else None

    int_data = json.dumps(ints)
    trail_data = json.dumps(trails)

    n_trails = len(trails["features"])
    n_ints = len([f for f in ints["features"] if not f["properties"].get("no_sign")])
    trail_names = set()
    for f in trails["features"]:
        name = f["properties"].get("pdf_name") or f["properties"].get("name") or ""
        if name:
            trail_names.add(name)
    n_names = len(trail_names)

    if trail_int_map is None:
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

    client = {k: region[k] for k in ("name", "zones", "view", "bounds", "storagePrefix", "report", "otherMaps", "zonesPage")}
    client["placeLabels"] = region.get("placeLabels", [])
    client["blazes"] = region.get("blazes", {})
    client["widths"] = region.get("widths", {})
    client["terrain"] = region.get("terrain", [])
    client["eleStep"] = ele_step
    html = MAP_TEMPLATE
    # Legend rows only for kinds of marker this region has
    for kind in ("post", "landmark", "road"):
        if not any(f["properties"].get(kind) for f in ints["features"] + trails["features"]):
            html = re.sub(r'  <div class="legend-row" data-legend="%s">.*\n' % kind, "", html)
        html = html.replace(' data-legend="%s"' % kind, "")
    html = html.replace("__REGION_JSON__", json.dumps(client))
    html = html.replace("__REGION_NAME__", region["name"])
    html = html.replace("__N_ZONES__", str(len(region["zones"])))
    html = html.replace("__NAV__", region["nav"])
    html = html.replace("__TRAIL_DATA__", trail_data)
    html = html.replace("__INT_DATA__", int_data)
    html = html.replace("__TRAIL_INT_MAP__", trail_int_json)
    html = html.replace("__INT_TRAIL_MAP__", int_trail_json)
    html = html.replace("__N_INTS__", str(n_ints))
    html = html.replace("__N_TRAILS__", str(n_trails))
    html = html.replace("__N_NAMES__", str(n_names))

    with open(os.path.join(out_dir, "map.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote " + os.path.join(out_dir, "map.html"))

    # How to let the site use your location, linked from the map when it can't
    report = region.get("report") or {}
    contact = ('<a href="mailto:%s?subject=%s">email us</a>.' % (report["email"], urllib.parse.quote(region["name"] + ": location won't work"))
               if report.get("email") else "use the map's Report a problem link.")
    page = (LOCATION_HELP.replace("__REGION_NAME__", region["name"]).replace("__NAV__", region["nav"])
            .replace("__REPORT__", contact))
    with open(os.path.join(out_dir, "location-help.html"), "w", encoding="utf-8") as f:
        f.write(page)


# ---------------------------------------------------------------------------
# Map HTML template
# ---------------------------------------------------------------------------

LOCATION_HELP = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta name="theme-color" content="#2c3e50">
<title>Turning on location — __REGION_NAME__</title>
<style>
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #222; line-height: 1.5; }
  nav.topnav { background: #2c3e50; padding: 10px 20px; display: flex; gap: 18px; align-items: center; flex-wrap: wrap; }
  @media (max-width: 420px) { nav.topnav { gap: 12px; padding: 10px 12px; } nav.topnav a { font-size: 13px; } }   /* one row on a phone */
  nav.topnav a { color: #ecf0f1; font-size: 14px; font-weight: 500; text-decoration: none; }
  .container { max-width: 720px; margin: 0 auto; padding: 20px; }
  h1 { font-size: 22px; margin: 4px 0 6px; }
  h2 { font-size: 18px; margin: 26px 0 8px; padding-bottom: 4px; border-bottom: 2px solid #eee; }
  .lead { color: #555; margin: 0 0 12px; }
  ol { padding-left: 22px; margin: 6px 0; }
  li { margin: 6px 0; }
  .path { font-weight: 600; }
  .tip { background: #fff8e1; border-left: 4px solid #f9a825; padding: 8px 12px; margin: 12px 0; font-size: 14px; }
  .jump a { display: inline-block; margin: 4px 8px 4px 0; padding: 6px 12px; border-radius: 16px; background: #eceff1; color: #263238;
            text-decoration: none; font-size: 14px; font-weight: 600; }
  .back { display: inline-block; margin-top: 18px; padding: 10px 16px; border-radius: 6px; background: #0d47a1; color: white;
          text-decoration: none; font-weight: 600; }
</style>
</head>
<body>
__NAV__
<div class="container">
<h1>Turning on location</h1>
<p class="lead">The map can show where you are, follow you along a route, and tell you which way to turn. For that, your
phone has to let this website use its location. Your location stays on your phone: the map only sends it if you choose
to, in a problem report.</p>
<p class="jump"><a href="#iphone">iPhone</a><a href="#iphone-chrome">iPhone with Chrome</a><a href="#android">Android</a><a href="#still">Still stuck?</a></p>

<h2 id="iphone">iPhone or iPad (Safari)</h2>
<p>There are three switches, and all three have to be on. Most trouble comes from the third: if you ever tapped
<strong>Don&rsquo;t Allow</strong>, Safari remembers it and stops asking.</p>
<ol>
  <li><strong>Location for the phone.</strong> Open <span class="path">Settings &rsaquo; Privacy &amp; Security &rsaquo; Location Services</span>
    and turn <strong>Location Services</strong> on.</li>
  <li><strong>Location for websites.</strong> On that same screen, scroll down to <span class="path">Safari Websites</span>. Choose
    <strong>While Using the App</strong> (or <strong>Ask Next Time Or When I Share</strong>), and turn on <strong>Precise Location</strong>.
    Without Precise Location, the phone only shares a rough area, and the map will think you&rsquo;re nowhere near the trails.</li>
  <li><strong>Location for this site.</strong> Open the map in Safari. Tap the <strong>aA</strong> button (or the small page icon) at the
    left end of the address bar, then <span class="path">Website Settings &rsaquo; Location</span>, and choose <strong>Allow</strong> or
    <strong>Ask</strong>.
    <br>Or for every site at once: <span class="path">Settings &rsaquo; Apps &rsaquo; Safari &rsaquo; Location</span> (on older iPhones,
    <span class="path">Settings &rsaquo; Safari &rsaquo; Location</span>), and choose <strong>Ask</strong> or <strong>Allow</strong>.</li>
  <li><strong>Try it.</strong> Reload the map and tap the locate button (the circle with a cross, at the top right). If the phone
    asks, tap <strong>Allow</strong>.</li>
</ol>
<div class="tip"><strong>Using the map from its home-screen icon?</strong> It asks for location separately from Safari. If you once
told it no, open the map in Safari, allow location there as above, then try the icon again. If the icon still won&rsquo;t ask,
remove it from the home screen and add it again: in Safari, tap <span class="path">Share &rsaquo; Add to Home Screen</span>.</div>
<p style="font-size:13px;color:#666">The names of these settings move around a little between iPhone updates; if a step
doesn&rsquo;t match what you see, look for the closest wording.</p>

<h2 id="iphone-chrome">iPhone with Chrome (or another browser)</h2>
<ol>
  <li>Open <span class="path">Settings &rsaquo; Privacy &amp; Security &rsaquo; Location Services</span> and make sure
    <strong>Location Services</strong> is on.</li>
  <li>On that screen, find <strong>Chrome</strong> (or your browser) in the list, choose <strong>While Using the App</strong>,
    and turn on <strong>Precise Location</strong>.</li>
  <li>Back in the browser, reload the map, tap the locate button, and tap <strong>Allow</strong> when asked.</li>
</ol>

<h2 id="android">Android (Chrome)</h2>
<ol>
  <li>Swipe down from the top of the screen and make sure <strong>Location</strong> is on. In the phone&rsquo;s
    <span class="path">Settings &rsaquo; Location</span>, turn on <strong>Use precise location</strong> (or <strong>Google Location
    Accuracy</strong>) if you see it.</li>
  <li>In Chrome, open the map and tap the icon at the left end of the address bar, then <span class="path">Permissions &rsaquo;
    Location</span> (or <strong>Site settings &rsaquo; Location</strong>), and choose <strong>Allow</strong>.
    <br>Or: <span class="path">Chrome menu &rsaquo; Settings &rsaquo; Site settings &rsaquo; Location</span>, and remove this site
    from the <strong>Blocked</strong> list.</li>
  <li>Reload the map, tap the locate button, and tap <strong>Allow</strong> when asked.</li>
</ol>

<h2 id="still">Still stuck?</h2>
<p>Out in the woods, the first location can take a minute: give it time with a view of the sky. If it still won&rsquo;t
work, let us know what kind of phone you have and what you see: __REPORT__</p>
<a class="back" href="map.html">Back to the map</a>
</div>
</body>
</html>
"""


MAP_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#2c3e50">
<title>Map — __REGION_NAME__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  a { color: #2980b9; text-decoration: none; }
  a:hover { text-decoration: underline; }
  nav.topnav { background: #2c3e50; padding: 10px 20px; display: flex; gap: 18px;
               align-items: center; flex-wrap: wrap; position: relative; z-index: 1001; }
  @media (max-width: 420px) { nav.topnav { gap: 12px; padding: 10px 12px; } nav.topnav a { font-size: 13px; } }   /* one row on a phone */
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
  .legend-head { cursor: pointer; user-select: none; display: flex; align-items: center; gap: 6px; }
  .legend-caret { font-size: 11px; color: #888; }
  .legend-panel.collapsed { padding: 6px 12px; }
  .legend-panel.collapsed h3 { margin-bottom: 0; }
  .legend-panel.collapsed .legend-row { display: none; }
  .legend-row { display: flex; align-items: center; margin: 3px 0; }
  .legend-swatch {
    width: 14px; height: 14px; border-radius: 50%; margin-right: 8px;
    border: 2px solid white; box-shadow: 0 0 2px rgba(0,0,0,0.3); flex-shrink: 0;
  }
  .legend-line {
    width: 20px; height: 3px; margin-right: 8px; border-radius: 2px; flex-shrink: 0;
  }

  .marker-label {
    background: none !important; border: none !important; box-shadow: none !important;
    font-size: 10px; font-weight: bold; font-family: -apple-system, sans-serif;
    white-space: nowrap;
  }
  .int-list { margin-top: 8px; }
  .int-list .int-row { display: flex; align-items: center; gap: 6px; padding: 3px 0; }
  .int-link {
    font-weight: 700; cursor: pointer; padding: 1px 6px; border-radius: 4px;
    font-size: 12px; color: white; display: inline-block; min-width: 36px; text-align: center;
  }
  .int-link:hover { opacity: 0.8; text-decoration: none; }
  .rock-svg { display: inline-block; vertical-align: middle; filter: drop-shadow(0 1px 1px rgba(0,0,0,0.35)); }
  .int-link.icon-pill { white-space: nowrap; min-width: 0; padding: 0 2px; color: #333; }
  .int-link.icon-pill .rock-svg { margin-top: -2px; }
  .rock-name { margin-left: 5px; font-weight: 600; vertical-align: middle; }
  .rock-name.passed { color: #9e9e9e; }
  /* Digits sit on the baseline with room below for descenders they don't have, so center
     the box and lift them a pixel */
  .post-badge { display: inline-flex; align-items: center; justify-content: center; padding-bottom: 1px;
    width: 15px; height: 15px; box-sizing: border-box;
    background: #9c7a4f; color: #ffd54f; font: 800 10px/1 sans-serif;
    text-shadow: 0 0 1px #3e2a12, 0 0 1px #3e2a12;
    border-radius: 3px; border: 1.5px solid #fff; box-shadow: 0 0 0 1px #5d4425, 0 1px 3px rgba(0,0,0,0.4);
    vertical-align: middle; cursor: pointer; }
  .junction-dot { display: inline-block; flex: none; width: 10px; height: 10px; border-radius: 50%;
    background: #9e9e9e; border: 2px solid #fff; box-shadow: 0 0 0 1px #9e9e9e; vertical-align: middle; margin: 0 2px; }
  .junction-dot.passed { opacity: 0.4; }
  .int-list .int-dist { color: #888; font-size: 11px; }
  .int-list .seg-bar { color: #bbb; font-size: 10px; padding: 0 0 0 16px; }
  .int-list .seg-link { display: block; color: #78909c; cursor: pointer; text-decoration: none; padding: 2px 0 2px 16px; }
  .int-list .seg-link:hover { color: #0277bd; text-decoration: underline; }
  .int-list .seg-link.sel { color: #00838f; font-weight: 700; border-left: 3px solid #00b8d4; padding-left: 13px; margin-left: 3px; }
  .trail-break { font-size: 10px; color: #90a4ae; font-style: italic; padding: 2px 0 2px 16px; }
  .trail-whole { color: #0277bd; cursor: pointer; text-decoration: underline; white-space: nowrap; }
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
  .turn-icon { flex: none; }
  .int-link.shape-pill { background: transparent; padding: 0; min-width: 0; line-height: 0; border-radius: 50%; }
  .shape-head { display: flex; align-items: center; gap: 10px; }
  /* Centered on its point (Leaflet places the marker itself by its transform, so the span moves) */
  .place-label span { position: absolute; transform: translate(-50%, -50%); white-space: nowrap; font: 600 11px sans-serif;
    color: #455a64; text-shadow: 1px 1px 0 #fff, -1px 1px 0 #fff, 1px -1px 0 #fff, -1px -1px 0 #fff; }
  .route-step.passed .turn-icon { opacity: 0.45; }
  .route-trail-name { color: #555; font-style: italic; }
  .entry-diamond { width: 24px; height: 24px; margin: 5px; transform: rotate(45deg);
    border: 4px solid #555; background: rgba(255,255,255,0.9); box-sizing: border-box;
    box-shadow: 0 0 0 1.5px #222; }
  .legend-diamond { width: 12px; height: 12px; margin: 2px 6px 2px 2px; border-width: 2px; display: inline-block; box-shadow: none; }
  .entry-tag { font-size: 11px; font-weight: 700; color: #333; }
  /* The P centered in the box, as in .lot-badge (a 15px line in a 12px box sat low) */
  .parking-badge { position: absolute; left: -9px; top: 22px; width: 15px; height: 15px; box-sizing: border-box;
    display: flex; align-items: center; justify-content: center;
    border-radius: 3px; background: #1565c0; color: #fff; border: 1.5px solid #fff;
    font: 700 11px/1 sans-serif; box-shadow: 0 0 0 1px #0d3c78; }
  .legend-row .parking-badge { position: static; display: inline-flex; margin: 0 6px 0 1px; vertical-align: middle; }
  .parking-tag { font-size: 11px; font-weight: 700; color: #1565c0; margin-left: 6px; }
  .lot-badge { display: inline-flex; align-items: center; justify-content: center;
    width: 16px; height: 16px; box-sizing: border-box; border-radius: 3px; background: #1565c0; color: #fff;
    font: 700 11px/1 sans-serif; border: 1.5px solid #fff; box-shadow: 0 0 0 1px #0d3c78; vertical-align: middle; }
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
    padding: 1px 5px; vertical-align: middle; }
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
  .route-title { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
  .route-compact-head .live-tag, .route-title .live-tag { margin-left: auto; }
  .route-row { display: flex; align-items: center; overflow-x: auto; position: relative;
    padding: 5px 4px 7px; scrollbar-width: none; }
  .route-row::-webkit-scrollbar { display: none; }
  .route-row .int-link { flex: none; min-width: 30px; }
  .route-next { white-space: nowrap; }
  .route-next .turn-icon { vertical-align: middle; margin-left: 4px; }
  .start-chip { display: inline-block; padding: 0 7px; border-radius: 10px; border: 2px solid #0d47a1;
    background: #fff; color: #0d47a1; font-size: 11px; font-weight: 700; line-height: 15px; flex: none; }
  .plan-link { margin-top: 8px; font-size: 12px; }
  .plan-link a { color: #777; text-decoration: underline; cursor: pointer; }
  .report-link { margin-top: 10px; font-size: 12px; text-align: right; }
  .report-link a { color: #777; text-decoration: underline; cursor: pointer; }
  .report-head { font-size: 13px; margin-bottom: 6px; }
  .report-kind { display: block; font-size: 13px; padding: 3px 0; cursor: pointer; }
  .report textarea { width: 100%; margin: 6px 0; font: inherit; font-size: 13px; padding: 4px 6px;
    border: 1px solid #ccc; border-radius: 4px; }
  .report-warn { color: #c62828; font-size: 12px; }
  .report-fine { color: #888; font-size: 11px; margin-top: 6px; }
  .estimated-tag { font-size: 11px; color: #b26a00; }
  .blaze-chip { display: inline-flex; margin-left: 4px; vertical-align: middle; }
  .blaze-chip.against { opacity: 0.35; }
  .blaze-row { display: flex; align-items: flex-start; gap: 6px; padding: 2px 0; line-height: 1.25; }
  .blaze-row svg { margin-top: 2px; }
  .blaze-marks { font-size: 11px; color: #888; }
  .route-terrain { font-size: 12px; color: #455a64; margin: -4px 0 8px; }
  .terrain-tag { display: inline-flex; margin-left: 6px; vertical-align: middle; }
  .grade-tag { font-size: 10px; font-weight: 700; color: #37474f; margin-left: 6px; white-space: nowrap; }
  .route-ele { font-size: 12px; color: #455a64; margin: -2px 0 8px; }
  .ele-profile { display: block; width: 100%; height: 54px; margin-top: 3px; }
  .ele-range { display: flex; justify-content: space-between; font-size: 10px; color: #90a4ae; }
  .seg-pick { padding: 6px 0 8px; margin-bottom: 8px; border-bottom: 1px solid #eee; font-size: 13px; }
  .route-skipped { font-size: 12px; color: #777; margin: -2px 0 6px; }
  .turn-tag { font-size: 10px; font-weight: 700; color: #0d47a1; text-transform: uppercase; letter-spacing: 0.3px; }
  .rr-link { flex: none; width: 14px; border-top: 3px dashed #0d47a1; margin: 0 3px; }
  .rr-link.passed { border-top-color: #bbb; }
  .route-row .seg-you { margin: 0 1px; }
  .exits { margin-top: 10px; padding-top: 8px; border-top: 1px solid #eee; }
  .exits-head { font-size: 12px; font-weight: 600; color: #555; margin-bottom: 4px; }
  .exit-btn { display: flex; align-items: center; gap: 6px; width: 100%; margin: 4px 0; padding: 6px 8px;
    border: 1px solid #cfd8dc; border-radius: 6px; background: #f7f9fa; cursor: pointer;
    font: inherit; text-align: left; }
  .exit-btn:hover { background: #eaf2f8; }
  a.exit-btn { color: inherit; text-decoration: none; box-sizing: border-box; }
  .drive-row { display: flex; align-items: stretch; gap: 6px; }
  .drive-row .exit-btn { flex: 1; min-width: 0; }
  .share-btn { flex: none; margin: 4px 0; padding: 0 10px; border: 1px solid #dde3e7; border-radius: 6px; background: #f5f7f8;
    color: #37474f; cursor: pointer; display: flex; align-items: center; }
  .exit-dist { font-weight: 600; color: #222; white-space: nowrap; min-width: 38px; text-align: right;
    font-variant-numeric: tabular-nums; flex: none; }
  /* The P centered between the distance and the note, a pixel left for the space after "mi" */
  .park-slot { width: 10px; flex: none; text-align: center; padding-right: 2px; box-sizing: border-box; font-size: 11px; font-weight: 700; color: #1565c0; }
  .exit-chip { display: inline-flex; justify-content: center; min-width: 36px; flex: none; }
  .exit-note { font-size: 11px; color: #666; }

  @media (max-width: 640px) {
    .info-panel { width: calc(100vw - 20px); top: auto; bottom: 0; left: 0;
      border-radius: 12px 12px 0 0; max-height: 45vh; }
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
  <h2>__REGION_NAME__</h2>
  <div class="content" id="infoContent"><div id="welcomeInfo">
    <p style="color:#888">Click a trail or intersection marker for details.</p>
    <p style="margin-top:6px;font-size:12px"><a onclick="showDriveList()" style="cursor:pointer">Directions to an entrance</a> &nbsp;&middot;&nbsp; <a href="location-help.html">Location not working?</a></p>
    <p style="margin-top:8px;color:#888;font-size:11px">__N_INTS__ numbered intersections across __N_ZONES__ zones.<br>
    __N_TRAILS__ trail segments, __N_NAMES__ named trails.</p></div>
  </div>
</div>

<div class="legend-panel">
  <h3 class="legend-head" onclick="toggleLegend()" title="Show or hide the legend">Legend <span class="legend-caret">▾</span></h3>
  <div class="legend-row"><div class="legend-line" style="background:#2c3e50"></div> Trail</div>
  <div class="legend-row"><div class="legend-line" style="background:#00b8d4;height:4px"></div> Trail (highlighted)</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#888"></div> Intersection</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#f1c40f;border-color:#222"></div> Selected</div>
  <div class="legend-row"><div class="entry-diamond legend-diamond"></div> Entry point</div>
  <div class="legend-row"><div class="parking-badge">P</div> Parking</div>
  <div class="legend-row" data-legend="road"><div class="legend-line" style="background:repeating-linear-gradient(90deg,#757575 0 6px,transparent 6px 12px)"></div> Road link</div>
  <div class="legend-row" data-legend="post"><span class="post-badge" style="margin:0 6px 0 1px;cursor:default">1</span> Numbered post</div>
  <div class="legend-row" data-legend="landmark"><span style="margin:0 4px 0 0;display:inline-flex"><svg width="22" height="18" viewBox="0 0 20 16"><path d="M2 14 L1 9 L4 4 L9 2 L14 3 L18 7 L19 12 L17 15 L5 15 Z" fill="#9e9e9e" stroke="#424242" stroke-width="1.3" stroke-linejoin="round"/></svg></span> Landmark</div>
</div>

<script>
// The region this map is for: name, zones, starting view, bounds, and so on (trailmap.py)
var REGION = __REGION_JSON__;
var ZONE_COLORS = {}, ZONE_NAMES = {};
Object.keys(REGION.zones).forEach(function(z) {
  ZONE_COLORS[z] = REGION.zones[z].color;
  ZONE_NAMES[z] = REGION.zones[z].name;
});

var trailData = __TRAIL_DATA__;
var intData = __INT_DATA__;
var trailIntMap = __TRAIL_INT_MAP__;
var intTrailMap = __INT_TRAIL_MAP__;

// Build adjacency graph for routing. Each edge has its true length (dist) and what it
// costs to route along (cost): a trail can carry route_cost, a multiplier that makes
// routing favor the main way over a side trail of about the same length.
var trailRouteCost = {};
trailData.features.forEach(function(f) {
  var c = f.properties.route_cost;
  if (c) trailRouteCost[f.properties.pdf_name || f.properties.name || "Unnamed"] = c;
});
var routeGraph = {};
Object.keys(intTrailMap).forEach(function(label) {
  if (!routeGraph[label]) routeGraph[label] = [];
  (intTrailMap[label] || []).forEach(function(c) {
    if (c[1]) routeGraph[label].push({to: c[1], dist: c[2], cost: c[2] * (trailRouteCost[c[0]] || 1), trail: c[0]});
  });
});

// A priority queue of {node, d}, smallest d first (a binary heap)
function MinQueue() { this.items = []; }
MinQueue.prototype.push = function(item) {
  var a = this.items, i = a.length;
  a.push(item);
  while (i > 0) {
    var up = (i - 1) >> 1;
    if (a[up].d <= a[i].d) break;
    var t = a[up]; a[up] = a[i]; a[i] = t; i = up;
  }
};
MinQueue.prototype.pop = function() {
  var a = this.items, top = a[0], last = a.pop();
  if (a.length) {
    a[0] = last;
    var i = 0;
    for (;;) {
      var l = 2 * i + 1, r = l + 1, m = i;
      if (l < a.length && a[l].d < a[m].d) m = l;
      if (r < a.length && a[r].d < a[m].d) m = r;
      if (m === i) break;
      var t = a[m]; a[m] = a[i]; a[i] = t; i = m;
    }
  }
  return top;
};
MinQueue.prototype.size = function() { return this.items.length; };

// Shortest paths from start to everywhere. The graph never changes, so each start's
// tree is worked out once and kept; a live locate panel asks for the same few often.
// dist is the routing cost (see routeGraph), len the true length along the way.
var pathTrees = {};
function pathTree(start) {
  if (pathTrees[start]) return pathTrees[start];
  var dist = {}, len = {}, prev = {}, via = {}, visited = {};
  Object.keys(routeGraph).forEach(function(n) { dist[n] = Infinity; });
  dist[start] = 0;
  len[start] = 0;
  var queue = new MinQueue();
  queue.push({node: start, d: 0});
  while (queue.size() > 0) {
    var u = queue.pop();
    if (visited[u.node]) continue;
    visited[u.node] = true;
    (routeGraph[u.node] || []).forEach(function(edge) {
      var alt = dist[u.node] + edge.cost;
      if (alt < dist[edge.to]) {
        dist[edge.to] = alt;
        len[edge.to] = len[u.node] + edge.dist;
        prev[edge.to] = u.node;
        via[edge.to] = edge.trail;
        queue.push({node: edge.to, d: alt});
      }
    });
  }
  return (pathTrees[start] = {dist: dist, len: len, prev: prev, via: via});
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
    result = {path: path, totalDist: tree.len[end]};
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

var map = L.map("map", {zoomControl: false}).setView(REGION.view.center, REGION.view.zoom);
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
  style: function(f) {
    // Road links (stretches of road between trails) are dashed
    return f.properties.road ? {color: "#757575", weight: 3, opacity: 0.6, dashArray: "6,6"} : {color: "#2c3e50", weight: 3, opacity: 0.6};
  },
  onEachFeature: function(feature, layer) {
    layer.on("click", function(e) {
      L.DomEvent.stopPropagation(e);
      // On a trail right by an intersection, a finger means the intersection
      if (!tapNearInt(e)) showTrailInfo(feature, layer, e.latlng);
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

var intMarkers = {};
var labelMarkers = {};
var selectedMarker = null;
var selectedRing = null;
var intFeatures = {};
var entryMarkers = {};
map.createPane("entryPane").style.zIndex = 390;

// Numbered posts stand at some intersections. A post with no sign (no_sign) is an
// intersection of its own, labeled "P<n>" inside the code and "Post <n>" on screen.
// Posts look like the real ones: wood, with the number painted yellow
var POST_COLOR = "#9c7a4f", POST_SIZE = 15;

function intName(label) {
  var p = intFeatures[label].properties;
  return p.junction ? "unmarked junction" : p.shape ? shapeName(label) : p.landmark || p.lot || (p.no_sign ? "Post " + p.post : label);
}

// --- Unnumbered intersections (shape: true, as build_saratoga.py makes them): each is a small picture of the trails
// meeting there (junctionIconHtml), named by them: "Main Trail & Sybil"
function shapeName(label) {
  var names = [], p = intFeatures[label].properties;
  (intTrailMap[label] || []).forEach(function(c) {
    if (c[0] && !/^(unnamed|road)\b/i.test(c[0]) && names.indexOf(c[0]) < 0) names.push(c[0]);
  });
  if (!names.length) return p.parking_name || (p.entry ? "Trailhead" : "Trail junction");
  if (names.length === 1) return names[0];
  return names.slice(0, -1).join(", ") + " & " + names[names.length - 1];
}

// A parking lot (lot: its name) that isn't at an intersection and isn't in a zone: no
// sign or number, a routing point for the trail that leads in from it. It shows as a P.
function lotBadgeHtml() { return '<span class="lot-badge">P</span>'; }

// A place in a list of entrances or exits: its pill, or for a lot, just its P, centered
// in a column as wide as the pills so the distances after it line up
function entryChipHtml(label) {
  var p = intFeatures[label].properties;
  return '<span class="exit-chip">' + (p.lot ? lotBadgeHtml() : p.shape ? junctionIconHtml(label, 26)
    : '<span class="int-link" style="background:' + ZONE_COLORS[p.zone] + '">' + label + '</span>') + '</span>';
}

// A fixed-width slot for the P of a place with parking (empty without), so the notes after
// it line up from row to row
function parkSlotHtml(label) {
  return '<span class="park-slot">' + (intFeatures[label].properties.parking ? 'P' : '') + '</span>';
}

// The light note after the distance: where an entrance leads ("from" or "to" it; the
// short form if it has one, connects_short), or a lot's name
function entryNoteHtml(label, word) {
  var p = intFeatures[label].properties, to = p.connects_short || p.connects;
  return p.lot ? '<span class="exit-note">' + esc(p.lot) + '</span>'
    : to ? '<span class="exit-note">' + word + ' ' + esc(to) + '</span>' : '';
}

// Unsigned junctions (junction: true) are where trails meet with no sign: routing points
// only, invisible on the map, and a small grey dot in routes where you change trails
function isJunction(label) { return !!intFeatures[label].properties.junction; }

// A landmark on a trail (Teetering Rock) is a routing point like an intersection, so
// routes along its trail pass through it
function rockSvg(size) {
  return '<svg class="rock-svg" width="' + size + '" height="' + Math.round(size * 0.8) + '" viewBox="0 0 20 16">' +
    '<path d="M2 14 L1 9 L4 4 L9 2 L14 3 L18 7 L19 12 L17 15 L5 15 Z" fill="#9e9e9e" stroke="#424242" stroke-width="1.3" stroke-linejoin="round"/>' +
    '<path d="M5 6 L9 4 L12 5" fill="none" stroke="#e0e0e0" stroke-width="1.2" stroke-linecap="round"/></svg>';
}

// A dot's resting look. Signless points (Post 4, Teetering Rock) hide their dot behind
// their badge or icon; it still shows when selected or hovered.
function restStyle(m) {
  return {radius: 7, weight: 2, color: "#fff", fillColor: ZONE_COLORS[m._zone] || "#1565c0",
          fillOpacity: m._hidden ? 0 : 0.85, opacity: m._hidden ? 0 : 1};
}

// Badge icon anchor for a post on the given compass side (N, NE, ... or null for
// centered): the badge's nearest edge or corner just clears the 8 px dot
var POST_DIRS = {N: [0, -1], NE: [1, -1], E: [1, 0], SE: [1, 1], S: [0, 1], SW: [-1, 1], W: [-1, 0], NW: [-1, -1]};
function postAnchor(dir) {
  var half = POST_SIZE / 2, anchor = [half, half];
  var v = POST_DIRS[dir];
  if (v) {
    var len = Math.hypot(v[0], v[1]), ux = v[0] / len, uy = v[1] / len;
    var reach = 8 + 1 + half * (Math.abs(ux) + Math.abs(uy));
    anchor = [half - ux * reach, half - uy * reach];
  }
  return anchor;
}

function postBadgeHtml(n) {
  return '<span class="post-badge">' + n + '</span>';
}

intData.features.forEach(function(f) {
  var zone = f.properties.zone;
  var label = f.properties.label;
  var ll = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
  var color = ZONE_COLORS[zone];

  if (f.properties.entry && !f.properties.lot) {
    var em = L.marker(ll, {
      pane: "entryPane", interactive: false,
      icon: L.divIcon({className: "", iconSize: [34, 34], iconAnchor: [17, 17],
        html: '<div class="entry-diamond" style="border-color:' + color + '"></div>' +
          (f.properties.parking ? '<div class="parking-badge">P</div>' : '')})
    }).addTo(map);
    em._zone = zone;
    entryMarkers[label] = em;
  }

  var marker = L.circleMarker(ll, {radius: 7, interactive: !f.properties.junction}).addTo(map);
  marker._zone = zone;
  marker._hidden = !!f.properties.no_sign;
  marker.setStyle(restStyle(marker));
  function onTap(e) {
    L.DomEvent.stopPropagation(e);
    if (routeMode) {
      completeRoute(f.properties.label);
    } else {
      showIntInfo(f, marker);
    }
  }
  marker.on("click", onTap);
  marker._onTap = onTap;
  intMarkers[label] = marker;
  intFeatures[label] = f;

  if (f.properties.lot) {
    L.marker(ll, {
      icon: L.divIcon({className: "", html: lotBadgeHtml(), iconSize: [18, 18], iconAnchor: [9, 9]}),
      title: f.properties.lot, keyboard: false
    }).on("click", onTap).addTo(map);
  }

  if (f.properties.landmark) {
    var mark = f.properties.mark ? [f.properties.mark[1], f.properties.mark[0]] : ll;
    L.marker(mark, {
      icon: L.divIcon({className: "", html: rockSvg(22), iconSize: [22, 18], iconAnchor: [11, 9]}),
      title: f.properties.landmark, keyboard: false
    }).on("click", onTap).addTo(map);
  }

  // A post's badge sits against its intersection's dot on the side where the post
  // stands (post_dir), or in place of the dot when there's no sign
  if (f.properties.post) {
    L.marker(ll, {
      icon: L.divIcon({className: "", html: postBadgeHtml(f.properties.post), iconSize: [POST_SIZE, POST_SIZE],
        iconAnchor: postAnchor(f.properties.no_sign ? null : f.properties.post_dir)}),
      title: "Post " + f.properties.post, keyboard: false
    }).on("click", onTap).addTo(map);
  }
  if (f.properties.no_sign || f.properties.shape) return;

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

// Names the map tiles don't show (REGION.placeLabels), once you're close enough to see buildings
var PLACE_LABEL_ZOOM = 17, placeLabels = L.layerGroup();
REGION.placeLabels.forEach(function(p) {
  placeLabels.addLayer(L.marker([p.lat, p.lon], {interactive: false, keyboard: false,
    icon: L.divIcon({className: "place-label", html: '<span>' + esc(p.name) + '</span>', iconSize: [0, 0], iconAnchor: [0, 0]})}));
});
function showPlaceLabels() {
  if (map.getZoom() >= PLACE_LABEL_ZOOM) placeLabels.addTo(map);
  else placeLabels.remove();
}
if (REGION.placeLabels.length) {
  map.on("zoomend", showPlaceLabels);
  showPlaceLabels();
}

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
  marker.setStyle({fillColor: "#f1c40f", radius: 11, weight: 3, color: "#222", fillOpacity: 1, opacity: 1});
  selectedMarker = marker;
  selectedRing = L.circleMarker(marker.getLatLng(), {
    radius: 20, color: "#f1c40f", weight: 2, fillOpacity: 0, opacity: 0.7,
    dashArray: "4,4"
  }).addTo(map);

  var p = feature.properties;
  var pubTag = p.is_public
    ? '<span class="tag tag-public">Public</span>'
    : '<span class="tag tag-private">Private</span>';
  var zoneTag = !ZONE_COLORS[p.zone] ? '' : (REGION.zonesPage ? '<a href="zones.html#zone-' + p.zone + '"' : '<span') + ' class="tag tag-zone" style="background:' +
    ZONE_COLORS[p.zone] + '">' + p.zone + ': ' + ZONE_NAMES[p.zone] + (REGION.zonesPage ? '</a>' : '</span>');
  var ownerHref = p.owner ? 'owners.html#' + ownerSlug(p.owner) : '';

  var html = '<table>' +
    (p.lot
      ? '<tr><td>Parking</td><td>' + lotBadgeHtml() + ' <strong style="font-size:16px;vertical-align:middle">' + esc(p.lot) + '</strong></td></tr>'
      : p.landmark
      ? '<tr><td>Landmark</td><td>' + rockSvg(20) + ' <strong style="font-size:16px;vertical-align:middle">' + esc(p.landmark) + '</strong> ' + zoneTag + '</td></tr>'
      : p.no_sign
      ? '<tr><td>Post</td><td>' + postBadgeHtml(p.post) + ' ' + zoneTag + '<div class="connects-tag">No sign here</div></td></tr>'
      : p.shape
      ? '<tr><td>Junction</td><td><div class="shape-head">' + junctionIconHtml(p.label, 64) + '<div><strong style="font-size:15px">' +
        esc(intName(p.label)) + '</strong><div style="margin-top:4px">' + zoneTag + '</div></div></div></td></tr>'
      : '<tr><td>Label</td><td><strong style="font-size:16px">' + p.label + '</strong> ' + zoneTag + '</td></tr>' +
        (p.post ? '<tr><td>Post</td><td>' + postBadgeHtml(p.post) + '</td></tr>' : '')) +
    (p.ele !== undefined && REGION.eleStep ? '<tr class="full-only"><td>Elevation</td><td>' + feet(p.ele) + '</td></tr>' : '') +
    (p.entry ? '<tr><td>Access</td><td><span class="entry-tag">◆ Entry point</span>' +
      (p.parking ? '<span class="parking-tag">P Parking</span>' : '') +
      (p.connects ? '<div class="connects-tag">Connects to ' + esc(p.connects) + '</div>' : '') +
      '</td></tr>' : '') +
    (p.owner ? '<tr class="full-only"><td>Owner</td><td><a href="' + esc(ownerHref) + '" onmouseover="hoverOwner(' + jsArg(p.owner) + ')" onmouseout="unhover()">' + esc(p.owner) + '</a> ' + pubTag + '</td></tr>' : '') +
    (p.town ? '<tr class="full-only"><td>Town</td><td>' + esc(p.town) + '</td></tr>' : '') +
    // Something to check here on the next walk (checks.html)
    (p.check ? '<tr class="full-only"><td>Field check</td><td><a href="' + esc('checks.html#' + p.label) + '">' + esc(p.check) + '</a></td></tr>' : '') +
    // A conservation restriction on the land (it doesn't change the owner)
    (p.cr ? '<tr class="full-only"><td>Protected</td><td><a href="' + esc('owners.html#' + ownerSlug(p.cr)) + '" onmouseover="hoverOwner(' +
      jsArg(p.cr) + ', ' + jsArg("cr") + ')" onmouseout="unhover()">' + esc(p.cr) + '</a><div class="blaze-marks">held by ' + esc(p.cr_holders) + '</div></td></tr>' : '') +
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
          html += '<div class="int-row">' +
            '<span class="seg-bar" style="padding:0">→</span> ' + intPill(seg.neighbor) +
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

  html += backToRouteBtn();
  if (plan && plan.trip.to !== p.label) {
    html += isPendingStop(p.label)
      ? '<button class="route-btn" style="background:#0d47a1" onclick="removeWaypoint(\'' + p.label + '\')">Remove waypoint</button> '
      : '<button class="route-btn" style="background:#0d47a1" onclick="addWaypoint(\'' + p.label + '\')">Add waypoint</button> ';
  }
  if (userLatLng) {
    html += '<button class="route-btn" style="background:#1e88e5" onclick="routeFromMe(\'' + p.label + '\')">Route here</button>' +
      ' <button class="route-btn" style="background:#1e88e5" onclick="roundTripFromMe(\'' + p.label + '\')">Round trip</button>';
  }
  html += planFromHtml(p.label, 'Route from here');
  html += reportLinkHtml("int", p.label);

  document.getElementById("infoContent").innerHTML = html;
  currentIntFeature = feature;
}

// Planning a route between two intersections. With your location on, routes from where
// you are cover most needs, so this is a small link, in the large view only; without it,
// it's the way to route.
function planFromHtml(label, text) {
  var go = 'onclick="startRoute(\'' + label + '\')"';
  return userLatLng
    ? '<div class="plan-link full-only"><a ' + go + '>' + text + '</a></div>'
    : ' <button class="route-btn" ' + go + '>' + text + '</button>';
}

function startRoute(label) {
  routeFrom = label;
  routeMode = true;
  clearRouteDisplay();
  document.getElementById("infoContent").innerHTML =
    '<div class="route-msg">Routing from <strong>' + intName(label) + '</strong><br>' +
    'Click a destination intersection.<br><br>' +
    '<button class="route-btn" style="background:#888" onclick="cancelRoute()">Cancel</button></div>';
}

function cancelRoute() {
  clearSelection();   // also drops the starting intersection's highlight
  showHome();
}

function removeRouteLayers() {
  if (routeLine) { map.removeLayer(routeLine); routeLine = null; }
  routeMarkers.forEach(function(m) { map.removeLayer(m); });
  routeMarkers = [];
}

function clearRouteDisplay() {
  removeRouteLayers();
  plan = null;
  saveTrip();
}

// The route survives leaving the map (for Checks, or Home) and coming back in this tab,
// like the breadcrumbs: the trip (its stops, and which are done) is kept, and the route
// worked out again from it. A fresh start (you drove away, or a long break) drops it.
var TRIP_KEY = REGION.storagePrefix + "Trip";
var pendingTrip = null;   // a live route to pick up once your location is known
// (and the latest progress is saved as you leave, too)
window.addEventListener("pagehide", function() { if (plan) saveTrip(); });

function saveTrip() {
  try {
    if (plan) {
      sessionStorage.setItem(TRIP_KEY, JSON.stringify(plan.trip, function(k, v) {
        return v instanceof L.LatLng ? {lat: v.lat, lng: v.lng, latLng: true} : v;
      }));
    } else {
      sessionStorage.removeItem(TRIP_KEY);
    }
  } catch (e) {}
}

function savedTrip() {
  try {
    return JSON.parse(sessionStorage.getItem(TRIP_KEY), function(k, v) {
      return v && v.latLng === true ? L.latLng(v.lat, v.lng) : v;
    });
  } catch (e) {
    return null;
  }
}

function completeRoute(destLabel) {
  routeMode = false;
  var startLabel = routeFrom;
  routeFrom = null;
  if (startLabel === destLabel) { cancelRoute(); return; }

  if (dijkstra(startLabel, destLabel)) {
    startTrip(newTrip(startLabel, [], destLabel));
  } else {
    clearSelection();   // so a first GPS fix doesn't reopen the start intersection over this
    document.getElementById("infoContent").innerHTML =
      '<div class="route-msg">No route found from <strong>' + intName(startLabel) + '</strong> to <strong>' + intName(destLabel) + '</strong>.<br><br>' +
      '<button class="route-btn" style="background:#888" onclick="cancelRoute()">Close</button></div>';
  }
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
  if (plan.arrived) return i === plan.steps.length - 1 && plan.trip.to !== null ? "here" : "passed";
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
  plan.hist.steps.forEach(function(s) { if (!isJunction(s.label)) ring(s.label, true); });
  plan.steps.forEach(function(s, i) { if (!isJunction(s.label)) ring(s.label, stepState(i) === "passed"); });
  if (plan.trip.to === null) {
    routeMarkers.push(L.circleMarker(plan.trip.home, {
      radius: 6, color: "#0d47a1", weight: 3, fillColor: "#fff", fillOpacity: 1, interactive: false
    }).addTo(map));
  }
}

// Trimming is in pixels, so it has to be redone at each zoom level
map.on("zoomend", function() { if (plan) drawRoute(); });

// --- Turn icons: a small picture of a route step's intersection, the trails within
// TURN_R_M of it as they lie, turned so you arrive from the bottom, with your way through
// in bold ending in an arrow. An unsigned junction just ahead is taken into the picture,
// so a jog (right, then left a few steps on) reads as one turn.
var TURN_R_M = 30, TURN_MAX_R_M = 60, TURN_HALF_PX = 14;
var turnClipId = 0;

function routePointAt(s) {
  var segs = plan.segs;
  for (var k = 0; k < segs.length; k++) {
    if (s <= segs[k].s0 + segLen(segs[k]) || k === segs.length - 1) return segPointAt(segs[k], s - segs[k].s0);
  }
  return null;
}

function routeLineBetween(a, b) {
  var pts = [];
  plan.segs.forEach(function(seg) { var p = segPiece(seg, a, b); if (p) pts = pts.concat(p); });
  return pts;
}

// Drawn once per route; each copy on the page gets its own clip id (an icon can be in
// both views, and a clip in the hidden one doesn't work everywhere)
function turnIconHtml(i) {
  plan.turnIcons = plan.turnIcons || {};
  if (plan.turnIcons[i] === undefined) plan.turnIcons[i] = turnIconSvg(i);
  return plan.turnIcons[i].replace(/CLIP_ID/g, 'turn-clip-' + (turnClipId++));
}

// Turning back (an out and back's turnaround): the way you came, so a plain U-turn sign
var U_TURN_SVG = '<svg class="turn-icon" width="' + 2 * TURN_HALF_PX + '" height="' + 2 * TURN_HALF_PX + '" viewBox="' +
  -TURN_HALF_PX + ' ' + -TURN_HALF_PX + ' ' + 2 * TURN_HALF_PX + ' ' + 2 * TURN_HALF_PX + '">' +
  '<circle r="' + (TURN_HALF_PX - 0.5) + '" fill="#f4f6f7" stroke="#cfd8dc"/>' +
  '<path d="M4.5 10V-2A4.75 4.75 0 0 0-5-2V3" fill="none" stroke="#0d47a1" stroke-width="2.6" stroke-linecap="round"/>' +
  '<path d="M-5 8.5L-8.6 2.6H-1.4Z" fill="#0d47a1"/></svg>';

function isUTurn(i) {
  var prev = plan.steps[i - 1], next = plan.steps[i + 1];
  return !!(prev && next && next.label === prev.label && next.trail === plan.steps[i].trail);
}

function turnIconSvg(i) {
  var step = plan.steps[i], at = step.at;
  if (!step.nextTrail || !plan.segs.length) return '';
  if (isUTurn(i)) return U_TURN_SVG;
  var c = intMarkers[step.label].getLatLng();
  var r = TURN_R_M;
  for (var j = i + 1; j < plan.steps.length && isJunction(plan.steps[j].label) && plan.steps[j].at - at <= TURN_MAX_R_M - 20; j++) {
    r = Math.max(r, plan.steps[j].at - at + 20);
  }
  // Facing the way you arrive (at the start, the way you leave), in meters from c
  function local(ll) { return [(ll.lng - c.lng) * 82000, (ll.lat - c.lat) * 111000]; }
  var p0 = local(routePointAt(Math.max(at - 15, 0))), p1 = local(routePointAt(at > 1 ? at : at + 15));
  var h = at > 1 ? Math.atan2(-p0[0], -p0[1]) : Math.atan2(p1[0], p1[1]);
  var cos = Math.cos(h), sin = Math.sin(h), k = (TURN_HALF_PX - 1) / r;
  function xy(m) {
    return [(m[0] * cos - m[1] * sin) * k, -(m[0] * sin + m[1] * cos) * k];
  }
  function pathD(pts) {
    return pts.map(function(p, n) { return (n ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1); }).join('');
  }
  // The trails near it, each the runs of its points within reach (the circle clips them)
  var others = '';
  trailData.features.forEach(function(f) {
    var m = flatCoords(f.geometry).map(function(q) { return local(L.latLng(q[1], q[0])); });
    var near = m.map(function(q) { return Math.abs(q[0]) < 2 * r && Math.abs(q[1]) < 2 * r; });
    var run = [];
    for (var n = 0; n <= m.length; n++) {
      if (n < m.length && (near[n] || near[n - 1] || near[n + 1])) {
        run.push(xy(m[n]));
      } else {
        if (run.length > 1) others += pathD(run);
        run = [];
      }
    }
  });
  // Your way through: in from beyond the edge, out to an arrowhead near it. The arrow
  // ends where the route gets that far from the middle, however it wiggles on the way (a
  // marker a few meters off the trails' meeting point has the route double back to it),
  // but no farther along it than 1.5 r, so a route that turns back stays readable.
  var way = routeLineBetween(Math.max(at - 2 * r, 0), at).map(function(ll) { return xy(local(ll)); });
  var out = routeLineBetween(at, at + 1.5 * r).map(function(ll) { return xy(local(ll)); });
  var reach = 0.8 * (TURN_HALF_PX - 1);
  for (var o = 1; o < out.length; o++) {
    var d0 = Math.hypot(out[o - 1][0], out[o - 1][1]), d1 = Math.hypot(out[o][0], out[o][1]);
    if (d1 >= reach) {
      var f = d1 > d0 ? (reach - d0) / (d1 - d0) : 1;
      out = out.slice(0, o).concat([[out[o - 1][0] + f * (out[o][0] - out[o - 1][0]), out[o - 1][1] + f * (out[o][1] - out[o - 1][1])]]);
      break;
    }
  }
  way = way.concat(out);
  var tip = way[way.length - 1], back = tip;
  for (var b = way.length - 2; b >= 0; b--) {
    back = way[b];
    if (Math.hypot(tip[0] - back[0], tip[1] - back[1]) >= 4) break;
  }
  var dx = tip[0] - back[0], dy = tip[1] - back[1], len = Math.hypot(dx, dy) || 1;
  dx /= len; dy /= len;
  var head = [[tip[0] + dx * 2, tip[1] + dy * 2], [tip[0] - dx * 3 - dy * 3.2, tip[1] - dy * 3 + dx * 3.2],
              [tip[0] - dx * 3 + dy * 3.2, tip[1] - dy * 3 - dx * 3.2]];
  var id = 'CLIP_ID', w = 2 * TURN_HALF_PX;
  return '<svg class="turn-icon" width="' + w + '" height="' + w + '" viewBox="' + -TURN_HALF_PX + ' ' + -TURN_HALF_PX + ' ' + w + ' ' + w + '">' +
    '<defs><clipPath id="' + id + '"><circle r="' + (TURN_HALF_PX - 1) + '"/></clipPath></defs>' +
    '<circle r="' + (TURN_HALF_PX - 0.5) + '" fill="#f4f6f7" stroke="#cfd8dc"/>' +
    '<g clip-path="url(#' + id + ')" fill="none" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="' + others + '" stroke="#9aa5ab" stroke-width="2"/>' +
    '<path d="' + pathD(way) + '" stroke="#0d47a1" stroke-width="2.6"/></g>' +
    '<path d="' + pathD(head) + 'Z" fill="#0d47a1"/></svg>';
}

// An unnumbered intersection's picture: the trails within SHAPE_R_M of it, north up, each
// in its blaze's color (grey if it has none), no arrow. Drawn once, at px across.
var SHAPE_R_M = 30, shapeIcons = {};

function junctionIconHtml(label, px) {
  if (shapeIcons[label] === undefined) shapeIcons[label] = junctionIconSvg(label);
  return shapeIcons[label].replace(/SIZE/g, px).replace(/CLIP_ID/g, 'turn-clip-' + (turnClipId++));
}

function junctionIconSvg(label) {
  var c = intMarkers[label].getLatLng(), r = SHAPE_R_M, k = (TURN_HALF_PX - 1) / r;
  function xy(lng, lat) { return [(lng - c.lng) * 82000 * k, -(lat - c.lat) * 111000 * k]; }
  var grey = '', colored = '';
  trailData.features.forEach(function(f, ti) {
    var pts = flatCoords(f.geometry), run = [];
    function flush() {
      if (run.length > 1) {
        var mid = run[Math.floor(run.length / 2)], at = trailCum[ti][mid.i];
        var on = blazesOn(ti, Math.max(at - 5, 0), at + 5);
        var d = run.map(function(q, n) { return (n ? 'L' : 'M') + q.x.toFixed(1) + ' ' + q.y.toFixed(1); }).join('');
        if (on.length) {
          colored += '<path d="' + d + '" stroke="' + REGION.blazes[on[0].key].color + '" stroke-width="3"/>';
          if (on.length > 1) colored += '<path d="' + d + '" stroke="' + REGION.blazes[on[1].key].color + '" stroke-width="3" stroke-dasharray="3,3"/>';
        } else {
          grey += '<path d="' + d + '" stroke="' + (f.properties.road ? "#b0bec5" : "#78909c") + '" stroke-width="2.2"/>';
        }
      }
      run = [];
    }
    for (var i = 0; i < pts.length; i++) {
      var dx = (pts[i][0] - c.lng) * 82000, dy = (pts[i][1] - c.lat) * 111000;
      var near = Math.abs(dx) < 2 * r && Math.abs(dy) < 2 * r;
      var nextNear = i + 1 < pts.length && Math.abs((pts[i + 1][0] - c.lng) * 82000) < 2 * r && Math.abs((pts[i + 1][1] - c.lat) * 111000) < 2 * r;
      var prevNear = i > 0 && Math.abs((pts[i - 1][0] - c.lng) * 82000) < 2 * r && Math.abs((pts[i - 1][1] - c.lat) * 111000) < 2 * r;
      if (near || nextNear || prevNear) {
        var q = xy(pts[i][0], pts[i][1]);
        run.push({x: q[0], y: q[1], i: i});
      } else {
        flush();
      }
    }
    flush();
  });
  var h = TURN_HALF_PX;
  return '<svg class="turn-icon" width="SIZE" height="SIZE" viewBox="' + -h + ' ' + -h + ' ' + 2 * h + ' ' + 2 * h + '">' +
    '<defs><clipPath id="CLIP_ID"><circle r="' + (h - 1) + '"/></clipPath></defs>' +
    '<circle r="' + (h - 0.5) + '" fill="#f4f6f7" stroke="#cfd8dc"/>' +
    '<g clip-path="url(#CLIP_ID)" fill="none" stroke-linecap="round" stroke-linejoin="round">' + grey + colored + '</g>' +
    '<circle r="1.8" fill="#263238"/></svg>';
}

// ft (optional): distance to the next step shown, if quiet steps are skipped in between;
// icon (optional): its turn icon, in place of the arrow
function stepRowHtml(step, state, ft, icon) {
  var html = '<div class="route-step' + (state === "passed" ? ' passed' : '') + '">' +
    (state === "here" ? '<span class="you-badge">You</span>' : '') +
    // The pill (or a signless place's icon, unnamed: it says what it is when tapped)
    // centered in a column, so what follows lines up from row to row
    '<span class="exit-chip">' + pillIcon(step.label, state) + '</span>';
  if (step.nextTrail) {
    html += (icon || '<span class="route-arrow">→</span>') +
      '<span class="route-trail-name">' + esc(step.nextTrail) + '</span>' + blazeChipsHtml(step.nextBlazes || []) +
      '<span class="int-dist">' + formatDist((ft === undefined ? step.nextFt : ft) / 3.28084) + '</span>' +
      // Rough legs are flagged (the route's terrain summary says what the bars mean)
      (step.nextTerrain >= 2 ? '<span class="terrain-tag" title="' + esc(REGION.terrain[step.nextTerrain]) + ' terrain">' +
        terrainSvg(step.nextTerrain) + '</span>' : '') + gradeTagHtml(step.nextClimb);
  }
  var stop = step.segStart || (step.stop && !step.stop.edge ? step.stop : null);
  if (stop) html += '<span class="turn-tag">' + (isTurnaround(stop) ? 'turn around' : 'waypoint') + '</span>';
  return html + '</div>';
}

// An unsigned junction where the route stays on the same trail: nothing to look for or
// do there, so routes don't show it
function quietStep(step) {
  return isJunction(step.label) && !!step.nextTrail && step.trail === step.nextTrail && !step.stop && !step.segStart;
}

// Each step's distance to the next step that's shown, adding up quiet steps between
function shownFt(steps) {
  var ft = steps.map(function(s) { return s.nextFt; });
  for (var i = steps.length - 2; i >= 0; i--) {
    if (quietStep(steps[i + 1])) ft[i] += ft[i + 1];
  }
  return ft;
}

// A round trip to one intersection turns around there
function isTurnaround(stop) {
  var trip = plan.trip;
  return trip.to === null && trip.stops.length === 1 && !stop.edge;
}

// How a stop reads in titles: "A12", or "Challenger (C13–C34)" for a trail segment
function stopName(stop) {
  return stop.edge ? esc(stop.edge.trail) + ' (' + intName(stop.edge.a) + '–' + intName(stop.edge.b) + ')' : intName(stop.label);
}

function routePanelHtml() {
  var trip = plan.trip;
  var states = plan.steps.map(function(s, i) { return stepState(i); });
  // You are either at a step ("here") or on the way to the first step still ahead
  var youBefore = -1;
  if (plan.live && !plan.arrived && states.indexOf("here") < 0) youBefore = states.indexOf("ahead");
  var toGo = plan.live ? Math.max(plan.total - plan.progress, 0) : plan.graphDist;
  var toGoStr = formatDist(toGo);
  var dest = trip.to;
  // A round trip ends where it began: at that intersection, if it began at one
  var homePill = trip.homeLabel ? intPill(trip.homeLabel) : END_CHIP;
  var destHtml = dest === null ? homePill : intPill(dest);
  var arrivedHtml = dest === null
    ? (trip.homeLabel ? "You're back at " + homePill : "You're back where you started")
    : "You've arrived at " + intPill(dest);
  // ...and the route's last pill is already that intersection, so no End chip after it
  var endChip = dest === null && !(trip.homeLabel && plan.steps[plan.steps.length - 1].label === trip.homeLabel);
  var live = plan.live && !plan.arrived ? ' <span class="live-tag">LIVE</span>' : '';
  // On a live route, also how far to the next pill and its turn; at a pill, its turn
  var nextAt = -1, hereAt = -1;
  if (plan.live && !plan.arrived) {
    plan.steps.forEach(function(s, i) {
      if (!quietStep(s)) {
        if (states[i] === "here" && hereAt < 0) hereAt = i;
        if (states[i] === "ahead" && nextAt < 0) nextAt = i;
      }
    });
  }
  var next = nextAt >= 0 ? plan.steps[nextAt] : null;
  // "0.4 mi to A12 · 160 ft to A2 (turn)", or "0.4 mi to A12 · at A2 (turn)". A function:
  // the line is in both views, and each copy of a turn icon needs its own id.
  var distLine = function() {
    var html = '<span class="route-next"><strong>' + toGoStr + '</strong> to ' + destHtml + '</span>';
    if (hereAt >= 0 && turnIconHtml(hereAt)) {
      html += ' <span class="route-next">· at ' + intPill(plan.steps[hereAt].label) + turnIconHtml(hereAt) + '</span>';
    } else if (next && next.label !== dest) {
      html += ' <span class="route-next">· <strong>' + formatDist(next.at - plan.progress) + '</strong> to ' +
        intPill(next.label) + turnIconHtml(nextAt) + '</span>';
    }
    return html;
  };

  // Small view: one row of pills
  var row = '';
  var link = function(past) { return '<span class="rr-link' + (past ? ' passed' : '') + '"></span>'; };
  plan.hist.steps.forEach(function(s) {
    if (!quietStep(s)) row += (row ? link(true) : '') + intPill(s.label, "passed");
  });
  plan.steps.forEach(function(s, i) {
    if (i === youBefore) row += (row ? link(true) : '') + '<span class="seg-you rr-you"></span>';
    if (!quietStep(s)) row += (row ? link(states[i] !== "ahead") : '') + intPill(s.label, states[i]);
  });
  if (endChip) row += link(plan.arrived) + homePill;
  var small = '<div class="compact-only">' +
    '<div class="route-compact-head">' + (plan.arrived
      ? arrivedHtml
      : distLine() + live) +
    '</div><div class="route-row">' + row + '</div></div>';

  // Large view: the step list
  // Stops in the order the route reaches them
  var inOrder = [];
  plan.hist.steps.concat(plan.steps).forEach(function(st) { if (st.stop && inOrder.indexOf(st.stop) < 0) inOrder.push(st.stop); });
  trip.stops.forEach(function(s) { if (!s.skipped && inOrder.indexOf(s) < 0) inOrder.push(s); });
  var names = inOrder.filter(function(s) { return !s.skipped; }).map(stopName);
  var title = dest === null
    ? (names.length === 1 ? 'Round trip: out to ' + names[0] + ' and back' : 'Round trip via ' + names.join(', '))
    : 'Route: ' + (plan.live ? 'Your location' : intName(trip.from)) + ' → ' + intName(dest) + (names.length ? ' via ' + names.join(', ') : '');
  var html = '<div class="route-title"><strong style="font-size:14px">' + (plan.arrived ? arrivedHtml : title) + '</strong>' + live + '</div>';
  var skipped = trip.stops.filter(function(s) { return s.skipped; });
  if (skipped.length) {
    html += '<div class="route-skipped">Skipped ' + skipped.map(function(s) { return s.edge ? stopName(s) : intPill(s.label, "passed"); }).join(', ') + '</div>';
  }
  if (!plan.arrived) {
    html += '<div style="font-size:13px;margin-bottom:8px">' + distLine() + '</div>' + routeTerrainHtml() + routeEleHtml();
  }
  html += '<div class="int-list">';
  var histFt = shownFt(plan.hist.steps), stepFt = shownFt(plan.steps);
  plan.hist.steps.forEach(function(s, i) { if (!quietStep(s)) html += stepRowHtml(s, "passed", histFt[i]); });
  plan.steps.forEach(function(s, i) {
    if (i === youBefore) {
      var trail = i === 0 ? plan.legTrail : s.trail;
      var upTo = plan.steps.filter(function(t, j) { return j >= i && !quietStep(t); })[0] || s;
      html += '<div class="route-step"><span class="you-badge">You</span>' +
        '<span class="route-arrow">→</span>' +
        '<span class="route-trail-name">' + esc(trail) + '</span>' +
        '<span class="int-dist">' + formatDist(upTo.at - plan.progress) + '</span></div>';
    }
    if (!quietStep(s)) html += stepRowHtml(s, states[i], stepFt[i], turnIconHtml(i));
  });
  if (endChip) html += '<div class="route-step">' + homePill + '</div>';
  html += '</div>';
  // Planning links go under the buttons; without your location they're buttons, before Clear
  var planning = (plan.live ? '' : planFromHtml(trip.from, 'New route from ' + intName(trip.from))) +
    (dest !== null ? planFromHtml(dest, 'New route from ' + intName(dest)) : '');
  html += '<div style="margin-top:10px">' + (userLatLng ? '' : planning) +
    (canReverseLoop() ? ' <button class="route-btn" onclick="reverseLoopNow()">Reverse loop</button>' : '') +
    ' <button class="route-btn" style="background:#888" onclick="cancelRoute()">Clear</button></div>' +
    (userLatLng ? planning : '');

  return '<div id="routeInfo">' + small + '<div class="full-only">' + html + '</div></div>';
}

var END_CHIP = '<span class="start-chip">End</span>';

function showRoutePanel() {
  document.getElementById("infoContent").innerHTML = routePanelHtml();
  // Keep where you are in view in the pill row
  var rowEl = document.querySelector("#routeInfo .route-row");
  var you = rowEl && rowEl.querySelector(".rr-you, .int-link.here");
  if (you) rowEl.scrollLeft = Math.max(0, you.offsetLeft - rowEl.clientWidth / 3);
}

// Every route is a trip: from your location (from null) or an intersection, through
// stops (waypoints, which can be added along the way), to an intersection, or back
// where you started (to null) for a round trip:
//   {from, stops: [stop], to, home, homeAnchors, homeLabel, origin}
// A stop is an intersection {label} or a stretch of trail between two neighboring
// intersections {edge: {a, b, trail}}, walked whichever way suits; each has done and
// skipped. Stops are kept in the order that makes the shortest trip (optimizeStops).
// origin is where the trip began; homeLabel, the intersection a round trip began at, if any.
function newTrip(from, stopLabels, to) {
  var here = userLatLng && L.latLng(userLatLng.lat, userLatLng.lng);
  var at = to === null ? nearestInt(here) : null;
  return {from: from, to: to, homeLabel: at && at.dist <= AT_INT_M ? at.label : null,
          stops: stopLabels.map(function(l) { return {label: l, done: false, skipped: false}; }),
          home: to === null ? here : null, homeAnchors: to === null ? userAnchors(here) : null,
          origin: from === null ? here : intMarkers[from].getLatLng()};
}

function pendingStops(trip) { return trip.stops.filter(function(s) { return !s.done; }); }

// The edges a path uses, both ways, as keys for pathToAnchors' avoid
function edgeSet(path) {
  var set = {};
  for (var k = 1; k < path.length; k++) {
    set[path[k - 1].label + "|" + path[k].label + "|" + path[k].trail] = true;
    set[path[k].label + "|" + path[k - 1].label + "|" + path[k].trail] = true;
  }
  return set;
}

// Length of a segment stop's trail, along its chain of intersections
function edgeLen(edge) {
  var len = 0;
  for (var k = 1; k < edge.chain.length; k++) {
    var piece = Infinity;
    (intTrailMap[edge.chain[k - 1]] || []).forEach(function(c) { if (c[0] === edge.trail && c[1] === edge.chain[k]) piece = c[2]; });
    len += piece;
  }
  return len;
}

// A stop's ways in: [entry, exit, chain walked] ; a segment can be walked either way
function stopWays(stop) {
  return stop.edge
    ? [[stop.edge.a, stop.edge.b, stop.edge.chain], [stop.edge.b, stop.edge.a, stop.edge.chain.slice().reverse()]]
    : [[stop.label, stop.label, null]];
}

// The shortest trip through stops in this order: {cost, ways}, where ways picks each
// stop's way in. Distances are plain trail distances, remembered in memo.
function planStops(trip, stops, memo) {
  var dist = function(a, b) {
    var key = a + "|" + b;
    if (!(key in memo)) memo[key] = tripLegDist(trip, a, b);
    return memo[key];
  };
  var states = [{exit: trip.from, cost: 0, ways: []}];
  stops.forEach(function(st) {
    states = stopWays(st).map(function(way, wi) {
      var best = null;
      states.forEach(function(s) {
        var c = s.cost + dist(s.exit, way[0]) + (st.edge ? edgeLen(st.edge) : 0);
        if (!best || c < best.cost) best = {exit: way[1], cost: c, ways: s.ways.concat([wi])};
      });
      return best;
    });
  });
  var end = trip.to === null ? "home" : trip.to, best = null;
  states.forEach(function(s) {
    var c = s.cost + dist(s.exit, end);
    if (!best || c < best.cost) best = {cost: c, ways: s.ways};
  });
  return best;
}

// Put the stops still ahead in the order that makes the shortest trip: every order for a
// few stops, or adding them one at a time where each fits best for more
function optimizeStops(trip) {
  var pending = pendingStops(trip), memo = {}, best = null;
  var tryOrder = function(order) {
    var c = planStops(trip, order, memo).cost;
    if (!best || c < best.cost) best = {cost: c, order: order};
  };
  var permute = function(done, rest) {
    if (!rest.length) tryOrder(done);
    rest.forEach(function(s, i) { permute(done.concat([s]), rest.slice(0, i).concat(rest.slice(i + 1))); });
  };
  if (pending.length <= 6) {
    permute([], pending);
  } else {
    var order = [];
    pending.forEach(function(s) {
      best = null;
      for (var k = 0; k <= order.length; k++) tryOrder(order.slice(0, k).concat([s], order.slice(k)));
      order = best.order;
    });
  }
  if (best) trip.stops = trip.stops.filter(function(s) { return s.done; }).concat(best.order);
}

// The route for what's left of a trip, from where you are (or the trip's start). Returns
// {start, result: {path, totalDist}, userLeg, info: {trip, tail, stopAt}} or null.
// stopAt maps a path index to its stop. Each leg after a stop avoids the trails the
// previous leg arrived on, so a route goes through a waypoint instead of touching it and
// turning back (unless it's a dead end). A round trip's way home avoids the trails used
// on the way out (they cost LOOP_REUSE_COST times their length), if that's at most
// LOOP_BACK_RATIO times as long as retracing your steps.
// A route that passes an intersection stop on the way to another counts it there, rather
// than coming back to it later.
function compileTrip(trip) {
  var passed = [], args = buildTrip(trip, passed), more = !!args;
  while (more) {
    var early = pendingStops(trip).filter(function(st) {
      return !st.edge && passed.indexOf(st) < 0 && firstAt(args.result.path, st.label) < stopIndex(args, st);
    })[0];
    var next = early && buildTrip(trip, passed.concat([early]));
    more = !!next && firstAt(next.result.path, early.label) >= 0;
    if (more) { passed.push(early); args = next; }
  }
  if (args) {
    passed.forEach(function(st) { args.info.stopAt[firstAt(args.result.path, st.label)] = st; });
  }
  return args;
}

function firstAt(path, label) {
  for (var i = 0; i < path.length; i++) if (path[i].label === label) return i;
  return -1;
}

function stopIndex(args, stop) {
  var found = -1;
  Object.keys(args.info.stopAt).forEach(function(k) { if (args.info.stopAt[k] === stop) found = +k; });
  return found;
}

// compileTrip's route, leaving out the stops in passed
function buildTrip(trip, passed) {
  var targets = pendingStops(trip).filter(function(st) { return passed.indexOf(st) < 0; });
  var ways = targets.length ? planStops(trip, targets, {}).ways : [];
  // Places to go in turn; a segment is its entry, then its exit along the segment's trail
  var seq = [];
  targets.forEach(function(st, i) {
    var way = stopWays(st)[ways[i]];
    if (st.edge) seq.push({label: way[0], stop: null}, {label: way[1], along: st.edge.trail, chain: way[2], stop: st});
    else seq.push({label: st.label, stop: st});
  });
  if (trip.to !== null) seq.push({label: trip.to, stop: null});
  var path, dist = 0, userLeg = null, stopAt = {}, ok = true, tail = null, homeOnly = false;
  if (trip.from !== null) {
    path = [{label: trip.from, trail: null}];
  } else if (seq.length) {
    var lead = bestRouteFromMe(seq[0].label);
    ok = !!lead;
    if (ok) { path = lead.result.path.slice(); dist = lead.result.totalDist; userLeg = lead.anchor; }
  } else {
    // A round trip with every stop behind you: straight home
    var best = null;
    userAnchors(userLatLng).forEach(function(a) {
      var r = pathToAnchors(a.label, trip.homeAnchors, {});
      if (r && (!best || a.dist + r.len < best.total)) best = {a: a, r: r, total: a.dist + r.len};
    });
    ok = !!best;
    homeOnly = true;
    if (ok) { path = best.r.path; dist = best.r.len - best.r.anchor.dist; userLeg = best.a; tail = best.r.anchor; }
  }
  if (ok && trip.from === null && seq.length && seq[0].stop) stopAt[path.length - 1] = seq[0].stop;
  var legStart = 0;
  for (var i = trip.from !== null ? 0 : 1; ok && i < seq.length; i++) {
    if (seq[i].along) {
      legStart = path.length - 1;
      seq[i].chain.slice(1).forEach(function(l) { path.push({label: l, trail: seq[i].along}); });
      dist += edgeLen(seq[i].stop.edge);
    } else {
      var r = pathToAnchors(path[path.length - 1].label, [{label: seq[i].label, dist: 0}], edgeSet(path.slice(legStart)));
      ok = !!r;
      if (ok) { legStart = path.length - 1; path = path.concat(r.path.slice(1)); dist += r.len; }
    }
    if (ok && seq[i].stop) stopAt[path.length - 1] = seq[i].stop;
  }
  if (ok && trip.to === null && !homeOnly) {
    var last = path[path.length - 1].label;
    var same = pathToAnchors(last, trip.homeAnchors, {}), other = pathToAnchors(last, trip.homeAnchors, edgeSet(path));
    var back = other && same && other.len <= LOOP_BACK_RATIO * same.len ? other : same;
    ok = !!back;
    if (ok) { path = path.concat(back.path.slice(1)); dist += back.len - back.anchor.dist; tail = back.anchor; }
  }
  return ok ? {start: path[0].label, result: {path: path, totalDist: dist}, userLeg: userLeg,
               info: {trip: trip, tail: tail, stopAt: stopAt}} : null;
}

// userLeg (optional): {dist, trail, ti, along, cum} for the walk from the user's position to
// the first intersection (ti/along: where the user snaps onto that trail, if on one).
// A route with a userLeg is live: progress along it is tracked as the user moves.
// noFit keeps the view. hist: {steps, segs} already walked before a reroute; with hist the
// panel and any selection are left alone, and the caller redraws.
// info: {trip, tail, stopAt} from compileTrip; a round trip ends with a walk from the tail
// anchor back home.
function renderRoute(result, userLeg, noFit, hist, info) {
  if (!hist) clearSelection();
  clearRouteDisplay();

  var trip = info.trip, path = result.path;
  var segs = [];
  if (userLeg) {
    var legPts = [userLatLng];
    if (userLeg.ti !== undefined) {
      legPts = legPts.concat(sliceTrail(userLeg.ti, userLeg.along, userLeg.cum));
    }
    legPts.push(intMarkers[path[0].label].getLatLng());
    segs.push({pts: legPts, trimStart: false, trimEnd: !isJunction(path[0].label)});
  }
  for (var k = 0; k < path.length - 1; k++) {
    var u = path[k].label, v = path[k + 1].label;
    var e = routeEdge(u, v, path[k + 1].trail);
    var pts = e ? sliceTrail(e.ti, e.a, e.b) : [];
    pts.unshift(intMarkers[u].getLatLng());
    pts.push(intMarkers[v].getLatLng());
    // Stop short only where there's a ring (junctions have none)
    segs.push({pts: pts, trimStart: !isJunction(u), trimEnd: !isJunction(v)});
  }
  if (info.tail) {
    var tail = info.tail, tailPts = [intMarkers[tail.label].getLatLng()];
    if (tail.ti !== undefined) tailPts = tailPts.concat(sliceTrail(tail.ti, tail.cum, tail.along));
    tailPts.push(trip.home);
    segs.push({pts: tailPts, trimStart: !isJunction(tail.label), trimEnd: false});
  }
  // Lay the pieces end to end so every point has a position along the route
  var s = 0;
  segs.forEach(function(seg) { seg.cum = lineCum(seg.pts); seg.s0 = s; s += segLen(seg); });

  var segStartAt = {};
  Object.keys(info.stopAt).forEach(function(idx) {
    var st = info.stopAt[idx];
    if (st.edge) segStartAt[idx - (st.edge.chain.length - 1)] = st;
  });
  var steps = path.map(function(step, i) {
    var k = userLeg ? i : i - 1;
    var next = path[i + 1], nextFt = 0;
    if (next) {
      (intTrailMap[step.label] || []).forEach(function(c) {
        if (c[0] === next.trail && c[1] === next.label) nextFt = c[2] * 3.28084;
      });
    }
    var edge = next && routeEdge(step.label, next.label, next.trail);
    return {label: step.label, trail: step.trail, nextTrail: next ? next.trail : null, nextFt: nextFt,
            nextBlazes: edge ? blazesOn(edge.ti, edge.a, edge.b) : [],
            nextTerrain: edge ? terrainOn(edge.ti, edge.a, edge.b) : null,
            nextClimb: edge && REGION.eleStep ? climbStats(eleProfile(edge.ti, edge.a, edge.b)) : null,
            at: k < 0 ? 0 : segs[k].s0 + segLen(segs[k]), stop: info.stopAt[i] || null,
            segStart: segStartAt[i] || null};
  });

  plan = {trip: trip, live: !!userLeg, segs: segs, steps: steps, total: s,
          graphDist: result.totalDist, progress: userLeg ? 0 : null, arrived: false,
          legTrail: userLeg ? (userLeg.trail || 'off trail') : null,
          hist: hist || {steps: [], segs: []}};
  saveTrip();
  if (hist) return;
  drawRoute();

  if (!noFit) {
    setFollowing(false);   // show the whole route; tap locate to follow again
    var allPts = [].concat.apply([], segs.map(function(seg) { return seg.pts; }));
    map.fitBounds(L.latLngBounds(allPts).pad(0.1));
  }
  showRoutePanel();
}

// Start a trip and show it, or say why there's no route
function startTrip(trip, failMsg) {
  var args = compileTrip(trip);
  if (args) renderRoute(args.result, args.userLeg, false, null, args.info);
  else showPanelMsg(failMsg);
}

var LOOP_REUSE_COST = 4, LOOP_BACK_RATIO = 1.2;
var LOOP_REVERSE_M = 100;   // a jump this far ahead onto the way back means you went the other way
var BACKWARD_M = 10;        // ...once you've walked this far back along it (see trackProgress)
var BACKWARD_FIXES = 6;     // fixes to wait for that before treating it as leaving the route
var SKIP_MARGIN_M = 50;     // see skipMissedStops

// Shortest path from an intersection to the nearest of some anchors ({label, dist, ...}),
// with the edges in avoid costing more. Returns {path, len, anchor}; len is in true meters
// and includes the anchor's dist.
function pathToAnchors(start, anchors, avoid) {
  var cost = {}, len = {}, prev = {}, via = {}, done = {}, queue = new MinQueue();
  cost[start] = 0;
  len[start] = 0;
  queue.push({node: start, d: 0});
  while (queue.size()) {
    var u = queue.pop().node;
    if (!done[u]) {
      done[u] = true;
      (routeGraph[u] || []).forEach(function(e) {
        var c = cost[u] + e.cost * (avoid[u + "|" + e.to + "|" + e.trail] ? LOOP_REUSE_COST : 1);
        if (!(cost[e.to] <= c)) {
          cost[e.to] = c; len[e.to] = len[u] + e.dist; prev[e.to] = u; via[e.to] = e.trail;
          queue.push({node: e.to, d: c});
        }
      });
    }
  }
  var best = null;
  anchors.forEach(function(a) {
    if (cost[a.label] !== undefined && (!best || cost[a.label] + a.dist < best.cost)) best = {cost: cost[a.label] + a.dist, anchor: a};
  });
  var result = null;
  if (best) {
    var path = [], n = best.anchor.label;
    while (n !== undefined) { path.unshift({label: n, trail: via[n] || null}); n = prev[n]; }
    result = {path: path, len: len[best.anchor.label] + best.anchor.dist, anchor: best.anchor};
  }
  return result;
}

function roundTripFromMe(label) {
  if (awayFromTrails()) {
    pickEntrance(label, true);
  } else if (userLatLng.distanceTo(intMarkers[label].getLatLng()) <= AT_INT_M) {
    showPanelMsg('You are already at ' + intPill(label));
  } else {
    startTrip(newTrip(null, [label], null), 'No round trip found from your location to <strong>' + intName(label) + '</strong>.');
  }
}

// --- Starting from an entrance

// Away from the trails (at home, say), a route from where you are means nothing: you'll
// drive to an entrance. So routes start from an entrance you pick instead.
function awayFromTrails() { return snapToTrail(userLatLng).d > ON_TRAILS_M; }

var ENTRANCE_CHOICES = 6;   // nearest entrances offered before "More entrances"

function pickEntrance(destLabel, roundTrip, all) {
  var opts = entryLabels().filter(function(l) { return l !== destLabel; }).map(function(l) {
    var t = pathTree(l);
    return {label: l, len: t.len[destLabel], cost: t.dist[destLabel]};
  }).filter(function(o) { return o.len !== undefined; }).sort(function(a, b) { return a.cost - b.cost; });
  if (opts.length) {
    clearSelection(true);
    all = all || opts.length <= ENTRANCE_CHOICES + 1;   // "More" for just one more isn't worth it
    var html = '<div class="route-msg" style="margin-top:0">You\'re away from the trails. Start the ' +
      (roundTrip ? 'round trip' : 'route') + ' to ' + intPill(destLabel) + ' from which entrance?</div><div class="exits">';
    opts.slice(0, all ? opts.length : ENTRANCE_CHOICES).forEach(function(o) {
      var p = intFeatures[o.label].properties;
      html += '<button class="exit-btn" onclick="routeFromEntrance(\'' + o.label + '\', \'' + destLabel + '\', ' + roundTrip + ')">' +
        entryChipHtml(o.label) +
        '<span class="exit-dist">' + formatDist(roundTrip ? 2 * o.len : o.len) + '</span>' + parkSlotHtml(o.label) +
        entryNoteHtml(o.label, "from") + '</button>';
    });
    if (!all && opts.length > ENTRANCE_CHOICES)
      html += '<div class="plan-link"><a onclick="pickEntrance(\'' + destLabel + '\', ' + roundTrip + ', true)">More entrances (' +
        (opts.length - ENTRANCE_CHOICES) + ')</a></div>';
    document.getElementById("infoContent").innerHTML = html + '</div>' + backToRouteBtn();
  } else {
    showPanelMsg('You\'re away from the trails, and no entrance has a route to ' + intPill(destLabel) + '.');
  }
}

// A planned route (or round trip) from an entrance. It's a plan, not live: you aren't
// there yet. Once you are, Route here or Round trip follows you from where you stand.
function routeFromEntrance(entry, destLabel, roundTrip) {
  var trip = newTrip(entry, roundTrip ? [destLabel] : [], roundTrip ? null : destLabel);
  if (roundTrip) {
    trip.home = intMarkers[entry].getLatLng();
    trip.homeAnchors = [{label: entry, dist: 0}];
    trip.homeLabel = entry;
  }
  startTrip(trip, 'No ' + (roundTrip ? 'round trip' : 'route') + ' found from <strong>' + intName(entry) + '</strong> to <strong>' + intName(destLabel) + '</strong>.');
}

// --- Waypoints

// Distance by trail, in meters, between two places: a label, null for "where you are" (as
// a start), or "home" (as an end, for a round trip)
function tripLegDist(trip, a, b) {
  var d;
  if (b === "home") {
    var r = a === null ? {len: 0} : pathToAnchors(a, trip.homeAnchors, {});
    d = r ? r.len : Infinity;
  } else if (a === null) {
    var best = bestRouteFromMe(b);
    d = best ? best.total : Infinity;
  } else {
    d = pathTree(a).len[b];
  }
  return d === undefined ? Infinity : d;
}

// Add or remove a stop; the stops ahead are then put back in the best order
function changeStops(change) {
  var trip = plan.trip;
  change(trip);
  optimizeStops(trip);
  replanTrip(plan.progress === null ? 0 : plan.progress);
}

function addWaypoint(label) {
  changeStops(function(trip) { trip.stops.push({label: label, edge: null, done: false, skipped: false}); });
}

function removeWaypoint(label) {
  changeStops(function(trip) { trip.stops = trip.stops.filter(function(s) { return s.done || s.label !== label; }); });
}

function sameEdge(e, a, b, trail) {
  return !!e && e.trail === trail && ((e.a === a && e.b === b) || (e.a === b && e.b === a));
}

function addSegment(a, b, trail, chain) {
  changeStops(function(trip) {
    trip.stops.push({label: null, edge: {a: a, b: b, trail: trail, chain: chain || [a, b]}, done: false, skipped: false});
  });
  clearSelection(true);
}

function removeSegment(a, b, trail) {
  changeStops(function(trip) { trip.stops = trip.stops.filter(function(s) { return s.done || !sameEdge(s.edge, a, b, trail); }); });
  clearSelection(true);
}

function isPendingStop(label) {
  return !!plan && pendingStops(plan.trip).some(function(s) { return s.label === label; });
}

function isPendingSegment(a, b, trail) {
  return !!plan && pendingStops(plan.trip).some(function(s) { return sameEdge(s.edge, a, b, trail); });
}

// Plan what's left of the trip again, keeping what was walked up to walked as history
function replanTrip(walked) {
  var args = compileTrip(plan.trip);
  if (args) {
    renderRoute(args.result, args.userLeg, true, historyTo(walked, true), args.info);
    drawRoute();
    showRoutePanel();
  }
}

// Steps and route pieces up to walked, added to what was already history. passedOnly
// leaves out the step you're at, for a replan that starts from you and includes it again.
function historyTo(walked, passedOnly) {
  var hist = {steps: plan.hist.steps.slice(), segs: plan.hist.segs.slice()};
  var upTo = passedOnly ? walked - AT_INT_M : walked + AT_INT_M;
  if (plan.live) {
    plan.steps.forEach(function(st) { if (st.at <= upTo) hist.steps.push(st); });
    plan.segs.forEach(function(seg) {
      var pts = segPiece(seg, seg.s0, walked);
      if (pts) hist.segs.push({pts: pts, trimStart: seg.trimStart,
                               trimEnd: walked >= seg.s0 + segLen(seg) && seg.trimEnd});
    });
  }
  return hist;
}

// A stop is done once you're at it or past it; exit is where you left it (for a segment,
// whichever end you walked it to)
function markReachedStops() {
  plan.steps.forEach(function(st, i) {
    if (st.stop && !st.stop.done && stepState(i) !== "ahead") { st.stop.done = true; st.stop.exit = st.label; }
  });
}

// Distance by trail, in meters, from a point to an intersection
function distFromPoint(ll, label) {
  var best = Infinity;
  userAnchors(ll).forEach(function(a) {
    var d = pathTree(a.label).len[label];
    if (d !== undefined) best = Math.min(best, a.dist + d);
  });
  return best;
}

// Off the route and heading for a stop you missed: skip it once you're closer to the stop
// after it than the missed stop is, and you've got SKIP_MARGIN_M closer to that one since
// the last stop (or the trip's start), so a stop behind you isn't dropped at the outset.
// A round trip's turnaround is never skipped.
function skipMissedStops() {
  var trip = plan.trip, pending = pendingStops(trip), go = true;
  var ends = function(stop) { return stop.edge ? [stop.edge.a, stop.edge.b] : [stop.label]; };
  var nearest = function(froms, tos, d) {
    var best = Infinity;
    froms.forEach(function(f) { tos.forEach(function(t) { best = Math.min(best, d(f, t)); }); });
    return best;
  };
  var legDist = function(a, b) { return tripLegDist(trip, a, b); };
  while (go && pending.length) {
    var w = pending[0], after = pending[1] ? ends(pending[1]) : trip.to !== null ? [trip.to] : null;
    go = after !== null;
    if (go) {
      var prev = trip.stops.slice(0, trip.stops.indexOf(w)).filter(function(s) { return s.done && !s.skipped; }).pop();
      var from = prev ? intMarkers[prev.exit || prev.label || prev.edge.b].getLatLng() : trip.origin;
      var meAfter = nearest([null], after, legDist);
      go = meAfter < nearest(ends(w), after, legDist) &&
        meAfter < nearest([from], after, distFromPoint) - SKIP_MARGIN_M;
      if (go) { w.done = true; w.skipped = true; pending.shift(); }
    }
  }
}

// --- Round trip direction

// The same round trip the other way: the route reversed, and the stops still ahead in
// reverse order. From where you are, it joins at the far end of the old route.
function reverseLoop() {
  var trip = plan.trip, n = plan.steps.length, rp = [], ok = false;
  for (var i = n - 1; i >= 0; i--) rp.push({label: plan.steps[i].label, trail: i < n - 1 ? plan.steps[i + 1].trail : null});
  var lead = bestRouteFromMe(rp[0].label);
  var tail = trip.homeAnchors.filter(function(a) { return a.label === rp[n - 1].label; })[0];
  var extra = tail ? null : pathToAnchors(rp[n - 1].label, trip.homeAnchors, {});
  if (lead && (tail || extra)) {
    var path = lead.result.path.concat(rp.slice(1), extra ? extra.path.slice(1) : []);
    var stopAt = {}, offset = lead.result.path.length - 1;
    plan.steps.forEach(function(st, j) {
      if (st.stop) stopAt[offset + n - 1 - (st.stop.edge ? j - (st.stop.edge.chain.length - 1) : j)] = st.stop;
    });
    var pending = pendingStops(trip).reverse();
    trip.stops = trip.stops.filter(function(s) { return s.done; }).concat(pending);
    renderRoute({path: path, totalDist: lead.result.totalDist + plan.graphDist + (extra ? extra.len - extra.anchor.dist : 0)},
                lead.anchor, true, historyTo(plan.progress, true), {trip: trip, tail: tail || extra.anchor, stopAt: stopAt});
    ok = true;
  }
  return ok;
}

// Whether a reversed round trip would be any different: not for a plain out and back
function canReverseLoop() {
  var labels = plan.steps.map(function(s) { return s.label; });
  return plan.trip.to === null && plan.live && !plan.arrived && !plan.trip.stops.some(function(s) { return s.done; }) &&
    labels.join(" ") !== labels.slice().reverse().join(" ");
}

// The Reverse loop button
function reverseLoopNow() {
  if (reverseLoop()) {
    drawRoute();
    showRoutePanel();
  }
}

// The step of the last stop still ahead, or null once every stop is done
function lastStopStep() {
  var found = null;
  plan.steps.forEach(function(st) { if (st.stop && !st.stop.done) found = st; });
  return found;
}

// A rough fix (say, a phone that just woke up) isn't good enough to call you off the route
var REROUTE_MAX_ACC_M = 50;

function liveRouting() { return plan && plan.live && !plan.arrived; }

// Where on the live route you are. Prefers spots at or past your last position, so a
// route that doubles back doesn't jump ahead. Returns false when you're off the route,
// and "reverse" when you're going around a round trip the other way.
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
  // Where a route passes the same ground twice (an out and back), a spot matches both
  // ways. Going backwards costs a meter per meter, and jumping ahead a little, so the
  // match just ahead of your last position wins.
  var cost = function(c) {
    return c.d + Math.max(0, plan.progress - c.s) + 0.02 * Math.max(0, c.s - plan.progress);
  };
  var cheapest = function(list) {
    var best = null;
    list.forEach(function(c) { if (!best || cost(c) < cost(best)) best = c; });
    return best;
  };
  // On a round trip, matching far along the way home before the last stop means you set
  // off around the loop the other way (only before any stop is reached, as for the
  // Reverse loop button)
  var any = cheapest(near), lastStop = canReverseLoop() ? lastStopStep() : null;
  var result = "reverse";
  var far = any.s - plan.progress > LOOP_REVERSE_M;
  // Otherwise (a stop already reached, say the first loop of a figure 8 walked), matching
  // far ahead, beyond two or more stops, and walking back along the route from there, means
  // you set off around this part the other way: those stops get visited last first. A
  // fix or two is needed to see which way you're walking; till then you stay on the route.
  var behind = far && !lastStop ? stopsBefore(any.s) : [];
  var back = plan.backward;
  plan.backward = null;
  if (behind.length >= 2 && userAccuracy <= REROUTE_MAX_ACC_M) {
    if (back && any.s <= back.s - BACKWARD_M) {
      flipStops(behind);
      plan.flipped = behind.slice().reverse();
      return "replan";
    }
    if (!back || any.s < back.s + BACKWARD_M && back.fixes < BACKWARD_FIXES) {
      plan.backward = back && any.s < back.s + BACKWARD_M ? {s: back.s, fixes: back.fixes + 1} : {s: any.s, fixes: 1};
      return true;
    }
  }
  if (!(lastStop && far && any.s > lastStop.at)) {
    // Progress can't skip past a stop you haven't reached: a later part of the route can
    // run near the turnoff for it, and walking that way means you're missing the stop
    var stop = nextStopStep();
    var best = cheapest(near.filter(function(c) { return !stop || c.s <= stop.at + AT_INT_M; }));
    if (best) plan.progress = best.s;
    result = !!best;
  }
  return result;
}

// The stops not yet reached on the route before position s, in route order
function stopsBefore(s) {
  var found = [];
  plan.steps.forEach(function(st) {
    if (st.stop && !st.stop.done && st.at < s && found.indexOf(st.stop) < 0) found.push(st.stop);
  });
  return found;
}

// The trip's stops with these ones (in route order) put in the opposite order, in place
function flipStops(list) {
  var stops = plan.trip.stops, slots = list.map(function(st) { return stops.indexOf(st); });
  list.slice().reverse().forEach(function(st, i) { stops[slots[i]] = st; });
}

// The step of the first stop not yet reached, or null
function nextStopStep() {
  return plan.steps.filter(function(st) { return st.stop && !st.stop.done; })[0] || null;
}

// trackProgress, reversing a round trip first if you're going around it the other way
function trackOrReverse() {
  var onRoute = trackProgress();
  if (onRoute === "reverse") onRoute = reverseLoop() && trackProgress() === true;
  if (onRoute === "replan") {
    var was = plan;
    rerouteFromHere();
    if (plan === was) flipStops(was.flipped);   // no way from here: the old order again
    onRoute = trackProgress() === true;
  }
  return onRoute;
}

// Called on each new fix while a live route is up
function updateLiveRoute() {
  saveTrip();
  var trip = plan.trip;
  var onRoute = trackOrReverse();
  markReachedStops();
  var allDone = pendingStops(trip).length === 0;
  var destLL = trip.to === null ? trip.home : intMarkers[trip.to].getLatLng();
  if (allDone && userLatLng.distanceTo(destLL) <= AT_INT_M) {
    plan.progress = plan.total;
    plan.arrived = true;
  } else if (onRoute) {
    if (allDone && plan.total - plan.progress <= AT_INT_M) plan.arrived = true;
  } else if (userAccuracy <= REROUTE_MAX_ACC_M) {
    rerouteFromHere();   // with no way from here, the old route stays up
  }
  drawRoute();
  if (document.getElementById("routeInfo")) showRoutePanel();
  else refreshLocateInfo();
}

// How far along the route you walked before leaving it. Fixes are seconds apart, so the
// last one on the route often falls short of the intersection where you turned off.
// If the trail you're on now starts at an intersection still ahead on the route, and
// the new route (newPath) doesn't go back through it, you walked to it and turned there.
function turnedAt(newPath) {
  var walked = plan.progress, snap = snapToTrail(userLatLng);
  if (snap.d < SNAP_M) {
    var ends = segmentEnds(snap), onNew = {};
    newPath.forEach(function(p) { onNew[p.label] = true; });
    var endLabels = [ends.before, ends.after].filter(Boolean).map(function(e) { return e[0]; });
    var turn = plan.steps.filter(function(st) {
      return st.at > plan.progress + AT_INT_M && endLabels.indexOf(st.label) >= 0 && !onNew[st.label];
    })[0];
    if (turn) walked = turn.at;
  }
  return walked;
}

// Off the route: plan again from here, keeping what was already walked as grey history
function rerouteFromHere() {
  var stops = plan.trip.stops, was = stops.map(function(s) { return [s.done, s.skipped]; });
  skipMissedStops();
  var args = compileTrip(plan.trip);
  if (args) {
    renderRoute(args.result, args.userLeg, true, historyTo(turnedAt(args.result.path)), args.info);
  } else {
    stops.forEach(function(s, i) { s.done = was[i][0]; s.skipped = was[i][1]; });
  }
}

var hoverMarker = null;
var hoverTrailLayers = [];
var hoverOwnerMarkers = [];

// Highlight every intersection with this owner (or, with field "cr", on this
// conservation restriction's land)
function hoverOwner(ownerName, field) {
  unhover();
  Object.keys(intFeatures).forEach(function(label) {
    var f = intFeatures[label];
    var m = intMarkers[label];
    if (f.properties[field || "owner"] === ownerName && m && m !== selectedMarker && !f.properties.junction) {
      m.setStyle({radius: 11, weight: 4, color: "#111", fillColor: ZONE_COLORS[m._zone] || "#1565c0", fillOpacity: 1, opacity: 1});
      m.bringToFront();
      hoverOwnerMarkers.push(label);
    }
  });
}

function hoverInt(label) {
  unhover();
  if (intMarkers[label]) {
    intMarkers[label].setStyle({radius: 11, weight: 3, color: "#f1c40f", fillColor: "#f1c40f", fillOpacity: 1, opacity: 1});
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
      intMarkers[hoverMarker].setStyle(restStyle(intMarkers[hoverMarker]));
    }
    hoverMarker = null;
  }
  hoverOwnerMarkers.forEach(function(label) {
    var m = intMarkers[label];
    if (m && m !== selectedMarker) {
      var z = m._zone;
      m.setStyle(restStyle(m));
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

// The stretch of a trail between the signed places on either side of a point on it:
// {a, b, trail, chain, ti, from, to}, where chain lists a, any unsigned junctions passed,
// and b; or null where the trail ends without an intersection
function segmentAt(feature, ll) {
  var ti = feature.properties._idx, seg = null;
  if (trailIntMap[ti]) {
    var ends = segmentEnds(snapOnTrail(ll, ti), true);
    if (ends.before && ends.after && ends.before[0] !== ends.after[0]) {
      seg = {a: ends.before[0], b: ends.after[0], trail: feature.properties.pdf_name || feature.properties.name || "Unnamed",
             chain: ends.chain, ti: ti, from: ends.before[1], to: ends.after[1]};
    }
  }
  return seg;
}

var selectedSegLine = null;

// The pieces of trail ti's trail: those with its name that connect to it, through
// intersections or ends they share. Two trails far apart can have the same name.
function sameTrail(ti) {
  var name = function(i) { var q = trailData.features[i].properties; return q.pdf_name || q.name || ""; };
  var ends = function(i) {
    var c = flatCoords(trailData.features[i].geometry), out = {};
    [c[0], c[c.length - 1]].forEach(function(p) { out[p[0].toFixed(5) + "," + p[1].toFixed(5)] = true; });
    ((trailIntMap[i] || {}).ints || []).forEach(function(e) { out[e[0]] = true; });
    return out;
  };
  var found = {}, queue = [ti], mine = name(ti);
  var others = trailData.features.map(function(f, i) { return i; }).filter(function(i) { return name(i) === mine; });
  var keys = {};
  others.forEach(function(i) { keys[i] = ends(i); });
  found[ti] = true;
  while (queue.length) {
    var a = queue.pop();
    others.forEach(function(b) {
      if (!found[b] && Object.keys(keys[a]).some(function(k) { return keys[b][k]; })) { found[b] = true; queue.push(b); }
    });
  }
  return found;
}

// The pieces of trail ti's trail in walking order: {pieces: [{ti, rev, off, len, jump}],
// total}. Pieces join where they share an end (a point, or an intersection right at it).
// A trail that forks can't be walked in one line; jump marks a piece that starts another
// branch, not meeting the one before it.
function trailChain(ti) {
  var p = trailData.features[ti].properties;
  var set = (p.pdf_name || p.name) ? Object.keys(sameTrail(ti)).map(Number) : [ti];
  var lenOf = function(i) { return trailCum[i][trailCum[i].length - 1]; };
  var endKeys = function(i, atEnd) {
    var c = flatCoords(trailData.features[i].geometry), q = atEnd ? c[c.length - 1] : c[0], keys = {};
    keys[q[0].toFixed(5) + "," + q[1].toFixed(5)] = true;
    ((trailIntMap[i] || {}).ints || []).forEach(function(e) {
      var near = Math.min(15, lenOf(i) / 2);
      if (atEnd ? lenOf(i) - e[1] < near : e[1] < near) keys[e[0]] = true;
    });
    return keys;
  };
  var ends = {};
  set.forEach(function(i) { ends[i] = [endKeys(i, false), endKeys(i, true)]; });
  var meets = function(a, b) { return Object.keys(a).some(function(k) { return b[k]; }); };
  var shared = function(i, e) { return set.some(function(j) { return j !== i && (meets(ends[i][e], ends[j][0]) || meets(ends[i][e], ends[j][1])); }); };
  // Start from a loose end, if there is one
  var first = set.filter(function(i) { return !shared(i, 0) || !shared(i, 1); })[0];
  if (first === undefined) first = set[0];
  var pieces = [], used = {}, off = 0, cur = first, rev = shared(first, 0) && !shared(first, 1), jump = false;
  while (cur !== undefined) {
    used[cur] = true;
    pieces.push({ti: cur, rev: rev, off: off, len: lenOf(cur), jump: jump});
    off += lenOf(cur);
    var tail = ends[cur][rev ? 0 : 1], next;
    next = set.filter(function(j) { return !used[j] && (meets(tail, ends[j][0]) || meets(tail, ends[j][1])); })[0];
    jump = next === undefined;
    if (jump) {
      // A branch: preferably one starting at a loose end
      var left = set.filter(function(j) { return !used[j]; });
      next = left.filter(function(j) { return !shared(j, 0) || !shared(j, 1); })[0];
      if (next === undefined) next = left[0];
      if (next !== undefined) rev = shared(next, 0) && !shared(next, 1);
    } else {
      rev = !meets(tail, ends[next][0]) && meets(tail, ends[next][1]);
    }
    cur = next;
  }
  return {pieces: pieces, total: off};
}

// The pieces' stretches from d0 to d1 along the chain: [{ti, a, b}], a to b in walking order
function chainSlices(chain, d0, d1) {
  var out = [];
  chain.pieces.forEach(function(pc) {
    var lo = Math.max(d0, pc.off), hi = Math.min(d1, pc.off + pc.len);
    if (hi - lo > 0.5) {
      var a = lo - pc.off, b = hi - pc.off;
      var jump = pc.jump && lo <= pc.off + 0.5;
      out.push(pc.rev ? {ti: pc.ti, a: pc.len - a, b: pc.len - b, jump: jump} : {ti: pc.ti, a: a, b: b, jump: jump});
    }
  });
  return out;
}

// The numbered intersections along the chain, in order: [{label, d, piece}] (piece: its
// index in the chain)
function chainStops(chain) {
  var stops = [];
  chain.pieces.forEach(function(pc, i) {
    var ints = ((trailIntMap[pc.ti] || {}).ints || []).slice();
    if (pc.rev) ints.reverse();
    ints.forEach(function(e) {
      var d = pc.off + (pc.rev ? pc.len - e[1] : e[1]), last = stops[stops.length - 1];
      // Where two pieces meet, their shared intersection is listed once
      var again = last && last.label === e[0] && !(pc.jump && last.piece < i);
      if (!isJunction(e[0]) && !again) stops.push({label: e[0], d: d, piece: i});
    });
  });
  return stops;
}

var TERRAIN_MIN_M = 20;   // less of a terrain than this in a stretch goes unmentioned

// Terrain over some stretches: [[terrain, meters]], roughest first
function terrainMix(slices) {
  var len = [];
  slices.forEach(function(sl) {
    var lo = Math.min(sl.a, sl.b), hi = Math.max(sl.a, sl.b);
    (trailData.features[sl.ti].properties.widths || []).forEach(function(r) {
      var x = Math.max(lo, r[1]), y = Math.min(hi, r[2]);
      if (y > x) { var t = terrainOn(sl.ti, x, y); if (t !== null) len[t] = (len[t] || 0) + (y - x); }
    });
  });
  var out = [];
  for (var t = len.length - 1; t >= 0; t--) if (len[t]) out.push([t, len[t]]);
  return out;
}

// What the trail panel shows: the trail (feature and layer tapped), its chain and stops,
// and the stretch selected ([from, to] along the chain), or null for the whole trail
var trailView = null;

// Show a stretch of the trail in the panel: from mark k to the next. While routing, as if
// its middle were tapped, so it can be added to the route.
function showTrailStretch(k) {
  var v = trailView, marks = trailMarks(v);
  var mid = chainSlices(v.chain, (marks[k].d + marks[k + 1].d) / 2, marks[k + 1].d)[0];
  if (plan && mid) {
    var l = trailLayer.getLayers().filter(function(x) { return x.feature.properties._idx === mid.ti; })[0];
    showTrailInfo(l.feature, l, pointAlong(mid.ti, mid.a));
  } else {
    showTrailInfo(v.feature, v.layer, null, k);
  }
}

function showWholeTrail() {
  showTrailInfo(trailView.feature, trailView.layer, null, null);
}

// Where the stretches begin and end: [{d, label, brk}] along the chain. Each run of
// connected pieces (each branch) has marks at its ends, named for the intersection there
// if there is one, and at its stops; brk marks a branch's first. Stretches run from a
// mark to the next, within a branch.
function trailMarks(v) {
  var marks = [], pieces = v.chain.pieces, first = 0;
  for (var i = 1; i <= pieces.length; i++) {
    if (i < pieces.length && !pieces[i].jump) continue;
    var a = pieces[first].off, b = i < pieces.length ? pieces[i].off : v.chain.total;
    var run = [{d: a, label: null, brk: marks.length > 0}];
    v.stops.forEach(function(st) {
      if (st.piece < first || st.piece >= i) return;
      var last = run[run.length - 1];
      if (st.d - last.d <= 3) { if (!last.label) last.label = st.label; }
      else run.push({d: st.d, label: st.label});
    });
    var end = run[run.length - 1];
    if (run.length > 1 && b - end.d <= 3) end.d = b;
    else run.push({d: b, label: null});
    marks = marks.concat(run);
    first = i;
  }
  return marks;
}

// ll (optional): where the trail was tapped, which picks out the stretch between the
// intersections around it (and while routing, a segment that can be added to the route
// as a waypoint). k (optional): show the stretch from trailMarks mark k to the next
// instead; null for the whole trail.
function showTrailInfo(feature, layer, ll, k) {
  clearSelection(true);

  var p = feature.properties;
  var name = p.pdf_name || p.name || "";
  var seg = plan && ll ? segmentAt(feature, ll) : null;
  var chain = trailChain(p._idx);
  trailView = {feature: feature, layer: layer, chain: chain, stops: chainStops(chain)};
  var marks = trailMarks(trailView);

  // Which stretch: the one tapped, the one asked for, or (null) the whole trail
  var sel = null;
  if (ll) {
    var snap = snapOnTrail(ll, p._idx);
    var pi = chain.pieces.findIndex(function(x) { return x.ti === p._idx; }), pc = chain.pieces[pi];
    var d = pc.off + (pc.rev ? pc.len - snap.along : snap.along);
    // The stretch around it, in the tapped piece's branch
    for (var m = 0; m < marks.length - 1; m++) {
      if (!marks[m + 1].brk && d >= marks[m].d - 0.5 && d <= marks[m + 1].d + 0.5 &&
          chainSlices(chain, marks[m].d, marks[m + 1].d).some(function(sl) { return sl.ti === p._idx; })) { k = m; break; }
    }
  }
  // A trail with no intersections along it is all one stretch: the whole trail
  if (k !== undefined && k !== null && marks.length > 2) sel = {a: marks[k], b: marks[k + 1], k: k};
  // While routing, a tapped segment (which can be added to the route) is what's shown
  var slices = seg ? [{ti: seg.ti, a: seg.from, b: seg.to}] : sel ? chainSlices(chain, sel.a.d, sel.b.d) : chainSlices(chain, 0, chain.total);
  var spanLen = slices.reduce(function(t, sl) { return t + Math.abs(sl.b - sl.a); }, 0);

  // The trail (or stretch) drawn over the map, above any blazes
  highlightedSegments = [];
  selectedSegLine = L.featureGroup(slices.map(function(sl) {
    return L.polyline(sliceTrail(sl.ti, sl.a, sl.b), {color: "#00b8d4", weight: sel || seg ? 7 : 6, opacity: 1, interactive: false});
  })).addTo(map);

  var displayName = name || "Unnamed trail";
  var html = '';
  if (seg) {
    var segArgs = jsArg(seg.a) + ', ' + jsArg(seg.b) + ', ' + jsArg(seg.trail);
    var addArgs = segArgs + ', ' + esc(JSON.stringify(seg.chain));
    html += '<div class="seg-pick">' + intPill(seg.a) + ' – ' + intPill(seg.b) + ' on <strong>' + esc(seg.trail) + '</strong>' +
      ' <span class="int-dist">' + formatDist(Math.abs(seg.to - seg.from)) + '</span><div>' +
      (isPendingSegment(seg.a, seg.b, seg.trail)
        ? '<button class="route-btn" style="background:#0d47a1" onclick="removeSegment(' + segArgs + ')">Remove from route</button> '
        : '<button class="route-btn" style="background:#0d47a1" onclick="addSegment(' + addArgs + ')">Add to route</button> ') +
      backToRouteBtn() + '</div></div>';
  }

  // The stretch shown, by the intersections at its ends (a dot where the trail ends)
  var endName = function(label) {
    return label ? intPill(label) : '<span class="int-terminus" title="End of the trail"></span>';
  };
  var ends = seg ? [seg.a, seg.b] : sel ? [sel.a.label, sel.b.label] : null;
  html += '<table><tr><td>Trail</td><td><strong style="font-size:16px">' + esc(displayName) + '</strong>' + (ends
    ? '<div class="blaze-marks">' + endName(ends[0]) + ' → ' + endName(ends[1]) +
      ' &nbsp;·&nbsp; <a class="trail-whole" onclick="showWholeTrail()">whole trail</a></div>'
    : '') + '</td></tr>';
  if (chain.total > 0) {
    html += '<tr><td>Length</td><td>' + formatDist(spanLen) +
      (ends ? ' <span class="int-dist">of ' + formatDist(chain.total) + '</span>' : '') + '</td></tr>';
  }

  // Blazes on the stretch (on most of it), or anywhere on the whole trail
  var blazed = [];
  slices.forEach(function(sl) {
    var here = ends ? blazesOn(sl.ti, sl.a, sl.b).map(function(o) { return o.key; })
      : (trailData.features[sl.ti].properties.blazes || []).map(function(r) { return r[0]; });
    here.forEach(function(k) { if (blazed.indexOf(k) < 0) blazed.push(k); });
  });
  if (blazed.length) {
    html += '<tr><td>Blazes</td><td>' + blazed.map(function(k) {
      var b = REGION.blazes[k];
      // The name, and under it how it's marked
      return '<div class="blaze-row">' + blazeMarkSvg(k) + '<div>' + esc(b.name) + '<div class="blaze-marks">' + esc(b.marks) +
        (b.one_way ? ', one way' : '') + '</div></div></div>';
    }).join('') + '</td></tr>';
  }

  // A few meters of another terrain where a stretch begins or ends isn't worth saying
  var mix = terrainMix(slices), worth = mix.filter(function(m) { return m[1] >= TERRAIN_MIN_M; });
  if (worth.length) mix = worth;
  if (mix.length) {
    var main = mix.slice().sort(function(a, b) { return b[1] - a[1]; })[0];
    var widths = {};
    slices.forEach(function(sl) { var w = widthOn(sl.ti, sl.a, sl.b); if (w) widths[w] = true; });
    var widthText = Object.keys(widths).map(function(w) { return REGION.widths[w].toLowerCase(); }).join(', ');
    html += '<tr><td>Terrain</td><td><div class="blaze-row">' + terrainSvg(main[0]) + '<div>' + esc(REGION.terrain[main[0]]) +
      (mix.length > 1 ? ' mostly' : '') + '<div class="blaze-marks">' +
      (mix.length > 1 ? mix.map(function(m) { return formatDist(m[1]) + ' ' + REGION.terrain[m[0]].toLowerCase(); }).join(' · ') : esc(widthText)) +
      '</div></div></div></td></tr>';
  }

  if (REGION.eleStep) {
    var prof = [], off = 0;
    slices.forEach(function(sl) {
      if (sl.jump && prof.length) prof.push(null);
      eleProfile(sl.ti, sl.a, sl.b).forEach(function(q, i) {
        if (i || !prof.length || prof[prof.length - 1] === null) prof.push([off + q[0], q[1]]);
      });
      off += Math.abs(sl.b - sl.a);
    });
    if (prof.length > 1) {
      var st = climbStats(prof), worst = Math.max(st.maxUp, st.maxDown);
      html += '<tr><td>Climb</td><td>' + climbHtml(st) +
        '<div class="blaze-marks">' + steepness(worst) + (worst >= STEEPNESS[0][0] ? ', ' + Math.round(100 * worst) + '% at the steepest' : '') + '</div>' +
        profileSvg(prof) + '</td></tr>';
    }
  }
  if (p.surface) html += '<tr class="full-only"><td>Surface</td><td>' + esc(p.surface) + '</td></tr>';
  if (p.highway) html += '<tr class="full-only"><td>Type</td><td>' + esc(p.highway) + '</td></tr>';
  html += '</table>';

  // Intersections along the trail; the stretches between them pick out that stretch
  html += '<div class="int-list full-only"><strong style="font-size:12px;color:#555">Intersections</strong>';
  for (var m = 0; m < marks.length; m++) {
    if (marks[m].brk) html += '<div class="trail-break">branch</div>';
    html += '<div class="int-row">' + endName(marks[m].label) + '</div>';
    if (m < marks.length - 1 && !marks[m + 1].brk) {
      var on = sel && sel.k === m;
      html += '<a class="seg-bar seg-link' + (on ? ' sel' : '') + '" onclick="showTrailStretch(' + m + ')" title="Show this stretch">↕ ' +
        formatDist(marks[m + 1].d - marks[m].d) + '</a>';
    }
  }
  html += '</div>';
  if (plan && !seg) html += '<div style="margin-top:6px">' + backToRouteBtn() + '</div>';
  html += reportLinkHtml("trail", name || "Unnamed trail", seg && (seg.a + "–" + seg.b),
                         blazed.map(function(k) { return REGION.blazes[k].marks; }).join(", "));

  document.getElementById("infoContent").innerHTML = html;
}

function clearSelection(keepRoute) {
  if (selectedSegLine) {
    map.removeLayer(selectedSegLine);
    selectedSegLine = null;
  }
  if (selectedRing) {
    map.removeLayer(selectedRing);
    selectedRing = null;
  }
  if (selectedMarker) {
    var z = selectedMarker._zone;
    selectedMarker.setStyle(restStyle(selectedMarker));
    selectedMarker = null;
  }
  highlightedSegments.forEach(function(l) { trailLayer.resetStyle(l); });
  highlightedSegments = [];
  if (!keepRoute) clearRouteDisplay();
  routeMode = false;
  routeFrom = null;
  currentIntFeature = null;
}

// --- Reporting a problem. The site has no server, so a report is an email: the form
// fills in a message for the phone's mail app, with the details needed to act on it.
// REGION.report: {email, signReports}; signReports adds "I'm standing at this sign".

// blazes (optional, for a trail): the blazes the map shows on it, for the report to say
function reportLinkHtml(what, ref, extra, blazes) {
  return REGION.report
    ? '<div class="report-link full-only"><a onclick="showReport(' + jsArg(what) + ', ' + jsArg(ref) + ', ' + jsArg(extra || "") + ', ' +
      jsArg(blazes || "") + ')">Report a problem</a></div>'
    : '';
}

var REPORT_KINDS = {
  int: ["Wrong location on the map", "Wrong number", "Missing or damaged sign", "Trail problem here (blocked, washed out...)", "Other"],
  trail: ["Trail is drawn in the wrong place", "Trail doesn't exist or is closed", "Blocked, overgrown, or washed out", "Wrong name", "Other"],
  here: ["A trail here is missing from the map", "Something's wrong with the map here", "Other"]
};
var AT_SIGN = "I'm standing at this sign";
// Offered for trails where the region maps blazes, to collect what's really out there
var BLAZE_KIND = "Blaze color wrong or missing";
var REPORT_HINTS = {};
REPORT_HINTS[BLAZE_KIND] = "What blazes do you see? The colors, and where along the trail they start and stop";
var NOTE_HINT = "Anything else? (optional)";

function showReport(what, ref, extra, blazes) {
  var kinds = REPORT_KINDS[what].slice();
  var p = what === "int" ? intFeatures[ref].properties : null;
  if (what === "int" && REGION.report.signReports && !p.no_sign) kinds.unshift(AT_SIGN);
  if (what === "trail" && Object.keys(REGION.blazes || {}).length) kinds.splice(kinds.length - 1, 0, BLAZE_KIND);
  var subject = what === "int" ? intName(ref) : what === "trail" ? ref + (extra ? " (" + extra + ")" : "") : "where I am";
  var html = '<div class="report"><div class="report-head">Report a problem with <strong>' + esc(subject) + '</strong></div>';
  kinds.forEach(function(k, i) {
    html += '<label class="report-kind"><input type="radio" name="reportKind" value="' + esc(k) + '"' + (i === 0 ? ' checked' : '') +
      ' onchange="document.getElementById(\'reportNote\').placeholder = ' + jsArg(REPORT_HINTS[k] || NOTE_HINT) + '"> ' + esc(k) + '</label>';
  });
  html += '<textarea id="reportNote" rows="3" placeholder="' + esc(NOTE_HINT) + '"></textarea>' +
    '<div id="reportWarn" class="report-warn"></div>' +
    '<button class="route-btn" onclick="sendReport(' + jsArg(what) + ', ' + jsArg(ref) + ', ' + jsArg(extra || "") + ', ' + jsArg(blazes || "") + ')">Send report</button> ' +
    '<button class="route-btn" style="background:#888" onclick="closeReport(' + jsArg(what) + ', ' + jsArg(ref) + ')">Cancel</button>' +
    '<div class="report-fine">Opens your mail app with the report filled in, including your location if it\'s on. Send it from there.</div></div>';
  document.getElementById("infoContent").innerHTML = html;
}

// Hands a mailto: link to the phone's mail app (a separate step so tests can catch it)
function openMail(url) { location.href = url; }

function closeReport(what, ref) {
  if (what === "int") showIntInfo(intFeatures[ref], intMarkers[ref]);
  else if (plan) backToRoute();
  else showHome();
}

function sendReport(what, ref, extra, blazes) {
  var picked = document.querySelector('input[name="reportKind"]:checked');
  var kind = picked ? picked.value : "Other";
  var note = document.getElementById("reportNote").value.trim();
  var warn = document.getElementById("reportWarn");
  if (kind === AT_SIGN && !userLatLng) {
    warn.textContent = "Turn on your location (the locate button) so the report can say where the sign is.";
  } else {
    var c = map.getCenter();
    var lines = [REGION.name + " map report", "", "What: " + kind];
    if (note) lines.push("Note: " + note);
    if (what === "int") {
      var p = intFeatures[ref].properties, at = intMarkers[ref].getLatLng();
      lines.push("Intersection: " + intName(ref) + (intName(ref) !== ref ? " [" + ref + "]" : "") +
                 (p.number !== undefined ? " (data #" + p.number + ")" : "") + (p.estimated ? ", position estimated" : ""));
      lines.push("Map has it at: " + at.lat.toFixed(6) + ", " + at.lng.toFixed(6));
      if (kind === AT_SIGN) lines.push("Sign is " + Math.round(userLatLng.distanceTo(at)) + " m from where the map has it");
    } else if (what === "trail") {
      lines.push("Trail: " + ref + (extra ? ", between " + extra : ""));
      if (Object.keys(REGION.blazes || {}).length) lines.push("Blazes on the map: " + (blazes || "none"));
    }
    lines.push(userLatLng
      ? "My location: " + userLatLng.lat.toFixed(6) + ", " + userLatLng.lng.toFixed(6) + " (+/- " + Math.round(userAccuracy) + " m)"
      : "My location: not available");
    lines.push("Map view: " + c.lat.toFixed(5) + ", " + c.lng.toFixed(5) + ", zoom " + map.getZoom());
    lines.push("When: " + new Date().toISOString());
    lines.push("Page: " + location.href.split("?")[0]);
    lines.push("Device: " + navigator.userAgent);
    var subj = REGION.name + ": " + kind + (what === "int" ? " - " + intName(ref) : what === "trail" ? " - " + ref : "");
    openMail("mailto:" + REGION.report.email + "?subject=" + encodeURIComponent(subj) + "&body=" + encodeURIComponent(lines.join("\n")));
    document.getElementById("infoContent").innerHTML = '<div class="route-msg" style="margin-top:0">Thanks! Your mail app should open with the report filled in; send it from there.' +
      '<br><br><button class="route-btn" onclick="closeReport(' + jsArg(what) + ', ' + jsArg(ref) + ')">Done</button></div>';
  }
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
var PANEL_KEY = REGION.storagePrefix + "PanelCompact";
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

var defaultInfo = '<div id="welcomeInfo"><p style="color:#888">Click a trail or intersection marker for details.</p>' +
  '<p style="margin-top:6px;font-size:12px"><a onclick="showDriveList()" style="cursor:pointer">Directions to an entrance</a> &nbsp;·&nbsp; ' +
  '<a href="location-help.html' + (/iPhone|iPad|iPod/.test(navigator.userAgent) ? '#iphone' : '') + '">Location not working?</a></p>' +
  '<p class="full-only" style="margin-top:8px;color:#888;font-size:11px">__N_INTS__ numbered intersections across __N_ZONES__ zones.<br>' +
  '__N_TRAILS__ trail segments, __N_NAMES__ named trails.</p></div>';

// The panel when nothing is selected: where you are, once your location is known, or
// the welcome text. Unlike showLocateInfo, this leaves the map where it is.
function showHome() {
  clearSelection(true);
  document.getElementById("infoContent").innerHTML = userLatLng ? locateHtml(userPlace(userLatLng)) : defaultInfo;
}

// Only the Clear button ends a route; a tap on the map just brings the route panel back
// Fingers are wide and the lines thin: a tap this near an intersection or trail picks it
// (the nearest), as if it had landed on it
var TAP_INT_PX = 16, TAP_TRAIL_PX = 20;

function tapNearInt(e) {
  var best = null;
  Object.keys(intMarkers).forEach(function(l) {
    if (intFeatures[l].properties.junction) return;
    var d = map.latLngToContainerPoint(intMarkers[l].getLatLng()).distanceTo(e.containerPoint);
    if (d <= TAP_INT_PX && (!best || d < best.d)) best = {d: d, label: l};
  });
  if (best) intMarkers[best.label]._onTap({});
  return !!best;
}

function tapNearTrail(e) {
  var snap = snapToTrail(e.latlng);
  if (snap.d === Infinity) return false;
  var at = pointAlong(snap.ti, snap.along);
  if (map.latLngToContainerPoint(at).distanceTo(e.containerPoint) > TAP_TRAIL_PX) return false;
  var layer = trailLayer.getLayers().filter(function(l) { return l.feature.properties._idx === snap.ti; })[0];
  showTrailInfo(layer.feature, layer, at);
  return true;
}

map.on("click", function(e) {
  if (tapNearInt(e) || tapNearTrail(e)) return;
  if (plan) {
    if (!document.getElementById("routeInfo")) backToRoute();
  } else {
    clearSelection();
    showHome();
  }
});

// Deep-link support: map.html?int=A1 zooms to that intersection
var params = new URLSearchParams(window.location.search);
var targetInt = params.get("int");
if (targetInt && intMarkers[targetInt]) {
  var m = intMarkers[targetInt];
  var f = intFeatures[targetInt];
  map.setView(m.getLatLng(), 17);
  setTimeout(function() { showIntInfo(f, m); }, 300);
} else {
  map.fitBounds(REGION.bounds);
}

// Geolocation
var userAccuracy = 0, userDot = null, userAccCircle = null, watchId = null;
var locateRequested = false, locateBtn = null;
var NETWORK_BOUNDS = L.latLngBounds(REGION.bounds);

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

// --- Blazed trails (REGION.blazes). Each is drawn over the trails in marks like its own:
// dots, blue blazes, or for triangle-marked loops a stripe with arrows showing which way
// it's marked (the arrows only up close, where they're far enough apart). They're named
// in trail details and route steps. A trail's blazes are [blaze, from m, to m, direction]
// stretches; direction is +1 or -1 along the trail for one-way blazes, 0 for the rest.
var blazeKeys = Object.keys(REGION.blazes || {});
var BLAZE_ARROW_M = 150, BLAZE_ARROW_ZOOM = 15;
var blazeArrows = L.layerGroup();

// A small sample of a blaze's mark, for the legend, trail details, and route steps
function blazeMarkSvg(key) {
  var b = REGION.blazes[key];
  var mark = b.style === "dots" ? '<circle cx="7" cy="7" r="4" fill="' + b.color + '" stroke="#333" stroke-width="1"/>'
    : b.style === "blazes" ? '<rect x="4.5" y="2" width="5" height="10" fill="' + b.color + '" stroke="#0d47a1" stroke-width="0.8"/>'
    : '<path d="M3 2.5 L12 7 L3 11.5 Z" fill="' + b.color + '" stroke="#333" stroke-width="1" stroke-linejoin="round"/>';
  return '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;flex:none">' + mark + '</svg>';
}

function blazeArrowIcon(color, bearing) {
  return L.divIcon({className: "", iconSize: [14, 14], iconAnchor: [7, 7],
    html: '<svg width="14" height="14" viewBox="0 0 14 14" style="transform:rotate(' + Math.round(bearing - 90) + 'deg)">' +
      '<path d="M2.5 2.5 L12 7 L2.5 11.5 Z" fill="' + color + '" stroke="#333" stroke-width="1.2" stroke-linejoin="round"/></svg>'});
}

function bearingAlong(ti, s) {
  var a = pointAlong(ti, Math.max(0, s - 5)), b = pointAlong(ti, s + 5);
  return (Math.atan2((b.lng - a.lng) * 82000, (b.lat - a.lat) * 111000) * 180 / Math.PI + 360) % 360;
}

var blazeLayer = L.layerGroup();
// Stripes first, so dots and blazes sharing the stretch show on top
trailData.features.forEach(function(f, ti) {
  (f.properties.blazes || []).forEach(function(r) {
    var b = REGION.blazes[r[0]];
    if (b.style === "arrows") {
      var pts = sliceTrail(ti, r[1], r[2]);
      blazeLayer.addLayer(L.polyline(pts, {color: "#333", weight: 7, opacity: 0.9, interactive: false}));
      blazeLayer.addLayer(L.polyline(pts, {color: b.color, weight: 4, opacity: 1, interactive: false}));
    }
  });
});
trailData.features.forEach(function(f, ti) {
  // Blazes sharing a stretch take turns along it, each a step on from the one before
  var keysHere = blazeKeys.filter(function(k) { return (f.properties.blazes || []).some(function(r) { return r[0] === k; }); });
  (f.properties.blazes || []).forEach(function(r) {
    var b = REGION.blazes[r[0]], pts = sliceTrail(ti, r[1], r[2]);
    var rect = b.style === "blazes";
    var line = {dashArray: rect ? "4,12" : "0.1,10", dashOffset: String(keysHere.indexOf(r[0]) * 5),
                lineCap: rect ? "butt" : "round", interactive: false, opacity: 1};
    if (b.style !== "arrows") {
      blazeLayer.addLayer(L.polyline(pts, L.extend({}, line, {color: rect ? "#fff" : "#333", weight: rect ? 8 : 5})));
      blazeLayer.addLayer(L.polyline(pts, L.extend({}, line, {color: b.color, weight: rect ? 5 : 4})));
    }
    if (r[3]) {
      for (var s = r[1] + 60; s < r[2] - 20; s += BLAZE_ARROW_M) {
        blazeArrows.addLayer(L.marker(pointAlong(ti, s), {icon: blazeArrowIcon(b.color, bearingAlong(ti, s) + (r[3] < 0 ? 180 : 0)),
                                                          interactive: false, keyboard: false}));
      }
    }
  });
});
if (blazeKeys.length) {
  blazeLayer.addTo(map);
  var showBlazeArrows = function() {
    if (map.getZoom() >= BLAZE_ARROW_ZOOM) blazeArrows.addTo(map);
    else blazeArrows.remove();
  };
  map.on("zoomend", showBlazeArrows);
  showBlazeArrows();
  var legendPanel = document.querySelector(".legend-panel");
  blazeKeys.forEach(function(k) {
    var b = REGION.blazes[k];
    legendPanel.insertAdjacentHTML("beforeend", '<div class="legend-row">' + blazeMarkSvg(k) + '&nbsp; ' + esc(b.name) +
      (b.one_way ? ' (one way)' : '') + '</div>');
  });
}

// The legend shows with the home panel (the welcome, or where you are) and steps aside for
// everything else (trails, intersections, routes), which would run down under it; and in
// any case if the panel reaches it
function fitLegend() {
  var legend = document.querySelector(".legend-panel"), panel = document.getElementById("infoPanel");
  if (!legend || !panel) return;
  var home = !!document.querySelector("#infoContent #welcomeInfo, #infoContent #locateInfo");
  legend.style.visibility = "";
  var a = legend.getBoundingClientRect(), b = panel.getBoundingClientRect();
  var overlap = a.width && b.width && a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  legend.style.visibility = home && !overlap ? "" : "hidden";
}
// The legend can be folded away to just its heading; the browser remembers which
var LEGEND_KEY = REGION.storagePrefix + "LegendCollapsed";
function setLegendCollapsed(collapsed) {
  var legend = document.querySelector(".legend-panel");
  legend.classList.toggle("collapsed", collapsed);
  legend.querySelector(".legend-caret").textContent = collapsed ? "▸" : "▾";
  try { localStorage.setItem(LEGEND_KEY, collapsed ? "1" : ""); } catch (e) {}
  fitLegend();
}
function toggleLegend() { setLegendCollapsed(!document.querySelector(".legend-panel").classList.contains("collapsed")); }
try { if (localStorage.getItem(LEGEND_KEY)) setLegendCollapsed(true); } catch (e) {}
if (window.ResizeObserver) new ResizeObserver(fitLegend).observe(document.getElementById("infoPanel"));
if (window.MutationObserver) new MutationObserver(fitLegend).observe(document.getElementById("infoContent"), {childList: true});
window.addEventListener("resize", fitLegend);
fitLegend();

// The blazes along trail ti from a to b (meters along it): those covering most of it.
// against: a one-way blaze marked the other way, so its marks face away from you.
function blazesOn(ti, a, b) {
  var lo = Math.min(a, b), hi = Math.max(a, b), out = [];
  (trailData.features[ti].properties.blazes || []).forEach(function(r) {
    var cover = Math.min(hi, r[2]) - Math.max(lo, r[1]);
    if (cover >= 0.5 * (hi - lo) && out.every(function(o) { return o.key !== r[0]; })) {
      out.push({key: r[0], against: !!r[3] && (b > a) !== (r[3] > 0)});
    }
  });
  return out;
}

// --- Terrain (REGION.widths, REGION.terrain). A trail's widths are [width, from m, to m]
// stretches. A wide trail or road is easy; a narrow one is rougher, and how rough depends
// on its blaze (REGION.blazes terrain): a narrow stretch of the Skyline is the roughest.
function widthOn(ti, a, b) {
  var lo = Math.min(a, b), hi = Math.max(a, b), best = null, most = 0;
  (trailData.features[ti].properties.widths || []).forEach(function(r) {
    var cover = Math.min(hi, r[2]) - Math.max(lo, r[1]);
    if (lo === hi ? lo >= r[1] && lo <= r[2] : cover > most) { best = r[0]; most = cover; }
  });
  return best;
}

// The terrain from a to b along trail ti, as an index into REGION.terrain, or null if unknown
function terrainOn(ti, a, b) {
  var width = widthOn(ti, a, b);
  if (!width) return null;
  if (width !== "narrow") return 0;
  return blazesOn(ti, a, b).reduce(function(t, o) { return Math.max(t, REGION.blazes[o.key].terrain || 0); }, 1);
}

// Four rising bars, as many dark as the terrain is rough
function terrainSvg(level) {
  var bars = '';
  for (var i = 0; i < 4; i++) {
    bars += '<rect x="' + (i * 4) + '" y="' + (9 - 3 * i) + '" width="3" height="' + (3 + 3 * i) + '" fill="' + (i <= level ? '#37474f' : '#cfd8dc') + '"/>';
  }
  return '<svg width="15" height="12" viewBox="0 0 15 12" style="vertical-align:middle;flex:none">' + bars + '</svg>';
}

function terrainHtml(level) {
  return terrainSvg(level) + ' ' + esc(REGION.terrain[level]);
}

// How much of the route ahead is each kind of terrain: "1.2 mi Easy · 0.3 mi Difficult"
function routeTerrainHtml() {
  var len = [];
  plan.steps.forEach(function(s, i) {
    var next = plan.steps[i + 1];
    var e = next && stepState(i + 1) !== "passed" && routeEdge(s.label, next.label, next.trail);
    var t = e ? terrainOn(e.ti, e.a, e.b) : null;
    if (t !== null) len[t] = (len[t] || 0) + Math.abs(e.b - e.a);
  });
  var parts = [];
  for (var t = len.length - 1; t >= 0; t--) {
    if (len[t]) parts.push(terrainSvg(t) + ' ' + formatDist(len[t]) + ' ' + esc(REGION.terrain[t].toLowerCase()));
  }
  return parts.length ? '<div class="route-terrain full-only">' + parts.join(' &nbsp;·&nbsp; ') + '</div>' : '';
}

// --- Elevation (REGION.eleStep). A trail's ele is its elevation in meters every eleStep
// along it, and at its end (USGS 3D Elevation Program lidar). Routes show their climb and
// an elevation profile, steep legs are flagged, and trail details give the climb between
// intersections.
var GRADE_SPAN_M = 50;   // steepness is measured over this distance, so a rock isn't a cliff
var CLIMB_MIN_M = 1;     // rises and dips smaller than this are noise
var STEEP_LEG = 0.10;    // a leg with a stretch this steep is flagged in route steps
var STEEPNESS = [[0.04, "Flat"], [0.08, "Gentle"], [0.15, "Steep"], [Infinity, "Very steep"]];

function eleAt(ti, s) {
  var e = trailData.features[ti].properties.ele, step = REGION.eleStep;
  if (!e || !step) return null;
  var total = trailCum[ti][trailCum[ti].length - 1];
  s = Math.max(0, Math.min(s, total));
  var i = Math.min(Math.floor(s / step), e.length - 2);
  if (i < 0) return e[0];
  var s1 = Math.min((i + 1) * step, total);
  var t = s1 > i * step ? (s - i * step) / (s1 - i * step) : 0;
  return e[i] + Math.max(0, Math.min(1, t)) * (e[i + 1] - e[i]);
}

// [[meters from a, elevation]] along trail ti from a to b
function eleProfile(ti, a, b) {
  var len = Math.abs(b - a), n = Math.max(1, Math.ceil(len / REGION.eleStep)), out = [];
  for (var k = 0; k <= n; k++) {
    var e = eleAt(ti, a + (b - a) * k / n);
    if (e === null) return [];
    out.push([len * k / n, e]);
  }
  return out;
}

// Total climb and descent (meters), and the steepest stretch up and down (as grades)
function climbStats(pts) {
  var up = 0, down = 0, maxUp = 0, maxDown = 0, ref = pts.length ? pts[0][1] : 0;
  for (var i = 0; i < pts.length; i++) {
    // A break (null) between branches: start again after it
    if (pts[i] === null) { if (pts[i + 1]) ref = pts[i + 1][1]; continue; }
    var d = pts[i][1] - ref;
    if (d >= CLIMB_MIN_M) { up += d; ref = pts[i][1]; }
    else if (d <= -CLIMB_MIN_M) { down -= d; ref = pts[i][1]; }
    for (var j = i + 1; j < pts.length && pts[j] !== null; j++) {
      var run = pts[j][0] - pts[i][0];
      // Over GRADE_SPAN_M, or the whole of a shorter stretch (if it's not tiny)
      if (run >= GRADE_SPAN_M || ((j === pts.length - 1 || pts[j + 1] === null) && i === 0 && run >= 20)) {
        var g = (pts[j][1] - pts[i][1]) / run;
        maxUp = Math.max(maxUp, g);
        maxDown = Math.max(maxDown, -g);
        break;
      }
    }
  }
  return {up: up, down: down, maxUp: maxUp, maxDown: maxDown};
}

function steepness(grade) {
  for (var i = 0; i < STEEPNESS.length; i++) if (grade < STEEPNESS[i][0]) return STEEPNESS[i][1];
}

function feet(m) { return Math.round(m * 3.28084).toLocaleString() + " ft"; }

function climbHtml(st) {
  return '↑ ' + feet(st.up) + ' &nbsp;↓ ' + feet(st.down);
}

// An elevation profile: the ground in grey, its steep stretches in red, and where you are
// (meters along it), if given. A null in pts breaks it (between a trail's branches).
function profileSvg(pts, here) {
  if (pts.length < 2) return '';
  var real = pts.filter(function(p) { return p !== null; });
  var W = 280, H = 54, total = real[real.length - 1][0] || 1;
  var lo = Infinity, hi = -Infinity;
  real.forEach(function(p) { lo = Math.min(lo, p[1]); hi = Math.max(hi, p[1]); });
  // At least 15 m of height, so a flat walk looks flat
  if (hi - lo < 15) { var mid = (hi + lo) / 2; lo = mid - 7.5; hi = mid + 7.5; }
  var x = function(d) { return (d / total * (W - 2) + 1).toFixed(1); };
  var y = function(e) { return (H - 3 - (e - lo) / (hi - lo) * (H - 8)).toFixed(1); };
  var runs = [[]];
  pts.forEach(function(p) { if (p === null) runs.push([]); else runs[runs.length - 1].push(p); });
  var ground = runs.filter(function(r) { return r.length > 1; }).map(function(r) {
    var line = r.map(function(p) { return x(p[0]) + ',' + y(p[1]); }).join(' ');
    return '<polygon points="' + x(r[0][0]) + ',' + H + ' ' + line + ' ' + x(r[r.length - 1][0]) + ',' + H + '" fill="#e0e4e7"/>' +
      '<polyline points="' + line + '" fill="none" stroke="#546e7a" stroke-width="1.5" vector-effect="non-scaling-stroke"/>';
  }).join('');
  var steep = '';
  for (var i = 0; i < pts.length - 1; i++) {
    if (pts[i] === null || pts[i + 1] === null) continue;
    // Each stretch's grade, over GRADE_SPAN_M around it
    var a = i, b = i + 1;
    while (a > 0 && pts[a - 1] !== null && pts[i][0] - pts[a][0] < GRADE_SPAN_M / 2) a--;
    while (b < pts.length - 1 && pts[b + 1] !== null && pts[b][0] - pts[i + 1][0] < GRADE_SPAN_M / 2) b++;
    var g = Math.abs(pts[b][1] - pts[a][1]) / ((pts[b][0] - pts[a][0]) || 1);
    if (g >= STEEPNESS[2][0]) {
      steep += '<line x1="' + x(pts[i][0]) + '" y1="' + y(pts[i][1]) + '" x2="' + x(pts[i + 1][0]) + '" y2="' + y(pts[i + 1][1]) + '"/>';
    }
  }
  var mark = here !== undefined && here !== null && here >= 0 && here <= total
    ? '<line x1="' + x(here) + '" y1="0" x2="' + x(here) + '" y2="' + H + '" stroke="#0d47a1" stroke-width="2" vector-effect="non-scaling-stroke"/>' : '';
  return '<svg class="ele-profile" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' +
    ground + '<g stroke="#c62828" stroke-width="2.5" vector-effect="non-scaling-stroke">' + steep + '</g>' + mark + '</svg>' +
    '<div class="ele-range"><span>' + feet(lo) + '</span><span>' + feet(hi) + '</span></div>';
}

// The route's elevation profile, from its first intersection
function routeProfile() {
  var pts = [], off = 0;
  plan.steps.forEach(function(s, i) {
    var next = plan.steps[i + 1];
    var e = next && routeEdge(s.label, next.label, next.trail);
    if (!e) return;
    var leg = eleProfile(e.ti, e.a, e.b);
    if (!leg.length && pts.length && pts[pts.length - 1] !== null) pts.push(null);
    leg.forEach(function(p, k) { if (k || !pts.length || pts[pts.length - 1] === null) pts.push([off + p[0], p[1]]); });
    off += Math.abs(e.b - e.a);
  });
  return pts;
}

function routeEleHtml() {
  if (!REGION.eleStep) return '';
  var pts = routeProfile();
  if (pts.length < 2) return '';
  var here = plan.live && plan.progress !== null ? plan.progress - plan.steps[0].at : null;
  return '<div class="route-ele full-only"><div>' + climbHtml(climbStats(pts)) + '</div>' + profileSvg(pts, here) + '</div>';
}

// A route step's flag for a steep leg: "↑12%" or "↓14%"
function gradeTagHtml(st) {
  if (!st || Math.max(st.maxUp, st.maxDown) < STEEP_LEG) return '';
  var upHill = st.maxUp >= st.maxDown, pct = Math.round(100 * Math.max(st.maxUp, st.maxDown));
  return '<span class="grade-tag" title="Steepest stretch: ' + pct + '% ' + (upHill ? 'up' : 'down') + '">' +
    (upHill ? '↑' : '↓') + pct + '%</span>';
}

function blazeChipsHtml(list) {
  return list.map(function(o) {
    var b = REGION.blazes[o.key];
    return '<span class="blaze-chip' + (o.against ? ' against' : '') + '" title="' + esc(b.name + ': ' + b.marks +
      (o.against ? ', marked the other way' : '')) + '">' + blazeMarkSvg(o.key) + '</span>';
  }).join('');
}

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
  Object.keys(intMarkers).filter(function(l) { return !isJunction(l); }).forEach(function(label) {
    var d = ll.distanceTo(intMarkers[label].getLatLng());
    if (d < bestD) { bestD = d; best = label; }
  });
  return {label: best, dist: bestD};
}

var SNAP_M = 60;     // farther than this from every trail counts as off trail
var ON_TRAILS_M = 300;   // this close to a trail, the map opens on you
var AT_INT_M = 20;   // this close to an intersection counts as being at it

// Nearest point on trail ti: {d, ti, along, tan}, with tan the compass bearing of the
// trail there, pointing toward increasing "along"
function snapOnTrail(ll, ti) {
  var px = ll.lng * 82000, py = ll.lat * 111000, best = {d: Infinity};
  var c = flatCoords(trailData.features[ti].geometry), cum = trailCum[ti];
  for (var i = 0; i < c.length - 1; i++) {
    var ax = c[i][0] * 82000, ay = c[i][1] * 111000;
    var vx = c[i + 1][0] * 82000 - ax, vy = c[i + 1][1] * 111000 - ay;
    var len2 = vx * vx + vy * vy;
    var t = len2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * vx + (py - ay) * vy) / len2)) : 0;
    var d = Math.hypot(px - ax - t * vx, py - ay - t * vy);
    if (d < best.d) {
      best = {d: d, ti: ti, along: cum[i] + t * (cum[i + 1] - cum[i]),
              tan: (Math.atan2(vx, vy) * 180 / Math.PI + 360) % 360};
    }
  }
  return best;
}

// Nearest point on any trail: distance to it, which trail, how far along it, and its name
function snapToTrail(ll) {
  var best = {d: Infinity};
  trailData.features.forEach(function(f, ti) {
    var s = snapOnTrail(ll, ti);
    if (s.d < best.d) best = s;
  });
  if (best.d < Infinity) {
    var props = trailData.features[best.ti].properties;
    best.name = props.pdf_name || props.name || "Unnamed";
  }
  return best;
}

// Intersections on either side of a snapped point along its trail, as [label, along]
// (either may be null). With signed, it goes on through unsigned junctions to the next
// sign, and chain lists the places from before to after.
function segmentEnds(snap, signed) {
  var ints = trailIntMap[snap.ti].ints, iB = -1, iA = -1;
  ints.forEach(function(e, k) { if (e[1] <= snap.along) iB = k; if (e[1] > snap.along && iA < 0) iA = k; });
  if (signed) {
    while (iB > 0 && isJunction(ints[iB][0])) iB--;
    while (iA >= 0 && iA < ints.length - 1 && isJunction(ints[iA][0])) iA++;
  }
  return {before: iB >= 0 ? ints[iB] : null, after: iA >= 0 ? ints[iA] : null,
          chain: iB >= 0 && iA >= 0 ? ints.slice(iB, iA + 1).map(function(e) { return e[0]; }) : []};
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

// The best route from where you are: the anchor with the lowest routing cost, and its
// route; total is the distance in meters. anchors (optional): userAnchors(userLatLng),
// when asking about several destinations.
function bestRouteFromMe(destLabel, anchors) {
  var best = null;
  (anchors || userAnchors(userLatLng)).forEach(function(a) {
    var r = dijkstra(a.label, destLabel), cost = a.dist + pathTree(a.label).dist[destLabel];
    if (r && (!best || cost < best.cost)) {
      best = {anchor: a, result: r, total: a.dist + r.totalDist, cost: cost};
    }
  });
  return best;
}

function routeFromMe(destLabel) {
  if (awayFromTrails()) {
    pickEntrance(destLabel, false);
  } else if (userLatLng.distanceTo(intMarkers[destLabel].getLatLng()) <= AT_INT_M) {
    showPanelMsg('You are already at ' + intPill(destLabel));
  } else {
    startTrip(newTrip(null, [], destLabel), 'No route found from your location to <strong>' + intName(destLabel) + '</strong>.');
  }
}

// state (optional): "passed" greys the pill, "here" rings it. A place with no sign (a
// post, a landmark, a parking lot) is its small map icon, with its name beside it in the
// large view only.
function intPill(label, state) {
  return pillIcon(label, state) + pillName(label, state);
}

function isSignless(p) { return !!(p.landmark || p.lot || p.no_sign); }

// The pill, or a signless place's icon, alone
function pillIcon(label, state) {
  var p = intFeatures[label].properties;
  if (p.shape) {
    return '<a class="int-link shape-pill' + (state === "passed" || state === "here" ? ' ' + state : '') + '" title="' + esc(intName(label)) +
      '" onmouseover="hoverInt(' + jsArg(label) + ')" onmouseout="unhover()" onclick="selectIntFromTrail(' + jsArg(label) + ')">' + junctionIconHtml(label, 26) + '</a>';
  }
  if (p.junction) {
    return '<span class="junction-dot' + (state === "passed" ? ' passed' : '') + '" title="Unmarked junction"></span>';
  }
  var cls = (isSignless(p) ? ' icon-pill' : '') + (state === "passed" || state === "here" ? ' ' + state : '');
  var bg = isSignless(p) ? 'transparent' : ZONE_COLORS[p.zone];
  return '<a class="int-link' + cls + '" style="background:' + bg + '" title="' + esc(intName(label)) + '" onmouseover="hoverInt(\'' + label + '\')" onmouseout="unhover()" onclick="selectIntFromTrail(\'' + label + '\')">' +
    (p.landmark ? rockSvg(18) : p.lot ? lotBadgeHtml() : p.no_sign ? postBadgeHtml(p.post) : intName(label)) + '</a>';
}

// A signless place's name, for beside its icon (large view only)
function pillName(label, state) {
  var p = intFeatures[label].properties;
  return p.junction || !isSignless(p) ? ''
    : '<span class="rock-name full-only' + (state === "passed" ? ' passed' : '') + '">' + esc(intName(label)) + '</span>';
}

// Where the user is: at an intersection, on a segment between two ends, or off trail
function userPlace(ll) {
  var n = nearestInt(ll);
  if (n.dist <= AT_INT_M) return {type: "at", label: n.label};
  var snap = snapToTrail(ll);
  if (snap.d >= SNAP_M) return {type: "off", label: n.label, dist: n.dist};

  // The strip runs between signs: unsigned junctions on the way aren't shown
  var ends = segmentEnds(snap, true);
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

var ROUGH_FIX_M = 300;   // a fix this vague means the phone is only sharing a rough area

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
  else if (!awayFromTrails()) html += exitsHtml();
  else html += driveLinkHtml();
  // (Only on phones: a computer without GPS is always this vague, and has no such setting)
  if (userAccuracy > ROUGH_FIX_M && (IS_IOS || /Android/.test(navigator.userAgent))) {
    html += '<div class="estimated-tag" style="margin-top:6px">Your phone is only sharing a rough location (within ' +
      formatDist(userAccuracy) + '). Turning on Precise Location fixes that. ' + HELP_LINK + '</div>';
  }
  html += reportLinkHtml("here", "");
  return '<div id="locateInfo">' + html + '</div>';
}

var ENTRY_NEAR_M = 60;   // crumbs this close to an entry point count as passing it
var showAllExits = false;

// --- Directions to an entrance: the entrances you can get to by road (with parking, or a
// road-end like C12's; drive_to is where to go), nearest first. Tapping one hands it to
// the phone: on Android a geo: link, which opens your default maps app or asks which
// (Maps, Waze, ...); on iPhones, which have no such chooser for websites, Apple Maps,
// Google Maps or Waze, as you pick (remembered); on a computer, Google Maps. The app
// picks walking or driving. Share sends the place to any app (messages, the car, ...).
var NAV_KEY = REGION.storagePrefix + "NavApp";
var DRIVE_CHOICES = 8;   // nearest entrances listed before "More"
var IS_ANDROID = /Android/.test(navigator.userAgent);
var NAV_APPS = {apple: "Apple Maps", google: "Google Maps", waze: "Waze"};

function navApp() {
  var pick = null;
  try { pick = localStorage.getItem(NAV_KEY); } catch (e) {}
  return NAV_APPS[pick] ? pick : "apple";
}

function setNavApp(app) {
  try { localStorage.setItem(NAV_KEY, app); } catch (e) {}
  showDriveList(driveListAll);
}

function driveLatLng(label) {
  var p = intFeatures[label].properties;
  return p.drive_to ? L.latLng(p.drive_to[1], p.drive_to[0]) : intMarkers[label].getLatLng();
}

function placeName(label) {
  var p = intFeatures[label].properties;
  return p.parking_name || p.lot || p.connects_short || p.connects || intName(label);
}

function googleMapsUrl(label) {
  var ll = driveLatLng(label);
  return "https://www.google.com/maps/dir/?api=1&destination=" + ll.lat.toFixed(6) + "," + ll.lng.toFixed(6);
}

function directionsUrl(label) {
  var ll = driveLatLng(label), at = ll.lat.toFixed(6) + "," + ll.lng.toFixed(6);
  // (the name's own parentheses encoded, as the label is wrapped in them)
  if (IS_ANDROID) return "geo:" + at + "?q=" + at + "(" + encodeURIComponent(placeName(label)).replace(/\(/g, "%28").replace(/\)/g, "%29") + ")";
  if (!IS_IOS) return googleMapsUrl(label);
  var app = navApp();
  return app === "google" ? googleMapsUrl(label)
    : app === "waze" ? "https://waze.com/ul?ll=" + at + "&navigate=yes"
    : "https://maps.apple.com/?daddr=" + at;
}

// The phone's share sheet (or, without one, the link copied)
function shareEntrance(label) {
  var name = placeName(label), url = googleMapsUrl(label);
  if (navigator.share) {
    navigator.share({title: name, text: name + " (" + REGION.name + ")", url: url}).catch(function() {});
  } else if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(function() { showPanelMsg("Copied a map link to " + esc(name) + "."); });
  } else {
    window.prompt("Map link to " + name + ":", url);
  }
}

var driveListAll = false;
function showDriveList(all) {
  driveListAll = !!all;
  clearSelection(true);
  // Nearest you first; without your location, nearest the middle of the map (no distances)
  var from = userLatLng || map.getCenter();
  var places = entryLabels().filter(function(l) {
    var p = intFeatures[l].properties;
    return p.parking || p.drive_to;
  }).map(function(l) {
    return {label: l, d: from.distanceTo(driveLatLng(l)), dist: userLatLng ? userLatLng.distanceTo(driveLatLng(l)) : null};
  });
  places.sort(function(a, b) { return a.d - b.d; });
  all = all || places.length <= DRIVE_CHOICES + 1;   // "More" for just one more isn't worth it
  var opens = IS_ANDROID ? "your maps app" : IS_IOS ? NAV_APPS[navApp()] : "Google Maps";
  var html = '<div class="route-msg" style="margin-top:0">Directions to an entrance' +
    '<div style="font-size:12px;color:#666;margin-top:2px">Tap one for directions in ' + opens + ', or share it.</div></div><div class="exits">';
  places.slice(0, all ? places.length : DRIVE_CHOICES).forEach(function(o) {
    html += '<div class="drive-row"><a class="exit-btn" href="' + esc(directionsUrl(o.label)) + '"' + (IS_ANDROID ? '' : ' target="_blank" rel="noopener"') + '>' +
      entryChipHtml(o.label) + (o.dist !== null ? '<span class="exit-dist">' + formatDist(o.dist) + '</span>' : '') +
      parkSlotHtml(o.label) +
      '<span class="exit-note">' + esc(placeName(o.label)) + '</span></a>' +
      '<button class="share-btn" title="Share" aria-label="Share" onclick="shareEntrance(' + jsArg(o.label) + ')">' + SHARE_ICON + '</button></div>';
  });
  if (!all && places.length > DRIVE_CHOICES) {
    html += '<div class="plan-link"><a onclick="showDriveList(true)">More entrances (' + (places.length - DRIVE_CHOICES) + ')</a></div>';
  }
  html += '</div>';
  if (IS_IOS) {
    html += '<div class="plan-link">Open in: ' + Object.keys(NAV_APPS).map(function(k) {
      return k === navApp() ? '<strong>' + NAV_APPS[k] + '</strong>' : '<a onclick="setNavApp(\'' + k + '\')">' + NAV_APPS[k] + '</a>';
    }).join(' · ') + '</div>';
  }
  html += '<div style="margin-top:8px"><button class="route-btn" style="background:#888" onclick="clearSelection();showHome()">Back</button></div>';
  document.getElementById("infoContent").innerHTML = html;
}

var SHARE_ICON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
  '<path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>';

function driveLinkHtml() {
  return '<div class="plan-link"><a onclick="showDriveList()">Directions to an entrance</a></div>';
}

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
    entryChipHtml(e.label) +
    '<span class="exit-dist">' + formatDist(e.dist) + '</span>' +
    parkSlotHtml(e.label) +
    entryNoteHtml(e.label, "to") + '</button>';
}

// Large view only, when not navigating and out on the trails: quick routes out to the
// entry points
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
var CRUMB_KEY = REGION.storagePrefix + "Crumbs";
var crumbs = [];
try { crumbs = JSON.parse(sessionStorage.getItem(CRUMB_KEY)) || []; } catch (e) { crumbs = []; }
// Each outing starts fresh. The phone stops tracking whenever the screen is off, so a gap
// alone doesn't mean you left; these are the signs that you did:
var FIX_KEY = REGION.storagePrefix + "LastFix";   // time and place of the last fix, across reloads
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

// Time since the fix before this one; a long one means the phone stopped reporting
var fixGapMs = 0;

// Called with each fix, before it is added as a crumb. The place rules only trust fixes
// good enough to tell: a rough fix can land a kilometer off, or near an entry you aren't at.
// Stopping near an exit only counts if you also come back near one (the same lot or
// another); otherwise it was probably a glance at the phone while walking past.
function checkFreshStart(ll, acc) {
  var last = readLastFix();
  var gap = last ? Date.now() - last.t : Infinity;
  fixGapMs = gap;
  var left = distFromNetwork(ll) - acc > FAR_FROM_NETWORK_M || gap >= NEW_DAY_GAP_MS ||
    (gap >= EXIT_GAP_MS && last.acc <= EXIT_NEAR_M && acc <= EXIT_NEAR_M &&
     nearEntry(L.latLng(last.lat, last.lng), EXIT_NEAR_M) && nearEntry(ll, EXIT_NEAR_M));
  if (crumbs.length && left) clearCrumbs();
  if (left && !plan) {
    pendingTrip = null;
    try { sessionStorage.removeItem(TRIP_KEY); } catch (e) {}
  }
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

// The phone stops reporting while the screen is off, leaving gaps in the crumbs. Rather
// than cut across the woods, fill a gap with the shortest way along the trails.
var CRUMB_GAP_M = 30;   // farther apart than this counts as a gap
// Only fill where the phone went quiet: GPS jitter while standing still can put a crumb
// on a neighboring trail, and a filled route there would be a phantom loop
var CRUMB_QUIET_MS = 20 * 1000;

// Trail points from a to b along the shortest trail route, or null to draw a straight line
function trailPathBetween(a, b) {
  var sa = snapToTrail(a), sb = snapToTrail(b);
  var best = null;
  if (sa.d < SNAP_M && sb.d < SNAP_M) {
    if (sa.ti === sb.ti) {
      best = {len: Math.abs(sa.along - sb.along), pts: sliceTrail(sa.ti, sa.along, sb.along)};
    }
    var endsA = segmentEnds(sa), endsB = segmentEnds(sb);
    [endsA.before, endsA.after].forEach(function(ea) {
      [endsB.before, endsB.after].forEach(function(eb) {
        var mid = ea && eb && pathTree(ea[0]).len[eb[0]] !== undefined ? pathTree(ea[0]).len[eb[0]] : Infinity;
        var len = mid < Infinity ? Math.abs(sa.along - ea[1]) + mid + Math.abs(sb.along - eb[1]) : Infinity;
        if (len < (best ? best.len : Infinity)) best = {len: len, ea: ea, eb: eb};
      });
    });
    if (best && !best.pts) {
      var pts = sliceTrail(sa.ti, sa.along, best.ea[1]);
      var path = dijkstra(best.ea[0], best.eb[0]).path;
      for (var k = 0; k < path.length - 1; k++) {
        var e = routeEdge(path[k].label, path[k + 1].label, path[k + 1].trail);
        pts = pts.concat(e ? sliceTrail(e.ti, e.a, e.b) : [intMarkers[path[k + 1].label].getLatLng()]);
      }
      best.pts = pts.concat(sliceTrail(sb.ti, best.eb[1], sb.along));
    }
    // A trail route far longer than the gap probably isn't what happened; cut across instead
    var straight = a.distanceTo(b);
    if (best && best.len > Math.max(3 * straight, straight + 400)) best = null;
  }
  return best ? best.pts : null;
}

// crumbFills[i]: trail points between crumbs[i - 1] and crumbs[i], or null.
// A crumb's 4th element is 1 when the phone was quiet just before it.
function crumbFill(i) {
  var a = L.latLng(crumbs[i - 1][0], crumbs[i - 1][1]), b = L.latLng(crumbs[i][0], crumbs[i][1]);
  return crumbs[i][3] && a.distanceTo(b) > CRUMB_GAP_M ? trailPathBetween(a, b) : null;
}
var crumbFills = crumbs.map(function(c, i) { return i > 0 ? crumbFill(i) : null; });

function crumbLatLngs() {
  var out = [];
  crumbs.forEach(function(c, i) {
    if (crumbFills[i]) out.push.apply(out, crumbFills[i]);
    out.push([c[0], c[1]]);
  });
  return out;
}

var crumbLine = L.polyline(crumbLatLngs(), {
  color: "#1e88e5", weight: 4, opacity: 0.6, dashArray: "1,8", lineCap: "round", interactive: false
}).addTo(map);

function addCrumb(ll, acc) {
  var last = crumbs.length ? L.latLng(crumbs[crumbs.length - 1]) : null;
  if (acc <= 40 && (!last || last.distanceTo(ll) >= 5) && distFromNetwork(ll) <= FAR_FROM_NETWORK_M) {
    var crumb = [+ll.lat.toFixed(6), +ll.lng.toFixed(6), Date.now()];
    if (fixGapMs >= CRUMB_QUIET_MS) crumb.push(1);
    crumbs.push(crumb);
    crumbFills.push(crumbs.length > 1 ? crumbFill(crumbs.length - 1) : null);
    if (crumbs.length > 5000) {
      crumbs.shift();
      crumbFills.shift();
      crumbFills[0] = null;
      if (entranceScanned > 0) entranceScanned--;
    }
    crumbLine.setLatLngs(crumbLatLngs());
    try { sessionStorage.setItem(CRUMB_KEY, JSON.stringify(crumbs)); } catch (e) {}
  }
}

function clearCrumbs() {
  crumbs = [];
  crumbFills = [];
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
  if (pendingTrip) {
    var resumed = pendingTrip;
    pendingTrip = null;
    locateRequested = false;   // the route panel, not "You are at"
    startTrip(resumed, "Couldn't pick up your route from here.");
  }
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
    else if (document.getElementById("welcomeInfo")) showHome();
    // Jump to you only if you're out on the trails: the network's bounding box takes in
    // whole neighborhoods, and opening the map at home shouldn't zoom to your house
    if (!targetInt && snapToTrail(userLatLng).d <= ON_TRAILS_M) map.setView(userLatLng, 16);
  } else if (liveRouting()) {
    updateLiveRoute();
  } else {
    refreshLocateInfo();
  }
  if (following) map.panTo(userLatLng);
}

// iPhones and iPads (an iPad can say it's a Mac): their location settings are the
// hardest to find, so they get the steps right in the panel
var IS_IOS = /iPhone|iPad|iPod/.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
var HELP_LINK = '<a href="location-help.html' + (IS_IOS ? '#iphone' : '') + '">How to turn on location</a>';

function onLocationError(err) {
  if (err.code === 1 && watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }
  if (locateRequested) {
    locateRequested = false;
    if (err.code === 1 && IS_IOS) {
      showPanelMsg("Your iPhone isn't letting this site use your location. Check all three:" +
        '<ol style="margin:6px 0 6px 18px;padding:0">' +
        '<li><b>Settings › Privacy &amp; Security › Location Services</b>: on</li>' +
        '<li>Same screen, <b>Safari Websites</b>: While Using the App, with Precise Location on</li>' +
        '<li>In Safari, tap <b>aA</b> in the address bar › Website Settings › Location: Allow</li></ol>' +
        'Then reload and tap the locate button. ' + HELP_LINK + '.');
    } else {
      showPanelMsg((err.code === 1
        ? "Location access is blocked for this site."
        : "Couldn't get your location. Out in the woods it can take a minute; try again.") + " " + HELP_LINK);
    }
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

// A route you had going before leaving the map: a planned one comes straight back; a
// live one (from where you are) once your location is known
(function() {
  var trip = targetInt ? null : savedTrip();
  if (!trip) return;
  if (trip.from !== null && trip.from !== undefined) {
    startTrip(trip, "Couldn't bring back your route.");
  } else {
    pendingTrip = trip;
    locateRequested = true;   // if your location can't be had, say why (and how to fix it)
    showPanelMsg("Picking up your route…");
    startWatch();
  }
})();

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
      m.setStyle(restStyle(m));
    }
  });
  searchHighlighted = [];
}

function applySearch() {
  searchHighlighted.forEach(function(label) {
    var m = intMarkers[label];
    if (m && m !== selectedMarker) {
      var z = m._zone;
      m.setStyle(restStyle(m));
    }
  });
  searchHighlighted = [];

  var matches = Object.keys(intMarkers).filter(function(label) {
    return label.toUpperCase().indexOf(searchBuf) === 0 && !isJunction(label);
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
      m.setStyle({radius: 11, weight: 3, color: "#f1c40f", fillColor: "#f1c40f", fillOpacity: 1, opacity: 1});
      m.bringToFront();
    }
  });
  searchHighlighted = matches;
}

document.addEventListener("keydown", function(e) {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
  var key = e.key.toUpperCase();

  // A zone key starts a label: any zone letter, or a zone digit when nothing's typed yet
  // (after that, digits carry on the number, as in 2070)
  if (ZONE_COLORS[key] && (searchBuf.length === 0 || !/^[0-9]$/.test(key))) {
    clearSearch();
    searchBuf = key;
    searchBadge.textContent = searchBuf;
    searchBadge.style.display = "block";
    applySearch();
    var zonePts = [];
    Object.keys(intMarkers).forEach(function(label) {
      var p = intFeatures[label].properties;
      if (p.zone === key && !p.no_sign) zonePts.push(intMarkers[label].getLatLng());
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
