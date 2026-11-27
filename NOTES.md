# Project notes

The state of the trail-map project: what's open, what's been decided and why, and what we
know about the land. How to build and the working rules are in **CLAUDE.md**. Kept up to
date as things change; dates are when something was learned or decided.

## Open items

1. **Town seals** on the "Welcome to Milford!" banner (2026-11-04): white seals in `seals/`,
   from the shirt art. We're asking the towns for permission before the site is made more
   public; don't publicize it further until they've said yes. Color seals would just
   replace the three files (only Milford's color one is on hand, inside its website logo).
2. **Around R2** the map has a bigger problem than the bypass that was reported. GPX
   recordings covering everything around R2 are coming: bring them in with `import_gpx.py`,
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
   and let newer ones show a bridge that changed. **`bridges_todo.md`**: the ones still
   to find (OSM's bridges, boardwalks and fords on our trails, not yet reported), by zone;
   check one off there (`[x]`) once reported or found to have none. **`bridges_todo.html`**
   is its field page (linked from nowhere, noindex): its unchecked items, nearest first,
   with a tick kept on the phone; it reads the .md and NOTES each time, so nothing to build.
   Reported so far (2026-11-15): at C17, 33 ft, 42.186392,-71.495415 to
   42.186412,-71.495300; College Rock Run C3–C6, 43 ft, 42.189325,-71.496319 to
   42.189417,-71.496424. 2026-11-17 (zone F): The Main Trail F2–F1, the long boardwalk,
   walked both ways (42.171014,-71.488060 to 42.171077,-71.489099, and
   42.171063,-71.489142 to 42.171025,-71.488077): the ends agree within 4 m and 2 m,
   the lengths within 2 m; averaged, 42.171070,-71.489120 to 42.171019,-71.488068, 285 ft
   (one walk is good to about 4 m an end; worth walking long ones twice); Swampside F11–F2, three: 26 ft
   (42.168486,-71.490564 to 42.168411,-71.490569), 10 ft (42.168103,-71.490512 to
   42.168079,-71.490516) and 39 ft (42.168049,-71.490524 to 42.167946,-71.490565), the
   last two nearly end to end; Fairbanks Trail F7–F9, 108 ft (42.168310,-71.491705 to
   42.168602,-71.491784); Fairbanks Trail F10–F5, 30 ft (42.169555,-71.492966 to
   42.169638,-71.492961). 2026-11-18 (zone A): New Trail A4–A3, 66 ft (42.179592,-71.486991
   to 42.179640,-71.487224); New Trail A19–A14, 33 ft (42.180540,-71.492627 to
   42.180523,-71.492741); Town Forest Trail A21–A17, 69 ft (42.175176,-71.493632 to
   42.175101,-71.493392). 2026-11-21 (zone F): Swamp Bypass F19–F18, one bridge about
   12-15 ft long by eye, walked twice: 3 ft (42.166712,-71.484347 to 42.166705,-71.484339)
   and 7 ft (42.166717,-71.484382 to 42.166704,-71.484359), both short (on a bridge this
   short the GPS, good to about 3 m, can't measure the length: trust the eye); it has a
   broken slat (a Maintenance report); Fairbanks Trail F7–F9 again, 102 ft
   (42.168332,-71.491742 to 42.168607,-71.491786); Toejam F7–F2, 3 ft (42.168973,-71.491265
   to 42.168977,-71.491250), a stone crossing, "more like a bridge than a ford": decide how
   to draw it when bridges go on the map; The Main Trail F2–F1 a third time, 269 ft
   (42.171087,-71.489159 to 42.171069,-71.488167). 2026-11-22: Knee Jerk F12–F14, 13 ft
   (42.168281,-71.493129 to 42.168295,-71.493175); Knee Jerk F15–F12, two where OSM has two
   fords, 10 ft (42.168461,-71.494084 to 42.168459,-71.494125) and 75 ft (42.168471,-71.494200
   to 42.168440,-71.494475); Charles River Trail by R16, 16 ft (42.174024,-71.503872 to
   42.174067,-71.503863), flooded and not passable (a Maintenance report). 2026-11-25
   (zone B; labels as on today's map, the report's A21 is A20): Charles River Tow Road
   Lower B2–B1, OSM's 30 ft bridge (7 m from OSM's point), but both ends were taken at
   one spot, 42.179054,-71.505889 to 42.179057,-71.505884, so no length: walk it again;
   at B2, 3 ft (42.178280,-71.506143 to 42.178289,-71.506138); Jungle Escape Route
   B2–B3, 7 ft (42.178429,-71.505408 to 42.178426,-71.505379); Holliston Highway B6–A20,
   52 ft (42.179002,-71.501445 to 42.178886,-71.501332); Krusher B14–B13, two: 3 ft
   (42.182805,-71.497097 to 42.182812,-71.497098) and 13 ft (42.182982,-71.497769 to
   42.182981,-71.497816). 2026-11-26 (zone M): on the yellow-striped trail M13-J238, one bridge
   walked both ways: 20 ft (42.196816,-71.450525 to 42.196864,-71.450564); the walk back
   took both ends at one spot (42.196974,-71.450663, 13 m on), so no length from it.
9. **Blue in zone F** (2026-11-17; a route since 2026-11-21): Tonto F3–A16, The Main Trail
   F3–F2 (with the red), Toejam F2–F7, and the Fairbanks Trail F7–F10. Seen on Toejam, and
   just past F7 heading west (twice); nothing seen for the rest of the way, marked anyway as
   the route's way through to the "blue turns left" blaze at F10. Where it goes past F10
   is still to find.
   Elsewhere: one white blaze on Deer Way A15–A17 (2026-11-18), alongside its blue, the
   only white seen anywhere; not marked (Upper Charles has no white). Blue on 7-11
   (2026-11-22, seen facing north from the middle, where a sign was until 2026-11-23):
   marked on all of it, R18–R13, now that it's one stretch sign to sign.
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
    - Only obstruction reports (tree, washout, flooded, other; the app calls them
      Maintenance since 2026-11-18, the kind is still "obstruction"), only from the Upper Charles
      map. Not bridges: ours record bridges that exist, not where one should go (he reads
      them as suggestions). Not notes, blazes, checks. The rule (2026-11-18): the
      **Maintenance** button is exactly what goes to him from Upper Charles, nothing more or
      less. Anything new for the crew (a sign down, once signs are up) is added there as
      another choice, not as a kind of its own.
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
      design question), then go to him (a "Sign down" or "Sign damaged" choice under
      Maintenance). Fixed issues show for about two
      weeks.
    Nothing to build on our side until his two endpoints are live.
11. **Signing Holliston's other trails** (raised at the committee meeting, 2026-11-23). From
    OSM (paths and tracks in Holliston outside the Upper Charles area, grouped where they
    connect; a local review map, `holliston_review.html`), the three to plan on
    (2026-11-24). **On the map since 2026-11-24** as zones H, M and W (proposed; the About
    page says so): every OSM way of each (source "osm ..., added 2026-11-24 (zone ...)"),
    a candidate sign wherever three or more ways meet (92 in all), the rest routing
    junctions; each zone's 1 (`ZONE_ONES`) was at first the sign nearest a parking lot OSM
    has; since 2026-11-25 (Jason) H1 is the Highland Town Forest lot on Highland Street
    and W1 the rail trail (was W10); every H and W label moved. **Thinned the same day** (a local review map, `cull_review.html`, with a first cut
    by spacing; Jason's picks went further): 92 down to 37, the 55 taken out made
    junctions as zone N's were, so routes still use them; one added back (M14 now), so 38.
    **Entrances** (Jason, same day; street names from OSM): Highland H5 (parking; the
    lot's name to find), H9 (the unpaved south end of Mellen Street), H11 (Hollis
    Street), H1 (the Highland Town Forest lot, on Highland Street), H14 (Washington Street); Miller Hill M1
    (Burnap Road parking, behind Pinecrest Golf Course: since 2026-11-26 at the lot itself, the trail's end, Jason), M15 (Highland Street, by a service road the heatmap shows
    well used), M10 (Gorwin Drive), M11 (Ridge Road), and from the heatmap M13 (the trail
    end at Pinecrest Road and Fairview Street), M12 (Beatrice Lane, 2026-11-26); Wenakeening W8 and W3 (Summer Street, two
    lots), W1 and W11 (the rail trail), W14 (Timber Ledge Drive: "may be an access point"),
    W5 (Cross Street), W16 (Highland Street parking), and W22 (Idylbrook Park parking,
    Medway; below). Seven of them new signs at trail ends; 50 signs in the three (188 in
    all). To check on the ground: whether M13
    (Pinecrest Road) can be reached without crossing a yard. Settled: the service road from
    Beatrice Lane (OSM 8758995, by the water tank) is a way in (Jason walked it,
    2026-11-26): back on, to J294, with its entrance (M12); the 33 m past J294 was a dead
    end and stays off. W6 (#581) was on this list, whether it's worth
    keeping (it was in the tightest cluster in the new zones); the heatmap settled it
    (Jason, 2026-11-25): it stays.
    The other trail ends at streets (Fairlane Way, Winter Street, Underwood Street, Cross
    Street and more) look like neighbors' paths, not entrances.
    **Checked against the Strava heatmap** (2026-11-25; Jason's screenshots, kept local in
    `strava_review/`, aligned on road intersections; heat measured along each trail):
    Miller Hill's main loops are all well used. Dropped five OSM trails with little or no
    heat (the loop west of J322, the cross-trails inside the loop east of the old M4, which
    went with them, and two stubs east of M14); added the two service roads above and a
    484 m loop west of M3 that isn't in OSM, traced from the heat (`trace_m2_west`:
    replace it with a GPS track). Then (Jason: no driveways or backyard paths) took out
    the Beatrice Lane service road and its entrance, the 144 m past M4 toward the houses
    on Pinecrest Road, the track south of J239 toward the houses off Underwood Street
    (its first 96 m, M14 to J239, stays: it closes the loop from J237), and the trail
    south of it, left unconnected; and put back 60 m of one dropped trail, joining the
    dead end at J257 to the M4-M7 trail.
    Wenakeening (labels as they are after the cull below): every trail well used but the
    77 m from W3 to the Summer Street north lot (kept: the heat goes through the lot).
    Added OSM's track from the Cross Street end south to the trail toward W6 (98% heat,
    beside ours) and a 266 m trail east of W6 down to the trail from W4 to W10, traced
    (`trace_w6_east`: replace with a GPS track). Not added: the tangle of singletrack
    between W1, W5 and W6 (heavy heat, none of it in OSM; a GPS job). **South into
    Medway** (Jason: include it, as the forest takes in Hopkinton and Milford): OSM's tracks south of W12 and W9 through Idylbrook Conservation Land to
    Idylbrook Park, left out at first only because they're over the town line; a second
    screenshot shows heat on nearly all of them. Added 12 (3.8 km; not the 80 m one OSM
    marks access=no, nor a low-heat stub toward Diane Drive), closed the 13 m gap where
    they meet ours (J287 went, the tracks' junction stands), and made nine of the 14 new
    junctions signs: the four-ways first, none within about 80 m of another but the
    four-way 60 m from W22, the entrance (where the two paths from the park's lot split).
    Owners: W22, W23 and W24 the Town of Medway's; **W17, W18, W19, W20 and W21 on a
    private parcel** (a development company's), one more owner to ask.
    **Wenakeening thinned again** (2026-11-25, with the new trails; a local review map,
    `cull_review.html`, with the heatmaps under it; my proposal, Jason's OK): 26 to 24.
    Dropped four (then W12, W4, W14 and W23): two of the four signs within 140 m (the
    other two, W4 and W6, stay), one 83 m from W9, and one 60 m from W22; made signs of two junctions the new trails made, where
    the traced trail meets the trail from W4 to W10 and where the Cross Street track meets
    the trail to W6. Left as they are: W12-W17 (118 m), W19-W20 (132 m), W23-W24 (135 m),
    each its own junction. Medway added to `TOWNS`, the owner rules and the town lines
    (`uc_towns.py`, for "Welcome to Medway").
    **Numbering now follows the map's directions** (2026-11-25, Jason asked whether lower
    numbers still lead out): they didn't everywhere (26 signs, most in W, where the walk
    the map gives you to the zone's 1 climbed before it came down), because renumbering
    measured only through signed intersections and ignored `route_cost` and `closed`.
    `build_trail_graph(..., routing=True)` now goes through every junction as the map
    does; 76 labels moved, in every zone. Every sign now passes only lower numbers on
    its way to its zone's 1, but for F's old G group (`F_G_GROUP`), numbered after the
    rest on purpose. The check also turned up a 15 m break the Miller Hill cut made (the
    trail from M2 to M4 ended at J245; mended).
    **Highland checked against the heatmap** (2026-11-25; Jason's screenshot; aligned on
    roads, then fine-tuned to the trails, which moved the fit by about 20 m). The Town
    Forest parcel and the trail to it from H5 have no heat, as expected: they're new, and
    to be remade in this project (kept). Everything else is well used but three dead
    ends, taken out: the 286 m northeast of the old H8 toward the houses on Winter Street
    (so it was no junction any more, and is a routing junction now; 14 signs in H), a
    stub east of J270 and one south of the White Trail at J269 (OSM has them). The
    trail from H13 to H14 (Washington Street) has light heat a little to the north of
    OSM's line (real, and a real entrance: Jason); the spur from H13 to the edge of the
    land comes out behind the Holliston Historical Society, a way in of a sort; the White Trail's heat runs on east past our end to Washington Street,
    about 25 m, maybe the way in meant there. Left for the remaking: the 8 m gap in the
    Town Forest parcel south of J288.
    **Miller Hill walked** (2026-11-26, Jason's reports and a photo of the kiosk's trail
    map, kept local in `zone_images/`: the trails were re-marked in 2024 as a Girl Scout
    Gold Award project; labels as now). Blazes as the kiosk map has them (rectangles
    unless it says triangles): **orange**, the loop from the lot: M1, M2, then M3 and
    J295 to M5 on the west, J245 and M4 on the east, joined by J322 and J242 (the walk
    reported it red, "maybe orange?": orange); **orange triangles**, the loop west of M3
    (`trace_m2_west`, J293 to J295, and J293 to M3); **blue triangles**, M5 south to
    M8, J321 (the old M5) by J251 and J240 to J246, and J242 by J241, J292, M6 and
    J250 to J246; **blue**, M8 to J247 and J150, M8 west to M11 (Ridge Road) and on
    to M10 (Gorwin Drive) and Ridge Road, J247 to J248, and J250 to M9; **white**, a loop
    off the orange: M4 to J259 and down by J297 to M7, and M4 by J242 and J292 to M6,
    east to J257 and J297; **yellow dots**, the long trail from its southwest end by M10,
    M9 and M7 to M14 (the kiosk calls it "rectangle and circle"; Jason saw dots);
    **yellow stripes**, M13 (Pinecrest Road) to J238. Not on the kiosk map: J241-J240,
    J251-J253-J322, the yellow dots east of M14. Blazes now run junction to junction
    (`blazeStops`; they ran sign to sign, which lost Miller Hill's turns at unsigned
    junctions); in the forest, that drew two as their data says: 7-11's blue J133-R13
    only (it filled out to the next sign), and Top Down's orange C24-J290 (left out
    before). Signs: M5's moved up to J243, where the orange turns off and the blue
    triangles begin ("the intersection should be moved to where it turned blue"; the
    old M5 is J321); M1 is now the lot itself ("Parking - rear of Pinecrest Golf
    Course", the kiosk says), at the trail's end (the old M1, a three-way junction,
    keeps a sign: M2); Beatrice Lane's entrance back (M12). A spur off the yellow dots
    east of M7 (42.195157,-71.450882) is marked private: not on our map (keep it off).
    Then (Jason, same day) the old M6, 40 m from M5, is a junction (J322), and two
    junctions are signs: M6, where the white leaves the blue triangles, and M8, where the
    blue triangles meet the blue rectangles south of M5. 15 signs in M, 191 in all. Then (Jason) M12-M14 in an order of
    their own, so neighbors go together: Beatrice Lane M12, Pinecrest Road M13, the one
    east of it M14 (`HAND_ORDER`; distance from M1 alone had them east, west, east). A
    nearest-next numbering for every zone was tried, but not taken: it moves most labels
    everywhere (18 of A's 22) and didn't give this order.
    Signs now 150-190 m apart at the median (Upper Charles' zones 70-110 m). Next: check
    names and blazes (White, Blue and Yellow Trails at Highland), and walk them (Miller
    Hill east of M7: M14 and M15). Owners from MassGIS parcels (added to
    `uc_data/parcels.geojson`).
    - **Miller Hill (M)** (Chamberlain St to Highland St): 7.3 km since the heatmap, 38
      candidates, 12 signs; 15 after the walk (2026-11-26). All on Town of Holliston land.
    - **Highland Town Forest (H)**, with Mellen Street, Poitras Memorial Land and the
      Daniels Property (north of town; White, Blue and Yellow Trails): 8.1 km, 29, 15 (11
      and four new entrances); 7.7 km and 14 signs after the heatmap. All the Town's; Mellen Street
      has a Mass Audubon CR.
    - **Wenakeening Woods (W)**: 6.6 km, 25, 17 (15 and two new entrances); 11.0 km and 24
      signs with the Medway part, after the second thinning. Mostly the Upper Charles Conservation Land Trust's land,
      some the Town's, a few on private parcels; in Medway, the Town of Medway's and one
      private parcel.
    About 23 km: about 50 signs at Upper Charles' 2.2 per km (140 on 62.6 km), 44 after the
    thinning and the entrances, so 140 to 184 (182 since two in A and C went). New
    partners to ask, as DCR and The Trustees were: the Upper Charles Conservation Land Trust, and Mass Audubon (the Mellen
    Street CR). OSM's junction counts run high before thinning. The rest are small enough
    for an entrance sign, not numbered ones: by Hopping Brook (4.2 km, mostly track), near Prentice St (2.2 km), Pleasure Point,
    Brentwood, Patoma Park, Factory Pond. Mass Audubon's are left to Mass Audubon (their
    own trails, maps and markers): Waseeka Wildlife Sanctuary, and Broad Hill Wildlife
    Sanctuary (off Highland Street; one 1.3 mi Nature Trail), which is very likely the
    Poitras CRs off Highland Rd (private land, Mass Audubon's CR; OSM has 3.8 km of paths
    and tracks there, more than the sanctuary's trail, some running north to the Ashland
    line). Decided: zones on the Upper Charles map (not a map of their own), its outline in
    patches (`areas.py` `outlines`), opening on the forest itself (`openBounds`).
12. **To do for the new zones** (Jason, 2026-11-25):
    - **The committee worklist:** add the new private landowners (owners.html has them):
      the parcel under W2, W5 (the Cross Street entrance) and W6, and the Medway
      development company's parcel under W17, W18, W19, W20 and W21; and the Upper
      Charles Conservation Land Trust (11 signs in W; a partner to ask, item 11). (H1 looked private
      at first: its point is in Highland Street, and the owner lookup took the parcel
      across the road; it now follows the sign's trail into the land, the Town's.)
    - **A Medway town seal**, white like the others, as `seals/medway.png`: the "Welcome
      to Medway" banner shows it once it's there and the map is rebuilt (item 1; ask
      Medway's permission as for the others).
    - **A contact in Medway** (Conservation, for the Town of Medway's land at W22, W23
      and W24, and maybe as a partner).
13. **Later: numbering neighbors together** (Jason, 2026-11-26). Numbers go out by
    distance from the zone's 1, so signs at about the same distance get neighboring
    numbers wherever they are (Miller Hill's M12-M14 were east, west, east; `HAND_ORDER`
    fixes that one by hand). Tried: numbering nearest-next, each sign the nearest to the
    last whose way out is already numbered. Consecutive numbers come 15-45% closer in
    every zone, but most labels move (18 of A's 22, where temporary signs are up), and it
    still put Beatrice Lane at M8. To look at: a zone at a time, other rules (a branch
    at a time), and whether it's worth it before the signs go up (RENUMBER).
14. **Jason's Strava tracks** (2026-11-26: his export, 2015-2026; 862 activities in
    Upper Charles, 700 of them in the forest, 169 W, 75 M, 7 H). Kept local: the tracks
    in a working folder outside the repo, a review page in `strava_review/` (gitignored:
    our trails, where the tracks went, off-trail clusters, and stretches drawn off).
    Findings: our lines are good (7 stretches 6-9 m off, about GPS error: left be); of 28
    off-trail clusters, 7 are the rail trail (not ours) and one is wandering around on
    top of College Rock (Jason; by the lot, so it looked like a lot);
    trails with none of his activities (62, mostly N and H) only say where he goes, not
    that they're unused. Added (Jason: "those are trails"): seven OSM paths east of
    College Rock around C8, C11, C13 and C14 (OSM 1380865707, 130500783, 306426101,
    1380865706, 1380913337, 1380913335, 1380865712), with 13 junctions; C13-C18 moved
    (Engel's sign is C18 now: the worklist); 130500783 starts 7 m back at J124, where it
    meets the trails, and ends at the loop west of Teeter Totter, a dead end (the loop
    isn't worth including: Jason). Also the rest of Kitchen in F, west from J95 to the Powerlines
    trail (OSM 162500137, three pieces between the trails it crosses; Jason: "a real
    trail, not worth intersections, but may as well connect": junctions, no signs). And
    Condo Rock in R, from Middle Sister to the top (72 m, a dead end: OSM 130212058's
    east end and 1380319243, the top by the lidar at 114 m; Jason: "a trail, at least to
    the top"; the way around the back, down to Middle Sister again, left off). Its
    prominence by the lidar is 39 ft, more than College Rock's 33 (Rocky Woods Range 165,
    the two unnamed hills by the Tow Road and Adams Street 65 and 54). The hill just west
    of it, on the Charles River Loop by R16 (385 ft, prominence 28 ft, no name found in
    OSM, Trailforks or the 2012 map), is on the map as an unnamed hilltop; Condo Rock is
    labeled too (372 ft). The rail trail's Cross Street lot (Jason: on the north side, just east of the rail
    trail; OSM 1040060989) is L2, a lot like Route 85's L1 (no sign, no zone), with 19 m
    along Cross Street to the crossing and the rail trail from W1's trail past it to W11
    (OSM's line): routes can use the rail trail between W1 and W11, and W's labels moved
    (W23, the rail trail's far end, is W11 now). And Cross Street from the crossing to W5's
    trails (153 m, OSM's street line; Jason: the lot is good access for W5 too).
    And W's Medway signs take its highest numbers, W17-W24 (`TOWN_LAST`, Jason): Holliston's
    are W1-W16, and every route out still passes only lower numbers. The same for every
    zone across a town line, as the first hand numbering had it (Jason): R's Milford signs
    after its Holliston ones (R6 and R7 swapped), and N's one Holliston sign last (N18,
    was N6). Now every zone's towns are one block each: A, H, M Holliston; B Milford then
    Holliston; C Hopkinton, Holliston, Milford; F Holliston, Milford; N Milford, Holliston;
    R Holliston, Milford; W Holliston, Medway.
    Left off: OSM's "Swamp Bypass(Flooded)" (1442933991) beside our Swamp Bypass in F,
    31 of his activities 2020-2026 ("used to be a trail, but it is deeply underwater").
    The review is done (Jason, 2026-11-26: no other candidates). Still possible: redraw
    the traced trails (`trace_m2_west`, `trace_w6_east`) from his tracks, kept for that
    in the working folder (the export's zip copy deleted).

## How the field work goes

We walk the trails with the map and file reports from it (a blaze, by color; maintenance,
like a tree down; a bridge, marked at each end; or a note), then send them in a batch by
email, to Jason Breslau by name. Back where you started, the map offers to send them, then shows
a walk summary picture to save or share. `read_reports.py` lists a pasted email's
reports against what the map has; we apply them to the data (blazes run sign to sign), rebuild, and push
the day's changes together.

## Decisions worth knowing

- **Breadcrumbs are the walk, not the drive (2026-11-26):** a loop planned at home and
  driven to counted the drive (1.9 miles) and kept the planned line on the map, so Jason
  cleared his breadcrumbs. Now breadcrumbs are only kept within 150 m of a trail and never
  at driving speed (over 9 m/s, about 20 mph), measured to the trails, not the map's
  rectangle (which, with H, M and W, takes in most of Holliston, so "you drove away"
  never fired either); and a route planned from an entrance follows you once you're
  there on foot (`goLiveAtStart`), with a banner saying so.
- **OSM first for lines (2026-10-23):** OpenStreetMap's lines sit on the map tiles and
  are mostly traced from imagery; ours were GPS tracks. 146 of the trails use OSM's
  geometry (`uc_osm_geometry.py`, a one-time conversion). Still ours: Dirty Little
  Secret, The Maine Line, the quarry access road, Armageddon, 495 Run B.
- **Names are ours.** OSM has Gintro, Giggity and The Gigg wrong. Ours: Gintro runs into
  R9; "The Gigg" (`tf_56`); "Giggity" (`tf_125`).
- **Signs snap to trails within 10 m** (`trailmap.SIGN_SNAP_M`).
- **The zones** were drawn by feel by the trail regulars, and a connectivity analysis
  (2026-10-13) backed them: 66-86% of each zone's sign-to-sign links stay inside it, and
  zones and the best clustering agree on 86% of sign pairs. The fuzzy edges (B toward C
  and A, N32-N34 toward R, R8/R13/F16/F17 toward N) were checked on the ground and kept.
- **Zone letters stand for their places (2026-11-24):** A Adams Town Forest, B Beaver Brook
  Woods, C College Rock Park, F Fairbanks, and now R Rocky Woods (was D) and N NEMBA Land
  (was E); the numbers didn't change, and these notes, `sign_logos.csv` and
  `tshirt_signs.md` were relabeled with them (an older note's E14 is today's N14). New
  areas take their own letter (item 11). Leave D and E unused for a while, so an old D or
  E label can't be mistaken for a new place. Avoid letters that read as digits (I, O, S,
  Z, G).
- **Blue Hills** is built from DCR's own trail data (2026-10-30), replacing a version
  traced from the park's PDF map. `bluehills_osm_fixes.md` lists where OSM is wrong there.
- **One site, many maps (2026-11-16):** each map stays its own page and its own
  home-screen app (people install the one they use; the QR codes go to `map.html`), joined
  by `areas.json`, the Overview and switching on arrival (CLAUDE.md). An app opened over a
  mile (`AREA_NEAR_M`) from every area starts on the Overview; one opened near another
  area goes to that one's map. Switching on arrival needs a fix within 50 m.
- **Switching by zoom (2026-11-23):** zoomed far out on a map (11), the Overview; zoomed in
  on the Overview (14, trails readable) with the middle of the view in an area, its map.
  The view carries over, so it reads as zooming on. The gap between 11 and 14 keeps it
  from flipping back and forth; no switch while you're following a route; a page's own
  fitting (a map's to a route, a zone or your walk; the Overview's to you or a group of
  maps) doesn't count. A map handed a view keeps it
  (no jump to you on the first fix, no launch redirect).
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
  and none of their trails has 100 m we lack, Zone N included (cleaned up earlier). The
  differences are ours on purpose: we leave out the short feature and jump lines on top of
  Rocky Woods Range (207, B-Line and their neighbors, around N6, N8 and N10), and
  keep Rib Breaker south of N14, Lost Trail by F25, the quarry access road and the rail
  trail, which Trailforks doesn't have. No GPX import needed. **Again 2026-11-23,** finer
  (40 m with nothing within 20 m; a local review map, `trailforks_review.html`): added from
  OSM the west side of Whaleback Rock (now the Charles River Trail), Link 7 (R21 to R20,
  north of Three Sisters West) and an unnamed side line off the NEMBA Loop by N10. Left out:
  Trailforks' Connector, a dead end off the White Trail over Beaver Brook toward private
  land, and the archived Down and Up and Rubberstamp. Ours only: Found, Firewall and To
  Firewall by F25, which Trailforks doesn't have.
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
- **Impassable trails (2026-11-22):** a trail marked `closed` (the Charles River Trail by
  R14, flooded at its bridge) is drawn in rose dashes from close in (an ordinary trail from
  farther out), its panel says why, and routes never use it (it can't be added to one, or
  to a loop). Take the mark off once it's passable again. Only the Charles River Trail's
  south part (`tf_29`, J13 to J14) is marked; its north part (`tf_29_n`, J13 to B3) is open.
- **Whaleback Rock is a jughandle (2026-11-23):** just the loop on the east side of the
  rock, off the Charles River Trail. The trail up the west side (from OSM, new) and on north
  to B3 is the Charles River Trail (`tf_29_n`).
- **Following a route (2026-11-22):** the part you've walked isn't drawn (it was grey, over
  the breadcrumbs and hiding them); the breadcrumbs show where you've been. Reverse (and
  Reverse loop) only show until you've set off: partway round, Reverse read as "go back
  the way you came".
- **Thinning the clusters, third round (2026-11-24):** of the signs 250 ft or less apart
  by trail (20 pairs in 14 clusters, none in the new zones; N1/R9 and R3/R4 kept as
  before): out A8 and C19 (labels then; now `J289`, `J290`). 31 labels moved in A, B and
  C; the open items and bridges_todo carry the new ones. 182 signs.
- **Thinning the clusters, second round (2026-11-23):** of the signs 200 ft or less
  apart: out C4, C12, C18, R14, R19 (labels then; now `J129`-`J133`), and a sign added in
  zone N where NEMBA Loop crosses itself, just south of the R14 that went (it was `J54`;
  on Town of Milford land, so it may need the town's OK). 140 signs.
- **Thinning the clusters (2026-11-23):** of the signs 150 ft or less apart by trail, one
  or two went from each cluster but R3/R4 (kept): A11 (the temporary sign posted as A12
  comes down), B8, B11, C13, C20, R11, R21, F24, F28, by their labels then; now junctions
  `J120`-`J128`. 144 signs. Every zone but E renumbered (by distance along the trails, so
  C and D shuffled); the notes were carried along, except the dated CR lists and zones
  analysis.
- **Fewer signs in zone N (2026-11-23):** 29 down to 17. NEMBA's land has its own trail
  signs, so ours there only need to make it read as part of the whole: hubs, the ways in
  (N2, the old N3, is one), and the R9/N1 pair kept on purpose, as the line between the
  areas. Out: the signs on the power line land and the private parcels by Cedar Street,
  where permission isn't likely, and the NEMBA ones in the tight strings. Each is an
  unsigned junction now (`J108`-`J119`), so routes still use it. Zone N renumbered: N1
  stays; old N3 is N2, N4 N3, N7 N4, N10 N5, N11 N6, N9 N7, N12 N8, N16 N9, N17 N10,
  N20 N11, N15 N12, N21 N13, N22 N14, N19 N15, N25 N16, N28 N17.
- **One fewer sign at the Fairbanks Trail cluster (2026-11-21):** three signs stood within
  about 100 ft, 31 m apart; the middle one (data 66, then F9) is now an unsigned junction
  (`J106`), so routing still joins its trails there. The zone F labels past it moved down
  one (then: F10 became F9, through F31 to F30); the notes were carried along, except the
  CR section's dated lists.

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
  by The Trustees and DCR and covers the whole parcel (Map 1-2-35). Signs: R1-R4 and
  F1-F19 for certain; A23 A24 N11 R5 R6 R8 depend on which boundary is right (the state's
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
- **Sign quotes:** Voss Signs (DCR's sign maker) and Alpine Signs (added 2026-11-18).
- **Sign size: 9 x 9 in (2026-11-24),** as DCR's Medfield sign (D3 there, measured from a
  photo with a hand for scale, and the hand against a ruler: 8.5 to 9 in square, so a
  standard 9 in blank; 81 sq in, well under the 400). What the photo shows: aluminum with
  rounded corners, two bolts (top and bottom, centered) on a wooden post, white
  reflective (prismatic) lettering on brown; the number about 4.25 in tall, the two lines
  of text about 0.75 in. `tshirt_art.py` draws the signs this size, square.
- **The Trustees** like the shirt idea but asked for their logo off the shirts.
- **NEMBA:** check before using its land's sign and its logo on the N1 shirt.
- **The towns:** check before using their seals on shirts, and on the map (item 1).

## T-shirts

One shirt per town (2026-11-18; it was one per zone), in the color of one of its zones,
each with one full-size sign, to raise money for the signs: **A7** (Holliston, red),
**C2** (Hopkinton, green), **N1** (Milford, NEMBA's land, purple). The reasoning, the
permissions and what's left before printing are in `tshirt_signs.md`; the art is
`tshirt_art.py`, previewed at `shirts/` (never linked).
