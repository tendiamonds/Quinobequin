# Upper Charles Forest T-shirts: one shirt per town

*One per town since 2026-11-18 (it was one per zone, picked 2026-10-13).*

**The idea:** a plain shirt in the color of one zone per town, printed with one real,
full-size sign from that zone. Sales help pay for the signs. Three shirts, one per town.

## The picks

| Zone | Shirt color (zone color) | Sign | Town | Land | Trails meeting there |
|---|---|---|---|---|---|
| A, Adams Town Forest | red, `#e74c3c` | **A7** | Holliston | Town of Holliston | Campfire Trail, Holliston Highway, Humpback Rock, SI Connector, Sudden Impact |
| C, College Rock Park | green, `#2ecc71` | **C2** | Hopkinton | Town of Hopkinton | College Rock, Walker Trail |
| N, NEMBA Land | purple, `#9b59b6` | **N1** | Milford | NEMBA | Gintro, Nemba Way, One Ledges, The Main Trail, Three Ledges |

## How the signs were picked

Each is on public land (N1 on NEMBA's own land, on purpose) and is a hub where several
trails meet. Each has a clean, single-digit number: nothing that calls something else to
mind, like `A1` (steak sauce), `A5` (Wagyu), `A4` and `B4` (paper sizes), `F5` (the
refresh key). No number repeats across the three.

- **A7:** chosen earlier for the site icon. Five trails meet there, more than at any
  other A sign.
- **C2:** Hopkinton's only public signs are C1 and C2. N1 takes the 1, so C2.
- **N1:** on NEMBA's land. The biggest hub of the three: nine ways in from five trails,
  and the third-most central sign in the network.

None of the three is on CR land, so no CR holder's logo comes into it.

## The art

`tshirt_art.py` draws the signs in the style of DCR's Medfield signs, with the town seals
and land logos from `tshirt_art/logos/`, and writes `shirts/`: a preview page on the site
(https://tendiamonds.github.io/Quinobequin/shirts/). It's marked noindex, and none of the
site's pages link to it; keep it that way. (It also draws the About page's six sample
trail signs, one per zone, in `sign_samples/`: those aren't shirts.)

The Holliston seal is Wikipedia's 314 px line art, cleaned up. A vector copy from the
Town Clerk would be better.

## Permissions first

- **NEMBA's OK** for the E shirt: its land's sign and its logo.
- **Each town's OK** to put its seal on merchandise (and on the map's town banners; see
  NOTES.md).
- **No DCR or Trustees logo on any shirt** (decided 2026-10-23: DCR can't endorse
  fundraising for another organization, and The Trustees asked for theirs off too).

## Before printing

- **Use the final sign artwork.** These picks come from the sign numbers on the map
  (`sign_logos.csv` and `map.html`); the shirts should use the final sign design once
  it's settled, and the numbers can still change until the signs are installed.

## Earlier: one shirt per zone (2026-10-13 to 2026-11-18)

Six shirts, A7 B3 C2 R5 N1 F4 (one Hopkinton, two Milford, three Holliston), with
B3 (Beaver Brook Woods, blue), R5 (Rocky Woods, orange) and F4 (Fairbanks, teal) besides
the three above. R5 and F4 are on the Fairbanks CR.
