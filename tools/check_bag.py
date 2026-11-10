#!/usr/bin/env python3
"""Сумка без лимита мест: миграция старых сейвов и точки передачи.

Правила совпадают с Postman/App/BagPolicy.swift. Реальных файлов сейва не читает.
Сдача письма всегда строго после подбора и, на бирке, строго впереди игрока.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


# (событие, шаг главы). Первая точка — та, что задумана. Дальше — запас, если её уже прошли.
DROPS = {
    (1, "l1"): [("d_l1", 2900)],
    (1, "l2"): [("d_l2", 6000)],
    (1, "l3"): [("finale", 20000)],
    (1, "l7"): [("finale", 20000)],
    (1, "l4"): [("d_vera", 13200)],
    (1, "l5"): [("d_vera", 13200)],
    (1, "batteries"): [("d_vera", 13200)],
    (1, "l6"): [("d_l6", 9100)],
    (2, "l1"): [("s_nii_drop", 400), ("e_khomut", 11000), ("finale", 25000)],
    (2, "l2"): [("s_nii_drop", 400), ("e_khomut", 11000), ("finale", 25000)],
    (2, "note_gar"): [("e_khomut", 11000), ("finale", 25000)],
    (2, "l3"): [("e_khomut", 11000), ("finale", 25000)],
    (2, "l4"): [("e_khomut", 11000), ("finale", 25000)],
    (2, "l5"): [("e_khomut", 11000), ("finale", 25000)],
    (2, "l6"): [("finale", 25000)],
    (2, "l7"): [("finale", 25000)],
    (2, "l8"): [("finale", 25000)],
    (3, "l1"): [("d_gat", 4000)],
    (3, "l4"): [("d_top", 9000)],
    (3, "note_fedya"): [("d_top", 9000)],
    (3, "l2"): [("d_torf", 12500)],
    (3, "l3"): [("d_barge", 16500)],
    (3, "l5"): [("d_reeds", 20000)],
    (3, "l7"): [("d_reeds", 20000)],
    (3, "l9"): [("d_otstoy", 28000)],
    (3, "find_edge"): [("d_gat", 4000)],
    (3, "find_tag"): [("d_top", 9000)],
    (3, "find_card"): [("d_top", 9000)],
    (3, "find_pole"): [("d_torf", 12500)],
    (3, "find_graph"): [("d_torf", 12500)],
    (3, "find_pass"): [("d_barge", 16500)],
}
HANDOFF = {key: drops[0][0] for key, drops in DROPS.items()}
PICKUP = {
    (1, "l5"): "p_l5", (1, "l6"): "p_l6", (1, "batteries"): "p_bat",
    (1, "animal_cat_stamp"): "e_animal_cat",
    (2, "l1"): "p_l1", (2, "l2"): "p_l2", (2, "l3"): "p_l3", (2, "l4"): "p_l4",
    (2, "l5"): "p_l5", (2, "l6"): "p_l6", (2, "l7"): "p_l7", (2, "l8"): "p_l8",
    (2, "l9"): "p_l9", (2, "note_gar"): "p_note_gar",
    (2, "animal_raven_scrap"): "e_animal_raven", (2, "animal_dog_horn"): "p_animal_dog_find",
    (3, "l1"): "p_l1", (3, "l2"): "p_l2", (3, "l3"): "p_l3", (3, "l4"): "p_l4",
    (3, "l5"): "p_l5", (3, "l6"): "p_l6", (3, "l7"): "p_l7", (3, "l8"): "p_l8",
    (3, "l9"): "p_l9", (3, "l10"): "p_l10", (3, "note_fedya"): "e_fedya_help",
    (3, "find_edge"): "p_edge", (3, "find_tag"): "e_fedya_help", (3, "find_card"): "p_card",
    (3, "find_pole"): "p_pole", (3, "find_graph"): "p_graph", (3, "find_pass"): "p_pass",
}
CARRIED = {"inBag", "inPocket"}
READ_ON = {(1, "l7"), (2, "l9"), (3, "l6"), (3, "l8"), (3, "l10")}


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
    moved_at = set()
    for item, status in list(items.items()):
        if status not in CARRIED:
            continue
        hit = next((event for event, _step in DROPS.get((chapter, item), []) if event in done), None)
        if hit is None or hit in settled:
            continue
        items[item] = close_status(chapter, item)
        moved_at.add(hit)
    for trigger in sorted(done):
        if trigger in settled:
            continue
        settled.add(trigger)
        if trigger in moved_at:
            logs.append(f"bag.handoff.{trigger}")
    return items, sorting, settled, logs


def ahead(chapter, item, player_step):
    return next((drop for drop in DROPS.get((chapter, item), []) if drop[1] > player_step), None)


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
hud = (ROOT / "Postman/UI/HUDView.swift").read_text(encoding="utf-8")
if "bagItems.count + engine.pocketItems.count" in hud:
    fail("the road bag counts personal finds as letters")
if "engine.mailItems.count" not in hud or "Format.things" not in hud:
    fail("the road bag does not count mail, and finds, with their own words")
if "bag.more" not in view:
    fail("a long bag does not say there is more below")
journal = (ROOT / "Postman/UI/JournalScreen.swift").read_text(encoding="utf-8")
if 'case "handoff": return "env_plain"' not in journal:
    fail("a mail handoff card has no picture")
if "entry.step > 0" not in journal:
    fail("a journal card still prints a zero step count")
if "showsPicture" not in journal:
    fail("a journal card draws a frame when it has no picture")
if 'Text(entry.place ?? "")' in journal:
    fail("an empty journal frame is still filled with a blank caption")
if "step: event?.step ?? 0" not in engine:
    fail("a migrated handoff is still logged at step 0")
if "prefix(4)" in view or "prefix(3)" in view or "bag.used" in view or "bag.pocket" in view or "Ink.chalk" in view:
    fail("the bag still hides items, counts slots, or writes chalk names on three compartments")
if 'name: "shelf"' not in view and 'place("shelf"' not in view:
    fail("the bag is no longer the wooden shelves")
if "needsSorting: Bool { false }" not in engine:
    fail("the morning choice can still block the road")
body = src.split("static func drops", 1)[1].split("static func handoff", 1)[0]
for (chapter, item), drops in DROPS.items():
    needle = f'({chapter}, "{item}")'
    idx = body.find(needle)
    window = body[idx:idx + 420] if idx >= 0 else ""
    if f'return [Drop(event: "{drops[0][0]}"' not in window and f'Drop(event: "{drops[0][0]}"' not in window:
        fail(f"handoff {chapter}/{item} is not {drops[0][0]}")
    for event, step in drops:
        if f'Drop(event: "{event}", step: {step})' not in window and not (
            event == drops[0][0] and f'step: {step}' in window
        ):
            # Несколько писем делят одну строку return. Ищем шаг во всём теле функции.
            if f'Drop(event: "{event}", step: {step})' not in body:
                fail(f"drop {chapter}/{item} lost {event} at {step}")
if '(2, "l9")' in body:
    fail("the telegram is taken out of the bag at pickup, before it can be read")
ru = (ROOT / "Postman/Resources/ru.lproj/Localizable.strings").read_text(encoding="utf-8")
en = (ROOT / "Postman/Resources/en.lproj/Localizable.strings").read_text(encoding="utf-8")
for key in ["bag.mail", "bag.personal", "bag.more", "bag.look", "bag.took.all", "bag.recovered", "bag.chapter.kept",
            "bag.handoff.s_nii_drop", "bag.handoff.finale", "bag.handoff.1.finale", "bag.handoff.2.finale",
            "bag.handoff.e_khomut", "bag.handoff.p_l9",
            "bag.act.1.l1", "bag.act.1.l6", "bag.act.2.l1", "bag.act.2.note_gar",
            "bag.act.3.l1", "bag.act.3.l4", "bag.act.3.note_fedya", "bag.act.3.l2",
            "bag.act.3.l3", "bag.act.3.l5", "bag.act.3.l7", "bag.act.3.l9",
            "bag.act.3.find_edge", "bag.act.3.find_tag", "bag.act.3.find_card",
            "bag.act.3.find_pole", "bag.act.3.find_graph", "bag.act.3.find_pass",
            "bag.act.drop.2.e_khomut", "bag.act.drop.2.finale",
            "bag.keep.animal_cat_stamp", "bag.keep.animal_raven_scrap", "bag.keep.animal_dog_horn"]:
    if f'"{key}"' not in ru or f'"{key}"' not in en:
        fail(f"missing bag string {key}")
ch1 = (ROOT / "Postman/GameAssets/Data/chapter1_story.json").read_text(encoding="utf-8")
ch2 = (ROOT / "Postman/GameAssets/Data/chapter2_story.json").read_text(encoding="utf-8")
if '"id": "animal_cat_stamp"' in ch1 and '"art": "form"' in ch1.split('"id": "animal_cat_stamp"', 1)[1][:400]:
    fail("the brass stamp still uses the requisition picture")
arts = {
    "note_gar": "env_plain",
    "animal_raven_scrap": "find_cloth",
    "animal_dog_horn": "find_horn",
    "l9": "card_telegram",
}
if '"art": "find_stamp"' not in ch1.split('"id": "animal_cat_stamp"', 1)[1][:400]:
    fail("the brass stamp has no picture of its own")
form_items = []
for story in (ch1, ch2):
    parts = story.split('"art": "form"')
    form_items.append(len(parts) - 1)
if form_items != [1, 0]:
    fail(f"the requisition picture is reused: {form_items}")
ui = (ROOT / "Postman/GameAssets/UI/ui_ch1.json").read_text(encoding="utf-8")
for name in ("find_cloth", "find_horn", "find_stamp"):
    if f'"image": "UI/ch1/{name}"' not in ui:
        fail(f"{name} is not in the UI catalog")
    if not (ROOT / f"Postman/GameAssets/UI/ch1/{name}.png").exists():
        fail(f"missing picture {name}")
for name, art in arts.items():
    chunk = ch2.split(f'"id": "{name}"', 1)[1][:500]
    if f'"art": "{art}"' not in chunk:
        fail(f"{name} does not use {art}")

# Подбор всегда раньше сдачи. Шаги сверены с событиями глав, а не только со словарём выше.
ch3 = (ROOT / "Postman/GameAssets/Data/chapter3_story.json").read_text(encoding="utf-8")
story_docs = {
    1: json.loads(ch1),
    2: json.loads(ch2),
    3: json.loads(ch3),
}
READ_IN_PLACE = {(1, "l7"), (2, "l9"), (3, "l6"), (3, "l8"), (3, "l10")}
# Находки гл.3 отдаются один раз в ящике впереди. Это не почта и не возврат назад.
GIFT = {
    (3, "find_edge"), (3, "find_tag"), (3, "find_card"),
    (3, "find_pole"), (3, "find_graph"), (3, "find_pass"),
}


def is_mail(item):
    return item.get("kind") in ("letter", "parcel", "secret") or item["id"] in ("l4", "note_gar", "l9")


def quoted(text, key):
    match = re.search(rf'"{re.escape(key)}"\s*=\s*"((?:\\.|[^"\\])*)"', text)
    return match.group(1) if match else ""


for chapter, doc in story_docs.items():
    steps = {event["id"]: event["step"] for event in doc["events"]}
    for item in doc["items"]:
        key = (chapter, item["id"])
        if not is_mail(item):
            if key in DROPS and key not in GIFT:
                fail(f"a find was given a delivery: {key}")
            if key in GIFT:
                pickup_step = steps.get(PICKUP.get(key), 0)
                delivery_step = DROPS[key][0][1]
                if pickup_step >= delivery_step:
                    fail(f"{key} is picked up at {pickup_step}, which is not before delivery {delivery_step}")
                if steps.get(DROPS[key][0][0]) != delivery_step:
                    fail(f"{key} drop is not the story event")
            continue
        for event, step in DROPS.get(key, []):
            if steps.get(event) != step:
                fail(f"{key} drop {event} is {step} in code and {steps.get(event)} in the story")
        if key in READ_IN_PLACE:
            continue
        if key not in DROPS:
            fail(f"mail {key} has no delivery ahead of the player")
            continue
        pickup_step = steps.get(PICKUP.get(key), 0)
        delivery_step = DROPS[key][0][1]
        if pickup_step >= delivery_step:
            fail(f"{key} is picked up at {pickup_step}, which is not before delivery {delivery_step}")

if "Кадушкам. Жив. Калитку чиню. Чаю мало. Если оказия — соли пришлите. Л." not in ch2:
    fail("the ranger's note to the Tubs was rewritten")

# iPhone, сборка 1.0(13): карта «Вы здесь 26 679», сразу за Пеньками (26 500). Глава 2 начинается с 20 000.
penki_step = 26679 - 20000
note_target = ahead(2, "note_gar", penki_step)
if penki_step != 6679 or note_target != ("e_khomut", 11000) or note_target[1] <= penki_step:
    fail(f"at world step 26679 the note to the Tubs does not point ahead: {note_target}")
note_pickup = {event["id"]: event["step"] for event in story_docs[2]["events"]}["p_note_gar"]
if note_pickup >= note_target[1]:
    fail("the note is still picked up at or after the Collar")
if "НИИ" in quoted(ru, "bag.act.2.note_gar") or "Institute" in quoted(en, "bag.act.2.note_gar"):
    fail("the open bag at the Stumps still sends the note back to the Institute")
if "Хомуте" not in quoted(ru, "bag.act.2.note_gar") or "Collar" not in quoted(en, "bag.act.2.note_gar"):
    fail("the note's tag does not name the pass that is still ahead")

held, _, _, held_logs = migrate(
    2, [], {"note_gar": "inPocket"},
    {"p_note_gar", "arrive_gar", "arrive_penki", "s_nii_drop"}, True, set())
if held["note_gar"] != "inPocket" or held_logs:
    fail(f"the note left the bag before the Collar: {held} {held_logs}")

passed_done = {"p_note_gar", "arrive_penki", "e_khomut"}
caught, _, caught_settled, caught_logs = migrate(2, [], {"note_gar": "inPocket"}, passed_done, True, set())
if caught["note_gar"] != "delivered" or caught_logs != ["bag.handoff.e_khomut"]:
    fail(f"a note whose pass is already behind stayed in the bag: {caught} {caught_logs}")
again_caught, _, _, again_logs = migrate(2, [], caught, passed_done, True, caught_settled)
if again_logs or again_caught["note_gar"] != "delivered":
    fail("closing a passed delivery is not idempotent")

if ahead(2, "note_gar", 12000) != ("finale", 25000):
    fail("past the Collar the note still names a place the player has left")
if ahead(2, "l1", 50) != ("s_nii_drop", 400):
    fail("Timofey's letter lost the box that is still ahead of the Saddle")

if FAILS:
    print(f"{len(FAILS)} bag check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("bag checks ok")
