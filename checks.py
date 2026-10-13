"""
A field checklist page: things to check at particular intersections on the next walk, with
a way to record what you found. Shared by the regions' sites.

  build_checks_page(checks, path, title=..., css=..., nav=..., storage_prefix=..., email=...)

checks: [{"id", "label", "lat", "lon", "question", "choices": [...], "why", "look_for"}],
one per thing to check ("label" is the intersection, for the map link and its card's
anchor, checks.html#A5).

On the page, each answer is saved on the phone (with where you were standing and how
sure the phone was of it), so the page can be closed and opened again. "Send results"
emails them all, the same way the map's problem reports do.
"""

import html
import json

PAGE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#2c3e50">
<title>__TITLE__</title>
<style>__CSS__
  .bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 4px 0 18px; }
  .bar .progress { font-weight: 600; margin-right: auto; }
  .btn2 { border: none; border-radius: 6px; padding: 9px 14px; font-size: 14px; font-weight: 600; cursor: pointer;
          background: #0d47a1; color: white; }
  .btn2.quiet { background: #eceff1; color: #263238; }
  .where { font-size: 12px; color: #607d8b; margin: -10px 0 16px; }
  .card { border: 1px solid #dde3e7; border-radius: 10px; padding: 14px 16px; margin: 0 0 14px; background: #fff; }
  .card.done { background: #f3f8f4; border-color: #b9dcc0; }
  .card-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 6px; }
  .card-head .lbl { font-size: 18px; font-weight: 700; }
  .card-head .dist { margin-left: auto; font-size: 13px; color: #546e7a; white-space: nowrap; }
  .card-head a { font-size: 13px; }
  .q { font-size: 15px; font-weight: 600; margin: 4px 0 6px; }
  .why, .look { font-size: 13px; color: #455a64; margin: 4px 0; }
  .look b, .why b { color: #263238; }
  .choices { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 8px; }
  .choices label { border: 1px solid #b0bec5; border-radius: 18px; padding: 7px 13px; font-size: 14px; cursor: pointer; }
  .choices input { margin-right: 5px; }
  .choices label.on { background: #e3f2fd; border-color: #1565c0; }
  textarea { width: 100%; font: inherit; font-size: 14px; padding: 6px 8px; border: 1px solid #cfd8dc; border-radius: 6px; }
  .saved { font-size: 13px; color: #2e7d32; margin-top: 8px; }
  .warn { font-size: 13px; color: #c62828; margin-top: 6px; }
</style>
</head>
<body>
__NAV__
<div class="container">
<h1>Field Checks</h1>
<p class="subtitle">__SUBTITLE__</p>
<div class="bar">
  <span class="progress" id="progress"></span>
  <button class="btn2 quiet" onclick="sortNearest()">Nearest first</button>
  <button class="btn2 quiet" onclick="copyResults()">Copy results</button>
  <button class="btn2" onclick="sendResults()">Send results</button>
</div>
__TIP__<div class="where" id="where">Finding where you are… (allow location to sort by distance and record where you stand)</div>
<div id="cards"></div>
</div>
<script>
var CHECKS = __CHECKS__;
var SHARED_TIP = __SHARED__;
var KEY = __KEY__, EMAIL = __EMAIL__, TITLE = __TITLE_JS__;
var saved = {};
var drafts = {};   // answers picked and notes typed but not saved yet, kept through redraws
try { saved = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { saved = {}; }
var here = null;   // {lat, lon, acc}

function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }
function distM(a, b) { var dx = (a.lon - b.lon) * 82000, dy = (a.lat - b.lat) * 111000; return Math.sqrt(dx * dx + dy * dy); }
function fmtDist(m) { var ft = m * 3.28084; return ft < 1000 ? Math.round(ft / 10) * 10 + " ft" : (m / 1609.344).toFixed(1) + " mi"; }
function store() { try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {} }

function cardHtml(c) {
  var s = saved[c.id], d = drafts[c.id] || {}, html = '<div class="card' + (s ? ' done' : '') + '" id="' + esc(c.label) + '">' +
    '<div class="card-head"><span class="lbl">' + esc(c.label) + '</span><a href="map.html?int=' + encodeURIComponent(c.label) + '">map</a>' +
    '<span class="dist" id="dist-' + esc(c.id) + '"></span></div>' +
    '<div class="q">' + esc(c.question) + '</div>' +
    (c.why ? '<div class="why"><b>Why:</b> ' + esc(c.why) + '</div>' : '') +
    (c.look_for && !SHARED_TIP ? '<div class="look"><b>Look for:</b> ' + esc(c.look_for) + '</div>' : '') +
    '<div class="choices">';
  c.choices.forEach(function(ch) {
    var on = d.answer !== undefined ? d.answer === ch : !!s && s.answer === ch;
    html += '<label class="' + (on ? 'on' : '') + '"><input type="radio" name="ch-' + esc(c.id) + '" value="' + esc(ch) + '"' +
      (on ? ' checked' : '') + ' onchange="pick(this, \'' + c.id + '\')">' + esc(ch) + '</label>';
  });
  html += '</div><textarea id="note-' + esc(c.id) + '" rows="2" placeholder="Notes (optional): what you saw" oninput="draft(\'' + c.id +
    '\').note = this.value">' + esc(d.note !== undefined ? d.note : s ? s.note : '') + '</textarea>' +
    '<div style="margin-top:8px"><button class="btn2" onclick="save(\'' + c.id + '\')">' + (s ? 'Save again' : 'Save') + '</button>' +
    (s ? ' <button class="btn2 quiet" onclick="unsave(\'' + c.id + '\')">Clear</button>' : '') + '</div>' +
    '<div class="warn" id="warn-' + esc(c.id) + '"></div>' +
    (s ? '<div class="saved">✓ ' + esc(s.answer) + ' — saved ' + esc(new Date(s.when).toLocaleString()) +
      (s.lat ? ', standing at ' + s.lat.toFixed(6) + ', ' + s.lon.toFixed(6) + ' (± ' + Math.round(s.acc) + ' m)' : ', location not available') + '</div>' : '') +
    '</div>';
  return html;
}

function render() {
  document.getElementById("cards").innerHTML = CHECKS.map(cardHtml).join("");
  var n = CHECKS.filter(function(c) { return saved[c.id]; }).length;
  document.getElementById("progress").textContent = n + " of " + CHECKS.length + " checked";
  showDistances();
}

function draft(id) { return drafts[id] || (drafts[id] = {}); }

function pick(input, id) {
  input.closest(".choices").querySelectorAll("label").forEach(function(l) { l.classList.toggle("on", l.contains(input)); });
  draft(id).answer = input.value;
}

function save(id) {
  var c = CHECKS.filter(function(x) { return x.id === id; })[0];
  var picked = document.querySelector('input[name="ch-' + id + '"]:checked');
  if (!picked) { document.getElementById("warn-" + id).textContent = "Pick an answer first."; return; }
  saved[id] = {answer: picked.value, note: document.getElementById("note-" + id).value.trim(), when: new Date().toISOString(),
               lat: here ? here.lat : null, lon: here ? here.lon : null, acc: here ? here.acc : null};
  delete drafts[id];
  store();
  render();
  location.hash = c.label;
}

function unsave(id) { delete saved[id]; delete drafts[id]; store(); render(); }

function showDistances() {
  CHECKS.forEach(function(c) {
    var el = document.getElementById("dist-" + c.id);
    if (el) el.textContent = here ? fmtDist(distM(here, c)) + " away" : "";
  });
}

function sortNearest() {
  if (!here) { document.getElementById("where").textContent = "Your location isn't available yet, so the list can't be sorted by distance."; return; }
  CHECKS.sort(function(a, b) { return distM(here, a) - distM(here, b); });
  render();
}

function resultsText() {
  var lines = [TITLE + " — field check results", ""];
  CHECKS.forEach(function(c) {
    var s = saved[c.id];
    lines.push(c.label + ": " + (s ? s.answer : "not checked yet"));
    if (s) {
      lines.push("  " + c.question);
      lines.push("  When: " + s.when);
      lines.push("  Standing at: " + (s.lat ? s.lat.toFixed(6) + ", " + s.lon.toFixed(6) + " (+/- " + Math.round(s.acc) + " m)" : "location not available"));
      if (s.note) lines.push("  Note: " + s.note);
    }
  });
  lines.push("", "Page: " + location.href.split("#")[0], "Device: " + navigator.userAgent);
  return lines.join("\n");
}

function sendResults() {
  location.href = "mailto:" + EMAIL + "?subject=" + encodeURIComponent(TITLE + ": field check results") +
    "&body=" + encodeURIComponent(resultsText());
}

function copyResults() {
  var text = resultsText();
  (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function() {
    document.getElementById("where").textContent = "Results copied; paste them anywhere.";
  }, function() { window.prompt("Copy the results:", text); });
}

if (navigator.geolocation) {
  var first = true;
  navigator.geolocation.watchPosition(function(pos) {
    here = {lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy};
    document.getElementById("where").textContent = "You're at " + here.lat.toFixed(5) + ", " + here.lon.toFixed(5) +
      " (± " + Math.round(here.acc) + " m). Save records this spot; stand at the post first.";
    if (first) { first = false; sortNearest(); } else { showDistances(); }
  }, function() {
    document.getElementById("where").textContent = "Location is off, so the list isn't sorted by distance and answers won't record where you stood.";
  }, {enableHighAccuracy: true, maximumAge: 5000});
}
render();
if (location.hash) { var el = document.getElementById(decodeURIComponent(location.hash.slice(1))); if (el) el.scrollIntoView(); }
</script>
</body>
</html>
"""


def build_checks_page(checks, path, title, subtitle, css, nav, storage_prefix, email):
    # What to look for, once at the top if it's the same for every check
    tips = {c.get("look_for") for c in checks}
    shared = len(tips) == 1 and next(iter(tips))
    tip = '<p class="look" style="margin:-8px 0 14px"><b>Look for:</b> %s</p>' % html.escape(shared) if shared else ""
    page = (PAGE.replace("__TIP__", tip).replace("__SHARED__", "true" if shared else "false")
            .replace("__TITLE__", html.escape(title))
            .replace("__TITLE_JS__", json.dumps(title))
            .replace("__SUBTITLE__", html.escape(subtitle))
            .replace("__CSS__", css)
            .replace("__NAV__", nav)
            .replace("__CHECKS__", json.dumps(checks))
            .replace("__KEY__", json.dumps(storage_prefix + "Checks"))
            .replace("__EMAIL__", json.dumps(email)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    print("Wrote %s (%d checks)" % (path, len(checks)))
