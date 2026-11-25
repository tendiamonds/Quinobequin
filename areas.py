"""
The areas: every map on the site, in one list (areas.json, at the site's root) that each
map reads, and the Overview (overview.html) that shows them all with how far you are from
each. Each build adds its own area (write_area, called by trailmap.build_map_page), so the
list is always the maps as last built.

An area in areas.json:
  key, name, short   from trailmap.SITE_MAPS
  href               its map, from the site's root
  color              its icon's color, for its outline on the Overview
  icon               its app icon, from the site's root: the Overview marks the area with
                     it when zoomed out (DETAIL_ZOOM), where its parking would pile up
  outlines           [[[lat, lon], ...], ...]: around its trails, OUTLINE_MARGIN_M out, one
                     for each patch of trails (PATCH_GAP_M apart or more), the biggest
                     first. Inside one you're "in" the area (a map switches to it when you
                     walk in)
  outline            the first of them (as before there were patches, for a page from then)
  starts             [{"name", "lat", "lon"}]: where you'd start, its parking (or its
                     trailheads, if it has no parking marked): the Overview measures to these
"""

import json
import math
import os

PROJ = os.path.dirname(os.path.abspath(__file__))
AREAS_JSON = os.path.join(PROJ, "areas.json")
OVERVIEW_HTML = os.path.join(PROJ, "overview.html")

OUTLINE_MARGIN_M = 250   # the outline runs this far outside the outermost trails
PATCH_GAP_M = 1000       # trails this far from any other are a patch of their own


def _hull(pts):
    """Convex hull (Andrew's monotone chain) of (x, y) points, counterclockwise"""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _patches(lines, gap):
    """The lines ([(x, y), ...] in meters) in groups, by a grid of gap / 2 squares: lines
    with points in the same or neighboring squares are together (so about gap apart, give
    or take). Biggest group (most points) first."""
    cell = gap / 2
    owner = list(range(len(lines)))
    def root(i):
        while owner[i] != i:
            owner[i] = owner[owner[i]]
            i = owner[i]
        return i
    grid = {}
    for i, line in enumerate(lines):
        for x, y in line:
            grid.setdefault((int(x // cell), int(y // cell)), set()).add(i)
    for (cx, cy), here in grid.items():
        near = set(here)
        for key in ((cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            near |= grid.get(key, set())
        first = root(next(iter(near)))
        for j in near:
            owner[root(j)] = first
    groups = {}
    for i in range(len(lines)):
        groups.setdefault(root(i), []).extend(lines[i])
    return sorted(groups.values(), key=len, reverse=True)


def outlines(trails, margin_m=OUTLINE_MARGIN_M, gap_m=PATCH_GAP_M):
    """[[[lat, lon], ...], ...] around the trails, margin_m out, a ring for each patch of
    them (gap_m apart): the hull of a patch, with each corner widened into a circle and the
    hull taken again. The biggest patch first."""
    lines = []
    for f in trails["features"]:
        g = f["geometry"]
        lines.extend(g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]])
    lat0 = sum(c[1] for line in lines for c in line) / sum(len(line) for line in lines)
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110540   # meters per degree
    rings = []
    for pts in _patches([[(c[0] * kx, c[1] * ky) for c in line] for line in lines], gap_m):
        hull = _hull(pts)
        wide = [(x + margin_m * math.cos(a), y + margin_m * math.sin(a))
                for x, y in hull for a in (i * math.pi / 8 for i in range(16))]
        rings.append([[round(y / ky, 5), round(x / kx, 5)] for x, y in _hull(wide)])
    return rings


def starts(ints):
    """Where you'd start: the parking, or the trailheads if no parking is marked"""
    def pick(test):
        return [{"name": p.get("lot") or p.get("parking_name") or p.get("place_name") or ("Parking" if p.get("parking") else "Trailhead"),
                 "lat": round(f["geometry"]["coordinates"][1], 6), "lon": round(f["geometry"]["coordinates"][0], 6)}
                for f in ints["features"] for p in [f["properties"]] if test(p)]
    return pick(lambda p: p.get("lot") or p.get("parking_name") or p.get("parking")) or pick(lambda p: p.get("entry"))


def write_area(key, ints, trails):
    """Put this area in areas.json (replacing what it had), then rewrite the Overview"""
    from trailmap import SITE_MAPS, maps_menu_html
    site = {m[0]: m for m in SITE_MAPS}
    _, name, href, color = site[key][:4]
    areas = []
    if os.path.exists(AREAS_JSON):
        with open(AREAS_JSON, encoding="utf-8") as f:
            areas = [a for a in json.load(f) if a["key"] != key and a["key"] in site]
    folder = href.rsplit("/", 1)[0] + "/" if "/" in href else ""
    rings = outlines(trails)
    areas.append({"key": key, "name": site[key][4], "short": name, "href": href, "color": color,
                  "icon": folder + "icon-192.png", "outline": rings[0], "outlines": rings,
                  "starts": starts(ints)})
    order = [m[0] for m in SITE_MAPS]
    areas.sort(key=lambda a: order.index(a["key"]))
    with open(AREAS_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(areas, f, separators=(",", ":"))
        f.write("\n")
    page = (OVERVIEW_TEMPLATE.replace("__AREAS__", json.dumps(areas))
            .replace("__MENU__", maps_menu_html("overview", "")))
    with open(OVERVIEW_HTML, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print("Wrote areas.json (%s) and overview.html" % ", ".join(a["short"] for a in areas))


OVERVIEW_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="icon" href="favicon.ico" sizes="48x48">
<meta name="theme-color" content="#2c3e50">
<title>Trail maps — Overview</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  html, body { overflow: hidden; overscroll-behavior: none; }
  body { display: flex; flex-direction: column; }
  select { font-size: 16px; }
  a { color: #2980b9; text-decoration: none; }
  nav.topnav { background: #2c3e50; padding: 10px 20px; display: flex; gap: 18px; align-items: center; }
  @media (max-width: 420px) { nav.topnav { gap: 12px; padding: 10px 12px; } }
  nav.topnav .title { color: #ecf0f1; font-size: 15px; font-weight: 600; }
  #map { flex: 1; min-height: 0; }
  #list { background: #fff; padding: 10px 14px 14px; box-shadow: 0 -2px 8px rgba(0,0,0,0.15); max-height: 45vh; overflow-y: auto; }
  #list h2 { font-size: 15px; margin-bottom: 6px; color: #263238; }
  .area { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #eceff1; }
  .area:last-child { border-bottom: none; }
  .swatch { width: 32px; height: 32px; flex: none; }
  .area-icon { width: 40px; height: 40px; filter: drop-shadow(0 1px 3px rgba(0,0,0,0.45)); cursor: pointer; }
  .area-count { width: 40px; height: 40px; border-radius: 50%; background: #2c3e50; color: #fff; border: 3px solid #fff;
                font: 700 17px/34px sans-serif; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.45); cursor: pointer; }
  .area .what { flex: 1; min-width: 0; }
  .area .name { font-weight: 600; font-size: 15px; }
  .area .fine { font-size: 12px; color: #607d8b; }
  .btn { display: inline-block; border-radius: 6px; padding: 7px 10px; font-size: 13px; font-weight: 600; color: #fff; background: #1e88e5; }
  .btn.alt { background: #607d8b; }
  .note { font-size: 13px; color: #546e7a; margin: 4px 0 8px; }
  .user-dot { width: 16px; height: 16px; border-radius: 50%; background: #1e88e5; border: 3px solid #fff; box-shadow: 0 0 4px rgba(0,0,0,0.4); }
  .start-p { width: 15px; height: 15px; border-radius: 3px; background: #1565c0; color: #fff; font: 700 11px/15px sans-serif; text-align: center; }
</style>
</head>
<body>
<nav class="topnav"><span class="title">Trail maps</span>__MENU__</nav>
<div id="map"></div>
<div id="list"></div>
<script>
// Every map on the site (areas.py). The list under the map: once your location is known,
// the nearest maps, with how far each is (as the crow flies to its nearest start, its
// parking) and directions there: the nearest, and any others within NEAR_FACTOR times as
// far, LIST_MAX at most. Until then (or without it), the maps in view, as you move the map.
var AREAS = __AREAS__;
var NEAR_FACTOR = 3, LIST_MAX = 6;

function esc(s) { return String(s).replace(/[&<>"']/g, function(c) { return "&#" + c.charCodeAt(0) + ";"; }); }

function formatMiles(m) {
  var mi = m / 1609.34;
  return mi < 0.1 ? Math.round(m * 3.28084) + " ft" : mi < 10 ? mi.toFixed(1) + " mi" : Math.round(mi) + " mi";
}

var map = L.map("map", {zoomControl: true});
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

// Zoomed out, each area is its app icon (its parking would pile up in one spot), and
// icons that would overlap (closer than ICON_GAP_PX) are one circle saying how many
// maps are there: tapping it zooms in on them. From DETAIL_ZOOM in, each area's parking,
// each with directions.
var DETAIL_ZOOM = 12, ICON_GAP_PX = 44;
var icons = L.layerGroup(), parking = L.layerGroup();
var all = L.latLngBounds([]);
AREAS.forEach(function(a) {
  // Each patch of its trails a ring (one polygon for all); its icon sits on the biggest
  a.rings = a.outlines || [a.outline];
  var poly = L.polygon(a.rings.map(function(r) { return [r]; }), {color: a.color, weight: 2, fillColor: a.color, fillOpacity: 0.15}).addTo(map);
  poly.bindTooltip(esc(a.name), {sticky: true});
  poly.on("click", function() { location.href = a.href; });
  a.center = L.latLngBounds(a.rings[0]).getCenter();
  a.starts.forEach(function(s) {
    L.marker([s.lat, s.lon], {icon: L.divIcon({className: "", iconSize: [15, 15], html: '<div class="start-p">P</div>'}), title: s.name})
      .addTo(parking).bindPopup('<b>' + esc(a.name) + '</b><br>' + esc(s.name) +
        '<br><a href="' + directions(s) + '" target="_blank" rel="noopener">Directions</a>');
  });
  a.poly = poly;
  all.extend(poly.getBounds());
});
// The icons at this zoom: each area on its own, then the closest two (on the screen)
// merged, again and again, until none are closer than ICON_GAP_PX. A group sits at its
// members' middle, so merging can bring it near another, which then merges too.
function drawIcons() {
  icons.clearLayers();
  var groups = AREAS.map(function(a) { return {pt: map.project(a.center), areas: [a]}; });
  for (;;) {
    var best = null;
    for (var i = 0; i < groups.length; i++) {
      for (var j = i + 1; j < groups.length; j++) {
        var d = groups[i].pt.distanceTo(groups[j].pt);
        if (d < ICON_GAP_PX && (!best || d < best.d)) best = {i: i, j: j, d: d};
      }
    }
    if (!best) break;
    var gi = groups[best.i], gj = groups.splice(best.j, 1)[0], n = gi.areas.length, m = gj.areas.length;
    gi.pt = gi.pt.multiplyBy(n).add(gj.pt.multiplyBy(m)).divideBy(n + m);
    gi.areas = gi.areas.concat(gj.areas);
  }
  groups.forEach(function(g) {
    if (g.areas.length === 1) {
      var a = g.areas[0];
      L.marker(a.center, {
        icon: L.divIcon({className: "", iconSize: [40, 40], iconAnchor: [20, 20], html: '<img class="area-icon" src="' + a.icon + '" alt="">'}),
        title: a.name
      }).on("click", function() { location.href = a.href; }).addTo(icons);
    } else {
      var b = L.latLngBounds(g.areas.map(function(a) { return a.center; }));
      L.marker(map.unproject(g.pt), {
        icon: L.divIcon({className: "", iconSize: [40, 40], iconAnchor: [20, 20], html: '<div class="area-count">' + g.areas.length + '</div>'}),
        title: g.areas.map(function(a) { return a.name; }).join(", ")
      }).on("click", function() {
        g.areas.forEach(function(a) { b.extend(a.poly.getBounds()); });
        fitQuietly(b, {padding: [40, 40]});
      }).addTo(icons);
    }
  });
}

function showDetail() {
  var near = map.getZoom() >= DETAIL_ZOOM;
  if (near) { map.removeLayer(icons); parking.addTo(map); } else { map.removeLayer(parking); drawIcons(); icons.addTo(map); }
}
map.on("zoomend", showDetail);

// The list takes room from the map, so the map is told its size whenever the list
// changes (otherwise it's centered too low, behind the list)
function setList(html) {
  document.getElementById("list").innerHTML = html;
  map.invalidateSize({pan: !!handedView});   // (a view handed over keeps its middle)
}

// The maps whose outlines are in view (or in bounds), by name
var located = false, listNote = "";
function inViewList(bounds) {
  var seen = AREAS.filter(function(a) { return bounds.intersects(a.poly.getBounds()); })
    .sort(function(x, y) { return x.name < y.name ? -1 : 1; });
  var html = '<h2>' + (seen.length === AREAS.length ? 'The maps' : 'Maps in view: ' + seen.length + ' of ' + AREAS.length) + '</h2>' +
    (listNote ? '<div class="note">' + listNote + '</div>' : '') +
    seen.slice(0, LIST_MAX).map(function(a) { return areaRow(a, null); }).join('');
  if (seen.length > LIST_MAX) html += '<div class="note">' + (seen.length - LIST_MAX) + ' more in view: zoom in, or see the Maps menu.</div>';
  if (!seen.length) html += '<div class="note">None here: zoom out to find them.</div>';
  return html;
}
map.on("moveend", function() { if (!located) setList(inViewList(map.getBounds())); });

function directions(s) {
  return "https://www.google.com/maps/dir/?api=1&destination=" + s.lat + "," + s.lon;
}

function nearestStart(a, ll) {
  var best = null;
  a.starts.forEach(function(s) {
    var d = ll.distanceTo(L.latLng(s.lat, s.lon));
    if (!best || d < best.d) best = {s: s, d: d};
  });
  return best;
}

function areaRow(a, near) {
  return '<div class="area"><a href="' + a.href + '"><img class="swatch" src="' + a.icon + '" alt=""></a><div class="what">' +
    '<div class="name">' + esc(a.name) + '</div>' +
    (near ? '<div class="fine">' + formatMiles(near.d) + ' away, to ' + esc(near.s.name) + '</div>' : '') + '</div>' +
    (near ? '<a class="btn alt" href="' + directions(near.s) + '" target="_blank" rel="noopener">Directions</a> ' : '') +
    '<a class="btn" href="' + a.href + '">Map</a></div>';
}

// Before your location is known: the maps in view, and a word about it
function showInView(note) {
  listNote = note;
  setList(inViewList(map.getBounds()));
}

var you = null, fitted = false;
function onLocation(pos) {
  var ll = L.latLng(pos.coords.latitude, pos.coords.longitude);
  if (!you) {
    you = L.marker(ll, {icon: L.divIcon({className: "", iconSize: [22, 22], iconAnchor: [11, 11], html: '<div class="user-dot"></div>'}),
                        title: "You", keyboard: false}).addTo(map);
  } else {
    you.setLatLng(ll);
  }
  var rows = AREAS.map(function(a) { return {a: a, near: nearestStart(a, ll)}; })
    .filter(function(r) { return r.near; }).sort(function(x, y) { return x.near.d - y.near.d; });
  if (!rows.length) return;
  var limit = Math.max(rows[0].near.d * NEAR_FACTOR, 1609);
  var shown = rows.filter(function(r) { return r.near.d <= limit; }).slice(0, LIST_MAX);
  located = true;
  setList('<h2>Nearest trail maps</h2>' +
    shown.map(function(r) { return areaRow(r.a, r.near); }).join('') +
    (shown.length < rows.length ? '<div class="note">' + (rows.length - shown.length) + ' more farther away: they\'re all in the Maps menu.</div>' : ''));
  if (!fitted) {
    // You and the nearest areas in view
    fitted = true;
    var b = L.latLngBounds([ll]);
    shown.forEach(function(r) { b.extend(r.a.poly.getBounds()); });
    fitQuietly(b, {padding: [30, 30], maxZoom: 13});
  }
}

// The list first (it takes its room), then the map fitted to what's left; or, handed a
// view (?view=lat,lon,zoom: zooming out on a map), that view, kept
listNote = navigator.geolocation ? "Finding where you are, for how far each one is…" : "";
document.getElementById("list").innerHTML = inViewList(all);
var handedView = (new URLSearchParams(location.search).get("view") || "").split(",").map(Number);
handedView = handedView.length === 3 && handedView.every(isFinite) ? handedView : null;
if (handedView) {
  history.replaceState(null, "", location.pathname + location.hash);   // not again on a reload
  map.invalidateSize({pan: false});
  map.setView([handedView[0], handedView[1]], handedView[2]);
  fitted = true;
} else {
  map.fitBounds(all, {padding: [20, 20]});
}
showDetail();

// Zoomed in to MAP_ZOOM (trails readable) with the middle of the view inside an area,
// that area's map takes over, on the same view. Only when you zoom: the Overview's own
// fitting (to you, or to a group of maps) doesn't count, for the moment it takes.
var MAP_ZOOM = 14, FIT_MS = 1500, fitUntil = 0;
function inOutline(r, ll) {
  var inside = false;
  for (var i = 0, j = r.length - 1; i < r.length; j = i++) {
    if ((r[i][0] > ll.lat) !== (r[j][0] > ll.lat) &&
        ll.lng < (r[j][1] - r[i][1]) * (ll.lat - r[i][0]) / (r[j][0] - r[i][0]) + r[i][1]) inside = !inside;
  }
  return inside;
}
function fitQuietly(b, opts) { fitUntil = Date.now() + FIT_MS; map.fitBounds(b, opts); }
map.on("zoomend", function() {
  if (Date.now() < fitUntil || map.getZoom() < MAP_ZOOM) return;
  var c = map.getCenter(), a = AREAS.filter(function(x) { return x.rings.some(function(r) { return inOutline(r, c); }); })[0];
  if (a) location.href = a.href + "?view=" + [c.lat.toFixed(5), c.lng.toFixed(5), map.getZoom()].join(",");
});
if (navigator.geolocation) {
  navigator.geolocation.watchPosition(onLocation, function() {
    if (!located) showInView("Without your location: the maps in view.");
  }, {enableHighAccuracy: false, maximumAge: 60000, timeout: 30000});
}
</script>
</body>
</html>
"""
