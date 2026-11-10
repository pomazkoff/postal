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


def fade_bottom(image, band):
    arr = np.array(image.convert("RGBA"))
    h = arr.shape[0]
    clear = min(band, int(round(h * 352 / 2532)))
    start = max(0, h - band)
    end = max(start, h - clear)
    ramp = np.linspace(1, 0, max(1, end - start), dtype=np.float32)
    arr[start:end, :, 3] = (arr[start:end, :, 3].astype(np.float32) * ramp[:, None]).astype(np.uint8)
    arr[end:, :, 3] = 0
    return Image.fromarray(arr)


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
    # The painted parchment edge sits at the top of the 560 px overlap, so the ramp
    # starts higher. Otherwise that edge stays opaque and reads as a cut.
    swamp_im = fade_bottom(swamp_im, overlap + 320)
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


if __name__ == "__main__":
    main()
