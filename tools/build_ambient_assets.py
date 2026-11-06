#!/usr/bin/env python3
"""Живой мир: атлас облаков/птиц/дыма/звёзд/колокола, кнопка «к почтальону», idle-листы жителей, ambient.json.

Исходники: tools/ambient_src/*_cut.png (fal flux-kontext + birefnet, пластилин; см. README §10),
GameAssets/Chapter1/places/place_zvonarnya_main.png (колокол вырезается, дыра заливается),
/workspace/walking-sim/assets_ch1/residents/<id>/spritesheet.png + rig.json (idle 12 fps).
Пишет:
  Postman/GameAssets/Ambient/ambient_atlas.png + .json
  Postman/GameAssets/Chapter1/places/place_zvonarnya_main_nobell.png
  Postman/GameAssets/UI/ch1/btn_postman.png (+ запись в UI/ui_ch1.json)
  Postman/GameAssets/Chapter1/residents/<id>/spritesheet.png, rig.json (idle)
  Postman/GameAssets/Data/ambient.json
"""
import json, math, os, random, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GA = os.path.join(ROOT, "Postman/GameAssets")
SRC = os.path.join(ROOT, "tools/ambient_src")
RES_SRC = "/workspace/walking-sim/assets_ch1/residents"


def components(path, min_area=4000):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)[:, :, 3]
    lab, n = ndimage.label(a > 24)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        if sl is None:
            continue
        area = int((lab[sl] == i).sum())
        if area < min_area:
            continue
        crop = np.asarray(im)[sl].copy()
        crop[:, :, 3] = np.where(lab[sl] == i, crop[:, :, 3], 0)
        out.append((sl[1].start, Image.fromarray(crop)))
    out.sort(key=lambda t: t[0])
    return [c for _, c in out]


def fit_h(im, h):
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


frames = {}
clouds = components(os.path.join(SRC, "clouds_cut.png"))
for i, c in enumerate(clouds):
    frames["cloud_%d" % i] = fit_h(c, 220)

birds = components(os.path.join(SRC, "birds_cut.png"), 2000)
assert len(birds) >= 2, "ожидались 2 птицы"
b0 = birds[0]                                    # крылья вверх, смотрит вправо
b1 = birds[1].transpose(Image.FLIP_LEFT_RIGHT)   # крылья вниз → тоже вправо
H = 96
b0, b1 = fit_h(b0, H), fit_h(b1, round(H * birds[1].height / birds[0].height))
W2, H2 = max(b0.width, b1.width), max(b0.height, b1.height)
for name, b in (("bird_0", b0), ("bird_1", b1)):
    cv = Image.new("RGBA", (W2, H2))
    cv.alpha_composite(b, (W2 - b.width, H2 - b.height))   # совмещаем клюв и низ брюшка
    frames[name] = cv

for i, c in enumerate(components(os.path.join(SRC, "smoke_cut.png"))):
    frames["smoke_%d" % i] = fit_h(c, 112)

# Звёзды: маленькие пластилиновые «кнопки» (процедурно).
rnd = random.Random(3)
for i, (r, col) in enumerate([(14, (255, 238, 190)), (11, (255, 248, 222)), (9, (240, 226, 255))]):
    s = 48
    im = Image.new("RGBA", (s * 4, s * 4))
    d = ImageDraw.Draw(im)
    pts = []
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        rr = (r * 4) if k % 2 == 0 else (r * 1.7)
        pts.append((s * 2 + math.cos(ang) * rr + rnd.uniform(-3, 3), s * 2 + math.sin(ang) * rr + rnd.uniform(-3, 3)))
    d.polygon(pts, fill=col + (255,))
    im = im.filter(ImageFilter.GaussianBlur(3))
    a = np.asarray(im).copy()
    a[:, :, 3] = np.clip((a[:, :, 3].astype(int) - 60) * 2, 0, 255)
    im = Image.fromarray(a.astype(np.uint8))
    hl = Image.new("RGBA", im.size)
    ImageDraw.Draw(hl).ellipse((s * 2 - r * 1.6, s * 2 - r * 2, s * 2 - r * 0.2, s * 2 - r * 0.7), fill=(255, 255, 255, 150))
    im.alpha_composite(hl.filter(ImageFilter.GaussianBlur(3)))
    frames["star_%d" % i] = im.resize((s, s), Image.LANCZOS)

# Колокол Звонарни: вырезаем (с языком) и заливаем дыру тёмной глубиной арки.
ZV = os.path.join(GA, "Chapter1/places/place_zvonarnya_main.png")
zv = Image.open(ZV).convert("RGBA")
OX, OY = 380, 420
poly = [(165, 82), (205, 82), (232, 110), (245, 150), (258, 205), (275, 232), (272, 264),
        (98, 264), (95, 232), (112, 205), (125, 150), (138, 110)]
mask = Image.new("L", zv.size)
md = ImageDraw.Draw(mask)
md.polygon([(x + OX, y + OY) for x, y in poly], fill=255)
md.rectangle((OX + 158, OY + 255, OX + 210, OY + 322), fill=255)
arr = np.asarray(zv).astype(np.float32)
lum = arr[:, :, :3] @ np.array([0.3, 0.59, 0.11])
m = np.asarray(mask) > 0
bell_m = m & (lum > 72)
bell_m = ndimage.binary_opening(bell_m, iterations=1)
bell_m = ndimage.binary_fill_holes(bell_m)
lab, n = ndimage.label(bell_m)
if n > 1:  # оставляем колокол и язык (самые крупные куски)
    sizes = ndimage.sum(bell_m, lab, range(1, n + 1))
    keep = [i + 1 for i in np.argsort(sizes)[::-1][:2]]
    bell_m = np.isin(lab, keep)
ys, xs = np.nonzero(bell_m)
x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
soft = ndimage.gaussian_filter(bell_m.astype(np.float32), 0.8)
bell = arr[y0:y1, x0:x1].copy()
bell[:, :, 3] = np.minimum(bell[:, :, 3], soft[y0:y1, x0:x1] * 255)
frames["bell_zvon"] = Image.fromarray(bell.astype(np.uint8))
# Дыра: inpaint (OpenCV Telea) по окружению — глубина арки и задняя стена.
import cv2
hole = ndimage.binary_dilation(bell_m, iterations=4)
rgb = np.ascontiguousarray(arr[:, :, :3].astype(np.uint8)[:, :, ::-1])
fill = cv2.inpaint(rgb, (hole * 255).astype(np.uint8), 9, cv2.INPAINT_TELEA)[:, :, ::-1]
patched = arr.copy().astype(np.uint8)
patched[:, :, :3] = np.where(hole[:, :, None], fill, patched[:, :, :3])
patched = Image.fromarray(patched)
patched.save(os.path.join(GA, "Chapter1/places/place_zvonarnya_main_nobell.png"), optimize=True)
hang_src = (565, 508)  # кольцо подвеса в пикселях исходника
bell_info = {"pivot": [hang_src[0], hang_src[1]], "hang": [hang_src[0] - int(x0), hang_src[1] - int(y0)]}

# Упаковка атласа «полками».
order = sorted(frames, key=lambda k: -frames[k].height)
PAD, AW = 4, 2048
x = y = rowh = 0
rects = {}
for k in order:
    im = frames[k]
    if x + im.width + PAD > AW:
        x, y, rowh = 0, y + rowh + PAD, 0
    rects[k] = [x, y, im.width, im.height]
    x += im.width + PAD
    rowh = max(rowh, im.height)
AH = y + rowh
atlas = Image.new("RGBA", (AW, AH))
for k, (ax, ay, w, h) in rects.items():
    atlas.alpha_composite(frames[k], (ax, ay))
os.makedirs(os.path.join(GA, "Ambient"), exist_ok=True)
atlas.save(os.path.join(GA, "Ambient/ambient_atlas.png"), optimize=True)
json.dump({"size": [AW, AH], "frames": rects}, open(os.path.join(GA, "Ambient/ambient_atlas.json"), "w"), indent=1)

# Кнопка «к почтальону»: голова НАД стрелкой, шея уходит в дерево (лицо не обрезано).
arrow = Image.open(os.path.join(GA, "UI/ch1/arrow.png")).convert("RGBA")
head = Image.open(os.path.join(GA, "Rig/parts/head.png")).convert("RGBA")
head = fit_h(head, 178)
head = head.rotate(-5, resample=Image.BICUBIC, expand=True)
ha = np.asarray(head).astype(np.float32)
fade_h = max(1, int(head.height * 0.08))
fade = np.ones(head.height, dtype=np.float32)
fade[-fade_h:] = np.linspace(1.0, 0.55, fade_h)
ha[:, :, 3] *= fade[:, None]
head = Image.fromarray(ha.astype(np.uint8))
overlap = 78
pad_top = head.height - overlap
btn = Image.new("RGBA", (arrow.width, arrow.height + pad_top))
btn.alpha_composite(arrow, (0, pad_top))
hx, hy = 42, 0
sh = Image.new("RGBA", head.size, (0, 0, 0, 0))
sh.putalpha(head.getchannel("A").point(lambda v: int(v * 0.32)))
sh = sh.filter(ImageFilter.GaussianBlur(6))
btn.alpha_composite(sh, (hx + 5, hy + 8))
btn.alpha_composite(head, (hx, hy))
ba = np.asarray(btn)
m = ba[:, :, 3] > 6
ys, xs = np.nonzero(m)
x0, x1 = max(0, int(xs.min()) - 2), min(btn.width, int(xs.max()) + 3)
y0, y1 = max(0, int(ys.min()) - 2), min(btn.height, int(ys.max()) + 3)
btn = btn.crop((x0, y0, x1, y1))
btn.save(os.path.join(GA, "UI/ch1/btn_postman.png"), optimize=True)
uij = os.path.join(GA, "UI/ui_ch1.json")
ui = json.load(open(uij))
pad_c = pad_top - y0
ui["art"]["btn_postman"] = {"image": "UI/ch1/btn_postman", "width": int(btn.width), "height": int(btn.height),
                            "anchors": {"body": [16, int(max(0, pad_c - 4)), min(int(btn.width) - 16, 360),
                                                 int(btn.height) - int(max(0, pad_c - 4)) - 6]}}
json.dump(ui, open(uij, "w"), ensure_ascii=False, indent=1)

# Жители: idle-листы (12 fps, 24 кадра) и rig.json с блоком idle.
for rid in ["kuzma", "mitya", "pimen", "nina", "vera"]:
    s, d = os.path.join(RES_SRC, rid), os.path.join(GA, "Chapter1/residents", rid)
    if os.path.exists(os.path.join(s, "spritesheet.png")) and os.path.isdir(d):
        shutil.copy(os.path.join(s, "spritesheet.png"), os.path.join(d, "spritesheet.png"))
        shutil.copy(os.path.join(s, "rig.json"), os.path.join(d, "rig.json"))

amb = {
    "fps": 12,
    "atlas": "Ambient/ambient_atlas",
    "deepSoilColor": "#2A1D16",
    "timeOfDay": [
        {"hour": 0, "skyTop": "#07131F", "skyBottom": "#15304A", "tint": "#8090B8", "stars": 1},
        {"hour": 4.5, "skyTop": "#07131F", "skyBottom": "#1A3350", "tint": "#8090B8", "stars": 1},
        {"hour": 6, "skyTop": "#3A4E7A", "skyBottom": "#E8A27A", "tint": "#C9B8B0", "stars": 0.3},
        {"hour": 7.5, "skyTop": "#2F6F86", "skyBottom": "#A9C9C0", "tint": "#F2ECE2", "stars": 0},
        {"hour": 10, "tint": "#FFFFFF", "stars": 0},
        {"hour": 16.5, "tint": "#FFFFFF", "stars": 0},
        {"hour": 18.5, "skyTop": "#2E3F66", "skyBottom": "#E39A5E", "tint": "#F0C6A0", "stars": 0},
        {"hour": 20, "skyTop": "#142540", "skyBottom": "#6A4E6E", "tint": "#9A8FB0", "stars": 0.6},
        {"hour": 21.5, "skyTop": "#07131F", "skyBottom": "#15304A", "tint": "#8090B8", "stars": 1},
    ],
    "clouds": [
        {"parallax": 0.03, "y": [2050, 2350], "height": [110, 150], "count": 5, "speed": 6, "alpha": 0.75, "z": -760},
        {"parallax": 0.07, "y": [1850, 2200], "height": [150, 200], "count": 4, "speed": 10, "alpha": 0.88, "z": -720},
        {"parallax": 0.12, "y": [1650, 2000], "height": [200, 260], "count": 3, "speed": 16, "alpha": 1.0, "z": -680},
    ],
    "birds": {"interval": [25, 70], "parallax": 0.3, "y": [1600, 2150], "speed": [170, 240],
              "height": 46, "flock": [1, 3], "z": -450},
    "stars": {"count": 46, "topFraction": 0.42, "size": [12, 26]},
    "smoke": [
        {"prop": "places/place_pochta_main", "at": [515, 235], "scale": 1.0, "interval": 0.9, "wind": 1},
        {"prop": "places/place_nii_main", "at": [1278, 242], "scale": 0.8, "interval": 1.1, "wind": 1},
        {"prop": "places/el_zvon_candle_hut", "at": [195, 50], "scale": 0.6, "interval": 1.2, "wind": 1},
    ],
    "sway": [
        {"match": "foreground/fg_grass", "amp": 2.2, "period": [2.6, 3.6]},
        {"match": "foreground/fg_reeds", "amp": 2.8, "period": [3.0, 4.0]},
        {"match": "foreground/fg_fern", "amp": 1.8, "period": [2.8, 3.8]},
        {"match": "foreground/fg_dill", "amp": 3.0, "period": [2.4, 3.2]},
        {"match": "places/el_kad_dill_rope", "amp": 0.8, "period": [3.4, 4.2]},
    ],
    "bells": [
        {"prop": "places/place_zvonarnya_main", "baseImage": "places/place_zvonarnya_main_nobell",
         "frame": "bell_zvon", "pivot": bell_info["pivot"], "hang": bell_info["hang"],
         "amp": 5, "period": 2.8, "z": 1},
    ],
}
json.dump(amb, open(os.path.join(GA, "Data/ambient.json"), "w"), ensure_ascii=False, indent=1)
print("atlas", AW, AH, sorted(rects), "bell", bell_info)
