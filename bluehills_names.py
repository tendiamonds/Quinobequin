"""
Name the Blue Hills trails OpenStreetMap leaves unnamed, from the labels on the park's own
trail map (bluehills_data/blue-hills-trail-map-2020.pdf).

The PDF's trail names are real text, set along the trails, so each letter has a place on
the page. Straight labels come out whole; labels set along a curve come out letter by
letter, so letters are chained back into words by how close they are. Long names are often
set on two lines ("Tucker" over "Hill Path"); a capitalized word just before a label is
its first line. Labels that are road names are left out (OSM names roads itself), and so
are ones that are only the end of a longer name ("Hill Path" beside "Tucker Hill Path"),
since which name they belong to isn't clear.

Each letter's place converts to the ground (as in bluehills_pdf.py), and the label names
the OSM paths most of its letters fall on: within LABEL_TO_TRAIL_M, and running the same
way as the label, so a label beside two trails picks the one it follows.

Writes bluehills_data/pdf_names.json: {OSM way: name}, for every path a label falls on
(named in OSM or not; build_bluehills.py uses it only for those that aren't).
"""

import collections
import json
import math
import os
import re

import pymupdf

import bluehills_pdf as P
from build_bluehills import load, load_numbered

LABEL_SIZE, LABEL_COLOR = 7.5, 0x231f20   # how the map sets trail names
LETTER_GAP_PT = 6       # letters of a word are this close on the page
FIRST_LINE_PT = 12      # the first line of a two-line name is this close to the second
LABEL_TO_TRAIL_M = 50   # a letter this close to a path can be naming it
SAME_WAY_DEG = 35       # a path within this angle of the label runs the same way
KIND = r"(Path|Trail|Road|Line|Run|Way|Loop|Boardwalk|Greenway)"
LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "’": "'"}


def page_letters():
    """[(letter, x, y, reading direction)] of the trail-name text"""
    out = []
    for b in pymupdf.open(P.PDF)[0].get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if abs(s["size"] - LABEL_SIZE) < 0.3 and s["color"] == LABEL_COLOR:
                    for ch in s["chars"]:
                        if ch["c"].strip():
                            x0, y0, x1, y1 = ch["bbox"]
                            out.append((LIGATURES.get(ch["c"], ch["c"]), (x0 + x1) / 2, (y0 + y1) / 2, l["dir"]))
    return out


def gap(a, b):
    """Closest distance on the page between two words' letters"""
    return min(math.hypot(p[0] - q[0], p[1] - q[1]) for p in a["pts"] for q in b["pts"])


def join(a, b):
    a["text"] += ("" if b["text"][0].islower() else " ") + b["text"]
    a["pts"] += b["pts"]
    a["dir"] = (a["dir"][0] + b["dir"][0], a["dir"][1] + b["dir"][1])
    b["text"] = ""


def page_words(letters):
    """Letters chained into words: [{text, pts, dir}], each in reading order"""
    parent = list(range(len(letters)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, a in enumerate(letters):
        for j in range(i + 1, len(letters)):
            b = letters[j]
            if abs(a[1] - b[1]) <= LETTER_GAP_PT and math.hypot(a[1] - b[1], a[2] - b[2]) <= LETTER_GAP_PT:
                parent[root(i)] = root(j)
    groups = collections.defaultdict(list)
    for i in range(len(letters)):
        groups[root(i)].append(i)
    words = []
    for g in groups.values():
        dx, dy = sum(letters[i][3][0] for i in g), sum(letters[i][3][1] for i in g)
        g.sort(key=lambda i: letters[i][1] * dx + letters[i][2] * dy)
        text = "".join(letters[i][0] for i in g)
        # The words of a straight label run together; split them at capitals
        text = re.sub(r"(?<=[a-z.'])(?=[A-Z])", " ", text)
        words.append({"text": text, "pts": [letters[i][1:3] for i in g], "dir": (dx, dy)})
    return words


def pair_up(firsts, seconds, limit, ok):
    """Join each first to a second, closest pairs first, each used once"""
    pairs = sorted((gap(a, b), i, j) for i, a in enumerate(firsts) for j, b in enumerate(seconds)
                   if a is not b and ok(a, b) and gap(a, b) <= limit)
    used_a, used_b = set(), set()
    for _, i, j in pairs:
        if i not in used_a and j not in used_b and firsts[i]["text"] and seconds[j]["text"]:
            used_a.add(i)
            used_b.add(j)
            join(firsts[i], seconds[j])


def before(a, b):
    """Whether word a starts before word b, along b's reading direction"""
    d = b["dir"]
    return a["pts"][0][0] * d[0] + a["pts"][0][1] * d[1] <= b["pts"][0][0] * d[0] + b["pts"][0][1] * d[1] + 3


def first_line_of(f, n):
    """Whether word f is the first line of the name n: on the line just above (or below)
    over n's span, or on the same line just before it, and running the same way"""
    d = n["dir"]
    k = math.hypot(*d) or 1
    ux, uy = d[0] / k, d[1] / k
    e = f["dir"]
    if (e[0] * ux + e[1] * uy) / (math.hypot(*e) or 1) < math.cos(math.radians(45)):   # labels on a curve turn
        return False
    o = n["pts"][0]
    along = lambda p: (p[0] - o[0]) * ux + (p[1] - o[1]) * uy
    across = lambda p: (p[1] - o[1]) * ux - (p[0] - o[0]) * uy
    span = max(along(p) for p in n["pts"])
    c = (sum(p[0] for p in f["pts"]) / len(f["pts"]), sum(p[1] for p in f["pts"]) / len(f["pts"]))
    line_above = 5 <= abs(across(c)) <= FIRST_LINE_PT and -2 <= along(c) <= span + 2
    same_line = abs(across(c)) <= 6 and along(f["pts"][-1]) <= 2
    return line_above or same_line


def trail_labels():
    words = page_words(page_letters())
    # A piece of a word split on a curve ("Sum" "mit") rejoins the piece before it
    pair_up(words, [w for w in words if re.fullmatch(r"[a-z]+( [A-Z].*)?", w["text"])], 10, lambda a, b: before(a, b))
    # A lone "Path", "Road"... finishes the name before it
    pair_up([w for w in words if re.fullmatch(r"[A-Z][A-Za-z' ]*", w["text"]) and not re.search(KIND + "$", w["text"])],
            [w for w in words if re.fullmatch(KIND, w["text"])], 14, lambda a, b: True)
    # The first line of a two-line name
    names = [w for w in words if re.search(" " + KIND + "$", w["text"]) or w["text"] == "Pipe Line"]
    firsts = [w for w in words if re.fullmatch(r"[A-Z][a-z']+", w["text"])]
    pairs = sorted((gap(f, n), i, j) for i, f in enumerate(firsts) for j, n in enumerate(names)
                   if gap(f, n) <= FIRST_LINE_PT and first_line_of(f, n))
    used_f, used_n = set(), set()
    for _, i, j in pairs:
        if i not in used_f and j not in used_n:
            used_f.add(i)
            used_n.add(j)
            f, n = firsts[i], names[j]
            n["text"] = f["text"] + " " + n["text"]
            n["pts"] = f["pts"] + n["pts"]
    roads = {r["tags"]["name"] for r in load("osm_roads.json") if r["type"] == "way" and r.get("tags", {}).get("name")}
    full = {n["text"] for n in names} | roads
    return [n for n in names if n["text"] not in roads and not any(f.endswith(" " + n["text"]) for f in full)]


def main():
    labels = trail_labels()
    osm = {num: ll for num, node, ll in load_numbered()}
    at, _ = P.page_dots()
    to_ground = P.make_predictor(at, osm, [n for n in at if n in osm])

    els = load("osm_trails.json")
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in els if e["type"] == "node"}
    ways = [w for w in els if w["type"] == "way" and w.get("tags", {}).get("footway") not in ("sidewalk", "crossing")]
    cell = 0.002
    grid = collections.defaultdict(list)    # map cell -> (way, a, b) for each piece of path near it
    for w in ways:
        pts = [nodes[n] for n in w["nodes"] if n in nodes]
        for a, b in zip(pts, pts[1:]):
            for gx in range(int(min(a[0], b[0]) / cell) - 1, int(max(a[0], b[0]) / cell) + 2):
                for gy in range(int(min(a[1], b[1]) / cell) - 1, int(max(a[1], b[1]) / cell) + 2):
                    grid[(gx, gy)].append((w["id"], a, b))

    def meters(a, b):
        return ((b[0] - a[0]) * P.M_LON, (b[1] - a[1]) * P.M_LAT)

    def off(p, a, b):
        (ax, ay), (vx, vy) = meters(p, a), meters(a, b)
        t = max(0, min(1, -(ax * vx + ay * vy) / (vx * vx + vy * vy or 1)))
        return math.hypot(ax + t * vx, ay + t * vy)

    votes = collections.defaultdict(collections.Counter)    # way -> name -> letters
    for lab in labels:
        # Which way the label runs on the ground, from its middle
        d = lab["dir"]
        n = math.hypot(*d) or 1
        p = lab["pts"][len(lab["pts"]) // 2]
        run = meters(to_ground(p), to_ground((p[0] + 20 * d[0] / n, p[1] + 20 * d[1] / n)))
        cos_ok = math.cos(math.radians(SAME_WAY_DEG))

        def same_way(a, b):
            v = meters(a, b)
            return abs(v[0] * run[0] + v[1] * run[1]) >= cos_ok * math.hypot(*v) * math.hypot(*run)
        hits = collections.Counter()
        for p in lab["pts"]:
            g = to_ground(p)
            near = [(off(g, a, b), wid) for wid, a, b in grid[(int(g[0] / cell), int(g[1] / cell))] if same_way(a, b)]
            if near and min(near)[0] <= LABEL_TO_TRAIL_M:
                hits[min(near)[1]] += 1
        for wid, k in hits.items():
            if k >= max(3, 0.3 * len(lab["pts"])):
                votes[wid][lab["text"]] += k
    names = {wid: v.most_common(1)[0][0] for wid, v in votes.items()}
    json.dump(names, open(os.path.join(P.DATA, "pdf_names.json"), "w"), indent=1, sort_keys=True)
    print("%d trail labels; named %d paths: wrote pdf_names.json" % (len(labels), len(names)))
    return labels, names, ways


if __name__ == "__main__":
    main()
