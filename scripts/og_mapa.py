#!/usr/bin/env python3
"""Náhľadový obrázok pre sociálne siete (og:image, 1200×630) s novou komunitnou mapou.

  python3 scripts/og_mapa.py <Cairo.ttf> <logo.png> [--bez-vyrocia]

Podklad scripts/podklady/og-mapa.jpg (2400×1260) je záber komunitnej mapy zo stránky: rovnaký štýl
ako js/mapa.js, bez popisov sídiel a bez zhlukovania, kamera center [19.62, 49.2], zoom 6.76,
náklon 50°, otočenie −5°. Keď pribudnú organizácie, záber treba spraviť nanovo.
Cairo.ttf: variabilný font z github.com/google/fonts (ofl/cairo). logo.png: images/qgis-logo_SK_color.svg
vyrenderované napr. `qlmanage -t -s 600 -o . images/qgis-logo_SK_color.svg`.
Výstup: images/og-mapa-6-rokov.jpg, s --bez-vyrocia images/og-mapa.jpg (výzva bez výročia).
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FONT, LOGO = sys.argv[1], sys.argv[2]
VYROCIE = "--bez-vyrocia" not in sys.argv
S = 2; W, H = 1200 * S, 630 * S
WHITE, LEMON, GREEN, TEXT, MUTED = (255, 255, 255), (240, 230, 74), (88, 150, 50), (221, 231, 216), (159, 176, 154)
DARK = (14, 24, 17)
ORANGE = (238, 121, 19)

def font(size, weight):
    f = ImageFont.truetype(FONT, int(size * S))
    f.set_variation_by_axes([weight, 0])
    return f

img = Image.open(os.path.join(ROOT, "scripts", "podklady", "og-mapa.jpg")).convert("RGB").resize((W, H), Image.LANCZOS)

# stmavenie hore (pod text) a jemne dole (pod adresu), aby bol text čitateľný na reliéfe
tien = Image.new("L", (1, H), 0)
for y in range(H):
    hore = max(0.0, 1 - y / (300 * S)) ** 1.5 * 0.86
    dole = max(0.0, (y - (H - 150 * S)) / (150 * S)) ** 1.6 * 0.7
    tien.putpixel((0, y), int(255 * min(1, hore + dole)))
img.paste(Image.new("RGB", (W, H), DARK), (0, 0), tien.resize((W, H)))
d = ImageDraw.Draw(img, "RGBA")

# ---- logo na bielom štítku + názov ----
logo = Image.open(LOGO).convert("RGB")
maska = logo.convert("L").point(lambda v: 255 if v < 250 else 0)
logo = logo.crop(maska.getbbox())
lh = 46 * S; logo = logo.resize((int(logo.width * lh / logo.height), lh), Image.LANCZOS)
px, py = 18 * S, 13 * S
x0, y0 = 60 * S, 44 * S
d.rounded_rectangle([x0, y0, x0 + logo.width + 2 * px, y0 + lh + 2 * py], radius=16 * S, fill=WHITE)
img.paste(logo, (x0 + px, y0 + py))
stred = y0 + (lh + 2 * py) / 2
d.text((x0 + logo.width + 2 * px + 20 * S, stred), "QGIS Slovensko", font=font(31, 700), fill=WHITE, anchor="lm")

if VYROCIE:
    # dátumy výročia vpravo hore
    t = "18. 11. 2020 – 18. 11. 2026"; f = font(21, 700); tw = d.textlength(t, font=f)
    d.rounded_rectangle([W - 60 * S - tw - 44 * S, stred - 24 * S, W - 60 * S, stred + 24 * S], radius=24 * S,
                        fill=(12, 22, 16, 190), outline=LEMON + (200,), width=int(1.5 * S))
    d.text((W - 60 * S - 22 * S, stred), t, font=f, fill=LEMON, anchor="rm")
    # nadpis: „6 rokov“ citrónovou, zvyšok bielou
    f = font(57, 700); x, y = 60 * S, 150 * S
    d.text((x, y), "6 rokov", font=f, fill=LEMON); x += d.textlength("6 rokov ", font=f)
    d.text((x, y), "komunity QGIS na Slovensku", font=f, fill=WHITE)
    d.text((62 * S, 236 * S), "Zaplníme spolu mapu Slovenska? Pridajte sa.", font=font(27, 500), fill=TEXT)
else:
    f = font(57, 700)
    d.text((60 * S, 150 * S), "Zaplníme mapu Slovenska?", font=f, fill=WHITE)
    d.text((62 * S, 236 * S), "Komunita používateľov QGIS. Pridajte sa, zaberie to minútu.", font=font(27, 500), fill=TEXT)

# ---- adresa vpravo dole, zdroj podkladu vľavo dole ----
t = "qgis.sk"; f = font(30, 700); tw = d.textlength(t, font=f)
bx1, by1 = W - 60 * S, H - 44 * S
d.rounded_rectangle([bx1 - tw - 64 * S, by1 - 58 * S, bx1, by1], radius=29 * S, fill=GREEN)
d.text((bx1 - 32 * S, by1 - 29 * S), t, font=f, fill=WHITE, anchor="rm")
if VYROCIE:
    # nálepka „Nový web“ pri adrese: oranžová, mierne pootočená, s bielym okrajom
    t2 = "NOVÝ WEB"; f2 = font(21, 700); w2 = int(d.textlength(t2, font=f2) + 44 * S); h2 = 44 * S; ok = 3 * S
    nal = Image.new("RGBA", (w2 + 2 * ok, h2 + 2 * ok), (0, 0, 0, 0)); dn = ImageDraw.Draw(nal)
    dn.rounded_rectangle([0, 0, nal.width - 1, nal.height - 1], radius=nal.height // 2, fill=WHITE)
    dn.rounded_rectangle([ok, ok, ok + w2, ok + h2], radius=h2 // 2, fill=ORANGE)
    dn.text((nal.width / 2, nal.height / 2), t2, font=f2, fill=WHITE, anchor="mm")
    nal = nal.rotate(7, resample=Image.BICUBIC, expand=True)
    img.paste(nal, (int(bx1 - tw - 64 * S - nal.width * 0.62), int(by1 - 58 * S - nal.height * 0.62)), nal)
d.text((60 * S, H - 40 * S), "body: organizácie, ktoré pracujú s QGIS  ·  podklad © OpenStreetMap, OpenFreeMap, AWS Terrain Tiles",
       font=font(15, 500), fill=MUTED, anchor="ls")

out = os.path.join(ROOT, "images", "og-mapa-6-rokov.jpg" if VYROCIE else "og-mapa.jpg")
img.resize((1200, 630), Image.LANCZOS).save(out, "JPEG", quality=88, optimize=True)
print(out, os.path.getsize(out) // 1024, "kB")
