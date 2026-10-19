"""
Make a site's icons: a tiny trail sign, white letters on a colored square. For Upper
Charles, "A7" (the network's busiest junction) on the sign brown; other regions call
make_icons with their own (build_bluehills.py).
  favicon.svg          — modern browsers
  favicon.ico          — older browsers (16, 32, 48 px)
  apple-touch-icon.png — iPhone/iPad home screen (180 px, square; iOS rounds the corners)
  icon-192.png, icon-512.png                   — app icons, rounded square as is
  icon-maskable-192.png, icon-maskable-512.png — Android home screen; full bleed, and the
      letters fit the safe zone (a centered circle 80% across) so any crop shape works
  manifest.webmanifest — names the icons and opens the map like an app
"""

import json
import os
from PIL import Image, ImageDraw, ImageFont

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"
BROWN = "#7a3122"   # same as the Upper Charles signs
NAVY = "#2c3e50"    # the sites' top bar
FONT = r"C:\Windows\Fonts\arialbd.ttf"


def draw_icon(size, shape, ink_width, label, color):
    """Draw at 4x and scale down, for smooth edges.
    shape: "rounded" (inset rounded square) or "square" (full bleed).
    ink_width: width of the letters as a fraction of the icon."""
    big = size * 4
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if shape == "rounded":
        inset = big * 2 // 64
        d.rounded_rectangle([inset, inset, big - inset, big - inset], radius=big * 14 // 64, fill=color)
    else:
        d.rectangle([0, 0, big, big], fill=color)
    # Size the font so the letters' ink is the requested width
    probe = ImageFont.truetype(FONT, 100)
    l, t, r, b = d.textbbox((0, 0), label, font=probe)
    font = ImageFont.truetype(FONT, round(100 * ink_width * big / (r - l)))
    # Center the ink of the text, not its line box
    l, t, r, b = d.textbbox((0, 0), label, font=font)
    d.text(((big - (r - l)) / 2 - l, (big - (b - t)) / 2 - t), label, font=font, fill="white")
    return im.resize((size, size), Image.LANCZOS), ((r - l) / big, (b - t) / big)


def make_icons(out_dir, label, color, name, short_name):
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect x="2" y="2" width="60" height="60" rx="14" fill="{color}"/>
<text x="32" y="47" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-weight="700" font-size="40" fill="#fff" letter-spacing="-1">{label}</text>
</svg>
"""
    manifest = {
        "name": name,
        "short_name": short_name,
        "start_url": "map.html",
        "scope": "./",
        "display": "standalone",
        # Android colors the installed app's bottom bar from background_color but draws its
        # buttons to suit theme_color, so the two match (white buttons on white otherwise)
        "background_color": NAVY,
        "theme_color": NAVY,
        "icons": [
            {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "icon-maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    path = lambda f: os.path.join(out_dir, f)
    with open(path("favicon.svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    draw_icon(48, "rounded", 0.72, label, color)[0].save(path("favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    draw_icon(180, "square", 0.68, label, color)[0].convert("RGB").save(path("apple-touch-icon.png"))
    for px in (192, 512):
        draw_icon(px, "rounded", 0.68, label, color)[0].save(path("icon-%d.png" % px))
        im, (w, h) = draw_icon(px, "square", 0.64, label, color)
        # The letters' corners must stay inside the safe circle
        assert (w * w + h * h) ** 0.5 <= 0.8, (w, h)
        im.convert("RGB").save(path("icon-maskable-%d.png" % px))
    with open(path("manifest.webmanifest"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print("Wrote icons and manifest.webmanifest in " + out_dir)


if __name__ == "__main__":
    make_icons(PROJ, label="A7", color=BROWN, name="Upper Charles Forest", short_name="Upper Charles")
