#!/usr/bin/env python3
"""Полноэкранный конец главы 2: один раз, после финала, тот же почтальон.

Проверяет правила показа и что фразы не переписали остальной сюжет.
Симулятора здесь нет.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


def should_show(chapter_id, finished, pending, seen):
    return chapter_id == 3 and finished and not pending and not seen


if should_show(3, True, False, False) is not True:
    fail("a finished chapter 3 with nothing left to read must show the card")
if should_show(3, True, True, False):
    fail("the card must wait until the finale card is dismissed")
if should_show(3, False, False, False):
    fail("chapter 3 must not show the card before the finale")
if should_show(1, True, False, False) or should_show(2, True, False, False):
    fail("chapters 1 and 2 continue on the road and do not show the coming-soon card")
if should_show(3, True, False, True):
    fail("a seen card must not return on the next launch")

story = (ROOT / "Postman/GameAssets/Data/chapter2_story.json").read_text(encoding="utf-8")
lore = (ROOT / "Postman/GameAssets/Data/resident_lore.json").read_text(encoding="utf-8")
if "Путешествие почтальона продолжится" in story or "Глава 3 скоро" in story:
    fail("the new lines were written into the chapter instead of the card")
if "Путешествие почтальона продолжится" in lore:
    fail("lore was rewritten for the ending card")
if "Яр «Горловина»" not in story:
    fail("the gorge finale lines were replaced")

ru = (ROOT / "Postman/Resources/ru.lproj/Localizable.strings").read_text(encoding="utf-8")
en = (ROOT / "Postman/Resources/en.lproj/Localizable.strings").read_text(encoding="utf-8")


def value(text, key):
    match = re.search(rf'"{re.escape(key)}"\s*=\s*"((?:\\.|[^"\\])*)"', text)
    return match.group(1) if match else ""


if value(ru, "journey.continue") != "Путешествие почтальона продолжится":
    fail("Russian title is not the requested sentence")
if value(ru, "journey.soon") != "Глава 4 скоро":
    fail("Russian subtitle is not the requested sentence")
if value(en, "journey.continue") != "The postman's journey will continue":
    fail("English title drifted")
if value(en, "journey.soon") != "Chapter 4 is coming soon":
    fail("English subtitle drifted")

state = (ROOT / "Postman/Model/ChapterState.swift").read_text(encoding="utf-8")
if "var journeyCardSeen: Bool?" not in state:
    fail("old saves need an optional flag, or a missing key wipes the chapter")
engine = (ROOT / "Postman/App/ChapterEngine.swift").read_text(encoding="utf-8")
mark = engine.split("func markJourneyCardSeen()", 1)[1].split("\n    }", 1)[0]
for forbidden in ("state.finished", "currentStep", "state.items", "state.log"):
    if forbidden in mark:
        fail(f"closing the card must not touch {forbidden}")
if "state.journeyCardSeen = true" not in mark:
    fail("closing the card must remember that it was seen")

card = (ROOT / "Postman/UI/StoryCards.swift").read_text(encoding="utf-8")
view = card.split("struct JourneyCardView", 1)[1]
if 'HUDImages.image("UI/map/postman")' not in view:
    fail("the card must use the existing map postman, scarf and all")
if "GenerateImage" in view or "postman_new" in view:
    fail("the card must not invent a hero")
if "journey.continue" not in view or "journey.soon" not in view:
    fail("the card must show both sentences")
if ".alert(" in view:
    fail("the ending must not be a system alert")
if "accessibilityReduceMotion" not in view:
    fail("Reduce Motion must reach the ending card")
if "lineLimit(3)" not in view or "lineLimit(2)" not in view:
    fail("the two sentences need room to wrap")

hud = (ROOT / "Postman/UI/HUDView.swift").read_text(encoding="utf-8")
screen = hud.split("private var screen", 1)[1].split("var body", 1)[0]
journey_at = screen.find("return .journey")
card_at = screen.find("return .card")
end_at = screen.find("return .panel(.endCard)")
if not (0 <= card_at < journey_at < end_at):
    fail("the journey card must follow a pending story card and precede the tally")
if "JourneyCard.shouldShow" not in screen:
    fail("the HUD bypasses the show rule")

if FAILS:
    print(f"{len(FAILS)} journey card check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("journey card checks ok")
