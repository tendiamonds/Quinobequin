"""
Field checks: things to check at particular intersections on the next walk. They're
answered on the map and the Reports page (reports.py); this has what's left of the old
Checks page, the part for a desk review: a table of where the map has each one, and the
same as checks.csv and checks.geojson for GIS.

checks: [{"id", "label", "lat", "lon", "question", "choices": [...], "why", "look_for"}],
one per thing to check ("label" is the intersection).
"""

import csv
import html
import json
import os


DESK = """<div class="desk" id="desk">
<h2>For a desk review</h2>
<p>Where the map has each of these. They're the mapped positions of the trail
intersections, not surveyed post locations, so expect them to be off by several meters.</p>
<p><button class="btn2 quiet" onclick="copyTable()">Copy table</button>
  <a href="checks.csv" download>Download CSV</a> &middot; <a href="checks.geojson" download>Download GeoJSON</a>
  <span id="deskCopied" style="color:#2e7d32;margin-left:6px"></span></p>
<table id="deskTable">
<tr><th>Intersection</th><th>Latitude</th><th>Longitude</th><th>Why it's in question</th><th></th></tr>
%s
</table>
</div>"""


def desk_rows(checks):
    return "\n".join(
        '<tr><td>%s</td><td class="num">%.6f</td><td class="num">%.6f</td><td>%s</td>'
        '<td><a href="map.html?int=%s">map</a></td></tr>'
        % (html.escape(c["label"]), c["lat"], c["lon"], html.escape(c.get("why") or c["question"]), html.escape(c["label"]))
        for c in checks)


def write_desk_files(checks, folder):
    """checks.csv and checks.geojson: where the map has each check, for GIS"""
    with open(os.path.join(folder, "checks.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["intersection", "latitude", "longitude", "question", "why"])
        for c in checks:
            w.writerow([c["label"], "%.6f" % c["lat"], "%.6f" % c["lon"], c["question"], c.get("why", "")])
    features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(c["lon"], 6), round(c["lat"], 6)]},
                 "properties": {"intersection": c["label"], "question": c["question"], "why": c.get("why", "")}}
                for c in checks]
    with open(os.path.join(folder, "checks.geojson"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "FeatureCollection", "features": features}, indent=2) + "\n")
