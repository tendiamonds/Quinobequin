"""
Make the site icons: a tiny trail sign (white "A7" on the sign brown). A7 is the
network's busiest junction.
  favicon.svg          — modern browsers
  favicon.ico          — older browsers (16, 32, 48 px)
  apple-touch-icon.png — iPhone/iPad home screen (180 px, square; iOS rounds the corners)
  icon-192.png, icon-512.png                   — app icons, rounded square as is
  icon-maskable-192.png, icon-maskable-512.png — Android home screen; full bleed, and the
      letters fit the safe zone (a centered circle 80% across) so any crop shape works
  manifest.webmanifest — names the icons and opens the map like an app
"""

import json
from PIL import Image, ImageDraw, ImageFont

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"
BROWN = "#7a3122"   # same as the signs
NAVY = "#2c3e50"    # the site's top bar
FONT = r"C:\Windows\Fonts\arialbd.ttf"
LABEL = "A7"

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect x="2" y="2" width="60" height="60" rx="14" fill="{BROWN}"/>
<text x="32" y="47" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-weight="700" font-size="40" fill="#fff" letter-spacing="-1">{LABEL}</text>
</svg>
"""

MANIFEST = {
    "name": "Upper Charles Forest",
    "short_name": "Upper Charles",
    "start_url": "map.html",
    "scope": "./",
    "display": "standalone",
    "background_color": "#ffffff",
    "theme_color": NAVY,
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "icon-maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
        {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}


def draw_icon(size, shape, ink_width):
    """Draw at 4x and scale down, for smooth edges.
    shape: "rounded" (inset rounded square) or "square" (full bleed).
    ink_width: width of the letters as a fraction of the icon."""
    big = size * 4
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if shape == "rounded":
        inset = big * 2 // 64
        d.rounded_rectangle([inset, inset, big - inset, big - inset], radius=big * 14 // 64, fill=BROWN)
    else:
        d.rectangle([0, 0, big, big], fill=BROWN)
    # Size the font so the letters' ink is the requested width
    probe = ImageFont.truetype(FONT, 100)
    l, t, r, b = d.textbbox((0, 0), LABEL, font=probe)
    font = ImageFont.truetype(FONT, round(100 * ink_width * big / (r - l)))
    # Center the ink of the text, not its line box
    l, t, r, b = d.textbbox((0, 0), LABEL, font=font)
    d.text(((big - (r - l)) / 2 - l, (big - (b - t)) / 2 - t), LABEL, font=font, fill="white")
    return im.resize((size, size), Image.LANCZOS), ((r - l) / big, (b - t) / big)


with open(rf"{PROJ}\favicon.svg", "w", encoding="utf-8") as f:
    f.write(SVG)
draw_icon(48, "rounded", 0.72)[0].save(rf"{PROJ}\favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
draw_icon(180, "square", 0.68)[0].convert("RGB").save(rf"{PROJ}\apple-touch-icon.png")
for px in (192, 512):
    draw_icon(px, "rounded", 0.68)[0].save(rf"{PROJ}\icon-{px}.png")
    im, (w, h) = draw_icon(px, "square", 0.64)
    # The letters' corners must stay inside the safe circle
    assert (w * w + h * h) ** 0.5 <= 0.8, (w, h)
    im.convert("RGB").save(rf"{PROJ}\icon-maskable-{px}.png")
with open(rf"{PROJ}\manifest.webmanifest", "w", encoding="utf-8") as f:
    json.dump(MANIFEST, f, indent=2)
    f.write("\n")
print("Wrote favicon.svg, favicon.ico, apple-touch-icon.png, icon-*.png, manifest.webmanifest")
