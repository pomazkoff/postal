#!/usr/bin/env python3
"""Офлайн-кадр сумки в координатах макета 1170×2532.

Повторяет полки, бирки и сумку из BagScreen.swift. Это не кадр симулятора.
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "Postman/GameAssets/UI/ch1"
FONT = ROOT / "Postman/GameAssets/Fonts"
OUT = Path("/opt/cursor/artifacts/bag-screen")
W, H = 1170, 2532

# Совпадает с BagScreen.swift
SCROLL_TOP = 390
SCROLL_H = 960
BAG_RING = (400, 1415)
TITLE = (585, 210)
ARROW_RIGHT, ARROW_BOTTOM = 1136, 2470

art = json.loads((ROOT / "Postman/GameAssets/UI/ui_ch1.json").read_text())["art"]


def font(name, size):
    return ImageFont.truetype(str(FONT / name), max(8, int(size)))


def strings(code):
    text = (ROOT / f"Postman/Resources/{code}.lproj/Localizable.strings").read_text(encoding="utf-8")
    import re
    return {k: v for k, v in re.findall(r'"((?:\\.|[^"\\])*)"\s*=\s*"((?:\\.|[^"\\])*)"\s*;', text)}


def load_art(name):
    entry = art[name]
    image = Image.open(ROOT / "Postman/GameAssets" / f"{entry['image']}.png").convert("RGBA")
    if image.size != (entry["width"], entry["height"]):
        image = image.resize((entry["width"], entry["height"]), Image.Resampling.LANCZOS)
    return image, entry


def body_anchor(entry, key):
    if key == "origin":
        return (0, 0)
    if key == "center":
        b = entry["anchors"]["body"]
        return (b[0] + b[2] / 2, b[1] + b[3] / 2)
    if key == "bottom":
        b = entry["anchors"]["body"]
        return (b[0] + b[2] / 2, b[1] + b[3])
    if key == "hole":
        h = entry["anchors"]["hole"]
        return (h[0], h[1])
    if key == "ring":
        r = entry["anchors"]["ring"]
        return (r[0], r[1])
    return (entry["width"] / 2, entry["height"] / 2)


def paste(base, sprite, anchor, at, scale=1, angle=0):
    if scale != 1:
        sprite = sprite.resize((max(1, int(sprite.width * scale)), max(1, int(sprite.height * scale))), Image.Resampling.LANCZOS)
        anchor = (anchor[0] * scale, anchor[1] * scale)
    if abs(angle) > 0.2:
        rad = math.radians(angle)
        cx, cy = sprite.width / 2, sprite.height / 2
        dx, dy = anchor[0] - cx, anchor[1] - cy
        rot = sprite.rotate(-angle, expand=True, resample=Image.Resampling.BICUBIC)
        rdx = dx * math.cos(rad) + dy * math.sin(rad)
        rdy = -dx * math.sin(rad) + dy * math.cos(rad)
        anchor = (rot.width / 2 + rdx, rot.height / 2 + rdy)
        sprite = rot
    x = int(round(at[0] - anchor[0]))
    y = int(round(at[1] - anchor[1]))
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.paste(sprite, (x, y), sprite)
    return Image.alpha_composite(base, layer), (x, y, x + sprite.width, y + sprite.height)


def fit(draw, text, face_name, width, size, minimum):
    while size > minimum and draw.textlength(text, font=font(face_name, size)) > width:
        size -= 1
    return font(face_name, size), size


def wrap(draw, text, face_name, width, size):
    words = text.split()
    if not words:
        return [""], size
    face = font(face_name, size)
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if draw.textlength(trial, font=face) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > 2 and size > 14:
        return wrap(draw, text, face_name, width, size - 1)
    return lines[:2], size


def tag_image(line1, line2, scale=0.9):
    image, entry = load_art("tag")
    image = image.resize((int(entry["width"] * scale), int(entry["height"] * scale)), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    w = entry["anchors"]["textWidth"][0] * scale
    l1 = entry["anchors"]["line1"]
    l2 = entry["anchors"]["line2"]
    face1, s1 = fit(draw, line1, "YesevaOne.ttf", w, 42 * scale, 16 * scale)
    draw.text((l1[0] * scale, l1[1] * scale), line1, font=face1, fill=(69, 46, 28, 255), anchor="mm")
    lines, s2 = wrap(draw, line2, "Kurale.ttf", w, 28 * scale)
    face2 = font("Kurale.ttf", s2)
    y = (l2[1] + 10) * scale - (len(lines) - 1) * s2 * 0.55
    for line in lines:
        draw.text((l2[0] * scale, y), line, font=face2, fill=(69, 46, 28, 230), anchor="mm")
        y += s2 * 1.15
    hole = (entry["anchors"]["hole"][0] * scale, entry["anchors"]["hole"][1] * scale)
    return image, hole, min(s1, s2)


def section_image(title):
    """Та же бирка и тот же кегль для «Почта» и «Личные вещи», без ужатия длинной строки."""
    scale = 0.8
    image, entry = load_art("tag")
    image = image.resize((int(entry["width"] * scale), int(entry["height"] * scale)), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    w = entry["anchors"]["textWidth"][0] * scale
    y = (entry["anchors"]["line1"][1] + entry["anchors"]["line2"][1]) / 2 * scale
    size = 32 * scale
    face = font("YesevaOne.ttf", size)
    width = draw.textlength(title, font=face)
    if width > w:
        raise SystemExit(f"section title does not fit: {title!r} {width:.0f} > {w:.0f}")
    draw.text((entry["anchors"]["line1"][0] * scale, y), title, font=face, fill=(69, 46, 28, 255), anchor="mm")
    hole = (entry["anchors"]["hole"][0] * scale, entry["anchors"]["hole"][1] * scale)
    return image, hole


def draw_ui(base, mail, personal, copy, scroll=0):
    notes = []
    boxes = []

    def put(name, key, at, scale=1, angle=0):
        image, entry = load_art(name)
        anchor = body_anchor(entry, key)
        return paste(base, image, anchor, at, scale, angle)

    sprite, hole, size = tag_image(copy["bag.title"], copy["bag.withYou"], 1)
    base, box = paste(base, sprite, hole, TITLE, angle=-2)
    boxes.append(("title", box))
    if size < 18:
        notes.append(f"title text shrunk to {size:.0f}")

    scroll_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    y = SCROLL_TOP - scroll
    groups = [
        (copy["bag.mail"], mail, copy["bag.mail.empty"], True),
        (copy["bag.personal"], personal, copy["bag.personal.empty"], False),
    ]
    for title, items, empty, on_left in groups:
        sprite, hole = section_image(title)
        at = (210 if on_left else 585, y + 120)
        scroll_layer, box = paste(scroll_layer, sprite, hole, at, angle=-3 if on_left else 2)
        boxes.append((title, box))
        y += 250
        pairs = [(None, None)] if not items else [
            (items[i], items[i + 1] if i + 1 < len(items) else None) for i in range(0, len(items), 2)
        ]
        for left, right in pairs:
            image, entry = load_art("shelf")
            scroll_layer, box = paste(scroll_layer, image, (0, 0), (2, y + 36))
            boxes.append(("shelf", box))
            slots = [(left, 290, 175, -4)]
            if items:
                slots.append((right, 890, 790, 3))
            for item, cx, tx, angle in slots:
                if item is None and not items:
                    sprite, hole, tsize = tag_image(empty, "", 0.9)
                    scroll_layer, box = paste(scroll_layer, sprite, hole, (tx, y + 150), angle=angle)
                    boxes.append(("empty", box))
                    continue
                if item is None:
                    continue
                image, entry = load_art(item["art"])
                anchor = body_anchor(entry, "bottom")
                scale = min(0.82, 200 / entry["height"])
                scroll_layer, box = paste(scroll_layer, image, anchor, (cx, y + 64), scale, angle * 0.4)
                boxes.append((item["id"], box))
                sprite, hole, tsize = tag_image(item["line1"], item["line2"], 0.9)
                at = (tx, y + 150)
                scroll_layer, box = paste(scroll_layer, sprite, hole, at, angle=angle)
                boxes.append((item["id"] + " tag", box))
                nail, nentry = load_art("nail")
                scroll_layer, _ = paste(scroll_layer, nail, body_anchor(nentry, "center"), at, 0.85)
                if tsize < 15:
                    notes.append(f"{item['id']} text {tsize:.0f}px: {item['line2']}")
            y += 390
    band = scroll_layer.crop((0, SCROLL_TOP, W, SCROLL_TOP + SCROLL_H))
    base.paste(band, (0, SCROLL_TOP), band)
    # кожаная сумка без меловых имён
    back, entry = load_art("bag_back")
    ring = entry["anchors"]["ring"]
    origin = (BAG_RING[0] - ring[0] * 0.9, BAG_RING[1] - ring[1] * 0.9)
    base, bag_box = paste(base, back, (0, 0), origin, 0.9)
    front, _ = load_art("bag_front")
    base, bag_box = paste(base, front, (0, 0), origin, 0.9)
    boxes.append(("bag", bag_box))
    # стрелка
    arrow, entry = load_art("arrow")
    body = entry["anchors"]["body"]
    center = (ARROW_RIGHT - body[2] / 2, ARROW_BOTTOM - body[3] / 2)
    draw = ImageDraw.Draw(arrow)
    face, _ = fit(draw, copy["bag.close"], "YesevaOne.ttf", body[2] * 0.62, 44, 18)
    t = entry["anchors"]["text"]
    draw.text(t, copy["bag.close"], font=face, fill=(242, 234, 214, 255), anchor="mm")
    base, arrow_box = paste(base, arrow, ((body[0] + body[2] / 2), (body[1] + body[3] / 2)), center)
    boxes.append(("arrow", arrow_box))
    # пересечение сумки и стрелки
    if overlaps(bag_box, arrow_box, 8):
        notes.append(f"bag overlaps close arrow {bag_box} {arrow_box}")
    return base, notes


def overlaps(a, b, pad=0):
    return not (a[2] < b[0] + pad or b[2] < a[0] + pad or a[3] < b[1] + pad or b[3] < a[1] + pad)


def dim(image):
    veil = Image.new("RGBA", image.size, (8, 23, 26, int(255 * 0.66)))
    return Image.alpha_composite(image, veil)


def valley():
    ridges = Image.open(ROOT / "Postman/GameAssets/Chapter1/places/bg_far_ridges_tile.png").convert("RGBA")
    fields = Image.open(ROOT / "Postman/GameAssets/Chapter1/places/bg_mid_fields_tile.png").convert("RGBA")
    place = Image.open(ROOT / "Postman/GameAssets/Chapter1/places/place_pochta_main.png").convert("RGBA")
    sky = Image.new("RGBA", (W, H), (58, 110, 112, 255))
    sky.paste(ridges.resize((W, 900), Image.Resampling.LANCZOS), (0, 80), ridges.resize((W, 900), Image.Resampling.LANCZOS))
    sky.paste(fields.resize((W, 700), Image.Resampling.LANCZOS), (0, 620), fields.resize((W, 700), Image.Resampling.LANCZOS))
    ph = 980
    pw = int(place.width * ph / place.height)
    place = place.resize((pw, ph), Image.Resampling.LANCZOS)
    sky.paste(place, ((W - pw) // 2, 280), place)
    watch, _ = load_art_path(ROOT / "Postman/GameAssets/UI/watch_collapsed.png", (311, 645))
    sky.paste(watch, (507, 0), watch)
    return dim(sky)


def penki_shot():
    shot = Image.open("/home/ubuntu/.cursor/projects/agent-repos-POSTAL/assets/bag_chapter2_t410.png").convert("RGBA")
    # Кадр макета вписан в скрин почти целиком. Кладём UI в макет, потом масштабируем на скрин.
    return shot


def load_art_path(path, size):
    image = Image.open(path).convert("RGBA")
    if image.size != size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    return image, None


def banner(image, text):
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, W, 34), fill=(120, 36, 28, 255))
    draw.text((16, 4), text, font=font("Neucha.ttf", 22), fill=(255, 244, 220, 255))
    return image


def item(story, code, copy, chapter, ident):
    src = story[ident]
    if src["kind"] == "form" and ident not in ("l4", "note_gar", "l9"):
        line1 = copy[f"bag.keep.{ident}"] if f"bag.keep.{ident}" in copy else copy["bag.keep.other"]
        line2 = copy["bag.look"]
    elif ident in ("animal_cat_stamp", "animal_raven_scrap", "animal_dog_horn"):
        line1 = copy[f"bag.keep.{ident}"]
        line2 = copy["bag.look"]
    else:
        line1 = src["to"] if code == "ru" else en_to(chapter, ident, src["to"])
        line2 = copy.get(f"bag.act.{chapter}.{ident}", "")
    return {"id": ident, "art": src["art"], "line1": line1, "line2": line2}


def en_to(chapter, ident, fallback):
    en = json.loads((ROOT / "Postman/GameAssets/L10n/en.json").read_text())
    block = en["stories"][str(chapter)]["items"].get(ident, {})
    return block.get("to", fallback)


def story(chapter):
    data = json.loads((ROOT / f"Postman/GameAssets/Data/chapter{chapter}_story.json").read_text())
    return {item["id"]: item for item in data["items"]}


def save(image, name, notes):
    OUT.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(OUT / name, quality=90)
    print(name, "; ".join(notes) if notes else "no overlap notes")


def main():
    ch1, ch2 = story(1), story(2)
    for code in ("ru", "en"):
        copy = strings(code)
        mail1 = [item(ch1, code, copy, 1, i) for i in ("l3", "l4", "l5", "l6", "batteries")]
        personal1 = [item(ch1, code, copy, 1, "animal_cat_stamp")]
        base = valley()
        frame, notes = draw_ui(base, mail1, personal1, copy, scroll=0)
        label = "OFFLINE composite, not a simulator frame" if code == "en" else "ОФЛАЙН-склейка, не кадр симулятора"
        save(banner(frame, label), f"bag_ch1_{code}.jpg", notes)
        frame, notes = draw_ui(valley(), mail1, personal1, copy, scroll=1100)
        save(banner(frame, label + " · scroll"), f"bag_ch1_{code}_scroll.jpg", notes)

        mail2 = [item(ch2, code, copy, 2, i) for i in ("l3", "l4", "l5", "l6", "l7", "l8", "note_gar", "l9")]
        personal2 = [item(ch2, code, copy, 2, i) for i in ("animal_raven_scrap", "animal_dog_horn")]
        frame, notes = draw_ui(valley(), mail2, personal2, copy, scroll=0)
        save(banner(frame, label), f"bag_ch2_{code}.jpg", notes)
        frame, notes = draw_ui(valley(), mail2, personal2, copy, scroll=1160)
        save(banner(frame, label + " · scroll"), f"bag_ch2_{code}_scroll.jpg", notes)

    # Середина главы 2 у Пеньков: записка и две находки, без чужих бланков.
    copy = strings("ru")
    mail = [item(ch2, "ru", copy, 2, "note_gar")]
    personal = [item(ch2, "ru", copy, 2, i) for i in ("animal_raven_scrap", "animal_dog_horn")]
    frame, notes = draw_ui(valley(), mail, personal, copy, scroll=0)
    save(banner(frame, "ОФЛАЙН-склейка, не кадр симулятора · Пеньки"), "bag_ch2_penki_ru.jpg", notes)
    frame, notes = draw_ui(valley(), mail, personal, copy, scroll=640)
    save(banner(frame, "ОФЛАЙН-склейка, не кадр симулятора · Пеньки, прокрутка"), "bag_ch2_penki_ru_scroll.jpg", notes)


if __name__ == "__main__":
    main()
