#!/usr/bin/env python3
"""Целые кадры меню, дороги и истории из игровых PNG и строк.

Это не кадр симулятора и не сейв. Хроника собрана тем же фильтром, что
StoryChronicle: пройденная глава, сделанные события, одна выбранная ветка.
"""
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "Postman/GameAssets"
UI = ASSETS / "UI/ch1"
FONT_DIR = ASSETS / "Fonts"
OUT = Path("/opt/cursor/artifacts/menu-history-preview")
W, H = 1170, 2532
BROWN = (69, 46, 28, 255)
PENCIL = (59, 56, 61, 255)
CHALK = (242, 235, 214, 255)
PAPER = (232, 217, 178, 255)
EDGE = (158, 128, 84, 255)
FAILS = []


def fail(msg):
    FAILS.append(msg)


def font(name, size):
    return ImageFont.truetype(str(FONT_DIR / name), max(8, int(round(size))))


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def strings(code):
    text = (ROOT / f"Postman/Resources/{code}.lproj/Localizable.strings").read_text(encoding="utf-8")
    out = {}
    for key, value in re.findall(r'"((?:\\.|[^"\\])*)"\s*=\s*"((?:\\.|[^"\\])*)"\s*;', text):
        out[key] = value.replace(r"\n", "\n").replace(r"\"", '"')
    return out


def fmt(template, *args):
    out = template
    for arg in args:
        out = out.replace("%@", str(arg), 1)
    return out


def steps_text(n, russian):
    if russian:
        return f"{n:,}".replace(",", "\u00a0")
    return f"{n:,}"


ART = load_json(ASSETS / "UI/ui_ch1.json")["art"]
EN = load_json(ASSETS / "L10n/en.json")


def entry(name):
    return ART[name]


def open_art(name, scale=1.0, flip=False):
    e = entry(name)
    im = Image.open(UI / f"{name}.png").convert("RGBA")
    if im.size != (e["width"], e["height"]):
        im = im.resize((int(e["width"]), int(e["height"])), Image.Resampling.LANCZOS)
    if scale != 1:
        im = im.resize((max(1, int(round(e["width"] * scale))), max(1, int(round(e["height"] * scale)))),
                        Image.Resampling.LANCZOS)
    if flip:
        im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return im


def text_size(draw, text, face):
    box = draw.textbbox((0, 0), text, font=face)
    return box[2] - box[0], box[3] - box[1], box


def fit_face(name, size, text, max_width, draw, min_scale=0.7):
    size = max(8, int(round(size)))
    floor = max(8, int(round(size * min_scale)))
    face = font(name, size)
    while size > floor and text_size(draw, text, face)[0] > max_width:
        size -= 1
        face = font(name, size)
    return face


def wrap(draw, text, face, width):
    lines = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        cur = ""
        for word in para.split():
            trial = word if not cur else cur + " " + word
            if text_size(draw, trial, face)[0] <= width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def draw_centered(draw, xy, text, face, fill):
    box = draw.textbbox((0, 0), text, font=face)
    x = xy[0] - (box[0] + box[2]) / 2
    y = xy[1] - (box[1] + box[3]) / 2
    draw.text((x, y), text, font=face, fill=fill)
    return (x + box[0], y + box[1], x + box[2], y + box[3])


def draw_block(draw, center, lines, face, fill, gap):
    heights = []
    for line in lines:
        heights.append(text_size(draw, line or " ", face)[1])
    block = sum(heights) + gap * (len(lines) - 1)
    y = center[1] - block / 2
    boxes = []
    for line, h in zip(lines, heights):
        boxes.append(draw_centered(draw, (center[0], y + h / 2), line, face, fill))
        y += h + gap
    left = min(b[0] for b in boxes)
    top = min(b[1] for b in boxes)
    right = max(b[2] for b in boxes)
    bottom = max(b[3] for b in boxes)
    return (left, top, right, bottom)


def anchor_xy(name, key, scale, flip=False):
    e = entry(name)
    x, y = e["anchors"][key][:2]
    if flip:
        x = e["width"] - x
    return x * scale, y * scale


def body_rect(name, scale, flip=False):
    e = entry(name)
    x, y, w, h = e["anchors"]["body"]
    if flip:
        x = e["width"] - (x + w)
    return (x * scale, y * scale, w * scale, h * scale)


def paste(base, im, xy):
    base.alpha_composite(im, (int(round(xy[0])), int(round(xy[1]))))


def assert_on_paper(label, box, body, pad=8):
    if box[0] < body[0] - pad or box[2] > body[0] + body[2] + pad or box[1] < body[1] - pad or box[3] > body[1] + body[3] + pad:
        fail(f"{label} leaves the paper: text {tuple(round(v) for v in box)} body {tuple(round(v) for v in body)}")


def assert_center(label, box, point, tol=6):
    cx = (box[0] + box[2]) / 2
    cy = (box[1] + box[3]) / 2
    if abs(cx - point[0]) > tol or abs(cy - point[1]) > tol:
        fail(f"{label} center ({cx:.1f},{cy:.1f}) is off the anchor ({point[0]:.1f},{point[1]:.1f})")


def labeled(name, scale, lines, face_name, face_size, fill, flip=False, rotation=0, y_mode="mid"):
    """Картинка и подпись в её координатах. y_mode: line1 | mid (между line1 и line2)."""
    im = open_art(name, scale, flip)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    ax, ay1 = anchor_xy(name, "line1", scale, flip)
    _, ay2 = anchor_xy(name, "line2", scale, flip)
    point = (ax, ay1 if y_mode == "line1" else (ay1 + ay2) / 2)
    width = entry(name)["anchors"]["textWidth"][0] * scale
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    size = face_size
    face = font(face_name, size)
    wrapped = []
    for line in lines:
        wrapped.extend(wrap(probe, line, face, width) or [""])
    floor = max(8, int(round(face_size * 0.7)))
    while len(wrapped) > 2 and size > floor:
        size -= 1
        face = font(face_name, size)
        wrapped = []
        for line in lines:
            wrapped.extend(wrap(probe, line, face, width) or [""])
    if len(wrapped) == 1:
        face = fit_face(face_name, size, wrapped[0], width, probe)
        box = draw_centered(draw, point, wrapped[0], face, fill)
    else:
        box = draw_block(draw, point, wrapped[:2], face, fill, 2)
    assert_on_paper(lines[0], box, body_rect(name, scale, flip))
    assert_center(lines[0], box, point)
    im.alpha_composite(layer)
    if rotation:
        im = im.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=False, center=(im.width / 2, im.height / 2))
    return im


def pin_view_center(base, im, center):
    paste(base, im, (center[0] - im.width / 2, center[1] - im.height / 2))


def pin_body(base, im, name, scale, point, flip=False):
    e = entry(name)
    bx, by, bw, bh = e["anchors"]["body"]
    cx = (e["width"] - (bx + bw / 2) if flip else bx + bw / 2) * scale
    cy = (by + bh / 2) * scale
    paste(base, im, (point[0] - cx, point[1] - cy))


def arrow(base, title, right, bottom, face_size=44):
    e = entry("arrow")
    body = e["anchors"]["body"]
    center = (right - body[2] / 2, bottom - body[3] / 2)
    im = open_art("arrow")
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    point = e["anchors"]["text"]
    face = fit_face("YesevaOne.ttf", face_size, title, body[2] * 0.62, draw)
    box = draw_centered(draw, point, title, face, CHALK)
    assert_on_paper(title, box, tuple(body), pad=18)
    assert_center(title, box, point, tol=8)
    im.alpha_composite(layer)
    # pinned: body center at `center`
    bcx, bcy = body[0] + body[2] / 2, body[1] + body[3] / 2
    paste(base, im, (center[0] - bcx, center[1] - bcy))


def gradient(size, top, bottom):
    column = Image.new("RGB", (1, size[1]))
    px = column.load()
    last = max(1, size[1] - 1)
    for y in range(size[1]):
        t = y / last
        px[0, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return column.resize(size, Image.Resampling.BILINEAR).convert("RGBA")


def tile_at(base, path, top, height):
    src = Image.open(path).convert("RGBA")
    scale = height / src.height
    tile = src.resize((max(1, int(src.width * scale)), int(height)), Image.Resampling.LANCZOS)
    x = 0
    while x < W:
        base.alpha_composite(tile, (x, int(top)))
        x += tile.width


def road_scene():
    """Упрощённая дорога из слоёв world.json. Не рендер SpriteKit."""
    sky = gradient((W, H), (0x14, 0x50, 0x5F), (0x3C, 0x78, 0x73))
    tile_at(sky, ASSETS / "Chapter1/places/bg_far_ridges_tile.png", 520, 980)
    tile_at(sky, ASSETS / "Chapter1/places/bg_mid_fields_tile.png", 1080, 560)
    road = Image.open(ASSETS / "Chapter1/road/road_main_ogorody_1.png").convert("RGBA")
    rh = 980
    road = road.resize((max(1, int(road.width * rh / road.height)), rh), Image.Resampling.LANCZOS)
    x = -80
    while x < W:
        paste(sky, road, (x, 1500))
        x += road.width - 8
    place = Image.open(ASSETS / "Chapter1/places/place_pochta_main.png").convert("RGBA")
    ph = 980
    place = place.resize((max(1, int(place.width * ph / place.height)), ph), Image.Resampling.LANCZOS)
    paste(sky, place, (80, 1720 - ph + 40))
    postman = Image.open(ASSETS / "UI/map/postman.png").convert("RGBA")
    ph = 430
    postman = postman.resize((max(1, int(postman.width * ph / postman.height)), ph), Image.Resampling.LANCZOS)
    paste(sky, postman, (int(W * 0.55 - postman.width / 2), 1720 - ph + 30))
    return sky


def banner(im, lines):
    face = font("Kurale.ttf", 26)
    pad = 10
    draw = ImageDraw.Draw(im)
    height = pad * 2 + sum(text_size(draw, line, face)[1] + 4 for line in lines)
    bar = Image.new("RGBA", (W, height), (10, 14, 16, 220))
    im.alpha_composite(bar, (0, 0))
    draw = ImageDraw.Draw(im)
    y = pad
    for line in lines:
        draw.text((16, y), line, font=face, fill=(236, 226, 206, 255))
        y += text_size(draw, line, face)[1] + 4
    return height


def hud_buttons(base, ru_strings, lang):
    bag = open_art("hud_bag")
    mp = open_art("hud_map")
    pin_body(base, bag, "hud_bag", 1, (190, 2330))
    pin_body(base, mp, "hud_map", 1, (990, 2330))
    scale = 1.22
    button = (entry("tag_small")["width"] * scale, entry("tag_small")["height"] * scale)
    bag_body = entry("hud_bag")["anchors"]["body"]
    map_body = entry("hud_map")["anchors"]["body"]
    bag_c = (bag_body[0] + bag_body[2] / 2, bag_body[1] + bag_body[3] / 2)
    map_c = (map_body[0] + map_body[2] / 2, map_body[1] + map_body[3] / 2)
    bag_r = (190 - bag_c[0], 2330 - bag_c[1], entry("hud_bag")["width"], entry("hud_bag")["height"])
    map_r = (990 - map_c[0], 2330 - map_c[1], entry("hud_map")["width"], entry("hud_map")["height"])
    x = bag_r[0] + bag_r[2] + (map_r[0] - (bag_r[0] + bag_r[2])) / 2
    limit = 2532 - 8
    half = button[1] / 2
    history_y = min(limit - half, max(half, bag_r[1] + bag_r[3] / 2))
    menu_y = max(half, history_y - 12 - button[1])
    menu = labeled("tag_small", scale, [ru_strings["menu.open"]], "YesevaOne.ttf", 62 * scale, BROWN, y_mode="mid")
    history = labeled("tag_small", scale, [ru_strings["history.open"]], "YesevaOne.ttf", 52 * scale, BROWN,
                      flip=True, y_mode="mid")
    pin_view_center(base, menu, (x, menu_y))
    pin_view_center(base, history, (x, history_y))
    if menu_y + half > history_y - half:
        fail(f"{lang} history tag overlaps menu")
    if x - button[0] / 2 < bag_r[0] + bag_r[2] or x + button[0] / 2 > map_r[0]:
        fail(f"{lang} road tags overlap bag or map")


def tab_centers(scale):
    tag = entry("tag")
    size = (tag["width"] * scale, tag["height"] * scale)
    gap, margin = 14, 16
    cols = 2 if 4 * size[0] + 3 * gap + margin * 2 > 1170 else 4
    grid = cols * size[0] + (cols - 1) * gap
    left = (1170 - grid) / 2 + size[0] / 2
    first = 420 + 16 + size[1] / 2
    points = []
    for i in range(4):
        col, row = i % cols, i // cols
        points.append((left + col * (size[0] + gap), first + row * (size[1] + gap)))
    return points, size


def sheet_layout(tag_size, centers):
    tabs_bottom = max(p[1] for p in centers) + tag_size[1] / 2
    top = tabs_bottom + 8
    sheet = entry("sheet")
    fit_h = max(0.72, (1960 - top) / sheet["height"])
    fit_w = max(0.72, (1170 - 28) / sheet["width"])
    scale = min(fit_h, fit_w, 1.02)
    height = sheet["height"] * scale
    return scale, top + height / 2


def menu_frame(scene, lang, page, copy, story, lore, people, close_bottom=2460):
    base = scene.filter(ImageFilter.GaussianBlur(radius=14))
    dim = Image.new("RGBA", (W, H), (8, 23, 26, int(255 * 0.16)))
    base.alpha_composite(dim)
    plaque = open_art("plaque", 0.5)
    layer = Image.new("RGBA", plaque.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    point = entry("plaque")["anchors"]["text"]
    face = fit_face("YesevaOne.ttf", 46, copy["menu.title"], 420 * 0.5, draw, min_scale=0.6)
    # На экране шрифт 92 * (k*0.5) = 46 при k=1. Якорь — в пикселях картинки до scale? 
    # ArtView рисует текст в координатах уже умноженных на f=k*scale.
    # Здесь plaque уже уменьшен в 0.5, поэтому якорь тоже *0.5, а шрифт 92*0.5.
    point = (point[0] * 0.5, point[1] * 0.5)
    box = draw_centered(draw, point, copy["menu.title"], face, BROWN)
    assert_center(copy["menu.title"], box, point, tol=4)
    assert_on_paper(copy["menu.title"], box, body_rect("plaque", 0.5), pad=10)
    plaque.alpha_composite(layer)
    pin_body(base, plaque, "plaque", 0.5, (585, 292))

    scale = 0.88
    centers, tag_size = tab_centers(scale)
    titles = [copy["menu.quest.title"], copy["menu.people.title"], copy["menu.about.title"], copy["menu.settings"]]
    for i, (title, center) in enumerate(zip(titles, centers)):
        tag = labeled("tag", scale, title.split("\n"), "YesevaOne.ttf", 48 * scale, BROWN, y_mode="mid")
        if i != page:
            tag = ImageEnhance.Color(tag).enhance(0.35)
        pin_view_center(base, tag, center)

    sheet_scale, sheet_y = sheet_layout(tag_size, centers)
    sheet = open_art("sheet", sheet_scale)
    # Текст в textTL…textBR, как PaperArt.
    tl = entry("sheet")["anchors"]["textTL"]
    br = entry("sheet")["anchors"]["textBR"]
    origin = (585 - sheet.width / 2, sheet_y - sheet.height / 2)
    text_origin = (origin[0] + tl[0] * sheet_scale, origin[1] + tl[1] * sheet_scale)
    text_size_px = ((br[0] - tl[0]) * sheet_scale, (br[1] - tl[1]) * sheet_scale)
    content = page_image(page, copy, story, lore, people, text_size_px, lang)
    sheet.alpha_composite(content, (int(tl[0] * sheet_scale), int(tl[1] * sheet_scale)))
    paste(base, sheet, origin)

    for title, at, rotation in ((copy["menu.map"], (250, 2036), -6), (copy["menu.bag"], (920, 2036), 5)):
        # TagArt: size1 68 * f * 0.62, f = 0.92, слово на line1.
        tag = labeled("tag_small", 0.92, [title], "YesevaOne.ttf", 68 * 0.92 * 0.62, BROWN,
                      rotation=rotation, y_mode="line1")
        pin_view_center(base, tag, at)
    arrow(base, copy["menu.close"], 1136, close_bottom, 44)
    return base, text_origin, text_size_px


def page_image(page, copy, story, lore, people, size, lang):
    im = Image.new("RGBA", (max(1, int(size[0])), max(1, int(size[1]))), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    title_f = font("YesevaOne.ttf", 56)
    hand = font("Neucha.ttf", 46)
    small = font("Neucha.ttf", 30)
    y = 0
    width = im.width - 4

    def heading(text):
        nonlocal y
        draw.text((0, y), text, font=title_f, fill=BROWN)
        y += text_size(draw, text, title_f)[1] + 16

    def paragraph(text, face, gap=10):
        nonlocal y
        for line in wrap(draw, text, face, width):
            draw.text((0, y), line, font=face, fill=PENCIL)
            y += text_size(draw, line or " ", face)[1] + 6
        y += gap

    if page == 0:
        heading(copy["menu.quest.title"])
        paragraph(story["quest"], hand)
    elif page == 1:
        heading(copy["menu.people.title"])
        for person in people[:3]:
            row_top = y
            fig = person.get("image")
            text_x = 0
            if fig is not None:
                fitted = fit_image(fig, 160, 220)
                im.alpha_composite(fitted, (0, int(y)))
                text_x = fitted.width + 18
            name_f = font("YesevaOne.ttf", 44)
            draw.text((text_x, y), person["name"], font=name_f, fill=BROWN)
            y += text_size(draw, person["name"], name_f)[1] + 6
            body = font("Neucha.ttf", 32)
            for line in wrap(draw, person["text"], body, width - text_x):
                draw.text((text_x, y), line, font=body, fill=PENCIL)
                y += text_size(draw, line, body)[1] + 4
            y = max(y, row_top + (fitted.height if fig is not None else 0)) + 22
            if y > im.height - 40:
                break
    elif page == 2:
        heading(copy["menu.about.title"])
        paragraph(copy["menu.about.body"], font("Neucha.ttf", 44))
    else:
        heading(copy["menu.settings"])
        draw.text((0, y), copy["menu.language"], font=font("Kurale.ttf", 34), fill=BROWN)
        y += 48
        for key, on in (("menu.language.system", True), ("menu.language.ru", False), ("menu.language.en", False)):
            tag = labeled("tag_small", 0.92, [copy[key]], "YesevaOne.ttf", 64 * 0.92 * 0.62, BROWN, y_mode="line1")
            if not on:
                tag = ImageEnhance.Color(tag).enhance(0.25)
            if y + tag.height > im.height:
                break
            im.alpha_composite(tag, (0, int(y)))
            y += tag.height + 8
        paragraph(copy["menu.language.note"], small)
    if y < 80:
        fail(f"{lang} menu page {page} drew almost no text")
    return im


def fit_image(im, max_w, max_h):
    scale = min(max_w / im.width, max_h / im.height, 1)
    return im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.Resampling.LANCZOS)


def localize_story(story, chapter):
    spec = ((EN.get("stories") or {}).get(str(chapter)) or {})
    out = json.loads(json.dumps(story))
    events = {e["id"]: e for e in out["events"]}
    for eid, ev in ((spec.get("events") or {}).items()):
        if eid not in events:
            continue
        for key in ("title", "text", "fallback", "note"):
            if key in ev:
                events[eid][key] = ev[key]
        if "options" in ev:
            by_id = {o["id"]: o for o in events[eid].get("options") or []}
            for oid, opt in ev["options"].items():
                if oid in by_id:
                    for key in ("label", "result", "auto"):
                        if key in opt:
                            by_id[oid][key] = opt[key]
        if "lines" in ev:
            for i, line in enumerate(ev["lines"]):
                if i < len(events[eid].get("lines") or []):
                    events[eid]["lines"][i]["who"] = line.get("who", events[eid]["lines"][i].get("who", ""))
                    events[eid]["lines"][i]["text"] = line.get("text", events[eid]["lines"][i].get("text", ""))
    arrivals = spec.get("arrivals") or {}
    for row in out.get("arrivals") or []:
        if row["settlement"] in arrivals:
            row["text"] = arrivals[row["settlement"]]
    names = spec.get("residents") or {}
    for row in out.get("residents") or []:
        if row["id"] in names:
            row["name"] = names[row["id"]]
    items = {it["id"]: it for it in out.get("items") or []}
    for iid, spec_item in (spec.get("items") or {}).items():
        if iid in items:
            for key in ("to", "place", "from", "text"):
                if key in spec_item:
                    items[iid][key] = spec_item[key]
    qmap = spec.get("quests") or {}
    for quest in out.get("quests") or []:
        key = (quest.get("event") or "") + "|" + (quest.get("if") or "")
        if key in qmap:
            quest["telegram"] = qmap[key]
    return out


def localize_world(world):
    out = json.loads(json.dumps(world))
    specs = ((EN.get("world") or {}).get("chapters") or {})
    for chapter in out["chapters"]:
        spec = specs.get(str(chapter["id"]))
        if not spec:
            continue
        chapter["title"] = spec.get("title", chapter["title"])
        names = spec.get("settlements") or {}
        for place in chapter["settlements"]:
            if place["id"] in names:
                place.update({k: names[place["id"]][k] for k in ("name", "nameGenitive", "fullName") if k in names[place["id"]]})
    return out


def localize_lore(lore):
    out = json.loads(json.dumps(lore))
    for key, spec in (EN.get("lore") or {}).items():
        if key in out:
            out[key]["title"] = spec.get("title", out[key]["title"])
            out[key]["lines"] = spec.get("lines", out[key]["lines"])
    return out


def describe(item, copy):
    if item["kind"] == "parcel":
        return fmt(copy["engine.item.parcel"], item["place"])
    if item["kind"] == "form":
        return copy["engine.item.form"]
    return fmt(copy["engine.item.letter"], item["to"])


def sentences(event, choices, items, carried, story, copy):
    lines = []

    def add(line):
        if line and line not in lines:
            lines.append(line)

    kind = event["type"]
    by_id = {it["id"]: it for it in story.get("items") or []}
    if kind == "choice":
        add(event.get("text"))
        picked = choices.get(event["id"])
        option = next((o for o in event.get("options") or [] if o["id"] == picked), None)
        add(option.get("result") if option else event.get("fallback"))
    elif kind == "scene":
        add(event.get("text"))
        for line in event.get("lines") or []:
            if line.get("if"):
                continue
            who = line.get("who") or ""
            add(line.get("text") if not who else f"{who}: «{line.get('text', '')}»")
    elif kind == "deliver":
        given = [i for i in event.get("items") or [] if items.get(i) == "delivered"]
        if not given:
            add(copy["engine.deliver.none"])
        else:
            names = [describe(by_id[i], copy) for i in given if i in by_id]
            add(fmt(copy["engine.deliver.some"], ", ".join(names)))
    elif kind == "pickup":
        iid = event.get("item")
        if iid and iid in by_id:
            status = items.get(iid)
            if status in ("inBag", "inPocket", "delivered", "sent", "read"):
                add(fmt(copy["engine.pickup.took"], describe(by_id[iid], copy)))
            elif status in ("leftBehind", "lostWind"):
                add(fmt(copy["engine.pickup.full"], describe(by_id[iid], copy)))
        add(event.get("text"))
    elif kind == "sort":
        taken = [i for i in event.get("candidates") or []
                 if i in carried or items.get(i) in ("inBag", "delivered", "sent")]
        if not taken:
            add(copy["engine.sort.empty"])
        else:
            names = [describe(by_id[i], copy) for i in taken if i in by_id]
            add(fmt(copy["engine.sort.some"], ", ".join(names)))
    elif kind == "finale":
        add(event.get("text"))
        add(copy["engine.finale.log"])
    return "\n".join(lines)


def chronicle(world, stories, copy, active_index, active_steps, choices, items, done, arrived):
    pages = []
    for index, chapter in enumerate(world["chapters"]):
        if index > active_index:
            continue
        story = stories[chapter["id"]]
        length = chapter["lengthSteps"]
        reached = length if index < active_index else max(0, min(length, active_steps))
        places = {p["id"]: p for p in chapter["settlements"]}
        for place in chapter["settlements"]:
            if place["step"] > reached or place["id"] not in arrived.get(chapter["id"], set()):
                continue
            line = next((a["text"] for a in story.get("arrivals") or [] if a["settlement"] == place["id"]), "")
            if not line:
                continue
            pages.append({
                "id": f"arrive:{chapter['id']}:{place['id']}",
                "world": chapter["startStep"] + place["step"],
                "chapter": chapter["title"],
                "place": place["name"],
                "heading": place["name"],
                "text": line,
                "resident": None,
                "folder": chapter["assetsFolder"],
                "place_id": place["id"],
            })
        for event in story["events"]:
            if event["step"] > reached or event["id"] not in done.get(chapter["id"], set()):
                continue
            text = sentences(event, choices.get(chapter["id"], {}), items.get(chapter["id"], {}),
                             done.get(chapter["id"], set()), story, copy)
            if not text:
                continue
            place = places.get(event["settlement"], {}).get("name", event["settlement"])
            pages.append({
                "id": f"{chapter['id']}:{event['id']}",
                "world": chapter["startStep"] + event["step"],
                "chapter": chapter["title"],
                "place": place,
                "heading": event.get("title") or place,
                "text": text,
                "resident": event.get("resident"),
                "folder": chapter["assetsFolder"],
                "place_id": event["settlement"],
            })
    pages.sort(key=lambda p: (p["world"], p["id"]))
    return pages


def figure(folder, resident_id):
    root = ASSETS / folder / "residents" / resident_id
    if not root.exists() and folder != "Chapter1":
        root = ASSETS / "Chapter1/residents" / resident_id
    rig_path = root / "rig.json"
    if rig_path.exists():
        rig = load_json(rig_path)
        order = rig.get("draw_order") or list((rig.get("offsets") or {}))
        parts = []
        for name in order:
            xy = (rig.get("offsets") or {}).get(name)
            if not xy:
                continue
            img = None
            for rel in (f"parts/{name}.png", f"{name}.png"):
                path = root / rel
                if path.exists():
                    img = Image.open(path).convert("RGBA")
                    break
            if img:
                parts.append((img, xy))
        if parts:
            min_x = min(xy[0] for _, xy in parts)
            min_y = min(xy[1] for _, xy in parts)
            max_x = max(xy[0] + img.width for img, xy in parts)
            max_y = max(xy[1] + img.height for img, xy in parts)
            canvas = Image.new("RGBA", (max(1, int(max_x - min_x)), max(1, int(max_y - min_y))), (0, 0, 0, 0))
            for img, xy in parts:
                canvas.alpha_composite(img, (int(xy[0] - min_x), int(xy[1] - min_y)))
            if (rig.get("facing") or "right").lower() != "left":
                canvas = canvas.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            return canvas
    for name in ("full.png", "preview.png", f"{resident_id}.png"):
        path = root / name
        if path.exists():
            return Image.open(path).convert("RGBA")
    return None


def place_image(folder, place_id):
    path = ASSETS / folder / "places" / f"place_{place_id}_main.png"
    if not path.exists():
        return None
    im = Image.open(path).convert("RGBA")
    if im.height <= 0 or im.width / im.height < 0.7:
        return None
    if im.width > 900:
        s = 900 / im.width
        im = im.resize((900, max(1, int(im.height * s))), Image.Resampling.LANCZOS)
    return im


def history_column(facts, copy, russian):
    width = 760
    column = Image.new("RGBA", (width, 20000), (0, 0, 0, 0))
    draw = ImageDraw.Draw(column)
    y = 0
    marks = {}
    title = font("YesevaOne.ttf", 64)
    chapter_f = font("YesevaOne.ttf", 40)
    head = font("YesevaOne.ttf", 48)
    body = font("Neucha.ttf", 42)

    def line_h(face, text):
        return text_size(draw, text or "Ag", face)[1]

    draw.text((0, y), copy["history.title"], font=title, fill=BROWN)
    y += line_h(title, copy["history.title"]) + 28
    previous = None
    for fact in facts:
        if fact["chapter"] != previous:
            marks[f"chapter:{fact['chapter']}"] = y
            draw.text((0, y), fact["chapter"], font=chapter_f, fill=BROWN)
            y += line_h(chapter_f, fact["chapter"]) + 18
            previous = fact["chapter"]
        marks[fact["id"]] = y
        for line in wrap(draw, fact["heading"], head, width):
            draw.text((0, y), line, font=head, fill=BROWN)
            y += line_h(head, line) + 4
        y += 8
        fig = figure(fact["folder"], fact["resident"]) if fact["resident"] else None
        pic = place_image(fact["folder"], fact["place_id"])
        if fig or pic:
            both = fig is not None and pic is not None
            row = []
            if fig is not None:
                row.append(fit_image(fig, 340 if both else 640, 520 if both else 780))
            if pic is not None:
                row.append(fit_image(pic, 560 if both else 900, 400 if both else 520))
            row_h = max(im.height for im in row)
            x = 0
            for im in row:
                column.alpha_composite(im, (x, int(y + row_h - im.height)))
                x += im.width + 16
            y += row_h + 12
        for line in wrap(draw, fact["text"], body, width):
            draw.text((0, y), line, font=body, fill=PENCIL)
            y += line_h(body, line) + 6
        y += 28
        if y > column.height - 400:
            fail("history column overflowed the paint buffer")
            break
    return column.crop((0, 0, width, max(1, int(y)))), marks


def paint_history(scene, column, marks, focus, copy, note):
    band_top, band_bottom = 0, 2532
    arrow_bottom = min(2470, band_bottom - 16)
    top, height = 80, 2200
    if top < band_top + 12 or top + height > arrow_bottom - 24:
        top = band_top + 16
        height = max(1200, min(2200, arrow_bottom - 36 - top))
    center_y = top + height / 2
    base = scene.copy()
    dim = Image.new("RGBA", (W, H), (8, 23, 26, int(255 * 0.62)))
    base.alpha_composite(dim)
    paper = Image.new("RGBA", (1040, height), PAPER)
    ImageDraw.Draw(paper).rounded_rectangle((1, 1, 1038, height - 2), radius=18, outline=EDGE, width=4)
    view_h = height - 112
    focus_y = marks.get(focus, 0)
    offset = 0 if focus is None else max(0, min(focus_y - 80, max(0, column.height - view_h)))
    window = column.crop((0, offset, column.width, min(column.height, offset + view_h)))
    paper.alpha_composite(window, (48, 56))
    paste(base, paper, (585 - 520, center_y - height / 2))
    arrow(base, copy["map.close"], 1136, arrow_bottom, 44)
    banner(base, note)
    return base


def short_phone_menu(scene, copy, quest):
    """375×667, aspectFill кадра 1170×2532. Стрелка поднята в видимую полосу, как FrameEdges."""
    view_w, view_h = 375, 667
    scale = max(view_w / 1170, view_h / 2532)
    origin_y = (view_h - 2532 * scale) / 2
    visible_top = max(0, -origin_y / scale)
    visible_bottom = min(2532, (view_h - origin_y) / scale)
    arrow_bottom = min(2460, visible_bottom - 16)
    if arrow_bottom > visible_bottom - 16:
        fail("short-phone close is below the visible frame")
    full, _, _ = menu_frame(scene, "ru-se", 0, copy, {"quest": quest}, {}, [], close_bottom=arrow_bottom)
    top = int(round(visible_top))
    bottom = int(round(min(H, visible_bottom)))
    crop = full.crop((0, top, W, bottom)).resize((W, int(round((bottom - top)))), Image.Resampling.LANCZOS)
    face = font("Kurale.ttf", 26)
    note = [
        "OFFLINE 375×667 aspectFill · not a simulator frame · banner is not part of the game",
        f"visible design y {visible_top:.0f}…{visible_bottom:.0f} · close lifted to {arrow_bottom:.0f}",
    ]
    bar_h = 18 + 32 * len(note)
    framed = Image.new("RGBA", (W, bar_h + crop.height), (10, 14, 16, 255))
    draw = ImageDraw.Draw(framed)
    y = 8
    for line in note:
        draw.text((16, y), line, font=face, fill=(236, 226, 206, 255))
        y += 32
    framed.alpha_composite(crop, (0, bar_h))
    return framed


def build_fixture(world, stories):
    """QA-прогон: глава 1 целиком, глава 2 до шага 300. Не сейв игрока."""
    choices, items, done, arrived = {}, {}, {}, {}
    for index, chapter in enumerate(world["chapters"]):
        story = stories[chapter["id"]]
        reached = chapter["lengthSteps"] if index == 0 else 300
        if index > 1:
            continue
        done[chapter["id"]] = {e["id"] for e in story["events"] if e["step"] <= reached}
        arrived[chapter["id"]] = {p["id"] for p in chapter["settlements"] if p["step"] <= reached}
        choices[chapter["id"]] = {}
        for event in story["events"]:
            if event["type"] == "choice" and event["step"] <= reached:
                choices[chapter["id"]][event["id"]] = "help" if event["id"] == "e_cart" else event.get("default")
        bag = {}
        for event in story["events"]:
            if event["step"] > reached:
                continue
            if event["type"] == "pickup" and event.get("item"):
                bag[event["item"]] = "inBag"
            if event["type"] == "deliver":
                for iid in event.get("items") or []:
                    bag[iid] = "delivered"
        items[chapter["id"]] = bag
    # Явно зафиксированные ветки, даже если default совпал.
    choices[1]["e_cart"] = "help"
    choices[2]["e_animal_raven"] = "trade"
    return choices, items, done, arrived


def main_line(story, chapter_title, folder, done, items, opened, choices, reached):
    """Те же абзацы, что StoryChronicle.beats. Не все события файла."""
    beats = [
        ("l1", 2900, "d_l1", "l1", False, "kuzma", "svai", None),
        ("l2", 6000, "d_l2", "l2", False, "pimen", "zvonarnya", None),
        ("l6", 9100, "d_l6", "l6", False, "nina", "kadushki", None),
        ("l4", 13200, "d_vera", "l4", False, "vera", "nii", None),
        ("l5", 13200, "d_vera", "l5", True, "vera", "nii", None),
        ("l3", 20000, "finale", "l3", False, "nina", "sedlo", "e_wind"),
        ("l7", 20000, "finale", "l7", False, None, "sedlo", None),
    ]
    by_id = {it["id"]: it for it in story["items"]}
    events = {ev["id"]: ev for ev in story["events"]}
    pages = []
    for bid, step, event, item_id, secret, resident, place, choice in beats:
        if step > reached or event not in done:
            continue
        item = by_id[item_id]
        status = items.get(item_id)
        if bid == "l4":
            if items.get("batteries") != "delivered":
                continue
            body = item.get("text")
        elif bid == "l3":
            lost = status == "lostWind" and "e_wind" in done
            if status != "sent" and not lost:
                continue
            body = item.get("text")
        elif bid == "l7":
            if status != "read":
                continue
            body = item.get("text")
        elif secret:
            if item_id in opened:
                body = item.get("text")
            elif status in ("delivered", "sent", "read"):
                body = item.get("outside")
            else:
                body = None
        else:
            body = item.get("text") if status in ("delivered", "sent", "read", "lostWind") or item_id in opened else None
        lines = [body] if body else []
        if choice and choice in done and events[choice]["step"] <= reached and choices.get(choice):
            picked = choices[choice]
            result = next(o["result"] for o in events[choice]["options"] if o["id"] == picked)
            if result not in lines:
                lines.append(result)
        if not lines:
            continue
        heading = " — ".join(part for part in (item.get("from"), item.get("to")) if part)
        pages.append({
            "id": bid, "chapter": chapter_title, "heading": heading,
            "text": "\n\n".join(lines), "resident": resident,
            "folder": folder, "place_id": place,
        })
    return pages


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ru = strings("ru")
    en = strings("en")
    world_ru = load_json(ASSETS / "Data/world.json")
    world_en = localize_world(world_ru)
    lore_ru = load_json(ASSETS / "Data/resident_lore.json")
    lore_en = localize_lore(lore_ru)
    stories_ru = {
        1: load_json(ASSETS / "Data/chapter1_story.json"),
        2: load_json(ASSETS / "Data/chapter2_story.json"),
    }
    stories_en = {k: localize_story(v, k) for k, v in stories_ru.items()}
    choices, items, done, arrived = build_fixture(world_ru, stories_ru)
    # Меню по-прежнему показывает каст старого прогона. История — отдельный частичный прогон писем.
    facts_ru = chronicle(world_ru, stories_ru, ru, 1, 300, choices, items, done, arrived)
    facts_en = chronicle(world_en, stories_en, en, 1, 300, choices, items, done, arrived)
    def carried(status):
        return status in ("inBag", "inPocket", "delivered", "sent", "read", "lostWind")

    def narrative(copy, items, done, opened, chapter_title):
        pages = []

        def add(pid, title, text, resident, place):
            pages.append({"id": pid, "chapter": chapter_title, "heading": title,
                          "text": text, "resident": resident, "folder": "Chapter1", "place_id": place})

        if "sort" in done:
            bits = [copy["history.main.road.out"]]
            if carried(items.get("l3")):
                bits.append(copy["history.main.road.nina"])
            if carried(items.get("l2")):
                bits.append(copy["history.main.road.mitya"])
            if items.get("l4") == "inPocket" or carried(items.get("l4")):
                bits.append(copy["history.main.road.vera"])
            add("road", copy["history.main.road.title"], " ".join(bits), None, "pochta")
        if "d_l1" in done and items.get("l1") == "delivered":
            add("stilts", copy["history.main.stilts.title"], copy["history.main.stilts.body"], "kuzma", "svai")
        if "d_l2" in done and items.get("l2") == "delivered":
            bits = [copy["history.main.belfry.body"]]
            if carried(items.get("l5")):
                bits.append(copy["history.main.belfry.fortyone"])
            if "l5" in opened:
                bits.append(copy["history.main.belfry.opened"])
            add("belfry", copy["history.main.belfry.title"], " ".join(bits), "pimen", "zvonarnya")
        if "s_nina" in done:
            if items.get("l3") == "inBag":
                ask = copy["history.main.ask.bag"]
            elif items.get("l3") == "atPost":
                ask = copy["history.main.ask.post"]
            else:
                ask = copy["history.main.ask.body"]
            add("ask", copy["history.main.ask.title"], ask, "nina", "kadushki")
        if "d_l6" in done and items.get("l6") == "delivered":
            add("strange", copy["history.main.strange.title"], copy["history.main.strange.body"], "nina", "kadushki")
        return pages

    partial_items = {"l1": "delivered", "l2": "delivered", "l3": "inBag", "l4": "inPocket", "l5": "inBag", "l6": "delivered"}
    partial_done = {"sort", "d_l1", "d_l2", "p_l5", "s_nina", "d_l6"}
    line_ru = narrative(ru, partial_items, partial_done, set(), "Долина")
    line_en = narrative(en, partial_items, partial_done, set(), "Valley")
    joined = "\n".join(page["text"] for page in line_ru)
    if "Ответ на это письмо уже пришёл" not in joined:
        fail("the noticed contradiction is missing")
    if "Кузьма Ерофеич здраствуй" in joined or "Взято" in joined:
        fail("the history reprinted a letter or a log line")
    if ru["history.main.belfry.opened"] in joined or ru["history.main.saddle.ksenia"] in joined:
        fail("a later or sealed revelation leaked into the partial story")
    if {page["id"] for page in line_ru} != {"road", "stilts", "belfry", "ask", "strange"}:
        fail(f"partial arc changed: {[p['id'] for p in line_ru]}")

    scene = road_scene()
    note = [
        "OFFLINE composite of game assets · not a simulator frame · not Ilya's save",
        "QA fixture: chapter 1 complete, cart choice = help · chapter 2 step 300, raven = trade · later mountains omitted",
    ]
    road = scene.copy()
    hud_buttons(road, ru, "ru")
    banner(road, ["OFFLINE composite · road HUD · not a simulator frame", "Menu and History tags use ui_ch1.json anchors"])
    road.convert("RGB").save(OUT / "road_hud_ru.jpg", quality=90)
    road_en = scene.copy()
    hud_buttons(road_en, en, "en")
    banner(road_en, ["OFFLINE composite · road HUD · English labels · not a simulator frame"])
    road_en.convert("RGB").save(OUT / "road_hud_en.jpg", quality=90)

    quest_ru = next(q["telegram"] for q in stories_ru[2]["quests"]
                    if q["event"] not in done[2] and (not q.get("if") or q.get("if") == "inBag:l1" and items[2].get("l1") == "inBag"))
    quest_en = next(q["telegram"] for q in stories_en[2]["quests"]
                    if q["event"] not in done[2] and (not q.get("if") or q.get("if") == "inBag:l1" and items[2].get("l1") == "inBag"))
    people = []
    for fact in facts_ru:
        if not fact["resident"] or any(p["id"] == fact["resident"] for p in people):
            continue
        lore = lore_ru.get(fact["resident"])
        if not lore:
            continue
        people.append({"id": fact["resident"], "name": lore["title"], "text": "\n".join(lore["lines"]),
                        "image": figure(fact["folder"], fact["resident"])})
    pages = {
        "menu_quest_ru.jpg": (0, ru, {"quest": quest_ru}, lore_ru, people),
        "menu_people_ru.jpg": (1, ru, {"quest": quest_ru}, lore_ru, people),
        "menu_about_ru.jpg": (2, ru, {"quest": quest_ru}, lore_ru, people),
        "menu_settings_ru.jpg": (3, ru, {"quest": quest_ru}, lore_ru, people),
    }
    for name, (page, copy, story, lore, cast) in pages.items():
        frame, _, _ = menu_frame(scene, "ru", page, copy, story, lore, cast)
        banner(frame, note if page == 0 else [
            "OFFLINE composite · menu tab · not a simulator frame · not Ilya's save",
            "Menu cast is a separate QA fixture from the history letters",
        ])
        frame.convert("RGB").save(OUT / name, quality=88)
    people_en = []
    for fact in facts_en:
        if not fact["resident"] or any(p["id"] == fact["resident"] for p in people_en):
            continue
        lore = lore_en.get(fact["resident"])
        if not lore:
            continue
        people_en.append({"id": fact["resident"], "name": lore["title"], "text": "\n".join(lore["lines"]),
                          "image": figure(fact["folder"], fact["resident"])})
    frame, _, _ = menu_frame(scene, "en", 0, en, {"quest": quest_en}, lore_en, people_en)
    banner(frame, [
        "OFFLINE composite · English menu · not a simulator frame · not Ilya's save",
        "QA fixture quest is the first unfinished chapter 2 errand at step 300",
    ])
    frame.convert("RGB").save(OUT / "menu_quest_en.jpg", quality=88)

    history_note = [
        "OFFLINE composite · not a simulator frame · not Ilya's save",
        "QA partial: sort, Stilts, Belfry, Nina's question, box no. 2. Seal closed. Saddle not reached.",
    ]
    column, marks = history_column(line_ru, ru, True)
    paint_history(scene, column, marks, None, ru, history_note).convert("RGB").save(OUT / "history_main_ru.jpg", quality=88)
    paint_history(scene, column, marks, "strange", ru, history_note).convert("RGB").save(OUT / "history_main_ru_next.jpg", quality=88)
    column_en, _ = history_column(line_en, en, False)
    paint_history(scene, column_en, {}, None, en, [
        "OFFLINE composite · English main arc · not a simulator frame · not Ilya's save",
        "Same partial progress. Author secrets stay out. Chapters 3–5 are not in this build.",
    ]).convert("RGB").save(OUT / "history_main_en.jpg", quality=88)
    short_phone_menu(scene, ru, quest_ru).convert("RGB").save(OUT / "menu_short_phone.jpg", quality=88)

    for stale in ("menu_larger_sheet.jpg", "road_history_tag.jpg", "history_scroll.jpg",
                  "history_top_ru.jpg", "history_choice_ru.jpg", "history_choice_en.jpg",
                  "history_chapter_ru.jpg", "history_chapter_en.jpg"):
        path = OUT / stale
        if path.exists():
            path.unlink()

    print(f"main-line letters: {[p['id'] for p in line_ru]}")
    print("quest:", quest_ru)
    if FAILS:
        print(f"{len(FAILS)} preview check(s) failed:")
        for item in FAILS:
            print(" -", item)
        raise SystemExit(1)
    print("preview layout checks ok")
    for path in sorted(OUT.iterdir()):
        print(path)


if __name__ == "__main__":
    main()
