#!/usr/bin/env python3
"""Глава 2, три строки интерфейса и восемь карточек лора: связность без новых сведений.

Прямая речь «соли бы» / we could use salt и «Отряхнул — взял с собой» не переписаны.
Глава 1 этим файлом не проверяется.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
story = json.loads((ROOT / "Postman/GameAssets/Data/chapter2_story.json").read_text(encoding="utf-8"))
en = json.loads((ROOT / "Postman/GameAssets/L10n/en.json").read_text(encoding="utf-8"))
lore = json.loads((ROOT / "Postman/GameAssets/Data/resident_lore.json").read_text(encoding="utf-8"))
events = {e["id"]: e for e in story["events"]}
ee = en["stories"]["2"]["events"]
raw = (ROOT / "Postman/GameAssets/Data/chapter2_story.json").read_text(encoding="utf-8")
en_raw = (ROOT / "Postman/GameAssets/L10n/en.json").read_text(encoding="utf-8")
ui_ru = (ROOT / "Postman/Resources/ru.lproj/Localizable.strings").read_text(encoding="utf-8")
ui_en = (ROOT / "Postman/Resources/en.lproj/Localizable.strings").read_text(encoding="utf-8")
FAILS = []


def fail(msg):
    FAILS.append(msg)


must = [
    "Если отмотать назад, в ящике у НИИ найдётся маленькая посылка от Веры Мите — предохранитель на 0,25 А.",
    "Ночёвка — «где застал день».",
    "Если на Хомуте не держать темп, сразу заметёт.",
    "Есть флажок, а будка дорожника пустует.",
    "Замело, и пришлось идти низом, по осыпи,",
    "Гудит как холодильник, только громче, чем в Долине.",
    "Лента осталась позади.",
    "Он просит передать: соли бы.",
    "Передай вниз родичам в Кадушки — соли бы.",
    "Отряхнул — взял с собой.",
]
for line in must:
    if line not in raw and line not in json.dumps(lore, ensure_ascii=False):
        fail(f"missing {line}")

if "Если отмотать ленту назад" in raw:
    fail("p_l2 must not invent the tape")
if "Дорогу замело" in raw:
    fail("wait result must stay impersonal")
if "Здесь ночуют" in raw:
    fail("the stump-camp saying must stay a saying")
if "we could use salt" not in en_raw:
    fail("ranger's own words were rewritten")
if "they could use salt" not in en_raw:
    fail("lore must keep the salt formula")
if "he could use some salt" in en_raw:
    fail("salt formula was unpacked")
if "The tape is behind you." not in ee["finale"]["lines"][2]["text"]:
    fail("finale must keep the existing tape wording")

if "Вскрыто: %@. На печати есть второй отпечаток." not in ui_ru:
    fail("opened line lost the placeholder")
if "Opened: %@. There's a second print on the seal." not in ui_en:
    fail("EN opened line lost the placeholder")
if "ТЧК" not in lore["pimen"]["lines"][1] or "STOP" not in en["lore"]["pimen"]["lines"][1]:
    fail("Pimen's STOP habit was expanded away")
if not lore["mitya"]["lines"][1].endswith("Приём."):
    fail("Mitya's Over was dropped")

# ids of edited events still present
for eid in ("p_l1", "p_l2", "e_animal_raven", "s_nii_drop", "e_windfall", "arrive_gar",
            "arrive_penki", "e_khomut", "arrive_repka", "e_krivulya_tempo", "p_l9", "finale"):
    if eid not in events or eid not in ee:
        fail(f"missing {eid}")

if FAILS:
    print(f"{len(FAILS)} chapter 2 copy check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("chapter 2 / UI / lore copy checks ok")
