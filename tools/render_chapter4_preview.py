
#!/usr/bin/env python3
"""Offline preview for Chapter 4 places, map sheets, and residents. No Xcode."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "Postman/GameAssets"
OUT = Path("/tmp/ch4_preview")
OUT.mkdir(parents=True, exist_ok=True)

PLACES = [
    ("shlagbaum", "01 Шлагбаум"),
    ("otstoyniki", "02 Отстойники"),
    ("truby", "03 Трубы"),
    ("shlam", "04 Шлам"),
    ("kotelnaya", "05 Котельная"),
    ("sarai", "06 Сараи"),
    ("naberezhnaya", "07 Набережная"),
    ("dvory", "08 Дворы"),
    ("otdelenie", "09 Отделение"),
    ("verkhnyaya", "10 Верхняя"),
]

def fit(im, w, h, bg=(20, 18, 16)):
    canvas = Image.new("RGB", (w, h), bg)
    im = im.convert("RGBA")
    scale = min(w / im.width, h / im.height)
    nw, nh = max(1, int(im.width * scale)), max(1, int(im.height * scale))
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas.paste(im, ((w - nw) // 2, (h - nh) // 2), im)
    return canvas

def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, im.height - 36, im.width, im.height), fill=(0, 0, 0, 180))
    d.text((8, im.height - 30), text, fill=(240, 230, 210))
    return im

# Places strip
thumbs = []
for key, title in PLACES:
    p = ASSETS / "Chapter4/places" / f"place_{key}_main.png"
    if not p.exists():
        # maybe different names
        alt = list((ASSETS / "Chapter4/places").glob(f"*{key}*"))
        p = alt[0] if alt else p
    if not p.exists():
        im = Image.new("RGB", (200, 280), (40, 30, 30))
        ImageDraw.Draw(im).text((10, 120), f"MISSING {key}", fill=(200, 80, 80))
    else:
        im = Image.open(p)
        im = fit(im, 200, 280)
    thumbs.append(label(im, title))
gap = 8
strip = Image.new("RGB", (len(thumbs) * 200 + (len(thumbs) - 1) * gap + 16, 300), (12, 11, 10))
x = 8
for im in thumbs:
    strip.paste(im, (x, 10))
    x += 200 + gap
strip.save(OUT / "places_strip.jpg", quality=85)
print("places_strip", strip.size, "->", OUT / "places_strip.jpg")

# Map sheets
maps = []
for name, title in (("stvor_color.jpg", "stvor color"), ("stvor_pencil.jpg", "stvor pencil"),
                    ("stvor_field.png", "stvor field")):
    p = ASSETS / "UI/map" / name
    im = Image.open(p) if p.exists() else Image.new("RGB", (117, 253), (30, 30, 30))
    maps.append(label(fit(im, 180, 390), title))
row = Image.new("RGB", (len(maps) * 180 + (len(maps) - 1) * gap + 16, 410), (12, 11, 10))
x = 8
for im in maps:
    row.paste(im, (x, 10))
    x += 180 + gap
row.save(OUT / "map_sheets.jpg", quality=85)
print("map_sheets", row.size)

# Residents + ambient
chars = []
res_dir = ASSETS / "Chapter4/residents"
for sub in sorted(res_dir.glob("*/full.png")) if res_dir.exists() else []:
    im = Image.open(sub)
    chars.append(label(fit(im, 160, 320, (30, 28, 24)), sub.parent.name))
amb = ASSETS / "Chapter4/ambient"
if amb.exists():
    for sub in sorted(amb.rglob("*.png")):
        im = Image.open(sub)
        chars.append(label(fit(im, 160, 320, (30, 28, 24)), sub.stem))
if chars:
    row = Image.new("RGB", (len(chars) * 160 + (len(chars) - 1) * gap + 16, 340), (12, 11, 10))
    x = 8
    for im in chars:
        row.paste(im, (x, 10))
        x += 160 + gap
    row.save(OUT / "characters.jpg", quality=85)
    print("characters", row.size, "n=", len(chars))

print("preview ok", OUT)
