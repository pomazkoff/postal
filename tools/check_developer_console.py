#!/usr/bin/env python3
"""The developer console is a Release gesture on the watch, not a DEBUG-only panel."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


console = (ROOT / "Postman/UI/DeveloperConsole.swift").read_text(encoding="utf-8")
watch = (ROOT / "Postman/UI/PocketWatchView.swift").read_text(encoding="utf-8")
hud = (ROOT / "Postman/UI/HUDView.swift").read_text(encoding="utf-8")
project = (ROOT / "Postman.xcodeproj/project.pbxproj").read_text(encoding="utf-8")

if "#if DEBUG" in console:
    fail("the developer console is compiled only for DEBUG")
if "static let seconds: Double = 10" not in console:
    fail("the hidden hold is not 10 seconds")
if "WatchHoldTarget" not in watch or "onDeveloperHold" not in watch:
    fail("the watch does not own the 10 second hold")
if "StoryReset.holdSeconds" not in console and "StoryReset.holdSeconds" not in watch:
    fail("the 3 second story reset was removed from the watch")
if "showDeveloper" not in hud or "DeveloperConsole(" not in hud:
    fail("the walking screen does not present the console")
# The presentation itself must not sit inside a DEBUG branch.
present = hud.split("if showDeveloper", 1)[-1][:400]
if "#if DEBUG" in present:
    fail("the console presentation is still DEBUG-only")
for needle in ("Сбросить прогресс", "Запланированных нет", "Последние события", "CFBundleShortVersionString", "DeveloperStamp.sha"):
    if needle not in console:
        fail(f"console is missing {needle}")
if "DeveloperConsole.swift in Sources" not in project:
    fail("DeveloperConsole.swift is not in the Xcode target")

if FAILS:
    print(f"{len(FAILS)} developer console check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("developer console checks ok")
