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
SCROLL_TOP = 400
SCROLL_H = 1080
BAG_RING = (400, 1560)
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
        scroll_layer, box = paste(scroll_layer, sprite, hole, (585, y + 90), angle=-2 if on_left else 2)
        boxes.append((title, box))
        y += 180
        pairs = [(None, None)] if not items else [
            (items[i], items[i + 1] if i + 1 < len(items) else None) for i in range(0, len(items), 2)
        ]
        for left, right in pairs:
            shelf_y = y + 8
            base_y = shelf_y + 22
            tag_y = shelf_y + 108
            image, entry = load_art("shelf")
            scroll_layer, box = paste(scroll_layer, image, (0, 0), (2, shelf_y), 0.82)
            boxes.append(("shelf", box))
            slots = [(left, 290, 175, -4)]
            if items:
                slots.append((right, 890, 790, 3))
            for item, cx, tx, angle in slots:
                if item is None and not items:
                    sprite, hole, tsize = tag_image(empty, "", 0.9)
                    scroll_layer, box = paste(scroll_layer, sprite, hole, (tx, tag_y), angle=angle)
                    boxes.append(("empty", box))
                    continue
                if item is None:
                    continue
                image, entry = load_art(item["art"])
                anchor = body_anchor(entry, "bottom")
                scale = min(0.82, 200 / entry["height"])
                scroll_layer, box = paste(scroll_layer, image, anchor, (cx, base_y), scale, angle * 0.4)
                boxes.append((item["id"], box))
                sprite, hole, tsize = tag_image(item["line1"], item["line2"], 0.9)
                at = (tx, tag_y)
                scroll_layer, box = paste(scroll_layer, sprite, hole, at, angle=angle)
                boxes.append((item["id"] + " tag", box))
                nail, nentry = load_art("nail")
                scroll_layer, _ = paste(scroll_layer, nail, body_anchor(nentry, "center"), at, 0.85)
                if tsize < 15:
                    notes.append(f"{item['id']} text {tsize:.0f}px: {item['line2']}")
            y += 310
    if y > SCROLL_TOP + SCROLL_H + 8 and scroll == 0:
        hint, entry = load_art("tag_small")
        draw = ImageDraw.Draw(hint)
        face = font("YesevaOne.ttf", 32)
        ytext = (entry["anchors"]["line1"][1] + entry["anchors"]["line2"][1]) / 2
        draw.text((entry["anchors"]["line1"][0], ytext), copy["bag.more"], font=face, fill=(69, 46, 28, 255), anchor="mm")
        scroll_layer, _ = paste(scroll_layer, hint, tuple(entry["anchors"]["hole"]), (585, SCROLL_TOP + SCROLL_H - 40), 0.72)
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
    base = bag_badge(base, copy, len(mail), len(personal))
    # пересечение сумки и стрелки
    if overlaps(bag_box, arrow_box, 8):
        notes.append(f"bag overlaps close arrow {bag_box} {arrow_box}")
    return base, notes


def ru_plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def bag_badge(base, copy, mail, things):
    """На дорожной сумке только почта. Находки — своим словом, и только если писем нет."""
    russian = "Почта" in copy.get("bag.mail", "")
    if mail > 0:
        count, word = mail, (ru_plural(mail, "письмо", "письма", "писем") if russian else ("letter" if mail == 1 else "letters"))
    elif things > 0:
        count, word = things, (ru_plural(things, "вещь", "вещи", "вещей") if russian else ("thing" if things == 1 else "things"))
    else:
        count, word = 0, ("писем" if russian else "letters")
    badge, entry = load_art("tag_small")
    draw = ImageDraw.Draw(badge)
    draw.text(tuple(entry["anchors"]["line1"]), str(count), font=font("YesevaOne.ttf", 42), fill=(69, 46, 28, 255), anchor="mm")
    draw.text(tuple(entry["anchors"]["line2"]), word, font=font("Kurale.ttf", 28), fill=(69, 46, 28, 255), anchor="mm")
    base, _ = paste(base, badge, tuple(entry["anchors"]["hole"]), (190, 2280), 0.7, 8)
    return base


def overlaps(a, b, pad=0):
    return not (a[2] < b[0] + pad or b[2] < a[0] + pad or a[3] < b[1] + pad or b[3] < a[1] + pad)


def dim(image):
    veil = Image.new("RGBA", image.size, (8, 23, 26, int(255 * 0.66)))
    return Image.alpha_composite(image, veil)


def earth_color(image):
    px = image.load()
    width, height = image.size
    for y in range(height - 1, int(height * 0.45), -4):
        colors = [px[x, y][:3] for x in range(0, width, 12) if px[x, y][3] > 210]
        if len(colors) > width / 24:
            return tuple(sum(c[i] for c in colors) // len(colors) for i in range(3))
    return (150, 124, 92)


def fit_width(image, width):
    height = max(1, int(image.height * width / image.width))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def scatter(canvas, folder, names, spots):
    ready = [folder / name for name in names if (folder / name).exists()]
    for index, (x, foot) in enumerate(spots):
        if not ready:
            return
        prop = Image.open(ready[index % len(ready)]).convert("RGBA")
        prop.thumbnail((240, 240), Image.Resampling.LANCZOS)
        canvas.paste(prop, (x, foot - prop.height), prop)


def location_backdrop(chapter):
    places = ROOT / f"Postman/GameAssets/Chapter{chapter}/places"
    foreground = ROOT / f"Postman/GameAssets/Chapter{chapter}/foreground"
    fields = Image.open(places / "bg_mid_fields_tile.png").convert("RGBA")
    ridges = Image.open(places / "bg_far_ridges_tile.png").convert("RGBA")
    canvas = Image.new("RGBA", (W, H), earth_color(fields) + (255,))
    ridges_s = fit_width(ridges, W + 60)
    canvas.paste(ridges_s, (-30, 0), ridges_s)
    # Сам холст локации доходит до низа кадра: низ картинки — земля под сумкой.
    fields_h = H - 280
    fields_s = fields.resize((max(W, int(fields.width * fields_h / fields.height)), fields_h), Image.Resampling.LANCZOS)
    if fields_s.width > W:
        left = (fields_s.width - W) // 2
        fields_s = fields_s.crop((left, 0, left + W, fields_h))
    canvas.paste(fields_s, (0, 280), fields_s)
    place_name = "place_pochta_main.png" if chapter == 1 else "place_penki_main.png"
    place = Image.open(places / place_name).convert("RGBA")
    ph = 860
    place = place.resize((int(place.width * ph / place.height), ph), Image.Resampling.LANCZOS)
    canvas.paste(place, ((W - place.width) // 2, 240), place)
    if chapter == 1:
        names = ["fg_grass_a.png", "fg_grass_b.png", "fg_fern.png", "fg_dill.png"]
    else:
        names = ["fg_fern_needles.png", "fg_fir_paw.png", "fg_boulder.png", "fg_reeds.png"]
    scatter(canvas, foreground, names, [
        (20, 1680), (980, 1740), (70, 2140), (860, 2200), (1040, 2420), (180, 2460), (620, 2480),
    ])
    watch, _ = load_art_path(ROOT / "Postman/GameAssets/UI/watch_collapsed.png", (311, 645))
    canvas.paste(watch, (507, 0), watch)
    return dim(canvas)


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
        base = location_backdrop(1)
        frame, notes = draw_ui(base, mail1, personal1, copy, scroll=0)
        label = "OFFLINE composite, not a simulator frame" if code == "en" else "ОФЛАЙН-склейка, не кадр симулятора"
        save(banner(frame, label), f"bag_ch1_{code}.jpg", notes)
        frame, notes = draw_ui(location_backdrop(1), mail1, personal1, copy, scroll=1100)
        save(banner(frame, label + " · scroll"), f"bag_ch1_{code}_scroll.jpg", notes)

        mail2 = [item(ch2, code, copy, 2, i) for i in ("l3", "l4", "l5", "l6", "l7", "l8", "note_gar", "l9")]
        personal2 = [item(ch2, code, copy, 2, i) for i in ("animal_raven_scrap", "animal_dog_horn")]
        frame, notes = draw_ui(location_backdrop(2), mail2, personal2, copy, scroll=0)
        save(banner(frame, label), f"bag_ch2_{code}.jpg", notes)
        frame, notes = draw_ui(location_backdrop(2), mail2, personal2, copy, scroll=1160)
        save(banner(frame, label + " · scroll"), f"bag_ch2_{code}_scroll.jpg", notes)

    # Середина главы 2 у Пеньков: записка и две находки, без чужих бланков.
    copy = strings("ru")
    mail = [item(ch2, "ru", copy, 2, "note_gar")]
    personal = [item(ch2, "ru", copy, 2, i) for i in ("animal_raven_scrap", "animal_dog_horn")]
    frame, notes = draw_ui(location_backdrop(2), mail, personal, copy, scroll=0)
    save(banner(frame, "ОФЛАЙН-склейка, не кадр симулятора · Пеньки"), "bag_ch2_penki_ru.jpg", notes)
    frame, notes = draw_ui(location_backdrop(2), mail, personal, copy, scroll=640)
    save(banner(frame, "ОФЛАЙН-склейка, не кадр симулятора · Пеньки, прокрутка"), "bag_ch2_penki_ru_scroll.jpg", notes)
    copy = strings("en")
    mail = [item(ch2, "en", copy, 2, "note_gar")]
    personal = [item(ch2, "en", copy, 2, i) for i in ("animal_raven_scrap", "animal_dog_horn")]
    frame, notes = draw_ui(location_backdrop(2), mail, personal, copy, scroll=0)
    save(banner(frame, "OFFLINE composite, not a simulator frame · Stumps"), "bag_ch2_penki_en.jpg", notes)


def journal_card(code):
    """Карточка сдачи почты: конверт вместо пустой рамки, без «0 ш.»."""
    copy = strings(code)
    sheet, entry = load_art("sheet")
    scale = 900 / entry["width"]
    paper = sheet.resize((int(entry["width"] * scale), int(entry["height"] * scale)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (24, 64, 68, 255))
    canvas.paste(paper, ((W - paper.width) // 2, 280), paper)
    env, eentry = load_art("env_plain")
    env.thumbnail((280, 220), Image.Resampling.LANCZOS)
    canvas.paste(env, ((W - env.width) // 2, 520), env)
    draw = ImageDraw.Draw(canvas)
    draw.text((220, 820), copy["bag.handoff.title"], font=font("Kurale.ttf", 36), fill=(69, 46, 28, 255))
    body = copy["bag.handoff.s_nii_drop"]
    y = 900
    face = font("Kurale.ttf", 34)
    words = body.split()
    line = ""
    for word in words:
        trial = word if not line else line + " " + word
        if draw.textlength(trial, font=face) > 720:
            draw.text((220, y), line, font=face, fill=(70, 62, 54, 255))
            y += 46
            line = word
        else:
            line = trial
    if line:
        draw.text((220, y), line, font=face, fill=(70, 62, 54, 255))
    label = "OFFLINE composite, not a simulator frame" if code == "en" else "ОФЛАЙН-склейка, не кадр симулятора"
    save(banner(canvas, label + " · journal"), f"journal_handoff_{code}.jpg", [])


if __name__ == "__main__":
    main()
    journal_card("ru")
    journal_card("en")
