#!/usr/bin/env python3
"""Ассеты диегетического UI главы 1 (сумка, письмо, вручение, карта, «пока вас не было», финал)
из пластилиновых вырезок walking-sim/ui/v4/cut (+ v3/cut) тем же конвейером, что ui/v4/bag.py и letter.py:
grade → rim → resize → contour → (rotate), тень запекается тёмной альфой. ТЕКСТОВ НЕТ — их рисует SwiftUI
(кроме декоративных надписей, которые в игре не меняются: «ТЕЛЕГРАММА», «ТРЕБОВАНИЕ № 23», штемпели).

Пишет Postman/GameAssets/UI/ch1/*.png и Postman/GameAssets/UI/ui_ch1.json:
  art[name] = {image, width, height, anchors{...}}  — px кадра 1170x2532 (= px картинки);
  layout    = позиции экранов в кадре макета (как screen_bag.jpg / screen_letter.jpg).
Запуск: python3 tools/build_ch1_ui_assets.py [путь к walking-sim/ui/v4] [--preview DIR]
"""
import sys, os, json, math
argv = sys.argv[1:]
PREVIEW = None
if "--preview" in argv:
    i = argv.index("--preview"); PREVIEW = os.path.abspath(argv[i + 1]); del argv[i:i + 2]
V4 = os.path.abspath(argv[0] if argv else "/workspace/walking-sim/ui/v4")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTDIR = os.path.join(ROOT, "Postman/GameAssets/UI/ch1")
os.makedirs(OUTDIR, exist_ok=True)
os.chdir(V4); sys.path.insert(0, V4)
from common import *   # noqa: F401,F403  (compose.* + tag/brass/fit/KU/YE)

V3CUT = os.path.join(V4, "..", "v3", "cut")
def loadv3(n): return Image.open(os.path.join(V3CUT, n + ".png")).convert("RGBA")

PAD_L, PAD_T, PAD_R, PAD_B = 24, 24, 64, 72
art = {}

def bake(obj, name, sh=dict(dx=12, dy=16, blur=10, op=0.5), anchors=None, pad=None):
    """obj -> png с запечённой тенью; anchors — точки в координатах obj (до паддинга)"""
    pl, pt, pr, pb = pad or (PAD_L, PAD_T, PAD_R, PAD_B)
    cv = Image.new("RGBA", (obj.width + pl + pr, obj.height + pt + pb), (0, 0, 0, 0))
    if sh:
        al = obj.split()[-1]; m = Image.new("L", cv.size, 0)
        m.paste(al, (int(pl + sh["dx"]), int(pt + sh["dy"])))
        m = m.filter(ImageFilter.GaussianBlur(sh["blur"]))
        s = Image.new("RGBA", cv.size, (12, 24, 26, 0)); s.putalpha(m.point(lambda v: int(v * sh["op"] * 0.9)))
        cv.alpha_composite(s)
    cv.alpha_composite(obj, (pl, pt))
    cv.save(os.path.join(OUTDIR, name + ".png"), optimize=True)
    a = {k: [round(v[0] + pl, 1), round(v[1] + pt, 1)] for k, v in (anchors or {}).items()}
    a["body"] = [pl, pt, obj.width, obj.height]
    art[name] = {"image": "UI/ch1/" + name, "width": cv.width, "height": cv.height, "anchors": a}
    return cv

def native(obj_src, sc, pt):
    """точка исходника -> координаты prep()-объекта (без поворота)"""
    bb = obj_src.split()[-1].getbbox()
    return ((pt[0] - bb[0]) * sc, (pt[1] - bb[1]) * sc)

def rotpt(w0, h0, p, ang):
    """точка p в неповёрнутом объекте w0×h0 -> в объекте после rotate(ang, expand=True)"""
    a = math.radians(ang); hx, hy = p[0] - w0 / 2, p[1] - h0 / 2
    W2 = (w0 * abs(math.cos(a)) + h0 * abs(math.sin(a))) / 2; H2 = (w0 * abs(math.sin(a)) + h0 * abs(math.cos(a))) / 2
    return (W2 + hx * math.cos(a) + hy * math.sin(a), H2 - hx * math.sin(a) + hy * math.cos(a))

def hue_to(obj, col, amt=0.9):
    a = A(obj); L = (a[..., :3] @ np.array([.299, .587, .114]))[..., None] / 255
    tgt = np.array(col, np.float32)[None, None, :] * (0.35 + 1.0 * L)
    a[..., :3] = a[..., :3] * (1 - amt) + tgt * amt
    return I(a, "RGBA")

# ---------------------------------------------------------------- shelf, nail, tag
S = prep(load("shelf_bg3"), 0.84, k=0.88, rimw=5, line=3)
bake(S, "shelf", sh=dict(dx=18, dy=26, blur=16, op=0.55))

TACK = load("tack_bg3")
def nail_img(d):
    return prep(TACK, d / (TACK.getbbox()[2] - TACK.getbbox()[0]), k=0.95, rimw=3, rims=0.6, line=2)
bake(nail_img(40), "nail", sh=dict(dx=6, dy=8, blur=4, op=0.55), pad=(10, 10, 24, 26))

TAGSRC = load("tag_bg3"); TSC = 0.42
T = prep(TAGSRC, TSC, rimw=4, line=2)
bake(T, "tag", anchors={"hole": native(TAGSRC, TSC, (396, 380)),
                        "line1": native(TAGSRC, TSC, (760, 300)), "line2": native(TAGSRC, TSC, (760, 462)),
                        "textWidth": (600 * TSC, 0)})

# ---------------------------------------------------------------- items on the shelf (0.40)
def item(name, obj, sc, ang=0, anchors=None):
    P = prep(obj, sc, angle=ang, rimw=6, line=3)
    bake(P, name, sh=dict(dx=14, dy=12, blur=10, op=0.5), anchors=anchors)
    return P

envplain = load("envplain_bg3"); envfat = load("envfat_bg3"); envseal = load("env_bg3")

def thumbprint(obj, c, r, col, op=0.55, phase=0.0):
    m = Image.new("L", obj.size, 0); d = ImageDraw.Draw(m)
    for i in range(7):
        rr = r * (0.25 + i * 0.12)
        d.arc((c[0] - rr * 1.12, c[1] - rr, c[0] + rr * 1.12, c[1] + rr), start=200 + phase * 40 + i * 9, end=520 + phase * 40 - i * 7, fill=255, width=5)
    return ink(obj, m, col, op, rough=0.35)

WAX = (204, 150, 58)
def wax_env(two):
    e = redseal(envseal.copy(), col=WAX, amt=0.92)
    e = thumbprint(e, (590, 445), 52, (120, 78, 28), 0.6)
    if two: e = thumbprint(e, (618, 470), 48, (96, 58, 22), 0.7, phase=1.7)
    # бечёвка крест-накрест + полоска счёта под ней
    strip = load("tape_bg3"); strip = strip.crop(strip.getbbox()).resize((430, 70), Image.LANCZOS)
    strip = ink(strip, textmask(strip.size, "СВЕЧИ ПОМИН. 41 ШТ", Fv("Oswald-VF.ttf", 38, 600), (215, 36)), INK, 0.9)
    e.alpha_composite(strip.rotate(3, expand=True, resample=Image.BICUBIC), (360, 560))
    m = Image.new("L", e.size, 0); d = ImageDraw.Draw(m)
    d.line([(306, 600), (876, 585)], fill=255, width=9); d.line([(470, 240), (520, 670)], fill=255, width=9)
    e = ink(e, m, (120, 92, 58), 0.85, rough=0.2)
    return e

form = load("telegram_bg3")
form = ink(form, textmask(form.size, "ТРЕБОВАНИЕ № 23", Fv("Oswald-VF.ttf", 50, 600), (592, 278)), (70, 36, 18), 0.85, rough=0.2)
ks_env = envplain.copy()
st = Image.new("L", ks_env.size, 0); sd = ImageDraw.Draw(st); c = (760, 380); r = 72
sd.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=255, width=7)
ks_env = ink(ks_env, st, (92, 62, 128), 0.75, rough=0.5)
tima_env = envplain.copy()
st = Image.new("L", tima_env.size, 0); sd = ImageDraw.Draw(st); c = (742, 436); r = 70
sd.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=255, width=7)
tima_env = ink(tima_env, st.rotate(-14, center=c), (92, 62, 128), 0.75, rough=0.5)

ENV_SC = 0.40
item("env_plain", envplain, ENV_SC, 3)
item("env_fat", envfat, ENV_SC, -2)
item("env_wax", wax_env(False), ENV_SC, -3)
item("env_wax2", wax_env(True), ENV_SC, -3)
item("env_tima", tima_env, ENV_SC, 2)
item("env_ksenia", ks_env, ENV_SC, -2)
item("form", form, ENV_SC, -3)
item("parcel", load("parcel_bg3"), 0.36, 6)

# вертикальный «торчащий из отделения» вариант (как bag.py: 150 px шириной, повёрнут на 90°)
def stick(name, src, ang):
    e = src.crop(src.getbbox()).rotate(90 + ang, expand=True, resample=Image.BICUBIC)
    s = 150 / e.width; e = grade(e.resize((int(e.width * s), int(e.height * s)), Image.LANCZOS), 0.92, 0.12)
    e.save(os.path.join(OUTDIR, name + ".png"), optimize=True)
    art[name] = {"image": "UI/ch1/" + name, "width": e.width, "height": e.height, "anchors": {"body": [0, 0, e.width, e.height]}}
stick("stick_plain", envplain, -5); stick("stick_fat", envfat, 6); stick("stick_wax", wax_env(False), -4)
stick("stick_tima", tima_env, 4); stick("stick_parcel", load("parcel_bg3"), 0)

# ---------------------------------------------------------------- bag (squashed strap, as bag.py), back + front
bag = load("bagstrap_e3"); a_ = A(bag); a_[:46, :, 3] = 0; bag = I(a_, "RGBA")
top = bag.crop((0, 0, 880, 140)); band = bag.crop((0, 140, 880, 540)).resize((880, 110), Image.LANCZOS); bot = bag.crop((0, 540, 880, 1184))
SQ = 400 - 110
bag2 = Image.new("RGBA", (880, 1184 - SQ), (0, 0, 0, 0)); bag2.paste(top, (0, 0)); bag2.paste(band, (0, 140)); bag2.paste(bot, (0, 250))
ny = lambda y: y - SQ
fa = A(bag2); yy = np.arange(fa.shape[0])[:, None]; fa[..., 3] = np.where(yy > ny(768), fa[..., 3], 0); front = I(fa, "RGBA")
BAGS = 1.08
bb = bag2.getbbox()
BB = prep(bag2, BAGS, rimw=7, line=3)
# front: crop by the SAME bbox as the full bag so both PNGs align
fr = front.crop(bb); fr = grade(fr, 0.9, 0.22); fr = rim(fr, 7, 0.5)
fr = fr.resize((BB.width, BB.height), Image.LANCZOS)
bk = bag2.crop(bb)
def bagpt(nx, nyy): return ((nx - bb[0]) * BAGS, (nyy - bb[1]) * BAGS)
anchors = {"ring": bagpt(442, 57), "slot0": bagpt(282, ny(760)), "slot1": bagpt(430, ny(760)), "slot2": bagpt(582, ny(760)),
           "label0": bagpt(282, ny(860)), "label1": bagpt(430, ny(860)), "label2": bagpt(582, ny(860)),
           "labelWidth": (140 * BAGS, 0)}
bake(BB, "bag_back", sh=dict(dx=22, dy=30, blur=20, op=0.55), anchors=anchors)
cvf = Image.new("RGBA", (BB.width + PAD_L + PAD_R, BB.height + PAD_T + PAD_B), (0, 0, 0, 0))
cvf.alpha_composite(fr, (PAD_L, PAD_T)); cvf.save(os.path.join(OUTDIR, "bag_front.png"), optimize=True)
art["bag_front"] = {"image": "UI/ch1/bag_front", "width": cvf.width, "height": cvf.height, "anchors": {"body": [PAD_L, PAD_T, BB.width, BB.height]}}

# ---------------------------------------------------------------- buttons
ar = prep(load("arrow_bg7"), 0.41, angle=-3, rimw=6, line=3)
bake(ar, "arrow", sh=dict(dx=16, dy=14, blur=12, op=0.5), anchors={"text": (ar.width * 0.47, ar.height * 0.52)})
p = brass(load("pad_bg3")); p = p.crop(p.getbbox()); P = prep(p, 360 / p.width, k=0.95, teal=0.1, rimw=5, line=3)
P = P.resize((P.width, int(P.height * 0.62)), Image.LANCZOS)
B = prep(load("bag2_bg7"), 0.42, rimw=6, line=3)
btn = Image.new("RGBA", (max(P.width, B.width) + 20, P.height + B.height), (0, 0, 0, 0))
btn.alpha_composite(P, ((btn.width - P.width) // 2, btn.height - P.height))
btn.alpha_composite(B, ((btn.width - B.width) // 2 - 10, btn.height - int(P.height * 0.42) - B.height + 16))
bake(btn.crop(btn.getbbox()), "btn_bag", sh=dict(dx=14, dy=12, blur=12, op=0.5))
# HUD: сумка и карта в нижних углах
bake(prep(load("bag2_bg7"), 0.30, angle=-4, rimw=5, line=3), "hud_bag", sh=dict(dx=12, dy=14, blur=10, op=0.5))
bake(prep(loadv3("map_h7"), 0.34, angle=6, rimw=5, line=3), "hud_map", sh=dict(dx=12, dy=14, blur=10, op=0.5))
bake(prep(load("tag_bg3"), 0.24, rimw=3, line=2), "tag_small",
     anchors={"hole": native(TAGSRC, 0.24, (396, 380)), "line1": native(TAGSRC, 0.24, (760, 300)),
              "line2": native(TAGSRC, 0.24, (760, 462)), "textWidth": (600 * 0.24, 0)})

# ---------------------------------------------------------------- letter reader
SH_SC = 1.58
sheet = prep(load("sheet_bg3"), SH_SC, angle=-1.2, k=0.98, teal=0.06, rimw=7, line=3)
bake(sheet, "sheet", sh=dict(dx=24, dy=34, blur=24, op=0.6),
     anchors={"textTL": (92, 96), "textBR": (sheet.width - 84, sheet.height - 92)})
# бланк НИИ: та же бумага без клетки (сероватая, обрезана по линейке)
fsrc = load("sheet_bg3"); fa = A(fsrc); L = (fa[..., :3] @ np.array([.299, .587, .114]))[..., None]
fa[..., :3] = np.clip(np.array([222, 216, 198]) * (0.72 + 0.32 * (L / max(1, L.max()))), 0, 255)
fsheet = prep(I(fa, "RGBA").filter(ImageFilter.GaussianBlur(1.2)), SH_SC, angle=0.8, k=0.98, teal=0.08, rimw=7, line=3)
bake(fsheet, "sheet_form", sh=dict(dx=24, dy=34, blur=24, op=0.6),
     anchors={"textTL": (92, 96), "textBR": (fsheet.width - 84, fsheet.height - 92)})
# бланк телеграммы крупно (А.Л., «Ксения», Пимен изнутри — лента подклеена на лист)
tg = load("telegram_bg3")
tg = ink(tg, textmask(tg.size, "ТЕЛЕГРАММА", Fv("Oswald-VF.ttf", 46, 600), (592, 262)), (70, 36, 18), 0.85, rough=0.2)
TG = prep(tg, 1.75, angle=1.0, k=0.97, teal=0.08, rimw=7, line=3)
bake(TG, "sheet_telegram", sh=dict(dx=24, dy=34, blur=24, op=0.6),
     anchors={"textTL": (110, 250), "textBR": (TG.width - 100, TG.height - 110)})
tape = load("tape_bg3"); tape = tape.crop(tape.getbbox())
tp = grade(tape, 0.95, 0.08); tp = tp.resize((900, 62), Image.LANCZOS)
tp.save(os.path.join(OUTDIR, "tape_line.png"), optimize=True)
art["tape_line"] = {"image": "UI/ch1/tape_line", "width": tp.width, "height": tp.height, "anchors": {"body": [0, 0, tp.width, tp.height]}}

# конверты под листом (0.80), без адресов — адрес пишет SwiftUI
def reader_env(name, src, ang):
    E = prep(src, 0.80, angle=ang, k=0.95, rimw=6, line=3)
    w0, h0 = (src.getbbox()[2] - src.getbbox()[0]) * 0.80, (src.getbbox()[3] - src.getbbox()[1]) * 0.80
    addr = rotpt(w0, h0, native(src, 0.80, (520, 576)), ang)
    stamp = rotpt(w0, h0, native(src, 0.80, (742, 436)), ang)
    bake(E, name, sh=dict(dx=20, dy=26, blur=16, op=0.55), anchors={"address": addr, "stamp": stamp})
reader_env("renv_open", load("envopen_bg3"), 6)
reader_env("renv_wax", wax_env(False), 4)
reader_env("renv_wax2", wax_env(True), 4)
reader_env("renv_fat", envfat, 5)

# штемпели (фиолетовый химический карандаш) — кольца; текст внутри пишет SwiftUI
def stamp(name, col, r=86):
    m = Image.new("L", (2 * r + 20, 2 * r + 20), 0); d = ImageDraw.Draw(m); c = (r + 10, r + 10)
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=255, width=7)
    d.ellipse((c[0] - r + 16, c[1] - r + 16, c[0] + r - 16, c[1] + r - 16), outline=255, width=3)
    o = Image.new("RGBA", m.size, col + (0,)); n = np.random.default_rng(5).random(m.size[::-1])
    al = A(m.filter(ImageFilter.GaussianBlur(0.7))) * (0.55 + 0.45 * n) * 0.85
    o.putalpha(I(al)); o.save(os.path.join(OUTDIR, name + ".png"), optimize=True)
    art[name] = {"image": "UI/ch1/" + name, "width": o.width, "height": o.height, "anchors": {"center": [c[0], c[1]], "body": [0, 0, o.width, o.height]}}
stamp("stamp_violet", (92, 62, 128))

# вложения
wr = load("wrapper3_bg21"); wr = wr.crop(wr.getbbox()); w, h = wr.size
def find_coeffs(pa, pb):
    M = []
    for p1, p2 in zip(pa, pb):
        M.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0] * p1[0], -p2[0] * p1[1]]); M.append([0, 0, 0, p1[0], p1[1], 1, -p2[1] * p1[0], -p2[1] * p1[1]])
    return np.linalg.lstsq(np.array(M, float), np.array(pb).reshape(8), rcond=None)[0]
co = find_coeffs([(w * 0.36, 0), (w * 0.64, 0), (w, h), (0, h)], [(0, 0), (w, 0), (w, h), (0, h)])
wr = wr.transform((w, h), Image.PERSPECTIVE, co, Image.BICUBIC)
bake(prep(wr, 0.56, angle=-14, k=0.95, rimw=6, line=3), "att_wrapper_green", sh=dict(dx=18, dy=22, blur=12, op=0.55))
bake(prep(hue_to(wr, (236, 196, 72)), 0.56, angle=10, k=0.95, rimw=6, line=3), "att_wrapper_yellow", sh=dict(dx=18, dy=22, blur=12, op=0.55))
# миллиметровка с чертежом антенны
mm = load("sheet_bg3"); mm = hue_to(mm, (236, 224, 196), 0.6)
dm = Image.new("L", mm.size, 0); d = ImageDraw.Draw(dm)
d.line([(440, 980), (440, 330)], fill=255, width=9); d.line([(440, 330), (300, 470)], fill=255, width=6); d.line([(440, 330), (590, 470)], fill=255, width=6)
for y in range(420, 900, 90): d.line([(410, y), (470, y)], fill=255, width=5)
d.polygon([(560, 600), (600, 560), (600, 640)], fill=255); d.line([(600, 600), (690, 600)], fill=255, width=5)
mm = ink(mm, dm, (70, 70, 84), 0.8, rough=0.4)
mm = ink(mm, textmask(mm.size, "14 м", F("Neucha.ttf", 64), (590, 380)), (70, 70, 84), 0.85)
mm = ink(mm, textmask(mm.size, "НЕ к колоколу", F("Neucha.ttf", 52), (450, 1040)), (70, 70, 84), 0.85)
bake(prep(mm, 0.44, angle=8, k=0.97, teal=0.06, rimw=5, line=3), "att_drawing", sh=dict(dx=16, dy=20, blur=12, op=0.5))
# этикетка кильки (дата изготовления пишется SwiftUI)
lb = load("tape_bg3"); lb = lb.crop(lb.getbbox()).resize((760, 260), Image.LANCZOS); lb = hue_to(lb, (214, 92, 58), 0.75)
lb = ink(lb, textmask(lb.size, "КИЛЬКА В ТОМАТЕ", Fv("Oswald-VF.ttf", 76, 650), (380, 92)), (250, 236, 210), 0.9, rough=0.15)
lb = ink(lb, textmask(lb.size, "Ольховский консервный завод", F("Kurale-Regular.ttf", 40), (380, 160)), (250, 236, 210), 0.85)
LB = prep(lb, 0.62, angle=-6, k=0.96, teal=0.06, rimw=5, line=3)
bake(LB, "att_label", sh=dict(dx=16, dy=20, blur=12, op=0.5), anchors={"date": rotpt(760 * 0.62, 260 * 0.62, (380 * 0.62, 214 * 0.62), -6)})

# ---------------------------------------------------------------- delivery / cards / map
bake(prep(load("hand_bg3"), 0.62, angle=-8, rimw=6, line=3), "hand", sh=dict(dx=18, dy=24, blur=16, op=0.5))
pl_ = prep(load("plaque_bg3"), 0.62, rimw=6, line=3)
bake(pl_, "plaque", sh=dict(dx=18, dy=24, blur=16, op=0.55), anchors={"text": (pl_.width / 2, pl_.height / 2)})
TGB = prep(loadv3("telegram_h9"), 1.62, angle=-0.8, k=0.97, teal=0.08, rimw=7, line=3)
bake(TGB, "card_telegram", sh=dict(dx=24, dy=34, blur=24, op=0.6),
     anchors={"textTL": (96, 200), "textBR": (TGB.width - 96, TGB.height - 120)})
# лента карты: бумажная полоса вертикально, длинная
rb = load("tape_bg3"); rb = rb.crop(rb.getbbox()); rb = grade(rb, 0.97, 0.06)
rb = rb.rotate(90, expand=True).resize((150, 1900), Image.LANCZOS); rb = rim(rb, 5, 0.45); rb = contour(rb, 3)
bake(rb, "ribbon", sh=dict(dx=16, dy=22, blur=14, op=0.5))
bake(prep(load("pin_bg3"), 0.22, rimw=4, line=2), "pin", sh=dict(dx=8, dy=10, blur=6, op=0.5), pad=(12, 12, 30, 30))
bake(prep(hue_to(load("pin_bg3"), (210, 70, 40), 0.85), 0.28, rimw=4, line=2),
     "pin_red", sh=dict(dx=8, dy=10, blur=6, op=0.5), pad=(12, 12, 30, 30))
bake(prep(loadv3("map_h7"), 0.72, rimw=6, line=3), "map_roll", sh=dict(dx=16, dy=22, blur=14, op=0.5))
# дорожные предметы для SpriteKit (конверт на палочке, свёрток)
es = loadv3("envstake_bg5"); bbx = es.getbbox()
ES = prep(es, 0.34, k=0.95, rimw=5, line=3)
bake(ES, "road_envstake", sh=None, pad=(0, 0, 0, 0))
art["road_envstake"]["anchors"]["foot"] = [round((440 - bbx[0]) * 0.34, 1), round((bbx[3] - bbx[1]) * 0.34, 1)]
PR = prep(load("parcel_bg3"), 0.26, k=0.95, rimw=5, line=3)
bake(PR, "road_parcel", sh=None, pad=(0, 0, 0, 0))
art["road_parcel"]["anchors"]["foot"] = [round(PR.width / 2, 1), round(PR.height - 6, 1)]

# ---------------------------------------------------------------- layout (кадр 1170x2532, как screen_bag.jpg)
SH = art["shelf"]
layout = {
    "frame": [W, H],
    "bag": {
        "title": {"hole": [595, 236], "angle": -2, "scale": 1.0},
        "shelves": [{"x": 585 - S.width / 2 - PAD_L, "y": 530 - PAD_T}, {"x": 585 - S.width / 2 - PAD_L, "y": 1000 - PAD_T}],
        "slots": [{"cx": 270, "base": 552, "tag": [160, 590], "tagAngle": -4},
                  {"cx": 880, "base": 552, "tag": [770, 590], "tagAngle": 3},
                  {"cx": 270, "base": 1022, "tag": [160, 1060], "tagAngle": -3},
                  {"cx": 880, "base": 1022, "tag": [770, 1060], "tagAngle": 4}],
        "bagRing": [470, 1262],
        "bagNail": [470, 1250],
        "arrow": {"right": 1136, "bottom": 2420},
    },
    "letter": {"sheetCenter": [585, 214 + sheet.height / 2], "envelope": [44, 1700], "attachment": [520, 1640],
               "button": {"cx": 905, "bottom": 2420}, "openTag": [140, 2300]},
    "delivery": {"resident": {"cx": 330, "bottom": 1720, "height": 640}, "hand": {"cx": 860, "bottom": 2010},
                 "speech": {"x": 70, "y": 260, "width": 1030, "height": 760}},
    "map": {"ribbon": {"cx": 585, "top": 380, "length": 1900}, "roll": {"cx": 585, "y": 150}},
}
json.dump({"art": art, "layout": layout}, open(os.path.join(ROOT, "Postman/GameAssets/UI/ui_ch1.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("ok", len(art), "assets ->", OUTDIR)

# ---------------------------------------------------------------- preview (screen_bag-like) for eyeballing
if PREVIEW:
    os.makedirs(PREVIEW, exist_ok=True)
    def P_(n): return Image.open(os.path.join(OUTDIR, n + ".png")).convert("RGBA")
    cv = world_dim()
    L_ = layout["bag"]
    for s in L_["shelves"]: cv.alpha_composite(P_("shelf"), (int(s["x"]), int(s["y"])))
    names = ["env_plain", "env_fat", "env_wax", "form"]
    for sl, n in zip(L_["slots"], names):
        im = P_(n); b = art[n]["anchors"]["body"]
        cv.alpha_composite(im, (int(sl["cx"] - b[0] - b[2] / 2), int(sl["base"] - b[1] - b[3])))
        t = P_("tag").rotate(-sl["tagAngle"] * 0 + sl["tagAngle"], expand=False)
        h = art["tag"]["anchors"]["hole"]; cv.alpha_composite(t, (int(sl["tag"][0] - h[0]), int(sl["tag"][1] - h[1])))
        nn = P_("nail"); cv.alpha_composite(nn, (int(sl["tag"][0] - nn.width / 2 + 7), int(sl["tag"][1] - nn.height / 2 + 8)))
    bk = P_("bag_back"); ring = art["bag_back"]["anchors"]["ring"]
    bx, by = int(L_["bagRing"][0] - ring[0]), int(L_["bagRing"][1] - ring[1])
    cv.alpha_composite(bk, (bx, by))
    for i, n in enumerate(["stick_plain", "stick_fat", "stick_wax"]):
        st_ = P_(n); sp = art["bag_back"]["anchors"]["slot%d" % i]
        cv.alpha_composite(st_, (int(bx + sp[0] - st_.width / 2), int(by + sp[1] + 60 - st_.height)))
    cv.alpha_composite(P_("bag_front"), (bx, by))
    arr = P_("arrow"); cv.alpha_composite(arr, (L_["arrow"]["right"] - arr.width + PAD_R, L_["arrow"]["bottom"] - arr.height + PAD_B))
    cv.convert("RGB").resize((390, 844), Image.LANCZOS).save(os.path.join(PREVIEW, "bag.jpg"), quality=88)
    print("preview", PREVIEW)
