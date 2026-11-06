#!/usr/bin/env python3
"""Вырезает ассеты карманных часов для HUD из исходников ui/v3 (тот же конвейер, что v3.py),
но БЕЗ цифр: числа рисует SwiftUI поверх. Пишет:
  Postman/GameAssets/UI/watch_collapsed.png  — нитка + закрытые часы (hunter_bg3), тень запечена
  Postman/GameAssets/UI/watch_expanded.png   — нитка + раскрытые часы (pedo_bg3) с делениями,
                                               вдавленным сабциферблатом и откинутой крышкой (openw_h9)
  Postman/GameAssets/UI/hud_layout.json      — координаты в кадре макета 1170x2532: где лежит картинка,
                                               куда ставить тексты, размеры шрифтов, зоны тапа, бирка/телеграмма.
Запуск: python3 tools/build_watch_assets.py [путь к walking-sim/ui/v3]
"""
import sys, os, json, math
V3 = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "/workspace/walking-sim/ui/v3")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTDIR = os.path.join(ROOT, "Postman/GameAssets/UI")
os.makedirs(OUTDIR, exist_ok=True)
os.chdir(V3); sys.path.insert(0, V3)
from compose import *          # noqa: E402,F403  (load, prep, ink, carve, grade, rim, contour, ...)

TY = 214   # нитка главы в макете; в игре нитки нет — верёвка часов идёт от верхнего края кадра

def blank(): return Image.new("RGBA", (W, H), (0, 0, 0, 0))

def put_t(cv, obj, x, y, sh=None):
    """как compose.put, но на прозрачном холсте: тень = тёмный слой с альфой"""
    if sh:
        al = obj.split()[-1]; m = Image.new("L", cv.size, 0)
        m.paste(al, (int(x + sh["dx"]), int(y + sh["dy"])))
        m = m.filter(ImageFilter.GaussianBlur(sh["blur"]))
        s = Image.new("RGBA", cv.size, (12, 24, 26, 0)); s.putalpha(m.point(lambda v: int(v * sh["op"] * 0.9)))
        cv.alpha_composite(s)
    cv.alpha_composite(obj, (int(x), int(y))); return cv

ROPE = load("rope_bg3"); ROPE = ROPE.crop(ROPE.getbbox())
def rope(cv, p0, p1, w=16):
    (x0, y0), (x1, y1) = p0, p1; Ln = math.hypot(x1 - x0, y1 - y0)
    s = w / ROPE.width; need = int(Ln / s) + 2
    seg = Image.new("RGBA", (ROPE.width, need))
    for yy in range(0, need, ROPE.height - 40): seg.alpha_composite(ROPE.crop((0, 20, ROPE.width, ROPE.height - 20)), (0, yy))
    seg = grade(seg, 0.92, 0.18); seg = rim(seg, 4, 0.4)
    seg = seg.resize((max(2, int(w)), int(Ln)), Image.LANCZOS); seg = contour(seg, 2)
    ang = math.degrees(math.atan2(x1 - x0, y1 - y0)); R = seg.rotate(ang, resample=Image.BICUBIC, expand=True)
    return put_t(cv, R, int((x0 + x1) / 2 - R.width / 2), int((y0 + y1) / 2 - R.height / 2), sh=dict(dx=10, dy=14, blur=6, op=0.45))

def holept(obj, pt, sc, ang):
    bb = obj.split()[-1].getbbox(); w0, h0 = (bb[2] - bb[0]) * sc, (bb[3] - bb[1]) * sc
    hx, hy = (pt[0] - bb[0]) * sc - w0 / 2, (pt[1] - bb[1]) * sc - h0 / 2; a = math.radians(ang)
    W2, H2 = (w0 * abs(math.cos(a)) + h0 * abs(math.sin(a))) / 2, (w0 * abs(math.sin(a)) + h0 * abs(math.cos(a))) / 2
    return W2 + hx * math.cos(a) + hy * math.sin(a), H2 - hx * math.sin(a) + hy * math.cos(a)

def save_crop(cv, name):
    bb = cv.split()[-1].getbbox(); bb = (max(0, bb[0] - 2), 0, min(W, bb[2] + 2), min(H, bb[3] + 2))
    cv.crop(bb).save(os.path.join(OUTDIR, name), optimize=True)
    return {"image": "UI/" + name.rsplit(".", 1)[0], "x": bb[0], "y": bb[1], "width": bb[2] - bb[0], "height": bb[3] - bb[1]}

def r1(v): return round(float(v), 1)
layout = {"frame": [W, H]}

# ---------- collapsed: hunter, lid closed, window shows today ----------
hu = load("hunter_bg3"); WC = (512, 580); SC_C, ANG_C = 0.42, 3
P = prep(hu, SC_C, angle=ANG_C, rimw=6, rims=0.65, line=3)
PX, PY = 640 - P.width // 2, 262
cv = blank()
cv = rope(cv, (PX + P.width // 2 - 4, -10), (PX + P.width // 2 - 2, PY + 22), w=15)
cv = put_t(cv, P, PX, PY, sh=dict(dx=20, dy=28, blur=16, op=0.55))
img = save_crop(cv, "watch_collapsed.png")
wx, wy = holept(hu, (WC[0], WC[1] + 4), SC_C, ANG_C)
layout["collapsed"] = {
    **img,
    "body": [PX, PY, P.width, P.height],                       # зона тапа и центр ореола
    "halo": {"cx": r1(PX + P.width / 2), "cy": r1(PY + P.height * 0.62), "r": r1(P.width * 0.7), "opacity": 0.34},
    "today": {"cx": r1(PX + wx), "cy": r1(PY + wy), "size": r1(168 * SC_C), "maxWidth": r1(330 * SC_C),
              "font": "Oswald", "weight": 650, "squeezeX": 0.86, "rotation": -ANG_C},
}

# ---------- expanded: pedo with ticks + recessed sub-dial, lid open on the left ----------
pedo = load("pedo_bg3"); D = (512, 598); R = 232
tick = Image.new("L", pedo.size, 0); td = ImageDraw.Draw(tick)
for i in range(40):
    ang = -math.pi / 2 + i * 2 * math.pi / 40; dg = math.degrees(ang) % 360
    if abs(dg - 90) < 44 or min(abs(dg - 0), abs(dg - 360)) < 22 or abs(dg - 180) < 22: continue
    r0 = R - 14; rr = R - (38 if i % 5 == 0 else 26)
    td.line([(D[0] + r0 * math.cos(ang), D[1] + r0 * math.sin(ang)), (D[0] + rr * math.cos(ang), D[1] + rr * math.sin(ang))],
            fill=255, width=6 if i % 5 == 0 else 3)
pedo = ink(pedo, tick, (70, 40, 22), 0.7)
SCc = (D[0], D[1] + 112); SR = 104
sub = Image.new("L", pedo.size, 0); ImageDraw.Draw(sub).ellipse((SCc[0] - SR, SCc[1] - SR, SCc[0] + SR, SCc[1] + SR), fill=255)
pedo = ink(pedo, sub, (214, 190, 150), 0.55, bleed=1.5, rough=0.1)
ring = Image.new("L", pedo.size, 0); ImageDraw.Draw(ring).ellipse((SCc[0] - SR, SCc[1] - SR, SCc[0] + SR, SCc[1] + SR), outline=255, width=7)
pedo = carve(pedo, ring, depth=4)
SC_E = 0.88
P = prep(pedo, SC_E, rimw=8, rims=0.6, line=3)
PX, PY = 512 - P.width // 2, 410
ow = load("openw_h9").crop((240, 175, 632, 540))
lid = ow.rotate(90, expand=True, resample=Image.BICUBIC)
L_ = prep(lid, 1.0, rimw=6, rims=0.5, line=3)
L_ = L_.resize((int(P.width * 0.30), int(P.width * 0.80)), Image.LANCZOS)
LX = PX - L_.width + 26; LY = PY + int(P.height * 0.555) - L_.height // 2
cv = blank()
cv = rope(cv, (PX + P.width // 2 - 2, -10), (PX + P.width // 2, PY + 26), w=16)
cv = put_t(cv, L_, LX, LY, sh=dict(dx=24, dy=34, blur=22, op=0.55))
cv = put_t(cv, P, PX, PY, sh=dict(dx=28, dy=40, blur=24, op=0.6))
img = save_crop(cv, "watch_expanded.png")
def ept(x, y):
    hx, hy = holept(pedo, (x, y), SC_E, 0); return r1(PX + hx), r1(PY + hy)
cxl, cyl = ept(D[0], D[1] - 150); cxt, cyt = ept(D[0], D[1] - 62)
cxs, cys = ept(SCc[0], SCc[1] - 46); cxv, cyv = ept(SCc[0], SCc[1] + 18)
layout["expanded"] = {
    **img,
    "body": [LX, PY, PX + P.width - LX, P.height],
    "halo": {"cx": r1(PX + P.width / 2), "cy": r1(PY + P.height * 0.58), "r": r1(P.width * 0.78), "opacity": 0.30},
    "todayLabel": {"cx": cxl, "cy": cyl, "size": r1(44 * SC_E), "font": "Kurale", "text": "сегодня"},
    "today": {"cx": cxt, "cy": cyt, "size": r1(146 * SC_E), "maxWidth": r1(380 * SC_E), "font": "YesevaOne"},
    "totalLabel": {"cx": cxs, "cy": cys, "size": r1(36 * SC_E), "font": "Kurale", "text": "всего"},
    "total": {"cx": cxv, "cy": cyv, "size": r1(54 * SC_E), "maxWidth": r1(176 * SC_E), "font": "YesevaOne"},
    "dim": {"brightness": 0.52, "saturation": 0.45, "hangingLayer": 0.78},
}

# ---------- hanging layer from v3.py (for placement only) ----------
tag = load("tag_bg3"); T = prep(tag, 0.45, angle=-7, rimw=5, line=2)
tg = load("telegram_bg3")
G1 = prep(tg, 0.58, angle=4, rimw=5, line=2); G2 = prep(tg, 0.62, angle=4, rimw=5, line=2)
layout["distanceTag"] = {"x": 48, "y": 362, "width": T.width, "height": T.height, "rotation": 7}
layout["telegram"] = {"collapsed": {"right": W - 18, "y": 548, "width": G1.width, "height": G1.height},
                      "expanded": {"right": W - 18, "y": 600, "width": G2.width, "height": G2.height}, "rotation": -4}
with open(os.path.join(OUTDIR, "hud_layout.json"), "w", encoding="utf-8") as fh:
    json.dump(layout, fh, ensure_ascii=False, indent=2)
print(json.dumps(layout, ensure_ascii=False))

# ---------- поправка «центр строки» -> «центр глифов» ----------
# Макет центрировал тексты по габаритам глифов; SwiftUI центрирует строку (ascent+descent).
# Для каждой надписи считаем, на сколько сдвинуть центр строки, чтобы глифы встали как в макете.
FONTFILES = {"Oswald": "Oswald-VF.ttf", "YesevaOne": "YesevaOne-Regular.ttf", "Kurale": "Kurale-Regular.ttf"}
def line_offset(font, size, sample, wght=None):
    f = ImageFont.truetype(FD + FONTFILES[font], int(round(size * 10)))
    if wght:
        try: f.set_variation_by_axes([wght])
        except Exception: pass
    bb = ImageDraw.Draw(Image.new("L", (10, 10))).textbbox((0, 0), sample, font=f, anchor="mm")
    return -(bb[1] + bb[3]) / 2 / 10
for st in ("collapsed", "expanded"):
    for k, v in layout[st].items():
        if isinstance(v, dict) and "font" in v:
            v["lineCY"] = r1(v["cy"] + line_offset(v["font"], v["size"], v.get("text", "0123456789"), v.get("weight")))
with open(os.path.join(OUTDIR, "hud_layout.json"), "w", encoding="utf-8") as fh:
    json.dump(layout, fh, ensure_ascii=False, indent=2)
