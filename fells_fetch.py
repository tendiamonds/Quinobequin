"""
Download what the Middlesex Fells map is built from into fells_data/. From OpenStreetMap:
  osm_boundary.json  the reservation's boundary (the trails kept are the ones inside it)
  osm_trails.json    paths, tracks and footways, with their points
  osm_routes.json    the marked trails (route relations: Skyline, Reservoir, Cross Fells...),
                     with their colors and member ways: the map's blazes
  osm_roads.json     roads you can walk, for the short road links between trails
  osm_divide.json    I-93, which splits the reservation into the West and East Fells
  osm_parking.json   parking lots, to mark the entry points
From the Massachusetts Department of Conservation and Recreation (DCR), its statewide
inventories (GPS, 2005-2014):
  dcr_trails.geojson  its trails and roads: the official ones (what its trail map shows;
                      the map leaves out the user-created paths OpenStreetMap has too)
  dcr_points.geojson  parking areas, trailheads, bridges, boardwalks, vistas
From MassGIS's protected open space:
  water_supply.geojson  water-supply land with no public access (Winchester's around its
                        reservoirs, "Restricted; No Public Access; Fines Apply" on DCR's
                        map, and MWRA's): no trails are kept in it

  python fells_fetch.py           fetch whatever isn't downloaded yet
  python fells_fetch.py --fresh   fetch everything again
"""

import json
import os
import sys

from bluehills_fetch import fetch, fetch_dcr

PROJ = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(PROJ, "fells_data")
BBOX = "(42.418,-71.135,42.475,-71.055)"   # south, west, north, east around the reservation
DCR_LAYERS = {
    "dcr_trails.geojson": ("https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/"
                           "DCR_Roads_and_Trails/FeatureServer/0", BBOX),
    "dcr_points.geojson": ("https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/"
                           "DCR_Roads_and_Trail_Point_Features/FeatureServer/0", BBOX),
    "water_supply.geojson": ("https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/openspace/FeatureServer/0",
                             BBOX, "PRIM_PURP = 'W' AND PUB_ACCESS = 'N'"),
}
QUERIES = {
    "osm_boundary.json": '[out:json][timeout:90];relation["name"="Middlesex Fells Reservation"];out geom;',
    "osm_trails.json": '[out:json][timeout:180];way%s["highway"~"^(path|footway|track|bridleway|cycleway|steps)$"];(._;>;);out qt;' % BBOX,
    "osm_routes.json": '[out:json][timeout:90];relation%s["route"~"^(hiking|foot|walking|mtb)$"];out body;' % BBOX,
    "osm_roads.json": '[out:json][timeout:180];way%s["highway"~"^(primary|secondary|tertiary|unclassified|residential|service|living_street|pedestrian)$"];(._;>;);out qt;' % BBOX,
    "osm_divide.json": '[out:json][timeout:90];way%s["highway"="motorway"]["ref"~"I 93"];out geom;' % BBOX,
    "osm_parking.json": '[out:json][timeout:90];nwr%s["amenity"="parking"];out center tags;' % BBOX,
}


def main(fresh):
    os.makedirs(DATA, exist_ok=True)
    for name, (layer, bbox, *where) in DCR_LAYERS.items():
        path = os.path.join(DATA, name)
        if fresh or not os.path.exists(path):
            s, w, n, e = bbox.strip("()").split(",")
            data = fetch_dcr(layer, envelope=(w, s, e, n), where=where[0] if where else "1=1")
            json.dump(data, open(path, "w"))
            print("Wrote %s (%d features)" % (name, len(data["features"])))
        else:
            print("Have %s" % name)
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
