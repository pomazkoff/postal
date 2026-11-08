#!/usr/bin/env python3
"""Шов Долины и гор: шаги из world.json, без выдуманных мест.

Пока mountains.json нет, шаг 2419 главы 2 не является точкой у Свай.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


VALLEY_JOIN = (705.8, 480.0)
MOUNTAIN_JOIN = (705.8, 2452.0)
PLACES = {
    "sedlo": 0,
    "gar": 2800,
    "penki": 6500,
    "khomut": 11000,
    "repka": 15500,
    "krivulya": 16500,
    "gorlovina": 24000,
}


def road_point(points, fraction):
    cum = [0.0]
    for a, b in zip(points, points[1:]):
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    s = min(1.0, max(0.0, fraction)) * cum[-1]
    for i in range(len(cum) - 1):
        if cum[i + 1] >= s or i == len(cum) - 2:
            span = max(1e-9, cum[i + 1] - cum[i])
            t = (s - cum[i]) / span
            a, b = points[i], points[i + 1]
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    return points[-1]


def atlas_point(global_step, valley_road, mountains):
    if mountains is not None and global_step >= 20000:
        local = min(25000, global_step - 20000)
        return road_point(mountains, local / 25000)
    local = min(20000, max(0, global_step))
    return road_point(valley_road, local / 20000)


world = json.loads((ROOT / "Postman/GameAssets/Data/world.json").read_text(encoding="utf-8"))
chapter2 = world["chapters"][1]
got = {s["id"]: s["step"] for s in chapter2["settlements"]}
if got != PLACES:
    fail(f"chapter 2 settlements drifted: {got}")
if chapter2["startStep"] != 20000 or chapter2["lengthSteps"] != 25000:
    fail("chapter 2 does not run 20000..45000")

map_json = json.loads((ROOT / "Postman/GameAssets/UI/map/map.json").read_text(encoding="utf-8"))
road = [tuple(p) for p in map_json["road"]]
if abs(road[-1][0] - VALLEY_JOIN[0]) > 0.05 or abs(road[-1][1] - VALLEY_JOIN[1]) > 0.05:
    fail(f"valley road no longer ends at the saddle: {road[-1]}")

# Шаг 2419 на долине — это Сваи. Запасной лист так делать не должен.
wrong = road_point(road, 2419 / 20000)
if wrong[1] < 1500:
    fail("2419 on the valley is no longer down by the Stilts; the regression moved")
held = atlas_point(22419, road, None)
if abs(held[0] - VALLEY_JOIN[0]) > 1 or abs(held[1] - VALLEY_JOIN[1]) > 1:
    fail(f"without mountain art, chapter 2 must stay on the saddle, got {held}")

straight = [MOUNTAIN_JOIN, (MOUNTAIN_JOIN[0], MOUNTAIN_JOIN[1] - 2432.0)]
moved = atlas_point(22419, road, straight)
if moved[1] > 2300:
    fail(f"chapter 2 step 2419 stayed near the saddle instead of moving up the road: {moved}")
if abs(moved[0] - 658) < 5 and abs(moved[1] - 1955) < 20:
    fail("chapter 2 step 2419 landed on the Stilts")

src = (ROOT / "Postman/Model/MapAtlas.swift").read_text(encoding="utf-8")
for token in ("705.8", "2452", "gar", "gorlovina", "mountains_color.jpg", "mountains.json"):
    if token not in src:
        fail(f"atlas is missing {token}")
screen = (ROOT / "Postman/UI/MapScreen.swift").read_text(encoding="utf-8")
if "centersHero" not in screen or "startStep + step" not in screen:
    fail("the map must scroll to the global step once the mountain sheet exists")
if "map.notDrawn" not in screen:
    fail("until the files exist, the valley sheet must still say the mountains are not drawn")
if (ROOT / "Postman/GameAssets/UI/map/mountains_color.jpg").exists():
    fail("a mountain picture is already in the app; this stage was not supposed to invent one")

if FAILS:
    print(f"{len(FAILS)} map atlas check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("map atlas checks ok (no mountain art in the app; saddle join is the valley road end)")
