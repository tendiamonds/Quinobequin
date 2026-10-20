"""Place the SMBA Daniels Road map (SMBA_DanielsRd_Map.pdf) on the ground: north up at the
scale bar's scale, centered on the state forest, then fitted closely to OSM's trails."""
import json, math
import numpy as np, pymupdf

LAT0, LON0 = 43.115, -73.79
KX = 111320 * math.cos(math.radians(LAT0))
def m(lon, lat): return ((lon - LON0) * KX, (lat - LAT0) * 111000)
def ll(x, y): return (x / KX + LON0, y / 111000 + LAT0)

PDF = "SMBA_DanielsRd_Map.pdf"
FOREST_FILL = (0.71, 0.84, 0.62)
TRAIL_STROKES = [((0.9, 0.0, 0.0), 1.5), ((0.0, 0.36, 0.9), 1.5), ((1.0, 1.0, 0.0), 1.5), ((0.0, 0.0, 0.0), 1.5),
                 ((0.54, 0.35, 0.27), 1.5), ((0.51, 0.51, 0.51), 1.5)]
M_PER_PT = 0.2 * 1609.344 / (109.5 - 44)

def close(c, t, tol=0.03): return c is not None and len(c) == 3 and max(abs(a - b) for a, b in zip(c, t)) < tol

def samples(d, step):
    out = []
    for it in d["items"]:
        if it[0] == "l": a, b = it[1], it[2]
        elif it[0] == "c": a, b = it[1], it[4]
        else: continue
        n = max(1, int(math.hypot(b.x - a.x, b.y - a.y) / step))
        out += [(a.x + (b.x - a.x) * i / n, a.y + (b.y - a.y) * i / n) for i in range(n + 1)]
    return out

def osm_segments():
    d = json.load(open("osm_trails.json"))
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in d["elements"] if e["type"] == "node"}
    segs = []
    for w in d["elements"]:
        if w["type"] == "way" and w.get("tags", {}).get("footway") not in ("sidewalk", "crossing"):
            pts = [m(*nodes[n]) for n in w["nodes"] if n in nodes]
            segs += [(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:])]
    return np.array(segs)

def nearest(S, p):
    ax, ay, bx, by = S.T; vx, vy = bx - ax, by - ay
    t = np.clip(((p[0] - ax) * vx + (p[1] - ay) * vy) / (vx * vx + vy * vy + 1e-9), 0, 1)
    qx, qy = ax + t * vx, ay + t * vy; d = np.hypot(qx - p[0], qy - p[1]); i = int(np.argmin(d))
    return float(d[i]), (float(qx[i]), float(qy[i]))

def named_segments():
    d = json.load(open("osm_trails.json"))
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in d["elements"] if e["type"] == "node"}
    by = {}
    for w in d["elements"]:
        n = w.get("tags", {}).get("name") if w["type"] == "way" else None
        if n:
            pts = [m(*nodes[k]) for k in w["nodes"] if k in nodes]
            by.setdefault(n.lower(), []).extend((a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:]))
    return {k: np.array(v) for k, v in by.items()}

def label_fit(page, T, verbose):
    by = named_segments()
    labels = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = " ".join(s["text"].strip() for s in l["spans"]).strip().lower()
            if t in by:
                x0, y0, x1, y1 = l["bbox"]; labels.append(((x0 + x1) / 2, (y0 + y1) / 2, t))
    # North up at the scale bar's scale; the shift from where the labels are against the
    # middles of their trails (a median, so long trails' middles far from a label don't count much)
    P = np.array([[x, y] for x, y, _ in labels])
    mid = {t: by[t][:, :2].mean(0) for t in by}
    T = np.array([[M_PER_PT, 0], [0, -M_PER_PT], [0, 0]])
    off = np.array([mid[t] - np.array([x, y, 1]) @ T for x, y, t in labels])
    T[2] = np.median(off, 0)
    for it in range(12):
        P = np.array([[x, y] for x, y, _ in labels]); Q = []
        for x, y, t in labels:
            Q.append(nearest(by[t], np.array([x, y, 1]) @ T)[1])
        Q = np.array(Q)
        # similarity: q = s R p + t
        pm, qm = P.mean(0), Q.mean(0); A, B = P - pm, Q - qm
        U, S_, Vt = np.linalg.svd(A.T @ B)
        D = np.diag([1, -np.sign(np.linalg.det(U @ Vt))])   # page y runs down: the fit flips
        R = U @ D @ Vt; scale = S_.sum() / (A ** 2).sum() if False else np.trace(np.diag(S_) @ D) / (A ** 2).sum()
        M = scale * R; t = qm - pm @ M
        if it < 6:   # translation only at first, till the labels find their own trails
            t = (Q - P @ T[:2]).mean(0); M = T[:2]
        T = np.vstack([M, t])
        res = np.hypot(*(P @ M + t - Q).T)
        if verbose and it in (0, 5, 11): print("labels: %d, median %.0f m off their trails" % (len(labels), np.median(res)))
    return T

def fit(verbose=True):
    page = pymupdf.open(PDF)[0]
    S = osm_segments()
    forest = [d["rect"] for d in page.get_drawings() if close(d.get("fill"), FOREST_FILL)]
    fr = forest[0]
    for r in forest[1:]: fr |= r
    areas = json.load(open("osm_paths.json"))["elements"]
    dr = [a for a in areas if a.get("tags", {}).get("name") == "Daniels Road State Forest"][0]
    g = [m(p["lon"], p["lat"]) for p in dr["geometry"]]
    gx = [p[0] for p in g]; gy = [p[1] for p in g]
    # Start: north up, the scale bar's scale, the forest's middle on the forest's middle
    cx, cy = (fr.x0 + fr.x1) / 2, (fr.y0 + fr.y1) / 2
    ox, oy = (min(gx) + max(gx)) / 2, (min(gy) + max(gy)) / 2
    T = np.array([[M_PER_PT, 0], [0, -M_PER_PT], [ox - M_PER_PT * cx, oy + M_PER_PT * cy]])
    # Then the trail name labels: each beside the OSM trail of that name (a fit of place,
    # scale and turn only, since labels sit off to one side of their lines)
    T = label_fit(page, T, verbose)
    lines = []
    for d in page.get_drawings():
        for c, w in TRAIL_STROKES:
            if close(d.get("color"), c) and abs((d.get("width") or 0) - w) < 0.05:
                lines += samples(d, 3)
    for tol in (120, 80, 50, 35, 25, 20, 15, 15):
        P, Q = [], []
        for x, y in lines:
            dd, q = nearest(S, np.array([x, y, 1]) @ T)
            if dd < tol: P.append([x, y, 1]); Q.append(q)
        T, *_ = np.linalg.lstsq(np.array(P), np.array(Q), rcond=None)
        if verbose:
            off = sorted(nearest(S, np.array([x, y, 1]) @ T)[0] for x, y in lines[::5])
            print("tol %3d: %d pairs, median %.1f m, 80%% within %.1f m" % (tol, len(P), off[len(off) // 2], off[int(.8 * len(off))]))
    return T

if __name__ == "__main__":
    T = fit()
    sx = math.hypot(*T[0]); sy = math.hypot(*T[1]); rot = math.degrees(math.atan2(T[0][1], T[0][0]))
    print("scale %.2f / %.2f m per pt (bar says %.2f), rotation %.1f deg" % (sx, sy, M_PER_PT, rot))
    np.save("sara_T.npy", T)
