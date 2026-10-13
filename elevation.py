"""
Trail elevations, from the USGS 3D Elevation Program (3DEP): bare-earth lidar, about 1 m
resolution across Massachusetts, served as an image of elevations for any box.

  add_elevations(ints, trails, bounds, cache)

gives each trail an elevation profile (properties "ele": meters, every STEP_M along it,
from its start) and each intersection its elevation ("ele"). The region's elevation grid
is downloaded once into cache (a GeoTIFF; delete it to fetch again).
"""

import math
import os
import time
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image

SERVICE = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
RES_M = 3        # grid spacing to fetch (meters)
MAX_PIXELS = 7e6 # the most the service will send in one image (it refuses about 13 million)
STEP_M = 10      # profiles have an elevation this often along each trail
SMOOTH = 3       # profile points averaged, to steady lidar noise (an odd count)
PAD_DEG = 0.003  # fetch a little past the region's bounds
M_LON, M_LAT = 82000, 111000   # meters per degree near 42 N (as in trailmap.dist_m)


def georeference(path):
    """A cached grid's (elevations, west, south, east, north), from the GeoTIFF's own tags
    (ModelTiepoint and ModelPixelScale): the service may cover a different box than asked"""
    im = Image.open(path)
    sx, sy = im.tag_v2[33550][:2]
    west, north = im.tag_v2[33922][3:5]
    cols, rows = im.size
    return np.array(im, dtype=np.float64), west, north - rows * sy, west + cols * sx, north


def fetch_grid(bounds, cache):
    """bounds [[south, west], [north, east]] -> (elevations, west, south, east, north),
    fetching the grid if there's none cached or it doesn't cover the bounds"""
    (s, w), (n, e) = bounds
    s, w, n, e = s - PAD_DEG, w - PAD_DEG, n + PAD_DEG, e + PAD_DEG
    if os.path.exists(cache):
        grid = georeference(cache)
        if grid[1] <= w and grid[2] <= s and grid[3] >= e and grid[4] >= n:
            return grid
    # Square pixels in degrees (RES_M north-south, or coarser for a big region, which the
    # service would refuse), so the service has nothing to stretch
    deg = max(RES_M / M_LAT, math.sqrt((e - w) * (n - s) / MAX_PIXELS))
    size = (round((e - w) / deg), round((n - s) / deg))
    query = urllib.parse.urlencode({
        "bbox": "%f,%f,%f,%f" % (w, s, e, n), "bboxSR": 4326, "imageSR": 4326, "size": "%d,%d" % size,
        "format": "tiff", "pixelType": "F32", "interpolation": "RSP_BilinearInterpolation", "f": "image"})
    for attempt in range(5):
        try:
            req = urllib.request.Request(SERVICE + "?" + query, headers={"User-Agent": "trail-map/1.0 (tendiamonds@gmail.com)"})
            data = urllib.request.urlopen(req, timeout=300).read()
            # The service reports some errors as a page, not an HTTP error
            if data[:4] in (b"II*\0", b"MM\0*"):
                break
            print("  elevation service sent no image: %s; retrying" % data[:200])
        except Exception as ex:
            print("  elevation service: %s; retrying" % ex)
        time.sleep(10)
    else:
        raise RuntimeError("The USGS elevation service didn't answer; try again later")
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache + ".tmp", "wb") as f:
        f.write(data)
    os.replace(cache + ".tmp", cache)
    print("Wrote %s (%d x %d)" % (cache, *size))
    return georeference(cache)


def sampler(grid):
    """(lon, lat) -> elevation in meters, interpolated between grid points"""
    z, w, s, e, n = grid
    rows, cols = z.shape

    def at(lon, lat):
        x = (lon - w) / (e - w) * cols - 0.5
        y = (n - lat) / (n - s) * rows - 0.5
        x0, y0 = min(max(int(math.floor(x)), 0), cols - 2), min(max(int(math.floor(y)), 0), rows - 2)
        fx, fy = min(max(x - x0, 0), 1), min(max(y - y0, 0), 1)
        return ((z[y0, x0] * (1 - fx) + z[y0, x0 + 1] * fx) * (1 - fy) +
                (z[y0 + 1, x0] * (1 - fx) + z[y0 + 1, x0 + 1] * fx) * fy)
    return at


def profile(coords, at):
    """Elevations every STEP_M along a line (and at its end), lightly smoothed"""
    pts, cum = [], [0.0]
    for a, b in zip(coords, coords[1:]):
        cum.append(cum[-1] + math.hypot((b[0] - a[0]) * M_LON, (b[1] - a[1]) * M_LAT))
    total, j = cum[-1], 0
    stops = [k * STEP_M for k in range(int(total // STEP_M) + 1)] + ([total] if total % STEP_M else [])
    for d in stops:
        while j < len(coords) - 2 and cum[j + 1] < d:
            j += 1
        span = cum[j + 1] - cum[j] if len(coords) > 1 else 0
        t = (d - cum[j]) / span if span else 0
        a, b = coords[j], coords[min(j + 1, len(coords) - 1)]
        pts.append(at(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    known = [v for v in pts if not math.isnan(v)]
    if not known:
        return []
    last = known[0]
    for i, v in enumerate(pts):
        if math.isnan(v):
            pts[i] = last
        else:
            last = v
    half = SMOOTH // 2
    return [round(sum(pts[max(0, i - half):i + half + 1]) / len(pts[max(0, i - half):i + half + 1]), 1) for i in range(len(pts))]


def add_elevations(ints, trails, bounds, cache):
    at = sampler(fetch_grid(bounds, cache))
    for f in trails["features"]:
        g = f["geometry"]
        coords = g["coordinates"] if g["type"] == "LineString" else [c for part in g["coordinates"] for c in part]
        prof = profile(coords, at) if len(coords) >= 2 else []
        if prof:
            f["properties"]["ele"] = prof
    for f in ints["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        e = at(lon, lat)
        if not math.isnan(e):
            f["properties"]["ele"] = round(e, 1)
    return STEP_M
