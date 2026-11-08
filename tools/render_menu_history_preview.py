#!/usr/bin/env python3
"""Компоновка меню и истории из игровых PNG. Не кадр симулятора."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "Postman/GameAssets/UI/ch1"
FONT = ROOT / "Postman/GameAssets/Fonts"
OUT = Path("/opt/cursor/artifacts/menu-history-preview")
W, H = 1170, 2532
BROWN = (69, 46, 28, 255)
PENCIL = (59, 56, 61, 255)


def font(name, size):
    return ImageFont.truetype(str(FONT / name), size)


def paste(base, name, xy, scale=1.0, flip=False):
    im = Image.open(UI / name).convert("RGBA")
    if scale != 1:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.Resampling.LANCZOS)
    if flip:
        im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    base.alpha_composite(im, (int(xy[0]), int(xy[1])))
    return im


def wrap(draw, text, face, width):
    lines, cur = [], ""
    for word in text.split():
        trial = word if not cur else cur + " " + word
        if draw.textlength(trial, font=face) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    story = json.loads((ROOT / "Postman/GameAssets/Data/chapter1_story.json").read_text(encoding="utf-8"))
    sample = story["arrivals"][0]["text"]

    menu = Image.new("RGBA", (W, H), (28, 36, 42, 255))
    draw = ImageDraw.Draw(menu)
    draw.text((40, 24), "вёрстка из ассетов, не кадр симулятора", font=font("Kurale.ttf", 28), fill=(230, 220, 200, 255))
    plaque = paste(menu, "plaque.png", (255, 70), 0.5)
    d = ImageDraw.Draw(menu)
    d.text((585, 70 + plaque.height * 0.42), "Меню", font=font("YesevaOne.ttf", 42), fill=BROWN, anchor="mm")
    # Четыре бирки чуть меньше прежних 1.08.
    tags = [("Сейчас\nв пути", 180, 430), ("Кого\nвстретил", 620, 430),
            ("Об игре", 180, 760), ("Настройки", 620, 760)]
    for title, x, y in tags:
        paste(menu, "tag.png", (x, y), 0.88)
        d.multiline_text((x + 190, y + 110), title, font=font("YesevaOne.ttf", 36), fill=BROWN, anchor="mm", align="center")
    sheet = paste(menu, "sheet.png", (80, 980), 0.96)
    d.text((160, 1120), "Сейчас в пути", font=font("YesevaOne.ttf", 54), fill=BROWN)
    d.text((160, 1210), "Перевал Хомут — темп", font=font("Neucha.ttf", 48), fill=PENCIL)
    d.text((160, 1290), "Лист выше и шире.\nДлинный текст уходит в прокрутку.", font=font("Neucha.ttf", 40), fill=PENCIL)
    paste(menu, "tag_small.png", (80, 2320), 0.9)
    d.text((200, 2390), "Карта", font=font("YesevaOne.ttf", 32), fill=BROWN)
    paste(menu, "tag_small.png", (760, 2320), 0.9)
    d.text((900, 2390), "Сумка", font=font("YesevaOne.ttf", 32), fill=BROWN)
    menu.convert("RGB").save(OUT / "menu_larger_sheet.jpg", quality=88)

    road = Image.new("RGBA", (W, H), (36, 48, 52, 255))
    rd = ImageDraw.Draw(road)
    rd.text((40, 24), "вёрстка из ассетов, не кадр симулятора", font=font("Kurale.ttf", 28), fill=(230, 220, 200, 255))
    paste(road, "hud_bag.png", (40, 2050))
    paste(road, "hud_map.png", (820, 2050))
    paste(road, "tag_small.png", (400, 1880), 1.22)
    rd.text((575, 1960), "Меню", font=font("YesevaOne.ttf", 42), fill=BROWN, anchor="mm")
    paste(road, "tag_small.png", (400, 2140), 1.22, flip=True)
    rd.text((575, 2220), "История", font=font("YesevaOne.ttf", 36), fill=BROWN, anchor="mm")
    road.convert("RGB").save(OUT / "road_history_tag.jpg", quality=88)

    hist = Image.new("RGBA", (W, H), (24, 30, 34, 255))
    hd = ImageDraw.Draw(hist)
    hd.rounded_rectangle((50, 40, 1120, 2280), radius=18, fill=(232, 217, 178, 255), outline=(158, 128, 84, 255), width=4)
    paste(hist, "sheet.png", (62, 48), 1.0)
    hd.text((120, 160), "История", font=font("YesevaOne.ttf", 64), fill=BROWN)
    hd.text((120, 250), "Долина", font=font("YesevaOne.ttf", 40), fill=BROWN)
    hd.text((120, 320), "Почта", font=font("YesevaOne.ttf", 48), fill=BROWN)
    hd.text((120, 390), "Почта · шаг 0", font=font("Kurale.ttf", 28), fill=BROWN)
    # Реальная строка прибытия — образец набора, не состояние сейва.
    body = font("Neucha.ttf", 40)
    hd.multiline_text((120, 460), wrap(hd, sample, body, 900), font=body, fill=PENCIL, spacing=8)
    hd.text((120, 2100), "Пример вёрстки одной уже известной строки. Не прохождение.", font=font("Kurale.ttf", 26), fill=BROWN)
    paste(hist, "arrow.png", (700, 2260), 0.85)
    hd.text((900, 2380), "Закрыть", font=font("YesevaOne.ttf", 32), fill=(242, 235, 214, 255))
    hist.convert("RGB").save(OUT / "history_scroll.jpg", quality=88)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
