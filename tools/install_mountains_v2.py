#!/usr/bin/env python3
"""Поставить лист гор v2 и собрать честный кадр компоновщика.

Цвет и шесть иконок — из сдачи художника. Якоря — из его JSON.
Поле пересчитывается в кодировке Долины (value = (доля + 0.1) / 1.3).
Карандаш v1 из архива не копируется: он снят со старого цвета.
Пластина карандаша выводится из цвета v2 той же связью, что у пары Долины.
"""
import json
import math
import random
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "Postman/GameAssets/UI/map"
UI = ROOT / "Postman/GameAssets/UI/ch1"
FONTS = ROOT / "Postman/GameAssets/Fonts"
SRC = Path("/tmp/mtn2")
OUT = Path("/opt/cursor/artifacts/map-v2-preview")

W, H = 1170, 2532
VALLEY_ORIGIN_Y = 2452.0 - 480.0
NAMES = {
    "gar": "Гарь",
    "penki": "Пеньки",
    "khomut": "Хомут",
    "repka": "Репка",
    "krivulya": "Кривуля",
    "gorlovina": "Горловина",
}
STEPS = {
    "gar": 2800, "penki": 6500, "khomut": 11000,
    "repka": 15500, "krivulya": 16500, "gorlovina": 24000,
}
# Связь цвет→карандаш, снятая с map_color.jpg / map_pencil.jpg Долины.
PENCIL_LUMA = (0.137601809, 177.554344)
PENCIL_CHROMA = 0.23269731
TAG_SCALE = 300.0 / 287.0
TAG_W = 199 * TAG_SCALE
TAG_H = 105 * TAG_SCALE
BROWN = (69, 46, 28, 255)
CHALK = (242, 235, 214, 255)


def arc_len(road):
    total = 0.0
    for a, b in zip(road, road[1:]):
        total += math.hypot(b[0] - a[0], b[1] - a[1])
    return total


def point_at(road, cum, fraction):
    s = min(1.0, max(0.0, fraction)) * cum[-1]
    for i in range(len(cum) - 1):
        if cum[i + 1] >= s or i == len(cum) - 2:
            span = max(1e-9, cum[i + 1] - cum[i])
            t = (s - cum[i]) / span
            a, b = road[i], road[i + 1]
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    return road[-1]


def cumulative(road):
    cum = [0.0]
    for a, b in zip(road, road[1:]):
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return cum


def dense_samples(road, cum, n=1601):
    return np.array([point_at(road, cum, i / (n - 1)) for i in range(n)], np.float64)


def nearest_index(dense, height, width, hs):
    n_h, n_w = height // hs, width // hs
    idx = np.empty((n_h, n_w), np.int32)
    xs = np.arange(n_w) * hs + hs * 0.5
    ys = np.arange(n_h) * hs + hs * 0.5
    for r0 in range(0, n_h, 24):
        r1 = min(n_h, r0 + 24)
        dy = ys[r0:r1, None, None] - dense[None, None, :, 1]
        dx = xs[None, :, None] - dense[None, None, :, 0]
        idx[r0:r1] = (dx * dx + dy * dy).argmin(axis=2)
    return idx, xs, ys


def blur(img, sigma):
    radius = int(round(sigma * 3))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(x * x) / (2 * sigma * sigma))
    kernel /= kernel.sum()

    def along(image, axis):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (radius, radius)
        padded = np.pad(image, pad, mode="edge")
        out = np.zeros_like(image)
        if axis == 1:
            for i, weight in enumerate(kernel):
                out += padded[:, i:i + image.shape[1]] * weight
        else:
            for i, weight in enumerate(kernel):
                out += padded[i:i + image.shape[0], :] * weight
        return out

    return along(along(img, 1), 0)


def encode_field(road):
    cum = cumulative(road)
    length = cum[-1]
    dense = dense_samples(road, cum)
    hs = 2
    idx, xs, ys = nearest_index(dense, H, W, hs)
    field_px = (idx / (len(dense) - 1)) * length
    yy = ys[:, None]
    start_y = dense[0, 1]
    field_px[(idx == 0) & (yy > start_y)] = -0.05 * length
    xx = xs[None, :]
    field_px = field_px + 28 * np.sin(xx / 95.0) + 18 * np.sin(xx / 41.0 + 1.3)
    field_px = blur(field_px, 22 / hs)
    field = field_px / length
    encoded = np.clip((field + 0.1) / 1.3, 0, 1)
    image = Image.fromarray((encoded * 255).round().astype(np.uint8), "L")
    return image, field, length


def pencil_from_color(color):
    arr = np.array(color.convert("RGB")).astype(np.float32)
    gray = arr.mean(axis=2, keepdims=True)
    luma = PENCIL_LUMA[0] * gray + PENCIL_LUMA[1]
    out = np.clip(luma + PENCIL_CHROMA * (arr - gray), 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGB")


def puff_rows(field):
    levels = 120
    rows = []
    cols = [50, 300, 590, 880, 1120]
    hs = 2
    for level in range(levels + 1):
        t0 = level / levels * 1.1
        row = []
        for ci, cx in enumerate(cols):
            col = field[:, min(int(cx / hs), field.shape[1] - 1)]
            cross = np.where((col[:-1] >= t0) & (col[1:] < t0))[0]
            if len(cross) == 0:
                continue
            y = (float(cross.max()) + 0.5) * hs
            rng = random.Random(level * 7 + ci)
            row.append([
                cx + rng.uniform(-40, 40),
                y - 15 + rng.uniform(-25, 20),
                round(rng.uniform(250, 360)),
                ci % 2,
            ])
        rows.append(row)
    return rows


def rect_of(center, width, height):
    return (center[0] - width / 2, center[1] - height / 2,
            center[0] + width / 2, center[1] + height / 2)


def overlap(a, b):
    w = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return w * h


def layout_tags(places, feet, include_postman, reached, next_id, frame=(W, H)):
    """Та же жадная раскладка, что ParchmentLayout.layout(places:)."""
    obstacles = []
    for place in places:
        r = (place["x"] - place["w"] / 2, place["y"] - place["h"],
             place["x"] + place["w"] / 2, place["y"])
        obstacles.append((r[0] + place["w"] * 0.12, r[1] + place["h"] * 0.1,
                          r[2] - place["w"] * 0.12, r[3] - place["h"] * 0.1))
    if include_postman:
        obstacles.append((feet[0] - 87 * 0.4, feet[1] - 230, feet[0] + 87 * 0.4, feet[1]))
    bounds = (12, 12, frame[0] - 12, frame[1] - 12)

    def cost(center):
        r = rect_of(center, TAG_W, TAG_H)
        score = 0.0
        for item in obstacles:
            score += overlap(r, item)
        inside_w = max(0, min(r[2], bounds[2]) - max(r[0], bounds[0]))
        inside_h = max(0, min(r[3], bounds[3]) - max(r[1], bounds[1]))
        score += (TAG_W * TAG_H - inside_w * inside_h) * 4
        return score

    def pick(candidates):
        best, best_cost = candidates[0], 1e18
        for i, candidate in enumerate(candidates):
            value = cost(candidate) + i * 0.5
            if value < best_cost:
                best, best_cost = candidate, value
            if value < 1:
                break
        r = rect_of(best, TAG_W, TAG_H)
        obstacles.append((r[0] - 6, r[1] - 6, r[2] + 6, r[3] + 6))
        return best, best_cost

    tags = {}
    postman = None
    if include_postman:
        dx = 87 * 0.4 + TAG_W / 2 + 8
        postman, _ = pick([
            (feet[0] - dx - 70, feet[1] - 230 * 0.72),
            (feet[0] - dx, feet[1] - 230 * 0.45),
            (feet[0] + dx, feet[1] - 230 * 0.45),
            (feet[0] - dx, feet[1] - 230 * 0.05),
            (feet[0] + dx, feet[1] - 230 * 0.05),
            (feet[0] - dx, feet[1] - 230 * 0.85),
            (feet[0] + dx, feet[1] - 230 * 0.85),
            (feet[0], feet[1] + TAG_H / 2 + 10),
            (feet[0], feet[1] - 230 - TAG_H / 2 - 6),
        ])
    order = sorted(places, key=lambda s: (0 if s["id"] == next_id else 1 if s["step"] <= reached else 2, s["step"]))
    for place in order:
        r = (place["x"] - place["w"] / 2, place["y"] - place["h"],
             place["x"] + place["w"] / 2, place["y"])
        side = 1 if (r[0] + r[2]) / 2 > frame[0] / 2 else -1
        below = r[3] + TAG_H / 2 - 4
        mid_x = (r[0] + r[2]) / 2
        mid_y = (r[1] + r[3]) / 2
        center, _ = pick([
            (mid_x - side * 10, below),
            (mid_x + side * (place["w"] / 2 + TAG_W / 2 - 10), mid_y + place["h"] * 0.15),
            (mid_x - side * (place["w"] / 2 + TAG_W / 2 - 10), mid_y + place["h"] * 0.15),
            (mid_x, r[1] - TAG_H / 2 + 6),
            (mid_x + side * 60, below + TAG_H * 0.7),
            (mid_x - side * 60, below + TAG_H * 0.7),
            (mid_x + side * (place["w"] / 2 + TAG_W / 2 - 10), r[1] + 10),
            (mid_x - side * (place["w"] / 2 + TAG_W / 2 - 10), r[1] + 10),
        ])
        tags[place["id"]] = center
    return tags, postman


def grouped(n):
    text = f"{n:,}".replace(",", " ")
    return text


def font(path, size):
    return ImageFont.truetype(str(path), size)


def paste_rgba(base, sprite, xy):
    sprite = sprite.convert("RGBA")
    base.alpha_composite(sprite, (int(round(xy[0])), int(round(xy[1]))))


def fit_line(draw, text, font_path, size, max_w, fill):
    face = font(font_path, size)
    while size > 12 and draw.textlength(text, font=face) > max_w:
        size -= 1
        face = font(font_path, size)
    return face


def draw_tag(base, center, line1, line2, dim=False, rotation=0):
    tag = Image.open(UI / "tag_small.png").convert("RGBA")
    scale = TAG_SCALE
    tag = tag.resize((int(tag.width * scale), int(tag.height * scale)), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(tag)
    # Якоря line1/line2 из ui_ch1.json, умноженные на масштаб бирки.
    draw.text((139 * scale, 55.9 * scale), line1, font=fit_line(
        draw, line1, FONTS / "YesevaOne.ttf", int(50 * scale * 0.62), 168 * scale, BROWN),
        fill=BROWN, anchor="mm")
    draw.text((139 * scale, 94.8 * scale), line2, font=fit_line(
        draw, line2, FONTS / "Kurale.ttf", int(38 * scale * 0.62), 168 * scale, BROWN),
        fill=(69, 46, 28, 216), anchor="mm")
    if dim:
        tag = ImageEnhance.Brightness(tag).enhance(1.15)
        alpha = tag.split()[-1].point(lambda v: int(v * 0.62))
        tag.putalpha(alpha)
    if rotation:
        tag = tag.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
    paste_rgba(base, tag, (center[0] - tag.width / 2, center[1] - tag.height / 2))


def icon_state(image, kind):
    image = image.convert("RGBA")
    if kind == "visited":
        return image
    arr = np.array(image).astype(np.float32)
    gray = arr[:, :, :3].mean(axis=2, keepdims=True)
    if kind == "next":
        rgb = gray * 0.55 + arr[:, :, :3] * 0.45
        rgb = np.clip(rgb + 12, 0, 255)
        alpha = arr[:, :, 3:4] * 0.78
    else:
        rgb = np.repeat(gray * 0.75 + 28, 3, axis=2)
        alpha = arr[:, :, 3:4] * 0.42
    out = np.concatenate([np.clip(rgb, 0, 255), np.clip(alpha, 0, 255)], axis=2)
    return Image.fromarray(np.ascontiguousarray(out.astype(np.uint8)), "RGBA")


def paste_icon(base, path, place, kind):
    image = icon_state(Image.open(path), kind)
    image = image.resize((int(round(place["w"])), int(round(place["h"]))), Image.Resampling.LANCZOS)
    paste_rgba(base, image, (place["x"] - place["w"] / 2, place["y"] - place["h"]))


def draw_dashes(draw, points, color=(204, 61, 36, 255)):
    if len(points) < 2:
        return
    span = 0.0
    for a, b in zip(points, points[1:]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        steps = max(1, int(length / 8))
        for i in range(steps):
            t0 = i / steps
            t1 = min(1, (i + 0.45) / steps)
            if int(span / 30) % 2 == 0:
                p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
                p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
                draw.line([p0, p1], fill=color, width=10)
            span += length / steps


def stake(base, xy, lit):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    fill = (89, 59, 33, 255) if lit else (171, 150, 125, 255)
    inner = (214, 171, 97, 255) if lit else (224, 212, 191, 255)
    x, y = xy
    d.ellipse((x - 13, y - 13, x + 13, y + 13), fill=fill)
    d.ellipse((x - 8, y - 9, x + 4, y + 3), fill=inner)
    base.alpha_composite(layer)


def blend_progress(color, pencil, field_img, t0, soft):
    c = np.array(color.convert("RGB")).astype(np.float32)
    p = np.array(pencil.resize(color.size).convert("RGB")).astype(np.float32)
    f = np.array(field_img.resize(color.size, Image.Resampling.BILINEAR)).astype(np.float32) / 255.0
    decoded = 1.3 * f + (-0.1)
    mask = np.clip((t0 + soft - decoded) / soft, 0, 1)[..., None]
    out = c * mask + p * (1 - mask)
    return Image.fromarray(out.round().astype(np.uint8), "RGB")


def main():
    MAP.mkdir(parents=True, exist_ok=True)
    artist = json.loads((SRC / "mountains.json").read_text(encoding="utf-8"))
    shutil.copy2(SRC / "mountains_color.jpg", MAP / "mountains_color.jpg")
    for name in NAMES:
        shutil.copy2(SRC / f"icon_{name}.png", MAP / f"icon_{name}.png")

    road = artist["road"]
    cum = cumulative(road)
    print("arc", round(cum[-1], 2), "points", len(road))
    field_img, field, length = encode_field(road)
    field_img.save(MAP / "mountains_field.png")
    color = Image.open(MAP / "mountains_color.jpg")
    pencil = pencil_from_color(color)
    pencil.save(MAP / "mountains_pencil.jpg", quality=90)
    puffs = puff_rows(field)
    places = []
    for raw in artist["settlements"]:
        w, h = raw["iconSize"]
        x, y = raw["anchor"]
        places.append({
            "id": raw["id"],
            "name": NAMES[raw["id"]],
            "step": raw["step"],
            "road": raw["road"],
            "icon": f"UI/map/icon_{raw['id']}",
            "x": x,
            "y": y,
            "w": w,
            "h": h,
        })
    doc = {
        "_comment": "Цвет и якоря — сдача v2. Поле — кодировка Долины, не полоса из архива. Карандаш выведен из цвета v2.",
        "size": [W, H],
        "lengthSteps": 25000,
        "globalStart": 20000,
        "join": [705.8, 2452.0],
        "roadLength": round(length, 1),
        "road": road,
        "aheadPx": 230.0,
        "softPx": 150.0,
        "field": {"image": "UI/map/mountains_field.png", "decodeScale": 1.3, "decodeBias": -0.1},
        "puffs": {
            "levels": 120,
            "maxT": 1.1,
            "image": "UI/map/fog",
            "aspect": round(247 / 360, 4),
            "points": puffs,
        },
        "settlements": places,
    }
    (MAP / "mountains.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    hero = point_at(road, cum, 2419 / 25000)
    print("hero", [round(v, 1) for v in hero])
    tags, you = layout_tags(places, hero, True, 2419, "gar")
    for place in places:
        r = (place["x"] - place["w"] / 2, place["y"] - place["h"], place["x"] + place["w"] / 2, place["y"])
        tr = rect_of(tags[place["id"]], TAG_W, TAG_H)
        print(place["id"], "iconR", round(r[2], 1), "tag", [round(v, 1) for v in tags[place["id"]]],
              "tagR", round(tr[2], 1), "inside", 0 <= tr[0] and tr[2] <= W and 0 <= tr[1] and tr[3] <= H)
    valley = np.array(Image.open(MAP / "map_color.jpg").crop((0, 0, W, 560)).convert("RGB"))
    band = np.array(color.crop((0, 1972, W, 2532)).convert("RGB"))
    print("seam mean abs", round(float(np.abs(valley.astype(np.int16) - band.astype(np.int16)).mean()), 2))

    local = 2419
    t0 = local / 25000 + 230 / length
    soft = 150 / length
    revealed = blend_progress(color, pencil, field_img, t0, soft)
    stack = Image.new("RGBA", (W, int(VALLEY_ORIGIN_Y + H)), (0, 0, 0, 255))
    stack.paste(Image.open(MAP / "map_color.jpg").convert("RGB"), (0, int(VALLEY_ORIGIN_Y)))
    stack.paste(revealed, (0, 0))

    # Облака только на текущем пороге.
    level = int(round(t0 / 1.1 * 120))
    level = min(max(level, 0), len(puffs) - 1)
    fog = Image.open(MAP / "fog.png").convert("RGBA")
    for item in puffs[level]:
        fw = int(item[2])
        fh = int(item[2] * 247 / 360)
        sprite = fog.resize((fw, fh), Image.Resampling.LANCZOS)
        if item[3] > 0.5:
            sprite = sprite.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        paste_rgba(stack, sprite, (item[0] - fw / 2, item[1] - fh / 2))

    draw = ImageDraw.Draw(stack)
    valley_map = json.loads((MAP / "map.json").read_text(encoding="utf-8"))
    valley_road = valley_map["road"]
    valley_cum = cumulative(valley_road)
    valley_pts = [point_at(valley_road, valley_cum, i / 80) for i in range(81)]
    valley_pts = [(p[0], p[1] + VALLEY_ORIGIN_Y) for p in valley_pts]
    draw_dashes(draw, valley_pts)
    walked = []
    steps_n = 40
    for i in range(steps_n + 1):
        walked.append(point_at(road, cum, (2419 / 25000) * i / steps_n))
    draw_dashes(draw, walked)

    valley_places = []
    for raw in valley_map["settlements"]:
        valley_places.append({**raw, "y": raw["y"] + VALLEY_ORIGIN_Y,
                              "road": [raw["road"][0], raw["road"][1] + VALLEY_ORIGIN_Y]})
    for place in valley_places:
        paste_icon(stack, MAP / f"icon_{place['id']}.png", place, "visited")
        stake(stack, place["road"], True)
    vtags, _ = layout_tags(
        [{**p, "y": p["y"] - VALLEY_ORIGIN_Y} for p in valley_places],
        (0, -1000), False, 20000, None, frame=(W, H))
    for place in valley_places:
        center = vtags[place["id"]]
        draw_tag(stack, (center[0], center[1] + VALLEY_ORIGIN_Y), place["name"],
                 (grouped(place["step"]) if place["step"] else "старт") + (" ш." if place["step"] else ""),
                 dim=False, rotation=-3 if place["step"] // 100 % 2 == 0 else 3)

    for place in places:
        kind = "next" if place["id"] == "gar" else "ghost"
        paste_icon(stack, MAP / f"icon_{place['id']}.png", place, kind)
        stake(stack, place["road"], False)
        draw_tag(stack, tags[place["id"]], place["name"], grouped(place["step"]) + " ш.",
                 dim=place["id"] != "gar", rotation=-3 if place["step"] // 100 % 2 == 0 else 3)
    post = Image.open(MAP / "postman.png").convert("RGBA").resize((87, 230), Image.Resampling.LANCZOS)
    paste_rgba(stack, post, (hero[0] + 4 - 43, hero[1] + 14 - 230))
    draw_tag(stack, you, "Вы здесь", grouped(2419) + " ш.", dim=False, rotation=5)

    OUT.mkdir(parents=True, exist_ok=True)
    stack.convert("RGB").save(OUT / "mountains_valley_full.jpg", quality=86)
    # Телефон: вертикально к герою, по горизонтали лист не сдвигается (ширина кадра = ширина листа).
    top = int(round(-(H / 2 - hero[1])))
    phone = stack.crop((0, top, W, top + H)).convert("RGBA")
    draw_phone_chrome(phone)
    phone.convert("RGB").save(OUT / "mountains_phone_hero.jpg", quality=88)
    stack.crop((0, 1900, W, 2400)).convert("RGB").save(OUT / "mountains_detail_gar.jpg", quality=90)
    stack.crop((0, 850, W, 1400)).convert("RGB").save(OUT / "mountains_detail_repka_krivulya.jpg", quality=90)
    stack.crop((520, 1180, W, 1750)).convert("RGB").save(OUT / "mountains_detail_khomut.jpg", quality=90)
    shutil.copy2(MAP / "map_pencil.jpg", OUT / "valley_map_pencil.jpg")
    shutil.copy2(MAP / "map.json", OUT / "valley_map.json")
    print("wrote", OUT)


def draw_phone_chrome(phone):
    plaque = Image.open(UI / "plaque.png").convert("RGBA")
    scale = 520 / 660
    plaque = plaque.resize((int(plaque.width * scale), int(plaque.height * scale)), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(plaque)
    draw.text((310 * scale, 150 * scale), "Горы", font=font(FONTS / "YesevaOne.ttf", int(64 * scale)),
              fill=BROWN, anchor="mm")
    draw.text((310 * scale, 210 * scale), "глава 2", font=font(FONTS / "Kurale.ttf", int(32 * scale)),
              fill=BROWN, anchor="mm")
    # Центр тела таблички в (300, 250). Тело: x24 y24 w572 h305, центр (310, 176.5).
    body_cx, body_cy = 310 * scale, 176.5 * scale
    paste_rgba(phone, plaque, (300 - body_cx, 250 - body_cy))

    compass = Image.open(MAP / "compass.png").convert("RGBA").resize((210, 215), Image.Resampling.LANCZOS)
    paste_rgba(phone, compass, (1010 - 105, 300 - 107))
    cdraw = ImageDraw.Draw(phone)
    cdraw.text((1010, 300 - 107 - 26), "С", font=font(FONTS / "YesevaOne.ttf", 36), fill=BROWN, anchor="mm")

    tag = Image.open(UI / "tag.png").convert("RGBA")
    tscale = 420 / 437
    tag = tag.resize((int(tag.width * tscale), int(tag.height * tscale)), Image.Resampling.LANCZOS)
    tag = tag.rotate(3, expand=True, resample=Image.Resampling.BICUBIC)
    tdraw = ImageDraw.Draw(tag)
    tdraw.text((tag.width / 2, tag.height * 0.38), f"{grouped(2419)} из {grouped(25000)}",
               font=font(FONTS / "YesevaOne.ttf", 28), fill=BROWN, anchor="mm")
    tdraw.text((tag.width / 2, tag.height * 0.58), "шаг 2 419",
               font=font(FONTS / "Kurale.ttf", 22), fill=BROWN, anchor="mm")
    paste_rgba(phone, tag, (300 - tag.width / 2, 2380 - tag.height / 2))

    arrow = Image.open(UI / "arrow.png").convert("RGBA")
    adraw = ImageDraw.Draw(arrow)
    adraw.text((188, 126), "Закрыть", font=font(FONTS / "YesevaOne.ttf", 42), fill=CHALK, anchor="mm")
    # Правый нижний угол тела (350×197 внутри 438×293) в (1136, 2470).
    paste_rgba(phone, arrow, (1136 - 350 - 24, 2470 - 197 - 24))


if __name__ == "__main__":
    main()
