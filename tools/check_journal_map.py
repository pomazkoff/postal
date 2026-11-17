#!/usr/bin/env python3
"""Сводка и карта: кроп ящика и единственный лист Долины.

Статическая проверка. Кадр с телефона здесь не снимался.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


def sheet_step(chapter_id, chapter_steps, sheet_length):
    if chapter_id == 1:
        return min(max(0, chapter_steps), sheet_length)
    return sheet_length


journal = (ROOT / "Postman/UI/JournalScreen.swift").read_text(encoding="utf-8")
picture = journal.split("private func picture", 1)[1]
if "scaledToFill()" in picture or "scaleEffect(1.5)" in picture:
    fail("the journal frame must not crop a place cutout into a texture")
if "scaledToFit()" not in picture:
    fail("a place cutout must be shown whole")

sedlo = ROOT / "Postman/GameAssets/Chapter2/places/place_sedlo_main.png"
if not sedlo.exists():
    fail("chapter 2 saddle art is missing")

map_json = json.loads((ROOT / "Postman/GameAssets/UI/map/map.json").read_text(encoding="utf-8"))
ids = [p["id"] for p in map_json["settlements"]]
if ids != ["pochta", "svai", "zvonarnya", "kadushki", "nii", "sedlo"]:
    fail(f"the only parchment is the valley, got {ids}")
if map_json["lengthSteps"] != 20000:
    fail("the parchment length is the valley, 20000 steps")
# Лист гор лежит рядом, но не подменяет поселения Долины в map.json.

if sheet_step(2, 2419, 20000) != 20000:
    fail("chapter 2 steps must not land on the Stilts")
if sheet_step(1, 2419, 20000) != 2419:
    fail("chapter 1 still uses its own steps")
screen = (ROOT / "Postman/UI/MapScreen.swift").read_text(encoding="utf-8")
if "sheetStep" not in screen or "map.valleyOnly" not in screen or "map.notDrawn" not in screen:
    fail("the valley sheet must say the mountains are not drawn")
if "StoryConfig.load(chapter: 1)" not in screen:
    fail("valley places must still open their own arrival lines")

ru = (ROOT / "Postman/Resources/ru.lproj/Localizable.strings").read_text(encoding="utf-8")
en = (ROOT / "Postman/Resources/en.lproj/Localizable.strings").read_text(encoding="utf-8")
for key in ("map.valleyOnly", "map.notDrawn", "map.sheetEnd", "map.elsewhere",
            "menu.reminders.wake.none", "menu.reminders.wake.last"):
    if f'"{key}"' not in ru or f'"{key}"' not in en:
        fail(f"missing {key}")

if FAILS:
    print(f"{len(FAILS)} journal/map check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("journal/map checks ok (valley sheet only; journal shows the whole cutout)")
