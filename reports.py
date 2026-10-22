"""
Reports, saved as you go and sent together. Shared by the regions' sites.

Out on a walk, a report takes a tap or two from the map (its Report button, or "Report"
in a trail's or intersection's details): a blaze you can see, picked by color, or a note.
Each one is saved on the phone with where you were (and how sure the phone was of it),
which way you were heading, and what the map has there: the trail, the sign-to-sign
stretch, and the blazes it expects. Nothing is sent as you go. The Reports page lists
what's saved, and "Send all" emails the unsent ones together, as text to read and a data
block for the map's tools to read back in.

Field checks (things to look at on the next walk, at particular intersections) are
answered the same way: from a badge on the intersection, the "Check here" note when
you're near one, or the Reports page. An answer is a report like any other.

  build_reports_page(path, title=..., css=..., nav=..., storage_prefix=..., email=...,
                     blazes=..., checks=..., checks_intro=...)

REPORTS_JS is the part the map shares (trailmap.py): it expects REPORTS_KEY,
REPORT_EMAIL, REPORT_TITLE, REPORT_BLAZES and REPORT_CHECKS to be defined first.
"""

import html
import json
import os

from checks import DESK, desk_rows, write_desk_files

REPORTS_JS = r"""
// --- Saved reports (reports.py), shared by the map and the Reports page through the
// phone's storage. A report: {id, when, kind ("blaze", "note", "check" or "sign"),
// blaze (a blaze key, "other" or "none"), check (its id), answer, text, at ({lat, lon,
// acc} or null), heading (degrees or null), about ({what: "int" or "trail", ref, extra}
// or null), ctx (what the map had there: {trail, stretch, expect: [blaze keys], near,
// nearM}), sent (when, or null)}
function loadReports() {
  try { return JSON.parse(localStorage.getItem(REPORTS_KEY)) || []; } catch (e) { return []; }
}
function storeReports(list) { try { localStorage.setItem(REPORTS_KEY, JSON.stringify(list)); } catch (e) {} }
function addReport(r) {
  var list = loadReports();
  r.id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  r.when = new Date().toISOString();
  r.sent = null;
  list.push(r);
  storeReports(list);
  return r;
}
function changeReport(id, fn) {
  var list = loadReports();
  list.forEach(function(r) { if (r.id === id) fn(r); });
  storeReports(list);
}
function dropReport(id) { storeReports(loadReports().filter(function(r) { return r.id !== id; })); }
function unsentReports() { return loadReports().filter(function(r) { return !r.sent; }); }
function checkById(id) { return REPORT_CHECKS.filter(function(c) { return c.id === id; })[0] || null; }
// The latest answer saved for a check, or null
function checkAnswer(id) {
  var hits = loadReports().filter(function(r) { return r.kind === "check" && r.check === id; });
  return hits.length ? hits[hits.length - 1] : null;
}

function blazeWords(key) {
  return key === "none" ? "no blaze here" : key === "other" ? "another color"
    : REPORT_BLAZES[key] ? REPORT_BLAZES[key].pick || REPORT_BLAZES[key].marks : key;
}
function reportHeadline(r) {
  // Another color: the color is what was typed for it ("purple"), if anything
  if (r.kind === "blaze" && r.blaze === "other") return "Blaze: " + (r.text || "another color (not said which)");
  if (r.kind === "blaze") return "Blaze: " + blazeWords(r.blaze);
  if (r.kind === "check") {
    var c = checkById(r.check);
    return "Check" + (c ? " at " + c.label : "") + ": " + r.answer;
  }
  if (r.kind === "sign") return "Standing at sign " + (r.about ? r.about.ref : "");
  return "Note";
}
function fmtCoords(at) { return at.lat.toFixed(6) + ", " + at.lon.toFixed(6); }
// The lines under a report's headline, for the list and the email
function reportDetails(r) {
  var out = [];
  if (r.kind === "check") {
    var c = checkById(r.check);
    if (c) out.push(c.question);
  }
  if (r.about && r.kind !== "check") out.push("About: " + (r.about.what === "trail" ? "trail " : "") + r.about.ref + (r.about.extra ? " (" + r.about.extra + ")" : ""));
  var x = r.ctx;
  if (x && x.trail) {
    out.push("On " + x.trail + ", " + x.stretch +
             (r.kind === "blaze" ? " (the map has " + (x.expect && x.expect.length ? x.expect.map(blazeWords).join(", ") : "no blaze") + ")" : ""));
  } else if (x && x.near) {
    out.push(x.nearM ? "Off trail, " + x.nearM + " m from " + x.near : "At " + x.near);
  }
  out.push(r.at ? "At " + fmtCoords(r.at) + " (+/- " + r.at.acc + " m)" + (r.heading !== null && r.heading !== undefined ? ", heading " + r.heading + "°" : "")
                : "Location not available");
  if (r.text && !(r.kind === "blaze" && r.blaze === "other")) out.push("Note: " + r.text);
  return out;
}
function reportsText(list) {
  var lines = [REPORT_TITLE + " — " + list.length + " report" + (list.length === 1 ? "" : "s"), ""];
  list.forEach(function(r, i) {
    lines.push((i + 1) + ". " + reportHeadline(r) + " — " + new Date(r.when).toLocaleString());
    reportDetails(r).forEach(function(l) { lines.push("   " + l); });
  });
  lines.push("", "Device: " + navigator.userAgent, "", "--- data (for the map's tools) ---", JSON.stringify(list));
  return lines.join("\n");
}
// Opens the mail app with the unsent reports, and marks them sent. Returns how many.
function sendReports() {
  var list = unsentReports();
  if (list.length) {
    location.href = "mailto:" + REPORT_EMAIL + "?subject=" + encodeURIComponent(REPORT_TITLE + ": " + list.length + " report" +
      (list.length === 1 ? "" : "s")) + "&body=" + encodeURIComponent(reportsText(list));
    var now = new Date().toISOString(), all = loadReports();
    all.forEach(function(r) { if (!r.sent) r.sent = now; });
    storeReports(all);
  }
  return list.length;
}

// Once: answers saved on the old Checks page become reports (already sent from there)
(function() {
  var oldKey = REPORTS_KEY.replace(/Reports$/, "Checks"), moved = REPORTS_KEY + "MovedChecks";
  try {
    if (localStorage.getItem(moved)) return;
    var old = JSON.parse(localStorage.getItem(oldKey) || "{}"), list = loadReports();
    Object.keys(old).forEach(function(id) {
      var s = old[id];
      list.push({id: "old-" + id, when: s.when, kind: "check", check: id, answer: s.answer, text: s.note || "",
                 at: s.lat ? {lat: s.lat, lon: s.lon, acc: Math.round(s.acc)} : null, heading: null, about: null, ctx: null,
                 sent: s.when});
    });
    storeReports(list);
    localStorage.setItem(moved, "1");
  } catch (e) {}
})();
"""

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
  .bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 4px 0 14px; }
  .bar .progress { font-weight: 600; margin-right: auto; }
  .btn2 { border: none; border-radius: 6px; padding: 9px 14px; font-size: 14px; font-weight: 600; cursor: pointer;
          background: #0d47a1; color: white; }
  .btn2.quiet { background: #eceff1; color: #263238; }
  .btn2:disabled { opacity: 0.45; cursor: default; }
  .where { font-size: 12px; color: #607d8b; margin: 0 0 12px; }
  .msg { font-size: 13px; color: #2e7d32; margin: -6px 0 12px; }
  h2 { font-size: 17px; margin: 22px 0 8px; }
  .card { border: 1px solid #dde3e7; border-radius: 10px; padding: 12px 14px; margin: 0 0 12px; background: #fff; }
  .card.done { background: #f3f8f4; border-color: #b9dcc0; }
  .card.sent { background: #f7f8f9; color: #546e7a; }
  .card-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 4px; }
  .card-head .lbl { font-size: 15px; font-weight: 700; }
  .card-head .dist, .card-head .when { margin-left: auto; font-size: 12px; color: #546e7a; white-space: nowrap; }
  .card-head a { font-size: 13px; }
  .detail { font-size: 13px; color: #455a64; margin: 2px 0; }
  .card-actions { margin-top: 8px; display: flex; gap: 10px; font-size: 13px; }
  .card-actions a { cursor: pointer; color: #0277bd; }
  .picks { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 10px; }
  .pick { display: inline-flex; align-items: center; gap: 6px; border: 1px solid #b0bec5; border-radius: 18px;
          padding: 7px 12px; font-size: 14px; background: #fff; cursor: pointer; }
  .pick:active { background: #e3f2fd; }
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
  .empty { font-size: 13px; color: #78909c; margin: 4px 0 12px; }
  details summary { cursor: pointer; font-size: 15px; font-weight: 600; margin: 22px 0 8px; }
  .desk { margin-top: 28px; }
  .desk h2 { font-size: 18px; margin-bottom: 8px; }
  .desk p { font-size: 13px; color: #455a64; margin: 6px 0; }
  .desk table { border-collapse: collapse; width: 100%; font-size: 13px; margin: 10px 0; }
  .desk th, .desk td { border: 1px solid #dde3e7; padding: 5px 8px; text-align: left; vertical-align: top; }
  .desk th { background: #eceff1; }
  .desk td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
</style>
</head>
<body>
__NAV__
<div class="container">
<h1>Reports</h1>
<p class="subtitle">Everything you report is kept on this phone until you send it. Out on the trail, the map's
Report button is the quickest way: a tap on a blaze's color records it right where you are.</p>
<div class="bar">
  <span class="progress" id="progress"></span>
  <button class="btn2 quiet" onclick="copyAll()">Copy</button>
  <button class="btn2" id="sendBtn" onclick="sendAll()">Send all</button>
</div>
<div class="msg" id="msg"></div>
<div class="where" id="where">Finding where you are… (allow location so reports record where you are)</div>

<div class="card" id="new">
  <div class="card-head"><span class="lbl">New report</span></div>
  <div id="newBlazes"></div>
  <textarea id="newNote" rows="2" placeholder="Something else? What did you see?"></textarea>
  <div style="margin-top:8px"><button class="btn2" onclick="saveNote()">Save note</button></div>
  <div class="warn" id="newWarn"></div>
</div>

<h2>Not sent yet</h2>
<div id="unsent"></div>

<div id="checksWrap">
<h2 id="checks">Field checks</h2>
<p class="subtitle" style="margin-top:-4px">__CHECKS_INTRO__</p>
<div id="cards"></div>
</div>

<details id="sentWrap"><summary id="sentHead">Sent</summary><div id="sent"></div>
  <button class="btn2 quiet" onclick="clearSent()">Clear sent reports</button></details>
__DESK__
</div>
<script>
var REPORTS_KEY = __KEY__, REPORT_EMAIL = __EMAIL__, REPORT_TITLE = __TITLE_JS__;
var REPORT_BLAZES = __BLAZES__, REPORT_CHECKS = __CHECKS__;
__REPORTS_JS__
var here = null;   // {lat, lon, acc}
var drafts = {};   // check answers picked and notes typed but not saved yet, kept through redraws

function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }
function jsq(s) { return "'" + String(s).replace(/\\/g, "\\\\").replace(/'/g, "\\'") + "'"; }
function distM(a, b) { var dx = (a.lon - b.lon) * 82000, dy = (a.lat - b.lat) * 111000; return Math.sqrt(dx * dx + dy * dy); }
function fmtDist(m) { var ft = m * 3.28084; return ft < 1000 ? Math.round(ft / 10) * 10 + " ft" : (m / 1609.344).toFixed(1) + " mi"; }
function say(t) { document.getElementById("msg").textContent = t || ""; }
function where() { return here ? {lat: +here.lat.toFixed(6), lon: +here.lon.toFixed(6), acc: Math.round(here.acc)} : null; }

// A blaze's mark, small: a bar for paint blazes, a dot, or a triangle
function blazeSwatch(key) {
  var b = REPORT_BLAZES[key], c = b.color, edge = c.toLowerCase() === "#ffffff" ? "#555" : "#0d47a1";
  var shape = b.style === "dots" ? '<circle cx="7" cy="7" r="5" fill="' + c + '" stroke="' + edge + '"/>'
    : b.style === "arrows" ? '<path d="M7 1 L13 13 L1 13 Z" fill="' + c + '" stroke="' + edge + '"/>'
    : '<rect x="4" y="1" width="6" height="12" fill="' + c + '" stroke="' + edge + '"/>';
  return '<svg width="14" height="14" viewBox="0 0 14 14">' + shape + '</svg>';
}

function newReportHtml() {
  var keys = Object.keys(REPORT_BLAZES);
  if (!keys.length) return '';
  return '<div class="detail">A blaze you can see here:</div><div class="picks">' +
    keys.map(function(k) { return '<button class="pick" onclick="saveBlaze(' + jsq(k) + ')">' + blazeSwatch(k) + esc(blazeWords(k)) + '</button>'; }).join('') +
    '<button class="pick" onclick="saveBlaze(\'other\')">Another color</button>' +
    '<button class="pick" onclick="saveBlaze(\'none\')">No blaze here</button></div>';
}

function saveBlaze(key) {
  var note = document.getElementById("newNote").value.trim();
  if (key === "other" && !note) {
    document.getElementById("newWarn").textContent = "Say which color in the note, then tap Another color again.";
    return;
  }
  addReport({kind: "blaze", blaze: key, text: note, at: where(), heading: null, about: null, ctx: null});
  document.getElementById("newNote").value = "";
  document.getElementById("newWarn").textContent = "";
  say("Saved: " + blazeWords(key) + (here ? "" : " (no location: it's off)"));
  render();
}

function saveNote() {
  var note = document.getElementById("newNote").value.trim();
  if (!note) { document.getElementById("newWarn").textContent = "Type what you saw first."; return; }
  addReport({kind: "note", text: note, at: where(), heading: null, about: null, ctx: null});
  document.getElementById("newNote").value = "";
  document.getElementById("newWarn").textContent = "";
  say("Saved." + (here ? "" : " (No location: it's off.)"));
  render();
}

function reportCardHtml(r) {
  var map = r.at ? 'https://www.google.com/maps/search/?api=1&query=' + r.at.lat + ',' + r.at.lon : null;
  return '<div class="card' + (r.sent ? ' sent' : '') + '"><div class="card-head"><span class="lbl">' + esc(reportHeadline(r)) + '</span>' +
    '<span class="when">' + esc(new Date(r.when).toLocaleString()) + '</span></div>' +
    reportDetails(r).map(function(l) { return '<div class="detail">' + esc(l) + '</div>'; }).join('') +
    '<div class="card-actions">' + (map ? '<a href="' + map + '">Open in maps</a>' : '') +
    (r.sent ? '<a onclick="unsend(' + jsq(r.id) + ')">Mark not sent</a>'
            : '<a onclick="editNote(' + jsq(r.id) + ')">' + (r.text ? 'Edit note' : 'Add a note') + '</a>') +
    '<a onclick="removeIt(' + jsq(r.id) + ')">Delete</a></div></div>';
}

function editNote(id) {
  var r = loadReports().filter(function(x) { return x.id === id; })[0];
  var t = window.prompt("Note:", r && r.text || "");
  if (t !== null) { changeReport(id, function(x) { x.text = t.trim(); }); render(); }
}
function removeIt(id) { if (window.confirm("Delete this report?")) { dropReport(id); render(); } }
function unsend(id) { changeReport(id, function(x) { x.sent = null; }); render(); }
function clearSent() {
  if (window.confirm("Delete every sent report from this phone?")) { storeReports(unsentReports()); render(); }
}

function sendAll() {
  var n = sendReports();
  say(n ? "Your mail app should open with " + n + " report" + (n === 1 ? "" : "s") + "; send it from there. They're now under Sent." : "Nothing to send.");
  render();
}
function copyAll() {
  var list = unsentReports(), text = reportsText(list);
  (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function() {
    say("Copied " + list.length + " report" + (list.length === 1 ? "" : "s") + "; paste them anywhere.");
  }, function() { window.prompt("Copy the reports:", text); });
}

// --- Field checks
function checkCardHtml(c) {
  var s = checkAnswer(c.id), d = drafts[c.id] || {};
  var html = '<div class="card' + (s ? ' done' : '') + '" id="check-' + esc(c.label) + '">' +
    '<div class="card-head"><span class="lbl">' + esc(c.label) + '</span><a href="map.html?int=' + encodeURIComponent(c.label) + '">map</a>' +
    '<span class="dist" id="dist-' + esc(c.id) + '"></span></div>' +
    '<div class="detail">Map has it at <a href="https://www.google.com/maps/search/?api=1&query=' + c.lat + ',' + c.lon + '">' +
      c.lat.toFixed(6) + ', ' + c.lon.toFixed(6) + '</a></div>' +
    '<div class="q">' + esc(c.question) + '</div>' +
    (c.why ? '<div class="why"><b>Why:</b> ' + esc(c.why) + '</div>' : '') +
    (c.look_for ? '<div class="look"><b>Look for:</b> ' + esc(c.look_for) + '</div>' : '') +
    '<div class="choices">';
  c.choices.forEach(function(ch) {
    var on = d.answer !== undefined ? d.answer === ch : !!s && s.answer === ch;
    html += '<label class="' + (on ? 'on' : '') + '"><input type="radio" name="ch-' + esc(c.id) + '" value="' + esc(ch) + '"' +
      (on ? ' checked' : '') + ' onchange="pick(this, ' + jsq(c.id) + ')">' + esc(ch) + '</label>';
  });
  html += '</div><textarea id="note-' + esc(c.id) + '" rows="2" placeholder="Notes (optional): what you saw" oninput="draft(' + jsq(c.id) +
    ').note = this.value">' + esc(d.note || '') + '</textarea>' +
    '<div style="margin-top:8px"><button class="btn2" onclick="saveCheck(' + jsq(c.id) + ')">' + (s ? 'Save another answer' : 'Save') + '</button></div>' +
    '<div class="warn" id="warn-' + esc(c.id) + '"></div>' +
    (s ? '<div class="saved">✓ ' + esc(s.answer) + ', saved ' + esc(new Date(s.when).toLocaleString()) +
      (s.at ? ', ' + fmtDist(distM(s.at, c)) + ' from the map\'s spot' : ', location not available') + (s.sent ? ' (sent)' : '') + '</div>' : '') +
    '</div>';
  return html;
}
function draft(id) { return drafts[id] || (drafts[id] = {}); }
function pick(input, id) {
  input.closest(".choices").querySelectorAll("label").forEach(function(l) { l.classList.toggle("on", l.contains(input)); });
  draft(id).answer = input.value;
}
function saveCheck(id) {
  var c = checkById(id), picked = document.querySelector('input[name="ch-' + id + '"]:checked');
  if (!picked) { document.getElementById("warn-" + id).textContent = "Pick an answer first."; return; }
  addReport({kind: "check", check: id, answer: picked.value, text: document.getElementById("note-" + id).value.trim(),
             at: where(), heading: null, about: {what: "int", ref: c.label, extra: ""}, ctx: null});
  delete drafts[id];
  say("Saved your answer for " + c.label + ".");
  render();
}
function showDistances() {
  REPORT_CHECKS.forEach(function(c) {
    var el = document.getElementById("dist-" + c.id);
    if (el) el.textContent = here ? fmtDist(distM(here, c)) + " away" : "";
  });
}

function render() {
  var all = loadReports(), unsent = all.filter(function(r) { return !r.sent; }), sent = all.filter(function(r) { return r.sent; });
  document.getElementById("progress").textContent = unsent.length + " not sent yet";
  document.getElementById("sendBtn").disabled = !unsent.length;
  document.getElementById("newBlazes").innerHTML = newReportHtml();
  document.getElementById("unsent").innerHTML = unsent.length ? unsent.slice().reverse().map(reportCardHtml).join('')
    : '<div class="empty">Nothing waiting to be sent.</div>';
  document.getElementById("sentWrap").style.display = sent.length ? "" : "none";
  document.getElementById("sentHead").textContent = "Sent (" + sent.length + ")";
  document.getElementById("sent").innerHTML = sent.slice().reverse().map(reportCardHtml).join('');
  document.getElementById("checksWrap").style.display = REPORT_CHECKS.length ? "" : "none";
  var checks = REPORT_CHECKS.slice();
  if (here) checks.sort(function(a, b) { return distM(here, a) - distM(here, b); });
  document.getElementById("cards").innerHTML = checks.map(checkCardHtml).join('');
  showDistances();
}

// The desk table, tab-separated, for a spreadsheet or GIS
function copyTable() {
  var text = [...document.querySelectorAll("#deskTable tr")].map(function(tr) {
    return [...tr.children].slice(0, 4).map(function(td) { return td.innerText.trim(); }).join("\t");
  }).join("\n");
  (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function() {
    document.getElementById("deskCopied").textContent = "Copied.";
  }, function() { window.prompt("Copy the table:", text); });
}

if (navigator.geolocation) {
  var first = true;
  navigator.geolocation.watchPosition(function(pos) {
    here = {lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy};
    document.getElementById("where").textContent = "You're at " + here.lat.toFixed(5) + ", " + here.lon.toFixed(5) +
      " (± " + Math.round(here.acc) + " m). Reports record this spot.";
    if (first) { first = false; render(); } else { showDistances(); }
  }, function() {
    document.getElementById("where").textContent = "Location is off, so reports won't record where you are.";
  }, {enableHighAccuracy: true, maximumAge: 5000});
}
render();
if (location.hash) { var el = document.getElementById(decodeURIComponent(location.hash.slice(1))); if (el) el.scrollIntoView(); }
</script>
</body>
</html>
"""

# Old links to the checks page (checks.html#A5) land on the check's card here
REDIRECT = """<!DOCTYPE html><meta charset="utf-8"><title>Field checks</title>
<script>location.replace("reports.html#" + (location.hash ? "check-" + location.hash.slice(1) : "checks"));</script>
<a href="reports.html#checks">Field checks are now on the Reports page</a>
"""


def build_reports_page(path, title, css, nav, storage_prefix, email, blazes, checks, checks_intro=""):
    """Write the Reports page (reports.html), checks.html pointing to it, and the checks'
    desk files (checks.csv, checks.geojson)"""
    # The emails name the place, as the map's do ("Reports — Blue Hills" -> "Blue Hills")
    place = title.split(" — ", 1)[-1]
    page = (PAGE.replace("__TITLE__", html.escape(title))
            .replace("__TITLE_JS__", json.dumps(place))
            .replace("__CSS__", css)
            .replace("__NAV__", nav)
            .replace("__CHECKS_INTRO__", checks_intro)   # HTML, from our own build scripts
            .replace("__KEY__", json.dumps(storage_prefix + "Reports"))
            .replace("__EMAIL__", json.dumps(email))
            .replace("__BLAZES__", json.dumps(blazes or {}))
            .replace("__CHECKS__", json.dumps(checks))
            .replace("__DESK__", DESK % desk_rows(checks) if checks else "")
            .replace("__REPORTS_JS__", REPORTS_JS))
    folder = os.path.dirname(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    with open(os.path.join(folder, "checks.html"), "w", encoding="utf-8") as f:
        f.write(REDIRECT)
    if checks:
        write_desk_files(checks, folder)
    print("Wrote %s (%d checks)" % (path, len(checks)))
