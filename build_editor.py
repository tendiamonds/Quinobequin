"""
Build the trail/intersection editor (trail_editor.html).

Embeds trails_selected.geojson and intersections_zoned.geojson into
a standalone Leaflet-based editing tool with these capabilities:

Trails:  rename, delete
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
    int_file = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\jbreslau\Downloads\intersections_zoned.geojson"
    print("Trail source: %s" % trail_file)
    print("Intersection source: %s" % int_file)
    with open(int_file) as f:
        ints = json.load(f)
    with open(rf"{PROJ}\trails_selected.geojson") as f:
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
  @keyframes pulse-ring { 0% { opacity: 0.8; } 50% { opacity: 0.3; } 100% { opacity: 0.8; } }
  .prox-warn-ring { animation: pulse-ring 1.2s ease-in-out infinite; }
</style>
</head>
<body>
<div class="topbar">
  <span class="title">Trail Editor</span>
  <span class="sep">|</span>
  <button class="mode-btn active" id="modeTrails" onclick="setMode('trails')">Trails</button>
  <button class="mode-btn" id="modeInts" onclick="setMode('intersections')">Intersections</button>
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

intData.features.forEach(function(f, idx) {
  var n = f.properties.number || 0;
  if (n >= nextIntNumber) nextIntNumber = n + 1;
  intFeatureByIdx[idx] = f;
});

function intZone(f, idx) {
  if (intReZones[idx] !== undefined) return intReZones[idx];
  return f.properties.zone;
}

function addIntMarker(f, idx) {
  var zone = intZone(f, idx);
  var ll = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
  var color = ZONE_COLORS[zone] || "#888";
  var marker = L.circleMarker(ll, {
    radius: 7, fillColor: color, color: "#fff", weight: 2, fillOpacity: 0.85
  }).addTo(map);
  marker._idx = idx;
  marker._zone = zone;
  marker.on("click", function(e) {
    L.DomEvent.stopPropagation(e);
    if (mode === "intersections" && !addingIntersection) selectIntersection(f, idx, marker);
  });
  intMarkers[idx] = marker;

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

function getActiveIntersections() {
  var active = [];
  intData.features.forEach(function(f, idx) {
    if (!deletedIntIndices[idx]) {
      var c = f.geometry.coordinates;
      active.push({lon: c[0], lat: c[1], idx: idx, zone: intZone(f, idx)});
    }
  });
  addedIntersections.forEach(function(a) {
    var c = a.feature.geometry.coordinates;
    active.push({lon: c[0], lat: c[1], idx: a.idx, zone: a.feature.properties.zone});
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
  mode = m;
  document.getElementById("modeTrails").classList.toggle("active", m === "trails");
  document.getElementById("modeInts").classList.toggle("active", m === "intersections");
  clearSelection();
  cancelAdd();
  updateLegend();
  if (m === "trails") {
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
    '<tr><td>Trail</td><td><strong>' + (name || '<em style="color:#999">unnamed</em>') + '</strong></td></tr>' +
    '<tr><td>ID</td><td style="font-size:11px;color:#888">' + fid + '</td></tr>' +
    (p.surface ? '<tr><td>Surface</td><td>' + p.surface + '</td></tr>' : '') +
    (p.highway ? '<tr><td>Type</td><td>' + p.highway + '</td></tr>' : '') +
    '</table>' +
    '<input type="text" id="trailNameInput" placeholder="Enter trail name..." value="' + (name || '') + '">' +
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
    '<label style="font-size:12px;font-weight:600;color:#555;margin-top:8px;display:block">Change zone:</label>' +
    '<select id="zoneSelect">' + zoneOptions + '</select>' +
    '<div class="btn-row">' +
    '<button class="btn btn-blue" onclick="saveIntZone(' + idx + ')">Save Zone</button>' +
    '<button class="btn btn-red" onclick="deleteIntersection(' + idx + ')">Remove</button>' +
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

function deleteIntersection(idx) {
  var f = intFeatureByIdx[idx] || intData.features[idx];
  deletedIntIndices[idx] = true;
  if (intMarkers[idx]) { map.removeLayer(intMarkers[idx]); delete intMarkers[idx]; }
  if (intLabels[idx]) { map.removeLayer(intLabels[idx]); delete intLabels[idx]; }
  addChange("removed", "Intersection #" + (f.properties.number || "?") + " (zone " + intZone(f, idx) + ")", idx, function() {
    delete deletedIntIndices[idx];
    addIntMarker(f, idx);
  });
  clearSelection();
  updateStats();
}

function refreshIntMarker(f, idx) {
  if (intMarkers[idx]) map.removeLayer(intMarkers[idx]);
  if (intLabels[idx]) map.removeLayer(intLabels[idx]);
  if (!deletedIntIndices[idx]) addIntMarker(f, idx);
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
  var idx = "new_" + addedIntersections.length;
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
    selectedIntMarker.setStyle({fillColor: ZONE_COLORS[zone] || "#888", radius: 7, weight: 2, color: "#fff", fillOpacity: 0.85});
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
      '<div class="legend-row"><div class="legend-swatch" style="background:#1abc9c"></div> Zone F</div>';
  }
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
  var added = Object.keys(addedFromOld).length;
  var deleted = Object.keys(deletedTrailIds).length;
  var renamed = Object.keys(trailRenames).length;
  console.log("Exporting " + out.features.length + " trails (" + added + " added, " + deleted + " deleted, " + renamed + " renamed)");
  downloadJSON(out, "trails_selected.geojson");
}

function exportIntersections() {
  var out = JSON.parse(JSON.stringify(intData));
  out.features = out.features.filter(function(f, idx) { return !deletedIntIndices[idx]; });
  out.features.forEach(function(f, idx) {
    if (intReZones[idx] !== undefined) f.properties.zone = intReZones[idx];
  });
  addedIntersections.forEach(function(a) {
    out.features.push(JSON.parse(JSON.stringify(a.feature)));
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
