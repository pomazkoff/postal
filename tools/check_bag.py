#!/usr/bin/env python3
"""Сумка без лимита мест: миграция старых сейвов и точки передачи.

Правила совпадают с Postman/App/BagPolicy.swift. Реальных файлов сейва не читает.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


HANDOFF = {
    (1, "l1"): "d_l1", (1, "l2"): "d_l2", (1, "l3"): "finale", (1, "l7"): "finale",
    (1, "l4"): "d_vera", (1, "l5"): "d_vera", (1, "batteries"): "d_vera", (1, "l6"): "d_l6",
    (2, "l1"): "s_nii_drop", (2, "l2"): "s_nii_drop",
    (2, "l3"): "finale", (2, "l4"): "finale", (2, "l5"): "finale", (2, "l6"): "finale",
    (2, "l7"): "finale", (2, "l8"): "finale", (2, "note_gar"): "finale",
}
PICKUP = {
    (1, "l5"): "p_l5", (1, "l6"): "p_l6", (1, "batteries"): "p_bat",
    (1, "animal_cat_stamp"): "e_animal_cat",
    (2, "l1"): "p_l1", (2, "l2"): "p_l2", (2, "l3"): "p_l3", (2, "l4"): "p_l4",
    (2, "l5"): "p_l5", (2, "l6"): "p_l6", (2, "l7"): "p_l7", (2, "l8"): "p_l8",
    (2, "l9"): "p_l9", (2, "note_gar"): "p_note_gar",
    (2, "animal_raven_scrap"): "e_animal_raven", (2, "animal_dog_horn"): "p_animal_dog_find",
}
CARRIED = {"inBag", "inPocket"}
READ_ON = {(1, "l7"), (2, "l9")}


def close_status(chapter, item):
    if (chapter, item) in READ_ON:
        return "read"
    if chapter == 1 and item == "l3":
        return "sent"
    return "delivered"


def migrate(chapter, candidates, items, done, sorting, settled):
    items = dict(items)
    settled = set(settled)
    logs = []
    if not sorting:
        took = False
        for item in candidates:
            if items.get(item) in ("atPost", None):
                items[item] = "inBag"
                took = True
        sorting = True
        if took:
            logs.append("bag.took.all")
    else:
        recovered = False
        for item in candidates:
            if items.get(item) == "atPost" and HANDOFF.get((chapter, item)) not in done:
                items[item] = "inBag"
                recovered = True
        for item, status in list(items.items()):
            if status != "leftBehind":
                continue
            pickup = PICKUP.get((chapter, item))
            if pickup in done and HANDOFF.get((chapter, item)) not in done:
                items[item] = "inBag"
                recovered = True
        if recovered:
            logs.append("bag.recovered")
    for trigger in sorted(done):
        if trigger in settled:
            continue
        moved = False
        for item, status in list(items.items()):
            if HANDOFF.get((chapter, item)) == trigger and status in CARRIED:
                items[item] = close_status(chapter, item)
                moved = True
        settled.add(trigger)
        if moved:
            logs.append(f"bag.handoff.{trigger}")
    return items, sorting, settled, logs


# Свежая глава 1: разбора ещё не было. Почтальон берёт все три письма.
items, sorting, settled, logs = migrate(1, ["l1", "l2", "l3"],
                                        {"l1": "atPost", "l2": "atPost", "l3": "atPost", "l4": "inPocket"},
                                        set(), False, set())
if items["l1"] != "inBag" or items["l2"] != "inBag" or items["l3"] != "inBag" or items["l4"] != "inPocket":
    fail(f"fresh chapter 1 did not take every letter: {items}")
if logs != ["bag.took.all"]:
    fail(f"fresh chapter 1 note: {logs}")
if not sorting:
    fail("fresh chapter 1 still asks what to take")
again, _, _, logs2 = migrate(1, ["l1", "l2", "l3"], items, set(), True, settled)
if logs2 or again["l1"] != "inBag":
    fail("taking every letter is not idempotent")

# Больше трёх подборов не оставляет письма на дороге: leftBehind после уже случившегося подбора возвращается.
items, _, _, _ = migrate(1, ["l1", "l2", "l3"],
                         {"l1": "inBag", "l2": "inBag", "l3": "inBag", "l6": "leftBehind", "batteries": "leftBehind"},
                         {"sort", "p_l6", "p_bat"}, True, {"sort"})
if items["l6"] != "inBag" or items["batteries"] != "inBag":
    fail(f"capacity leftovers were not recovered: {items}")

# Уже врученное не возвращается, даже если когда-то не влезло.
items, _, _, logs = migrate(1, ["l1", "l2", "l3"],
                            {"l1": "delivered", "l6": "leftBehind"},
                            {"d_l1", "d_l6", "p_l6"}, True, set())
if items["l1"] != "delivered" or items["l6"] != "leftBehind":
    fail(f"a finished delivery came back: {items}")
if logs:
    fail(f"a finished delivery wrote a new handoff note: {logs}")

# Старый отказ на утреннем разборе: письмо ещё впереди — берём. Уже пройденная сдача — не берём.
items, _, _, _ = migrate(1, ["l1", "l2", "l3"],
                         {"l1": "atPost", "l2": "delivered", "l3": "atPost"},
                         {"sort", "d_l2"}, True, {"sort"})
if items["l1"] != "inBag" or items["l3"] != "inBag" or items["l2"] != "delivered":
    fail(f"old shelf choice was mishandled: {items}")

# Середина главы 2, как на скрине: Нине и Мите всё ещё в сумке, ящик НИИ уже был.
items, sorting, settled, logs = migrate(
    2, [],
    {"l1": "inBag", "l2": "inBag", "note_gar": "inPocket", "animal_raven_scrap": "inPocket",
     "l9": "inPocket",
     "l5": "onRoad", "animal_dog_horn": "leftBehind"},
    {"p_l1", "p_l2", "s_nii_drop", "p_note_gar", "e_animal_raven", "arrive_penki"},
    True, set())
if items["l1"] != "delivered" or items["l2"] != "delivered":
    fail(f"chapter 2 mail did not leave at the Institute box: {items}")
if items["note_gar"] != "inPocket" or items["animal_raven_scrap"] != "inPocket" or items["l9"] != "inPocket":
    fail(f"later mail, the telegram or a find was cleared too early: {items}")
if items["animal_dog_horn"] != "leftBehind":
    fail("a find whose pickup has not happened was picked up by migration")
if logs != ["bag.handoff.s_nii_drop"]:
    fail(f"midway chapter 2 note: {logs}")
again, _, settled2, logs2 = migrate(2, [], items, {"p_l1", "p_l2", "s_nii_drop", "p_note_gar", "e_animal_raven", "arrive_penki"}, True, settled)
if logs2 or again != items or settled2 != settled:
    fail("migration is not idempotent")

# Ветер и вскрытие не трогаются.
items, _, _, _ = migrate(1, ["l1", "l2", "l3"],
                         {"l3": "lostWind", "l5": "inBag"},
                         {"e_wind", "p_l5"}, True, set())
if items["l3"] != "lostWind" or items["l5"] != "inBag":
    fail(f"wind or an unopened letter changed: {items}")

# Больше четырёх вещей остаются доступными: миграция ничего не отрезает.
many = {f"l{i}": "inBag" for i in range(1, 9)}
many["note_gar"] = "inBag"
many["animal_raven_scrap"] = "inPocket"
kept, _, _, _ = migrate(2, [], many, set(), True, set())
if len([s for s in kept.values() if s in ("inBag", "inPocket")]) != 10:
    fail("items were dropped to fit a shelf")

# Телеграмма уже подобрана, но лист ещё не закрывали — она остаётся, чтобы её можно было прочитать.
items, _, _, logs = migrate(2, [], {"l9": "inPocket"}, {"p_l9"}, True, set())
if items["l9"] != "inPocket" or logs:
    fail(f"unread telegram was removed: {items} {logs}")

# Письмо Нины сыну, уже донесённое до Седла, остаётся «отправлено», а не «вручено».
items, _, _, _ = migrate(1, ["l1", "l2", "l3"], {"l3": "inBag", "l7": "inBag"}, {"finale"}, True, set())
if items["l3"] != "sent" or items["l7"] != "read":
    fail(f"saddle mail closed with the wrong status: {items}")

src = (ROOT / "Postman/App/BagPolicy.swift").read_text(encoding="utf-8")
engine = (ROOT / "Postman/App/ChapterEngine.swift").read_text(encoding="utf-8")
view = (ROOT / "Postman/UI/BagScreen.swift").read_text(encoding="utf-8")
if "freeSlots" in engine:
    fail("pickup still refuses mail when the bag is full")
if "prefix(4)" in view or "bag.used" in view or "bag.pocket" in view:
    fail("the bag still hides items or talks about pockets and a slot limit")
if "needsSorting: Bool { false }" not in engine:
    fail("the morning choice can still block the road")
body = src.split("static func handoff", 1)[1].split("static func pickupEvent", 1)[0]
for (chapter, item), event in HANDOFF.items():
    needle = f'({chapter}, "{item}")'
    idx = body.find(needle)
    window = body[idx:idx + 240] if idx >= 0 else ""
    if f'return "{event}"' not in window:
        fail(f"handoff {chapter}/{item} is not {event}")
if '(2, "l9")' in body:
    fail("the telegram is taken out of the bag at pickup, before it can be read")
ru = (ROOT / "Postman/Resources/ru.lproj/Localizable.strings").read_text(encoding="utf-8")
en = (ROOT / "Postman/Resources/en.lproj/Localizable.strings").read_text(encoding="utf-8")
for key in ["bag.mail", "bag.personal", "bag.look", "bag.took.all", "bag.recovered", "bag.chapter.kept",
            "bag.handoff.s_nii_drop", "bag.handoff.finale", "bag.handoff.p_l9",
            "bag.act.1.l1", "bag.act.1.l6", "bag.act.2.l1", "bag.act.2.note_gar",
            "bag.keep.animal_cat_stamp", "bag.keep.animal_raven_scrap", "bag.keep.animal_dog_horn"]:
    if f'"{key}"' not in ru or f'"{key}"' not in en:
        fail(f"missing bag string {key}")
ch1 = (ROOT / "Postman/GameAssets/Data/chapter1_story.json").read_text(encoding="utf-8")
ch2 = (ROOT / "Postman/GameAssets/Data/chapter2_story.json").read_text(encoding="utf-8")
if '"id": "animal_cat_stamp"' in ch1 and '"art": "form"' in ch1.split('"id": "animal_cat_stamp"', 1)[1][:400]:
    fail("the brass stamp still uses the requisition picture")
arts = {
    "note_gar": "env_plain",
    "animal_raven_scrap": "att_wrapper_yellow",
    "animal_dog_horn": "pin_red",
    "l9": "card_telegram",
}
for name, art in arts.items():
    chunk = ch2.split(f'"id": "{name}"', 1)[1][:500]
    if f'"art": "{art}"' not in chunk:
        fail(f"{name} does not use {art}")

if FAILS:
    print(f"{len(FAILS)} bag check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("bag checks ok")
