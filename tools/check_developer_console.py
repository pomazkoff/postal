#!/usr/bin/env python3
"""The developer console is a hidden 10 s watch hold.

It must compile into Release (same binary can go from TestFlight to the App Store) and
open only when DeveloperAccess says so: DEBUG, the simulator, or a sandbox receipt
(TestFlight). A production App Store receipt must not open it.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


console = (ROOT / "Postman/UI/DeveloperConsole.swift").read_text(encoding="utf-8")
watch = (ROOT / "Postman/UI/PocketWatchView.swift").read_text(encoding="utf-8")
hud = (ROOT / "Postman/UI/HUDView.swift").read_text(encoding="utf-8")
core = (ROOT / "Postman/App/AppCore.swift").read_text(encoding="utf-8")
project = (ROOT / "Postman.xcodeproj/project.pbxproj").read_text(encoding="utf-8")

if "#if DEBUG" in console.split("struct DeveloperConsole", 1)[-1]:
    fail("the developer console UI is compiled only for DEBUG")
if "enum DeveloperAccess" not in console:
    fail("DeveloperAccess is missing")
if 'appStoreReceiptURL?.lastPathComponent == "sandboxReceipt"' not in console:
    fail("DeveloperAccess does not recognize the TestFlight sandbox receipt")
if "targetEnvironment(simulator)" not in console:
    fail("DeveloperAccess does not allow the simulator")
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
opener = hud.split("private func openDeveloper()", 1)[-1][:400]
if "DeveloperAccess.isAvailable" not in opener or "showDeveloper = true" not in opener:
    fail("openDeveloper does not gate on DeveloperAccess")
if "#if DEBUG" in opener:
    fail("openDeveloper is still DEBUG-only and would hide the console from TestFlight")
if "DeveloperAccess.isAvailable" not in core:
    fail("AppCore does not keep chapter jumps when the console is available")
if "forceChapterIndex = nil" in core.split("private init()", 1)[-1].split("let startIndex", 1)[0]:
    init = core.split("private init()", 1)[-1].split("let startIndex", 1)[0]
    if "if !DeveloperAccess.isAvailable" not in init:
        fail("AppCore still clears forced chapters in every Release build, including TestFlight")
for needle in ("Сбросить прогресс", "Запланированных нет", "Последние события", "CFBundleShortVersionString", "DeveloperStamp.sha"):
    if needle not in console:
        fail(f"console is missing {needle}")
if "game.world.chapters" not in console or "developerGo(chapterIndex:" not in console:
    fail("the console does not offer a jump to each world chapter")
if "DeveloperConsole.swift in Sources" not in project:
    fail("DeveloperConsole.swift is not in the Xcode target")

if FAILS:
    print(f"{len(FAILS)} developer console check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("developer console checks ok")
