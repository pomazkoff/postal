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


def seam(image, road, mountain, lift):
    """Fade the marsh into the peaks. The road stays the swamp's own colour."""
    del mountain, lift
    arr = np.array(image.convert("RGBA")).astype(np.float32)
    base = arr.copy()
    h, w = arr.shape[:2]
    fade = 420
    y0 = max(0, h - fade)
    for y in range(y0, h):
        t = (y - y0) / max(1, fade - 1)
        s = t * t * (3 - 2 * t)
        a = 1 - s
        arr[y, :, :3] *= a
        arr[y, :, 3] = a * 255
    radius = 26
    road_mask = np.zeros((h, w), dtype=bool)

    def stamp(cx, cy):
        x0, x1 = max(0, int(cx) - radius), min(w, int(cx) + radius + 1)
        y0, y1 = max(0, int(cy) - radius), min(h, int(cy) + radius + 1)
        if x0 >= x1 or y0 >= y1:
            return
        xs = np.arange(x0, x1)[None, :]
        ys = np.arange(y0, y1)[:, None]
        road_mask[y0:y1, x0:x1] |= (xs - cx) ** 2 + (ys - cy) ** 2 <= radius ** 2

    prev = np.array(road[0], dtype=float)
    for point in road[::3]:
        point = np.array(point, dtype=float)
        dist = float(np.hypot(*(point - prev)))
        steps = max(1, int(dist / 8))
        for s in range(steps + 1):
            cx, cy = prev + (point - prev) * (s / steps)
            stamp(cx, cy)
        prev = point
    # Дорога держится дольше дымки и к низу полосы отдаёт путь гор.
    if road_mask.any():
        yy = np.arange(h)[:, None]
        t = (yy - y0) / max(1, fade - 1)
        road_t = np.clip((t - 0.35) / 0.65, 0, 1)
        road_s = road_t * road_t * (3 - 2 * road_t)
        road_a = np.where(yy < y0, 1.0, 1 - road_s).astype(np.float32)
        painted = base.copy()
        painted[:, :, :3] *= road_a[:, :, None]
        painted[:, :, 3] = road_a[:, 0] * 255
        arr[road_mask] = painted[road_mask]
    return Image.fromarray(arr.astype(np.uint8))


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
    swamp_im = seam(swamp_im, swamps["road"], mountain_im, lift)
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
