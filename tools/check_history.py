#!/usr/bin/env python3
"""История: связный пересказ основной линии, не письма и не журнал событий."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


src = (ROOT / "Postman/App/StoryChronicle.swift").read_text(encoding="utf-8")
if "index <= activeIndex" not in src:
    fail("a chapter not yet reached must not be read")
if "beat.step <= gate" not in src or "progress.done.contains(beat.eventID)" not in src:
    fail("a main-line paragraph waits for its own event and step")
if "for event in story.events" in src or "item.text" in src:
    fail("history must not dump events or reprint letters")
if "story.arrivals" in src or "engine.pickup" in src or "engine.deliver" in src:
    fail("arrivals and system lines are not the narrative")
for beat in ("\"road\"", "\"strange\"", "\"two\"", "\"roosters\"", "\"lamp\"", "d_l6", "p_l1", "p_l4", "p_l9"):
    if beat not in src:
        fail(f"main-line gate {beat} is missing")
for side in ("e_cart", "e_animal", "e_ramka", "e_storm"):
    if side in src:
        fail(f"side event {side} was pulled into the main story")
if 'choices["e_wind"]' not in src:
    fail("the wind paragraph must follow the recorded choice")
if 'opened.contains("l5")' not in src:
    fail("Pimen's inner tape waits until the seal is opened")
if "history.main.belfry.fortyone" not in src:
    fail("the number 41 is only the outside of the account")
if "chapterID: 3" in src or "chapterID: 4" in src or "chapterID: 5" in src:
    fail("chapters 3–5 are not part of the playable history")
for banned in ("Агния", "Савелий", "хвостохранилищ", "включила К-2", "214 подпис"):
    if banned in src:
        fail(f"author secret leaked into the chronicle code: {banned}")
hud = (ROOT / "Postman/UI/HUDView.swift").read_text(encoding="utf-8")
if "HistoryScrollView" not in hud or "showHistory" not in hud:
    fail("the history sheet must open from the road")
view = (ROOT / "Postman/UI/HistoryScrollView.swift").read_text(encoding="utf-8")
if "scaledToFill" in view:
    fail("illustrations must not be cropped to fill")
if "width / image.size.height >= 0.7" not in view:
    fail("a narrow place cutout must not fill the sheet")
if "historyAnchor" not in view:
    fail("closing the sheet should keep the scroll position")
if "history.empty" not in view:
    fail("a new game needs an empty state")
if "history.where" in view:
    fail("the history sheet must not print place and step headers")
if "sheet" in view.split("struct HistoryScrollView", 1)[-1].split("struct ", 1)[0]:
    fail("the history page must be plain paper, without the gridded sheet")

ru = (ROOT / "Postman/Resources/ru.lproj/Localizable.strings").read_text(encoding="utf-8")
en = (ROOT / "Postman/Resources/en.lproj/Localizable.strings").read_text(encoding="utf-8")
keys = [
    "history.main.road.out", "history.main.strange.body", "history.main.two.body",
    "history.main.roosters.body", "history.main.lamp.compared", "history.main.belfry.opened",
    "history.main.gorge.body",
]
for key in keys:
    if f'"{key}"' not in ru or f'"{key}"' not in en:
        fail(f"missing narrative string {key}")
blob = "\n".join(line for line in (ru + "\n" + en).splitlines() if "history.main." in line)
for banned in ("Агния", "Савелий", "хвостохранилищ", "включила К-2", "Agnia forged", "Vera switched"):
    if banned in blob:
        fail(f"author secret in the history strings: {banned}")
if not (ROOT / "docs/canon/story-bible.md").exists():
    fail("the canon file was not kept with the repo")
if "она получить не могла" in ru:
    fail("box 2 still says Nina could not receive her own letter")
if "письмо Нины сыну всё ещё лежало" not in ru:
    fail("box 2 must say Nina's letter to her son was still in the bag")

# Зеркало фильтра: ноль, кусок главы 1, вход в главу 2 без её событий.
def visible(done, step, reached, chapter_index, active):
    if chapter_index > active or chapter_index > 0:
        return False
    return step <= reached and done


if visible(True, 100, 0, 0, 0):
    fail("zero progress must hide a later event")
if not visible(True, 100, 500, 0, 0):
    fail("a reached done event stays")
if visible(False, 100, 500, 0, 0):
    fail("walking past a step is not the same as the event having happened")
if visible(True, 50, 99999, 1, 0):
    fail("chapter 2 text must not appear just because chapter 1 is open")
if visible(True, 50, 200, 1, 1):
    fail("a done chapter 2 event is not a main-line paragraph; that timeline is not in the repo")

if "e.width - top.x" not in hud:
    fail("flipping the history tag must move the label onto the mirrored paper")
if "scaleEffect(x: flipX ? -1 : 1" not in (ROOT / "Postman/UI/UIArt.swift").read_text(encoding="utf-8"):
    fail("the tag image is what flips; the letters stay upright")

# Якорь line1 бирки tag_small после отражения вокруг центра картинки.
tag = {"width": 287, "line1": 139.0, "text": 168.0, "body": (24, 24, 199, 105)}
mirrored = tag["width"] - tag["line1"]
text_left = mirrored - tag["text"] / 2
text_right = mirrored + tag["text"] / 2
body_left = tag["width"] - (tag["body"][0] + tag["body"][2])
body_right = tag["width"] - tag["body"][0]
if text_left < body_left - 1 or text_right > body_right + 1:
    fail("mirrored history label leaves the paper")

logic = (ROOT / "Postman/App/MenuLogic.swift").read_text(encoding="utf-8")
if "func arrowBottom" not in logic or "FrameEdges" not in view:
    fail("close must rise on a short phone and above the home indicator")


def arrow_bottom(visible_bottom, safe_design, preferred):
    return min(preferred, visible_bottom - max(0, safe_design) - 16)


if arrow_bottom(2532, 0, 2470) != 2470:
    fail("a full frame without a home indicator keeps the history close button")
if arrow_bottom(2532, 102, 2470) >= 2470:
    fail("the home indicator must lift the close button")
if arrow_bottom(2306, 0, 2470) > 2306 - 16:
    fail("a short phone must keep close inside the visible frame")

if FAILS:
    print(f"{len(FAILS)} history check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("history checks ok")
