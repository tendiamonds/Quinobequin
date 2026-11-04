# Project notes

The state of the trail-map project: what's open, what's been decided and why, and what we
know about the land. How to build and the working rules are in **CLAUDE.md**. Kept up to
date as things change; dates are when something was learned or decided.

## Open items

1. **Due 2026-11-16: delete the service-worker cleanup** in `trailmap.py` (the
   `getRegistrations()...unregister()` block marked "delete this after 2026-11-16"). It
   removes the `sw.js` that a lock-screen next-turn notification left on phones (tried
   2026-10-30, taken out 2026-11-02: it didn't work in the field). Two weeks is plenty.
2. **Town seals** on the "Welcome to Milford!" banner (2026-11-04): white seals in `seals/`,
   from the shirt art. We're asking the towns for permission before the site is made more
   public; don't publicize it further until they've said yes. Color seals would just
   replace the three files (only Milford's color one is on hand, inside its website logo).
3. **Around D2** the map has a bigger problem than the bypass that was reported. GPX
   recordings covering everything around D2 are coming: bring them in with `import_gpx.py`,
   compare against OSM, then redraw.
4. **A bypass around Challenger** exists; we asked the trail stewards whether to add it.
   If it's added, rerun `add_junctions.py`.
5. **Trailforks data:** the Trailforks region admin (a NEMBA contact we want on board with
   the signs) offered better trail data as GPX. Zone E (NEMBA land) has changed most. When
   it comes: `import_gpx.py`, check the intersections in E, rebuild (the numbering follows).
6. **Owner labels overstate the Adams CR.** About 156 acres are labeled "Adams Town Forest
   (Trustees CR)", but the CR covers only the 85.6-acre additions (see below); the rest is
   likely the original Town Forest. Fix by matching our parcels to the CR's sketch map
   (page 18 of the recorded CR), labeling owners "Town of Holliston" with the CR as a
   separate attribute.
7. **Tests.** Checks so far are hand-run Playwright evaluations; automated regression tests
   (routing, loops, breadcrumbs, reports) would help.
8. **Ideas for another day:** "Save track" as GPX (phones stop GPS with the screen off, so
   tracks have gaps; the map fills them along trails, but it can't replace Strava);
   a direction-up map (Leaflet can't rotate: a plugin like leaflet-rotate, or rotating
   the container, which turns labels sideways).
9. Expect the conservation commission to ask to rename **Giggity**.

## How the field work goes

We walk the trails with the map and file reports from it (blazes by color, notes), then
send them in a batch by email. `read_reports.py` lists a pasted email's reports against
what the map has; we apply them to the data (blazes run sign to sign), rebuild, and push
the day's changes together.

## Decisions worth knowing

- **OSM first for lines (2026-10-23):** OpenStreetMap's lines sit on the map tiles and
  are mostly traced from imagery; ours were GPS tracks. 146 of the trails use OSM's
  geometry (`uc_osm_geometry.py`, a one-time conversion). Still ours: Dirty Little
  Secret, The Maine Line, the quarry access road, Armageddon, 495 Run B.
- **Names are ours.** OSM has Gintro, Giggity and The Gigg wrong. Ours: Gintro runs into
  D9; "The Gigg" (`tf_56`); "Giggity" (`tf_125`).
- **Signs snap to trails within 10 m** (`trailmap.SIGN_SNAP_M`).
- **The zones** were drawn by feel by the trail regulars, and a connectivity analysis
  (2026-10-13) backed them: 66-86% of each zone's sign-to-sign links stay inside it, and
  zones and the best clustering agree on 86% of sign pairs. The fuzzy edges (B toward C
  and A, E32-E34 toward D, D8/D13/F16/F17 toward E) were checked on the ground and kept.
- **Blue Hills** is built from DCR's own trail data (2026-10-30), replacing a version
  traced from the park's PDF map. `bluehills_osm_fixes.md` lists where OSM is wrong there.
- **Root Canal** is too steep: routes avoid it unless you add it yourself (`route_cost`).

## The land and its conservation restrictions

A CR doesn't change who owns the land; its holders enforce it. Signs on CR land carry the
holders' logos (`sign_logos.csv`, `crs.py`). The sign lists below are labels from
2026-10-13; labels move with each build, and `sign_logos.csv` always has today's.

- **Adams Street Town Forest Additions, Holliston CR #28.** Recorded 2013-09-25, Middlesex
  South Bk 62685 Pg 340. Owned by the Town of Holliston; The Trustees are the sole holder.
  11 parcels, 85.6 acres, west of Adams St (Map 4 Block 2 Lots 44, 47, 49, 64-69, 74, 75),
  bought from NSTAR in 2007-2013. It covers only the additions, not the original Town
  Forest. Trail building and marking, and trail-access signs, need no permission; new wood
  roads, kiosks, benches and interpretive signs need The Trustees' written permission
  (60 days' notice by certified mail; silence is approval). Stone walls and granite posts
  are protected. Signs on it: A1 A2 A3 A5 A15 A16 B19 C25 (labels as of 2026-10-13).
- **David Reed Fairbanks conservation area,** about 210 acres south of the Town Forest,
  bought by the town in 2002. Its CR (Bk 40805 Pg 64, state ID 136_CR_20) is held jointly
  by The Trustees and DCR and covers the whole parcel (Map 1-2-35). Signs: D1-D4 and
  F1-F19 for certain; A23 A24 E11 D5 D6 D8 depend on which boundary is right (the state's
  open-space polygon and the assessors' parcel disagree; the CR's recorded plan decides).
- **NEMBA's land ("Vietnam"),** 47 acres next to Fairbanks, owned outright by NEMBA.
- **Wenakeening Woods,** 100+ acres, owned by the Upper Charles Conservation Land Trust
  with a Trustees CR. **Waldenwoods** (Milford, private, Trustees CR): none of our signs.
- Sources: MassGIS open space (CR holders in `OLI_n_ORG`) and tax parcels (`MAP_PAR_ID`).

## Signs and permissions

- **DCR** (its CR contact, 2026-10-23): recreational signs on the CR need no review at
  400 sq in or smaller. The DCR logo goes only on signs on the Fairbanks CR, and then DCR
  approves the final design. DCR's sign shop doesn't make CR signs; the sign maker DCR
  uses is Voss Signs. DCR's Medfield signs are fine as a model. No DCR logo on shirts.
- **The Trustees** like the shirt idea but asked for their logo off the shirts.
- **NEMBA:** check before using its sign and logo on the E shirt.
- **The towns:** check before using their seals on shirts, and on the map (item 2).

## T-shirts

One shirt per zone in its color, each with one full-size sign, to raise money for the
signs: **A7 B3 C2 D5 E1 F4**. The reasoning, the rules and what's left before printing are
in `tshirt_signs.md`; the art is `tshirt_art.py`, previewed at `shirts/` (never linked).
