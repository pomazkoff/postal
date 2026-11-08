#!/usr/bin/env python3
"""Лист гор v2: якоря сдачи, кодировка поля как у Долины, бирки внутри кадра.

Стык с Долиной печатается как замер. Он не обязан быть нулевым: цвет стыка
доделывает художник, и этот прогон его не перекрашивает.
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "Postman/GameAssets/UI/map"
FAILS = []


def fail(msg):
    FAILS.append(msg)


doc = json.loads((MAP / "mountains.json").read_text(encoding="utf-8"))
if doc.get("size") != [1170, 2532] or doc.get("lengthSteps") != 25000 or doc.get("globalStart") != 20000:
    fail("sheet size or chapter span is wrong")
if doc.get("join") != [705.8, 2452.0]:
    fail(f"join {doc.get('join')}")
road = doc["road"]
if len(road) < 300 or abs(road[0][0] - 705.8) > 0.6 or abs(road[0][1] - 2452) > 0.6:
    fail("the road must start at the saddle join")
length = 0.0
for a, b in zip(road, road[1:]):
    length += math.hypot(b[0] - a[0], b[1] - a[1])
if abs(length - 2432.4) > 2:
    fail(f"road arc {length:.1f}, expected about 2432")
field = doc.get("field") or {}
if field.get("decodeScale") != 1.3 or field.get("decodeBias") != -0.1:
    fail("the mountain field must use the valley decode")

anchors = {s["id"]: s for s in doc["settlements"]}
expect = {
    "gar": (2800, 863.0),
    "penki": (6500, 509.9),
    "khomut": (11000, 997.8),
    "repka": (15500, 300.0),
    "krivulya": (16500, 704.7),
    "gorlovina": (24000, 450.1),
}
if list(anchors) != list(expect):
    fail(f"place order {list(anchors)}")
for pid, (step, x) in expect.items():
    got = anchors[pid]
    if got["step"] != step or abs(got["x"] - x) > 0.2:
        fail(f"{pid} step/anchor {got['step']} {got['x']}")
    rect = (got["x"] - got["w"] / 2, got["y"] - got["h"], got["x"] + got["w"] / 2, got["y"])
    if rect[0] < 8 or rect[2] > 1162 or rect[1] < 8 or rect[3] > 2524:
        fail(f"{pid} icon leaves the sheet {rect}")
ids = list(anchors)
for i, a in enumerate(ids):
    ra = anchors[a]
    aa = (ra["x"] - ra["w"] / 2, ra["y"] - ra["h"], ra["x"] + ra["w"] / 2, ra["y"])
    for b in ids[i + 1:]:
        rb = anchors[b]
        bb = (rb["x"] - rb["w"] / 2, rb["y"] - rb["h"], rb["x"] + rb["w"] / 2, rb["y"])
        w = max(0, min(aa[2], bb[2]) - max(aa[0], bb[0]))
        h = max(0, min(aa[3], bb[3]) - max(aa[1], bb[1]))
        if w * h:
            fail(f"{a} overlaps {b}")

pixels = np.array(Image.open(MAP / "mountains_field.png"))
if pixels.shape != (1266, 585) or pixels.min() < 0 or pixels.max() > 230:
    fail(f"field image {pixels.shape} {pixels.min()}..{pixels.max()}")


def decoded(x, y):
    v = pixels[min(int(y / 2), pixels.shape[0] - 1), min(int(x / 2), pixels.shape[1] - 1)]
    return 1.3 * (v / 255.0) - 0.1


hero_y = 2219.0
if not (decoded(697, hero_y) < decoded(*anchors["gorlovina"]["road"]) - 0.4):
    fail("the field does not open from the saddle toward the end")
if decoded(*anchors["gar"]["road"]) < decoded(697, hero_y):
    fail("Gar is behind the hero on the field")

color = Image.open(MAP / "mountains_color.jpg")
pencil = Image.open(MAP / "mountains_pencil.jpg")
if color.size != (1170, 2532) or pencil.size != (1170, 2532):
    fail("color or pencil size")
# Карандаш должен быть светлее цвета, как пластина Долины, и не совпадать с ней.
c = np.array(color.resize((200, 400))).astype(np.int16)
p = np.array(pencil.resize((200, 400))).astype(np.int16)
if abs(c - p).mean() < 40 or p.mean() < c.mean():
    fail("the pencil plate is not the light unwalked twin of the color")

valley = np.array(Image.open(MAP / "map_color.jpg").crop((0, 0, 1170, 560)))
band = np.array(color.crop((0, 1972, 1170, 2532)))
drift = float(np.abs(valley.astype(np.int16) - band.astype(np.int16)).mean())
print(f"seam mean channel drift {drift:.1f} (v2 color, not repainted here)")

screen = (ROOT / "Postman/UI/MapScreen.swift").read_text(encoding="utf-8")
if "map.notDrawn" not in screen.split("drawHero")[0]:
    pass
if "mountainPicture" not in screen or "revealThreshold" not in screen:
    fail("the mountain sheet must use the same color/pencil reveal")
if 'L10n.text("map.notDrawn")' in screen.split("if drawHero")[-1].split("private func openMountain")[0]:
    fail("the connected sheet still pins the missing-art label on the hero")

if FAILS:
    print(f"{len(FAILS)} mountain art check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("mountain art checks ok")
