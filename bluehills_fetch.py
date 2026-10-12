"""
Download what the Blue Hills map is built from, out of OpenStreetMap, into bluehills_data/:
  osm_trails.json     trail ways (path, footway, track, bridleway, cycleway) and their points
  osm_numbered.json   trail junctions carrying a four-digit Blue Hills intersection number
  osm_parking.json    parking lots, to mark the entry points
  osm_routes.json     hiking routes (many trails are named only on these, not on their paths)
  osm_roads.json      roads you can walk (not highways), for the short road links between trails

  python bluehills_fetch.py           fetch whatever isn't downloaded yet
  python bluehills_fetch.py --fresh   fetch everything again

The query servers are often busy, so each download retries and falls back to a mirror.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"
DATA = os.path.join(PROJ, "bluehills_data")
BBOX = "(42.180,-71.180,42.250,-71.020)"   # south, west, north, east around the reservation
SERVERS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
QUERIES = {
    "osm_trails.json": '[out:json][timeout:180];way%s["highway"~"^(path|footway|track|bridleway|cycleway)$"];(._;>;);out qt;' % BBOX,
    "osm_numbered.json": '[out:json][timeout:90];node%s["junction"]["ref"~"^[0-9]{4}$"];out;' % BBOX,
    "osm_routes.json": '[out:json][timeout:90];relation%s["route"~"^(hiking|foot|walking)$"];out body;' % BBOX,
    "osm_roads.json": '[out:json][timeout:180];way%s["highway"~"^(primary|secondary|tertiary|unclassified|residential|service|living_street|pedestrian|steps)$"];(._;>;);out qt;' % BBOX,
    "osm_parking.json": '[out:json][timeout:90];nwr%s["amenity"="parking"];out center tags;' % BBOX,
}


def fetch(query):
    for attempt in range(8):
        url = SERVERS[attempt % 2]
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": query}).encode(),
                                         headers={"User-Agent": "trail-map/1.0 (tendiamonds@gmail.com)",
                                                  "Accept": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=240).read().decode("utf-8"))["elements"]
        except Exception as e:
            print("  %s: %s; retrying" % (url, e))
            time.sleep(10)
    raise RuntimeError("OpenStreetMap servers didn't answer; try again later")


def main(fresh):
    os.makedirs(DATA, exist_ok=True)
    for name, query in QUERIES.items():
        path = os.path.join(DATA, name)
        if fresh or not os.path.exists(path):
            els = fetch(query)
            json.dump(els, open(path, "w"))
            print("Wrote %s (%d elements)" % (name, len(els)))
        else:
            print("Have %s" % name)


if __name__ == "__main__":
    main("--fresh" in sys.argv)
