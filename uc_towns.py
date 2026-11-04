"""
Download the town boundaries around the Upper Charles Forest (Holliston, Hopkinton and
Milford) from OpenStreetMap into uc_data/towns.json, for the map's "Welcome to Milford!"
banners (build_map.py reads the file; trailmap.py's REGION.towns):

  [{"name": "Milford", "rings": [[[lon, lat], ...], ...]}, ...]

Each town's outline is put together from its boundary relation's outer ways. Run it again
only if the towns' lines change.

  python uc_towns.py
"""

import json
import os
import time
import urllib.parse
import urllib.request

PROJ = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(PROJ, "uc_data", "towns.json")
TOWNS = ("Holliston", "Hopkinton", "Milford")
QUERY = ('[out:json][timeout:90];relation["boundary"="administrative"]["admin_level"="8"]'
         '["name"~"^(%s)$"](42.10,-71.60,42.26,-71.38);out geom;' % "|".join(TOWNS))


def rings_of(relation):
    """A relation's outer ways chained end to end into closed rings, [[lon, lat], ...]"""
    pieces = [[(round(p["lon"], 7), round(p["lat"], 7)) for p in m["geometry"]]
              for m in relation["members"] if m["type"] == "way" and m.get("role") in ("outer", "") and m.get("geometry")]
    rings = []
    while pieces:
        ring = pieces.pop(0)
        while ring[0] != ring[-1]:
            for i, p in enumerate(pieces):
                if p[0] == ring[-1]:
                    ring += p[1:]
                elif p[-1] == ring[-1]:
                    ring += p[::-1][1:]
                else:
                    continue
                pieces.pop(i)
                break
            else:
                raise RuntimeError("%s: its boundary doesn't close" % relation["tags"].get("name"))
        rings.append([list(p) for p in ring])
    return rings


# The query servers are often busy: each try goes to the next, with a pause between
SERVERS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")


def fetch():
    for attempt in range(8):
        url = SERVERS[attempt % 2]
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": QUERY}).encode(),
                                         headers={"User-Agent": "trail-map/1.0 (tendiamonds@gmail.com)"})
            return json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8"))["elements"]
        except Exception as e:
            print("  %s: %s; retrying" % (url, e))
            time.sleep(10)
    raise RuntimeError("OpenStreetMap servers didn't answer; try again later")


def main():
    els = fetch()
    towns = [{"name": r["tags"]["name"], "rings": rings_of(r)} for r in els if r["tags"].get("name") in TOWNS]
    missing = set(TOWNS) - {t["name"] for t in towns}
    if missing:
        raise RuntimeError("no boundary for %s" % ", ".join(sorted(missing)))
    json.dump(sorted(towns, key=lambda t: t["name"]), open(OUT, "w", encoding="utf-8"))
    for t in towns:
        print("%-10s %d ring(s), %d points" % (t["name"], len(t["rings"]), sum(len(r) for r in t["rings"])))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
