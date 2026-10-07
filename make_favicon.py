"""
Make the site icons: a tiny trail sign (white "A1" on the sign brown).
  favicon.svg          — modern browsers
  favicon.ico          — older browsers (16, 32, 48 px)
  apple-touch-icon.png — iPhone/iPad home screen (180 px, square; iOS rounds the corners)
"""

from PIL import Image, ImageDraw, ImageFont

PROJ = r"C:\Users\jbreslau\OneDrive - MathWorks\Documents\MATLAB\holliston_trails"
BROWN = "#7a3122"   # same as the signs
FONT = r"C:\Windows\Fonts\arialbd.ttf"

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect x="2" y="2" width="60" height="60" rx="14" fill="{BROWN}"/>
<text x="32" y="47" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-weight="700" font-size="40" fill="#fff" letter-spacing="-1">A1</text>
</svg>
"""


def draw_icon(size, rounded):
    """Draw at 4x and scale down, for smooth edges"""
    big = size * 4
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if rounded:
        inset = big * 2 // 64
        d.rounded_rectangle([inset, inset, big - inset, big - inset], radius=big * 14 // 64, fill=BROWN)
    else:
        d.rectangle([0, 0, big, big], fill=BROWN)
    font = ImageFont.truetype(FONT, big * 40 // 64)
    # Center the ink of the text, not its line box
    l, t, r, b = d.textbbox((0, 0), "A1", font=font)
    d.text(((big - (r - l)) / 2 - l, (big - (b - t)) / 2 - t), "A1", font=font, fill="white")
    return im.resize((size, size), Image.LANCZOS)


with open(rf"{PROJ}\favicon.svg", "w", encoding="utf-8") as f:
    f.write(SVG)
draw_icon(48, True).save(rf"{PROJ}\favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
draw_icon(180, False).convert("RGB").save(rf"{PROJ}\apple-touch-icon.png")
print("Wrote favicon.svg, favicon.ico, apple-touch-icon.png")
