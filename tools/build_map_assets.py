#!/usr/bin/env python3
"""Ассеты карты «Пергамент» (вариант A) из /workspace/walking-sim/ui/map_v2 → Postman/GameAssets/UI/map.

  map_color.jpg   — цветная пластилиновая долина (кадр 1170x2532, виньетка и низ уже запечены)
  map_pencil.jpg  — та же долина карандашным наброском (непройденное)
  map_field.png   — поле «длина дороги»: для каждого пикселя — доля длины дороги ближайшей точки (+волна),
                    8 бит, половинное разрешение; кодировка v = (field + 0.1) / 1.3
  icon_*.png, postman.png, compass.png, fog.png — вырезки
  map.json        — дорога (полилиния Почта→Седло, равномерная), места иконок, облака по уровням фронта

Поселения стоят на дороге по РЕАЛЬНЫМ долям шагов (step / lengthSteps по длине дуги).
Запуск: python3 tools/build_map_assets.py   (fal не нужен: используется готовый арт map_v2)."""
import json, math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage
from scipy.spatial import cKDTree

SRC = "/workspace/walking-sim/ui/map_v2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "Postman/GameAssets/UI/map")
WORLD = os.path.join(ROOT, "Postman/GameAssets/Data/world.json")
os.makedirs(OUT, exist_ok=True)
os.chdir(SRC)
sys.path.insert(0, SRC)
import compose as C  # noqa: E402  (рисовалка макета: pencil_fog, vignette, вырезки)

W, H = 1170, 2532
BASE, OY = "t2i_paper_s9_nc", 110
AHEAD, SOFT = 230.0, 150.0           # px: цвет открыт на AHEAD вперёд по дороге, мягкий край SOFT
IH = {"pochta": 230, "svai": 230, "zvonarnya": 300, "kadushki": 200, "nii": 220, "sedlo": 230}
SIDE = {"pochta": 1, "svai": -1, "zvonarnya": 1, "kadushki": -1, "nii": 1, "sedlo": -1}
# Неподвижная «рамка» карты в координатах кадра (табличка, компас, бирка шагов, «Закрыть»).
CHROME = [(40, 110, 560, 390), (890, 160, 1130, 430), (80, 2270, 520, 2490), (680, 2280, 1150, 2480)]

world = json.load(open(WORLD))
ch = world["chapters"][0]
LENGTH = ch["lengthSteps"]
SETS = [(s["id"], s["name"], s["step"]) for s in ch["settlements"]]

# ---- основа -------------------------------------------------------------------------------
color = Image.open(f"raw/fit_{BASE}.jpg").convert("RGBA").crop((0, OY, W, OY + H))
pencil = C.pencil_fog(color, np.ones((H, W), np.float32))
def finish(im):
    im = im.copy(); C.vignette(im, 90)
    gm = Image.linear_gradient("L").resize((W, 420)); g = Image.new("RGBA", (W, 420), (20, 40, 42, 0))
    g.putalpha(gm.point(lambda v: int(v * 0.55))); im.alpha_composite(g, (0, H - 420)); return im.convert("RGB")
finish(color).save(f"{OUT}/map_color.jpg", quality=90)
finish(pencil).save(f"{OUT}/map_pencil.jpg", quality=90)

# ---- дорога: от Почты до конца, равномерно по длине ------------------------------------------
pts, cum, _ = C.route(BASE, lambda p: (p[0], p[1] - OY), 2190)
L = float(cum[-1]); n = int(L // 8) + 1
road = [C.at(pts, cum, i / (n - 1))[0] for i in range(n)]
road = [(round(x, 1), round(y, 1)) for x, y in road]
def at_frac(f):
    return C.at(pts, cum, max(0.0, min(1.0, f)))[0]

# ---- поле длины дуги ----------------------------------------------------------------------
dense = np.array([C.at(pts, cum, i / 4000)[0] for i in range(4001)])
tree = cKDTree(dense)
hs = 2
yy, xx = np.mgrid[0:H:hs, 0:W:hs]
_, idx = tree.query(np.c_[xx.ravel(), yy.ravel()])
field_px = (idx.reshape(xx.shape) / 4000.0) * L
field_px[(idx.reshape(xx.shape) == 0) & (yy > dense[0][1])] = -0.05 * L   # ниже Почты — всегда цвет
field_px += 28 * np.sin(xx / 95.0) + 18 * np.sin(xx / 41.0 + 1.3)
field_px = ndimage.gaussian_filter(field_px, 22 / hs)
field = field_px / L
enc = np.clip((field + 0.1) / 1.3, 0, 1)
Image.fromarray((enc * 255).round().astype(np.uint8), "L").save(f"{OUT}/map_field.png")

# ---- облака вдоль фронта: для уровней T0 (доля дороги) — точки изолинии --------------------
LEVELS = 120
def fval(x, y):
    return field[min(int(y / hs), field.shape[0] - 1), min(int(x / hs), field.shape[1] - 1)]
random.seed(3)
puffs = []
cols = [50, 300, 590, 880, 1120]
for li in range(LEVELS + 1):
    t0 = li / LEVELS * 1.1
    row = []
    for ci, cx in enumerate(cols):
        col = field[:, int(cx / hs)]
        ys = np.where((col[1:] >= t0) & (col[:-1] < t0))[0]     # вверх по экрану поле растёт
        cross = np.where((col[:-1] >= t0) & (col[1:] < t0))[0]
        cand = list(cross)
        if not cand: continue
        y = (max(cand) + 0.5) * hs                                 # нижнее пересечение = край пройденного
        r = random.Random(li * 7 + ci)
        row.append([cx + r.uniform(-40, 40), y - 15 + r.uniform(-25, 20), round(r.uniform(250, 360)), ci % 2])
    puffs.append(row)

# ---- вырезки ------------------------------------------------------------------------------
def save_cut(img, name, h=None, w=None, mult=2.0):
    im = C.sc(img, h=int(h * mult)) if h else C.sc(img, w=int(w * mult))
    im.save(f"{OUT}/{name}.png", optimize=True)
    return im.width / mult, im.height / mult
icons = {}
for k, _, _ in SETS:
    icons[k] = save_cut(C.ICON[k], f"icon_{k}", h=IH[k])
pm_w, pm_h = save_cut(C.POST, "postman", h=230)
comp_w, comp_h = save_cut(C.COMP, "compass", w=210)
fog_w, fog_h = save_cut(C.FOG, "fog", w=360, mult=1.0)

# ---- места иконок (без наложений) ----------------------------------------------------------
def overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
placed, settlements = [], []
road_np = np.array(road)
for k, name, step in SETS:
    f = step / LENGTH
    x, y = at_frac(f)
    w, h = icons[k]
    best = None
    for sd in (SIDE[k], -SIDE[k]):
        for dx in (205, 240, 175, 270, 300):
            for oy in (40, 0, 80, -40):
                ix = min(max(x + sd * dx, w / 2 + 20), W - w / 2 - 20); iy = y + oy
                r = (ix - w / 2, iy - h, ix + w / 2, iy)
                s = sum(overlap(r, p) for p in placed) * 3 + sum(overlap(r, c) for c in CHROME) * 3
                inner = (r[0] + w * .15, r[1] + h * .15, r[2] - w * .15, r[3] - h * .1)
                on_road = ((road_np[:, 0] > inner[0]) & (road_np[:, 0] < inner[2]) &
                           (road_np[:, 1] > inner[1]) & (road_np[:, 1] < inner[3])).sum()
                s += on_road * 400 + abs(dx - 205) * 2 + abs(oy - 40)
                if r[1] < 0 or r[3] > H: s += 1e6
                if best is None or s < best[0]: best = (s, ix, iy, r)
    _, ix, iy, r = best
    placed.append(r)
    settlements.append({"id": k, "name": name, "step": step, "road": [round(x, 1), round(y, 1)],
                        "icon": f"UI/map/icon_{k}", "x": round(ix, 1), "y": round(iy, 1),
                        "w": round(w, 1), "h": round(h, 1)})
    print(f"{k:10s} step {step:6d} frac {f:.3f} road ({x:.0f},{y:.0f}) icon ({ix:.0f},{iy:.0f}) score {best[0]:.0f}")

meta = {
    "_comment": "Сгенерировано tools/build_map_assets.py. Координаты — кадр 1170x2532.",
    "size": [W, H], "lengthSteps": LENGTH, "roadLength": round(L, 1), "road": road,
    "aheadPx": AHEAD, "softPx": SOFT,
    "field": {"image": "UI/map/map_field.png", "decodeScale": 1.3, "decodeBias": -0.1},
    "puffs": {"levels": LEVELS, "maxT": 1.1, "image": "UI/map/fog", "aspect": round(fog_h / fog_w, 4), "points": puffs},
    "settlements": settlements,
    "postman": {"image": "UI/map/postman", "w": round(pm_w, 1), "h": round(pm_h, 1)},
    "compass": {"image": "UI/map/compass", "w": round(comp_w, 1), "h": round(comp_h, 1)},
    "chrome": CHROME,
}
json.dump(meta, open(f"{OUT}/map.json", "w"), ensure_ascii=False)
print("road length", round(L), "px; samples", len(road))
