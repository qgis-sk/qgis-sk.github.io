#!/usr/bin/env python3
"""Náhľadový obrázok pre sociálne siete (og:image, 1200×630): výzva + mapa Slovenska s organizáciami.

  python3 scripts/og_image.py <Cairo.ttf> <logo.png>

Cairo.ttf: variabilný font z github.com/google/fonts (ofl/cairo). logo.png: images/qgis-logo_SK_color.svg
vyrenderované napr. `qlmanage -t -s 600 -o . images/qgis-logo_SK_color.svg`. Výstup: images/og-vyzva.jpg
"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FONT, LOGO = sys.argv[1], sys.argv[2]
S = 2; W, H = 1200 * S, 630 * S
PAPER, INK, INK2, MUTED = (255, 255, 255), (28, 27, 27), (74, 74, 72), (122, 122, 118)
GREEN, GREEN_DK, SOFT, ORANGE = (88, 150, 50), (63, 111, 35), (232, 241, 223), (238, 121, 19)

def font(size, weight):
    f = ImageFont.truetype(FONT, size * S)
    f.set_variation_by_axes([weight, 0])
    return f

img = Image.new("RGB", (W, H), PAPER)
d = ImageDraw.Draw(img, "RGBA")

# ---- mapa: pravá časť ----
kraje = json.load(open(os.path.join(ROOT, "data", "sk-kraje.json"), encoding="utf-8"))
orgs = json.load(open(os.path.join(ROOT, "data", "organizacie.json"), encoding="utf-8"))["organizacie"]
cos = math.cos(math.radians(48.7))
rings = []
for f in kraje["features"]:
    g = f["geometry"]
    for poly in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]):
        rings.append(poly[0])
xs = [p[0] * cos for r in rings for p in r]; ys = [-p[1] for r in rings for p in r]
bx, by, bw, bh = 500 * S, 150 * S, 660 * S, 380 * S          # rámec mapy
sc = min(bw / (max(xs) - min(xs)), bh / (max(ys) - min(ys)))
ox = bx + (bw - (max(xs) - min(xs)) * sc) / 2; oy = by + (bh - (max(ys) - min(ys)) * sc) / 2
proj = lambda lon, lat: (ox + (lon * cos - min(xs)) * sc, oy + (-lat - min(ys)) * sc)
for r in rings:
    d.polygon([proj(*p) for p in r], fill=SOFT)
for r in rings:
    d.line([proj(*p) for p in r] + [proj(*r[0])], fill=PAPER, width=3 * S, joint="curve")
for o in sorted(orgs, key=lambda o: o["typ"] == "firma"):
    x, y = proj(o["lon"], o["lat"]); c = ORANGE if o["typ"] == "firma" else GREEN
    d.ellipse([x - 15 * S, y - 15 * S, x + 15 * S, y + 15 * S], fill=c + (40,))
    d.ellipse([x - 7 * S, y - 7 * S, x + 7 * S, y + 7 * S], fill=c, outline=PAPER, width=2 * S)

# ---- logo + názov ----
logo = Image.open(LOGO).convert("RGBA"); logo = logo.crop(logo.getbbox())
lh = 72 * S; logo = logo.resize((int(logo.width * lh / logo.height), lh), Image.LANCZOS)
img.paste(logo, (64 * S, 52 * S), logo)
d.text((64 * S + logo.width + 18 * S, 52 * S + lh / 2), "QGIS Slovensko", font=font(30, 700), fill=INK, anchor="lm")

# ---- text ----
d.text((64 * S, 166 * S), "KOMUNITNÁ VÝZVA", font=font(19, 700), fill=GREEN, anchor="ls", spacing=0)
y = 178 * S
for line, col in (("Zaplníme mapu", INK), ("Slovenska", INK), ("používateľmi", INK), ("QGIS?", GREEN)):
    d.text((62 * S, y), line, font=font(62, 700), fill=col); y += 68 * S
d.text((64 * S, 474 * S), "Pridajte sa, zaberie to minútu.", font=font(25, 400), fill=INK2)
# tlačidlo s adresou
t = "qgis.sk"; f = font(27, 700); tw = d.textlength(t, font=f)
d.rounded_rectangle([64 * S, 536 * S, 64 * S + tw + 56 * S, 536 * S + 52 * S], radius=26 * S, fill=GREEN)
d.text((64 * S + 28 * S, 536 * S + 26 * S), t, font=f, fill=PAPER, anchor="lm")
d.text((W - 64 * S, 590 * S), "zelená: inštitúcie, školy, samosprávy  ·  oranžová: firmy", font=font(17, 400), fill=MUTED, anchor="rs")

out = os.path.join(ROOT, "images", "og-vyzva.jpg")
img.resize((1200, 630), Image.LANCZOS).save(out, "JPEG", quality=88, optimize=True)
print(out, os.path.getsize(out) // 1024, "kB")
