# Blue Hills: five OpenStreetMap mistakes to check

The Blue Hills trail map app is built from OpenStreetMap (OSM). Comparing OSM with the park's 2020 trail map turned up five places where OSM looks wrong. The app already corrects all five on its own. Fixing them in OSM itself would fix them for every other app and map that uses OSM data.

**One catch:** OSM can't take corrections copied from the park's map, because that map is copyrighted. An edit has to come from someone seeing the sign or the trail in person. So the plan is:

1. **On a walk:** check each spot below. The app's map shows where to go. You can also tap the intersection, then "Report a problem", then "I'm standing at this sign", which emails your exact location.
2. **Then:** make the OSM edits for whatever you confirmed. Steps are at the end.

Each spot has a link to it on OpenStreetMap and Google Maps.

---

## 1. The sign that OSM calls 5153 should be 3153

- **Where:** Chickatawbut section, up the trail north of 3151 and 3152.
  [OSM](https://www.openstreetmap.org/node/2772818973) ·
  [Google Maps](https://www.google.com/maps?q=42.223661,-71.045687)
  (42.223661, -71.045687)
- **Check:** what number is on the sign?
- **Why it looks wrong:** 5xxx numbers are the Ponkapoag section, south of I-93. This spot is in Chickatawbut, which is 3xxx, and the park map has 3153 here.
- **Resolved 2026-10-21:** the sign says 3153. Fixed in OSM (marked for review).

## 2. The sign that OSM calls 5157 should be 3157

- **Where:** about 50 m east-southeast of the sign above.
  [OSM](https://www.openstreetmap.org/node/2782489159) ·
  [Google Maps](https://www.google.com/maps?q=42.223442,-71.045101)
  (42.223442, -71.045101)
- **Check:** what number is on the sign?
- **Why it looks wrong:** the same reason as #1. The park map has 3157 here.
- **Resolved 2026-10-21:** the sign says 3157. Fixed in OSM (marked for review).

## 3. Sign 5422 is on the wrong junction in OSM

- **Where it should be:** where Middle Road crosses the Pipe Line, the straight north–south corridor between 5425 to the north and 5421 to the south.
  [OSM](https://www.openstreetmap.org/node/1564733307) ·
  [Google Maps](https://www.google.com/maps?q=42.198533,-71.074663)
  (42.198533, -71.074663)
- **Where OSM has it:** about 150 m west, where Middle Road meets Wannamanhut Path.
  [OSM](https://www.openstreetmap.org/node/1564733119) ·
  [Google Maps](https://www.google.com/maps?q=42.198060,-71.076392)
  (42.198060, -71.076392)
- **Check:** which of the two junctions has the 5422 sign? Does the other junction have a sign at all?

## 4. Part of "Headquarters Path" by Chickatawbut is really the Pipe Line

- **Where:** OSM names one long track "Headquarters Path". It runs from Chickatawbut Road (southwest of 4012) north past 4048, 4049, 4046 and 4066.
  - [The whole track on OSM](https://www.openstreetmap.org/way/9113729)
  - 4048, where it changes: [Google Maps](https://www.google.com/maps?q=42.231346,-71.061380) (42.231346, -71.061380)
  - 4066, on the northern part: [Google Maps](https://www.google.com/maps?q=42.235444,-71.059670) (42.235444, -71.059670)
- **What the park map shows:**
  - From 4012 up to 4048, it's Headquarters Path. This is a second trail with that name; the other one is by the Reservation Headquarters in Milton.
  - From 4048 north, it's the Pipe Line: the same north–south corridor as at 5422.
- **Check:** is there anything at 4048, or along the northern stretch, that says which trail it is? A trail sign, a blaze or a gas-line marker would all help. "It's obviously the pipeline corridor" counts too.

## 5. The stretch from 5343 to 5370 is Acton Path, not Prescott Foot Path

- **Where:** the north side of Ponkapoag Pond, east of 5343, along the Green Dot Loop.
  - 5343: [Google Maps](https://www.google.com/maps?q=42.196356,-71.089654) (42.196356, -71.089654)
  - 5370: [Google Maps](https://www.google.com/maps?q=42.195795,-71.086257) (42.195795, -71.086257)
  - [The stretch on OSM](https://www.openstreetmap.org/way/503099008)
- **What OSM and the park map say:** OSM has Prescott Foot Path continuing past 5343 to 5370. The park map labels the 5343–5370 stretch Acton Path, part of the Acton Path loop around the pond.
- **Check:** any trail-name sign at 5343 or 5370? If there's none, note that too.

---

## Making the OSM edits

You need a free account at [openstreetmap.org](https://www.openstreetmap.org/user/new). Each "OSM" link above opens that spot. Click **Edit** there to make the change in the browser editor, called iD.

| # | If you confirmed | Edit |
|---|---|---|
| 1 | The sign says 3153 | Select the junction point and change `ref` from `5153` to `3153`. |
| 2 | The sign says 3157 | The same change, `5157` to `3157`. |
| 3 | 5422 is at Middle Road × Pipe Line | Select the point OSM has now ([1564733119](https://www.openstreetmap.org/node/1564733119)) and delete its `ref=5422` and `junction=yes` tags. Then select the junction at Middle Road × Pipe Line ([1564733307](https://www.openstreetmap.org/node/1564733307)) and add `junction=yes` and `ref=5422`. |
| 4 | North of 4048 is the Pipe Line | Select the track, then the point at 4048, and use **Split** (the scissors, or press X). Change the `name` on the northern part to `Pipe Line` and leave the southern part as `Headquarters Path`. If other Pipe Line pieces in OSM carry more tags (for example `man_made=pipeline` on a separate line), those stay as they are. |
| 5 | 5343–5370 is Acton Path | Select that stretch and change `name` to `Acton Path`. |

**When you save,** iD asks for a changeset comment. Something like this works:

> Blue Hills Reservation: corrected intersection sign numbers (3153, 3157), moved 5422 to the junction where the sign is, and fixed trail names (Pipe Line north of 4048; Acton Path from 5343 to 5370), from a survey on [date].

Set the **source** to `survey`.

Only change what you actually saw. If a spot doesn't match what's described here, leave OSM as it is and let us know. That's useful to hear about too, since the app may have its own correction wrong.
