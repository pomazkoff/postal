#!/usr/bin/env python3
"""Сборка превью карточки из игровых PNG и шрифтов. Это не кадр симулятора."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "Postman/GameAssets"
FONTS = ASSETS / "Fonts"
OUT = Path("/opt/cursor/artifacts")
W, H = 1170, 2532


def load(path):
    return Image.open(path).convert("RGBA")


def paste(base, im, xy):
    base.alpha_composite(im, (int(round(xy[0])), int(round(xy[1]))))


def wrap(draw, text, font, width):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_center(draw, lines, font, box, fill, gap):
    heights = [font.getbbox(line)[3] - font.getbbox(line)[1] for line in lines]
    block = sum(heights) + gap * (len(lines) - 1)
    y = box[1] + (box[3] - box[1] - block) / 2
    cx = box[0] + box[2] / 2
    for line, h in zip(lines, heights):
        tw = draw.textlength(line, font=font)
        draw.text((cx - tw / 2, y), line, font=font, fill=fill)
        y += h + gap


def journey(lang):
    if lang == "ru":
        title, soon, onward = "Путешествие почтальона продолжится", "Глава 3 скоро", "В путь"
        title_font = ImageFont.truetype(str(FONTS / "YesevaOne.ttf"), 56)
        soon_font = ImageFont.truetype(str(FONTS / "Kurale.ttf"), 40)
        arrow_font = ImageFont.truetype(str(FONTS / "YesevaOne.ttf"), 44)
    else:
        title, soon, onward = "The postman's journey will continue", "Chapter 3 is coming soon", "Onward"
        title_font = ImageFont.truetype(str(FONTS / "YesevaOne.ttf"), 52)
        soon_font = ImageFont.truetype(str(FONTS / "Kurale.ttf"), 36)
        arrow_font = ImageFont.truetype(str(FONTS / "YesevaOne.ttf"), 40)

    base = Image.new("RGBA", (W, H), (8, 23, 26, 255))
    postman = load(ASSETS / "UI/map/postman.png")
    ph = 1240
    pw = int(round(postman.width * ph / postman.height))
    postman = postman.resize((pw, ph), Image.Resampling.LANCZOS)
    paste(base, postman, (585 - pw / 2, 860 - ph / 2))

    sheet = load(ASSETS / "UI/ch1/sheet.png")
    scale = 0.6
    sw, sh = int(round(sheet.width * scale)), int(round(sheet.height * scale))
    sheet = sheet.resize((sw, sh), Image.Resampling.LANCZOS)
    sx, sy = 585 - sw / 2, 1880 - sh / 2
    paste(base, sheet, (sx, sy))

    # Текст в рамке textTL…textBR листа.
    tx, ty = sx + 116 * scale, sy + 120 * scale
    tw, th = (898 - 116) * scale, (1219 - 120) * scale
    draw = ImageDraw.Draw(base)
    title_lines = wrap(draw, title, title_font, tw - 8)
    soon_lines = wrap(draw, soon, soon_font, tw - 8)
    gap = 22
    block_h = 0
    chunks = [(title_lines, title_font, (69, 46, 28, 255), 8),
              (soon_lines, soon_font, (59, 56, 61, 255), 6)]
    for lines, font, _, line_gap in chunks:
        for line in lines:
            block_h += font.getbbox(line)[3] - font.getbbox(line)[1] + line_gap
        block_h += gap
    y = ty + (th - block_h) / 2
    for lines, font, fill, line_gap in chunks:
        for line in lines:
            h = font.getbbox(line)[3] - font.getbbox(line)[1]
            draw.text((tx + (tw - draw.textlength(line, font=font)) / 2, y), line, font=font, fill=fill)
            y += h + line_gap
        y += gap

    arrow = load(ASSETS / "UI/ch1/arrow.png")
    # Низ корпуса стрелки выше типичного домашнего индикатора (~34 pt на телефоне кадра).
    arrow_bottom = min(2460, 2532 - 102 - 16)
    body_br = (24 + 350, 24 + 197)
    ax = 1136 - body_br[0]
    ay = arrow_bottom - body_br[1]
    paste(base, arrow, (ax, ay))
    draw = ImageDraw.Draw(base)
    aw = draw.textlength(onward, font=arrow_font)
    draw.text((ax + 188.5 - aw / 2, ay + 126.4 - 22), onward, font=arrow_font, fill=(242, 235, 214, 255))

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"chapter2_journey_card_{lang}.png"
    base.convert("RGB").save(path, quality=95)
    return path


def menu():
    """Макет открытого меню: фон размыт, бумага резкая. Не кадр с устройства."""
    night = Image.new("RGBA", (W, H), (12, 28, 48, 255))
    bag = load(ASSETS / "UI/ch1/hud_bag.png")
    map_im = load(ASSETS / "UI/ch1/hud_map.png")
    telegram = load(ASSETS / "UI/ch1/sheet_telegram.png")
    tag_small = load(ASSETS / "UI/ch1/tag_small.png")
    # То, что мешало на скриншоте, уходит под размытие.
    paste(night, telegram.resize((520, 640), Image.Resampling.LANCZOS), (620, 80))
    paste(night, tag_small.resize((300, 210), Image.Resampling.LANCZOS), (40, 80))
    paste(night, bag, (60, 2214))
    paste(night, map_im, (839, 2214))
    blurred = night.filter(ImageFilter.GaussianBlur(radius=16))
    dim = Image.new("RGBA", (W, H), (8, 23, 26, 40))
    blurred.alpha_composite(dim)

    plaque = load(ASSETS / "UI/ch1/plaque.png").resize((330, 200), Image.Resampling.LANCZOS)
    paste(blurred, plaque, (585 - 165, 292 - 100))
    title_font = ImageFont.truetype(str(FONTS / "YesevaOne.ttf"), 54)
    draw = ImageDraw.Draw(blurred)
    label = "Меню"
    draw.text((585 - draw.textlength(label, font=title_font) / 2, 292 - 28), label,
              font=title_font, fill=(69, 46, 28, 255))

    tag = load(ASSETS / "UI/ch1/tag.png")
    scale = 1.08
    tw, th = int(round(tag.width * scale)), int(round(tag.height * scale))
    tag_r = tag.resize((tw, th), Image.Resampling.LANCZOS)
    gap = 22
    first_y = 420 + 16 + th / 2
    grid_w = 2 * tw + gap
    left = (W - grid_w) / 2 + tw / 2
    names = ["Сейчас в пути", "Кого встретил", "Об игре", "Настройки"]
    tab_font = ImageFont.truetype(str(FONTS / "YesevaOne.ttf"), 42)
    for i, name in enumerate(names):
        col, row = i % 2, i // 2
        cx = left + col * (tw + gap)
        cy = first_y + row * (th + gap)
        paste(blurred, tag_r, (cx - tw / 2, cy - th / 2))
        draw = ImageDraw.Draw(blurred)
        text_w = 276 * scale
        lines = wrap(draw, name, tab_font, text_w)
        block = sum(tab_font.getbbox(line)[3] for line in lines) + 6 * (len(lines) - 1)
        y = cy - block / 2
        for line in lines:
            lw = draw.textlength(line, font=tab_font)
            draw.text((cx - lw / 2, y), line, font=tab_font, fill=(69, 46, 28, 255))
            y += tab_font.getbbox(line)[3] + 6

    sheet = load(ASSETS / "UI/ch1/sheet.png")
    ss = 0.58
    sw, sh = int(round(sheet.width * ss)), int(round(sheet.height * ss))
    sheet = sheet.resize((sw, sh), Image.Resampling.LANCZOS)
    tabs_bottom = first_y + (th + gap) + th / 2
    sheet_y = min(tabs_bottom + 28 + sh / 2, 1888)
    paste(blurred, sheet, (585 - sw / 2, sheet_y - sh / 2))
    hand = ImageFont.truetype(str(FONTS / "Neucha.ttf"), 42)
    head = ImageFont.truetype(str(FONTS / "YesevaOne.ttf"), 40)
    tx = 585 - sw / 2 + 116 * ss
    ty = sheet_y - sh / 2 + 150 * ss
    draw = ImageDraw.Draw(blurred)
    draw.text((tx, ty), "Сейчас в пути", font=head, fill=(69, 46, 28, 255))
    quest = "Донести письмо Нины до ящика на Седле"
    y = ty + 70
    for line in wrap(draw, quest, hand, (898 - 116) * ss):
        draw.text((tx, y), line, font=hand, fill=(59, 56, 61, 255))
        y += 48

    small = load(ASSETS / "UI/ch1/tag_small.png")
    small = small.resize((int(287 * 0.92), int(201 * 0.92)), Image.Resampling.LANCZOS)
    for caption, pos in (("Карта", (250, 2036)), ("Сумка", (920, 2036))):
        paste(blurred, small, (pos[0] - small.width / 2, pos[1] - small.height / 2))
        draw = ImageDraw.Draw(blurred)
        f = ImageFont.truetype(str(FONTS / "YesevaOne.ttf"), 36)
        draw.text((pos[0] - draw.textlength(caption, font=f) / 2, pos[1] - 24), caption,
                  font=f, fill=(69, 46, 28, 255))

    arrow = load(ASSETS / "UI/ch1/arrow.png")
    ax, ay = 1136 - (24 + 350), 2460 - (24 + 197)
    paste(blurred, arrow, (ax, ay))
    draw = ImageDraw.Draw(blurred)
    f = ImageFont.truetype(str(FONTS / "YesevaOne.ttf"), 40)
    word = "В путь"
    draw.text((ax + 188.5 - draw.textlength(word, font=f) / 2, ay + 104), word,
              font=f, fill=(242, 235, 214, 255))

    # Бирка «Меню» между сумкой и картой на размытом слое уже не нужна:
    # при открытом меню её закрывает этот экран. На превью её нет специально.

    path = OUT / "menu_open_layout_ru.png"
    blurred.convert("RGB").save(path, quality=95)
    return path


def menu_button():
    """Закрытый низ экрана: бирка «Меню» в зазоре сумки и карты. Не кадр с устройства."""
    base = Image.new("RGBA", (W, 520), (28, 22, 18, 255))
    bag = load(ASSETS / "UI/ch1/hud_bag.png")
    map_im = load(ASSETS / "UI/ch1/hud_map.png")
    # В кадре 2532 низ обрезан до полосы: y 2100…2532 → 0…432, плюс поля.
    shift = 2060

    def place(im, anchor_xy, body_center):
        x = anchor_xy[0] - body_center[0]
        y = anchor_xy[1] - body_center[1] - shift
        paste(base, im, (x, y))

    place(bag, (190, 2330), (24 + 213 / 2, 24 + 185 / 2))
    place(map_im, (990, 2330), (24 + 254 / 2, 24 + 185 / 2))
    tag = load(ASSETS / "UI/ch1/tag_small.png")
    scale = 1.22
    tw, th = int(round(tag.width * scale)), int(round(tag.height * scale))
    tag = tag.resize((tw, th), Image.Resampling.LANCZOS)
    bag_r = (190 - (24 + 213 / 2), 2330 - (24 + 185 / 2), bag.width, bag.height)
    map_r = (990 - (24 + 254 / 2), 2330 - (24 + 185 / 2), map_im.width, map_im.height)
    cx = bag_r[0] + bag_r[2] + (map_r[0] - (bag_r[0] + bag_r[2])) / 2
    cy = (bag_r[1] + bag_r[3] / 2 + map_r[1] + map_r[3] / 2) / 2
    safe = 110
    if cy + th / 2 > 2532 - safe - 12:
        cy = 2532 - safe - 12 - th / 2
    paste(base, tag, (cx - tw / 2, cy - th / 2 - shift))
    draw = ImageDraw.Draw(base)
    font = ImageFont.truetype(str(FONTS / "YesevaOne.ttf"), 48)
    word = "Меню"
    draw.text((cx - draw.textlength(word, font=font) / 2, cy - shift - 30), word,
              font=font, fill=(69, 46, 28, 255))
    path = OUT / "menu_button_between_bag_and_map.png"
    base.convert("RGB").save(path, quality=95)
    return path


if __name__ == "__main__":
    print(journey("ru"))
    print(journey("en"))
    print(menu())
    print(menu_button())
