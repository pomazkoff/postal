#!/usr/bin/env python3
"""Генератор Postman/GameAssets/Data/world.json.

Источник раскладки: walking-sim/assets_ch1/places/compose_places.py (словари P, POSTX, UGSH) —
там пропсы заданы в координатах кадра 1170x2532 относительно почтальона.
Здесь они переводятся в «шаг поселения + смещение dx (px дизайна) от центра почтальона».
JSON можно править руками; скрипт нужен только чтобы пересобрать из compose_places.py.
"""
import json, os, math
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "Postman", "GameAssets")
W, H, GY, PH = 1170, 2532, 1720, 430
PX_PER_STEP = 1.17            # 1000 шагов ≈ 1 экран ширины (chapter1-timeline.md §0)
POSTMAN_W = 167               # ширина кадра 03_passing_R при высоте 430 (bbox альфы)

SETTLEMENTS = [
    # id, короткое, родительный (для «до …»), полное, шаг
    ("pochta", "Почта", "Почты", "Почта на Развилке", 0),
    ("svai", "Сваи", "Свай", "Сваи", 2500),
    ("zvonarnya", "Звонарня", "Звонарни", "Звонарня", 5600),
    ("kadushki", "Кадушки", "Кадушек", "Кадушки", 8700),
    ("nii", "НИИ", "НИИ", "НИИ «Радиотень»", 12800),
    ("sedlo", "Седло", "Седла", "Ящик на Седле", 20000),
]
# --- из compose_places.py: (файл, x левого края в кадре, высота в кадре) ---
P = {
"pochta":[("el_pochta_pole_nowires",930,1150),("place_pochta_main",-60,1320),("el_pochta_bench",640,170),("el_pochta_barrow",960,165)],
"svai":[("place_svai_main",-160,1460),("el_svai_kuzma_pole",840,900),("el_svai_mitya_antenna",1010,640),("el_svai_fish_rope",660,300)],
"zvonarnya":[("el_zvon_candle_hut",700,440),("place_zvonarnya_main",-20,1700),("el_zvon_hives",560,360),("el_zvon_vera_bike",930,250)],
"kadushki":[("place_kadushki_main",-922,1500),("el_kad_shop_vat",860,780),("el_kad_dill_rope",700,330),("el_kad_well_box2",1010,400)],
"nii":[("place_nii_main",-1100,1150),("el_nii_fence",300,280),("el_nii_dish_goats",720,470),("el_nii_vera_box",470,360)],
"sedlo":[("el_sedlo_firs",-180,1050),("el_sedlo_raw_clay",820,820),("place_sedlo_main",120,1560),("el_sedlo_barrier",640,460)],
}
POSTX = {"pochta":680,"svai":560,"zvonarnya":600,"kadushki":520,"nii":620,"sedlo":620}
UG = {"pochta":"ug_pochta","svai":"ug_svai","zvonarnya":"ug_zvonarnya","kadushki":"ug_kadushki","nii":"ug_nii","sedlo":"ug_sedlo"}
UGSH = {"pochta":-480}
UG_SCALE = 2.0
UG_TILE_W = 1148 * UG_SCALE
# Переходные модули: рабочие позиции (предв.) — посередине больших промежутков Кадушки–НИИ и НИИ–Седло.
TRANS = [("ug_trans_a", 10690), ("ug_trans_b", 16298)]

def size(rel):
    with Image.open(os.path.join(ASSETS, "Chapter1", rel + ".png")) as im:
        return list(im.size)

def main():
    props = []
    z = 0
    for sid, short, gen, full, step in SETTLEMENTS:
        cx = POSTX[sid] + POSTMAN_W / 2
        for f, x, h in P[sid]:
            rel = "places/" + f
            props.append({"image": rel, "layer": "main", "step": step, "dx": round(x - cx, 1),
                          "height": h, "sink": 40, "z": z, "pixelSize": size(rel)})
            z += 1
    # Дорога между поселениями (обочины main, холмы mid, хребты far, передний план fg) —
    # раскладка генерируется walking-sim/assets_ch1/road/build_road.py и копируется сюда.
    road = os.path.join(HERE, "ch1_road_props.json")
    if os.path.exists(road):
        with open(road, encoding="utf-8") as fh:
            for p in json.load(fh):
                p["pixelSize"] = size(p["image"])
                props.append(p)
    # подземные модули: желаемые центры; промежутки между ними движок заполняет нейтральным тайлом N (с растяжкой по X)
    want = []
    for sid, short, gen, full, step in SETTLEMENTS:
        cx = POSTX[sid] + POSTMAN_W / 2
        want.append(("underground/" + UG[sid], step, 585 + UGSH.get(sid, 0) - cx))
    for name, step in TRANS:
        want.append(("underground/" + name, step, 0.0))
    modules = [{"image": img, "step": step, "dx": round(dx, 1)} for img, step, dx in want]

    quests = [
        {"untilStep": 2900, "telegram": "Отнести письмо Нины Кузьме в Сваи", "lettersInBag": 3},
        {"untilStep": 6000, "telegram": "Отнести письмо Мити Пимену в Звонарню", "lettersInBag": 2},
        {"untilStep": 9100, "telegram": "Дойти до Кадушек, заглянуть в ящик №2", "lettersInBag": 2},
        {"untilStep": 9300, "telegram": "Забрать 12 батареек в Лавке для Веры", "lettersInBag": 2},
        {"untilStep": 13200, "telegram": "Отнести батарейки и письмо Пимена Вере в НИИ", "lettersInBag": 3},
        {"untilStep": 20000, "telegram": "Донести письмо Нины до ящика на Седле", "lettersInBag": 1},
    ]
    world = {
        "_comment": "Единицы: px дизайна кадра 1170x2532 (y сверху вниз, как в макетах). step = шаг от начала главы, dx = смещение левого края пропса (у подземных модулей — центра) от центра почтальона, стоящего на этом шаге. Все шаги предв.",
        "game": {
            "totalSteps": 150000,
            "pixelsPerStep": PX_PER_STEP,
            "designWidth": W, "designHeight": H, "roadLineY": GY,
            "postman": {"height": PH, "feetBelowRoad": 30, "screenX": 0.55, "idleFrame": 2, "rigSourceHeight": 1028, "rigCenterX": 395, "jitter": "reference"},
            "camera": {"snapBackDelay": 1.2, "snapBackRate": 4.0, "leftMarginSteps": 200},
            "walking": {"speed": 450, "maxCatchUpSeconds": 6, "teleportGapSteps": 5000, "teleportLandBeforeSteps": 600},
        },
        "layers": {
            "sky": {"topColor": "#14505F", "bottomColor": "#3C7873"},
            "far": {"parallax": 0.1, "image": "places/bg_far_ridges_tile", "top": GY - 1050, "height": 1100, "brightness": 1.0, "fadeTopFraction": 0.22, "pixelSize": size("places/bg_far_ridges_tile")},
            "mid": {"parallax": 0.4, "image": "places/bg_mid_fields_tile", "top": GY - 470, "height": 520, "brightness": 0.82, "fadeTopFraction": 0, "pixelSize": size("places/bg_mid_fields_tile")},
            "mainParallax": 1.0, "undergroundParallax": 1.0, "foregroundParallax": 1.3,
        },
        "chapters": [{
            "id": 1, "title": "Долина", "startStep": 0, "lengthSteps": 20000, "assetsFolder": "Chapter1",
            "settlements": [{"id": s, "name": n, "nameGenitive": g, "fullName": f, "step": st} for s, n, g, f, st in SETTLEMENTS],
            "props": props,
            "underground": {"neutralTile": "underground/ug_neutral_tile", "top": GY - 20, "scale": UG_SCALE,
                             "tilePixelSize": [1148, 415], "minGapFraction": 0.3, "modules": modules},
            "quests": quests,
            "rawClayAfterStep": 20000,
        }],
    }
    out = os.path.join(ASSETS, "Data", "world.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(world, fh, ensure_ascii=False, indent=1)
    print("wrote", out, len(props), "props")

if __name__ == "__main__":
    main()
