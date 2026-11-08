#!/usr/bin/env python3
"""История: только письма основной линии главы 1, не журнал всех событий."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


src = (ROOT / "Postman/App/StoryChronicle.swift").read_text(encoding="utf-8")
if "index <= activeIndex" not in src:
    fail("a chapter not yet reached must not be read")
if "beat.step <= reached" not in src or "progress.done.contains(beat.eventID)" not in src:
    fail("a main-line paragraph waits for its own event and step")
if "for event in story.events" in src or "story.events where" in src:
    fail("history must not walk every done event")
if "story.arrivals" in src:
    fail("arrival blurbs are not the main story")
if "engine.pickup" in src or "engine.deliver" in src or "engine.sort" in src:
    fail("system pickup and delivery lines are not the narrative")
for beat in ("d_l1", "d_l2", "d_l6", "d_vera", "finale", "l1", "l2", "l3", "l4", "l5", "l6", "l7"):
    if beat not in src:
        fail(f"main-line beat {beat} is missing")
for side in ("e_cart", "e_animal", "e_ramka", "e_storm", "arrive:"):
    if side in src:
        fail(f"side event {side} was pulled into the main story")
if "progress.choices[choiceID]" not in src or "options?.first" not in src:
    fail("a letter consequence must be the recorded option only")
if "opened.contains" not in src or "item.outside" not in src:
    fail("a sealed letter must not open its inner text")
if "chapter2-timeline" not in src:
    fail("the missing chapter 2 source must stay named, not guessed")
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
