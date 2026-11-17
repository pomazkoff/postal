#!/usr/bin/env python3
"""Deeplink «Глава 3. Болота»: маршрут, фокус карты, отсутствие сдвига прогресса.

Разбор правил и исходников. Запуск на iOS здесь не делается, PASS холодного или
тёплого старта не заявляется.
"""
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
FAILS = []
fail = FAILS.append

SCHEME, HOST, EXACT = "mazkofpostman", "swamps", "mazkofpostman://swamps"
SWAMPS_START = 45000


def route(url):
    p = urlparse(url)
    return (p.scheme or "").lower() == SCHEME and (p.hostname or "").lower() == HOST and p.path in ("", "/")


def focus(global_step, start=SWAMPS_START):
    return ("hero", 0) if global_step >= start else ("ahead", max(0, start - global_step))


for ok in (EXACT, EXACT + "/", EXACT + "?ref=event", "MAZKOFPOSTMAN://SWAMPS"):
    if not route(ok):
        fail(f"must open {ok!r}")
for bad in ("mazkofpostman://first-mail", "mazkofpostman://swamps/extra", "postman://swamps",
            "https://mazkofpostman/swamps", "mazkofpostman://", ""):
    if route(bad):
        fail(f"must ignore {bad!r}")

if focus(0) != ("ahead", 45000):
    fail("fresh player sees the swamps ahead")
if focus(44999) != ("ahead", 1):
    fail("one step short is still ahead")
if focus(45000)[0] != "hero" or focus(60000)[0] != "hero":
    fail("from the chapter 3 start step the hero is shown")

world = __import__("json").loads((ROOT / "Postman/GameAssets/Data/world.json").read_text(encoding="utf-8"))
ch3 = [c for c in world["chapters"] if c["id"] == 3]
if not ch3 or ch3[0]["startStep"] != SWAMPS_START:
    fail("chapter 3 must start at 45000 in world.json")

link = (ROOT / "Postman/App/SwampsLink.swift").read_text(encoding="utf-8")
app = (ROOT / "Postman/App/PostmanApp.swift").read_text(encoding="utf-8")
delegate = (ROOT / "Postman/App/AppDelegate.swift").read_text(encoding="utf-8")
model = (ROOT / "Postman/App/GameModel.swift").read_text(encoding="utf-8")
hud = (ROOT / "Postman/UI/HUDView.swift").read_text(encoding="utf-8")
mapv = (ROOT / "Postman/UI/MapScreen.swift").read_text(encoding="utf-8")
plist = (ROOT / "Postman/Info.plist").read_text(encoding="utf-8")
pbx = (ROOT / "Postman.xcodeproj/project.pbxproj").read_text(encoding="utf-8")

if f'static let exactURL = "{EXACT}"' not in link:
    fail("exact URL missing from the parser")
if "<string>mazkofpostman</string>" not in plist:
    fail("scheme not registered")
if "game.receiveSwamps" not in app or "pullSwampsInbox" not in app:
    fail("window does not route the swamps link")
if "SwampsInbox.note(url)" not in delegate:
    fail("cold launch URL is not kept")
if pbx.count("SwampsLink.swift") < 4:
    fail("SwampsLink.swift is not in the Xcode target")

def body(src, start, end):
    return src.split(start, 1)[1].split(end, 1)[0]

for name, chunk in (
    ("receiveSwamps", body(model, "func receiveSwamps", "func pullSwampsInbox")),
    ("takeSwampsMapRequest", body(model, "func takeSwampsMapRequest", "func swampsFocus")),
    ("focusSwamps", body(mapv, "private func focusSwamps", "private func openMountain")),
    ("openSwampsMapIfReady", body(hud, "private func openSwampsMapIfReady", "// MARK: Экраны главы")),
):
    for forbidden in ("process()", "confirmSort", "jumpTo", "resetStory", "items[", "totalSteps =",
                      "chapterIndex =", "progress.", "engine.", "steps.", "forceChapter", "addSteps"):
        if forbidden in chunk:
            fail(f"{name} must not touch {forbidden}")

if "image: nil" not in body(mapv, "private func focusSwamps", "private func openMountain"):
    fail("the ahead card must not show a clear view of a place under the haze")

if FAILS:
    print(f"{len(FAILS)} swamps link check(s) failed:")
    for f in FAILS:
        print(" -", f)
    raise SystemExit(1)
print("swamps link checks ok (static; not an iOS cold/warm launch)")
