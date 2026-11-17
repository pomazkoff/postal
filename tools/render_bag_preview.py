#!/usr/bin/env python3
"""Офлайн-склейка сумки. Это не кадр симулятора и не сейв Ильи."""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "Postman/GameAssets/UI/ch1"
FONT = ROOT / "Postman/GameAssets/Fonts"
OUT = Path("/opt/cursor/artifacts/bag-preview")
PAPER = (232, 217, 178, 255)
BROWN = (92, 58, 36, 255)
PENCIL = (92, 58, 36, 210)
BANNER = (120, 36, 28, 255)


def font(name, size):
    return ImageFont.truetype(str(FONT / name), size)


def strings(code):
    text = (ROOT / f"Postman/Resources/{code}.lproj/Localizable.strings").read_text(encoding="utf-8")
    return {k: v for k, v in re.findall(r'"([^"]+)"\s*=\s*"([^"]*)"\s*;', text)}


def fit(draw, face_name, text, width, size):
    face = font(face_name, size)
    while size > 14 and draw.textlength(text, font=face) > width:
        size -= 1
        face = font(face_name, size)
    return face


def tag(line1, line2, scale=0.72):
    base = Image.open(UI / "tag.png").convert("RGBA")
    w, h = int(base.width * scale), int(base.height * scale)
    image = base.resize((w, h), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    face1 = fit(draw, "YesevaOne.ttf", line1, w * 0.62, int(42 * scale))
    face2 = fit(draw, "Neucha.ttf", line2, w * 0.70, int(34 * scale))
    draw.text((w * 0.28, h * 0.22), line1, font=face1, fill=BROWN)
    draw.text((w * 0.18, h * 0.48), line2, font=face2, fill=PENCIL)
    return image


def icon(name, size=120):
    image = Image.open(UI / f"{name}.png").convert("RGBA")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    return image


def row(line1, line2, art):
    label = tag(line1, line2)
    picture = icon(art)
    canvas = Image.new("RGBA", (picture.width + 16 + label.width, max(picture.height, label.height)), (0, 0, 0, 0))
    canvas.paste(picture, (0, (canvas.height - picture.height) // 2), picture)
    canvas.paste(label, (picture.width + 16, (canvas.height - label.height) // 2), label)
    return canvas


def frame(title, rows, note):
    width = 1170
    height = 2532
    image = Image.new("RGBA", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 92), fill=BANNER)
    banner = font("Neucha.ttf", 36)
    draw.text((36, 24), "НЕ КАДР СИМУЛЯТОРА · фикстура, не сейв", font=banner, fill=(255, 244, 220, 255))
    heading = tag(title, note, scale=0.9)
    image.paste(heading, ((width - heading.width) // 2, 140), heading)
    y = 460
    draw.text((80, y), "Почта", font=font("YesevaOne.ttf", 48), fill=BROWN)
    y += 70
    for line1, line2, art in rows[0]:
        item = row(line1, line2, art)
        image.paste(item, (70, y), item)
        y += item.height + 12
    y += 20
    draw.text((80, y), "Личные вещи", font=font("YesevaOne.ttf", 48), fill=BROWN)
    y += 70
    for line1, line2, art in rows[1]:
        item = row(line1, line2, art)
        image.paste(item, (70, y), item)
        y += item.height + 12
    bag = Image.open(UI / "bag_front.png").convert("RGBA")
    bag.thumbnail((520, 520), Image.Resampling.LANCZOS)
    image.paste(bag, ((width - bag.width) // 2, height - bag.height - 80), bag)
    return image.convert("RGB")


def main():
    ru = strings("ru")
    OUT.mkdir(parents=True, exist_ok=True)
    penki = frame(
        ru["bag.title"],
        (
            [("Кадушки", ru["bag.act.2.note_gar"], "env_plain")],
            [(ru["bag.keep.animal_raven_scrap"], ru["bag.look"], "att_wrapper_yellow")],
        ),
        ru["bag.withYou"],
    )
    penki.save(OUT / "bag_penki_mail_and_find.jpg", quality=90)
    many = frame(
        ru["bag.title"],
        (
            [
                ("Кузьме", ru["bag.act.1.l1"], "env_plain"),
                ("Пимену", ru["bag.act.1.l2"], "env_plain"),
                ("Тимофею", ru["bag.act.1.l3"], "env_fat"),
                ("Нине", ru["bag.act.1.l6"], "env_tima"),
                ("Вере", ru["bag.act.1.batteries"], "parcel"),
            ],
            [
                (ru["bag.keep.animal_cat_stamp"], ru["bag.look"], "stamp_violet"),
                (ru["bag.keep.animal_dog_horn"], ru["bag.look"], "pin_red"),
            ],
        ),
        "без обрезки",
    )
    many.save(OUT / "bag_more_than_four.jpg", quality=90)
    print(OUT)


if __name__ == "__main__":
    main()
