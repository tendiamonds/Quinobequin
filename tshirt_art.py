"""
Print-quality art of the T-shirt signs (tshirt_signs.md), after DCR's trail signs (the
Charles River Reservation's D4 in Medfield): the trail-sign brown, the town and zone on
top, the number big below, and small marks along the bottom: the town seal at the left,
the CR holders' or landowner's logos at the right. One PNG each, 12 inches wide at
300 dpi with a clear background around the sign, written to tshirt_art/.

The marks are white images with clear backgrounds in tshirt_art/logos/ (holliston_seal.png,
milford_seal.png, hopkinton_seal.png, dcr.png, trustees.png, nemba.png); a mark that
isn't there yet is left off, and listed. Use only marks their owners have OK'd.

  python tshirt_art.py

It also writes shirts/: a page of the six on their shirt colors, to show people. It's
published with the site but linked from nowhere (and kept out of search engines). And
sign_samples/: the six as trail signs, with every logo their land calls for (DCR's too, on
the Fairbanks CR), for the About page.
"""

import os

from PIL import Image, ImageDraw, ImageFont

PROJ = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(PROJ, "tshirt_art")
LOGOS = os.path.join(OUT, "logos")
BROWN = (122, 49, 34)          # the sign brown (DCR's is close to this)
WIDTH = 3600                   # 12 in at 300 dpi
RATIO = 0.94                   # height to width, as the Medfield sign
FONT = r"C:\Windows\Fonts\seguisb.ttf"     # Segoe UI Semibold: close to DCR's type
FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"

# label, town, zone, logos at the right (the seal at the left comes from the town). DCR and
# The Trustees ask that their logos not be used on fundraising shirts (2026-10-23), so the
# Fairbanks CR signs show just the town seal; the trail signs themselves carry both logos
# (TRAIL_LOGOS).
SIGNS = [
    ("A7", "Holliston", "Adams Town Forest", []),
    ("B3", "Milford", "Beaver Brook Woods", []),
    ("C2", "Hopkinton", "College Rock Park", []),
    ("D5", "Holliston", "Rocky Woods", []),   # on the Fairbanks CR (its holders' logos: not on shirts)
    ("E1", "Milford", "NEMBA Land", ["nemba"]),                # NEMBA's own land
    ("F4", "Holliston", "Fairbanks", []),     # on the Fairbanks CR (its holders' logos: not on shirts)
]

# The layout, as shares of the sign's width (W) and height (H), from the Medfield sign
CORNER = 0.055                 # of W
LINES = [(0.135, 0.075), (0.265, 0.075)]   # (center y, cap height) of H: town, zone
BIG = (0.585, 0.47)            # center y and cap height of the number
MARK_Y, MARK_H = 0.905, 0.11   # center y and height of the marks along the bottom
MARK_X = 0.075                 # the seal's left edge, and the logos' right edge, in from the side
TEXT_MAX_W = 0.88
BIG_MAX_W = 0.86


def cap_height(path, size):
    """The font's cap height in pixels at this size (from an H)"""
    f = ImageFont.truetype(path, size)
    l, t, r, b = f.getbbox("H")
    return b - t


def fitted(text, path, cap_px, max_w):
    """A font for text with caps cap_px tall, shrunk to fit max_w if need be"""
    size = round(cap_px * 100 / cap_height(path, 100))
    f = ImageFont.truetype(path, size)
    w = f.getlength(text)
    if w > max_w:
        f = ImageFont.truetype(path, int(size * max_w / w))
    return f


def mark(name, h):
    """A mark from tshirt_art/logos, h pixels tall, or None if it isn't there"""
    p = os.path.join(LOGOS, name + ".png")
    if not os.path.exists(p):
        return None
    im = Image.open(p).convert("RGBA")
    box = im.getbbox()   # (trimmed to what's drawn)
    if box:
        im = im.crop(box)
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


def draw(label, town, zone, logos, path):
    W = WIDTH
    H = round(W * RATIO)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=round(CORNER * W), fill=BROWN + (255,))
    white = (255, 255, 255, 255)
    for (cy, cap), text in zip(LINES, (town, zone)):
        f = fitted(text, FONT, cap * H, TEXT_MAX_W * W)
        c = cap_height(FONT, f.size)
        d.text((W / 2, cy * H + c / 2), text, font=f, fill=white, anchor="ms")
    f = fitted(label, FONT_BOLD, BIG[1] * H, BIG_MAX_W * W)
    c = cap_height(FONT_BOLD, f.size)
    d.text((W / 2, BIG[0] * H + c / 2), label, font=f, fill=white, anchor="ms")

    missing = []
    h = round(MARK_H * H)
    top = round(MARK_Y * H - h / 2)
    seal = mark(town.lower() + "_seal", h)
    if seal:
        im.alpha_composite(seal, (round(MARK_X * W), top))
    else:
        missing.append(town.lower() + "_seal")
    x = round(W - MARK_X * W)
    for name in reversed(logos):
        m = mark(name, h)
        if m:
            x -= m.width
            im.alpha_composite(m, (x, top))
            x -= round(0.03 * W)
        else:
            missing.append(name)
    im.save(path, dpi=(300, 300))
    return W, H, missing


# The trail signs themselves carry every logo their land calls for: DCR's (its 2026 logo)
# with The Trustees' on the Fairbanks CR. These go on the About page as sample signs.
TRAIL_LOGOS = {"D5": ["dcr_2026", "trustees"], "F4": ["dcr_2026", "trustees"]}   # (DCR first: its wide logo beside the "t" reads better)
SAMPLES = os.path.join(PROJ, "sign_samples")
SHIRTS = os.path.join(PROJ, "shirts")      # the page to show people (published, linked from nowhere)
SHIRT_COLORS = {"A": ("red", "#e74c3c"), "B": ("blue", "#3498db"), "C": ("green", "#2ecc71"),
                "D": ("orange", "#f39c12"), "E": ("purple", "#9b59b6"), "F": ("teal", "#1abc9c")}
TEE = ("M105 12 C120 40 180 40 195 12 L245 26 L292 74 L258 116 L232 98 L232 322 L68 322 "
       "L68 98 L42 116 L8 74 L55 26 Z")


def heathered(color):
    """A zone color as a heathered shirt dyes it: a quarter of the way to a mid grey"""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(v * 0.75 + 0x88 * 0.25) for v in (r, g, b))


def write_samples():
    """sign_samples/<label>.png: the six as trail signs (all their logos), web-sized, for the
    About page"""
    os.makedirs(SAMPLES, exist_ok=True)
    for label, town, zone, logos in SIGNS:
        full = os.path.join(SAMPLES, label + "_full.png")
        W, H, missing = draw(label, town, zone, TRAIL_LOGOS.get(label, logos), full)
        im = Image.open(full)
        im.resize((600, round(600 * im.height / im.width)), Image.LANCZOS).save(os.path.join(SAMPLES, label + ".png"))
        os.remove(full)
        if missing:
            print("  %s sample still without %s" % (label, ", ".join(missing)))
    print("Wrote %s (six sample trail signs)" % SAMPLES)


def write_page():
    """shirts/index.html: each sign on its zone's shirt color, web-sized, with the print file.
    Linked from nowhere on the site, and kept out of search engines."""
    os.makedirs(SHIRTS, exist_ok=True)
    cards = []
    for label, town, zone, logos in SIGNS:
        art = Image.open(os.path.join(OUT, label + ".png"))
        art.resize((900, round(900 * art.height / art.width)), Image.LANCZOS).save(os.path.join(SHIRTS, label + ".png"))
        art.save(os.path.join(SHIRTS, label + "_print.png"), dpi=(300, 300))
        name, color = SHIRT_COLORS[label[0]]
        cards.append(
            '<figure class="card">\n'
            '  <div class="tee"><svg viewBox="0 0 300 330" aria-hidden="true"><path d="%s" fill="%s"/>'
            '<path d="%s" fill="#fff" filter="url(#heather)"/></svg>\n'
            '    <img src="%s.png" alt="Sign %s: %s, %s"></div>\n'
            '  <figcaption><b>%s</b> &middot; %s, %s<br><span>Heather %s shirt &middot; <a href="%s_print.png" download>print file</a> '
            '(12 &times; 11.3 in, 300 dpi)</span></figcaption>\n</figure>' % (TEE, heathered(color), TEE, label, label, town, zone,
                                                                            label, town, zone, name, label))
    page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Upper Charles Forest T-shirts (draft)</title>
<style>
  body { margin: 0; font: 16px/1.45 -apple-system, "Segoe UI", Roboto, sans-serif; color: #263238; background: #f5f3ef; }
  main { max-width: 1100px; margin: 0 auto; padding: 24px 18px 48px; }
  h1 { font-size: 26px; margin: 0 0 6px; }
  p.lead { margin: 0 0 22px; color: #546e7a; max-width: 760px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 26px; }
  .card { margin: 0; background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.12); }
  .tee { position: relative; }
  .tee svg { display: block; width: 100%%; height: auto; }
  .tee img { position: absolute; left: 28%%; top: 27%%; width: 44%%; filter: drop-shadow(0 1px 1px rgba(0,0,0,0.25)); }
  figcaption { margin-top: 10px; font-size: 15px; }
  figcaption span { color: #607d8b; font-size: 13px; }
  .note { margin-top: 30px; font-size: 13px; color: #78909c; max-width: 760px; }
</style>
</head>
<body>
<main>
<h1>Upper Charles Forest T-shirts</h1>
<p class="lead">A draft: one shirt for each of the forest's six zones, in the zone's color, printed with one of its
trail-intersection signs as it will look on the trail. Each card links to the full-size print file.</p>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <!-- heather: fine light and dark flecks over the shirt's color, kept inside the shirt -->
  <filter id="heather" x="0" y="0" width="100%%" height="100%%">
    <feTurbulence type="fractalNoise" baseFrequency="2.2 1.1" numOctaves="1" seed="7" result="noise"/>
    <feColorMatrix in="noise" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.9 -0.48" result="light"/>
    <feColorMatrix in="noise" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -0.8 0.36" result="dark"/>
    <feMerge result="flecks"><feMergeNode in="dark"/><feMergeNode in="light"/></feMerge>
    <feComposite in="flecks" in2="SourceGraphic" operator="in"/>
  </filter>
</defs></svg>
<div class="grid">
%s
</div>
<p class="note">Drafts for discussion. The town seals and NEMBA's logo belong to them, and
are shown here only to preview the design; they won't be printed without their owners' permission. Sign numbers
can still change until the signs are installed.</p>
</main>
</body>
</html>
""" % "\n".join(cards)
    with open(os.path.join(SHIRTS, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print("Wrote %s" % os.path.join(SHIRTS, "index.html"))


def main():
    sheet = []
    for label, town, zone, logos in SIGNS:
        p = os.path.join(OUT, label + ".png")
        W, H, missing = draw(label, town, zone, logos, p)
        sheet.append(Image.open(p))
        print("Wrote %s (%d x %d px, %.0f x %.1f in at 300 dpi)%s" % (
            p, W, H, W / 300, H / 300, "; still without " + ", ".join(missing) if missing else ""))
    # a sheet of all six, to look over
    tw = 600
    th = round(tw * RATIO)
    out = Image.new("RGB", (3 * tw + 4 * 20, 2 * th + 3 * 20), "white")
    for i, im in enumerate(sheet):
        small = im.resize((tw, th), Image.LANCZOS)
        out.paste(small, (20 + (i % 3) * (tw + 20), 20 + (i // 3) * (th + 20)), small)
    out.save(os.path.join(OUT, "all_six.png"))
    print("Wrote %s" % os.path.join(OUT, "all_six.png"))
    write_page()
    write_samples()


if __name__ == "__main__":
    main()
