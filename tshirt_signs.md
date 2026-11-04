# Upper Charles Forest T-shirts: one sign per zone

*Picked 2026-10-13.*

**The idea:** a plain shirt in each zone's color, printed with one full-size sign from that zone. Sales help pay for the signs.

## The picks

| Zone | Shirt color (zone color) | Sign | Town | Land | Trails meeting there |
|---|---|---|---|---|---|
| A, Adams Town Forest | red, `#e74c3c` | **A7** | Holliston | Town of Holliston | Campfire Trail, Holliston Highway, Humpback Rock, SI Connector, Sudden Impact |
| B, Beaver Brook Woods | blue, `#3498db` | **B3** | Milford | Town of Milford | Holliston Highway, Jungle Escape Route, Whaleback Rock |
| C, College Rock Park | green, `#2ecc71` | **C2** | Hopkinton | Town of Hopkinton | College Rock, Walker Trail |
| D, Rocky Woods | orange, `#f39c12` | **D5** | Holliston | Town of Holliston | The Gigg, Uphill Connector |
| E, NEMBA Land | purple, `#9b59b6` | **E1** | Milford | NEMBA | Gintro, Nemba Way, One Ledges, The Main Trail, Three Ledges |
| F, Fairbanks | teal, `#1abc9c` | **F4** | Holliston | Town of Holliston (Fairbanks CR) | Middle Child, The Main Trail |

## The rules we used

**Constraints:**
- Public land only, except E, which should be on NEMBA's own land.
- No number used twice.
- One Hopkinton shirt, two Milford, three Holliston.

**The tests from choosing A7 for the site icon:**
1. **A hub,** where the most trails meet.
2. **A clean number** that doesn't call something else to mind. For example `A1` (steak sauce), `A5` (Wagyu), `A4` and `B4` (paper sizes), `F5` (the refresh key, and a tornado rating).
3. **A single digit,** which reads boldest. All six picks are single digits.

## Why each one

- **A7:** chosen earlier for the site icon. Five trails meet there, more than at any other A sign.
- **B3:** tied for the most ways in B. It's the network's second-most central sign, meaning more shortest routes between other signs pass through it than through almost any other.
- **C2:** Hopkinton's only public signs are C1 and C2. E1 takes the 1, so C2.
- **D5:** a Holliston hub, with three ways in from two trails (Dead Irishman, its fourth, came off the map 2026-10-21). D had to be a Holliston shirt once E1 made E a Milford one.
- **E1:** on NEMBA's land. It's the biggest hub of all the picks: nine ways in from five trails, and the third-most central sign in the network.
- **F4:** a central junction on The Main Trail. F7 would repeat A7's 7, and F2 would repeat C2's 2.

## Alternative, if you'd rather show off D12

Use **A7, B13, C2, D12, E1, F4**.
- **D12** is the most central sign in the whole network: B Bypass, Middle Sister and Sister #3.
- B then becomes the Holliston shirt: **B13**, at Log Run, Milford Byway and CraftRoots Connector.
- The cost is two shirts with two-digit numbers.

## The art

`tshirt_art.py` draws the six signs in the style of DCR's Medfield signs, with the town seals and land logos from `tshirt_art/logos/`, and writes `shirts/`: a preview page on the site (https://tendiamonds.github.io/Quinobequin/shirts/). It's marked noindex, and none of the site's pages link to it; keep it that way.

## Decided (2026-10-23)

- **No DCR or Trustees logo on any shirt.** DCR can't endorse fundraising for another organization, and The Trustees asked for theirs off the shirts too (they like the shirts). So D5 and F4 show only the Holliston seal. NEMBA's logo is still on E1.
- **The Holliston seal** is Wikipedia's 314 px line art, cleaned up. A vector copy from the Town Clerk would be better.

## Before printing

- **NEMBA's OK.** Check with NEMBA about putting their land's sign and logo on the E shirt.
- **Town seals.** Each sign shows its town's seal. Check whether each town is fine with its seal on merchandise (and on the map's town banners; see NOTES.md).
- **"Alt+F4".** The F4 shirt may get "close window" jokes from people who know the keyboard shortcut. If that's unwelcome, the next F choice is F9.
- **Use the final sign artwork.** These picks come from the sign numbers on the map (`sign_logos.csv` and `map.html`). The shirts should use the final sign design once it's settled.
