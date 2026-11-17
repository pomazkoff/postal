#!/usr/bin/env python3
"""Offline composites of the marsh sheet. Not a device, not a save, not a build."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "Postman/GameAssets/UI/map"
OUT = Path("/opt/cursor/artifacts/chapter3")
OUT.mkdir(parents=True, exist_ok=True)


def road_point(road, fraction):
    pts = [np.array(p, dtype=float) for p in road]
    lengths = [0.0]
    for a, b in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + float(np.hypot(*(b - a))))
    total = lengths[-1] or 1
    target = min(1, max(0, fraction)) * total
    for i in range(1, len(lengths)):
        if lengths[i] >= target:
            span = lengths[i] - lengths[i - 1] or 1
            t = (target - lengths[i - 1]) / span
            return pts[i - 1] * (1 - t) + pts[i] * t
    return pts[-1]


def _ridge(row, hint, gold):
    x0, x1 = max(1, hint - 80), min(len(row) - 2, hint + 80)
    if x0 >= x1:
        return hint, 18
    r, g, b = row[:, 0], row[:, 1], row[:, 2]
    score = (r - b) if gold else (r + g + b) / 3
    window = score[x0:x1 + 1]
    best = x0 + int(np.argmax(window))
    base = float(window.mean())
    peak = float(score[best])
    thr = base + 0.45 * (peak - base)
    left = best
    while left > 1 and score[left] > thr:
        left -= 1
    right = best
    while right < len(row) - 2 and score[right] > thr:
        right += 1
    return best, max(14, min(26, (right - left) // 2))


def _x_at(line, y):
    for a, b in zip(line, line[1:]):
        span = b[1] - a[1]
        if abs(span) < 0.01:
            continue
        t = (y - a[1]) / span
        if 0 <= t <= 1:
            return a[0] + (b[0] - a[0]) * t
    return min(line, key=lambda p: abs(p[1] - y))[0]


def seam(image, road, mountain, lift, mountain_road=None):
    """Fade the marsh into the peaks and slide its road onto the mountain road."""
    arr = np.array(image.convert("RGBA")).astype(np.float32)
    base = arr.copy()
    mount = np.array(mountain.convert("RGBA")).astype(np.float32)
    h, w = arr.shape[:2]
    fade = 420
    y0 = max(0, h - fade)
    lift_y = int(round(lift * h / 2532))
    if mountain_road is None:
        mountain_road = road
    for y in range(y0, h):
        design_y = y * 2532 / h
        sw_x = _x_at(road, design_y) * w / 1170
        mt_x = _x_at(mountain_road, design_y - lift) * w / 1170
        t = (y - y0) / max(1, fade - 1)
        s = t * t * (3 - 2 * t)
        align_t = min(1.0, t / 0.55)
        align = align_t * align_t * (3 - 2 * align_t)
        dest = sw_x + (mt_x - sw_x) * align
        half = 19 + (21 - 19) * align
        road_px = int(np.clip(round(sw_x), 0, w - 1))
        keep = 24
        strip = np.stack([
            arr[y, int(np.clip(road_px + dx, 0, w - 1))]
            for dx in range(-keep, keep + 1)
        ])
        haze_x = int(np.clip(round(sw_x) - 48, 0, w - 1))
        erase = int(round(half)) + 8
        for dx in range(-erase, erase + 1):
            x = int(round(sw_x)) + dx
            if 0 <= x < w:
                base[y, x] = base[y, haze_x]
        a = 1 - s
        arr[y] = base[y]
        arr[y, :, :3] *= a
        arr[y, :, 3] = a * 255
        my = y - lift_y
        if my < 0 or my >= mount.shape[0]:
            continue
        edge = 3.0
        reach = int(round(half + edge))
        for dx in range(-reach, reach + 1):
            x = int(round(dest)) + dx
            if x < 0 or x >= w:
                continue
            along = dx / half if half else 0
            sample_x = int(np.clip(round(mt_x + along * 21), 0, w - 1))
            sample_y = int(np.clip(max(my, 401), 0, mount.shape[0] - 1))
            src_dx = int(np.clip(round(along * 19), -keep, keep))
            src = strip[src_dx + keep, :3]
            mixed = src * (1 - s) + mount[sample_y, sample_x, :3] * s
            dist = abs(dx)
            edge_a = 1.0 if dist <= half else max(0.0, 1 - (dist - half) / edge)
            arr[y, x, :3] = arr[y, x, :3] * (1 - edge_a) + mixed * edge_a
            arr[y, x, 3] = arr[y, x, 3] * (1 - edge_a) + 255 * edge_a
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def main():
    swamps = json.loads((MAP / "swamps.json").read_text(encoding="utf-8"))
    mountains = json.loads((MAP / "mountains.json").read_text(encoding="utf-8"))
    valley = json.loads((MAP / "map.json").read_text(encoding="utf-8"))
    swamp_im = Image.open(MAP / "swamps_color.jpg").convert("RGBA")
    mountain_im = Image.open(MAP / "mountains_color.jpg").convert("RGBA")
    valley_im = Image.open(MAP / "valley_color.jpg").convert("RGBA") if (MAP / "valley_color.jpg").exists() else None
    if valley_im is None:
        for name in ("map_color.jpg", "color.jpg", "parchment_color.jpg"):
            if (MAP / name).exists():
                valley_im = Image.open(MAP / name).convert("RGBA")
                break
    end = mountains["road"][-1]
    lift = int(round(swamps["join"][1] - end[1]))
    overlap = swamp_im.height - lift
    swamp_im = seam(swamp_im, swamps["road"], mountain_im, lift, mountains["road"])
    height = lift + mountain_im.height
    canvas_h = height
    sheet = Image.new("RGBA", (1170, canvas_h), (232, 220, 196, 255))
    sheet.paste(mountain_im, (0, lift), mountain_im)
    if valley_im is not None:
        valley_y = lift + int(round(2452 - 480))
        sheet.paste(valley_im, (0, valley_y), valley_im)
    sheet.paste(swamp_im, (0, 0), swamp_im)

    font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", 28)
    frames = {
        45000: "world step 45 000 · start of the marshes, the join",
        54000: "world step 54 000 · the Mire",
        75000: "world step 75 000 · the Settling Pool",
    }
    for step, caption in frames.items():
        local = min(30000, step - 45000)
        point = road_point(swamps["road"], local / 30000)
        hero = (float(point[0]), float(point[1]))
        view = sheet.copy()
        draw = ImageDraw.Draw(view)
        x, y = hero
        draw.ellipse((x - 18, y - 46, x + 18, y + 6), fill=(140, 48, 36, 255))
        top = int(max(0, min(canvas_h - 2532, y - 1400)))
        crop = view.crop((0, top, 1170, top + 2532))
        plate = Image.new("RGBA", (1170, 2532), (0, 0, 0, 0))
        d = ImageDraw.Draw(plate)
        d.rectangle((24, 24, 1146, 110), fill=(40, 28, 18, 210))
        d.text((40, 40), "OFFLINE composite · not a device · not a save", fill=(244, 232, 210, 255), font=font)
        d.text((40, 68), caption, fill=(244, 232, 210, 255), font=font)
        crop = Image.alpha_composite(crop.convert("RGBA"), plate)
        path = OUT / f"map_{step}.jpg"
        crop.convert("RGB").save(path, quality=85)
        print(path, "hero", round(x, 1), round(y, 1), "lift", lift, "overlap", overlap)

    card = Image.new("RGB", (900, 1200), (236, 224, 198))
    d = ImageDraw.Draw(card)
    d.text((40, 36), "OFFLINE card · not a device", fill=(40, 28, 18), font=font)
    d.text((40, 80), "Письмо 1 · Галя → Митя · текст из правки", fill=(40, 28, 18), font=font)
    body = (
        "Митюша, купила крючки, те самые тонкие,\n"
        "что ты просил на плотву. Деду не говори,\n"
        "а то скажет, рано ещё, сам куплю."
    )
    d.multiline_text((40, 140), body, fill=(40, 28, 18), font=font, spacing=8)
    d.rounded_rectangle((40, 980, 860, 1080), radius=16, fill=(90, 58, 36))
    d.text((70, 1010), "В ящик на Гати, оказия вниз", fill=(244, 232, 210), font=font)
    card.save(OUT / "letter_l1.jpg", quality=85)

    choice = Image.new("RGB", (900, 900), (236, 224, 198))
    d = ImageDraw.Draw(choice)
    d.text((40, 36), "OFFLINE choice · not a device", fill=(40, 28, 18), font=font)
    d.text((40, 90), "Настил в тумане", fill=(40, 28, 18), font=font)
    d.multiline_text((40, 160), "Жерди уходят в туман.\nДлина пути одна и та же.", fill=(40, 28, 18), font=font, spacing=8)
    d.rounded_rectangle((40, 360, 860, 470), radius=16, fill=(90, 58, 36))
    d.text((70, 396), "Идти по жердям", fill=(244, 232, 210), font=font)
    d.rounded_rectangle((40, 500, 860, 610), radius=16, fill=(214, 198, 168))
    d.text((70, 536), "Ступить в кочки", fill=(40, 28, 18), font=font)
    choice.save(OUT / "choice_fog.jpg", quality=85)
    print("cards written")
    taps = json.loads((ROOT / "Postman/GameAssets/Data/chapter3_taps.json").read_text(encoding="utf-8"))
    shown = ["frog1", "heron", "bubble1", "boat", "barge", "bell", "radio", "wall", "kettle", "barrier"]
    sheet = Image.new("RGB", (1100, 980), (236, 224, 198))
    d = ImageDraw.Draw(sheet)
    d.text((36, 28), "OFFLINE taps · not a device · sprites beside the road", fill=(40, 28, 18), font=font)
    for i, tid in enumerate(shown):
        kind = next(t["sprite"].rsplit("/", 1)[-1] for t in taps if t["id"] == tid)
        icon = Image.open(ROOT / "Postman/GameAssets" / f"Chapter3/taps/{kind}.png").convert("RGBA")
        icon.thumbnail((150, 120))
        col, row = i % 5, i // 5
        x, y = 40 + col * 210, 120 + row * 400
        sheet.paste(icon, (x, y), icon)
        d.text((x, y + 140), tid, fill=(40, 28, 18), font=font)
    sheet.save(OUT / "taps.jpg", quality=85)
    gift = Image.new("RGB", (900, 700), (236, 224, 198))
    d = ImageDraw.Draw(gift)
    d.text((40, 36), "OFFLINE handoff · not a device", fill=(40, 28, 18), font=font)
    d.text((40, 100), "Кромка марки", fill=(40, 28, 18), font=font)
    d.multiline_text((40, 170), "Оставить в ящике на Гати\nдля деда Феди.\nЯщик ещё впереди.", fill=(40, 28, 18), font=font, spacing=10)
    d.rounded_rectangle((40, 460, 860, 580), radius=16, fill=(90, 58, 36))
    d.text((70, 500), "В ящик на Гати, для деда Феди", fill=(244, 232, 210), font=font)
    gift.save(OUT / "gift_edge.jpg", quality=85)
    print("taps and gift")


if __name__ == "__main__":
    main()
