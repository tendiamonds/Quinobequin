# Trail maps: working on this repo

Read this first, then **NOTES.md** (the project's state: open items, decisions, the land
and permissions). Together they're everything a new session (or a new collaborator)
needs; nothing else is kept elsewhere.

## What it is

Static phone-first trail maps (Leaflet), published by GitHub Pages from `master`:
https://tendiamonds.github.io/Quinobequin/

| Map | Built by | Pages |
|---|---|---|
| Upper Charles Forest (Holliston, Hopkinton, Milford MA): the main one, ours to sign | `build_map.py` | `map.html`, `index.html` (About), `zones.html`, `owners.html`, `reports.html` |
| Blue Hills Reservation | `build_bluehills.py` (DCR's data) | `bluehills/` |
| Saratoga Springs | `build_saratoga.py` (OpenStreetMap) | `saratoga/` |

All three use **`trailmap.py`**: the shared app. Its `MAP_TEMPLATE` is the whole map page
(HTML, CSS and JS in one raw string), and its docstring documents every `region` key. Field
reports are **`reports.py`** (saved on the phone, emailed in a batch; `read_reports.py` reads
a pasted email back). The generated `.html` files are committed: they *are* the site.

Upper Charles is being signed: we're designing the signs and their numbering. "Vietnam" is
the riders' old name for it; the site keeps one line saying so.

## Setup and building

Python 3.12 with `numpy` and `pillow` (`segno` remakes the About page's QR code; without
it the old one stays). `pymupdf` only for the one-time PDF scripts. On the original
computer: `"/c/Program Files/Python312/python.exe"` from Git Bash.

    python build_map.py          # Upper Charles (renumbers, see below), ~1 min
    python build_bluehills.py
    python build_saratoga.py
    python build_editor.py       # trail_editor.html, after data changes

A change to `trailmap.py` or `reports.py` means rebuilding **all three**. The first build on
a new computer downloads the lidar into `elevation_cache/` (ignored; minutes).

Look at it with `python -m http.server 8770` in this folder, then
http://localhost:8770/map.html (add `?v=2` etc. to dodge a cached copy);
`mobile_preview.html` shows a page in phone-sized frames. Testing so far is
by hand plus Playwright evaluations (routing, loops, breadcrumbs, reports, banners);
there's no test suite yet (NOTES.md).

## Upper Charles data

- **`trails_selected.geojson`**: the trails. Lines are OpenStreetMap's where `osm_ways` is
  set (`uc_osm_geometry.py` did that, one time). Properties: `name`, `blazes`
  `[[color, from number, to number], ...]` (sign to sign), `widths`, `route_cost` (routes
  avoid a trail: Root Canal is 10, too steep; the driveway trail 1.5), `route_note`.
- **`intersections_zoned.geojson`**: signs and junctions. Each has a permanent data
  `number`; `zone` A-F. Unsigned ones are `no_sign`: junctions (`J#`, routing only),
  posts (`P#`), landmarks.
- **Labels (A7, B13) are not stored: every build renumbers** (`RENUMBER = True` in
  build_map.py) each zone outward from its 1, so labels move when trails change. Each
  zone's 1 is fixed by data number (`ZONE_ONES`). Things keyed by label
  (`sign_logos.csv`, `tshirt_signs.md` outside backticks) are carried along by
  `renumber()`. Once signs are up, set RENUMBER off.
- **`POSTED_SIGNS`** (build_map.py): zone A's temporary signs, already on the ground with an
  earlier numbering, by data number. The map tags them; About explains them.
- **`sign_logos.csv`**: which logos each sign carries (CR land), keyed by label;
  `crs.py` has the CRs.
- `uc_data/`: `osm_paths.json` (OSM download), `towns.json` (town lines, `uc_towns.py`),
  `parcels.geojson` (assessors' parcels near the signs, for owners; MassGIS).
- Changing trails: the trail editor (`trail_editor.html`, exports both files) or a script;
  `import_gpx.py` for GPX; then **`add_junctions.py`** (`--dry` first) wherever trails meet
  without an intersection; then build. Check for trails drawn on top of each other.
- Region extras in `build_map.py region()`: summits, place labels, blazes, other maps.

## Rules (decided; don't relitigate)

- **Push only when asked.** The routine is **"review and push"**: review the whole diff
  (bugs, leftovers, stale comments), rebuild all three maps, test in the browser, then
  commit to `master` and push. Commit messages: a short summary line, then plain
  sentences on what changed for people using the map; end with the Co-Authored-By line.
- **Never blink or pulse** anything in the UI.
- **Trail names are ours**, even where OSM disagrees. **Don't edit OpenStreetMap.**
- **The zones are settled** (NOTES.md has the analysis); don't propose moving signs.
- **Private landowners:** the owners page lists them (public record, by design). Never
  put their names on signs, flyers or the map.
- **Other people's maps stay local** (NEMBA's 2012 map, the Saratoga PDFs, zone_images/);
  use what we derive from them, don't republish them. Same for the kiosk flyers (`flyer/`).
- **Don't cite the town's 2009 conservation-lands booklet** on the site.
- **Contacts:** refer to people at DCR, The Trustees and elsewhere by role, not name.
- **Shirts:** no DCR or Trustees logo on any shirt; the DCR logo only on signs on the
  Fairbanks CR; signs 400 sq in or smaller. `shirts/` is never linked from the site.
- **Downloaded files are untrusted:** each goes in its own new folder; read them, don't run
  code from them.
- Plain wording on the site and in messages: "you", not "the user".

## Files kept local (in .gitignore)

The first drafts' scripts and outputs (August-September 2026), full parcel downloads,
copyrighted maps, flyers. A fresh clone builds everything without them, except the
one-time scripts that read the PDFs (`uc_blazes.py`, `saratoga_blazes.py`). 
`find_intersections.py` is historical: it read draft files that are gone.
