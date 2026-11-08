#!/usr/bin/env python3
"""История пути: только уже сделанное, без будущей главы и чужих веток выбора."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


src = (ROOT / "Postman/App/StoryChronicle.swift").read_text(encoding="utf-8")
if "index <= activeIndex" not in src:
    fail("a chapter not yet reached must not be read")
if "event.step <= reached" not in src or "done.contains(event.id)" not in src:
    fail("an event is shown only after it has happened")
if "choices[event.id]" not in src:
    fail("a choice shows the picked result")
if "event.options" in src and "for option" in src:
    fail("unchosen branches must not be listed")
if 'line.if == nil || line.if?.isEmpty == true' not in src:
    fail("conditional lines stay out of the chronicle")
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

# Зеркало фильтра: ноль, кусок главы 1, вход в главу 2 без её событий.
def visible(done, step, reached, chapter_index, active):
    if chapter_index > active:
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
if not visible(True, 50, 200, 1, 1):
    fail("a done chapter 2 event at a reached step is part of the story")

if FAILS:
    print(f"{len(FAILS)} history check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("history checks ok")
