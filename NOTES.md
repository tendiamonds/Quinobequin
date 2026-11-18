# Project notes

The state of the trail-map project: what's open, what's been decided and why, and what we
know about the land. How to build and the working rules are in **CLAUDE.md**. Kept up to
date as things change; dates are when something was learned or decided.

## Open items

1. **Town seals** on the "Welcome to Milford!" banner (2026-11-04): white seals in `seals/`,
   from the shirt art. We're asking the towns for permission before the site is made more
   public; don't publicize it further until they've said yes. Color seals would just
   replace the three files (only Milford's color one is on hand, inside its website logo).
2. **Around D2** the map has a bigger problem than the bypass that was reported. GPX
   recordings covering everything around D2 are coming: bring them in with `import_gpx.py`,
   compare against OSM, then redraw.
3. **A bypass around Challenger** exists; we asked the trail stewards whether to add it.
   If it's added, rerun `add_junctions.py`.
4. **Owner labels overstate the Adams CR.** About 156 acres are labeled "Adams Town Forest
   (Trustees CR)", but the CR covers only the 85.6-acre additions (see below); the rest is
   likely the original Town Forest. Fix by matching our parcels to the CR's sketch map
   (page 18 of the recorded CR), labeling owners "Town of Holliston" with the CR as a
   separate attribute.
5. **Tests.** Checks so far are hand-run Playwright evaluations; automated regression tests
   (routing, loops, breadcrumbs, reports) would help.
6. **Ideas for another day:** "Save track" as GPX (phones stop GPS with the screen off, so
   tracks have gaps; the map fills them along trails, but it can't replace Strava);
   a direction-up map (Leaflet can't rotate: a plugin like leaflet-rotate, or rotating
   the container, which turns labels sideways).
7. Expect the conservation commission to ask to rename **Giggity**.
8. **Bridges on the map** (the point of the bridge reports). Each bridge report has both
   ends; snapped to its trail, that's a stretch of it, which can be stored on the trail
   the way blazes are and drawn with a bridge symbol (a short pair of lines with flared
   ends). `read_reports.py` could print them ready to add. Blue Hills and the Fells may
   have them already: DCR's points layer has bridges and boardwalks, and OSM marks
   bridge ways. Every bridge gets reported again on every walk (2026-11-17), so the reports
   pile up on purpose: when this is built, keep them all raw (a file, with dates), group
   them by trail and overlapping stretch, average the ends along the trail, drop outliers,
   and let newer ones show a bridge that changed. Reported so far (2026-11-15): at C26, 33 ft, 42.186392,-71.495415 to
   42.186412,-71.495300; College Rock Run C4–C7, 43 ft, 42.189325,-71.496319 to
   42.189417,-71.496424. 2026-11-17 (zone F): The Main Trail F2–F1, the long boardwalk,
   walked both ways (42.171014,-71.488060 to 42.171077,-71.489099, and
   42.171063,-71.489142 to 42.171025,-71.488077): the ends agree within 4 m and 2 m,
   the lengths within 2 m; averaged, 42.171070,-71.489120 to 42.171019,-71.488068, 285 ft
   (one walk is good to about 4 m an end; worth walking long ones twice); Swampside F12–F2, three: 26 ft
   (42.168486,-71.490564 to 42.168411,-71.490569), 10 ft (42.168103,-71.490512 to
   42.168079,-71.490516) and 39 ft (42.168049,-71.490524 to 42.167946,-71.490565), the
   last two nearly end to end; Fairbanks Trail F7–F11, 108 ft (42.168310,-71.491705 to
   42.168602,-71.491784); Fairbanks Trail F10–F5, 30 ft (42.169555,-71.492966 to
   42.169638,-71.492961).
9. **Blue in zone F is a puzzle** (2026-11-17). Marked so far: Tonto F3–A18 and The Main
   Trail F3–F2 (with the red). Also seen, not marked: one blue blaze just past F7 heading
   to F9 (Fairbanks Trail), then nothing until F10, where a "blue turns left" blaze.
   Look for more blue around F7–F10 before marking any of it.
10. **Later: Trailforks reports** (parked 2026-11-16; the trail-cleanup lead, a BVNEMBA admin, asked):
    sync our obstruction reports with Trailforks'. Theirs are public (trail, status,
    description, coordinates; the region's list is
    `trailforks.com/region/vietnam-trail-network/reports/`), but the API needs an app id
    and secret, given "mostly to non-profit trail associations" (apply at
    `trailforks.com/about/api/`; they want the benefit to Trailforks and its community
    explained). We may apply ourselves, as the Town Forest Committee and its partners, or
    with BVNEMBA. Reading their open issues onto the map would be a build step (the secret
    can't be in the page); posting ours to Trailforks needs each person's Trailforks login
    (OAuth) and their POST methods are "under development". Their API page mentions RSS.
    **2026-11-16:** a NEMBA chapter contact has a Trailforks API key and a trail work app
    (`vietnamtrailwork.eaglesnest.app`): trails colored by their Trailforks status,
    Trailforks' reports as pins and planned projects, crew projects, volunteer sign-ups. It
    reads from Trailforks but can't write (can't mark an issue cleared). He suggested
    combining resources. Ways to: his app publishing the open issues as a public file our
    map reads (no key in our page); our obstruction reports going into his "suggest trail
    work" (his Trailforks trail data matches ours: see below). NEMBA wants people reporting
    on Trailforks, one app everywhere. Ours isn't for trail work, and isn't riders against
    walkers: it's the local map for people who don't use Trailforks or AllTrails (new to the
    woods, from town, or who'd rather have a map of this forest); anyone happy with those
    should keep using them.
    **Replied 2026-11-16** (waiting on him): asked whether our reports could go into his
    "suggest trail work" and whether his app could publish its open Trailforks reports as a
    small public file for our map; suggested unifying the shared trail data later. Told him
    the map began as a way to work out which property and town each sign is on (to make
    them right and get permissions), and that our reports are mainly the blaze and
    map-mismatch survey, obstacles a bonus.
    **His proposal (2026-11-16, a PDF spec; not in the repo):** his server takes our reports
    (`POST https://vietnamtrailwork.eaglesnest.app/api/public/reports`, body `{v: 1, source:
    "quinobequin", reports: [...]}`, up to 25 per post; replies `{accepted: [ids], skipped:
    [{id, why}]}`; repeats by id ignored; only from `tendiamonds.github.io`) and publishes
    open issues (`GET .../api/public/issues`: Trailforks reports and his crew's projects, plus
    `yours`: each report we sent, by id, with its status: received, planned, in progress,
    fixed, not taken up). He builds both endpoints first. Decided so far:
    - Only obstruction reports (tree, washout, flooded, other), only from the Upper Charles
      map. Not bridges: ours record bridges that exist, not where one should go (he reads
      them as suggestions). Not notes, blazes, checks.
    - Those obstruction reports go to him **instead of** the email (the crew handles them).
    - Retries: a report is posted once his server answers for it; until then it's tried
      again each time the Reports page opens.
    - One he skips (outside his area) goes in the email, as now, so none are lost.
    - The Reports page says in a line where obstruction reports go. Issues from his feed
      show on the Upper Charles map only, in our own style (borrowing from his icons where
      we have none); if his server is down, nothing extra shows.
    - Testing from localhost would be awkward to set up with him; not needed (test from the
      published site). The Town's site, when the map moves, has to be allowed to post.
    - We're the keeper of the numbering and the names: `upper_charles.json` (build_map.py
      `write_shared`): signs (permanent id, label, zone, location, entrance) and trails
      (permanent id, our name, signs in order, blazes sign to sign, line). His app reads it
      instead of copying map.html. Reports carry `ctx.trailId`; he keeps the match from our
      trail ids to his Trailforks trails.
    - His questions: the formats work. Sign reports stay ours until the signs are up (a
      design question), then go to him (maintenance). Fixed issues show for about two
      weeks.
    Nothing to build on our side until his two endpoints are live.

## How the field work goes

We walk the trails with the map and file reports from it (a blaze, by color; something in
the way; a bridge, marked at each end; or a note), then send them in a batch by email,
to Jason Breslau by name. Back where you started, the map offers to send them, then shows
a walk summary picture to save or share. `read_reports.py` lists a pasted email's
reports against what the map has; we apply them to the data (blazes run sign to sign), rebuild, and push
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
- **One site, many maps (2026-11-16):** each map stays its own page and its own
  home-screen app (people install the one they use; the QR codes go to `map.html`), joined
  by `areas.json`, the Overview and switching on arrival (CLAUDE.md). An app opened over a
  mile (`AREA_NEAR_M`) from every area starts on the Overview; one opened near another
  area goes to that one's map. Switching on arrival needs a fix within 50 m.
- **The Middlesex Fells (2026-11-16)** is built from OpenStreetMap, like Saratoga: OSM's
  lines are on the tiles, and its route relations give the marked trails' colors on exactly
  their ways (Skyline and Rock Circuit white, Reservoir and the Rock Circuit Connector
  orange, Cross Fells blue, the Mountain Bike Loop green, Virginia Wood and Crystal Spring
  red, the Historic Trail yellow, Long Pond Nature Trail yellow by DCR's legend). The
  intersections are the Fells' own numbers (grid square and number, C5-17, on posts and on
  DCR's map), from OSM's junction points (259 of them). Only the trails on DCR's map: OSM
  also has the user-created paths DCR is closing, so a path is kept only where it follows
  DCR's statewide trail lines (GPS 2011-2012, all marked legal; no colors or numbers), or
  is a marked trail; and none mostly on water-supply land with no public access
  (MassGIS: Winchester's around its reservoirs, purple on DCR's map, "Restricted; No
  Public Access; Fines Apply", and MWRA's at the Fells Reservoir). DCR's points layer adds
  parking OSM lacks, and has the Fells' bridges and boardwalks for later. Zones: the West
  and East Fells, either side of I-93, as DCR divides it (kept 2026-11-16: the numbers'
  letters are the map grid's columns, strips across the park, not areas). DCR's legend has
  four marked trails OSM lacks or has only a piece of: Wright's Tower, Mustang Loop,
  Cascade, Healthy Heart.
- **Our trails match Trailforks' (2026-11-16).** Compared with Trailforks' lines (from a
  NEMBA chapter contact's app, synced 2026-10-27): 97% of theirs is within 10 m of ours,
  and none of their trails has 100 m we lack, Zone E included (cleaned up earlier). The
  differences are ours on purpose: we leave out the short feature and jump lines on top of
  Rocky Woods Range (207, B-Line and their neighbors, between E8, E11, E12 and E16), and
  keep Rib Breaker south of E22, Lost Trail by F27, the quarry access road and the rail
  trail, which Trailforks doesn't have. No GPX import needed.
- **QR codes only at the entrances (2026-11-16),** on the kiosks, not on the trail signs:
  it's an idea some people like, but it makes the signs busy, and people can be wary of QR
  codes everywhere.
- **Marks (2026-11-17):** "Mark this spot (just for you)" in the Report sheet drops a flag
  where you stand (to come back for something: a poop bag). Not a report: kept on the
  phone for a day, never sent. Route here goes to the flag itself (a trip ending at a
  point, like a round trip's start). Coming back within about 100 ft, a banner stays up
  with Got it (removes it) and Later until you're 150 ft away; it starts watching only
  once you've walked off. Back where you started lists any still left. Your spot only:
  no marking a spot you tap. **Keeping** one (a bone, a rock formation, to find again):
  a "Keep it" box when you name it, or Keep in the list back where you started (with Go
  back for it and Clear). A kept mark never expires; its banner says just OK (it stays),
  and the back-at-start list leaves it out.
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
- **The towns:** check before using their seals on shirts, and on the map (item 1).

## T-shirts

One shirt per zone in its color, each with one full-size sign, to raise money for the
signs: **A7 B3 C2 D5 E1 F4**. The reasoning, the rules and what's left before printing are
in `tshirt_signs.md`; the art is `tshirt_art.py`, previewed at `shirts/` (never linked).
