"""
Build the trail/intersection editor (trail_editor.html).

Embeds trails_selected.geojson and intersections_zoned.geojson into
a standalone Leaflet-based editing tool with these capabilities:

Trails:  rename, delete, add from the available ones, draw one that's missing
Intersections:  add (click map), remove, change zone

Exports updated GeoJSON files that can be dropped back into the project.
"""

import json

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"


def main():
    import sys
    trail_file = sys.argv[1] if len(sys.argv) > 1 else rf"{PROJ}\trails_selected.geojson"
    with open(trail_file) as f:
        trails = json.load(f)
    int_file = sys.argv[2] if len(sys.argv) > 2 else rf"{PROJ}\intersections_zoned.geojson"   # the project's own, current
    print("Trail source: %s" % trail_file)
    print("Intersection source: %s" % int_file)
    with open(int_file) as f:
        ints = json.load(f)
    # Trails that can be added: OSM's paths and the Trailforks snapshot's trails not already
    # on the map (trails_available.geojson), shown dashed red to click and add
    with open(rf"{PROJ}\trails_available.geojson", encoding="utf-8") as f:
        old_trails = json.load(f)

    html = TEMPLATE.replace("__TRAIL_DATA__", json.dumps(trails))
    html = html.replace("__INT_DATA__", json.dumps(ints))
    html = html.replace("__OLD_TRAIL_DATA__", json.dumps(old_trails))

    with open(rf"{PROJ}\trail_editor.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote trail_editor.html (%d trails, %d intersections, %d available)" % (
        len(trails["features"]), len(ints["features"]), len(old_trails["features"])))


TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trail &amp; Intersection Editor</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  #map { height: calc(100vh - 42px); width: 100%; }

  .topbar {
    background: #2c3e50; padding: 8px 20px; display: flex; gap: 12px;
    align-items: center; color: #ecf0f1; font-size: 13px; flex-wrap: wrap;
  }
  .topbar .title { font-weight: 700; font-size: 15px; margin-right: 8px; }
  .topbar .sep { color: #7f8c8d; }
  .topbar .mode-btn {
    padding: 5px 12px; border-radius: 4px; border: 1px solid #7f8c8d;
    cursor: pointer; font-size: 12px; font-weight: 600; color: #bdc3c7;
    background: none; transition: all 0.15s;
  }
  .topbar .mode-btn.active { background: #ecf0f1; color: #2c3e50; border-color: #ecf0f1; }
  .topbar .mode-btn:hover { border-color: #ecf0f1; }
  .topbar button.export { padding: 5px 14px; border-radius: 4px; border: none; cursor: pointer;
    font-size: 12px; font-weight: 600; background: #27ae60; color: white; }
  .topbar button.export:hover { background: #219a52; }
  .topbar .stats { color: #95a5a6; margin-left: auto; font-size: 11px; }

  .panel {
    position: absolute; top: 52px; left: 10px; z-index: 1000;
    background: white; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.25);
    width: 320px; font-size: 13px; overflow: hidden;
  }
  .panel h3 {
    font-size: 14px; padding: 10px 14px 8px; border-bottom: 1px solid #e0e0e0;
    display: flex; justify-content: space-between; align-items: center;
  }
  .panel .content { padding: 10px 14px 14px; }
  .panel table { width: 100%; border-collapse: collapse; }
  .panel td { padding: 3px 0; vertical-align: top; }
  .panel td:first-child { font-weight: 600; width: 70px; color: #555; }
  .panel input[type="text"] {
    width: 100%; padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px;
    font-size: 13px; margin-top: 4px;
  }
  .panel input[type="text"]:focus { outline: none; border-color: #3498db; }
  .panel select {
    padding: 5px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px;
    margin-top: 4px;
  }
  .btn-row { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
  .btn { padding: 5px 12px; border-radius: 4px; border: none;
         cursor: pointer; font-size: 12px; font-weight: 600; }
  .btn-blue { background: #3498db; color: white; }
  .btn-blue:hover { background: #2980b9; }
  .btn-red { background: #e74c3c; color: white; }
  .btn-red:hover { background: #c0392b; }
  .btn-gray { background: #eee; color: #333; }
  .btn-gray:hover { background: #ddd; }
  .btn-green { background: #27ae60; color: white; }
  .btn-green:hover { background: #219a52; }

  .changelog {
    position: absolute; top: 52px; right: 54px; z-index: 1000;
    background: white; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.25);
    padding: 10px 14px; font-size: 12px; max-height: calc(100vh - 80px);
    overflow-y: auto; width: 280px;
  }
  .changelog h3 { font-size: 13px; margin-bottom: 6px; }
  .log-item {
    padding: 4px 0; border-bottom: 1px solid #f0f0f0; display: flex;
    justify-content: space-between; align-items: flex-start; gap: 6px;
  }
  .log-item .desc { flex: 1; }
  .log-item .action { font-weight: 600; font-size: 10px; text-transform: uppercase; }
  .log-item .action.renamed { color: #3498db; }
  .log-item .action.deleted { color: #e74c3c; }
  .log-item .action.added { color: #27ae60; }
  .log-item .action.removed { color: #e74c3c; }
  .log-item .action.rezoned { color: #f39c12; }
  .log-item .detail { color: #888; font-size: 11px; }
  .log-item .btn-undo { background: none; border: none; color: #e74c3c; cursor: pointer;
    font-size: 11px; padding: 2px 4px; white-space: nowrap; }
  .log-item .btn-undo:hover { text-decoration: underline; }

  .legend-panel {
    position: absolute; bottom: 24px; left: 10px; z-index: 1000;
    background: white; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.25);
    padding: 10px 14px; font-size: 12px;
  }
  .legend-row { display: flex; align-items: center; margin: 3px 0; }
  .legend-line { width: 20px; height: 3px; margin-right: 8px; border-radius: 2px; flex-shrink: 0; }
  .legend-swatch { width: 14px; height: 14px; border-radius: 50%; margin-right: 8px;
    border: 2px solid white; box-shadow: 0 0 2px rgba(0,0,0,0.3); flex-shrink: 0; }

  .marker-label {
    background: none !important; border: none !important; box-shadow: none !important;
    font-size: 10px; font-weight: bold; white-space: nowrap;
  }
  .prox-slider-row { display: flex; align-items: center; gap: 6px; margin-top: 8px; }
  .prox-slider-row label { font-size: 11px; color: #555; white-space: nowrap; }
  .prox-slider-row input[type=range] { flex: 1; }
  .prox-slider-row .prox-val { font-weight: 700; min-width: 36px; text-align: right; font-size: 12px; }
  .prox-warn-ring { }   /* steady, no pulsing */
</style>
</head>
<body>
<div class="topbar">
  <span class="title">Trail Editor</span>
  <span class="sep">|</span>
  <button class="mode-btn active" id="modeTrails" onclick="setMode('trails')">Trails</button>
  <button class="mode-btn" id="modeInts" onclick="setMode('intersections')">Intersections</button>
  <button class="mode-btn" id="modeDraw" onclick="setMode('draw')">Draw Trail</button>
  <span class="sep">|</span>
  <button class="export" onclick="exportTrails()">Export Trails</button>
  <button class="export" onclick="exportIntersections()">Export Intersections</button>
  <button class="mode-btn active" id="toggleAvailBtn" onclick="toggleAvailable()">Hide Available</button>
  <span class="stats" id="statsDisplay"></span>
</div>
<div id="map"></div>

<div class="panel" id="panel">
  <h3><span id="panelTitle">Trail Editor</span></h3>
  <div class="content" id="panelContent">
    <p style="color:#888">Select a mode and click a trail or intersection to edit.</p>
  </div>
</div>

<div class="changelog" id="changelog">
  <h3>Changes (<span id="changeCount">0</span>)</h3>
  <div id="changeItems"><p style="color:#888">No changes yet.</p></div>
</div>

<div class="legend-panel" id="legendPanel"></div>

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
var oldTrailData = __OLD_TRAIL_DATA__;

var mode = "trails";
var showAvailable = true;
var changeLog = [];
var selectedTrailLayer = null;
var selectedTrailFeature = null;
var selectedIntMarker = null;
var selectedIntFeature = null;
var addingIntersection = false;
var tempMarker = null;

// Track deletions and modifications
var deletedTrailIds = {};
var trailRenames = {};
var deletedIntIndices = {};
var addedIntersections = [];
var intReZones = {};

var map = L.map("map", {zoomControl: false}).setView([42.178, -71.498], 14);
L.control.zoom({position: "topright"}).addTo(map);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '&copy; <a href="https://osm.org/copyright">OSM</a>',
  maxZoom: 19
}).addTo(map);
map.fitBounds([[42.156, -71.518], [42.201, -71.483]]);

// --- Trail layer ---
var trailLayerById = {};

function trailName(f) {
  var fid = f.properties.id;
  if (trailRenames[fid]) return trailRenames[fid];
  return f.properties.pdf_name || f.properties.name || "";
}

function trailStyle(f) {
  var fid = f.properties.id;
  if (deletedTrailIds[fid]) return {color: "#ccc", weight: 2, opacity: 0.3, dashArray: "4,4"};
  if (trailRenames[fid]) return {color: "#27ae60", weight: 4, opacity: 0.8};
  var name = f.properties.pdf_name || f.properties.name || "";
  if (!name) return {color: "#e74c3c", weight: 4, opacity: 0.75, dashArray: "6,4"};
  return {color: "#3498db", weight: 3, opacity: 0.5};
}

var trailLayer = L.geoJSON(trailData, {
  style: function(f) { return trailStyle(f); },
  onEachFeature: function(feature, layer) {
    trailLayerById[feature.properties.id] = layer;
    layer.on("click", function(e) {
      L.DomEvent.stopPropagation(e);
      if (mode === "trails") selectTrail(feature, layer);
    });
    layer.on("mouseover", function() {
      if (mode === "trails" && layer !== selectedTrailLayer && !deletedTrailIds[feature.properties.id])
        layer.setStyle({weight: 6, opacity: 1});
    });
    layer.on("mouseout", function() {
      if (layer !== selectedTrailLayer) layer.setStyle(trailStyle(feature));
    });
  }
}).addTo(map);

// --- Available (old) trail layer ---
var addedFromOld = {};
var oldLayerById = {};
var selectedOldLayer = null;
var selectedOldFeature = null;

var oldTrailLayer = L.geoJSON(oldTrailData, {
  style: function() { return {color: "#e74c3c", weight: 3, opacity: 0.5, dashArray: "6,4"}; },
  onEachFeature: function(feature, layer) {
    var fid = feature.properties.id;
    oldLayerById[fid] = layer;
    layer.on("click", function(e) {
      L.DomEvent.stopPropagation(e);
      if (mode === "trails" && showAvailable && !addedFromOld[fid]) selectOldTrail(feature, layer);
    });
    layer.on("mouseover", function() {
      if (mode === "trails" && showAvailable && !addedFromOld[fid] && layer !== selectedOldLayer)
        layer.setStyle({weight: 6, opacity: 0.9});
    });
    layer.on("mouseout", function() {
      if (layer !== selectedOldLayer) {
        if (addedFromOld[fid]) layer.setStyle({color: "#ccc", weight: 1, opacity: 0.15});
        else layer.setStyle({color: "#e74c3c", weight: 3, opacity: 0.5, dashArray: "6,4"});
      }
    });
  }
});
oldTrailLayer.addTo(map);
oldTrailLayer.bringToBack();

function selectOldTrail(feature, layer) {
  clearSelection();
  selectedOldLayer = layer;
  selectedOldFeature = feature;
  layer.setStyle({color: "#e67e22", weight: 6, opacity: 1, dashArray: ""});

  var name = feature.properties.pdf_name || feature.properties.name || "";
  var fid = feature.properties.id;
  document.getElementById("panelContent").innerHTML =
    '<p style="font-weight:600;color:#e74c3c;font-size:12px">AVAILABLE TRAIL (from old data)</p>' +
    '<table>' +
    '<tr><td>Trail</td><td><strong>' + (name || '<em style="color:#999">unnamed</em>') + '</strong></td></tr>' +
    '<tr><td>ID</td><td style="font-size:11px;color:#888">' + fid + '</td></tr>' +
    (feature.properties.surface ? '<tr><td>Surface</td><td>' + feature.properties.surface + '</td></tr>' : '') +
    '</table>' +
    '<input type="text" id="addTrailNameInput" placeholder="Trail name..." value="' + (name || '') + '">' +
    '<div class="btn-row">' +
    '<button class="btn btn-green" onclick="addOldTrail()">Add Trail</button>' +
    '<button class="btn btn-gray" onclick="clearSelection()">Cancel</button>' +
    '</div>';
  setTimeout(function() {
    var inp = document.getElementById("addTrailNameInput");
    if (inp) { inp.focus(); inp.select(); }
  }, 50);
}

function addOldTrail() {
  if (!selectedOldFeature) return;
  var inp = document.getElementById("addTrailNameInput");
  var name = inp ? inp.value.trim() : "";
  var fid = selectedOldFeature.properties.id;
  var newFeature = JSON.parse(JSON.stringify(selectedOldFeature));
  var newId = "old_" + fid;
  newFeature.properties.id = newId;
  if (name) {
    newFeature.properties.pdf_name = name;
    newFeature.properties.name = name;
  }
  newFeature.properties.source = "added_from_old";

  trailData.features.push(newFeature);
  var newLayer = L.geoJSON(newFeature, {
    style: function() { return {color: "#27ae60", weight: 4, opacity: 0.8}; },
    onEachFeature: function(feature, layer) {
      trailLayerById[newId] = layer;
      layer.on("click", function(e) {
        L.DomEvent.stopPropagation(e);
        if (mode === "trails") selectTrail(feature, layer);
      });
      layer.on("mouseover", function() {
        if (mode === "trails" && layer !== selectedTrailLayer)
          layer.setStyle({weight: 6, opacity: 1});
      });
      layer.on("mouseout", function() {
        if (layer !== selectedTrailLayer) layer.setStyle({color: "#27ae60", weight: 4, opacity: 0.8});
      });
    }
  }).addTo(map);

  addedFromOld[fid] = newId;
  if (oldLayerById[fid]) oldLayerById[fid].setStyle({color: "#ccc", weight: 1, opacity: 0.15});

  addChange("added", "Trail: " + (name || "(unnamed)") + " (from old data)", newId, function() {
    trailData.features = trailData.features.filter(function(f) { return f.properties.id !== newId; });
    if (trailLayerById[newId]) { map.removeLayer(trailLayerById[newId]); delete trailLayerById[newId]; }
    map.removeLayer(newLayer);
    delete addedFromOld[fid];
    if (oldLayerById[fid]) oldLayerById[fid].setStyle({color: "#e74c3c", weight: 3, opacity: 0.5, dashArray: "6,4"});
  });
  clearSelection();
  updateStats();
}

function toggleAvailable() {
  showAvailable = !showAvailable;
  if (showAvailable) {
    oldTrailLayer.addTo(map);
    oldTrailLayer.bringToBack();
  } else {
    map.removeLayer(oldTrailLayer);
  }
  document.getElementById("toggleAvailBtn").textContent = showAvailable ? "Hide Available" : "Show Available";
  updateLegend();
}

// --- Intersection layer ---
var intMarkers = {};
var intLabels = {};
var intFeatureByIdx = {};
var nextIntNumber = 0;
var nextNewId = 0;   // ids for added intersections, never reused (undo can shrink the list)

intData.features.forEach(function(f, idx) {
  var n = f.properties.number || 0;
  if (n >= nextIntNumber) nextIntNumber = n + 1;
  intFeatureByIdx[idx] = f;
});

function intZone(f, idx) {
  if (intReZones[idx] !== undefined) return intReZones[idx];
  return f.properties.zone;
}

// An unmarked junction (no sign: a routing point where trails meet) is a small grey dot, so
// it can't be mistaken for an intersection that gets a numbered sign
function isUnmarked(f) { return !!(f.properties.junction || f.properties.no_sign); }

function intMarkerStyle(f, zone) {
  return isUnmarked(f)
    ? {radius: 3.5, fillColor: "#90a4ae", color: "#fff", weight: 1, fillOpacity: 0.9}
    : {radius: 7, fillColor: ZONE_COLORS[zone] || "#888", color: "#fff", weight: 2, fillOpacity: 0.85};
}

function addIntMarker(f, idx) {
  var zone = intZone(f, idx);
  var ll = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
  var color = ZONE_COLORS[zone] || "#888";
  var marker = L.circleMarker(ll, intMarkerStyle(f, zone)).addTo(map);
  marker._idx = idx;
  marker._zone = zone;
  marker._feature = f;
  marker.on("click", function(e) {
    L.DomEvent.stopPropagation(e);
    if (mode === "intersections" && !addingIntersection) selectIntersection(f, idx, marker);
  });
  intMarkers[idx] = marker;
  if (isUnmarked(f)) return;   // no zone letter beside an unmarked junction

  var label = L.marker(ll, {
    icon: L.divIcon({
      className: "marker-label",
      html: '<span style="color:' + color + ';text-shadow:1px 1px 0 #fff,-1px 1px 0 #fff,1px -1px 0 #fff,-1px -1px 0 #fff">' + zone + '</span>',
      iconAnchor: [-6, 12]
    }),
    interactive: false
  }).addTo(map);
  intLabels[idx] = label;
}

intData.features.forEach(function(f, idx) {
  addIntMarker(f, idx);
});

// --- Proximity warnings ---
var proxThreshold = 30; // meters
var proxRings = [];

function distMeters(lon1, lat1, lon2, lat2) {
  var dx = (lon1 - lon2) * 82000;
  var dy = (lat1 - lat2) * 111000;
  return Math.sqrt(dx*dx + dy*dy);
}

// The signed intersections (spacing matters between signs, not unmarked junctions)
function getActiveIntersections() {
  var active = [];
  intData.features.forEach(function(f, idx) {
    if (!deletedIntIndices[idx] && !isUnmarked(f)) {
      var c = f.geometry.coordinates;
      active.push({lon: c[0], lat: c[1], idx: idx, zone: intZone(f, idx)});
    }
  });
  addedIntersections.forEach(function(a) {
    if (!deletedIntIndices[a.idx]) {
      var c = a.feature.geometry.coordinates;
      active.push({lon: c[0], lat: c[1], idx: a.idx, zone: intZone(a.feature, a.idx)});
    }
  });
  return active;
}

function updateProximityWarnings() {
  proxRings.forEach(function(r) { map.removeLayer(r); });
  proxRings = [];
  if (proxThreshold <= 0) return;
  var pts = getActiveIntersections();
  var flagged = {};
  for (var i = 0; i < pts.length; i++) {
    for (var j = i + 1; j < pts.length; j++) {
      var d = distMeters(pts[i].lon, pts[i].lat, pts[j].lon, pts[j].lat);
      if (d < proxThreshold) {
        flagged[i] = true;
        flagged[j] = true;
      }
    }
  }
  var count = 0;
  for (var k in flagged) {
    var p = pts[k];
    var ring = L.circleMarker([p.lat, p.lon], {
      radius: 14, fillColor: "#e74c3c", color: "#e74c3c",
      weight: 3, fillOpacity: 0.2, opacity: 0.7, className: "prox-warn-ring",
      interactive: false
    }).addTo(map);
    proxRings.push(ring);
    count++;
  }
  var el = document.getElementById("proxCount");
  if (el) el.textContent = count + " flagged";
}

function proxSliderHtml() {
  return '<div class="prox-slider-row">' +
    '<label>Min spacing:</label>' +
    '<input type="range" id="proxSlider" min="0" max="80" value="' + proxThreshold + '" ' +
    'oninput="proxThreshold=+this.value;document.getElementById(\'proxVal\').textContent=this.value+\'m\';updateProximityWarnings()">' +
    '<span class="prox-val" id="proxVal">' + proxThreshold + 'm</span>' +
    '<span id="proxCount" style="font-size:11px;color:#e74c3c;margin-left:4px"></span>' +
    '</div>';
}

// --- Mode switching ---
function setMode(m) {
  if (mode === "draw" && m !== "draw") stopDrawing();
  mode = m;
  document.getElementById("modeTrails").classList.toggle("active", m === "trails");
  document.getElementById("modeInts").classList.toggle("active", m === "intersections");
  document.getElementById("modeDraw").classList.toggle("active", m === "draw");
  clearSelection();
  cancelAdd();
  updateLegend();
  if (m === "draw") {
    document.getElementById("panelTitle").textContent = "Draw a Trail";
    startDrawing();
  } else if (m === "trails") {
    document.getElementById("panelTitle").textContent = "Trail Editor";
    proxRings.forEach(function(r) { map.removeLayer(r); });
    proxRings = [];
    showDefaultPanel();
  } else {
    document.getElementById("panelTitle").textContent = "Intersection Editor";
    showIntDefault();
  }
}

function showDefaultPanel() {
  var unnamed = 0;
  trailData.features.forEach(function(f) {
    if (!deletedTrailIds[f.properties.id] && !trailName(f)) unnamed++;
  });
  var total = trailData.features.length - Object.keys(deletedTrailIds).length;
  document.getElementById("panelContent").innerHTML =
    '<p style="color:#888">Click a <span style="color:#3498db;font-weight:600">blue trail</span> to rename or delete it.' +
    (showAvailable ? ' Click a <span style="color:#e74c3c;font-weight:600">red dashed trail</span> to add it.' : '') + '</p>' +
    '<p style="margin-top:6px;color:#888;font-size:11px">' + total + ' trails, ' +
    unnamed + ' unnamed.</p>';
}

function showIntDefault() {
  var total = intData.features.length - Object.keys(deletedIntIndices).length + addedIntersections.length;
  document.getElementById("panelContent").innerHTML =
    '<p style="color:#888">Click an intersection to edit or remove it.</p>' +
    '<div class="btn-row" style="margin-top:8px">' +
    '<button class="btn btn-green" onclick="startAddIntersection()">+ Add Intersection</button></div>' +
    '<p style="margin-top:6px;color:#888;font-size:11px">' + total + ' intersections.</p>' +
    proxSliderHtml();
  updateProximityWarnings();
}

// --- Trail editing ---
// Text from the data, made safe to put in HTML (some trail names contain quotes)
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function selectTrail(feature, layer) {
  clearSelection();
  var fid = feature.properties.id;
  if (deletedTrailIds[fid]) return;
  selectedTrailLayer = layer;
  selectedTrailFeature = feature;
  layer.setStyle({color: "#e67e22", weight: 6, opacity: 1});

  var name = trailName(feature);
  var p = feature.properties;
  document.getElementById("panelContent").innerHTML =
    '<table>' +
    '<tr><td>Trail</td><td><strong>' + (name ? esc(name) : '<em style="color:#999">unnamed</em>') + '</strong></td></tr>' +
    '<tr><td>ID</td><td style="font-size:11px;color:#888">' + fid + '</td></tr>' +
    (p.surface ? '<tr><td>Surface</td><td>' + esc(p.surface) + '</td></tr>' : '') +
    (p.highway ? '<tr><td>Type</td><td>' + esc(p.highway) + '</td></tr>' : '') +
    '</table>' +
    '<input type="text" id="trailNameInput" placeholder="Enter trail name..." value="' + esc(name || '') + '">' +
    '<div class="btn-row">' +
    '<button class="btn btn-blue" onclick="saveTrailName(\'' + fid + '\')">Save Name</button>' +
    '<button class="btn btn-red" onclick="deleteTrail(\'' + fid + '\')">Delete Trail</button>' +
    '<button class="btn btn-gray" onclick="clearSelection()">Cancel</button>' +
    '</div>';
  setTimeout(function() {
    var inp = document.getElementById("trailNameInput");
    if (inp) { inp.focus(); inp.select(); }
  }, 50);
}

function saveTrailName(fid) {
  var inp = document.getElementById("trailNameInput");
  if (!inp) return;
  var name = inp.value.trim();
  if (!name) return;
  var oldName = trailName(selectedTrailFeature) || "(unnamed)";
  trailRenames[fid] = name;
  addChange("renamed", "Trail: " + oldName + " → " + name, fid, function() {
    delete trailRenames[fid];
    if (trailLayerById[fid]) trailLayerById[fid].setStyle(trailStyle(selectedTrailFeature));
    refreshTrailStyles();
  });
  clearSelection();
  refreshTrailStyles();
}

function deleteTrail(fid) {
  var name = trailName(selectedTrailFeature) || "(unnamed)";
  deletedTrailIds[fid] = true;
  addChange("deleted", "Trail: " + name, fid, function() {
    delete deletedTrailIds[fid];
    refreshTrailStyles();
  });
  clearSelection();
  refreshTrailStyles();
}

function refreshTrailStyles() {
  trailData.features.forEach(function(f) {
    var layer = trailLayerById[f.properties.id];
    if (layer) layer.setStyle(trailStyle(f));
  });
  updateStats();
}

// --- Intersection editing ---
function selectIntersection(feature, idx, marker) {
  clearSelection();
  selectedIntMarker = marker;
  selectedIntFeature = feature;
  marker.setStyle({fillColor: "#f1c40f", radius: 11, weight: 3, color: "#222", fillOpacity: 1});

  var zone = intZone(feature, idx);
  var p = feature.properties;
  // idx is a number for loaded points and a string ("new_0") for added ones
  var ia = JSON.stringify(idx).replace(/"/g, "&quot;");
  var zoneOptions = "";
  "ABCDEF".split("").forEach(function(z) {
    var sel = z === zone ? " selected" : "";
    zoneOptions += '<option value="' + z + '"' + sel + '>' + z + ': ' + ZONE_NAMES[z] + '</option>';
  });

  document.getElementById("panelContent").innerHTML =
    '<table>' +
    '<tr><td>Zone</td><td><span style="background:' + ZONE_COLORS[zone] +
    ';color:white;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">' +
    zone + ': ' + ZONE_NAMES[zone] + '</span></td></tr>' +
    '<tr><td>Degree</td><td>' + (p.degree || "?") + '-way</td></tr>' +
    '<tr><td>Number</td><td style="font-size:11px;color:#888">' + (p.number || "?") + '</td></tr>' +
    '<tr><td>Coords</td><td style="font-size:11px;color:#888">' +
    feature.geometry.coordinates[1].toFixed(6) + ', ' +
    feature.geometry.coordinates[0].toFixed(6) + '</td></tr>' +
    '</table>' +
    '<label style="font-size:12px;font-weight:600;color:#555;margin-top:8px;display:block">' +
    '<input type="checkbox"' + (isUnmarked(feature) ? '' : ' checked') + ' onchange="setSigned(' + ia + ', this.checked)"> Numbered sign</label>' +
    '<label style="font-size:12px;font-weight:600;color:#555;margin-top:4px;display:block">' +
    '<input type="checkbox"' + (p.entry ? ' checked' : '') + ' onchange="toggleFlag(' + ia + ', \'entry\', \'entry point\', this.checked)"> Entry point</label>' +
    '<label style="font-size:12px;font-weight:600;color:#555;margin-top:4px;display:block">' +
    '<input type="checkbox"' + (p.parking ? ' checked' : '') + ' onchange="toggleFlag(' + ia + ', \'parking\', \'parking\', this.checked)"> Parking</label>' +
    '<label style="font-size:12px;font-weight:600;color:#555;margin-top:4px;display:block">Connects to: ' +
    '<input type="text" style="width:150px;font-size:12px" placeholder="e.g. Upper Charles Rail Trail" value="' + (p.connects || '').replace(/"/g, '&quot;') + '" onchange="setConnects(' + ia + ', this.value)"></label>' +
    '<label style="font-size:12px;font-weight:600;color:#555;margin-top:8px;display:block">Change zone:</label>' +
    '<select id="zoneSelect">' + zoneOptions + '</select>' +
    '<div class="btn-row">' +
    '<button class="btn btn-blue" onclick="saveIntZone(' + ia + ')">Save Zone</button>' +
    '<button class="btn btn-red" onclick="deleteIntersection(' + ia + ')">Remove</button>' +
    '<button class="btn btn-gray" onclick="clearSelection()">Cancel</button>' +
    '</div>';
}

function saveIntZone(idx) {
  var sel = document.getElementById("zoneSelect");
  if (!sel) return;
  var newZone = sel.value;
  var f = intFeatureByIdx[idx] || intData.features[idx];
  var oldZone = intZone(f, idx);
  if (newZone === oldZone) { clearSelection(); return; }
  intReZones[idx] = newZone;
  addChange("rezoned", "Intersection #" + (f.properties.number || "?") + ": " + oldZone + " → " + newZone, idx, function() {
    delete intReZones[idx];
    refreshIntMarker(f, idx);
  });
  refreshIntMarker(f, idx);
  clearSelection();
}

function setConnects(idx, value) {
  var f = intFeatureByIdx[idx] || intData.features[idx];
  var prev = f.properties.connects;
  value = value.trim();
  if (value) f.properties.connects = value; else delete f.properties.connects;
  addChange("rezoned", "Intersection #" + (f.properties.number || "?") + ": connects to " + (value || "(none)"), idx, function() {
    if (prev) f.properties.connects = prev; else delete f.properties.connects;
  });
}

function toggleFlag(idx, key, desc, on) {
  var f = intFeatureByIdx[idx] || intData.features[idx];
  var prev = !!f.properties[key];
  if (on) f.properties[key] = true; else delete f.properties[key];
  addChange("rezoned", "Intersection #" + (f.properties.number || "?") + ": " + desc + " " + (on ? "on" : "off"), idx, function() {
    if (prev) f.properties[key] = true; else delete f.properties[key];
  });
}

// Turn an unmarked junction into an intersection that gets a numbered sign, or back. The
// build gives a new sign its label (RENUMBER), so only the junction properties change here.
var JUNCTION_KEYS = ["junction", "no_sign", "code"];
function setSigned(idx, on) {
  var f = intFeatureByIdx[idx] || intData.features[idx];
  var prev = {};
  JUNCTION_KEYS.forEach(function(k) { if (k in f.properties) prev[k] = f.properties[k]; });
  if (on) JUNCTION_KEYS.forEach(function(k) { delete f.properties[k]; });
  else { f.properties.junction = true; f.properties.no_sign = true; }
  var restyle = function() {
    refreshIntMarker(f, idx);
    if (intMarkers[idx]) selectIntersection(f, idx, intMarkers[idx]);
  };
  addChange("rezoned", "Intersection #" + (f.properties.number || "?") + ": " +
            (on ? "unmarked junction → numbered sign" : "numbered sign → unmarked junction"), idx, function() {
    JUNCTION_KEYS.forEach(function(k) { delete f.properties[k]; });
    Object.keys(prev).forEach(function(k) { f.properties[k] = prev[k]; });
    refreshIntMarker(f, idx);
  });
  restyle();
}

function deleteIntersection(idx) {
  var f = intFeatureByIdx[idx] || intData.features[idx];
  deletedIntIndices[idx] = true;
  if (intMarkers[idx]) { map.removeLayer(intMarkers[idx]); delete intMarkers[idx]; }
  if (intLabels[idx]) { map.removeLayer(intLabels[idx]); delete intLabels[idx]; }
  addChange("removed", "Intersection #" + (f.properties.number || "?") + " (zone " + intZone(f, idx) + ")", idx, function() {
    delete deletedIntIndices[idx];
    refreshIntMarker(f, idx);
  });
  clearSelection();
  updateStats();
}

// Undos can run out of order, so only show points that still exist (an added point whose
// "added" entry was undone is gone from intFeatureByIdx)
function refreshIntMarker(f, idx) {
  if (intMarkers[idx]) map.removeLayer(intMarkers[idx]);
  if (intLabels[idx]) { map.removeLayer(intLabels[idx]); delete intLabels[idx]; }
  if (!deletedIntIndices[idx] && intFeatureByIdx[idx]) addIntMarker(f, idx);
}

// --- Add intersection ---
function startAddIntersection() {
  addingIntersection = true;
  document.getElementById("panelContent").innerHTML =
    '<p style="color:#e67e22;font-weight:600">Click on the map to place a new intersection.</p>' +
    '<div class="btn-row"><button class="btn btn-gray" onclick="cancelAdd()">Cancel</button></div>';
  map.getContainer().style.cursor = "crosshair";
}

function cancelAdd() {
  addingIntersection = false;
  if (tempMarker) { map.removeLayer(tempMarker); tempMarker = null; }
  map.getContainer().style.cursor = "";
  if (mode === "intersections") showIntDefault();
}

map.on("click", function(e) {
  if (mode === "intersections" && addingIntersection) {
    placeNewIntersection(e.latlng);
  } else {
    clearSelection();
    if (mode === "trails") showDefaultPanel();
    else if (mode === "intersections") showIntDefault();
  }
});

function placeNewIntersection(latlng) {
  if (tempMarker) map.removeLayer(tempMarker);
  tempMarker = L.circleMarker(latlng, {
    radius: 9, fillColor: "#f1c40f", color: "#222", weight: 3, fillOpacity: 0.9
  }).addTo(map);

  var zoneOptions = "";
  "ABCDEF".split("").forEach(function(z) {
    zoneOptions += '<option value="' + z + '">' + z + ': ' + ZONE_NAMES[z] + '</option>';
  });

  document.getElementById("panelContent").innerHTML =
    '<table>' +
    '<tr><td>Coords</td><td style="font-size:11px;color:#888">' +
    latlng.lat.toFixed(6) + ', ' + latlng.lng.toFixed(6) + '</td></tr>' +
    '</table>' +
    '<label style="font-size:12px;font-weight:600;color:#555;margin-top:8px;display:block">Zone:</label>' +
    '<select id="newZoneSelect">' + zoneOptions + '</select>' +
    '<label style="font-size:12px;font-weight:600;color:#555;margin-top:6px;display:block">Degree (ways):</label>' +
    '<input type="number" id="newDegree" value="3" min="2" max="6" style="width:60px;padding:4px 8px;border:1px solid #ccc;border-radius:4px;font-size:13px">' +
    '<div class="btn-row">' +
    '<button class="btn btn-green" onclick="confirmAddIntersection(' +
    latlng.lat + ',' + latlng.lng + ')">Add</button>' +
    '<button class="btn btn-gray" onclick="cancelAdd()">Cancel</button>' +
    '</div>';
}

function confirmAddIntersection(lat, lng) {
  var zone = document.getElementById("newZoneSelect").value;
  var degree = parseInt(document.getElementById("newDegree").value) || 3;
  var num = nextIntNumber++;
  var feature = {
    type: "Feature",
    properties: { number: num, degree: degree, zone: zone },
    geometry: { type: "Point", coordinates: [lng, lat] }
  };
  var idx = "new_" + (nextNewId++);
  intFeatureByIdx[idx] = feature;
  addedIntersections.push({feature: feature, idx: idx});
  addIntMarker(feature, idx);

  if (tempMarker) { map.removeLayer(tempMarker); tempMarker = null; }
  addingIntersection = false;
  map.getContainer().style.cursor = "";

  addChange("added", "Intersection #" + num + " (zone " + zone + ")", idx, function() {
    if (intMarkers[idx]) map.removeLayer(intMarkers[idx]);
    if (intLabels[idx]) map.removeLayer(intLabels[idx]);
    delete intMarkers[idx];
    delete intLabels[idx];
    delete intFeatureByIdx[idx];
    delete deletedIntIndices[idx];   // a later "removed" no longer counts against the total
    delete intReZones[idx];
    addedIntersections = addedIntersections.filter(function(a) { return a.idx !== idx; });
  });
  showIntDefault();
  updateStats();
}

// --- Selection management ---
function clearSelection() {
  if (selectedTrailLayer) {
    selectedTrailLayer.setStyle(trailStyle(selectedTrailFeature));
    selectedTrailLayer = null;
    selectedTrailFeature = null;
  }
  if (selectedOldLayer) {
    var ofid = selectedOldFeature.properties.id;
    if (addedFromOld[ofid]) selectedOldLayer.setStyle({color: "#ccc", weight: 1, opacity: 0.15});
    else selectedOldLayer.setStyle({color: "#e74c3c", weight: 3, opacity: 0.5, dashArray: "6,4"});
    selectedOldLayer = null;
    selectedOldFeature = null;
  }
  if (selectedIntMarker) {
    var idx = selectedIntMarker._idx;
    var zone = selectedIntMarker._zone;
    selectedIntMarker.setStyle(selectedIntMarker._feature ? intMarkerStyle(selectedIntMarker._feature, zone)
      : {fillColor: ZONE_COLORS[zone] || "#888", radius: 7, weight: 2, color: "#fff", fillOpacity: 0.85});
    selectedIntMarker = null;
    selectedIntFeature = null;
  }
}

// --- Change log ---
function addChange(action, desc, ref, undoFn) {
  changeLog.push({action: action, desc: desc, ref: ref, undo: undoFn});
  renderChangeLog();
}

function undoChange(index) {
  var entry = changeLog[index];
  if (entry && entry.undo) entry.undo();
  changeLog.splice(index, 1);
  renderChangeLog();
  updateStats();
}

function renderChangeLog() {
  document.getElementById("changeCount").textContent = changeLog.length;
  if (changeLog.length === 0) {
    document.getElementById("changeItems").innerHTML = '<p style="color:#888">No changes yet.</p>';
    return;
  }
  var html = "";
  for (var i = changeLog.length - 1; i >= 0; i--) {
    var c = changeLog[i];
    html += '<div class="log-item">' +
      '<div class="desc"><span class="action ' + c.action + '">' + c.action + '</span> ' +
      '<span class="detail">' + c.desc + '</span></div>' +
      '<button class="btn-undo" onclick="undoChange(' + i + ')">undo</button></div>';
  }
  document.getElementById("changeItems").innerHTML = html;
}

// --- Stats ---
function updateStats() {
  var tTotal = trailData.features.length - Object.keys(deletedTrailIds).length;
  var tUnnamed = 0;
  trailData.features.forEach(function(f) {
    if (!deletedTrailIds[f.properties.id] && !trailName(f)) tUnnamed++;
  });
  var iTotal = intData.features.length - Object.keys(deletedIntIndices).length + addedIntersections.length;
  document.getElementById("statsDisplay").textContent =
    tTotal + " trails (" + tUnnamed + " unnamed) | " + iTotal + " intersections | " +
    changeLog.length + " changes";
}

// --- Legend ---
function updateLegend() {
  var el = document.getElementById("legendPanel");
  if (mode === "trails") {
    el.innerHTML =
      '<div class="legend-row"><div class="legend-line" style="background:#3498db"></div> Named trail</div>' +
      '<div class="legend-row"><div class="legend-line" style="background:#27ae60;height:4px"></div> Renamed / Added</div>' +
      '<div class="legend-row"><div class="legend-line" style="background:#ccc"></div> Deleted</div>' +
      '<div class="legend-row"><div class="legend-line" style="background:#e67e22;height:5px"></div> Selected</div>' +
      (showAvailable ? '<div class="legend-row"><div class="legend-line" style="background:#e74c3c;height:3px;border-top:1px dashed #e74c3c"></div> Available (old data)</div>' : '');
  } else {
    el.innerHTML =
      '<div class="legend-row"><div class="legend-swatch" style="background:#e74c3c"></div> Zone A</div>' +
      '<div class="legend-row"><div class="legend-swatch" style="background:#3498db"></div> Zone B</div>' +
      '<div class="legend-row"><div class="legend-swatch" style="background:#2ecc71"></div> Zone C</div>' +
      '<div class="legend-row"><div class="legend-swatch" style="background:#f39c12"></div> Zone D</div>' +
      '<div class="legend-row"><div class="legend-swatch" style="background:#9b59b6"></div> Zone E</div>' +
      '<div class="legend-row"><div class="legend-swatch" style="background:#1abc9c"></div> Zone F</div>' +
      '<div class="legend-row"><div class="legend-swatch" style="background:#90a4ae;width:8px;height:8px"></div> Unmarked junction (no sign)</div>';
  }
}

// --- Drawing a missing trail. Each click adds a point; a click within SNAP_PX of a trail
// lands on it, so the new trail joins it there (add_junctions.py then adds the junction).
// A clear layer over the map takes the clicks, even on top of trails.
var SNAP_PX = 12;
var drawPts = [], drawLine = null, drawDots = null, drawCatcher = null, drawnCount = 0;

function startDrawing() {
  drawPts = [];
  if (!map.getPane("drawPane")) map.createPane("drawPane").style.zIndex = 650;
  drawDots = L.layerGroup().addTo(map);
  drawLine = L.polyline([], {color: "#27ae60", weight: 4, dashArray: "6,4", interactive: false}).addTo(map);
  drawCatcher = L.rectangle([[-85, -180], [85, 180]], {pane: "drawPane", stroke: false, fillOpacity: 0.001, cursor: "crosshair"}).addTo(map);
  drawCatcher.on("click", function(e) { addDrawPoint(e.latlng); });
  showDrawPanel();
}

function stopDrawing() {
  [drawLine, drawDots, drawCatcher].forEach(function(l) { if (l) map.removeLayer(l); });
  drawLine = drawDots = drawCatcher = null;
  drawPts = [];
}

// The nearest point on a trail to a click, if within SNAP_PX: {ll, name} or null
function snapToTrail(ll) {
  var p = map.latLngToLayerPoint(ll), best = null, bestD = SNAP_PX;
  trailData.features.forEach(function(f) {
    if (deletedTrailIds[f.properties.id]) return;
    var c = f.geometry.type === "LineString" ? f.geometry.coordinates : [].concat.apply([], f.geometry.coordinates);
    for (var i = 0; i < c.length - 1; i++) {
      var a = map.latLngToLayerPoint([c[i][1], c[i][0]]), b = map.latLngToLayerPoint([c[i + 1][1], c[i + 1][0]]);
      var vx = b.x - a.x, vy = b.y - a.y, L2 = vx * vx + vy * vy || 1e-9;
      var t = Math.max(0, Math.min(1, ((p.x - a.x) * vx + (p.y - a.y) * vy) / L2));
      var q = L.point(a.x + t * vx, a.y + t * vy), d = q.distanceTo(p);
      if (d < bestD) { bestD = d; best = {ll: map.layerPointToLatLng(q), name: trailName(f) || "(unnamed)"}; }
    }
  });
  return best;
}

function addDrawPoint(ll) {
  var snap = snapToTrail(ll), at = snap ? snap.ll : ll;
  drawPts.push({ll: at, onto: snap ? snap.name : null});
  L.circleMarker(at, {radius: snap ? 6 : 4, color: snap ? "#e67e22" : "#27ae60", weight: 2, fillOpacity: 1,
                      fillColor: "#fff", interactive: false}).addTo(drawDots);
  drawLine.setLatLngs(drawPts.map(function(q) { return q.ll; }));
  showDrawPanel();
}

function undoDrawPoint() {
  drawPts.pop();
  var dots = drawDots.getLayers();
  if (dots.length) drawDots.removeLayer(dots[dots.length - 1]);
  drawLine.setLatLngs(drawPts.map(function(q) { return q.ll; }));
  showDrawPanel();
}

function drawnLength() {
  var m = 0;
  for (var i = 1; i < drawPts.length; i++) m += drawPts[i - 1].ll.distanceTo(drawPts[i].ll);
  return m;
}

function showDrawPanel() {
  var ends = drawPts.length ? [drawPts[0], drawPts[drawPts.length - 1]] : [];
  var joins = drawPts.filter(function(q) { return q.onto; }).map(function(q) { return q.onto; });
  document.getElementById("panelContent").innerHTML =
    '<p style="font-size:12px;color:#555">Click along the trail. A click near an existing trail lands on it ' +
    '(orange), so the new one joins it there.</p>' +
    '<p><strong>' + drawPts.length + '</strong> points, <strong>' + Math.round(drawnLength()) + ' m</strong>' +
    (joins.length ? '<br><span style="font-size:12px">joins: ' + joins.join(", ") + '</span>' : '') + '</p>' +
    '<input type="text" id="drawNameInput" placeholder="Trail name...">' +
    '<div class="btn-row">' +
    '<button class="btn btn-green" onclick="finishDrawing()"' + (drawPts.length < 2 ? ' disabled' : '') + '>Add Trail</button>' +
    '<button class="btn btn-gray" onclick="undoDrawPoint()"' + (drawPts.length ? '' : ' disabled') + '>Undo point</button>' +
    '<button class="btn btn-gray" onclick="stopDrawing(); startDrawing()">Clear</button>' +
    '</div>';
}

function finishDrawing() {
  if (drawPts.length < 2) return;
  var name = (document.getElementById("drawNameInput").value || "").trim();
  var newId = "drawn_" + Date.now() + "_" + (++drawnCount);
  var feature = {type: "Feature", properties: {id: newId, name: name, pdf_name: name, source: "drawn in the editor"},
                 geometry: {type: "LineString", coordinates: drawPts.map(function(q) {
                   return [Math.round(q.ll.lng * 1e7) / 1e7, Math.round(q.ll.lat * 1e7) / 1e7]; })}};
  trailData.features.push(feature);
  var layer = L.geoJSON(feature, {style: function() { return {color: "#27ae60", weight: 4, opacity: 0.9}; }}).addTo(map);
  trailLayerById[newId] = layer;
  addChange("added", "Trail: " + (name || "(unnamed)") + " (drawn, " + Math.round(drawnLength()) + " m)", newId, function() {
    trailData.features = trailData.features.filter(function(f) { return f.properties.id !== newId; });
    map.removeLayer(layer);
    delete trailLayerById[newId];
  });
  stopDrawing();
  startDrawing();
  updateStats();
}

// --- Export ---
function exportTrails() {
  var out = JSON.parse(JSON.stringify(trailData));
  out.features = out.features.filter(function(f) { return !deletedTrailIds[f.properties.id]; });
  out.features.forEach(function(f) {
    var fid = f.properties.id;
    if (trailRenames[fid]) {
      f.properties.pdf_name = trailRenames[fid];
      f.properties.name = trailRenames[fid];
    }
  });
  var added = Object.keys(addedFromOld).length + drawnCount;
  var deleted = Object.keys(deletedTrailIds).length;
  var renamed = Object.keys(trailRenames).length;
  console.log("Exporting " + out.features.length + " trails (" + added + " added, " + deleted + " deleted, " + renamed + " renamed)");
  downloadJSON(out, "trails_selected.geojson");
}

function exportIntersections() {
  var out = JSON.parse(JSON.stringify(intData));
  // Rezone by original index before removing anything, so indices still line up
  out.features.forEach(function(f, idx) {
    if (intReZones[idx] !== undefined) f.properties.zone = intReZones[idx];
  });
  out.features = out.features.filter(function(f, idx) { return !deletedIntIndices[idx]; });
  addedIntersections.forEach(function(a) {
    if (!deletedIntIndices[a.idx]) {
      var f = JSON.parse(JSON.stringify(a.feature));
      f.properties.zone = intZone(a.feature, a.idx);
      out.features.push(f);
    }
  });
  downloadJSON(out, "intersections_zoned.geojson");
}

function downloadJSON(obj, filename) {
  var json = JSON.stringify(obj, null, 2);
  var blob = new Blob([json], {type: "application/json"});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

// Keyboard shortcuts
document.addEventListener("keydown", function(e) {
  if (e.key === "Enter" && mode === "trails") {
    if (document.getElementById("trailNameInput")) {
      var fid = selectedTrailFeature && selectedTrailFeature.properties.id;
      if (fid) saveTrailName(fid);
    } else if (document.getElementById("addTrailNameInput")) {
      addOldTrail();
    }
  }
  if (e.key === "Escape") {
    if (addingIntersection) cancelAdd();
    else clearSelection();
    if (mode === "trails") showDefaultPanel();
    else showIntDefault();
  }
});

// Init
updateLegend();
updateStats();
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
